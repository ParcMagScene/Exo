"""
faster_whisper_backend.py — EXO Faster-Whisper GPU/CPU backend

Wraps the faster-whisper library (CTranslate2) for STT transcription.
Supports CUDA GPU (float16) and CPU (int8) inference.

Returns the same dict format as whisper_cpp.py:
  {"text": str, "segments": list[dict], "duration": float}
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import numpy as np

logger = logging.getLogger("exo.stt.faster_whisper")

SAMPLE_RATE = 16000


class FasterWhisperEngine:
    """Faster-Whisper (CTranslate2) STT backend with CUDA GPU support."""

    def __init__(
        self,
        model_size: str = "small",
        device: str = "auto",
        compute_type: str = "auto",
        language: str = "fr",
        beam_size: int = 1,
    ) -> None:
        self.model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self._model = None
        self.actual_device = "unknown"

    def load(self) -> None:
        """Load the Faster-Whisper model."""
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ImportError(
                "faster-whisper not installed. Run: pip install faster-whisper"
            )

        device = self._device
        compute_type = self._compute_type

        # Auto-detect device
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        # Auto compute type based on device
        if compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"

        # Force int8 on CPU (float16 not supported)
        if device == "cpu":
            compute_type = "int8"

        logger.info(
            "Loading faster-whisper '%s' on %s (%s)...",
            self.model_size, device, compute_type,
        )
        t0 = time.monotonic()
        self._model = WhisperModel(
            self.model_size,
            device=device,
            compute_type=compute_type,
        )
        self.actual_device = device
        dt = time.monotonic() - t0
        logger.info(
            "Faster-whisper loaded in %.1fs (device=%s, compute=%s)",
            dt, device, compute_type,
        )

    def transcribe(
        self,
        audio_pcm16: np.ndarray,
        *,
        initial_prompt: Optional[str] = None,
    ) -> dict:
        """
        Transcribe PCM16 audio (16kHz mono).

        Returns:
            {"text": str, "segments": list, "duration": float}
        """
        if self._model is None:
            raise RuntimeError("FasterWhisperEngine not loaded — call load() first")

        audio_f32 = audio_pcm16.astype(np.float32) / 32768.0
        duration = len(audio_f32) / SAMPLE_RATE

        if duration < 0.3:
            logger.warning("Audio %.2fs < 0.3s — ignored", duration)
            return {"text": "", "segments": [], "duration": duration}

        prompt = initial_prompt or (
            "EXO est un assistant vocal domotique français. "
            "Jarvis, allume, éteins, météo, température, lumière."
        )

        t0 = time.monotonic()
        segments_gen, info = self._model.transcribe(
            audio_f32,
            language=self.language,
            beam_size=self.beam_size,
            word_timestamps=False,
            initial_prompt=prompt,
            condition_on_previous_text=False,
            no_speech_threshold=0.4,
            log_prob_threshold=-1.0,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 400,
                "speech_pad_ms": 200,
            },
        )

        segments = []
        full_text_parts = []
        for seg in segments_gen:
            segments.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
            })
            full_text_parts.append(seg.text.strip())

        full_text = " ".join(full_text_parts).strip()
        dt = time.monotonic() - t0
        dt_ms = dt * 1000

        logger.info(
            "[Latency] faster-whisper: %.0f ms (audio=%.1fs RTF=%.2f): %s",
            dt_ms, duration, dt / max(duration, 0.01), full_text[:80],
        )

        return {
            "text": full_text,
            "segments": segments,
            "duration": round(duration, 2),
        }

    def close(self) -> None:
        """Release model resources."""
        self._model = None
        logger.info("FasterWhisperEngine closed")
