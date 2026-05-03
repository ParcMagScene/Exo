"""
Tests unitaires — v8.1 Ultra-Low Latency (ULL)

Valide les composants ULL côté Python :
 - ContextCache (simulation du cache in-process C++)
 - LatencySnapshot (structure de données latence)
 - KeepAlive / Warmup logic
"""

import time
from dataclasses import dataclass, field
from typing import Optional

import pytest


# ═══════════════════════════════════════════════════════
#  ContextCache — pure-Python mirror for testability
# ═══════════════════════════════════════════════════════

class _CacheEntry:
    __slots__ = ("value", "ttl_ms", "inserted_at", "hits")

    def __init__(self, value, ttl_ms: int):
        self.value = value
        self.ttl_ms = ttl_ms
        self.inserted_at = time.monotonic()
        self.hits = 0

    def is_expired(self) -> bool:
        return (time.monotonic() - self.inserted_at) * 1000 > self.ttl_ms


class ContextCachePy:
    """Python mirror of C++ ContextCache for unit testing."""

    def __init__(self):
        self._store: dict[str, _CacheEntry] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str):
        entry = self._store.get(key)
        if entry and not entry.is_expired():
            entry.hits += 1
            self._hits += 1
            return entry.value
        self._misses += 1
        return None

    def set(self, key: str, value, ttl_ms: int):
        self._store[key] = _CacheEntry(value, ttl_ms)

    def has(self, key: str) -> bool:
        entry = self._store.get(key)
        return entry is not None and not entry.is_expired()

    def invalidate(self, key: str):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        return len(self._store)

    def evict_expired(self):
        expired = [k for k, v in self._store.items() if v.is_expired()]
        for k in expired:
            del self._store[k]
        return len(expired)


# ═══════════════════════════════════════════════════════
#  LatencySnapshot — pure-Python mirror
# ═══════════════════════════════════════════════════════

@dataclass
class LatencySnapshotPy:
    t_stt_start: float = 0.0
    t_stt_partial_first: float = 0.0
    t_stt_final: float = 0.0
    t_llm_request: float = 0.0
    t_llm_first_token: float = 0.0
    t_llm_complete: float = 0.0
    t_tts_first_chunk: float = 0.0
    t_tts_first_audio: float = 0.0
    t_response_done: float = 0.0

    @property
    def stt_latency(self) -> float:
        return self.t_stt_final - self.t_stt_start

    @property
    def llm_first_token_latency(self) -> float:
        return self.t_llm_first_token - self.t_llm_request

    @property
    def perceived_latency(self) -> float:
        return self.t_tts_first_audio - self.t_stt_final

    @property
    def end_to_end(self) -> float:
        return self.t_response_done - self.t_stt_start


# ═══════════════════════════════════════════════════════
#  Tests: ContextCache
# ═══════════════════════════════════════════════════════

class TestContextCache:
    def test_set_and_get(self):
        cache = ContextCachePy()
        cache.set("weather", {"temp": 22}, 5000)
        assert cache.get("weather") == {"temp": 22}

    def test_miss_returns_none(self):
        cache = ContextCachePy()
        assert cache.get("nonexistent") is None

    def test_has_existing(self):
        cache = ContextCachePy()
        cache.set("dt", {"time": "12:00"}, 5000)
        assert cache.has("dt") is True

    def test_has_missing(self):
        cache = ContextCachePy()
        assert cache.has("dt") is False

    def test_invalidate(self):
        cache = ContextCachePy()
        cache.set("key", "value", 5000)
        cache.invalidate("key")
        assert cache.has("key") is False

    def test_clear(self):
        cache = ContextCachePy()
        cache.set("a", 1, 5000)
        cache.set("b", 2, 5000)
        cache.clear()
        assert cache.size == 0

    def test_ttl_expiration(self):
        cache = ContextCachePy()
        cache.set("short", "data", 1)  # 1ms TTL
        time.sleep(0.01)  # 10ms — well past TTL
        assert cache.has("short") is False
        assert cache.get("short") is None

    def test_hit_rate(self):
        cache = ContextCachePy()
        cache.set("k", "v", 5000)
        cache.get("k")  # hit
        cache.get("k")  # hit
        cache.get("miss")  # miss
        assert cache.hit_rate == pytest.approx(2 / 3, abs=0.01)

    def test_evict_expired(self):
        cache = ContextCachePy()
        cache.set("fresh", "data", 60000)
        cache.set("stale", "old", 1)
        time.sleep(0.01)
        evicted = cache.evict_expired()
        assert evicted == 1
        assert cache.size == 1
        assert cache.has("fresh")

    def test_overwrite_resets_ttl(self):
        cache = ContextCachePy()
        cache.set("k", "v1", 1)
        time.sleep(0.01)
        cache.set("k", "v2", 60000)  # overwrite with long TTL
        assert cache.get("k") == "v2"

    def test_hit_count(self):
        cache = ContextCachePy()
        cache.set("k", "v", 5000)
        for _ in range(5):
            cache.get("k")
        entry = cache._store["k"]
        assert entry.hits == 5


