"""listener.py - Boucle d'écoute permanente d'EXO.

Pipeline complet et permanent:
  1. Écoute micro en continu (VAD)
  2. Transcription Whisper de chaque utterance
  3. Détection du wake word "EXO"
  4. Extraction de la commande
  5. Réponse GPT-4o (BrainEngine)
  6. Synthèse vocale (TTSClient → OpenAI TTS nova)
  7. Playback audio (pygame)

Ce module est le cœur de l'assistant : il tourne en boucle infinie
et ne s'arrête que sur Ctrl+C.
"""

import asyncio
import io
import os
import sys
import time
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ─── Configuration par défaut ────────────────────────────
DEFAULT_DEVICE_INDEX = None      # None = micro par défaut du système
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
CHANNELS = 1
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")  # "base" = rapide sur CPU, bon FR
FOLLOWUP_TIMEOUT_SEC = 7.0      # Attente après "Exo" seul (généreux)


class ExoListener:
    """Boucle d'écoute permanente avec wake word, STT, LLM et TTS."""

    def __init__(
        self,
        device_index: Optional[int] = None,
        whisper_model: str = WHISPER_MODEL,
    ):
        """
        Args:
            device_index: Index du micro PyAudio (None = défaut système)
            whisper_model: Taille modèle Whisper (tiny/base/small/medium/large)
        """
        self.device_index = device_index
        self.whisper_model_name = whisper_model

        # Composants (initialisés dans start())
        self._whisper = None
        self._brain = None
        self._tts = None
        self._pa = None
        self._stream = None
        self._pygame_ready = False

    # ─── Initialisation ───────────────────────────────────

    async def _init_all(self):
        """Initialise tous les composants."""
        import pyaudio  # type: ignore

        logger.info("=" * 55)
        logger.info("  EXO — Assistant vocal permanent")
        logger.info("  Dites « Exo » suivi de votre commande")
        logger.info("=" * 55)

        # 1. Faster-Whisper (STT)
        logger.info("Chargement Faster-Whisper (%s)...", self.whisper_model_name)
        from faster_whisper import WhisperModel  # type: ignore

        t0 = time.time()
        loop = asyncio.get_running_loop()
        self._whisper = await loop.run_in_executor(
            None,
            lambda: WhisperModel(
                self.whisper_model_name,
                device="cpu",
                compute_type="float32",
            ),
        )
        logger.info("✅ Whisper OK (modèle: %s, chargé en %.1fs)", self.whisper_model_name, time.time() - t0)

        # 2. BrainEngine (GPT-4o)
        logger.info("Initialisation BrainEngine...")
        from src.brain.brain_engine import BrainEngine

        self._brain = BrainEngine()
        await self._brain.initialize()
        logger.info("✅ Brain OK")

        # 3. TTSClient (Kokoro → Piper → OpenAI fallback)
        logger.info("Initialisation TTSClient...")
        from src.assistant.tts_client import TTSClient

        self._tts = TTSClient()
        self._tts.preload()  # Pré-charger pour éviter latence au 1er appel
        logger.info("✅ TTS OK")

        # 4. Pygame mixer (playback — sample rate adapté au moteur TTS)
        import pygame  # type: ignore

        tts_sr = self._tts.sample_rate  # 22050 (Piper) ou 24000 (Kokoro/OpenAI)
        pygame.mixer.init(frequency=tts_sr, size=-16, channels=1)
        self._pygame_ready = True
        logger.info(f"✅ Pygame mixer OK (frequency={tts_sr}Hz)")

        # 5. Microphone (PyAudio)
        self._pa = pyaudio.PyAudio()

        # Résoudre le device index
        if self.device_index is None:
            self.device_index = self._find_best_input_device()

        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=CHUNK_SIZE,
        )
        dev_name = self._pa.get_device_info_by_index(self.device_index).get("name", "?")
        logger.info("✅ Micro ouvert — device %d : %s (%d Hz)", self.device_index, dev_name, SAMPLE_RATE)

        # 6. Calibration du bruit ambiant (seuil VAD adaptatif)
        from src.audio.wake_word import calibrate_noise_floor
        logger.info("🔇 Calibration bruit ambiant (silence 2s)...")
        calibrate_noise_floor(self._stream, CHUNK_SIZE)

    def _find_best_input_device(self) -> int:
        """Trouve le meilleur micro disponible."""
        assert self._pa is not None
        try:
            default_info = self._pa.get_default_input_device_info()
            idx = int(default_info["index"])
            logger.info("Micro par défaut : %s (index %d)", default_info.get("name"), idx)
            return idx
        except Exception:
            # Fallback : premier device avec input > 0
            for i in range(self._pa.get_device_count()):
                info = self._pa.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    logger.info("Micro fallback : %s (index %d)", info.get("name"), i)
                    return i
            raise RuntimeError("Aucun microphone trouvé")

    # ─── Transcription ────────────────────────────────────

    def _transcribe(self, audio_bytes: bytes) -> str:
        """Transcrit un buffer PCM16 avec Whisper (sync, thread-safe)."""
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if len(samples) < 4800:  # < 0.3s → trop court
            return ""
        segments, _ = self._whisper.transcribe(
            samples, language="fr", beam_size=1,
            no_speech_threshold=0.85,
            log_prob_threshold=-1.5,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        return " ".join(seg.text for seg in segments).strip()

    # ─── Playback ─────────────────────────────────────────

    def _play_audio_wav(self, audio_data: bytes):
        """Fallback : joue des bytes WAV via pygame (sync)."""
        import pygame  # type: ignore

        try:
            sound = pygame.mixer.Sound(io.BytesIO(audio_data))
            sound.play()
            while pygame.mixer.get_busy():
                pygame.time.wait(50)
        except Exception as e:
            logger.error("Erreur playback WAV : %s", e)

    def _flush_input_buffer(self):
        """Vide le buffer micro pour éviter qu'EXO s'entende elle-même."""
        if not self._stream:
            return
        try:
            avail = self._stream.get_read_available()
            while avail > 0:
                self._stream.read(min(avail, CHUNK_SIZE), exception_on_overflow=False)
                avail = self._stream.get_read_available()
        except Exception:
            pass

    # ─── Traitement d'une commande ────────────────────────

    async def _process_command(self, command_text: str):
        """Pipeline commande → GPT-4o → TTS WAV → playback pygame.

        Fiable et propre :
        - Téléchargement WAV complet (tts-1 = rapide, ~1-2s)
        - Playback pygame (pas de grésillements, qualité parfaite)
        - Micro coupé pendant la réponse (évite auto-écoute)
        - Buffer micro vidé après playback
        - Instrumentation timing complète
        """
        logger.info("💬 COMMANDE : « %s »", command_text)
        t0_total = time.time()

        # ── Couper le micro pendant la réponse ──
        if self._stream:
            self._stream.stop_stream()

        # ── Brain (GPT-4o) ──
        t0 = time.time()
        result = await self._brain.process_command(
            text=command_text,
            room="local",
            context={"source": "wake_word"},
        )
        brain_time = time.time() - t0
        response_text = result.get("text", "")
        function_calls = result.get("function_calls", [])

        logger.info("🤖 Réponse (%0.2fs) : %s", brain_time, response_text[:200])

        if function_calls:
            for fc in function_calls:
                logger.info("🔧 Action : %s(%s)", fc["name"], fc["arguments"])

        # ── TTS + Playback ──
        if response_text:
            t0 = time.time()
            try:
                audio = await self._tts.speak(response_text)
                tts_time = time.time() - t0
                logger.info("🔊 TTS (%.2fs, %dKB)", tts_time, len(audio) // 1024)

                # Playback pygame (propre, sans grésillements)
                import pygame  # type: ignore
                t0_play = time.time()
                sound = pygame.mixer.Sound(io.BytesIO(audio))
                sound.play()
                while pygame.mixer.get_busy():
                    await asyncio.sleep(0.05)

                play_time = time.time() - t0_play
                total_time = time.time() - t0_total
                logger.info("✅ Pipeline complet : Brain=%.2fs + TTS=%.2fs + Play=%.2fs = TOTAL %.2fs",
                            brain_time, tts_time, play_time, total_time)
            except Exception as e:
                logger.error("Erreur TTS/playback : %s", e)
                print(f"\n  EXO : {response_text}\n")

        # ── Réactiver le micro et vider le buffer ──
        if self._stream:
            self._stream.start_stream()
            self._flush_input_buffer()

    # ─── Boucle principale ────────────────────────────────

    async def start(self):
        """Lance la boucle d'écoute permanente. Bloque jusqu'à Ctrl+C."""
        from src.audio.wake_word import (
            contains_wake_word,
            extract_command_after_wake,
            is_hallucination,
        )
        from src.audio.streaming_stt import streaming_capture_and_transcribe

        await self._init_all()

        logger.info("")
        logger.info("👂 En écoute permanente — dites « Exo » pour activer.")
        logger.info("   Ctrl+C pour quitter.")
        logger.info("─" * 55)

        try:
            while True:
                # ── Étape 1+2 : Capture + Transcription streaming ──
                transcript, utterance, timing = await streaming_capture_and_transcribe(
                    self._stream,
                    self._whisper,
                    sample_rate=SAMPLE_RATE,
                    chunk_size=CHUNK_SIZE,
                )

                if not transcript:
                    continue

                # Filtrer les hallucinations Whisper (bruit de fond)
                if is_hallucination(transcript):
                    logger.debug("Hallucination filtrée : « %s »", transcript)
                    continue

                reused_tag = " ⚡réutilisé" if timing.get("reused") else ""
                logger.info("📝 Entendu : « %s » (capture=%.2fs, audio=%.1fs, STT=%.2fs%s)",
                            transcript, timing.get("capture_sec", 0),
                            timing.get("audio_sec", 0), timing.get("stt_sec", 0),
                            reused_tag)

                # ── Étape 3 : Wake word ? ─────────────────
                if not contains_wake_word(transcript):
                    continue  # Pas de wake word, on ignore

                logger.info("=" * 55)
                logger.info("  ✨ WAKE WORD « EXO » DÉTECTÉ")
                logger.info("=" * 55)

                # ── Étape 4 : Extraire la commande ────────
                command = extract_command_after_wake(transcript)

                if len(command.split()) >= 2:
                    # Commande déjà dans l'utterance
                    await self._process_command(command)
                else:
                    # Juste "Exo" → attendre la suite
                    if command:
                        logger.info("Fragment : « %s » — attente suite...", command)
                    else:
                        logger.info("Juste « Exo » — attente commande...")
                    logger.info("🎤 Parlez maintenant (timeout %ds)...", FOLLOWUP_TIMEOUT_SEC)

                    # Retry loop avec timeout réel (évite les faux timeouts par bruit)
                    followup_text = ""
                    deadline = time.time() + FOLLOWUP_TIMEOUT_SEC
                    while time.time() < deadline:
                        remaining = deadline - time.time()
                        if remaining <= 0:
                            break
                        text, _, _ = await streaming_capture_and_transcribe(
                            self._stream,
                            self._whisper,
                            sample_rate=SAMPLE_RATE,
                            chunk_size=CHUNK_SIZE,
                            min_sec=0.3,
                            timeout_sec=remaining,
                        )
                        if text:
                            followup_text = text
                            break  # Vrai audio capturé + transcrit

                    if not followup_text:
                        logger.warning("⏱ Timeout — aucune commande après « Exo »")
                        logger.info("👂 En écoute...")
                        continue

                    full_command = (command + " " + followup_text).strip() if command else followup_text
                    await self._process_command(full_command)

                logger.info("─" * 55)
                logger.info("👂 En écoute — dites « Exo » pour activer.")

        except KeyboardInterrupt:
            logger.info("\n⚠️ Arrêt demandé par l'utilisateur")

        finally:
            await self.shutdown()

    # ─── Shutdown ─────────────────────────────────────────

    async def shutdown(self):
        """Libère toutes les ressources proprement."""
        logger.info("🛑 Arrêt d'EXO...")

        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass

        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass

        if self._brain:
            await self._brain.close()

        if self._pygame_ready:
            try:
                import pygame  # type: ignore
                pygame.mixer.quit()
            except Exception:
                pass

        logger.info("✅ Ressources libérées. Au revoir !")
