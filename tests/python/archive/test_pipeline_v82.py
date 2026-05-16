"""
Tests unitaires — Pipeline Ultra-Low Latency v8.2

Tests complets pour tous les modules v8.2 :
- LLMWarmup (warmup, keepalive, métriques)
- FusedPipeline (états, partial, final, anticipation, métriques)
- TTSPredictive (buffer circulaire, accumulateur, sessions)
- ContextCache (get/set, TTL, LRU, domaines, invalidation)
- CPUGPUOrchestrator (priorités, snapshots, métriques)
- PipelineProfiler (profils, percentiles, historique)
- PipelineResilience (timeout, retry, fallback, health)
- PipelineV9Integration (métriques, health check)

Tous testables sans dépendances externes (CUDA, psutil, etc.).
"""

import sys
import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════
# LLMWarmup
# ═══════════════════════════════════════════════════════════════

class TestLLMWarmup:
    """Tests du module LLM Warmup + KeepAlive."""

    def test_import(self):
        from llm_warmup import LLMWarmup
        w = LLMWarmup()
        assert w is not None

    def test_initial_state(self):
        from llm_warmup import LLMWarmup
        w = LLMWarmup()
        assert w.warmed_up is False
        assert w.last_warmup_latency == 0.0

    def test_metrics_initial(self):
        from llm_warmup import LLMWarmup
        w = LLMWarmup()
        m = w.metrics()
        assert m["warmed_up"] is False
        assert m["warmup_count"] == 0
        assert m["keepalive_count"] == 0
        assert m["running"] is False

    @pytest.mark.asyncio
    async def test_warmup_no_send_fn(self):
        from llm_warmup import LLMWarmup
        w = LLMWarmup()
        result = await w.warmup()
        assert result["status"] == "skip"
        assert result["warmed_up"] is False

    @pytest.mark.asyncio
    async def test_warmup_success(self):
        from llm_warmup import LLMWarmup
        w = LLMWarmup()
        mock_send = AsyncMock(return_value="OK")
        w.set_send_function(mock_send)
        result = await w.warmup()
        assert result["status"] == "ok"
        assert result["warmed_up"] is True
        assert result["latency_ms"] >= 0
        assert w.warmed_up is True
        assert w.last_warmup_latency >= 0

    @pytest.mark.asyncio
    async def test_warmup_timeout(self):
        from llm_warmup import LLMWarmup
        w = LLMWarmup()

        async def slow_send(*args):
            await asyncio.sleep(100)
            return "OK"

        w.set_send_function(slow_send)
        # Override timeout to be very short
        import llm_warmup
        original = llm_warmup.WARMUP_TIMEOUT
        llm_warmup.WARMUP_TIMEOUT = 0.01
        try:
            result = await w.warmup()
            assert result["status"] == "timeout"
        finally:
            llm_warmup.WARMUP_TIMEOUT = original

    @pytest.mark.asyncio
    async def test_warmup_error(self):
        from llm_warmup import LLMWarmup
        w = LLMWarmup()

        async def broken_send(*args):
            raise ConnectionError("fail")

        w.set_send_function(broken_send)
        result = await w.warmup()
        assert result["status"] == "error"
        assert "fail" in result["error"]

    @pytest.mark.asyncio
    async def test_warmup_count_increments(self):
        from llm_warmup import LLMWarmup
        w = LLMWarmup()
        w.set_send_function(AsyncMock(return_value="OK"))
        await w.warmup()
        await w.warmup()
        m = w.metrics()
        assert m["warmup_count"] == 2

    def test_stop_keepalive_when_not_started(self):
        from llm_warmup import LLMWarmup
        w = LLMWarmup()
        w.stop_keepalive()  # Ne doit pas crasher

    @pytest.mark.asyncio
    async def test_keepalive_start_stop(self):
        from llm_warmup import LLMWarmup
        w = LLMWarmup(keepalive_interval=0.05)
        w.set_send_function(AsyncMock(return_value="OK"))
        w.start_keepalive()
        await asyncio.sleep(0.02)
        assert w.metrics()["running"] is True
        w.stop_keepalive()

    def test_custom_params(self):
        from llm_warmup import LLMWarmup
        w = LLMWarmup(
            keepalive_interval=120,
            warmup_prompt="Test",
            warmup_max_tokens=5,
            system_prompt="System",
        )
        m = w.metrics()
        assert m["keepalive_interval_s"] == 120


# ═══════════════════════════════════════════════════════════════
# FusedPipeline
# ═══════════════════════════════════════════════════════════════

