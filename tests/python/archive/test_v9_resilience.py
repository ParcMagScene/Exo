"""
Tests unitaires — v9 Error Manager & Resilience

Valide la gestion d'erreurs et les patterns de résilience :
 - ErrorCategory, ExoError, sous-classes typées
 - RETRY_POLICIES, TIMEOUT_POLICIES
 - with_retry, with_timeout, with_fallback decorators
 - CircuitBreaker
 - @resilient combined decorator
"""

import asyncio
import time

import pytest

import sys
from pathlib import Path


# ═══════════════════════════════════════════════════════
#  ErrorManager
# ═══════════════════════════════════════════════════════

from shared.error_manager import (
    ErrorCategory, ExoError, AudioError, LLMError, ToolError,
    NetworkError, IoTError, ErrorManager,
    RETRY_POLICIES, TIMEOUT_POLICIES,
    with_retry, with_timeout, with_fallback,
)


class TestExoError:
    def test_base_error(self):
        err = ExoError("test error")
        assert str(err) == "test error"
        assert err.category == ErrorCategory.INTERNAL
        assert err.recoverable is True
        assert err.timestamp > 0

    def test_audio_error(self):
        err = AudioError("mic failed")
        assert err.category == ErrorCategory.AUDIO

    def test_llm_error(self):
        err = LLMError("timeout")
        assert err.category == ErrorCategory.LLM

    def test_tool_error(self):
        err = ToolError("not found")
        assert err.category == ErrorCategory.TOOL

    def test_network_error(self):
        err = NetworkError("connection refused")
        assert err.category == ErrorCategory.NETWORK

    def test_iot_error(self):
        err = IoTError("device offline")
        assert err.category == ErrorCategory.IOT

    def test_context_dict(self):
        err = ExoError("error", context={"device": "lamp"})
        assert err.context["device"] == "lamp"

    def test_non_recoverable(self):
        err = ExoError("fatal", recoverable=False)
        assert err.recoverable is False


class TestErrorPolicies:
    def test_retry_policies_complete(self):
        for module in ("stt", "tts", "llm", "tools", "domotique", "network"):
            assert module in RETRY_POLICIES
            p = RETRY_POLICIES[module]
            assert "retries" in p
            assert "backoff" in p

    def test_timeout_policies_complete(self):
        for module in ("stt", "llm", "tts", "tools", "domotique", "network"):
            assert module in TIMEOUT_POLICIES
            assert TIMEOUT_POLICIES[module] > 0


class TestErrorManager:
    def setup_method(self):
        ErrorManager.reset()

    def test_singleton(self):
        a = ErrorManager.instance()
        b = ErrorManager.instance()
        assert a is b

    def test_handle_logs_error(self):
        em = ErrorManager.instance()
        err = AudioError("test")
        em.handle(err)
        recent = em.recent_errors(10)
        assert len(recent) == 1
        assert recent[0]["category"] == "AudioError"

    def test_handle_with_metrics(self):
        from shared.metrics_manager import MetricsManager
        MetricsManager.reset()
        mm = MetricsManager("test")
        em = ErrorManager.instance()
        em.set_metrics(mm)
        em.handle(LLMError("timeout"))
        assert mm.counter("errors_total").value == 1
        assert mm.counter("errors.LLMError").value == 1

    def test_register_handler(self):
        em = ErrorManager.instance()
        handled = []
        em.register_handler(ErrorCategory.TOOL, lambda e: handled.append(str(e)))
        em.handle(ToolError("not found"))
        assert len(handled) == 1
        assert "not found" in handled[0]

    def test_error_log_capped(self):
        em = ErrorManager.instance()
        for i in range(600):
            em.handle(ExoError(f"error {i}"))
        assert len(em.recent_errors(1000)) == 500


class TestWithRetry:
    def test_success_no_retry(self):
        call_count = 0

        @with_retry("stt")
        async def ok_fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = asyncio.get_event_loop().run_until_complete(ok_fn())
        assert result == "ok"
        assert call_count == 1

    def test_retry_then_success(self):
        call_count = 0

        @with_retry("llm")
        async def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("fail")
            return "recovered"

        result = asyncio.get_event_loop().run_until_complete(flaky_fn())
        assert result == "recovered"
        assert call_count == 3

    def test_retry_exhausted_raises(self):
        @with_retry("stt")  # 1 retry = 2 attempts
        async def always_fail():
            raise RuntimeError("fatal")

        with pytest.raises(RuntimeError, match="fatal"):
            asyncio.get_event_loop().run_until_complete(always_fail())

    def test_fallback_on_failure(self):
        async def safe_fallback(*args, **kwargs):
            return "fallback_result"

        @with_retry("stt", fallback=safe_fallback)
        async def always_fail():
            raise RuntimeError("fail")

        result = asyncio.get_event_loop().run_until_complete(always_fail())
        assert result == "fallback_result"


