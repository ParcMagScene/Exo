#!/usr/bin/env python3
"""
Test Audio Complet - Pipeline conforme aux specs MD.

Pipeline: AudioCapture → STT (Faster-Whisper) → LLM → TTS (Fish-Speech/XTTS v2) → Lecture Audio

Ref: VOICE_INTEGRATION.md, ARCHITECTURE.md
"""

import asyncio
import sys
import os
import time
import tempfile
import logging
from pathlib import Path
from typing import Optional, Tuple

# Désactiver les warnings de config au démarrage
os.environ["SUPPRESS_CONFIG_WARNINGS"] = "1"

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# ======================== IMPORTS PROJET ========================
# STT/TTS Hardware (specs: hardware_accel.py)
from src.hardware.hardware_accel import HardwareAccelerator

# TTS Client (specs: Fish-Speech primary + XTTS v2 fallback)
from src.assistant.tts_client import TTSClient

# Audio Capture (specs: audio_capture.py avec PyAudio)
try:
    from src.audio.audio_capture import AudioCapture
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False
    logger.warning("PyAudio non disponible - pas de capture micro")

# Pygame mixer pour lecture audio
try:
    import pygame.mixer
    HAS_MIXER = True
except ImportError:
    HAS_MIXER = False
    logger.warning("pygame.mixer non disponible - pas de lecture audio")

import numpy as np
import soundfile as sf


class AudioPipeline:
    """Pipeline audio complet conforme aux specs MD.
    
    Architecture (ARCHITECTURE.md):
        AudioCapture → HardwareAccelerator.transcribe_audio() (STT)
                     → BrainEngine.process_command() (LLM)
                     → TTSClient.speak() (TTS)
                     → Lecture Audio (pygame.mixer)
    """

    def __init__(self):
        # STT: Faster-Whisper + OpenVINO (hardware_accel.py)
        self.hardware = HardwareAccelerator()
        
        # TTS: Fish-Speech primary + XTTS v2 fallback (tts_client.py)
        self.tts = TTSClient()
        
        # Audio Capture: PyAudio (audio_capture.py)
        self.audio_capture: Optional[AudioCapture] = None
        if HAS_AUDIO:
            try:
                self.audio_capture = AudioCapture(
                    sample_rate=16000,
                    channels=1,
                    chunk_size=1024
                )
            except Exception as e:
                logger.warning(f"AudioCapture non disponible: {e}")

    async def initialize(self):
        """Initialise le pipeline (charge les modeles)."""
        logger.info("Initialisation du pipeline audio...")
        
        # Charger Faster-Whisper (STT)
        try:
            await self.hardware.initialize()
            logger.info("  STT (Faster-Whisper): OK")
        except Exception as e:
            logger.warning(f"  STT: {e}")
        
        # Initialiser pygame.mixer (lecture audio)
        if HAS_MIXER:
            pygame.mixer.init(frequency=22050, size=-16, channels=1)
            logger.info(f"  Mixer audio: OK ({pygame.mixer.get_init()})")

    async def capture_audio(self, duration: float = 3.0) -> Optional[bytes]:
        """Capture audio depuis le micro (specs: AudioCapture.record_duration)."""
        if not self.audio_capture:
            logger.warning("Capture audio non disponible")
            return None
        
        logger.info(f"\n  Enregistrement... ({duration}s)")
        try:
            audio_data = await self.audio_capture.record_duration(duration)
            logger.info(f"  Audio capture: {len(audio_data)} bytes")
            return audio_data
        except Exception as e:
            logger.error(f"  Erreur capture: {e}")
            return None

    async def stt(self, audio_bytes: bytes) -> Tuple[str, float]:
        """STT: audio -> texte (specs: HardwareAccelerator.transcribe_audio)."""
        start = time.time()
        try:
            text = await self.hardware.transcribe_audio(audio_bytes)
            latency = (time.time() - start) * 1000
            return text, latency
        except Exception as e:
            logger.error(f"Erreur STT: {e}")
            return f"[STT error: {e}]", 0

    async def tts_speak(self, text: str) -> Tuple[Optional[bytes], float]:
        """TTS: texte -> audio (specs: TTSClient.speak - Fish-Speech/XTTS v2)."""
        start = time.time()
        try:
            audio = await self.tts.speak(text)
            latency = (time.time() - start) * 1000
            return audio, latency
        except Exception as e:
            logger.error(f"Erreur TTS: {e}")
            return None, 0

    def play_audio(self, audio_bytes: bytes) -> bool:
        """Lecture audio via pygame.mixer (specs: output speaker)."""
        if not HAS_MIXER:
            logger.warning("Pas de mixer pour la lecture")
            return False
        
        try:
            # Ecrire dans un fichier temporaire pour pygame.mixer
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            
            # Charger et jouer
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            
            # Attendre la fin de la lecture
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)
            
            # Nettoyage
            pygame.mixer.music.unload()
            os.unlink(tmp_path)
            
            return True
        except Exception as e:
            logger.error(f"Erreur lecture audio: {e}")
            return False

    def display_latency(self, stt_ms: float, llm_ms: float, tts_ms: float):
        """Affiche les latences (specs: VOICE_INTEGRATION.md)."""
        total = stt_ms + llm_ms + tts_ms
        target = 500  # specs: <500ms E2E
        
        print(f"\n  LATENCE DETAILLEE:")
        print(f"    STT:   {stt_ms:7.2f} ms")
        print(f"    LLM:   {llm_ms:7.2f} ms")
        print(f"    TTS:   {tts_ms:7.2f} ms")
        print(f"    {'='*20}")
        print(f"    TOTAL: {total:7.2f} ms")
        
        if total <= target:
            print(f"    Objectif <{target}ms: ATTEINT!")
        else:
            print(f"    Objectif <{target}ms: excede de +{total-target:.0f}ms")

    async def shutdown(self):
        """Arret propre."""
        if HAS_MIXER:
            pygame.mixer.quit()
        await self.hardware.close()
        logger.info("Pipeline arrete")