class TestFusedPipeline:
    """Tests du pipeline fusionné STT → LLM → TTS."""

    def test_import(self):
        from fused_pipeline import FusedPipeline, PipelineState
        p = FusedPipeline()
        assert p.state == PipelineState.IDLE

    def test_begin_interaction(self):
        from fused_pipeline import FusedPipeline, PipelineState
        p = FusedPipeline()
        ctx = p.begin_interaction()
        assert ctx.interaction_id == "int-000001"
        assert p.state == PipelineState.LISTENING
        assert ctx.t_start > 0

    def test_multiple_interactions(self):
        from fused_pipeline import FusedPipeline
        p = FusedPipeline()
        ctx1 = p.begin_interaction()
        ctx2 = p.begin_interaction()
        assert ctx1.interaction_id != ctx2.interaction_id

    @pytest.mark.asyncio
    async def test_on_partial(self):
        from fused_pipeline import FusedPipeline, PipelineState
        p = FusedPipeline()
        p.begin_interaction()
        await p.on_partial("bonjour")
        assert p.state == PipelineState.TRANSCRIBING

    @pytest.mark.asyncio
    async def test_on_partial_no_context(self):
        from fused_pipeline import FusedPipeline
        p = FusedPipeline()
        await p.on_partial("test")  # Ne doit pas crasher

    @pytest.mark.asyncio
    async def test_on_final_no_llm(self):
        from fused_pipeline import FusedPipeline, PipelineState
        p = FusedPipeline()
        p.begin_interaction()
        await p.on_final("allume la lumière")
        assert p.state == PipelineState.IDLE

    @pytest.mark.asyncio
    async def test_on_final_with_llm(self):
        from fused_pipeline import FusedPipeline, PipelineState
        mock_llm = AsyncMock(return_value="Lumière allumée")
        p = FusedPipeline(llm_send=mock_llm)
        p.begin_interaction()
        await p.on_final("allume la lumière")
        assert p.state == PipelineState.IDLE
        mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_final_with_llm_and_tts(self):
        from fused_pipeline import FusedPipeline
        mock_llm = AsyncMock(return_value="Lumière allumée")
        mock_tts = AsyncMock()
        p = FusedPipeline(llm_send=mock_llm, tts_stream=mock_tts)
        p.begin_interaction()
        await p.on_final("allume la lumière")
        mock_tts.assert_called_once_with("Lumière allumée")

    @pytest.mark.asyncio
    async def test_on_final_llm_error(self):
        from fused_pipeline import FusedPipeline, PipelineState
        mock_llm = AsyncMock(side_effect=ConnectionError("LLM down"))
        p = FusedPipeline(llm_send=mock_llm)
        p.begin_interaction()
        await p.on_final("test")
        # Devrait passer en IDLE après erreur
        assert p.state == PipelineState.IDLE

    def test_on_llm_token_sentence(self):
        from fused_pipeline import FusedPipeline
        p = FusedPipeline()
        p.begin_interaction()
        result = p.on_llm_token("Bonjour")
        assert result is None  # pas de phrase complète
        result = p.on_llm_token(". ")
        assert result == "Bonjour."

    def test_on_llm_token_accumulation(self):
        from fused_pipeline import FusedPipeline
        p = FusedPipeline()
        p.begin_interaction()
        p.on_llm_token("La ")
        p.on_llm_token("lumière ")
        result = p.on_llm_token("est allumée! ")
        assert result == "La lumière est allumée!"

    def test_flush_sentence_buffer(self):
        from fused_pipeline import FusedPipeline
        p = FusedPipeline()
        p.begin_interaction()
        p.on_llm_token("Texte restant")
        result = p.flush_sentence_buffer()
        assert result == "Texte restant"

    def test_flush_empty_buffer(self):
        from fused_pipeline import FusedPipeline
        p = FusedPipeline()
        result = p.flush_sentence_buffer()
        assert result is None

    def test_cancel(self):
        from fused_pipeline import FusedPipeline, PipelineState
        p = FusedPipeline()
        p.begin_interaction()
        p.cancel()
        assert p.state == PipelineState.IDLE
        assert p.current_context is None

    def test_state_change_callback(self):
        from fused_pipeline import FusedPipeline, PipelineState
        states = []
        p = FusedPipeline(on_state_change=lambda s: states.append(s))
        p.begin_interaction()
        assert PipelineState.LISTENING in states

    def test_metrics_initial(self):
        from fused_pipeline import FusedPipeline
        p = FusedPipeline()
        m = p.metrics()
        assert m["state"] == "IDLE"
        assert m["total_interactions"] == 0

    @pytest.mark.asyncio
    async def test_metrics_after_interaction(self):
        from fused_pipeline import FusedPipeline
        p = FusedPipeline()
        p.begin_interaction()
        await p.on_final("test")
        m = p.metrics()
        assert m["total_interactions"] == 1

    def test_history(self):
        from fused_pipeline import FusedPipeline
        p = FusedPipeline()
        assert p.history() == []

    def test_interaction_context_snapshot(self):
        from fused_pipeline import InteractionContext
        ctx = InteractionContext(interaction_id="test-001")
        snap = ctx.snapshot()
        assert snap["interaction_id"] == "test-001"
        assert snap["state"] == "IDLE"

    def test_interaction_context_latencies(self):
        from fused_pipeline import InteractionContext
        ctx = InteractionContext(
            interaction_id="test-001",
            t_start=100.0,
            t_stt_start=100.0,
            t_stt_end=100.3,
            t_llm_start=100.3,
            t_llm_first_token=100.5,
            t_llm_end=101.0,
            t_tts_start=101.0,
            t_tts_first_chunk=101.2,
        )
        assert abs(ctx.stt_latency_ms - 300.0) < 0.1
        assert abs(ctx.llm_first_token_ms - 200.0) < 0.1
        assert abs(ctx.llm_latency_ms - 700.0) < 0.1
        assert abs(ctx.tts_first_chunk_ms - 200.0) < 0.1
        assert abs(ctx.total_latency_ms - 1200.0) < 0.1