class TestWithTimeout:
    def test_fast_function_ok(self):
        @with_timeout("stt")  # 3s
        async def fast_fn():
            return "fast"

        result = asyncio.get_event_loop().run_until_complete(fast_fn())
        assert result == "fast"

    def test_slow_function_times_out(self):
        @with_timeout("stt")  # 3s
        async def slow_fn():
            await asyncio.sleep(10)
            return "never"

        with pytest.raises(asyncio.TimeoutError):
            asyncio.get_event_loop().run_until_complete(slow_fn())


class TestWithFallback:
    def test_primary_succeeds(self):
        async def primary():
            return "primary"

        async def fallback():
            return "fallback"

        fn = with_fallback(primary, fallback)
        result = asyncio.get_event_loop().run_until_complete(fn())
        assert result == "primary"

    def test_fallback_on_error(self):
        async def primary():
            raise RuntimeError("fail")

        async def fallback():
            return "fallback"

        fn = with_fallback(primary, fallback)
        result = asyncio.get_event_loop().run_until_complete(fn())
        assert result == "fallback"


# ═══════════════════════════════════════════════════════
#  Resilience — CircuitBreaker + @resilient
# ═══════════════════════════════════════════════════════

from shared.resilience import CircuitBreaker, get_breaker, resilient


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == "closed"
        assert not cb.is_open

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.state == "open"
        assert cb.is_open

    def test_success_resets(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.state == "closed"  # counter reset

    def test_half_open_after_cooldown(self):
        cb = CircuitBreaker(failure_threshold=1, cooldown_s=0.01)
        cb.record_failure()
        assert cb.state == "open"
        time.sleep(0.05)
        assert cb.state == "half_open"


class TestGetBreaker:
    def test_get_same_breaker(self):
        # Clear global registry
        from shared import resilience
        resilience._breakers.clear()
        b1 = get_breaker("test_module")
        b2 = get_breaker("test_module")
        assert b1 is b2

    def test_get_different_breakers(self):
        from shared import resilience
        resilience._breakers.clear()
        b1 = get_breaker("mod_a")
        b2 = get_breaker("mod_b")
        assert b1 is not b2


class TestResilient:
    def test_success(self):
        @resilient("test", retries=2)
        async def ok_fn():
            return "ok"

        result = asyncio.get_event_loop().run_until_complete(ok_fn())
        assert result == "ok"

    def test_retry_and_recover(self):
        call_count = 0

        @resilient("test", retries=2, backoff=0.01)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("fail")
            return "ok"

        result = asyncio.get_event_loop().run_until_complete(flaky())
        assert result == "ok"

    def test_fallback(self):
        @resilient("test", retries=0, fallback=lambda: "safe")
        async def fail_fn():
            raise RuntimeError("fail")

        result = asyncio.get_event_loop().run_until_complete(fail_fn())
        assert result == "safe"

    def test_timeout(self):
        @resilient("test", retries=0, timeout_s=0.05)
        async def slow_fn():
            await asyncio.sleep(10)

        with pytest.raises(asyncio.TimeoutError):
            asyncio.get_event_loop().run_until_complete(slow_fn())

    def test_circuit_breaker_integration(self):
        from shared import resilience
        resilience._breakers.clear()

        @resilient("cb_test", retries=0, circuit_breaker=True,
                   fallback=lambda: "cb_fallback")
        async def fail_fn():
            raise RuntimeError("fail")

        loop = asyncio.get_event_loop()
        # Trip the circuit breaker (threshold=5 by default)
        for _ in range(5):
            result = loop.run_until_complete(fail_fn())
            assert result == "cb_fallback"

        # Now the breaker should be open — returns fallback without calling fn
        result = loop.run_until_complete(fail_fn())
        assert result == "cb_fallback"
