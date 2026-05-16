"""
vad_server.py — EXO Silero VAD Server

WebSocket server that receives PCM16 audio chunks and returns
real-time voice activity detection scores using Silero VAD.

Protocol:
  → Binary: PCM16 audio chunks (16kHz mono)
  → JSON:   {"type": "config", "threshold": 0.5}
             {"type": "reset"}
  ← JSON:   {"type": "ready", "model": "silero_vad"}
             {"type": "vad", "score": 0.85, "is_speech": true}

Port: 8768 (default)

Dependencies:
  pip install websockets torch silero-vad
"""

from __future__ import annotations

# Patch global EXO : forcer le working directory à D:/EXO/ pour tous les services
import os
os.chdir("D:/EXO/")

import asyncio
try:
    import ujson as json  # v6.0 perf : 3-5x plus rapide que stdlib (audit perf)
except ImportError:
    import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

# Force torch cache into project/cache (prevent ~/.cache/torch/ leak)
import os as _os
if "TORCH_HOME" not in _os.environ:
    _os.environ["TORCH_HOME"] = "D:/EXO/cache/torch"

import torch

# Singleton guard — prevent duplicate instances
from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9, json_loads, json_dumps


# --- Logging EXO centralisé (identique C++) ---
def _get_exo_logfile():
    # Correction : tous les logs doivent aller dans D:/EXO/logs/
    log_dir = os.environ.get("EXO_LOGS_DIR", "D:/EXO/logs")
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    ts = os.environ.get("EXO_SESSION_TIMESTAMP")
    if not ts:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(log_dir, f"exo_{ts}.log")

logfile = _get_exo_logfile()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [VAD] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("exo.vad")
_file_handler = logging.FileHandler(logfile, encoding="utf-8", delay=False)
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [VAD] %(levelname)s %(message)s", datefmt="%H:%M:%S"))
_file_handler.flush = _file_handler.stream.flush
logger.addHandler(_file_handler)
logger.propagate = True
logger.info("=== EXO VAD_SERVER STARTUP ===")
_file_handler.flush()

# Log d'amorçage immédiat pour diagnostic
logger.info("=== EXO VAD_SERVER STARTUP ===")
_file_handler.flush()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8768
SAMPLE_RATE = 16000
# Silero VAD expects chunks of 512 samples at 16kHz (32ms)
CHUNK_SAMPLES = 512


class SileroVAD:
    """Wrapper around Silero VAD model."""

    def __init__(self) -> None:
        self._model = None
        self._threshold = 0.5
        self._is_speech = False
        self._speech_frames = 0
        self._silence_frames = 0
        self._speech_start_frames = 2
        self._speech_hang_frames = 25  # ~800ms at 32ms chunks — tolerates natural mid-sentence pauses

    def load(self) -> None:
        """Load Silero VAD model."""
        t0 = time.monotonic()
        try:
            from silero_vad import load_silero_vad
            # onnx=True : utilise onnxruntime (déjà installé) au lieu du JIT torch.
            # Économie ~150 MB RAM vs mode JIT par défaut. Inférence équivalente
            # (le wrapper accepte toujours torch.Tensor en entrée).
            self._model = load_silero_vad(onnx=True)
            load_ms = (time.monotonic() - t0) * 1000
            logger.info("[Latency] Preload VAD (ONNX): OK (%.0f ms)", load_ms)
        except Exception as e:
            logger.error("Failed to load Silero VAD: %s", e)
            raise

    def reset(self) -> None:
        """Reset model state for new session."""
        if self._model is not None:
            self._model.reset_states()
        self._is_speech = False
        self._speech_frames = 0
        self._silence_frames = 0
        logger.info("VAD state reset")

    def process_chunk(self, pcm16: np.ndarray) -> tuple[float, bool]:
        """
        Process a chunk of PCM16 audio.

        Args:
            pcm16: int16 PCM array (should be CHUNK_SAMPLES long)

        Returns:
            (score, is_speech) tuple
        """
        if self._model is None:
            return 0.0, False

        # Convert to float32 tensor
        audio = torch.from_numpy(pcm16.astype(np.float32) / 32768.0)

        # Silero expects exactly 512 samples at 16kHz
        if len(audio) != CHUNK_SAMPLES:
            # Pad or truncate
            if len(audio) < CHUNK_SAMPLES:
                audio = torch.nn.functional.pad(audio, (0, CHUNK_SAMPLES - len(audio)))
            else:
                audio = audio[:CHUNK_SAMPLES]

        score = float(self._model(audio, SAMPLE_RATE))

        # Update speech state with hysteresis
        frame_is_speech = score >= self._threshold
        if frame_is_speech:
            self._speech_frames += 1
            self._silence_frames = 0
        else:
            self._silence_frames += 1

        prev_speech = self._is_speech
        if not self._is_speech:
            if self._speech_frames >= self._speech_start_frames:
                self._is_speech = True
                logger.debug("[Latency] VAD speech-start after %d frames", self._speech_frames)
        else:
            if self._silence_frames >= self._speech_hang_frames:
                self._is_speech = False
                self._speech_frames = 0
                logger.debug("[Latency] VAD speech-end after %d silence frames (~%d ms)",
                            self._silence_frames, self._silence_frames * 32)

        return score, self._is_speech

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float) -> None:
        self._threshold = max(0.01, min(0.99, value))


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------

