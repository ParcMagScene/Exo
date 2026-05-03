"""
benchmark_stt.py — Benchmark STT EXO v4.1

Mesure le RTF (Real-Time Factor) du backend whisper.cpp + Vulkan GPU.
Génère un fichier WAV de test si absent, transcrit via whisper-server HTTP,
et affiche les résultats.

Usage:
    python scripts/benchmark_stt.py
    python scripts/benchmark_stt.py --audio path/to/test.wav
    python scripts/benchmark_stt.py --model medium --runs 5
"""

from __future__ import annotations

import argparse
import io
import json
import os
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np

# ── Paths ──────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WHISPER_SERVER = PROJECT_ROOT / "whisper.cpp" / "build_vk" / "bin" / "Release" / "whisper-server.exe"
MODELS_DIR = PROJECT_ROOT / "whisper.cpp" / "models"
DEFAULT_MODEL = "small"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8769
SAMPLE_RATE = 16000


def find_model(name: str) -> Path:
    """Locate a ggml model file."""
    path = MODELS_DIR / f"ggml-{name}.bin"
    if path.exists():
        return path
    # Try without prefix
    for p in MODELS_DIR.glob(f"*{name}*.bin"):
        if "for-tests" not in p.name:
            return p
    raise FileNotFoundError(f"Modèle '{name}' introuvable dans {MODELS_DIR}")