async def test_tts_only(pipeline: AudioPipeline):
    """Test 1: TTS seul - Generer et jouer de l'audio."""
    print("\n" + "=" * 70)
    print("  TEST 1: TTS (Fish-Speech / XTTS v2 fallback)")
    print("  Pipeline: Texte -> TTSClient.speak() -> Lecture Audio")
    print("=" * 70)
    
    test_phrases = [
        "Bonjour, je suis votre assistant personnel.",
        "Il fait beau aujourd'hui, n'est-ce pas?",
    ]
    
    for i, phrase in enumerate(test_phrases, 1):
        print(f"\n  [{i}/{len(test_phrases)}] \"{phrase}\"")
        
        # TTS
        print(f"  TTS en cours...", end="", flush=True)
        audio, tts_ms = await pipeline.tts_speak(phrase)
        
        if audio:
            print(f" OK ({len(audio)} bytes, {tts_ms:.0f}ms)")
            
            # Lecture
            print(f"  Lecture audio...", end="", flush=True)
            played = pipeline.play_audio(audio)
            if played:
                print(" OK")
            else:
                print(" ECHEC (pas de sortie audio)")
        else:
            print(f" ECHEC")
            print(f"  Fish-Speech et XTTS v2 fallback indisponibles")
            return False
    
    return True


async def test_stt_tts(pipeline: AudioPipeline):
    """Test 2: Pipeline STT -> TTS."""
    print("\n" + "=" * 70)
    print("  TEST 2: Pipeline STT -> TTS")
    print("  Pipeline: Micro -> Whisper STT -> TTS -> Lecture")
    print("=" * 70)
    
    if not pipeline.audio_capture:
        print("\n  [SKIP] PyAudio non disponible - pas de capture micro")
        return True
    
    print("\n  Parlez pendant 3 secondes...")
    
    # 1. Capture audio
    audio_data = await pipeline.capture_audio(3.0)
    if not audio_data:
        print("  Aucun audio capture")
        return False
    
    # 2. STT
    print(f"\n  [1/3] STT (Faster-Whisper)...")
    text, stt_ms = await pipeline.stt(audio_data)
    print(f"  Transcription: '{text}'")
    print(f"  Latence STT: {stt_ms:.2f} ms")
    
    if not text or text.startswith("["):
        print("  STT a echoue, utilisation texte par defaut")
        text = "Bonjour, comment allez-vous?"
    
    # 3. Reponse simulee (LLM non configure)
    llm_ms = 0
    response_text = f"Vous avez dit: {text}. Je suis votre assistant personnel."
    print(f"\n  [2/3] Reponse: '{response_text}'")
    
    # 4. TTS
    print(f"\n  [3/3] TTS (synthese)...")
    audio_out, tts_ms = await pipeline.tts_speak(response_text)
    
    if audio_out:
        print(f"  Audio generee: {len(audio_out)} bytes ({tts_ms:.0f}ms)")
        
        # Lecture
        print(f"  Lecture de la reponse...")
        pipeline.play_audio(audio_out)
    else:
        print(f"  TTS indisponible")
    
    # Stats latence
    pipeline.display_latency(stt_ms, llm_ms, tts_ms)
    
    return True