# ═══════════════════════════════════════════════════════════════
# TTSPredictive
# ═══════════════════════════════════════════════════════════════

class TestCircularAudioBuffer:
    """Tests du buffer circulaire audio."""

    def test_import(self):
        from tts_predictive import CircularAudioBuffer
        buf = CircularAudioBuffer()
        assert buf.size == 0
        assert buf.empty is True

    def test_push_pop(self):
        from tts_predictive import CircularAudioBuffer
        buf = CircularAudioBuffer(capacity=10)
        chunk = buf.push(b"\x00" * 100)
        assert chunk.seq == 1
        assert buf.size == 1
        popped = buf.pop()
        assert popped.data == b"\x00" * 100
        assert buf.empty is True

    def test_capacity_eviction(self):
        from tts_predictive import CircularAudioBuffer
        buf = CircularAudioBuffer(capacity=3)
        buf.push(b"a")
        buf.push(b"b")
        buf.push(b"c")
        buf.push(b"d")  # devrait évincer "a"
        assert buf.size == 3
        first = buf.pop()
        assert first.data == b"b"

    def test_pop_empty(self):
        from tts_predictive import CircularAudioBuffer
        buf = CircularAudioBuffer()
        chunk = buf.pop()
        assert chunk is None

    def test_peek(self):
        from tts_predictive import CircularAudioBuffer
        buf = CircularAudioBuffer()
        buf.push(b"test")
        peeked = buf.peek()
        assert peeked.data == b"test"
        assert buf.size == 1  # non retiré

    def test_clear(self):
        from tts_predictive import CircularAudioBuffer
        buf = CircularAudioBuffer()
        buf.push(b"a")
        buf.push(b"b")
        buf.clear()
        assert buf.empty is True

    def test_metrics(self):
        from tts_predictive import CircularAudioBuffer
        buf = CircularAudioBuffer(capacity=10)
        buf.push(b"a")
        buf.push(b"b")
        buf.pop()
        m = buf.metrics()
        assert m["current_size"] == 1
        assert m["total_pushed"] == 2
        assert m["total_popped"] == 1
        assert m["underruns"] == 0

    def test_underrun_count(self):
        from tts_predictive import CircularAudioBuffer
        buf = CircularAudioBuffer()
        buf.pop()
        buf.pop()
        m = buf.metrics()
        assert m["underruns"] == 2


class TestTextAccumulator:
    """Tests du micro-buffer textuel."""

    def test_import(self):
        from tts_predictive import TextAccumulator
        acc = TextAccumulator()
        assert acc.pending == ""

    def test_add_no_sentence(self):
        from tts_predictive import TextAccumulator
        acc = TextAccumulator()
        result = acc.add("Bonjour ")
        assert result is None
        assert acc.pending == "Bonjour "

    def test_add_with_sentence(self):
        from tts_predictive import TextAccumulator
        acc = TextAccumulator()
        acc.add("Bonjour ")
        result = acc.add("le monde. ")
        assert result == "Bonjour le monde."

    def test_flush(self):
        from tts_predictive import TextAccumulator
        acc = TextAccumulator()
        acc.add("Texte ")
        acc.add("restant")
        result = acc.flush()
        assert result == "Texte restant"

    def test_flush_empty(self):
        from tts_predictive import TextAccumulator
        acc = TextAccumulator()
        result = acc.flush()
        assert result is None

    def test_flushed_count(self):
        from tts_predictive import TextAccumulator
        acc = TextAccumulator()
        acc.add("Phrase un. ")
        acc.add("Phrase deux! ")
        assert acc.flushed_count == 2

    def test_exclamation_mark(self):
        from tts_predictive import TextAccumulator
        acc = TextAccumulator()
        result = acc.add("Super bien! ")
        assert result == "Super bien!"

    def test_question_mark(self):
        from tts_predictive import TextAccumulator
        acc = TextAccumulator()
        result = acc.add("Ça va bien? ")
        assert result == "Ça va bien?"