def generate_test_wav(path: Path, duration: float = 5.0) -> Path:
    """Generate a test WAV with a spoken-like tone pattern (for latency measurement)."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), dtype=np.float32)
    # Mix of frequencies to simulate voice-like signal
    signal = (
        0.3 * np.sin(2 * np.pi * 200 * t)
        + 0.2 * np.sin(2 * np.pi * 500 * t)
        + 0.1 * np.sin(2 * np.pi * 1200 * t)
    )
    # Add some modulation
    signal *= 0.5 * (1 + np.sin(2 * np.pi * 3 * t))
    pcm16 = (signal * 16000).astype(np.int16)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm16.tobytes())

    print(f"  Fichier test généré : {path} ({duration:.1f}s)")
    return path


def _server_ready(port: int, timeout: float = 30.0) -> bool:
    """Wait for whisper-server to be ready."""
    import urllib.request
    import urllib.error
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(f"http://{SERVER_HOST}:{port}/")
            with urllib.request.urlopen(req, timeout=2):
                return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    return False


def transcribe_http(wav_path: Path, port: int) -> tuple[str, float]:
    """Send WAV to whisper-server /inference and return (text, server_time_ms)."""
    import urllib.request
    import urllib.error

    with open(wav_path, "rb") as f:
        wav_data = f.read()

    boundary = "----ExoBenchmark"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="benchmark.wav"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode() + wav_data + f"\r\n--{boundary}\r\n".encode() + (
        f'Content-Disposition: form-data; name="response_format"\r\n\r\njson'
        f"\r\n--{boundary}--\r\n"
    ).encode()

    req = urllib.request.Request(
        f"http://{SERVER_HOST}:{port}/inference",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        elapsed = time.perf_counter() - t0
        result = json.loads(resp.read().decode())

    text = result.get("text", "").strip()
    return text, elapsed


def get_audio_duration(wav_path: Path) -> float:
    """Return duration of a WAV file in seconds."""
    with wave.open(str(wav_path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def run_benchmark(
    model_name: str,
    wav_path: Path,
    num_runs: int = 3,
    language: str = "fr",
    beam_size: int = 5,
) -> None:
    """Run the full benchmark: start server, transcribe N times, report."""

    model_path = find_model(model_name)
    audio_duration = get_audio_duration(wav_path)

    print(f"\n{'='*60}")
    print(f"  BENCHMARK STT — EXO v4.1")
    print(f"{'='*60}")
    print(f"  Backend    : whisper.cpp + Vulkan GPU")
    print(f"  Modèle     : {model_name} ({model_path.stat().st_size / 1024 / 1024:.0f} MB)")
    print(f"  Audio      : {wav_path.name} ({audio_duration:.1f}s)")
    print(f"  Langue     : {language}")
    print(f"  Beam size  : {beam_size}")
    print(f"  Runs       : {num_runs}")
    print(f"{'='*60}\n")

    # Start whisper-server
    print("  Démarrage whisper-server...")
    env = os.environ.copy()

    # Add Vulkan SDK to PATH if available
    vulkan_sdk = os.environ.get("VULKAN_SDK", r"C:\VulkanSDK\1.4.341.1")
    if Path(vulkan_sdk).exists():
        env["PATH"] = str(Path(vulkan_sdk) / "Bin") + ";" + env.get("PATH", "")

    # Add whisper.cpp DLLs to PATH
    dll_dir = WHISPER_SERVER.parent
    env["PATH"] = str(dll_dir) + ";" + env.get("PATH", "")

    cmd = [
        str(WHISPER_SERVER),
        "--model", str(model_path),
        "--host", SERVER_HOST,
        "--port", str(SERVER_PORT),
        "--language", language,
        "--beam-size", str(beam_size),
    ]

    proc = subprocess.Popen(
        cmd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    try:
        if not _server_ready(SERVER_PORT):
            print("  ERREUR : whisper-server n'a pas démarré dans les 30s")
            return

        print("  whisper-server prêt.\n")

        rtfs = []
        for i in range(num_runs):
            text, elapsed = transcribe_http(wav_path, SERVER_PORT)
            rtf = elapsed / audio_duration
            rtfs.append(rtf)
            print(f"  Run {i+1}/{num_runs}: {elapsed:.3f}s  RTF={rtf:.3f}  \"{text[:80]}\"")

        # Results
        avg_rtf = np.mean(rtfs)
        min_rtf = np.min(rtfs)
        max_rtf = np.max(rtfs)

        print(f"\n{'─'*60}")
        print(f"  RÉSULTATS")
        print(f"{'─'*60}")
        print(f"  RTF moyen  : {avg_rtf:.3f}")
        print(f"  RTF min    : {min_rtf:.3f}")
        print(f"  RTF max    : {max_rtf:.3f}")
        print(f"  Latence moy: {avg_rtf * audio_duration:.3f}s pour {audio_duration:.1f}s audio")

        if avg_rtf <= 0.3:
            verdict = "EXCELLENT — temps réel fluide"
        elif avg_rtf <= 0.5:
            verdict = "BON — utilisable en temps réel"
        elif avg_rtf <= 1.0:
            verdict = "ACCEPTABLE — léger décalage"
        else:
            verdict = "INSUFFISANT — pas temps réel"

        print(f"  Verdict    : {verdict}")
        print(f"{'─'*60}\n")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def main():
    parser = argparse.ArgumentParser(description="Benchmark STT EXO v4.1")
    parser.add_argument("--audio", type=str, help="Chemin vers un fichier WAV 16kHz mono")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Nom du modèle (small, medium, large-v3)")
    parser.add_argument("--runs", type=int, default=3, help="Nombre de runs")
    parser.add_argument("--language", type=str, default="fr", help="Langue")
    parser.add_argument("--beam-size", type=int, default=5, help="Beam size")
    args = parser.parse_args()

    # Resolve audio file
    if args.audio:
        wav_path = Path(args.audio)
        if not wav_path.exists():
            print(f"ERREUR: Fichier audio introuvable : {wav_path}")
            sys.exit(1)
    else:
        wav_path = PROJECT_ROOT / "scripts" / "_benchmark_test.wav"
        if not wav_path.exists():
            print("  Génération d'un fichier audio de test...")
            generate_test_wav(wav_path, duration=5.0)

    run_benchmark(
        model_name=args.model,
        wav_path=wav_path,
        num_runs=args.runs,
        language=args.language,
        beam_size=args.beam_size,
    )


if __name__ == "__main__":
    main()
