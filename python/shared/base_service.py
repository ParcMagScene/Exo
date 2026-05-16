"""EXO v9.1 — BaseService: unified foundation for all microservices.

Integrates: LogManager, MetricsManager, TraceManager, ErrorManager,
SecurityManager, ConfigManager, health check endpoint.

v9.1 additions:
- WS serve helper with native ping/pong (20s interval, 5s timeout)
- retry_send() with 3× backoff 200ms
- Per-service CircuitBreaker (open after 3 consecutive errors)
- orjson fast-path for JSON serialization
"""

import asyncio
import time
from typing import Any, Optional

from .log_manager import LogManager
from .metrics_manager import MetricsManager
from .trace_manager import TraceManager
from .error_manager import ErrorManager, ExoError
from .security_manager import SecurityManager
from .config_manager import ConfigManager
from .singleton_guard import ensure_single_instance
from .resilience import CircuitBreaker

# ── Fast JSON ────────────────────────────────────────────────
try:
    import orjson as _orjson

    def json_loads(raw):
        return _orjson.loads(raw)

    def json_dumps(obj, **kw):
        opts = _orjson.OPT_NON_STR_KEYS
        return _orjson.dumps(obj, option=opts).decode()

except ImportError:
    try:
        import ujson as _ujson  # v6.0 perf : 3-5x plus rapide que stdlib (Python free-threaded)

        def json_loads(raw):
            return _ujson.loads(raw)

        def json_dumps(obj, **kw):
            return _ujson.dumps(obj, **kw)

    except ImportError:
        import json as _json

        def json_loads(raw):
            return _json.loads(raw)

        def json_dumps(obj, **kw):
            return _json.dumps(obj, ensure_ascii=False, default=str, **kw)


# ── WS defaults (RAM-opt v9 : valeurs cibles, surchargeables via config exo_v9.json) ──
WS_PING_INTERVAL = 20   # seconds between pings
WS_PING_TIMEOUT  = 10   # seconds to wait for pong before closing
# WS_MAX_SIZE / WS_BUFFER_SIZE : valeurs par défaut = profil RAM 64 Go.
# Surchargées au runtime depuis ConfigManager (ws.maxMessageSize / ws.bufferSize).
WS_MAX_SIZE      = 8 * 1024 * 1024   # 8 MB max message size (RAM-opt)
WS_BUFFER_SIZE   = 4 * 1024 * 1024   # 4 MB socket write buffer (RAM-opt)
WS_RETRY_COUNT   = 3
WS_RETRY_BACKOFF = 0.2  # seconds (doubled each attempt)
WS_RETRY_MAX_BACKOFF = 0.4  # v6.0 perf audit : cap exp backoff (voice pipeline must not stall)


def _ws_runtime_limits() -> tuple[int, int]:
    """Read ws.maxMessageSize / ws.bufferSize from ConfigManager if available.

    Falls back silently to module defaults if config is not loaded yet
    (e.g. very early in a service bootstrap or in tests).
    """
    try:
        cfg = ConfigManager.instance()
        max_size = int(cfg.get("ws.maxMessageSize", cfg.get("ws.max_message_size", WS_MAX_SIZE)))
        buf_size = int(cfg.get("ws.bufferSize", cfg.get("ws.buffer_size", WS_BUFFER_SIZE)))
        return max_size, buf_size
    except Exception:
        return WS_MAX_SIZE, WS_BUFFER_SIZE
CB_FAILURE_THRESHOLD = 3
CB_COOLDOWN_S = 15.0