class TestTTSPredictive:
    """Tests du gestionnaire prédictif TTS."""

    def test_import(self):
        from tts_predictive import TTSPredictive
        tts = TTSPredictive()
        assert tts is not None

    def test_begin_session(self):
        from tts_predictive import TTSPredictive
        tts = TTSPredictive()
        tts.begin_session()
        m = tts.metrics()
        assert m["total_sessions"] == 1
        assert m["active"] is True

    def test_end_session(self):
        from tts_predictive import TTSPredictive
        tts = TTSPredictive()
        tts.begin_session()
        tts.end_session()
        m = tts.metrics()
        assert m["active"] is False

    @pytest.mark.asyncio
    async def test_feed_token(self):
        from tts_predictive import TTSPredictive
        tts = TTSPredictive()
        tts.begin_session()
        await tts.feed_token("Bonjour. ")
        # Phrase complète devrait être dans la queue
        assert not tts._synth_queue.empty()

    @pytest.mark.asyncio
    async def test_flush(self):
        from tts_predictive import TTSPredictive
        tts = TTSPredictive()
        tts.begin_session()
        await tts.feed_token("Texte")
        await tts.flush()
        # Queue devrait avoir le texte + None (signal de fin)
        items = []
        while not tts._synth_queue.empty():
            items.append(await tts._synth_queue.get())
        assert "Texte" in items
        assert None in items

    def test_cancel(self):
        from tts_predictive import TTSPredictive
        tts = TTSPredictive()
        tts.begin_session()
        tts.cancel()
        m = tts.metrics()
        assert m["active"] is False

    def test_metrics_initial(self):
        from tts_predictive import TTSPredictive
        tts = TTSPredictive()
        m = tts.metrics()
        assert m["total_sessions"] == 0
        assert m["avg_first_chunk_ms"] == 0.0


# ═══════════════════════════════════════════════════════════════
# ContextCache
# ═══════════════════════════════════════════════════════════════

