#!/usr/bin/env python3
"""
Démo interactive: Voice input → LLM → Voice output.

Démontre le pipeline audio complet avec latence mesurée.
Support du microphone (si PyAudio disponible) ou input texte simulé.
"""

import asyncio
import sys
import time
import os
from pathlib import Path
from typing import Optional, Tuple
import logging

# Désactiver les warnings de config au démarrage
os.environ["SUPPRESS_CONFIG_WARNINGS"] = "1"

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hardware.hardware_accel import HardwareAccelerator

# Brain optionnelle
try:
    from src.brain.brain_engine import BrainEngine
    from src.config import Config
    HAS_BRAIN = True
except Exception as e:
    HAS_BRAIN = False
    logger_warning = f"Brain non available: {e}"

# Importation optionnelle audio capture
try:
    from src.audio.audio_capture import AudioCapture
    HAS_AUDIO_CAPTURE = True
except ImportError:
    HAS_AUDIO_CAPTURE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class VoiceAssistant:
    """Assistant personnel avec interface vocale."""
    
    def __init__(self):
        """Initialise l'assistant."""
        self.hardware = HardwareAccelerator()
        
        self.brain = None
        if HAS_BRAIN:
            try:
                config = Config()
                self.brain = BrainEngine(config)
            except Exception as e:
                logger.warning(f"BrainEngine non disponible: {e}")
        
        self.audio_capture: Optional[AudioCapture] = None
        if HAS_AUDIO_CAPTURE:
            try:
                self.audio_capture = AudioCapture()
            except Exception as e:
                logger.warning(f"Audio capture non disponible: {e}")
    
    async def process_voice_input(
        self,
        audio_data: bytes
    ) -> Tuple[str, float]:
        """
        Convertit audio → texte avec mesure de latence.
        
        Returns:
            (texte, latence_ms)
        """
        start_time = time.time()
        try:
            text = await self.hardware.transcribe_audio(audio_data)
            latency_ms = (time.time() - start_time) * 1000
            return text, latency_ms
        except Exception as e:
            logger.error(f"Erreur STT: {e}")
            return f"[Erreur STT: {e}]", 0
    
    async def process_text_response(
        self,
        text: str,
        room: str = "salon"
    ) -> Tuple[dict, float]:
        """
        Traite le texte avec LLM avec mesure de latence.
        
        Returns:
            (réponse, latence_ms)
        """
        if not self.brain:
            return {"text": "Assistant LLM non disponible"}, 0
        
        start_time = time.time()
        try:
            response = await self.brain.process_command(text, room=room)
            latency_ms = (time.time() - start_time) * 1000
            return response, latency_ms
        except Exception as e:
            logger.error(f"Erreur LLM: {e}")
            return {"text": f"[Erreur LLM: {e}]"}, 0
    
    async def synthesize_response(
        self,
        text: str
    ) -> Tuple[Optional[bytes], float]:
        """
        Synthétise texte → audio avec mesure de latence.
        
        Returns:
            (audio_bytes, latence_ms)
        """
        start_time = time.time()
        try:
            audio = await self.hardware.text_to_speech(text)
            latency_ms = (time.time() - start_time) * 1000
            return audio, latency_ms
        except Exception as e:
            logger.warning(f"Erreur TTS: {e}")
            return None, 0
    
    async def display_latency_stats(
        self,
        stt_ms: float,
        llm_ms: float,
        tts_ms: float
    ) -> None:
        """Affiche les stats de latence."""
        total_ms = stt_ms + llm_ms + tts_ms
        
        logger.info(f"\n⏱️  LATENCE DÉTAILLÉE:")
        logger.info(f"   🎤 STT: {stt_ms:6.2f} ms")
        logger.info(f"   🧠 LLM: {llm_ms:6.2f} ms")
        logger.info(f"   🔊 TTS: {tts_ms:6.2f} ms")
        logger.info(f"   {'─'*20}")
        logger.info(f"   ⌛ TOTAL: {total_ms:6.2f} ms")
        
        # Cible <500ms
        target = 500
        if total_ms <= target:
            logger.info(f"   ✅ Objectif <{target}ms: ATTEINT!")
        else:
            logger.warning(f"   ⚠️  Objectif <{target}ms: excédé de +{total_ms-target:.0f}ms")
    
    async def run_interactive_demo(self) -> None:
        """Lance la démo interactive."""
        logger.info("=" * 80)
        logger.info("🎤 DÉMO VOICE INTERACTIVE - Assistant Personnel")
        logger.info("=" * 80)
        
        logger.info("\n💡 Modes disponibles:")
        logger.info("   1. Micro réel (si PyAudio disponible)")
        logger.info("   2. Input texte (simulation)")
        
        if self.audio_capture:
            logger.info("\n🎙️  PyAudio détecté - Mic capture disponible!\n")
            await self._demo_with_mic()
        else:
            logger.info("\n⚠️  PyAudio non disponible - Mode simulation texte\n")
            await self._demo_with_text()
    
    async def _demo_with_mic(self) -> None:
        """Démo avec microphone réel."""
        logger.info("🎤 MODE MICROPHONE RÉEL")
        logger.info("─" * 80)
        
        # Lister appareils
        try:
            if self.audio_capture:
                logger.info("\n📋 Périphériques audio disponibles:")
                self.audio_capture.list_devices()
        except:
            pass
        
        logger.info("\n💬 Test: Prononcez quelque chose pendant 3 secondes...")
        logger.info("   (La demo va capturer, transcrire, traiter et répondre)")
        
        try:
            # Capturer audio
            if not self.audio_capture:
                logger.error("Capture audio non disponible")
                return
            
            logger.info("\n🔴 Enregistrement... (3 secondes)")
            audio_data = await self.audio_capture.record_duration(3.0)
            
            if not audio_data:
                logger.warning("Aucun audio capturé")
                return
            
            logger.info(f"✓ Audio capturé ({len(audio_data)} bytes)")
            
            # STT
            logger.info("\n[1/3] STT (audio → texte)...")
            text, stt_ms = await self.process_voice_input(audio_data)
            logger.info(f"✓ Transcription: '{text}'")
            logger.info(f"  Latence: {stt_ms:.2f} ms")
            
            # LLM
            logger.info(f"\n[2/3] LLM (texte → réponse)...")
            response, llm_ms = await self.process_text_response(text)
            response_text = response.get("text", "")
            logger.info(f"✓ Réponse: '{response_text[:80]}'")
            logger.info(f"  Latence: {llm_ms:.2f} ms")
            
            # TTS
            logger.info(f"\n[3/3] TTS (réponse → audio)...")
            audio_out, tts_ms = await self.synthesize_response(response_text)
            if audio_out:
                logger.info(f"✓ Audio générée ({len(audio_out)} bytes)")
                logger.info(f"  Latence: {tts_ms:.2f} ms")
            else:
                logger.warning("TTS indisponible")
            
            # Stats
            await self.display_latency_stats(stt_ms, llm_ms, tts_ms)
            
        except Exception as e:
            logger.error(f"Erreur demo mic: {e}", exc_info=True)
    
    async def _demo_with_text(self) -> None:
        """Démo avec input texte simulé."""
        logger.info("📝 MODE SIMULATION TEXTE")
        logger.info("─" * 80)
        
        # Prompts de test
        test_inputs = [
            {
                "text": "Quelle est la signification philosophique de l'existence?",
                "room": "salon",
                "category": "Philosophie"
            },
            {
                "text": "Allume les lumières du salon à 80%",
                "room": "salon",
                "category": "Domotique"
            }
        ]
        
        for i, test in enumerate(test_inputs, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"Test {i}/2: {test['category']}")
            logger.info(f"{'='*80}")
            
            input_text = test["text"]
            logger.info(f"\n👤 Input: '{input_text}'")
            
            # Simuler STT (très rapide en mode texte)
            stt_ms = 100  # Simulation
            logger.info(f"\n✓ STT simulée: {stt_ms:.2f} ms")
            
            # LLM
            logger.info(f"\n[Processing LLM...]")
            response, llm_ms = await self.process_text_response(
                input_text,
                room=test["room"]
            )
            response_text = response.get("text", "")
            logger.info(f"✓ Réponse: '{response_text[:100]}...'")
            logger.info(f"  Latence LLM: {llm_ms:.2f} ms")
            
            # TTS simulation
            tts_ms = 200  # Simulation (Fish-Speech pas disponible)
            logger.info(f"\n✓ TTS simulée: {tts_ms:.2f} ms")
            
            # Stats
            await self.display_latency_stats(stt_ms, llm_ms, tts_ms)
            
            await asyncio.sleep(1)
        
        logger.info(f"\n{'='*80}")
        logger.info("✅ DÉMO TERMINÉE")
        logger.info("=" * 80)


async def main():
    """Fonction principale."""
    assistant = VoiceAssistant()
    
    logger.info("\n" + "=" * 80)
    logger.info("🚀 DÉMARRAGE ASSISTANT VOCAL")
    logger.info("=" * 80)
    
    try:
        await assistant.run_interactive_demo()
    except KeyboardInterrupt:
        logger.info("\n⏸️  Démo interrompue par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    logger.info("\n" + "▶️  VOICE INTERACTIVE DEMO")
    logger.info("   Mode: STT + LLM + TTS avec mesure latence\n")
    
    asyncio.run(main())
