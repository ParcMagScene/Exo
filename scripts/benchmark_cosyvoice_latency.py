import json
import os
import statistics
import time
from pathlib import Path

from python.tts.cosyvoice_engine import CosyVoiceEngine

MODEL_DIR = Path(r"D:/EXO/models/cosyvoice")
CACHE_DIR = MODEL_DIR / ".cache"

# Keep everything under D:/EXO
os.environ.setdefault("EXO_COSYVOICE_MODELS", str(MODEL_DIR))
os.environ.setdefault("HF_HOME", str(CACHE_DIR))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(CACHE_DIR))
os.environ.setdefault("TRANSFORMERS_CACHE", str(CACHE_DIR))
os.environ.setdefault("TORCH_HOME", str(CACHE_DIR))
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))
os.environ.setdefault("TEMP", str(CACHE_DIR))
os.environ.setdefault("TMP", str(CACHE_DIR))
os.environ.setdefault("HOME", str(CACHE_DIR / "user"))
os.environ.setdefault("USERPROFILE", str(CACHE_DIR / "user"))

TEXT = "Bonjour, je suis EXO. Ceci est un test de latence en streaming vocal français en temps réel."
VOICES = ["fr_female_01", "fr_female_02", "fr_male_01"]
RUNS_PER_MODE = 5


def p95(values):
    if not values:
        return 0.0
    vals = sorted(values)
    idx = max(0, min(len(vals) - 1, int(round(0.95 * (len(vals) - 1)))))
    return vals[idx]


def run_bench(engine: CosyVoiceEngine, optimized: bool):
    engine.latency_optimized = optimized

    first_chunk_ms_all = []
    e2e_ms_all = []
    chunk_gap_ms_all = []
    chunks_per_req = []

    for i in range(RUNS_PER_MODE):
        voice = VOICES[i % len(VOICES)]
        t0 = time.perf_counter()
        first_ts = None
        prev_ts = None
        chunks = 0

        for chunk in engine.synthesize_stream(TEXT, voice=voice, lang="fr", rate=1.0):
            now = time.perf_counter()
            if not chunk:
                continue
            chunks += 1
            if first_ts is None:
                first_ts = now
                first_chunk_ms_all.append((first_ts - t0) * 1000.0)
            if prev_ts is not None:
                chunk_gap_ms_all.append((now - prev_ts) * 1000.0)
            prev_ts = now

        t1 = time.perf_counter()
        e2e_ms_all.append((t1 - t0) * 1000.0)
        chunks_per_req.append(chunks)

    return {
        "mode": "optimized" if optimized else "baseline",
        "runs": RUNS_PER_MODE,
        "first_chunk_ms": {
            "avg": round(statistics.mean(first_chunk_ms_all), 2),
            "p95": round(p95(first_chunk_ms_all), 2),
            "min": round(min(first_chunk_ms_all), 2),
            "max": round(max(first_chunk_ms_all), 2),
        },
        "chunk_to_chunk_ms": {
            "avg": round(statistics.mean(chunk_gap_ms_all), 2) if chunk_gap_ms_all else 0.0,
            "p95": round(p95(chunk_gap_ms_all), 2) if chunk_gap_ms_all else 0.0,
        },
        "end_to_end_ms": {
            "avg": round(statistics.mean(e2e_ms_all), 2),
            "p95": round(p95(e2e_ms_all), 2),
            "min": round(min(e2e_ms_all), 2),
            "max": round(max(e2e_ms_all), 2),
        },
        "chunks_per_request": {
            "avg": round(statistics.mean(chunks_per_req), 2),
            "min": min(chunks_per_req),
            "max": max(chunks_per_req),
        },
    }


def run_stability(engine: CosyVoiceEngine):
    engine.latency_optimized = True
    failures = []
    total_chunks = 0
    n = 15
    text = "Test de stabilité streaming continu."

    for i in range(n):
        voice = VOICES[i % len(VOICES)]
        got = 0
        try:
            for chunk in engine.synthesize_stream(text, voice=voice, lang="fr", rate=1.0):
                if chunk:
                    got += 1
            total_chunks += got
            if got == 0:
                failures.append({"run": i, "voice": voice, "error": "no_chunk"})
        except Exception as exc:
            failures.append({"run": i, "voice": voice, "error": str(exc)})

    return {
        "runs": n,
        "failures": failures,
        "failure_count": len(failures),
        "total_chunks": total_chunks,
    }


def main():
    engine = CosyVoiceEngine(voice="fr_female_01", lang="fr")
    t_load0 = time.perf_counter()
    engine.load()
    load_ms = (time.perf_counter() - t_load0) * 1000.0

    baseline = run_bench(engine, optimized=False)
    optimized = run_bench(engine, optimized=True)
    stability = run_stability(engine)

    result = {
        "load_ms": round(load_ms, 2),
        "baseline": baseline,
        "optimized": optimized,
        "stability": stability,
        "voices": engine.list_voices(),
    }

    out = Path(r"D:/EXO/project/docs/cosyvoice_latency_metrics.json")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
