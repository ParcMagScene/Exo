"""streaming_stt.py - STT streaming avec Faster-Whisper.

Transcrit l'audio en parallèle pendant la capture micro, au lieu
d'attendre la fin de l'utterance pour lancer Whisper.

Gain typique: ~0.5-1s sur le pipeline E2E.

Principe:
  1. VAD capture l'audio en continu (même logique que capture_utterance)
  2. Toutes les ~1s de parole, lance Whisper sur l'audio accumulé (thread)
  3. Quand le silence est détecté → la transcription est déjà prête
  4. Pas besoin de re-lancer Whisper → gain ≈ durée de transcription
"""

import asyncio
import concurrent.futures
import logging
import time
from collections import deque
from typing import Dict, Optional, Tuple

import numpy as np

from src.audio.wake_word import (
    DEFAULT_MAX_UTTERANCE_SEC,
    DEFAULT_MIN_UTTERANCE_SEC,
    DEFAULT_MIN_VOICE_CHUNKS,
    DEFAULT_SILENCE_CHUNKS,
    DEFAULT_VOICE_THRESHOLD,
    SILENCE_END_RATIO,
    SILENCE_WINDOW_SIZE,
    calibrate_noise_floor,
    get_adaptive_threshold,
    is_hallucination,
    rms_energy,
)

logger = logging.getLogger(__name__)

# ─── Configuration streaming ─────────────────────────────
TRANSCRIBE_INTERVAL_SEC = 1.0   # Intervalle min entre soumissions Whisper
REUSE_VOICE_THRESHOLD = 6       # Si < N chunks vocaux dans le tail → réutiliser (≈0.4s)


def _transcribe_buffer(whisper_model, audio_bytes: bytes) -> str:
    """Transcrit un buffer PCM16 avec Whisper (sync, pour executor thread)."""
    samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    if len(samples) < 4800:  # < 0.3s
        return ""
    segments, _ = whisper_model.transcribe(
        samples, language="fr", beam_size=1,
        no_speech_threshold=0.85,
        log_prob_threshold=-1.5,
        vad_filter=False,
        condition_on_previous_text=False,  # Évite dérives, accélère
        without_timestamps=True,            # Accélère la transcription
    )
    return " ".join(seg.text for seg in segments).strip()