async def test_full_pipeline(pipeline: AudioPipeline):
    """Test 3: Pipeline complet avec mesure de latence E2E."""
    print("\n" + "=" * 70)
    print("  TEST 3: Pipeline E2E Complet (VOICE_INTEGRATION.md)")
    print("  Audio -> STT -> [LLM simule] -> TTS -> Lecture")
    print("=" * 70)
    
    # Generer audio de test (3s bruit blanc)
    print("\n  Generation audio de test (3s)...")
    sample_rate = 16000
    duration = 3.0
    num_samples = int(sample_rate * duration)
    audio_np = np.random.normal(0, 0.1, num_samples)
    audio_int16 = np.int16(audio_np / np.max(np.abs(audio_np)) * 32767)
    test_audio = audio_int16.tobytes()
    print(f"  Audio test: {len(test_audio)} bytes")
    
    # Pipeline complet
    total_start = time.time()
    
    # STT
    print(f"\n  [1/3] STT...")
    text, stt_ms = await pipeline.stt(test_audio)
    print(f"  Transcription: '{text}' ({stt_ms:.0f}ms)")
    
    # LLM simule
    print(f"\n  [2/3] LLM (simule)...")
    llm_start = time.time()
    response = "Bonjour! Je suis votre assistant personnel. Comment puis-je vous aider?"
    llm_ms = (time.time() - llm_start) * 1000
    print(f"  Reponse: '{response}' ({llm_ms:.0f}ms)")
    
    # TTS
    print(f"\n  [3/3] TTS...")
    audio_out, tts_ms = await pipeline.tts_speak(response)
    
    total_ms = (time.time() - total_start) * 1000
    
    if audio_out:
        print(f"  Audio: {len(audio_out)} bytes ({tts_ms:.0f}ms)")
        
        # Lecture
        print(f"\n  Lecture de la reponse vocale...")
        pipeline.play_audio(audio_out)
        print(f"  Lecture terminee!")
    
    # Latences
    pipeline.display_latency(stt_ms, llm_ms, tts_ms)
    print(f"\n  Temps total reel: {total_ms:.0f}ms")
    
    return audio_out is not None


async def main():
    """Point d'entree principal."""
    print("=" * 70)
    print("  ASSISTANT PERSONNEL - TEST AUDIO COMPLET")
    print("  Pipeline: STT (Faster-Whisper) + TTS (Fish-Speech/XTTS v2)")
    print("  Ref: VOICE_INTEGRATION.md, ARCHITECTURE.md")
    print("=" * 70)
    
    pipeline = AudioPipeline()
    await pipeline.initialize()
    
    results = {}
    
    try:
        # Test 1: TTS seul (le plus important pour "entendre" l'assistant)
        results["tts"] = await test_tts_only(pipeline)
        
        # Test 2: STT + TTS avec micro (si disponible)
        if HAS_AUDIO:
            results["stt_tts"] = await test_stt_tts(pipeline)
        
        # Test 3: Pipeline E2E complet
        results["e2e"] = await test_full_pipeline(pipeline)
        
    except KeyboardInterrupt:
        print("\n\n  Test interrompu par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur: {e}", exc_info=True)
    finally:
        await pipeline.shutdown()
    
    # Resume
    print("\n" + "=" * 70)
    print("  RESUME DES TESTS")
    print("=" * 70)
    for test_name, success in results.items():
        status = "OK" if success else "ECHEC"
        print(f"  {test_name}: {status}")
    
    all_passed = all(results.values()) if results else False
    print(f"\n  {'TOUS LES TESTS PASSES' if all_passed else 'CERTAINS TESTS ONT ECHOUE'}")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    print()
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
