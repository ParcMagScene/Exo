"""
whisper_cpp.py — Python wrapper for whisper.cpp via whisper-server HTTP API (Vulkan GPU)

Instead of fragile ctypes struct manipulation, this module communicates with
whisper-server.exe (built with Vulkan) running as a local HTTP server.
The server loads the model once and stays resident, accepting audio via
multipart POST to /inference and returning JSON transcription.

Usage from stt_server.py:
    engine = WhisperCppEngine(model_path=..., server_exe=..., port=8769)
    engine.load()          # starts whisper-server.exe subprocess
    result = engine.transcribe(pcm16_array)
    engine.close()         # kills subprocess
"""

from __future__ import annotations

import io
import json
import logging
import os
import signal
import subprocess
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("exo.stt.whispercpp")

SAMPLE_RATE = 16000


class WhisperCppEngine:
    """Manages a whisper-server.exe subprocess and sends audio via HTTP."""

    def __init__(
        self,
        model_path: str,
        server_exe: str | None = None,
        lib_dir: str | None = None,
        language: str = "fr",
        beam_size: int = 1,
        no_speech_thold: float = 0.4,
        threads: int = 6,
        initial_prompt: str = "EXO est un assistant vocal domotique français. Jarvis, allume, éteins, météo, température, lumière.",
        host: str = "127.0.0.1",
        port: int = 8769,
    ):
        self.model_path = model_path
        self.language = language
        self.beam_size = beam_size
        self.no_speech_thold = no_speech_thold
        self.threads = threads
        self.initial_prompt = initial_prompt
        self.host = host
        self.port = port
        self._process: subprocess.Popen | None = None
        self._base_url = f"http://{host}:{port}"
        self.last_transcribe_ts: float = 0.0  # monotonic timestamp of last transcribe()

        if lib_dir is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            lib_dir = os.environ.get(
                "EXO_WHISPERCPP_BIN",
                os.path.join(project_root, "whispercpp", "build_vk", "bin", "Release"),
            )
        if server_exe is None:
            server_exe = os.path.join(lib_dir, "whisper-server.exe")
        self.server_exe = server_exe
        self._lib_dir = lib_dir

    def load(self) -> None:
        """Start whisper-server.exe as a subprocess with the model loaded."""
        if not os.path.isfile(self.server_exe):
            raise FileNotFoundError(f"whisper-server.exe not found: {self.server_exe}")
        if not os.path.isfile(self.model_path):
            raise FileNotFoundError(f"Model not found: {self.model_path}")

        # Kill any orphan whisper-server.exe binding our port (left over by a
        # previous EXO crash/restart). Without this, a stale instance keeps the
        # port and the new one collides → HTTP 500 / WinError 10054 on every
        # request.
        self._kill_orphans_on_port()

        cmd = [
            self.server_exe,
            "--model", self.model_path,
            "--host", self.host,
            "--port", str(self.port),
            "--language", self.language,
            "--beam-size", str(self.beam_size),
            "--no-speech-thold", str(self.no_speech_thold),
            "--threads", str(self.threads),
            "--flash-attn",
            "--suppress-nst",
        ]

        logger.info("Starting whisper-server: %s", " ".join(cmd))

        env = os.environ.copy()
        env["PATH"] = self._lib_dir + os.pathsep + env.get("PATH", "")

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW
            if os.name == "nt"
            else 0,
        )

        # Wait for server to be ready (poll /inference endpoint)
        self._wait_for_ready(timeout=30)
        logger.info(
            "whisper-server ready on %s (model=%s, gpu=vulkan)",
            self._base_url,
            os.path.basename(self.model_path),
        )

    def _wait_for_ready(self, timeout: float = 30) -> None:
        """Poll the server until it responds or timeout."""
        import urllib.request
        import urllib.error

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # Check subprocess hasn't crashed
            if self._process and self._process.poll() is not None:
                stderr = self._process.stderr.read().decode(errors="replace") if self._process.stderr else ""
                raise RuntimeError(
                    f"whisper-server exited with code {self._process.returncode}: {stderr[:500]}"
                )
            try:
                req = urllib.request.Request(self._base_url, method="GET")
                urllib.request.urlopen(req, timeout=2)
                return
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.5)

        raise TimeoutError(
            f"whisper-server did not start within {timeout}s"
        )

    def transcribe(self, audio_pcm16: np.ndarray) -> dict:
        """
        Transcribe PCM16 int16 audio at 16kHz mono.

        Returns:
            {"text": str, "segments": list[dict], "duration": float}
        """
        import urllib.request
        import urllib.error

        duration = len(audio_pcm16) / SAMPLE_RATE
        if duration < 0.3:
            return {"text": "", "segments": [], "duration": duration}

        # Encode audio as WAV in memory
        wav_bytes = self._pcm16_to_wav(audio_pcm16)

        # Build multipart/form-data request
        boundary = "----ExoWhisperBoundary"
        body = self._build_multipart(wav_bytes, boundary)

        url = f"{self._base_url}/inference"
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }

        t0 = time.monotonic()
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        # Timeout : si whisper-server freeze (GPU idle / Vulkan asleep, contention
        # avec TTS Orpheus, etc.), on restart en ~10s au lieu de 30s. 10s laisse
        # de la marge en cas de freeze ponctuel sans declencher de restart inutile
        # (audio 10s, RTF ~0.1 => ~1s de calcul nominal).
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
        except (urllib.error.URLError, ConnectionError, OSError, TimeoutError) as e:
            logger.error("whisper-server request failed: %s — restarting server", e)
            self._restart_server()
            return {"text": "", "segments": [], "duration": round(duration, 2)}

        dt = time.monotonic() - t0
        self.last_transcribe_ts = time.monotonic()

        # Parse JSON response
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Invalid JSON from whisper-server: %s", raw[:200])
            return {"text": "", "segments": [], "duration": round(duration, 2)}

        # Extract text from verbose_json format
        full_text = data.get("text", "").strip()
        segments = []
        for seg in data.get("segments", []):
            segments.append({
                "start": round(seg.get("t0", 0) / 100.0, 2) if "t0" in seg else seg.get("start", 0),
                "end": round(seg.get("t1", 0) / 100.0, 2) if "t1" in seg else seg.get("end", 0),
                "text": seg.get("text", "").strip(),
            })

        dt_ms = dt * 1000
        logger.info(
            "[Latency] STT: %.0f ms (audio=%.1fs RTF=%.2f): %s",
            dt_ms, duration, dt / max(duration, 0.01), full_text[:80],
        )
        if dt_ms > 450:
            logger.warning("[Latency] STT exceeded target (%.0f ms > 450 ms)", dt_ms)

        return {
            "text": full_text,
            "segments": segments,
            "duration": round(duration, 2),
        }

    def _pcm16_to_wav(self, pcm16: np.ndarray) -> bytes:
        """Convert int16 PCM array to WAV bytes in memory."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm16.tobytes())
        return buf.getvalue()

    def _build_multipart(self, wav_bytes: bytes, boundary: str) -> bytes:
        """Build multipart/form-data body with audio file and parameters."""
        parts = []

        # Audio file
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
            f"Content-Type: audio/wav\r\n\r\n"
        )
        parts.append(wav_bytes)
        parts.append(b"\r\n")

        # Parameters
        params = {
            "response_format": "verbose_json",
            "temperature": "0.0",
            "language": self.language,
        }
        if self.initial_prompt:
            params["prompt"] = self.initial_prompt

        for key, value in params.items():
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                f"{value}\r\n"
            )

        parts.append(f"--{boundary}--\r\n")

        # Combine into bytes
        result = b""
        for part in parts:
            if isinstance(part, str):
                result += part.encode("utf-8")
            else:
                result += part
        return result

    @property
    def actual_device(self) -> str:
        return "vulkan"

    def close(self) -> None:
        """Stop the whisper-server subprocess."""
        if self._process:
            logger.info("Stopping whisper-server (pid=%d)", self._process.pid)
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=3)
            self._process = None
        # Belt-and-braces: also nuke any stray whisper-server.exe still bound
        # to our port (e.g. orphaned by a hard kill of the parent service).
        self._kill_orphans_on_port()

    def _kill_orphans_on_port(self) -> None:
        """Kill any whisper-server.exe process currently bound to self.port.

        Necessary because launch_exo_silent.ps1 stops services by PID without
        terminating their child processes, so a previous whisper-server.exe
        can outlive the python parent and still hold port 8769.
        """
        if os.name != "nt":
            return
        try:
            import psutil  # type: ignore
        except ImportError:
            psutil = None  # type: ignore
        try:
            killed = 0
            if psutil is not None:
                for p in psutil.process_iter(attrs=["pid", "name"]):
                    try:
                        name = (p.info.get("name") or "").lower()
                        if name != "whisper-server.exe":
                            continue
                        for c in p.net_connections(kind="inet"):
                            if c.laddr and c.laddr.port == self.port:
                                logger.warning(
                                    "Killing orphan whisper-server.exe pid=%d on port %d",
                                    p.pid, self.port,
                                )
                                p.kill()
                                killed += 1
                                break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            else:
                # Fallback: blunt taskkill on every whisper-server.exe instance
                # (no per-port filtering without psutil).
                r = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq whisper-server.exe", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=5,
                )
                if "whisper-server.exe" in r.stdout:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", "whisper-server.exe"],
                        capture_output=True, timeout=5,
                    )
                    logger.warning("Killed orphan whisper-server.exe via taskkill (no psutil)")
                    killed = 1
            if killed:
                time.sleep(0.5)  # let the OS release the socket
        except Exception as e:
            logger.warning("Failed to kill orphan whisper-server.exe: %s", e)

    def _restart_server(self) -> None:
        """Kill and restart whisper-server after a timeout/crash."""
        logger.warning("Restarting whisper-server...")
        self.close()
        time.sleep(1)
        try:
            self.load()
            logger.info("whisper-server restarted successfully")
        except Exception as e:
            logger.error("Failed to restart whisper-server: %s", e)

    def __del__(self):
        self.close()
