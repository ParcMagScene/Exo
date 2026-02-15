"""utils.py - Utilitaires communs pour l'assistant."""

import asyncio
import logging
import time
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)


def async_timed(func: Callable) -> Callable:
    """Décorateur pour mesurer le temps d'exécution async."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = await func(*args, **kwargs)
            elapsed = (time.time() - start) * 1000
            if elapsed > 100:  # Log si > 100ms
                logger.debug(f"⏱️ {func.__name__} pris {elapsed:.0f}ms")
            return result
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.error(f"❌ {func.__name__} erreur après {elapsed:.0f}ms: {e}")
            raise
    return wrapper


def sync_timed(func: Callable) -> Callable:
    """Décorateur pour mesurer le temps d'exécution sync."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = (time.time() - start) * 1000
            if elapsed > 100:
                logger.debug(f"⏱️ {func.__name__} pris {elapsed:.0f}ms")
            return result
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.error(f"❌ {func.__name__} erreur après {elapsed:.0f}ms: {e}")
            raise
    return wrapper


async def run_with_timeout(coro, timeout_ms: float) -> Any:
    """Exécute une coroutine avec timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_ms / 1000)
    except asyncio.TimeoutError:
        logger.warning(f"⏱️ Timeout après {timeout_ms}ms")
        return None


def format_latency(ms: float) -> str:
    """Formate une latence en ms."""
    if ms < 1:
        return f"{ms * 1000:.0f}µs"
    elif ms < 1000:
        return f"{ms:.0f}ms"
    else:
        return f"{ms / 1000:.1f}s"