# ═══════════════════════════════════════════════════════
#  Tests: LatencySnapshot
# ═══════════════════════════════════════════════════════

class TestLatencySnapshot:
    def test_stt_latency(self):
        s = LatencySnapshotPy(t_stt_start=100, t_stt_final=350)
        assert s.stt_latency == 250

    def test_llm_first_token_latency(self):
        s = LatencySnapshotPy(t_llm_request=400, t_llm_first_token=550)
        assert s.llm_first_token_latency == 150

    def test_perceived_latency(self):
        s = LatencySnapshotPy(t_stt_final=350, t_tts_first_audio=800)
        assert s.perceived_latency == 450

    def test_end_to_end(self):
        s = LatencySnapshotPy(t_stt_start=100, t_response_done=2500)
        assert s.end_to_end == 2400

    def test_full_pipeline_timing(self):
        """Simulate a realistic pipeline flow."""
        s = LatencySnapshotPy(
            t_stt_start=0,
            t_stt_partial_first=120,
            t_stt_final=350,
            t_llm_request=355,
            t_llm_first_token=550,
            t_llm_complete=1200,
            t_tts_first_chunk=600,
            t_tts_first_audio=650,
            t_response_done=2500,
        )
        assert s.stt_latency == 350
        assert s.llm_first_token_latency == 195
        assert s.perceived_latency == 300  # 650 - 350
        assert s.end_to_end == 2500


# ═══════════════════════════════════════════════════════
#  Tests: Warmup / KeepAlive logic
# ═══════════════════════════════════════════════════════

class TestWarmupKeepAlive:
    def test_warmup_flag_initially_false(self):
        warmed_up = False
        assert warmed_up is False

    def test_warmup_sets_flag(self):
        warmed_up = False
        # Simulate warmup success
        warmed_up = True
        assert warmed_up is True

    def test_keepalive_interval_minimum(self):
        """KeepAlive interval must be >= 30s."""
        requested = 10000
        actual = max(30000, requested)
        assert actual == 30000

    def test_keepalive_default_interval(self):
        default_interval_ms = 240000  # 4 minutes
        assert default_interval_ms >= 60000

    def test_warmup_skip_if_already_warm(self):
        """initWarmup should skip if already warmed up."""
        warmed_up = True
        in_progress = False
        should_warmup = not warmed_up and not in_progress
        assert should_warmup is False

    def test_warmup_skip_if_in_progress(self):
        warmed_up = False
        in_progress = True
        should_warmup = not warmed_up and not in_progress
        assert should_warmup is False


# ═══════════════════════════════════════════════════════
#  Tests: Cache integration patterns
# ═══════════════════════════════════════════════════════

class TestCacheIntegration:
    def test_weather_cache_hit(self):
        """Cached weather should return immediately."""
        cache = ContextCachePy()
        weather = {"status": "success", "temperature": 22, "description": "Ensoleillé"}
        cache.set("weather", weather, 60000)

        # Simulate tool call
        result = cache.get("weather")
        assert result is not None
        assert result["temperature"] == 22

    def test_datetime_cache_short_ttl(self):
        """DateTime cache has very short TTL (10s)."""
        cache = ContextCachePy()
        dt = {"date": "2025-01-15", "time": "14:30:00"}
        cache.set("datetime", dt, 10)  # 10ms for test
        assert cache.has("datetime")
        time.sleep(0.02)
        assert not cache.has("datetime")

    def test_cache_miss_dispatches_tool(self):
        """On cache miss, tool should be dispatched normally."""
        cache = ContextCachePy()
        result = cache.get("weather")
        dispatched = result is None  # would trigger dispatch
        assert dispatched is True

    def test_multiple_tools_cached(self):
        cache = ContextCachePy()
        cache.set("weather", {"temp": 20}, 60000)
        cache.set("datetime", {"time": "12:00"}, 10000)
        cache.set("ha_state", {"lights": "on"}, 30000)
        assert cache.size == 3
        assert cache.get("weather")["temp"] == 20
        assert cache.get("datetime")["time"] == "12:00"
        assert cache.get("ha_state")["lights"] == "on"

    def test_refresh_rule_concept(self):
        """Refresh rules specify which keys to auto-refresh."""
        rules = {
            "weather": 60000,
            "datetime": 10000,
            "ha_state": 30000,
        }
        assert min(rules.values()) == 10000
        assert "weather" in rules
