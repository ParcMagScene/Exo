"""Profiler factuel des voix CosyVoice2 FR.

Mesure (par voix) sur un echantillon court synthetise:
  - pitch_median_hz   (librosa.yin)
  - pitch_std_hz      (stabilite de hauteur)
  - speech_rate_sps   (syllabes/seconde, via Whisper FR + heuristique syllabes)
  - duration_s
  - rtf_estimate

Classe les voix par un score 'fr_score' simple base sur:
  - debit dans la fenetre francaise typique (3.5 - 4.5 syl/s)  -> +
  - stabilite de pitch                                          -> +
Sans heuristique 'accent etranger' (non mesurable de maniere fiable).

Sortie: D:/EXO/logs/tts_voice_report.json

Usage:
    python scripts/profile_voices.py [--port 8767]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import struct
import sys
import time
from pathlib import Path

import numpy as np

REPORT_PATH = Path(r"D:/EXO/logs/tts_voice_report.json")
SAMPLE_TEXT = "Bonjour, ceci est un test de la voix francaise."
SAMPLE_RATE = 24000  # CosyVoice2 native


def _pcm16_to_float(pcm: bytes) -> np.ndarray:
    if not pcm:
        return np.zeros(0, dtype=np.float32)
    n = len(pcm) // 2
    arr = np.frombuffer(pcm[: n * 2], dtype="<i2").astype(np.float32) / 32768.0
    return arr


async def _ws_synthesize(uri: str, text: str, voice: str | None = None, timeout: float = 60.0) -> tuple[bytes, float]:
    import websockets  # type: ignore
    pcm = bytearray()
    t0 = time.monotonic()
    async with websockets.connect(uri, max_size=None) as ws:
        # Wait ready
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
            if isinstance(msg, str):
                try:
                    data = json.loads(msg)
                except Exception:
                    continue
                if data.get("type") == "ready":
                    break
        req = {"type": "synthesize", "text": text, "lang": "fr", "rate": 1.0}
        if voice:
            req["voice"] = voice
        await ws.send(json.dumps(req))
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
            if isinstance(msg, (bytes, bytearray)):
                pcm.extend(msg)
            else:
                try:
                    data = json.loads(msg)
                except Exception:
                    continue
                t = data.get("type")
                if t in ("end", "synthesis_end", "done"):
                    break
                if t == "error":
                    raise RuntimeError(f"server error: {data}")
    return bytes(pcm), time.monotonic() - t0


async def _list_voices(uri: str, timeout: float = 30.0) -> tuple[list[str], str | None]:
    import websockets  # type: ignore
    async with websockets.connect(uri, max_size=None) as ws:
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
            if isinstance(msg, str):
                d = json.loads(msg)
                if d.get("type") == "ready":
                    break
        await ws.send(json.dumps({"type": "list_voices"}))
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
            if isinstance(msg, str):
                d = json.loads(msg)
                if d.get("type") == "voices":
                    return list(d.get("available") or []), d.get("current")
    return [], None


def _measure_pitch(audio: np.ndarray, sr: int) -> tuple[float, float]:
    import librosa  # type: ignore
    if audio.size < sr // 4:
        return 0.0, 0.0
    try:
        f0 = librosa.yin(audio, fmin=70, fmax=400, sr=sr, frame_length=2048)
        f0 = f0[np.isfinite(f0)]
        if f0.size == 0:
            return 0.0, 0.0
        return float(np.median(f0)), float(np.std(f0))
    except Exception:
        return 0.0, 0.0


_VOWEL_GROUPS = re.compile(r"[aeiouy\u00e0\u00e2\u00e4\u00e9\u00e8\u00ea\u00eb\u00ee\u00ef\u00f4\u00f6\u00f9\u00fb\u00fc]+", re.IGNORECASE)


def _count_syllables_fr(text: str) -> int:
    # Approximation: groupes de voyelles consecutives ~ noyaux syllabiques.
    return len(_VOWEL_GROUPS.findall(text))


def _score_voice(pitch_std: float, rate_sps: float) -> float:
    # Distance au debit FR cible 4.0 syl/s (intervalle confortable 3.5-4.5).
    if rate_sps <= 0:
        rate_pen = 1.0
    else:
        rate_pen = min(1.0, abs(rate_sps - 4.0) / 4.0)
    # Pitch instable (std) penalise.
    pitch_pen = min(1.0, pitch_std / 100.0)
    score = 1.0 - 0.6 * rate_pen - 0.4 * pitch_pen
    return round(max(0.0, score), 4)


async def _profile(port: int, voices_filter: list[str] | None) -> dict:
    uri = f"ws://127.0.0.1:{port}"
    voices, current = await _list_voices(uri)
    if voices_filter:
        voices = [v for v in voices if v in voices_filter]
    print(f"[info] voices: {voices} (current={current})", flush=True)
    results = []
    for v in voices:
        try:
            print(f"[run] voice={v} ...", flush=True)
            pcm, total_s = await _ws_synthesize(uri, SAMPLE_TEXT, voice=v)
            audio = _pcm16_to_float(pcm)
            dur = audio.size / SAMPLE_RATE
            pitch_med, pitch_std = _measure_pitch(audio, SAMPLE_RATE)
            syl = _count_syllables_fr(SAMPLE_TEXT)
            rate_sps = (syl / dur) if dur > 0 else 0.0
            rtf = total_s / dur if dur > 0 else float("inf")
            score = _score_voice(pitch_std, rate_sps)
            entry = {
                "voice": v,
                "duration_s": round(dur, 3),
                "synth_total_s": round(total_s, 3),
                "rtf_estimate": round(rtf, 3),
                "pitch_median_hz": round(pitch_med, 1),
                "pitch_std_hz": round(pitch_std, 1),
                "speech_rate_sps": round(rate_sps, 2),
                "fr_score": score,
            }
            print(f"  -> {entry}", flush=True)
            results.append(entry)
        except Exception as e:
            print(f"  ! voice={v} failed: {e}", flush=True)
            results.append({"voice": v, "error": str(e)})
    results.sort(key=lambda x: x.get("fr_score", -1.0), reverse=True)
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sample_text": SAMPLE_TEXT,
        "sample_rate": SAMPLE_RATE,
        "current_voice": current,
        "ranking": [r["voice"] for r in results if "fr_score" in r],
        "results": results,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[ok] report -> {REPORT_PATH}", flush=True)
    return report


def get_best_french_voices(top_n: int = 3) -> list[str]:
    """Lit le rapport et retourne les top_n voix par fr_score.

    Retourne [] si rapport absent (l'engine choisira EXO_TTS_DEFAULT_VOICE).
    """
    try:
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return list(report.get("ranking", []))[:top_n]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8767)
    p.add_argument("--voices", nargs="*", default=None, help="filtre optionnel d'IDs")
    args = p.parse_args()
    asyncio.run(_profile(args.port, args.voices))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
