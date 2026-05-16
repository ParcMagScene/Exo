"""
wakeword_server.py — EXO OpenWakeWord Server

WebSocket server that receives PCM16 audio chunks and detects
wake words using OpenWakeWord neural models.

Protocol:
  → Binary: PCM16 audio chunks (16kHz mono)
  → JSON:   {"type": "config", "threshold": 0.5, "wake_words": ["hey_jarvis"]}
             {"type": "reset"}
  ← JSON:   {"type": "ready", "models": ["hey_jarvis"]}
             {"type": "wakeword", "word": "hey_jarvis", "score": 0.92}

Port: 8770 (default)

Dependencies:
  pip install websockets openwakeword
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
import os
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

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
    format="%(asctime)s [WW] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("exo.wakeword")
_file_handler = logging.FileHandler(logfile, encoding="utf-8", delay=False)
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [WW] %(levelname)s %(message)s", datefmt="%H:%M:%S"))
_file_handler.flush = _file_handler.stream.flush
logger.addHandler(_file_handler)
logger.propagate = True
logger.info("=== EXO WAKEWORD_SERVER STARTUP ===")
_file_handler.flush()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8770
SAMPLE_RATE = 16000
# OpenWakeWord expects 1280-sample chunks at 16kHz (80ms)
CHUNK_SAMPLES = 1280
DEFAULT_THRESHOLD = 0.7
# Cooldown after detection to prevent re-triggering during speech (seconds)
DETECTION_COOLDOWN_S = 3.0
    # Correction : tous les modèles doivent être dans D:/EXO/models/wakeword
EXO_WAKEWORD_DIR = Path("D:/EXO/models/wakeword")
DEFAULT_MODELS = ["hey_jarvis"]


class WakeWordEngine:
    """Wrapper around OpenWakeWord."""

    def __init__(self, models: list[str] | None = None,
                 threshold: float = DEFAULT_THRESHOLD) -> None:
        self._model = None
        self._models = models or DEFAULT_MODELS
        self._threshold = threshold
        self._active_models: list[str] = []

    def load(self) -> None:
        """Load OpenWakeWord models."""
        t0 = time.monotonic()
        try:
            from openwakeword.model import Model

            # Resolve models: prefer .onnx files from custom dir, else built-in
            resolved = []
            for m in self._models:
                if m.endswith(".onnx") and Path(m).exists():
                    resolved.append(m)
                elif EXO_WAKEWORD_DIR.is_dir():
                    # Search for matching .onnx in custom dir (e.g. hey_jarvis → hey_jarvis_v0.1.onnx)
                    matches = list(EXO_WAKEWORD_DIR.glob(f"{m}*.onnx"))
                    if matches:
                        resolved.append(str(matches[0]))
                        logger.info("Using custom model: %s", matches[0])
                    else:
                        resolved.append(m)  # fallback to built-in name
                else:
                    resolved.append(m)

            self._model = Model(
                wakeword_models=resolved,
                inference_framework="onnx",
            )
            self._active_models = list(self._model.models.keys())

            load_ms = (time.monotonic() - t0) * 1000
            logger.info("[Latency] Preload WakeWord: OK (%.0f ms) — models: %s",
                        load_ms, self._active_models)
        except Exception as e:
            logger.error("Failed to load OpenWakeWord: %s", e)
            raise

    def reset(self) -> None:
        """Reset model states."""
        if self._model is not None:
            self._model.reset()
        logger.info("WakeWord state reset")

    def process_chunk(self, pcm16: np.ndarray) -> dict[str, float]:
        """
        Process audio chunk, return wake word scores.

        Args:
            pcm16: int16 PCM array (1280 samples recommended)

        Returns:
            Dict of {model_name: score}
        """
        if self._model is None:
            return {}

        # OpenWakeWord expects int16 numpy array
        prediction = self._model.predict(pcm16)
        return {k: float(v) for k, v in prediction.items()}

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float) -> None:
        self._threshold = max(0.01, min(0.99, value))

    @property
    def active_models(self) -> list[str]:
        return self._active_models


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------

class WakeWordSession:
    """One WebSocket client session."""

    def __init__(self, engine: WakeWordEngine) -> None:
        self.engine = engine
        self._chunk_buffer = bytearray()
        self._last_detection_time: float = 0.0

    async def handle(self, ws) -> None:
        """Handle a WebSocket connection."""
        logger.info("WakeWord client connected")
        self.engine.reset()

        await ws.send(json.dumps({
            "type": "ready",
            "models": self.engine.active_models,
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
            logger.error("WakeWord session error: %s", e)
        finally:
            logger.info("WakeWord client disconnected")

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
                self.engine.threshold = float(msg["threshold"])
                logger.info("Threshold: %.2f", self.engine.threshold)
        elif msg_type == "reset":
            self.engine.reset()

    async def _on_audio(self, ws, data: bytes) -> None:
        """Process incoming audio for wake word detection."""
        self._chunk_buffer.extend(data)

        chunk_bytes = CHUNK_SAMPLES * 2
        while len(self._chunk_buffer) >= chunk_bytes:
            chunk = self._chunk_buffer[:chunk_bytes]
            self._chunk_buffer = self._chunk_buffer[chunk_bytes:]

            self._chunk_start_time = time.monotonic()
            pcm = np.frombuffer(bytes(chunk), dtype=np.int16)
            # Run ONNX inference in default executor to avoid blocking event loop.
            loop = asyncio.get_running_loop()
            scores = await loop.run_in_executor(
                None, self.engine.process_chunk, pcm
            )

            # Only send if any model exceeds threshold + cooldown elapsed
            now = time.monotonic()
            for model_name, score in scores.items():
                if score >= self.engine.threshold:
                    if (now - self._last_detection_time) < DETECTION_COOLDOWN_S:
                        logger.debug("Wake word suppressed (cooldown): %s (%.3f)", model_name, score)
                        continue
                    self._last_detection_time = now
                    detect_ms = (now - self._chunk_start_time) * 1000 if hasattr(self, '_chunk_start_time') else 0
                    await ws.send(json.dumps({
                        "type": "wakeword",
                        "word": model_name,
                        "score": round(score, 4),
                    }))
                    logger.info("[Latency] WakeWord detected: %s (%.3f) in ~%.0f ms",
                                model_name, score, detect_ms)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    global _v9

    import argparse

    parser = argparse.ArgumentParser(description="EXO OpenWakeWord Server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS,
                        help="Wake word models to load (built-in names or .onnx paths)")
    args = parser.parse_args()

    # Prevent duplicate instances
    ensure_single_instance(args.port, "wakeword_server")
    _v9 = init_v9("wakeword_server", args.port)

    engine = WakeWordEngine(models=args.models, threshold=args.threshold)
    engine.load()

    # Mutex : un seul client WakeWord actif à la fois (état interne non partageable)
    _session_lock = asyncio.Lock()

    async def handler(ws):
        if _session_lock.locked():
            await ws.send(json.dumps({"type": "error", "message": "WakeWord busy — another session is active"}))
            await ws.close(1013, "WakeWord busy")
            logger.warning("Rejected WakeWord client — session already active")
            return
        async with _session_lock:
            session = WakeWordSession(engine)
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
    logger.info("WakeWord server running on ws://%s:%d (models=%s, threshold=%.2f)",
                args.host, args.port, engine.active_models, engine.threshold)
    logger.info("[Latency] WakeWord: chunk=%d samples (%d ms), cooldown=%.1f s",
                CHUNK_SAMPLES, CHUNK_SAMPLES * 1000 // SAMPLE_RATE, DETECTION_COOLDOWN_S)
    logger.info("[Latency] Streaming: OK — ready for low-latency wake word detection")

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        await server.wait_closed()
        logger.info("WakeWord server stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception("WakeWord server fatal error")
        sys.exit(1)
