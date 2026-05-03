"""EXO v9 — Resilience decorators: retry, timeout, fallback, circuit breaker."""

import asyncio
import functools
import time
from typing import Any, Callable, Optional


class CircuitBreaker:
    """Simple circuit breaker: CLOSED → OPEN after N failures, HALF_OPEN after cooldown."""

    def __init__(self, failure_threshold: int = 5, cooldown_s: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self._failures = 0
        self._state = "closed"  # closed | open | half_open
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> str:
        if self._state == "open":
            if time.monotonic() - self._last_failure_time >= self.cooldown_s:
                self._state = "half_open"
        return self._state

    def record_success(self) -> None:
        self._failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failures += 1
        self._last_failure_time = time.monotonic()
        if self._failures >= self.failure_threshold:
            self._state = "open"

    @property
    def is_open(self) -> bool:
        return self.state == "open"


# Registry of circuit breakers per module
_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(module: str, **kwargs) -> CircuitBreaker:
    if module not in _breakers:
        _breakers[module] = CircuitBreaker(**kwargs)
    return _breakers[module]


def resilient(module: str, *,
              retries: int = 1,
              backoff: float = 0.3,
              timeout_s: Optional[float] = None,
              fallback: Optional[Callable] = None,
              circuit_breaker: bool = False):
    """Combined resilience decorator for async functions.

    Args:
        module: Service name (for breaker key + logging).
        retries: Max retry attempts.
        backoff: Initial backoff seconds (doubled each retry).
        timeout_s: Per-attempt timeout.
        fallback: Fallback async/sync callable on final failure.
        circuit_breaker: Enable circuit breaker pattern.
    """

    def decorator(fn):
        breaker = get_breaker(module) if circuit_breaker else None

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            if breaker and breaker.is_open:
                if fallback is not None:
                    return await _call(fallback, *args, **kwargs)
                raise RuntimeError(f"Circuit open for {module}")

            last_exc = None
            for attempt in range(retries + 1):
                try:
                    coro = fn(*args, **kwargs)
                    if timeout_s:
                        result = await asyncio.wait_for(coro, timeout=timeout_s)
                    else:
                        result = await coro
                    if breaker:
                        breaker.record_success()
                    return result
                except Exception as exc:
                    last_exc = exc
                    if breaker:
                        breaker.record_failure()
                    if attempt < retries:
                        await asyncio.sleep(backoff * (2 ** attempt))

            if fallback is not None:
                return await _call(fallback, *args, **kwargs)
            raise last_exc  # type: ignore[misc]

        return wrapper
    return decorator


async def _call(fn, *args, **kwargs):
    if asyncio.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    return fn(*args, **kwargs)