class BaseService:
    """Base class that every EXO microservice can compose or inherit.

    Provides structured logging, metrics, tracing, error handling,
    security, config, circuit breaker, and a standard health-check
    WebSocket response.
    """

    def __init__(self, name: str, port: int, *, init_config: bool = True):
        self.name = name
        self.port = port
        self._start_time = time.monotonic()

        # ── v9 modules ───────────────────────────────────────────
        self.log = LogManager.get(name)
        self.metrics = MetricsManager(name)
        self.traces = TraceManager(name)
        self.errors = ErrorManager.instance()
        self.errors.set_metrics(self.metrics)
        self.security = SecurityManager.instance()

        if init_config:
            self.config = ConfigManager.instance()
        else:
            self.config = None

        # ── v9.1: per-service circuit breaker ────────────────────
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=CB_FAILURE_THRESHOLD,
            cooldown_s=CB_COOLDOWN_S,
        )

        self.log.info(f"Service {name} initializing on port {port}")

    # ── health check ─────────────────────────────────────────────
    def health_check(self) -> dict[str, Any]:
        uptime = time.monotonic() - self._start_time
        return {
            "type": "health",
            "service": self.name,
            "status": "ok" if not self.circuit_breaker.is_open else "degraded",
            "uptime_s": round(uptime, 1),
            "circuit_breaker": self.circuit_breaker.state,
            "metrics": {
                "requests": self.metrics.counter("requests_total").value,
                "errors": self.metrics.counter("errors_total").value,
            },
        }

    # ── WebSocket message handler ────────────────────────────────
    async def handle_ws_message(self, ws, raw: str) -> Optional[str]:
        """Handle standard v9 protocol messages.

        Returns JSON response string, or None if not a v9 message.
        """
        try:
            msg = json_loads(raw)
        except (ValueError, TypeError):
            return None

        msg_type = msg.get("type") or msg.get("action", "")

        if msg_type == "ping":
            return json_dumps({"type": "pong"})

        if msg_type == "health":
            return json_dumps(self.health_check())

        if msg_type == "metrics":
            return json_dumps({"type": "metrics", **self.metrics.snapshot()})

        if msg_type == "traces":
            n = msg.get("count", 20)
            return json_dumps({"type": "traces", "traces": self.traces.recent(n)})

        if msg_type == "errors":
            n = msg.get("count", 20)
            return json_dumps({"type": "errors",
                               "errors": self.errors.recent_errors(n)})

        return None

    # ── retry send ───────────────────────────────────────────────
    async def retry_send(self, ws, data: str | bytes, *,
                         retries: int = WS_RETRY_COUNT,
                         backoff: float = WS_RETRY_BACKOFF,
                         max_backoff: float = WS_RETRY_MAX_BACKOFF) -> bool:
        """Send with retry + exponential backoff (capped). Returns True on success."""
        for attempt in range(retries + 1):
            try:
                await ws.send(data)
                self.circuit_breaker.record_success()
                return True
            except Exception as exc:
                self.circuit_breaker.record_failure()
                if attempt < retries:
                    # v6.0 perf audit : cap exp backoff a max_backoff (default 0.4s)
                    # pour eviter un stall de 0.8s/1.6s sur le pipeline vocal.
                    delay = min(backoff * (2 ** attempt), max_backoff)
                    await asyncio.sleep(delay)
                else:
                    self.log.warning("retry_send exhausted (%d attempts): %s",
                                     retries + 1, exc)
                    return False

    # ── request instrumentation ──────────────────────────────────
    def begin_request(self, request_id: Optional[str] = None) -> str:
        rid = request_id or LogManager.new_request_id()
        LogManager.set_request_id(rid)
        self.metrics.counter("requests_total").inc()
        self._req_start = time.monotonic()
        return rid

    def end_request(self, request_id: Optional[str] = None, *, error: bool = False) -> float:
        """End request, returns elapsed ms."""
        elapsed_ms = (time.monotonic() - getattr(self, '_req_start', time.monotonic())) * 1000
        if error:
            self.metrics.counter("errors_total").inc()
            self.circuit_breaker.record_failure()
        else:
            self.circuit_breaker.record_success()
        hist = self.metrics.histogram("request_latency_s")
        hist.observe(elapsed_ms / 1000)
        return elapsed_ms

    # ── WS serve helper ──────────────────────────────────────────
    def ws_serve_kwargs(self, **overrides) -> dict:
        """Return standard websockets.serve kwargs with keepalive.

        RAM-opt v9 : ``max_size`` lu depuis ConfigManager
        (ws.maxMessageSize) si dispo, sinon defaults module.
        Note: ``write_limit`` / ``read_limit`` ne sont pas accept\u00e9s par
        ``websockets.asyncio.server.serve`` -> on s'en tient \u00e0 ``max_size``.
        """
        max_size, _buf_size = _ws_runtime_limits()
        defaults = {
            "ping_interval": WS_PING_INTERVAL,
            "ping_timeout": WS_PING_TIMEOUT,
            "max_size": max_size,
        }
        defaults.update(overrides)
        return defaults

    # ── lifecycle ────────────────────────────────────────────────
    def on_shutdown(self) -> None:
        self.log.info(f"Service {self.name} shutting down")
        self.traces.export_json()


def init_v9(service_name: str, port: int, *,
            init_config: bool = True) -> BaseService:
    """One-liner to initialize all v9 infrastructure for a microservice."""
    return BaseService(service_name, port, init_config=init_config)
