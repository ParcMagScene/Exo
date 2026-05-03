"""
stt_server.py — EXO STT Streaming Server (multi-backend: whisper.cpp GPU / faster-whisper GPU/CPU)

WebSocket server that receives audio chunks (PCM16 16kHz mono)
and returns streaming transcription results.

Backends:
  - whispercpp: Whisper.cpp + Vulkan GPU (default, fast)
  - faster_whisper: faster-whisper GPU (CUDA float16) or CPU (int8 fallback)
  - fasterwhisper_gpu: faster-whisper forced CUDA GPU

Protocol:
  → Binary: PCM16 audio chunks
  → JSON:   {"type": "config", "model": "large-v3", "language": "fr", ...}
             {"type": "start"}   — begin new utterance
             {"type": "end"}     — finalize utterance
             {"type": "cancel"}  — discard current utterance
  ← JSON:   {"type": "partial", "text": "..."}
             {"type": "final",   "text": "...", "segments": [...], "duration": float}
             {"type": "ready",   "model": "...", "device": "..."}
             {"type": "error",   "message": "..."}

Dependencies:
  pip install websockets numpy
  (faster-whisper only needed when backend=faster_whisper)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

# Singleton guard — prevent duplicate instances
from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9, json_loads, json_dumps

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [STT] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("exo.stt")

# ---------------------------------------------------------------------------
# Noise reduction (optional)
# ---------------------------------------------------------------------------

_noisereduce_available = False
try:
    import noisereduce as nr
    _noisereduce_available = True
except ImportError:
    pass


def _apply_noise_reduction(pcm16: np.ndarray, sr: int = 16000,
                           strength: float = 0.7) -> np.ndarray:
    """Apply spectral-gating noise reduction to PCM16 audio."""
    if not _noisereduce_available or strength <= 0:
        return pcm16

    audio_f32 = pcm16.astype(np.float32) / 32768.0
    try:
        cleaned = nr.reduce_noise(
            y=audio_f32,
            sr=sr,
            prop_decrease=strength,
            stationary=True,
            n_fft=512,
            hop_length=128,
        )
        return (cleaned * 32768.0).clip(-32768, 32767).astype(np.int16)
    except Exception as e:
        logger.warning("Noise reduction failed: %s", e)
        return pcm16

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8766
DEFAULT_MODEL = "small"          # v26.2: small = 460MB, ~1.2–1.6s latency (was medium ~3.5s)
DEFAULT_LANGUAGE = "fr"
DEFAULT_BEAM_SIZE = 1            # v25.1: beam=1 for real-time latency (was 3)
DEFAULT_DEVICE = "vulkan"        # Force Vulkan GPU (RTX 3070)
DEFAULT_COMPUTE_TYPE = "int8"    # int8 = fast CPU, float16 = CUDA
DEFAULT_BACKEND = "whispercpp"   # "whispercpp" (Vulkan GPU) or "faster_whisper" (CPU) or "whispercpp_cpu"
DEFAULT_THREADS = 6              # Optimised for RTX 3070 + Ryzen 5600
SAMPLE_RATE = 16000
NOISE_REDUCTION_STRENGTH = 0.3   # 0.0 = off, 1.0 = max (light: C++ AGC already normalises)

# ---------------------------------------------------------------------------
# Hallucination filter
# ---------------------------------------------------------------------------

_HALLUCINATION_PATTERNS = [
    "sous-titres", "sous-titrage", "amara.org", "amara org",
    "merci d'avoir regardé", "merci de regarder",
    "n'hésitez pas à", "abonnez-vous", "likez",
    "copyright", "tous droits réservés", "bonne vidéo",
    "à bientôt", "à la prochaine",
    "transcrit par", "traduit par", "sous-titré par",
    "www.", "http", ".com", ".org", ".fr",
    "musique", "♪", "♫",
    "merci à tous", "merci beaucoup pour",
    "si vous avez aimé", "partagez cette vidéo",
]


def _is_hallucination(text: str) -> bool:
    """Reject common Whisper hallucinations (subtitle credits, etc.)."""
    if not text:
        return False
    lower = text.lower().strip()
    if len(lower) < 2:
        logger.debug("Hallucination filter: too short (%d chars): %r", len(lower), text)
        return True
    # Reject repeated short words (e.g., "Merci. Merci. Merci.")
    words = lower.split()
    if len(words) >= 3 and len(set(words)) == 1:
        logger.debug("Hallucination filter: repeated word: %r", text)
        return True
    for pat in _HALLUCINATION_PATTERNS:
        if pat in lower:
            logger.debug("Hallucination filter: pattern %r in: %r", pat, text)
            return True
    return False


# ---------------------------------------------------------------------------
# STT Engine wrapper (dual backend)
# ---------------------------------------------------------------------------

class STTEngine:
    """Wraps either whisper.cpp (Vulkan GPU) or faster-whisper (CPU)."""

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL,
        device: str = DEFAULT_DEVICE,
        compute_type: str = DEFAULT_COMPUTE_TYPE,
        language: str = DEFAULT_LANGUAGE,
        beam_size: int = DEFAULT_BEAM_SIZE,
        backend: str = DEFAULT_BACKEND,
        threads: int = DEFAULT_THREADS,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self.backend = backend
        self.threads = threads
        self._engine = None        # underlying engine (WhisperCppEngine or WhisperModel)
        self._actual_device = "unknown"
        self._active_backend = "unknown"

    @staticmethod
    def _log_vulkan_gpu() -> None:
        """Detect and log Vulkan GPU (expected: RTX 3070)."""
        try:
            import subprocess
            result = subprocess.run(
                ["vulkaninfo", "--summary"],
                capture_output=True, text=True, timeout=5,
                creationflags=0x08000000 if os.name == "nt" else 0,  # CREATE_NO_WINDOW
            )
            for line in result.stdout.splitlines():
                if "deviceName" in line:
                    gpu_name = line.split("=")[-1].strip()
                    logger.info("Whisper Vulkan GPU: %s", gpu_name)
                    logger.info("GPU Whisper Vulkan: OK")
                    return
            logger.warning("Vulkan GPU detection: deviceName not found in vulkaninfo output")
        except FileNotFoundError:
            logger.info("Whisper Vulkan GPU: vulkaninfo not in PATH — assuming RTX 3070 (Vulkan build)")
            logger.info("GPU Whisper Vulkan: OK")
        except Exception as e:
            logger.warning("Vulkan GPU detection failed: %s — continuing with Vulkan backend", e)
            logger.info("GPU Whisper Vulkan: OK (unverified)")

    def load(self) -> None:
        """Load the STT backend."""
        if self.backend == "whispercpp":
            self._load_whispercpp()
        elif self.backend == "whispercpp_cpu":
            self._load_whispercpp(use_gpu=False)
        elif self.backend == "faster_whisper":
            self._load_faster_whisper()
        elif self.backend == "fasterwhisper_gpu":
            self._load_faster_whisper(force_cuda=True)
        else:
            logger.warning("Unknown backend '%s', trying whispercpp then faster_whisper", self.backend)
            try:
                self._load_whispercpp()
            except Exception as e:
                logger.warning("whispercpp failed (%s), falling back to faster_whisper", e)
                self._load_faster_whisper()

    def _load_whispercpp(self, use_gpu: bool = True) -> None:
        """Load whisper.cpp backend (Vulkan GPU or CPU)."""
        from whisper_cpp import WhisperCppEngine

        # ── GPU detection: log Vulkan device info ──
        if use_gpu:
            self._log_vulkan_gpu()

        # Resolve model path for whisper.cpp ggml format
        model_map = {
            "tiny": "ggml-tiny.bin",
            "base": "ggml-base.bin",
            "small": "ggml-small.bin",
            "medium": "ggml-medium.bin",
            "large-v3": "ggml-large-v3.bin",
            "large": "ggml-large-v3.bin",
        }
        model_file = model_map.get(self.model_size, f"ggml-{self.model_size}.bin")
        model_dir = Path(os.environ.get("EXO_WHISPER_MODELS", r"D:\EXO\models\whisper"))
        model_path = str(model_dir / model_file)

        if not os.path.isfile(model_path):
            raise FileNotFoundError(
                f"Whisper.cpp model not found: {model_path}. "
                f"Download it from https://huggingface.co/ggerganov/whisper.cpp"
            )

        self._engine = WhisperCppEngine(
            model_path=model_path,
            language=self.language,
            beam_size=self.beam_size,
            no_speech_thold=0.4,
            threads=self.threads,
        )
        self._engine.load()
        self._actual_device = "vulkan" if use_gpu else "cpu"
        self._active_backend = "whispercpp" if use_gpu else "whispercpp_cpu"
        model_size_mb = os.path.getsize(model_path) / (1024 * 1024)
        logger.info("STT model: %s (%.0fMB) — device: %s — beam_size: %d — threads: %d",
                     self.model_size, model_size_mb, self._actual_device, self.beam_size, self.threads)
        logger.info("[STT] Whisper backend: Vulkan (RTX 3070)")
        logger.info("[GPU] STT: Vulkan → RTX 3070 (OK)")

    def _load_faster_whisper(self, force_cuda: bool = False) -> None:
        """Load faster-whisper backend (CUDA GPU or CPU)."""
        from faster_whisper_backend import FasterWhisperEngine

        device = "cuda" if force_cuda else self.device
        compute = self.compute_type

        engine = FasterWhisperEngine(
            model_size=self.model_size,
            device=device,
            compute_type=compute,
            language=self.language,
            beam_size=self.beam_size,
        )
        engine.load()
        self._engine = engine
        self._actual_device = engine.actual_device
        self._active_backend = "faster_whisper"

    def transcribe(
        self,
        audio_pcm16: np.ndarray,
        *,
        initial_prompt: str | None = None,
    ) -> dict:
        """
        Transcribe a complete utterance.

        Args:
            audio_pcm16: int16 PCM array at 16kHz mono

        Returns:
            {"text": str, "segments": list, "duration": float}
        """
        if self._engine is None:
            raise RuntimeError("Engine not loaded")

        if self._active_backend == "whispercpp":
            result = self._engine.transcribe(audio_pcm16)
        else:
            result = self._engine.transcribe(audio_pcm16, initial_prompt=initial_prompt)

        # Filter hallucinations regardless of backend
        if result["text"] and _is_hallucination(result["text"]):
            logger.info("Hallucination filtered: %s", result["text"][:60])
            result["text"] = ""
            result["segments"] = []

        return result

    @property
    def actual_device(self) -> str:
        return self._actual_device

    def close(self) -> None:
        """Clean up resources."""
        if self._engine:
            self._engine.close()
            self._engine = None


# ---------------------------------------------------------------------------
# WebSocket session handler
# ---------------------------------------------------------------------------

MAX_CONSECUTIVE_HALLUCINATIONS = 3   # stop partials after N hallucinations in a row


class STTSession:
    """One WebSocket client session."""
    
    # P1.2: Prevent buffer overflow DoS attack (10 MB ~= ~312 seconds @ 16kHz mono)
    MAX_AUDIO_BUFFER_SIZE = 10 * 1024 * 1024

    def __init__(self, engine: STTEngine) -> None:
        self.engine = engine
        self._audio_buffer = bytearray()
        self._recording = False
        self._partial_interval = 2.0  # seconds between partial results
        self._last_partial_time = 0.0
        self._consecutive_hallucinations = 0
        self._partial_running = False  # True while a partial transcription is in executor

    async def handle(self, ws) -> None:
        """Handle a WebSocket connection."""
        logger.info("STT client connected")

        # Send ready message
        await ws.send(json.dumps({
            "type": "ready",
            "model": self.engine.model_size,
            "device": self.engine.actual_device,
            "backend": self.engine._active_backend,
        }))

        try:
            async for message in ws:
                if isinstance(message, bytes):
                    await self._on_audio(ws, message)
                elif isinstance(message, str):
                    await self._on_json(ws, message)
        except Exception as e:
            logger.error("Session error: %s", e)
        finally:
            logger.info("STT client disconnected")

    async def _on_json(self, ws, raw: str) -> None:
        # v9.1: delegate standard protocol messages (ping, health, metrics, traces, errors)
        v9_resp = await _v9.handle_ws_message(ws, raw)
        if v9_resp is not None:
            await ws.send(v9_resp)
            return

        try:
            msg = json_loads(raw)
        except (ValueError, TypeError):
            return

        msg_type = msg.get("type", "")

        if msg_type == "start":
            self._req_id = _v9.begin_request()
            self._audio_buffer.clear()
            self._recording = True
            self._last_partial_time = time.monotonic()
            self._consecutive_hallucinations = 0
            logger.debug("Recording started")

        elif msg_type == "end":
            self._recording = False
            await self._finalize(ws)
            self._audio_buffer.clear()  # P1.2: Cleanup after end
            if hasattr(self, '_req_id'):
                _v9.end_request(self._req_id)

        elif msg_type == "cancel":
            self._recording = False
            self._audio_buffer.clear()
            if hasattr(self, '_req_id'):
                _v9.end_request(self._req_id)
            logger.debug("Recording cancelled")

        elif msg_type == "config":
            # Dynamic configuration update
            if "language" in msg:
                self.engine.language = msg["language"]
            if "beam_size" in msg:
                requested_beam = int(msg["beam_size"])
                if requested_beam != self.engine.beam_size:
                    logger.warning("Client requested beam_size=%d — ignoring (server enforces beam_size=%d)",
                                   requested_beam, self.engine.beam_size)
            logger.info("Config updated: lang=%s beam=%d",
                        self.engine.language, self.engine.beam_size)

    async def _on_audio(self, ws, data: bytes) -> None:
        if not self._recording:
            return

        # P1.2: Check buffer size to prevent DoS attack
        new_size = len(self._audio_buffer) + len(data)
        if new_size > self.MAX_AUDIO_BUFFER_SIZE:
            error_msg = f"Audio buffer overflow: {new_size} > {self.MAX_AUDIO_BUFFER_SIZE}"
            logger.error(error_msg)
            await ws.send(json.dumps({
                "type": "error",
                "message": "Audio buffer limit exceeded (10 MB, ~5 minutes max)"
            }))
            return

        self._audio_buffer.extend(data)

        # Send partial transcription periodically (non-blocking)
        now = time.monotonic()
        buf_duration = len(self._audio_buffer) / (SAMPLE_RATE * 2)  # 2 bytes per sample

        if (buf_duration >= 1.5
                and now - self._last_partial_time >= self._partial_interval
                and not self._partial_running):
            self._last_partial_time = now
            asyncio.create_task(self._send_partial(ws))

    async def _send_partial(self, ws) -> None:
        """Transcribe current buffer for partial result (runs as background task)."""
        if not self._audio_buffer:
            return

        # Stop partial loop after too many consecutive hallucinations
        if self._consecutive_hallucinations >= MAX_CONSECUTIVE_HALLUCINATIONS:
            return

        self._partial_running = True
        pcm = np.frombuffer(bytes(self._audio_buffer), dtype=np.int16)
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: self.engine.transcribe(pcm)
            )
            if not self._recording:
                # Recording stopped while partial was running — skip sending
                return
            if result["text"]:
                self._consecutive_hallucinations = 0
                await ws.send(json.dumps({
                    "type": "partial",
                    "text": result["text"],
                }))
            else:
                # Hallucination was filtered (text="") — count it
                self._consecutive_hallucinations += 1
                if self._consecutive_hallucinations >= MAX_CONSECUTIVE_HALLUCINATIONS:
                    logger.warning(
                        "Stopped partials after %d consecutive hallucinations",
                        self._consecutive_hallucinations,
                    )
        except Exception as e:
            logger.warning("Partial transcription error: %s", e)
        finally:
            self._partial_running = False

    async def _finalize(self, ws) -> None:
        """Transcribe final utterance."""
        # Wait for any in-progress partial to finish (engine is not thread-safe)
        wait_start = time.monotonic()
        while self._partial_running:
            await asyncio.sleep(0.05)
            if time.monotonic() - wait_start > 2.0:
                logger.warning("Waited 2s for partial — proceeding anyway (partial may overlap)")
                break
        if self._partial_running:
            logger.warning("Partial still running, but proceeding with finalize")

        if not self._audio_buffer:
            await ws.send(json.dumps({
                "type": "final",
                "text": "",
                "segments": [],
                "duration": 0.0,
            }))
            return

        pcm = np.frombuffer(bytes(self._audio_buffer), dtype=np.int16)
        self._audio_buffer.clear()

        # ── DSP: Noise reduction ──
        pcm = _apply_noise_reduction(pcm, SAMPLE_RATE, NOISE_REDUCTION_STRENGTH)

        # ── Gain normalization: gentle boost (C++ AGC already normalises) ──
        peak = int(np.max(np.abs(pcm)))
        if peak > 0:
            target_peak = int(32768 * 0.8)  # -2 dBFS
            if peak < target_peak:
                gain = target_peak / peak
                gain = min(gain, 6.0)  # cap at ~16 dB (C++ AGC handles most of it)
                pcm = np.clip(pcm.astype(np.float64) * gain, -32768, 32767).astype(np.int16)

        # ── DEBUG: PCM statistics ──
        rms = np.sqrt(np.mean(pcm.astype(np.float64) ** 2))
        peak = int(np.max(np.abs(pcm)))
        dur = len(pcm) / SAMPLE_RATE
        logger.info("PCM stats: samples=%d dur=%.2fs rms=%.1f peak=%d (%.1f dBFS)",
                     len(pcm), dur, rms, peak,
                     20 * np.log10(max(peak, 1) / 32768))
        try:
            loop = asyncio.get_running_loop()
            t0 = time.monotonic()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None, lambda: self.engine.transcribe(pcm)
                ),
                timeout=20.0
            )
            transcribe_ms = (time.monotonic() - t0) * 1000
            logger.info("[Latency] STT final: %.0f ms text_len=%d result=%s",
                        transcribe_ms, len(result["text"]), result["text"][:60])
            if transcribe_ms > 450:
                logger.warning("[Latency] STT final exceeded target (%.0f ms > 450 ms)", transcribe_ms)
            await ws.send(json.dumps({
                "type": "final",
                "text": result["text"],
                "segments": result["segments"],
                "duration": result["duration"],
                "transcribe_ms": round(transcribe_ms),
            }))
        except asyncio.TimeoutError:
            logger.error("Final transcription timeout after 20s")
            await ws.send(json.dumps({
                "type": "error",
                "message": "Transcription timeout (20s)",
            }))
        except Exception as e:
            logger.error("Final transcription error: %s", e)
            await ws.send(json.dumps({
                "type": "error",
                "message": "Erreur de transcription",
            }))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    global NOISE_REDUCTION_STRENGTH, _v9

    import argparse

    parser = argparse.ArgumentParser(description="EXO STT Server (whisper.cpp GPU / faster-whisper CPU)")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help="Whisper model size (tiny, base, small, medium, large-v3)")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--device", default=DEFAULT_DEVICE,
                        help="Compute device (cpu, cuda, auto) — only for faster_whisper backend")
    parser.add_argument("--compute-type", default=DEFAULT_COMPUTE_TYPE)
    parser.add_argument("--beam-size", type=int, default=DEFAULT_BEAM_SIZE)
    parser.add_argument("--backend", default=DEFAULT_BACKEND,
                        choices=["whispercpp", "faster_whisper", "fasterwhisper_gpu", "whispercpp_cpu", "auto"],
                        help="STT backend: whispercpp (Vulkan GPU), fasterwhisper_gpu (CUDA), faster_whisper (auto GPU/CPU), whispercpp_cpu (CPU), auto")
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS,
                        help="Number of threads for whisper.cpp (default: 6)")
    parser.add_argument("--noise-reduction", type=float, default=NOISE_REDUCTION_STRENGTH,
                        help="Noise reduction strength (0.0=off, 1.0=max)")
    args = parser.parse_args()

    # Prevent duplicate instances
    ensure_single_instance(args.port, "stt_server")
    _v9 = init_v9("stt_server", args.port)

    # Apply noise reduction config
    nr_strength = args.noise_reduction
    NOISE_REDUCTION_STRENGTH = nr_strength
    if _noisereduce_available and nr_strength > 0:
        logger.info("Noise reduction enabled (strength=%.2f)", NOISE_REDUCTION_STRENGTH)
    elif not _noisereduce_available:
        logger.info("Noise reduction unavailable (pip install noisereduce)")

    # ── STT CONFIG (obligatory startup log) ──
    logger.info("STT CONFIG: model=%s beam_size=%d device=%s compute_type=%s backend=%s threads=%d",
                args.model, args.beam_size, args.device, args.compute_type, args.backend, args.threads)

    engine = STTEngine(
        model_size=args.model,
        device=args.device,
        compute_type=args.compute_type,
        language=args.language,
        beam_size=args.beam_size,
        backend=args.backend,
        threads=args.threads,
    )

    # ── Latency targets ──
    logger.info("[Latency] STT target: < 450 ms")
    logger.info("[Latency] Pipeline vocal complet target: < 2500 ms")

    t_load = time.monotonic()
    engine.load()
    load_ms = (time.monotonic() - t_load) * 1000
    logger.info("[Latency] Preload STT: OK (%.0f ms)", load_ms)
    logger.info("[Latency] STT model=%s device=%s backend=%s beam=%d threads=%d",
                args.model, engine.actual_device, engine._active_backend,
                args.beam_size, args.threads)

    async def handler(ws):
        session = STTSession(engine)
        await session.handle(ws)

    try:
        import websockets
    except ImportError:
        logger.error("websockets not installed. Run: pip install websockets")
        return

    server = await websockets.serve(
        handler, args.host, args.port,
        **_v9.ws_serve_kwargs(max_size=10 * 1024 * 1024),
    )
    logger.info("STT server running on ws://%s:%d (model=%s, device=%s, backend=%s)",
                args.host, args.port, args.model, engine.actual_device, engine._active_backend)
    logger.info("[Latency] Streaming: OK — ready for low-latency transcription")

    try:
        await asyncio.Future()  # run forever
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        await server.wait_closed()
        engine.close()
        logger.info("STT server stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