async def streaming_capture_and_transcribe(
    stream,
    whisper_model,
    sample_rate: int = 16000,
    chunk_size: int = 1024,
    voice_threshold: float = DEFAULT_VOICE_THRESHOLD,
    silence_chunks_end: int = DEFAULT_SILENCE_CHUNKS,
    min_sec: float = DEFAULT_MIN_UTTERANCE_SEC,
    max_sec: float = DEFAULT_MAX_UTTERANCE_SEC,
    timeout_sec: Optional[float] = None,
    executor: Optional[concurrent.futures.ThreadPoolExecutor] = None,
) -> Tuple[str, bytes, Dict]:
    """Capture audio avec VAD + transcription Whisper en parallèle.

    Même logique VAD que capture_utterance(), mais lance des transcriptions
    Whisper en arrière-plan pendant la capture. Quand le silence est détecté,
    la transcription est souvent déjà disponible → on économise ~0.5-1s.

    Args:
        stream: PyAudio stream ouvert en input
        whisper_model: Instance WhisperModel Faster-Whisper
        sample_rate: Fréquence d'échantillonnage (16000)
        chunk_size: Taille de chaque chunk lu (1024)
        voice_threshold: Seuil RMS fixe (ajusté par l'adaptatif)
        silence_chunks_end: Chunks silencieux consécutifs = fin d'utterance
        min_sec: Durée minimum d'une utterance valide
        max_sec: Durée maximum (sécurité)
        timeout_sec: Abandon si aucune voix après ce délai
        executor: ThreadPoolExecutor dédié pour Whisper (None = pool par défaut)

    Returns:
        (transcript, audio_bytes, timing_info)
        timing_info: dict avec capture_sec, audio_sec, stt_sec, reused (bool)
    """
    import src.audio.wake_word as ww

    # Calibration bruit ambiant si pas encore fait
    if not ww._noise_calibrated:
        calibrate_noise_floor(stream, chunk_size)

    effective_threshold = get_adaptive_threshold(voice_threshold)
    loop = asyncio.get_running_loop()

    # ─── État VAD ─────────────────────────────────────────
    buffer = b""
    silent_count = 0
    voice_detected = False
    voice_chunks = 0
    total_chunks = 0
    max_chunks = int(max_sec * sample_rate / chunk_size)
    timeout_chunks = int(timeout_sec * sample_rate / chunk_size) if timeout_sec else None
    wait_chunks = 0

    # ─── État streaming STT ───────────────────────────────
    pending_future = None
    last_transcript = ""
    last_submit_offset = 0      # byte offset lors du dernier submit
    voice_since_submit = 0      # chunks vocaux depuis dernier submit
    interval_bytes = int(TRANSCRIBE_INTERVAL_SEC * sample_rate * 2)  # PCM16
    recent_voice = deque(maxlen=SILENCE_WINDOW_SIZE)  # Fenêtre glissante
    t0_capture = time.time()

    while total_chunks < max_chunks:
        try:
            data = stream.read(chunk_size, exception_on_overflow=False)
        except Exception:
            await asyncio.sleep(0.01)
            continue

        energy = rms_energy(data)

        if not voice_detected:
            if energy > effective_threshold:
                voice_detected = True
                buffer = data
                silent_count = 0
                voice_chunks = 1
                total_chunks = 1
                voice_since_submit = 1
            else:
                wait_chunks += 1
                if timeout_chunks and wait_chunks >= timeout_chunks:
                    return "", b"", {}
                await asyncio.sleep(0.001)
                continue
        else:
            buffer += data
            total_chunks += 1
            is_voice_chunk = energy >= effective_threshold
            recent_voice.append(is_voice_chunk)

            if not is_voice_chunk:
                silent_count += 1
                if silent_count >= silence_chunks_end:
                    break
            else:
                silent_count = 0
                voice_chunks += 1
                voice_since_submit += 1

            # Fin de parole robuste : fenêtre glissante
            if (voice_chunks >= DEFAULT_MIN_VOICE_CHUNKS
                    and len(recent_voice) >= SILENCE_WINDOW_SIZE):
                voice_ratio = sum(recent_voice) / len(recent_voice)
                if voice_ratio < SILENCE_END_RATIO:
                    break

            # ─── Soumettre transcription si assez de nouvel audio ───
            new_bytes = len(buffer) - last_submit_offset
            if (new_bytes >= interval_bytes
                    and pending_future is None
                    and voice_chunks >= DEFAULT_MIN_VOICE_CHUNKS):
                snapshot = bytes(buffer)
                # Plafonner le buffer intermédiaire à 8s (évite O(n²) si capture longue)
                max_stt_bytes = int(8.0 * sample_rate * 2)
                if len(snapshot) > max_stt_bytes:
                    snapshot = snapshot[-max_stt_bytes:]
                pending_future = loop.run_in_executor(
                    executor, _transcribe_buffer, whisper_model, snapshot
                )
                last_submit_offset = len(buffer)
                voice_since_submit = 0

            # ─── Vérifier si transcription terminée (non-bloquant) ──
            if pending_future is not None and pending_future.done():
                try:
                    result = pending_future.result()
                    if result and not is_hallucination(result, duration):
                        last_transcript = result
                except Exception:
                    pass
                pending_future = None

        await asyncio.sleep(0.001)

    capture_time = time.time() - t0_capture
    duration = len(buffer) / (sample_rate * 2)
    logger.debug("📊 Capture: %.1fs, %d voice/%d total chunks, fenêtre finale: %s",
                 capture_time, voice_chunks, total_chunks,
                 f"{sum(recent_voice)/len(recent_voice):.0%}" if recent_voice else "n/a")

    # ─── Vérifications minimum ────────────────────────────
    if duration < min_sec or voice_chunks < DEFAULT_MIN_VOICE_CHUNKS:
        if pending_future and not pending_future.done():
            pending_future.cancel()
        return "", b"", {}

    # ─── Récupérer la meilleure transcription ─────────────
    t0_stt = time.time()

    # Si une transcription est en cours, l'attendre
    if pending_future is not None:
        try:
            result = await pending_future
            if result and not is_hallucination(result, duration):
                last_transcript = result
        except Exception:
            pass
        pending_future = None

    # Décision : réutiliser le résultat streaming ou re-transcrire ?
    if last_transcript and voice_since_submit < REUSE_VOICE_THRESHOLD:
        # ⚡ La transcription streaming couvre toute la parole → réutiliser !
        stt_time = time.time() - t0_stt
        logger.info(
            "⚡ STT streaming : réutilisé (%.0fms attente, %d voice chunks tail)",
            stt_time * 1000, voice_since_submit,
        )
        return last_transcript, buffer, {
            "capture_sec": capture_time,
            "audio_sec": duration,
            "stt_sec": stt_time,
            "reused": True,
        }

    # Parole significative dans le tail → transcription finale complète
    transcript = await loop.run_in_executor(
        executor, _transcribe_buffer, whisper_model, buffer
    )
    stt_time = time.time() - t0_stt

    if not transcript or is_hallucination(transcript, duration):
        transcript = last_transcript  # fallback sur le dernier bon résultat

    logger.info(
        "📝 STT streaming : transcription finale (%.2fs, %d voice chunks tail)",
        stt_time, voice_since_submit,
    )
    return transcript, buffer, {
        "capture_sec": capture_time,
        "audio_sec": duration,
        "stt_sec": stt_time,
        "reused": False,
    }