class TestContextCache:
    """Tests du cache contextuel intelligent."""

    def test_import(self):
        from context_cache import ContextCache
        cache = ContextCache()
        assert cache.size == 0

    def test_set_get(self):
        from context_cache import ContextCache, CacheDomain
        cache = ContextCache()
        cache.set("meteo_paris", {"temp": 20}, domain=CacheDomain.WEATHER)
        result = cache.get("meteo_paris", domain=CacheDomain.WEATHER)
        assert result == {"temp": 20}

    def test_get_miss(self):
        from context_cache import ContextCache, CacheDomain
        cache = ContextCache()
        result = cache.get("inexistant", domain=CacheDomain.GENERAL)
        assert result is None

    def test_has(self):
        from context_cache import ContextCache, CacheDomain
        cache = ContextCache()
        cache.set("key", "val", domain=CacheDomain.GENERAL)
        assert cache.has("key", domain=CacheDomain.GENERAL) is True
        assert cache.has("missing", domain=CacheDomain.GENERAL) is False

    def test_ttl_expiration(self):
        from context_cache import ContextCache, CacheDomain
        cache = ContextCache()
        cache.set("fast", "val", domain=CacheDomain.GENERAL, ttl=0.01)
        import time
        time.sleep(0.02)
        assert cache.get("fast", domain=CacheDomain.GENERAL) is None

    def test_lru_eviction(self):
        from context_cache import ContextCache, CacheDomain
        cache = ContextCache(max_entries=3)
        cache.set("a", 1, domain=CacheDomain.GENERAL)
        cache.set("b", 2, domain=CacheDomain.GENERAL)
        cache.set("c", 3, domain=CacheDomain.GENERAL)
        cache.set("d", 4, domain=CacheDomain.GENERAL)  # évince "a"
        assert cache.get("a", domain=CacheDomain.GENERAL) is None
        assert cache.get("d", domain=CacheDomain.GENERAL) == 4

    def test_invalidate(self):
        from context_cache import ContextCache, CacheDomain
        cache = ContextCache()
        cache.set("key", "val", domain=CacheDomain.GENERAL)
        assert cache.invalidate("key", domain=CacheDomain.GENERAL) is True
        assert cache.get("key", domain=CacheDomain.GENERAL) is None

    def test_invalidate_missing(self):
        from context_cache import ContextCache, CacheDomain
        cache = ContextCache()
        assert cache.invalidate("missing", domain=CacheDomain.GENERAL) is False

    def test_invalidate_domain(self):
        from context_cache import ContextCache, CacheDomain
        cache = ContextCache()
        cache.set("a", 1, domain=CacheDomain.WEATHER)
        cache.set("b", 2, domain=CacheDomain.WEATHER)
        cache.set("c", 3, domain=CacheDomain.NEWS)
        count = cache.invalidate_domain(CacheDomain.WEATHER)
        assert count == 2
        assert cache.get("c", domain=CacheDomain.NEWS) == 3

    def test_clear(self):
        from context_cache import ContextCache, CacheDomain
        cache = ContextCache()
        cache.set("a", 1, domain=CacheDomain.GENERAL)
        cache.set("b", 2, domain=CacheDomain.GENERAL)
        cache.clear()
        assert cache.size == 0

    def test_cleanup_expired(self):
        from context_cache import ContextCache, CacheDomain
        cache = ContextCache()
        cache.set("fast", "val", domain=CacheDomain.GENERAL, ttl=0.01)
        cache.set("slow", "val", domain=CacheDomain.GENERAL, ttl=100)
        import time
        time.sleep(0.02)
        removed = cache.cleanup_expired()
        assert removed == 1
        assert cache.size == 1

    def test_domain_ttl_weather(self):
        from context_cache import DOMAIN_TTL, CacheDomain
        assert DOMAIN_TTL[CacheDomain.WEATHER] == 600.0

    def test_domain_ttl_domotique(self):
        from context_cache import DOMAIN_TTL, CacheDomain
        assert DOMAIN_TTL[CacheDomain.DOMOTIQUE] == 30.0

    def test_metrics(self):
        from context_cache import ContextCache, CacheDomain
        cache = ContextCache()
        cache.set("key", "val", domain=CacheDomain.WEATHER)
        cache.get("key", domain=CacheDomain.WEATHER)  # hit
        cache.get("miss", domain=CacheDomain.WEATHER)  # miss
        m = cache.metrics()
        assert m["hits"] == 1
        assert m["misses"] == 1
        assert m["hit_rate_pct"] == 50.0
        assert m["size"] == 1

    def test_metrics_by_domain(self):
        from context_cache import ContextCache, CacheDomain
        cache = ContextCache()
        cache.set("a", 1, domain=CacheDomain.WEATHER)
        cache.set("b", 2, domain=CacheDomain.NEWS)
        m = cache.metrics()
        assert m["by_domain"]["weather"] == 1
        assert m["by_domain"]["news"] == 1

    def test_different_domains_same_key(self):
        from context_cache import ContextCache, CacheDomain
        cache = ContextCache()
        cache.set("data", "weather_data", domain=CacheDomain.WEATHER)
        cache.set("data", "news_data", domain=CacheDomain.NEWS)
        assert cache.get("data", domain=CacheDomain.WEATHER) == "weather_data"
        assert cache.get("data", domain=CacheDomain.NEWS) == "news_data"

    def test_cache_entry_expired(self):
        from context_cache import CacheEntry, CacheDomain
        import time as _time
        entry = CacheEntry(
            key="test",
            value="val",
            domain=CacheDomain.GENERAL,
            created_at=_time.monotonic() - 100,
            ttl=50,
        )
        assert entry.expired is True

    def test_cache_entry_not_expired(self):
        from context_cache import CacheEntry, CacheDomain
        import time as _time
        entry = CacheEntry(
            key="test",
            value="val",
            domain=CacheDomain.GENERAL,
            created_at=_time.monotonic(),
            ttl=100,
        )
        assert entry.expired is False

    def test_update_existing_key(self):
        from context_cache import ContextCache, CacheDomain
        cache = ContextCache()
        cache.set("key", "v1", domain=CacheDomain.GENERAL)
        cache.set("key", "v2", domain=CacheDomain.GENERAL)
        assert cache.get("key", domain=CacheDomain.GENERAL) == "v2"
        assert cache.size == 1


# ═══════════════════════════════════════════════════════════════
# CPUGPUOrchestrator
# ═══════════════════════════════════════════════════════════════

class TestCPUGPUOrchestrator:
    """Tests de l'orchestrateur CPU/GPU."""

    def test_import(self):
        from cpu_gpu_orchestrator import CPUGPUOrchestrator
        o = CPUGPUOrchestrator()
        assert o is not None

    def test_thread_priority_enum(self):
        from cpu_gpu_orchestrator import ThreadPriority
        assert ThreadPriority.NORMAL == 0
        assert ThreadPriority.TIME_CRITICAL == 15

    def test_component_priorities(self):
        from cpu_gpu_orchestrator import COMPONENT_PRIORITY, ThreadPriority
        assert COMPONENT_PRIORITY["audio_capture"] == ThreadPriority.TIME_CRITICAL
        assert COMPONENT_PRIORITY["llm"] == ThreadPriority.NORMAL

    def test_metrics_initial(self):
        from cpu_gpu_orchestrator import CPUGPUOrchestrator
        o = CPUGPUOrchestrator()
        m = o.metrics()
        assert m["gpu_available"] is False
        assert m["snapshots_count"] == 0

    def test_snapshot(self):
        from cpu_gpu_orchestrator import CPUGPUOrchestrator
        o = CPUGPUOrchestrator()
        snap = o.snapshot()
        assert snap.thread_count > 0
        assert snap.timestamp > 0

    def test_probe_gpu(self):
        from cpu_gpu_orchestrator import CPUGPUOrchestrator
        o = CPUGPUOrchestrator()
        result = o.probe_gpu()
        assert "cuda_available" in result
        assert "vulkan_available" in result

    def test_apply_unknown_component(self):
        from cpu_gpu_orchestrator import CPUGPUOrchestrator
        o = CPUGPUOrchestrator()
        result = o.apply_component_priority("unknown_component")
        assert result is False

    def test_metrics_after_snapshot(self):
        from cpu_gpu_orchestrator import CPUGPUOrchestrator
        o = CPUGPUOrchestrator()
        o.snapshot()
        o.snapshot()
        m = o.metrics()
        assert m["snapshots_count"] == 2


