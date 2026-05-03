"""EXO v9 — Unified error handling: categories, retry, fallback, degradation."""

import asyncio
import enum
import functools
import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ErrorCategory(enum.Enum):
    AUDIO = "AudioError"
    LLM = "LLMError"
    TOOL = "ToolError"
    NETWORK = "NetworkError"
    IOT = "IoTError"
    STT = "STTError"
    TTS = "TTSError"
    CONFIG = "ConfigError"
    SECURITY = "SecurityError"
    INTERNAL = "InternalError"


class ExoError(Exception):
    """Base exception for all EXO errors."""

    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.INTERNAL,
                 recoverable: bool = True, context: Optional[dict] = None):
        super().__init__(message)
        self.category = category
        self.recoverable = recoverable
        self.context = context or {}
        self.timestamp = time.time()


class AudioError(ExoError):
    def __init__(self, message: str, **kw):
        super().__init__(message, ErrorCategory.AUDIO, **kw)


class LLMError(ExoError):
    def __init__(self, message: str, **kw):
        super().__init__(message, ErrorCategory.LLM, **kw)


class ToolError(ExoError):
    def __init__(self, message: str, **kw):
        super().__init__(message, ErrorCategory.TOOL, **kw)


class NetworkError(ExoError):
    def __init__(self, message: str, **kw):
        super().__init__(message, ErrorCategory.NETWORK, **kw)


class IoTError(ExoError):
    def __init__(self, message: str, **kw):
        super().__init__(message, ErrorCategory.IOT, **kw)


# ── Retry policies ───────────────────────────────────────────────

RETRY_POLICIES: dict[str, dict[str, Any]] = {
    "stt":        {"retries": 1, "backoff": 0.3},
    "tts":        {"retries": 1, "backoff": 0.3},
    "llm":        {"retries": 2, "backoff": 0.5},
    "tools":      {"retries": 1, "backoff": 0.2},
    "domotique":  {"retries": 2, "backoff": 0.3},
    "network":    {"retries": 1, "backoff": 0.5},
}

# ── Timeout policies ────────────────────────────────────────────

TIMEOUT_POLICIES: dict[str, float] = {
    "stt": 3.0,
    "llm": 10.0,
    "tts": 3.0,
    "tools": 5.0,
    "domotique": 3.0,
    "network": 5.0,
}


class ErrorManager:
    """Centralized error handling with retry/fallback strategies."""

    _instance: Optional["ErrorManager"] = None

    def __init__(self):
        self._handlers: dict[ErrorCategory, list[Callable]] = {}
        self._fallbacks: dict[str, Callable] = {}
        self._error_log: list[dict[str, Any]] = []
        self._metrics = None  # set externally

    @classmethod
    def instance(cls) -> "ErrorManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def set_metrics(self, metrics) -> None:
        self._metrics = metrics

    def register_fallback(self, module: str, fallback_fn: Callable) -> None:
        self._fallbacks[module] = fallback_fn

    def register_handler(self, category: ErrorCategory, handler: Callable) -> None:
        self._handlers.setdefault(category, []).append(handler)

    def handle(self, error: ExoError) -> Optional[Any]:
        """Process an error: log, metric, invoke handlers, try fallback."""
        entry = {
            "ts": error.timestamp,
            "category": error.category.value,
            "msg": str(error),
            "recoverable": error.recoverable,
            "context": error.context,
        }
        self._error_log.append(entry)
        if len(self._error_log) > 500:
            self._error_log = self._error_log[-500:]

        if self._metrics:
            self._metrics.counter("errors_total").inc()
            self._metrics.counter(f"errors.{error.category.value}").inc()

        for handler in self._handlers.get(error.category, []):
            try:
                handler(error)
            except Exception:
                logger.warning("Error handler failed for %s", error.category, exc_info=True)

        return None

    def recent_errors(self, n: int = 20) -> list[dict[str, Any]]:
        return list(self._error_log[-n:])


# ── Decorators ───────────────────────────────────────────────────

def with_retry(module: str, fallback: Optional[Callable] = None):
    """Decorator for async functions: retry with backoff, then fallback."""
    policy = RETRY_POLICIES.get(module, {"retries": 1, "backoff": 0.3})
    max_retries = policy["retries"]
    backoff = policy["backoff"]

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        await asyncio.sleep(backoff * (2 ** attempt))
            if fallback is not None:
                try:
                    return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
                except Exception:
                    logger.warning("Fallback for %s failed", fn.__name__, exc_info=True)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


def with_timeout(module: str):
    """Decorator for async functions: enforce timeout from TIMEOUT_POLICIES."""
    timeout_s = TIMEOUT_POLICIES.get(module, 5.0)

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(fn(*args, **kwargs), timeout=timeout_s)
        return wrapper
    return decorator


def with_fallback(primary_fn, fallback_fn):
    """Run primary; on failure run fallback."""
    @functools.wraps(primary_fn)
    async def wrapper(*args, **kwargs):
        try:
            return await primary_fn(*args, **kwargs)
        except Exception:
            if asyncio.iscoroutinefunction(fallback_fn):
                return await fallback_fn(*args, **kwargs)
            return fallback_fn(*args, **kwargs)
    return wrapper