class VADSession:
    """One WebSocket client session."""

    def __init__(self, vad: SileroVAD) -> None:
        self.vad = vad
        self._chunk_buffer = bytearray()

    async def handle(self, ws) -> None:
        """Handle a WebSocket connection."""
        logger.info("VAD client connected")

        # Reset state for new client
        self.vad.reset()

        # Send ready
        await ws.send(json.dumps({
            "type": "ready",
            "model": "silero_vad",
            "sample_rate": SAMPLE_RATE,
            "chunk_samples": CHUNK_SAMPLES,
        }))

        try:
            async for message in ws:
                if isinstance(message, bytes):
                    await self._on_audio(ws, message)
                elif isinstance(message, str):
                    await self._on_json(ws, message)
        except Exception as e:
            logger.error("VAD session error: %s", e)
        finally:
            logger.info("VAD client disconnected")

    async def _on_json(self, ws, raw: str) -> None:
        # v9.1: delegate standard protocol messages
        v9_resp = await _v9.handle_ws_message(ws, raw)
        if v9_resp is not None:
            await ws.send(v9_resp)
            return

        try:
            msg = json_loads(raw)
        except (ValueError, TypeError):
            return

        msg_type = msg.get("type", "")

        if msg_type == "config":
            if "threshold" in msg:
                self.vad.threshold = float(msg["threshold"])
                logger.info("VAD threshold: %.2f", self.vad.threshold)
        elif msg_type == "reset":
            self.vad.reset()

    async def _on_audio(self, ws, data: bytes) -> None:
        """Process incoming audio and return VAD score."""
        self._chunk_buffer.extend(data)

        # Process in CHUNK_SAMPLES-sized blocks
        chunk_bytes = CHUNK_SAMPLES * 2  # 2 bytes per int16 sample
        while len(self._chunk_buffer) >= chunk_bytes:
            chunk = self._chunk_buffer[:chunk_bytes]
            self._chunk_buffer = self._chunk_buffer[chunk_bytes:]

            pcm = np.frombuffer(bytes(chunk), dtype=np.int16)
            # Run Silero RNN inference in default executor to avoid blocking event loop.
            loop = asyncio.get_running_loop()
            score, is_speech = await loop.run_in_executor(
                None, self.vad.process_chunk, pcm
            )

            await ws.send(json.dumps({
                "type": "vad",
                "score": round(score, 4),
                "is_speech": is_speech,
            }))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    global _v9

    import argparse

    # Lecture seuil par defaut depuis ConfigManager (vad.threshold).
    _cfg_threshold = 0.5
    try:
        from shared.config_manager import ConfigManager
        _cfg_threshold = float(ConfigManager.instance().get("vad.threshold", 0.5))
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="EXO Silero VAD Server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--threshold", type=float, default=_cfg_threshold,
                        help="VAD threshold (0.01-0.99)")
    args = parser.parse_args()

    # Prevent duplicate instances
    ensure_single_instance(args.port, "vad_server")
    _v9 = init_v9("vad_server", args.port)

    vad = SileroVAD()
    vad.threshold = args.threshold
    vad.load()

    # Mutex : un seul client VAD actif à la fois (état interne RNN non partageable)
    _session_lock = asyncio.Lock()

    async def handler(ws):
        # 2026-05-16: send a "ready" handshake BEFORE refusing on the session
        # lock so passive readiness probes (ServiceSupervisor) see the service
        # as healthy instead of looping on "WS readiness perdu".
        if _session_lock.locked():
            try:
                await ws.send(json.dumps({
                    "type": "ready",
                    "model": "silero_vad",
                    "sample_rate": SAMPLE_RATE,
                    "chunk_samples": CHUNK_SAMPLES,
                    "busy": True,
                }))
                await ws.send(json.dumps({
                    "type": "error",
                    "message": "VAD occupé — une autre session est active",
                }))
            except Exception:
                pass
            await ws.close(1013, "VAD busy")
            logger.debug("Rejected VAD client — session already active (probe ack'd)")
            return
        async with _session_lock:
            session = VADSession(vad)
            await session.handle(ws)

    try:
        import websockets
    except ImportError:
        logger.error("websockets not installed. Run: pip install websockets")
        return

    server = await websockets.serve(
        handler, args.host, args.port,
        **_v9.ws_serve_kwargs(),
    )
    logger.info("VAD server running on ws://%s:%d (threshold=%.2f, hang_frames=%d)",
                args.host, args.port, vad.threshold, vad._speech_hang_frames)
    logger.info("[Latency] VAD: speech_hang=~%d ms, speech_start=~%d ms",
                vad._speech_hang_frames * 32, vad._speech_start_frames * 32)
    logger.info("[Latency] Streaming: OK — ready for low-latency VAD")

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        await server.wait_closed()
        logger.info("VAD server stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception("VAD server fatal error")
        sys.exit(1)