# ═══════════════════════════════════════════════════════════════
# PipelineProfiler
# ═══════════════════════════════════════════════════════════════

class TestPipelineProfiler:
    """Tests du profiler de pipeline."""

    def test_import(self):
        from pipeline_profiler import PipelineProfiler
        p = PipelineProfiler()
        assert p is not None

    def test_begin_end(self):
        from pipeline_profiler import PipelineProfiler
        p = PipelineProfiler()
        profile = p.begin("int-001")
        assert profile.interaction_id == "int-001"
        snapshot = p.end(profile)
        assert snapshot["interaction_id"] == "int-001"
        assert snapshot["total_ms"] >= 0

    def test_stages(self):
        from pipeline_profiler import PipelineProfiler
        p = PipelineProfiler()
        profile = p.begin("int-001")
        profile.begin_stage("stt")
        import time
        time.sleep(0.01)
        profile.end_stage("stt", model="medium")
        snapshot = p.end(profile)
        assert "stt" in snapshot["stages"]
        assert snapshot["stages"]["stt"]["duration_ms"] >= 5
        assert snapshot["stages"]["stt"]["model"] == "medium"

    def test_percentiles_empty(self):
        from pipeline_profiler import PipelineProfiler
        p = PipelineProfiler()
        pct = p.percentiles("stt")
        assert pct["count"] == 0

    def test_percentiles_filled(self):
        from pipeline_profiler import PipelineProfiler
        p = PipelineProfiler()
        for i in range(10):
            profile = p.begin()
            profile.begin_stage("stt")
            profile.end_stage("stt")
            p.end(profile)
        pct = p.percentiles("stt")
        assert pct["count"] == 10

    def test_all_percentiles(self):
        from pipeline_profiler import PipelineProfiler
        p = PipelineProfiler()
        profile = p.begin()
        profile.begin_stage("stt")
        profile.end_stage("stt")
        profile.begin_stage("llm")
        profile.end_stage("llm")
        p.end(profile)
        ap = p.all_percentiles()
        assert "stt" in ap
        assert "llm" in ap

    def test_summary(self):
        from pipeline_profiler import PipelineProfiler
        p = PipelineProfiler()
        s = p.summary()
        assert s["total_interactions"] == 0

    def test_recent(self):
        from pipeline_profiler import PipelineProfiler
        p = PipelineProfiler()
        profile = p.begin()
        p.end(profile)
        recent = p.recent(5)
        assert len(recent) == 1

    def test_auto_id(self):
        from pipeline_profiler import PipelineProfiler
        p = PipelineProfiler()
        profile = p.begin()
        assert profile.interaction_id.startswith("prof-")

    def test_first_audio_ms(self):
        from pipeline_profiler import PipelineProfiler, InteractionProfile
        profile = InteractionProfile(
            interaction_id="test",
            t_start=100.0,
        )
        profile.begin_stage("tts")
        profile.stages["tts"].metadata["first_chunk_at"] = 101.5
        profile.end_stage("tts")
        assert abs(profile.first_audio_ms - 1500.0) < 0.1

    def test_stage_snapshot(self):
        from pipeline_profiler import StageProfile
        s = StageProfile(name="stt", t_start=1.0, t_end=1.3,
                         metadata={"model": "medium"})
        snap = s.snapshot()
        assert snap["name"] == "stt"
        assert abs(snap["duration_ms"] - 300.0) < 0.1
        assert snap["model"] == "medium"


# ═══════════════════════════════════════════════════════════════
# PipelineResilience
# ═══════════════════════════════════════════════════════════════

