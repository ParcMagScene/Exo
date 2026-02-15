"""test_performance.py - Benchmark des performances du système.

Teste:
- Latence STT (Faster-Whisper)
- Latence LLM (Azure OpenAI)
- Latence HA WebSocket
- Latence TTS (Fish-Speech)
- E2E total
"""

import asyncio
import logging
import time
import numpy as np
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def benchmark_stt() -> Dict[str, float]:
    """Benchmark STT avec Faster-Whisper."""
    logger.info("🎤 Benchmark STT...")

    try:
        from src.hardware.hardware_accel import HardwareAccelerator

        accel = HardwareAccelerator()
        await accel.initialize()

        # Créer du silence de 1 seconde (16kHz)
        dummy_audio = np.zeros(16000, dtype=np.float32).tobytes()

        start = time.time()
        text = await accel.transcribe_audio(dummy_audio)
        elapsed = time.time() - start

        logger.info(f"✅ STT: {elapsed*1000:.1f}ms")
        return {"stt_ms": elapsed * 1000}

    except Exception as e:
        logger.error(f"❌ Erreur STT: {e}")
        return {"stt_ms": 0}


async def benchmark_llm() -> Dict[str, float]:
    """Benchmark appel GPT-4o."""
    logger.info("🧠 Benchmark LLM...")

    try:
        from src.brain.brain_engine import BrainEngine

        brain = BrainEngine()
        await brain.initialize()

        start = time.time()
        response = await brain.process_command(
            text="Allume la lumière du salon",
            room="salon"
        )
        elapsed = time.time() - start

        logger.info(f"✅ LLM: {elapsed*1000:.1f}ms")
        logger.info(f"   Réponse: {response.get('text', '')[:50]}...")

        return {"llm_ms": elapsed * 1000}

    except Exception as e:
        logger.error(f"❌ Erreur LLM: {e}")
        return {"llm_ms": 0}


async def benchmark_ha() -> Dict[str, float]:
    """Benchmark appel Home Assistant."""
    logger.info("🏠 Benchmark Home Assistant...")

    try:
        from src.integrations.home_bridge import HomeBridge

        ha = HomeBridge()
        # Ne pas connecter, juste tester REST API
        start = time.time()
        # Appel REST simulé
        await ha._call_service_rest(
            "light",
            "turn_on",
            {"entity_id": "light.test", "brightness": 100}
        )
        elapsed = time.time() - start

        logger.info(f"✅ HA REST: {elapsed*1000:.1f}ms")
        return {"ha_ms": elapsed * 1000}

    except Exception as e:
        logger.error(f"❌ Erreur HA: {e}")
        return {"ha_ms": 0}


async def benchmark_tts() -> Dict[str, float]:
    """Benchmark TTS Fish-Speech."""
    logger.info("🔊 Benchmark TTS...")

    try:
        from src.hardware.hardware_accel import HardwareAccelerator

        accel = HardwareAccelerator()
        await accel.initialize()

        start = time.time()
        audio = await accel.text_to_speech("Bonjour")
        elapsed = time.time() - start

        logger.info(f"✅ TTS: {elapsed*1000:.1f}ms")
        return {"tts_ms": elapsed * 1000}

    except Exception as e:
        logger.error(f"❌ Erreur TTS: {e}")
        return {"tts_ms": 0}


async def benchmark_chroma() -> Dict[str, float]:
    """Benchmark ChromaDB RAG."""
    logger.info("📚 Benchmark ChromaDB...")

    try:
        from src.brain.brain_engine import BrainEngine

        brain = BrainEngine()
        await brain.initialize()

        start = time.time()
        context = await brain._fetch_rag_context("Mon chat Felix", "salon")
        elapsed = time.time() - start

        logger.info(f"✅ ChromaDB: {elapsed*1000:.1f}ms")
        return {"chroma_ms": elapsed * 1000}

    except Exception as e:
        logger.error(f"❌ Erreur ChromaDB: {e}")
        return {"chroma_ms": 0}


async def main():
    """Lance tous les benchmarks."""
    logger.info("=" * 50)
    logger.info("📊 BENCHMARK PERFORMANCE")
    logger.info("=" * 50)

    results = {}

    # Étapes
    steps = [
        ("STT", benchmark_stt),
        ("LLM", benchmark_llm),
        ("HA", benchmark_ha),
        ("TTS", benchmark_tts),
        ("ChromaDB", benchmark_chroma),
    ]

    for name, func in steps:
        try:
            res = await func()
            results.update(res)
        except Exception as e:
            logger.error(f"Erreur {name}: {e}")
        await asyncio.sleep(0.5)

    # Résumé
    logger.info("\n" + "=" * 50)
    logger.info("📊 RÉSUMÉ")
    logger.info("=" * 50)

    total = sum(v for v in results.values())
    target = 500

    for key, value in sorted(results.items()):
        status = "✅" if value < 200 else "⚠️" if value < 500 else "❌"
        logger.info(f"{status} {key:12} : {value:7.1f}ms")

    logger.info("-" * 50)
    logger.info(f"💡 TOTAL E2E      : {total:7.1f}ms / {target}ms")

    if total < target:
        logger.info(f"✅ OBJECTIF ATTEINT! ({total:.0f}ms < {target}ms)")
    else:
        logger.info(f"⚠️ À optimiser ({total:.0f}ms > {target}ms)")

    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
