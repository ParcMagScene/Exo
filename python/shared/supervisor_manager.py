"""EXO v9 — Supervisor: health checks, watchdog, intelligent restart."""

import asyncio
import json
import logging
import time
import threading
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import websockets
except ImportError:
    websockets = None  # type: ignore[assignment]


class ServiceHealth(Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class OverallHealth(Enum):
    UNKNOWN = "unknown"
    ALL_HEALTHY = "all_healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class ServiceState:
    __slots__ = (
        "name", "port", "url", "health", "last_check",
        "latency_ms", "error", "consecutive_failures",
        "restart_count",
    )

    def __init__(self, name: str, port: int):
        self.name = name
        self.port = port
        self.url = f"ws://localhost:{port}"
        self.health = ServiceHealth.UNKNOWN
        self.last_check: float = 0.0
        self.latency_ms: float = 0.0
        self.error: Optional[str] = None
        self.consecutive_failures: int = 0
        self.restart_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "port": self.port,
            "health": self.health.value,
            "latency_ms": round(self.latency_ms, 1),
            "consecutive_failures": self.consecutive_failures,
            "restart_count": self.restart_count,
            "error": self.error,
        }


class SupervisorManager:
    """Monitors all EXO microservices, detects failures, triggers restarts."""

    _instance: Optional["SupervisorManager"] = None

    def __init__(self, *, check_interval_s: float = 10.0,
                 ping_timeout_s: float = 5.0,
                 degraded_latency_ms: float = 2000.0,
                 max_restart_attempts: int = 3):
        self.check_interval_s = check_interval_s
        self.ping_timeout_s = ping_timeout_s
        self.degraded_latency_ms = degraded_latency_ms
        self.max_restart_attempts = max_restart_attempts

        self._services: dict[str, ServiceState] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._log = None  # LogManager, set externally
        self._metrics = None  # MetricsManager, set externally
        self._restart_callback = None  # async callback(service_name)
        self._incident_log: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    @classmethod
    def instance(cls, **kwargs) -> "SupervisorManager":
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def set_log(self, log) -> None:
        self._log = log

    def set_metrics(self, metrics) -> None:
        self._metrics = metrics

    def set_restart_callback(self, callback) -> None:
        self._restart_callback = callback

    def register_service(self, name: str, port: int) -> None:
        self._services[name] = ServiceState(name, port)

    def register_services_from_config(self, services: list[dict]) -> None:
        for svc in services:
            name = svc.get("name", "")
            port = svc.get("port", 0)
            if name and port:
                self.register_service(name.lower(), port)

    # ── health check ─────────────────────────────────────────────
    async def check_service(self, state: ServiceState) -> None:
        if websockets is None:
            state.health = ServiceHealth.UNKNOWN
            return
        t0 = time.monotonic()
        try:
            async with websockets.connect(
                state.url,
                open_timeout=self.ping_timeout_s,
                close_timeout=2,
            ) as ws:
                await ws.send(json.dumps({"type": "ping"}))
                resp = await asyncio.wait_for(
                    ws.recv(), timeout=self.ping_timeout_s
                )
                latency = (time.monotonic() - t0) * 1000
                state.latency_ms = latency
                state.last_check = time.time()
                state.error = None
                if latency > self.degraded_latency_ms:
                    state.health = ServiceHealth.DEGRADED
                else:
                    state.health = ServiceHealth.HEALTHY
                state.consecutive_failures = 0
        except Exception as exc:
            state.latency_ms = (time.monotonic() - t0) * 1000
            state.last_check = time.time()
            state.health = ServiceHealth.DOWN
            state.error = str(exc)
            state.consecutive_failures += 1

    async def check_all(self) -> dict[str, Any]:
        tasks = [self.check_service(s) for s in self._services.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

        for state in self._services.values():
            if state.health == ServiceHealth.DOWN:
                self._record_incident(state)
                if (state.consecutive_failures >= 3 and
                        state.restart_count < self.max_restart_attempts):
                    await self._try_restart(state)

        return self.status()

    def status(self) -> dict[str, Any]:
        services = {n: s.to_dict() for n, s in self._services.items()}
        overall = self._compute_overall()
        return {
            "overall": overall.value,
            "services": services,
            "ts": time.time(),
        }

    def _compute_overall(self) -> OverallHealth:
        if not self._services:
            return OverallHealth.UNKNOWN
        healths = [s.health for s in self._services.values()]
        if all(h == ServiceHealth.HEALTHY for h in healths):
            return OverallHealth.ALL_HEALTHY
        if any(h == ServiceHealth.DOWN for h in healths):
            return OverallHealth.CRITICAL
        if any(h in (ServiceHealth.DEGRADED, ServiceHealth.UNKNOWN) for h in healths):
            return OverallHealth.DEGRADED
        return OverallHealth.ALL_HEALTHY

    # ── watchdog / restart ───────────────────────────────────────
    async def _try_restart(self, state: ServiceState) -> None:
        if self._log:
            self._log.warn(f"Attempting restart: {state.name}",
                           {"port": state.port, "failures": state.consecutive_failures})
        if self._restart_callback:
            try:
                await self._restart_callback(state.name)
                state.restart_count += 1
                state.consecutive_failures = 0
            except Exception as exc:
                if self._log:
                    self._log.error(f"Restart failed: {state.name}", exc=exc)

    def _record_incident(self, state: ServiceState) -> None:
        incident = {
            "ts": time.time(),
            "service": state.name,
            "health": state.health.value,
            "error": state.error,
            "consecutive_failures": state.consecutive_failures,
        }
        with self._lock:
            self._incident_log.append(incident)
            if len(self._incident_log) > 500:
                self._incident_log = self._incident_log[-500:]
        if self._log:
            self._log.warn(f"Service incident: {state.name}", incident)
        if self._metrics:
            self._metrics.counter(f"supervisor.incidents.{state.name}").inc()

    # ── lifecycle ────────────────────────────────────────────────
    async def start(self) -> None:
        self._running = True
        self._task = asyncio.ensure_future(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.check_all()
            except Exception:
                logger.warning("Supervisor check_all failed", exc_info=True)
            await asyncio.sleep(self.check_interval_s)

    def get_incidents(self, n: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._incident_log[-n:])

    def get_service_health(self, name: str) -> Optional[dict[str, Any]]:
        s = self._services.get(name)
        return s.to_dict() if s else None