class TestPipelineResilience:
    """Tests de la résilience pipeline."""

    def test_import(self):
        from pipeline_resilience import PipelineResilience
        r = PipelineResilience()
        assert r is not None

    @pytest.mark.asyncio
    async def test_call_success(self):
        from pipeline_resilience import PipelineResilience
        r = PipelineResilience()
        result = await r.call("stt", AsyncMock(return_value="transcription"))
        assert result == "transcription"

    @pytest.mark.asyncio
    async def test_call_unknown_module(self):
        from pipeline_resilience import PipelineResilience
        r = PipelineResilience()
        result = await r.call("unknown", AsyncMock(return_value="ok"))
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_call_timeout(self):
        from pipeline_resilience import PipelineResilience

        async def slow_fn():
            await asyncio.sleep(100)
            return "ok"

        r = PipelineResilience(config_overrides={
            "stt": {"timeout_s": 0.01, "retries": 0}
        })
        with pytest.raises(asyncio.TimeoutError):
            await r.call("stt", slow_fn)

    @pytest.mark.asyncio
    async def test_call_retry(self):
        from pipeline_resilience import PipelineResilience
        call_count = 0

        async def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("fail")
            return "ok"

        r = PipelineResilience(config_overrides={
            "llm": {"timeout_s": 5, "retries": 2, "backoff_base": 0.01}
        })
        result = await r.call("llm", flaky_fn)
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_call_fallback(self):
        from pipeline_resilience import PipelineResilience

        async def fail_fn():
            raise ConnectionError("fail")

        async def fallback_fn():
            return "fallback_result"

        r = PipelineResilience(config_overrides={
            "stt": {"timeout_s": 5, "retries": 0, "backoff_base": 0.01}
        })
        r.register_fallback("stt", fallback_fn)
        result = await r.call("stt", fail_fn)
        assert result == "fallback_result"

    def test_health_initial(self):
        from pipeline_resilience import PipelineResilience
        r = PipelineResilience()
        h = r.health("stt")
        assert h is not None
        assert h["state"] == "HEALTHY"
        assert h["total_calls"] == 0

    @pytest.mark.asyncio
    async def test_health_after_success(self):
        from pipeline_resilience import PipelineResilience
        r = PipelineResilience()
        await r.call("stt", AsyncMock(return_value="ok"))
        h = r.health("stt")
        assert h["total_calls"] == 1
        assert h["success_rate_pct"] == 100.0

    @pytest.mark.asyncio
    async def test_health_degraded(self):
        from pipeline_resilience import PipelineResilience, ModuleState

        async def fail_fn():
            raise ConnectionError("fail")

        r = PipelineResilience(config_overrides={
            "stt": {"timeout_s": 5, "retries": 0}
        })
        # Deux échecs consécutifs → DEGRADED
        for _ in range(2):
            try:
                await r.call("stt", fail_fn)
            except Exception:
                pass
        h = r.health("stt")
        assert h["state"] == "DEGRADED"

    def test_all_health(self):
        from pipeline_resilience import PipelineResilience
        r = PipelineResilience()
        ah = r.all_health()
        assert "stt" in ah
        assert "llm" in ah
        assert "tts" in ah

    def test_overall_state_healthy(self):
        from pipeline_resilience import PipelineResilience, ModuleState
        r = PipelineResilience()
        assert r.overall_state == ModuleState.HEALTHY

    def test_metrics(self):
        from pipeline_resilience import PipelineResilience
        r = PipelineResilience()
        m = r.metrics()
        assert m["overall_state"] == "HEALTHY"
        assert "modules" in m

    def test_module_config_backoff(self):
        from pipeline_resilience import ModuleConfig
        cfg = ModuleConfig(name="test", timeout_s=5, retries=3, backoff_base=0.5)
        assert cfg.backoff_delay(0) == 0.5
        assert cfg.backoff_delay(1) == 1.0
        assert cfg.backoff_delay(2) == 2.0

    def test_module_health_snapshot(self):
        from pipeline_resilience import ModuleHealth
        h = ModuleHealth(name="stt")
        h.record_success(150.0)
        h.record_success(200.0)
        snap = h.snapshot()
        assert snap["total_calls"] == 2
        assert snap["success_rate_pct"] == 100.0
        assert snap["last_latency_ms"] == 200.0

    def test_default_modules(self):
        from pipeline_resilience import DEFAULT_MODULES
        assert "stt" in DEFAULT_MODULES
        assert DEFAULT_MODULES["stt"]["timeout_s"] > 0
        assert DEFAULT_MODULES["llm"]["timeout_s"] == 10.0
        assert DEFAULT_MODULES["tts"]["timeout_s"] == 3.0
        assert DEFAULT_MODULES["tools"]["timeout_s"] == 5.0
        assert DEFAULT_MODULES["domotique"]["timeout_s"] == 3.0


# ═══════════════════════════════════════════════════════════════
# PipelineV9Integration
# ═══════════════════════════════════════════════════════════════

