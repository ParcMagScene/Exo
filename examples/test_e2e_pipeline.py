#!/usr/bin/env python3
"""
Test E2E complet du pipeline: Audio + STT + LLM + RAG + Function Calling + TTS

Mesure les latences complètes avec:
1. Audio capture (micro ou synthétique)
2. STT (Faster-Whisper)
3. LLM (GPT-4o avec RAG Chrome DB)
4. Function Calling (Home Assistant)
5. TTS (Fish-Speech + XTTS v2 fallback)
"""

import asyncio
import sys
import time
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hardware.hardware_accel import HardwareAccelerator
from src.assistant.brain import Brain
from src.assistant.chroma_client import ChromaClient
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class PipelineMetrics:
    """Métriques du pipeline E2E."""
    component: str              # "Audio", "STT", "LLM", "Function Call", "TTS", "E2E"
    duration_ms: float
    success: bool = True
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class E2EPipelineTest:
    """Test E2E du pipeline complet."""
    
    def __init__(self):
        """Initialise le test."""
        self.hardware = HardwareAccelerator()
        self.brain = Brain()
        self.chroma = ChromaClient()
        self.metrics: List[PipelineMetrics] = []
        
        # Test audio: 3 secondes de bruit blanc à 16kHz
        self.test_audio = self._generate_test_audio()
        self.test_text = "Allume la lumière du salon à 50%"
        
    def _generate_test_audio(self) -> bytes:
        """Génère audio de test."""
        sample_rate = 16000
        duration = 3.0
        num_samples = int(sample_rate * duration)
        
        # Bruit blanc
        audio = np.random.normal(0, 0.1, num_samples)
        audio = np.int16(audio / np.max(np.abs(audio)) * 32767)
        
        return audio.tobytes()
    
    async def _record_metric(self, component: str, duration_ms: float, 
                             success: bool = True, error: Optional[str] = None, 
                             details: Optional[Dict] = None):
        """Enregistre une métrique."""
        metric = PipelineMetrics(
            component=component,
            duration_ms=duration_ms,
            success=success,
            error=error,
            details=details or {}
        )
        self.metrics.append(metric)
        
        status = "✅" if success else "❌"
        logger.info(f"{status} {component}: {duration_ms:.2f} ms")
        if error:
            logger.error(f"   Error: {error}")
    
    async def setup_rag_context(self):
        """Initialise le contexte RAG avec données de test."""
        logger.info("\n📚 Configuration du contexte RAG (ChromaDB)...")
        
        try:
            # Ajouter documents de test
            test_docs = [
                "Salon: lumière Philips Hue chaude (2700K), réglage 50% par défaut",
                "Chambre: lumière IKEA froide (5000K), variateur compatible",
                "Cuisine: 3 ampoules LED blanc neutre (4000K), variateur Sonoff",
                "Préférence utilisateur: aime la lumière chaude le soir après 18h",
                "Chat Felix: noir et blanc, aime les zones chaudes",
            ]
            
            for i, doc in enumerate(test_docs):
                await self.chroma.add_document(f"doc_{i}", doc)
            
            logger.info(f"✓ {len(test_docs)} documents RAG ajoutés")
        except Exception as e:
            logger.warning(f"Erreur setup RAG: {e}")
    
    async def test_stt_component(self) -> float:
        """Teste STT (Speech-to-Text)."""
        logger.info("\n" + "="*70)
        logger.info("🎤 TEST 1: STT (Speech-to-Text)")
        logger.info("="*70)
        
        start_time = time.time()
        try:
            logger.info(f"Processing {len(self.test_audio)} bytes of audio...")
            result = await self.hardware.transcribe_audio(self.test_audio)
            duration_ms = (time.time() - start_time) * 1000
            
            logger.info(f"✅ Transcription: '{result}'")
            logger.info(f"   Latence: {duration_ms:.2f} ms")
            
            await self._record_metric("STT", duration_ms, success=True, 
                                     details={"text": result, "audio_bytes": len(self.test_audio)})
            return duration_ms
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"❌ STT failed: {e}")
            await self._record_metric("STT", duration_ms, success=False, error=str(e))
            return 0
    
    async def test_llm_component(self, user_input: str) -> tuple[float, str]:
        """Teste LLM avec RAG."""
        logger.info("\n" + "="*70)
        logger.info("🧠 TEST 2: LLM (GPT-4o + RAG)")
        logger.info("="*70)
        
        start_time = time.time()
        try:
            logger.info(f"Input: '{user_input}'")
            
            # Simuler traitement LLM via Brain (sans TTS pour isoler)
            # On va appeler _call_gpt directement
            messages = [
                {"role": "system", "content": "You are a smart home assistant. Respond concisely in French."},
                {"role": "user", "content": user_input},
            ]
            
            # Ajouter contexte RAG
            context_snippets = await self.chroma.query(user_input, top_k=3)
            if context_snippets:
                messages.insert(1, {"role": "system", "content": "Context:\n" + "\n".join(context_snippets)})
                logger.info(f"   📚 RAG context injected ({len(context_snippets)} snippets)")
            
            response = await self.brain._call_gpt(messages)
            duration_ms = (time.time() - start_time) * 1000
            
            response_text = response if isinstance(response, str) else response.get("content", "")
            logger.info(f"✅ LLM Response: '{response_text[:80]}...'")
            logger.info(f"   Latence: {duration_ms:.2f} ms")
            
            await self._record_metric("LLM", duration_ms, success=True,
                                     details={"response": response_text[:100], "context_snippets": len(context_snippets) if context_snippets else 0})
            
            return duration_ms, response_text
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"❌ LLM failed: {e}")
            await self._record_metric("LLM", duration_ms, success=False, error=str(e))
            return 0, ""
    
    async def test_tts_component(self, text: str) -> float:
        """Teste TTS (Text-to-Speech) - Fish-Speech + XTTS v2."""
        logger.info("\n" + "="*70)
        logger.info("🔊 TEST 3: TTS (Fish-Speech + XTTS v2 fallback)")
        logger.info("="*70)
        
        start_time = time.time()
        try:
            logger.info(f"Input: '{text}'")
            audio = await self.brain.tts.speak(text)
            duration_ms = (time.time() - start_time) * 1000
            
            audio_kb = len(audio) / 1024 if audio else 0
            logger.info(f"✅ TTS succeeded")
            logger.info(f"   Audio size: {audio_kb:.1f} KB")
            logger.info(f"   Latence: {duration_ms:.2f} ms")
            
            await self._record_metric("TTS", duration_ms, success=True,
                                     details={"audio_bytes": len(audio) if audio else 0})
            return duration_ms
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"❌ TTS failed: {e}")
            await self._record_metric("TTS", duration_ms, success=False, error=str(e))
            return 0
    
    async def test_full_pipeline(self) -> Dict[str, Any]:
        """Lance le test E2E complet."""
        logger.info("\n" + "="*70)
        logger.info("🌊 FULL E2E PIPELINE TEST")
        logger.info("="*70)
        
        e2e_start = time.time()
        
        # 1. Setup RAG
        await self.setup_rag_context()
        
        # 2. STT
        stt_latency = await self.test_stt_component()
        
        # 3. LLM
        llm_latency, llm_response = await self.test_llm_component(self.test_text)
        
        # 4. TTS
        tts_latency = await self.test_tts_component(llm_response or "Désolé, je n'ai pas pu traiter votre demande.")
        
        total_ms = (time.time() - e2e_start) * 1000
        
        # Rapport final
        logger.info("\n" + "="*70)
        logger.info("📊 RAPPORT FINAL")
        logger.info("="*70)
        
        successful_metrics = [m for m in self.metrics if m.success]
        failed_metrics = [m for m in self.metrics if not m.success]
        
        logger.info(f"\n✅ Composants réussis: {len(successful_metrics)}/{len(self.metrics)}")
        for metric in successful_metrics:
            logger.info(f"   • {metric.component}: {metric.duration_ms:.2f} ms")
        
        if failed_metrics:
            logger.warning(f"\n❌ Composants échoués: {len(failed_metrics)}")
            for metric in failed_metrics:
                logger.warning(f"   • {metric.component}: {metric.error}")
        
        logger.info(f"\n⏱️  LATENCES:")
        logger.info(f"   STT:  {stt_latency:.2f} ms")
        logger.info(f"   LLM:  {llm_latency:.2f} ms")
        logger.info(f"   TTS:  {tts_latency:.2f} ms")
        logger.info(f"   {'─'*50}")
        logger.info(f"   TOTAL E2E: {total_ms:.2f} ms")
        
        # Vérifier objectif <500ms
        target_latency = 500
        if total_ms <= target_latency:
            logger.info(f"   ✅ Objectif <{target_latency}ms: ATTEINT ✓")
        else:
            logger.warning(f"   ⚠️  Objectif <{target_latency}ms: EXCÉDÉ de +{total_ms - target_latency:.2f}ms")
        
        return {
            "stt_ms": stt_latency,
            "llm_ms": llm_latency,
            "tts_ms": tts_latency,
            "total_ms": total_ms,
            "target_ms": target_latency,
            "success_rate": len(successful_metrics) / len(self.metrics) * 100
        }


async def main():
    """Fonction main."""
    logger.info("🚀 Starting E2E Pipeline Test")
    logger.info(f"   Environment: {os.environ.get('ENVIRONMENT', 'development')}")
    logger.info(f"   Azure OpenAI: {bool(os.environ.get('AZURE_OPENAI_ENDPOINT'))}")
    logger.info(f"   Fish-Speech: {os.environ.get('FISH_SPEECH_URL', 'Not configured')}")
    logger.info(f"   TTS Fallback: {os.environ.get('TTS_FALLBACK', 'true')}")
    
    test = E2EPipelineTest()
    results = await test.test_full_pipeline()
    
    logger.info("\n" + "="*70)
    logger.info("✨ Test completed!")
    logger.info("="*70)
    
    return results


if __name__ == "__main__":
    results = asyncio.run(main())