class TestPipelineV9Integration:
    """Tests de l'intégration v9."""

    def test_import(self):
        from pipeline_v9 import PipelineV9Integration
        v9 = PipelineV9Integration("test")
        assert v9 is not None

    def test_health_check_healthy(self):
        from pipeline_v9 import PipelineV9Integration
        v9 = PipelineV9Integration("test")
        hc = v9.health_check()
        assert hc["service"] == "test"
        assert hc["status"] == "healthy"

    def test_health_check_degraded(self):
        from pipeline_v9 import PipelineV9Integration
        v9 = PipelineV9Integration("test")
        hc = v9.health_check(components={
            "stt": {"state": "DEGRADED"},
            "llm": {"state": "HEALTHY"},
        })
        assert hc["status"] == "degraded"

    def test_health_check_unhealthy(self):
        from pipeline_v9 import PipelineV9Integration
        v9 = PipelineV9Integration("test")
        hc = v9.health_check(components={
            "stt": {"state": "FAILED"},
        })
        assert hc["status"] == "unhealthy"

    def test_record_latency(self):
        from pipeline_v9 import PipelineV9Integration
        v9 = PipelineV9Integration("test")
        v9.record_latency("stt", 150.0)  # ne doit pas crasher

    def test_increment_counter(self):
        from pipeline_v9 import PipelineV9Integration
        v9 = PipelineV9Integration("test")
        v9.increment_counter("requests")  # ne doit pas crasher

    def test_set_gauge(self):
        from pipeline_v9 import PipelineV9Integration
        v9 = PipelineV9Integration("test")
        v9.set_gauge("buffer_size", 42)  # ne doit pas crasher

    def test_log_event(self):
        from pipeline_v9 import PipelineV9Integration
        v9 = PipelineV9Integration("test")
        v9.log_event("info", "test_event", data="hello")  # ne doit pas crasher

    def test_record_error(self):
        from pipeline_v9 import PipelineV9Integration
        v9 = PipelineV9Integration("test")
        v9.record_error(ValueError("test"), context="unit_test")  # ne doit pas crasher

    def test_check_access_default(self):
        from pipeline_v9 import PipelineV9Integration
        v9 = PipelineV9Integration("test")
        assert v9.check_access("audio") is True  # permissif par défaut


# ═══════════════════════════════════════════════════════════════
# PipelineManager (exo_server integration)
# ═══════════════════════════════════════════════════════════════

class TestPipelineManagerIntegration:
    """Tests d'intégration du PipelineManager dans exo_server."""

    def test_import_all_modules(self):
        """Vérifie que tous les modules v8.2 sont importables."""
        from llm_warmup import LLMWarmup
        from fused_pipeline import FusedPipeline, PipelineState
        from tts_predictive import TTSPredictive, CircularAudioBuffer, TextAccumulator
        from context_cache import ContextCache, CacheDomain
        from cpu_gpu_orchestrator import CPUGPUOrchestrator
        from pipeline_profiler import PipelineProfiler
        from pipeline_resilience import PipelineResilience
        from pipeline_v9 import PipelineV9Integration
        assert all([
            LLMWarmup, FusedPipeline, PipelineState,
            TTSPredictive, CircularAudioBuffer, TextAccumulator,
            ContextCache, CacheDomain,
            CPUGPUOrchestrator,
            PipelineProfiler,
            PipelineResilience,
            PipelineV9Integration,
        ])

    def test_cache_domain_values(self):
        from context_cache import CacheDomain
        domains = [d.value for d in CacheDomain]
        assert "weather" in domains
        assert "domotique" in domains
        assert "tts_audio" in domains

    def test_pipeline_state_enum(self):
        from fused_pipeline import PipelineState
        assert PipelineState.IDLE.name == "IDLE"
        assert PipelineState.ANTICIPATING.name == "ANTICIPATING"
        assert PipelineState.SPEAKING.name == "SPEAKING"

    @pytest.mark.asyncio
    async def test_full_interaction_flow(self):
        """Test d'un flux complet : STT partial → final → LLM → TTS."""
        from fused_pipeline import FusedPipeline, PipelineState
        from pipeline_profiler import PipelineProfiler

        states = []
        mock_llm = AsyncMock(return_value="La lumière est allumée.")
        mock_tts = AsyncMock()

        pipeline = FusedPipeline(
            llm_send=mock_llm,
            tts_stream=mock_tts,
            on_state_change=lambda s: states.append(s),
        )
        profiler = PipelineProfiler()

        # Démarrer l'interaction
        ctx = pipeline.begin_interaction()
        profile = profiler.begin(ctx.interaction_id)
        profile.begin_stage("stt")

        # Partial STT
        await pipeline.on_partial("allume")
        await pipeline.on_partial("allume la lumière")

        # Final STT
        profile.end_stage("stt")
        profile.begin_stage("llm")
        await pipeline.on_final("allume la lumière du salon")
        profile.end_stage("llm")
        profiler.end(profile)

        # Vérifications
        assert PipelineState.LISTENING in states
        assert PipelineState.TRANSCRIBING in states
        mock_llm.assert_called_once()
        mock_tts.assert_called_once()
        assert pipeline.state == PipelineState.IDLE
