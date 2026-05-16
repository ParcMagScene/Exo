"""Bench Orpheus GGUF : compare RTF / first_chunk entre Q4_K_M, Q5_K_M, Q6_K, Q8_0.

Usage:
    python services/orpheus/bench_quants.py [--text "..."] [--runs 3]

Exige que les fichiers GGUF soient presents dans D:\\EXO\\models\\orpheus_fr_gguf\\
sous forme :
    Orpheus-3b-French-FT-Q5_K_M.gguf
    Orpheus-3b-French-FT-Q6_K.gguf
    Orpheus-3b-French-FT-Q8_0.gguf

Pour les telecharger (~2.0-2.6 GB chacun), executer manuellement (approbation
utilisateur requise) :
    huggingface-cli download <repo> Orpheus-3b-French-FT-Q5_K_M.gguf \\
        --local-dir D:\\EXO\\models\\orpheus_fr_gguf\\

Le bench :
    - charge chaque modele a tour de role (decharge le precedent)
    - genere `runs` synthese(s) de la meme phrase
    - calcule RTF moyen et first_chunk moyen
    - affiche un tableau comparatif et recommande le meilleur compromis
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "models" / "orpheus_fr_gguf"
QUANTS = ["Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0"]
RESULTS_JSON = Path(__file__).with_name("bench_quants_results.json")

DEFAULT_TEXT = (
    "Bonjour, je suis EXO, ton assistant vocal. Je peux repondre a tes questions, "
    "lancer tes applications et controler ta maison."
)


def _bench_one(gguf: Path, text: str, runs: int) -> Tuple[float, float, float, float]:
    """Retourne (avg_rtf, avg_first_ms, avg_total_ms, vram_mb)."""
    os.environ["ORPHEUS_GGUF_PATH"] = str(gguf)
    # forcer reimport propre
    for mod in list(sys.modules):
        if mod.startswith("server_gguf") or mod.startswith("llama_cpp"):
            del sys.modules[mod]
    gc.collect()
    try:
        import torch as _torch
        _torch.cuda.empty_cache()
        vram_before = _torch.cuda.memory_allocated() / 1024 / 1024
    except Exception:
        vram_before = 0.0

    sys.path.insert(0, str(Path(__file__).parent))
    import server_gguf as srv  # type: ignore
    srv.load_models()

    try:
        import torch as _torch
        vram_after = _torch.cuda.memory_allocated() / 1024 / 1024
        vram_reserved = _torch.cuda.memory_reserved() / 1024 / 1024
    except Exception:
        vram_after = 0.0
        vram_reserved = 0.0
    vram_used = max(vram_after - vram_before, vram_reserved)

    rtfs: List[float] = []
    firsts: List[float] = []
    totals: List[float] = []
    for i in range(runs):
        t0 = time.time()
        first_ms = None
        # api directe : on appelle synthesize si dispo, sinon create_completion stream
        prompt = f"<|audio|>{srv.STATE.default_voice}: {text}<|eot_id|>"
        out = srv.STATE.llm.create_completion(
            prompt=prompt,
            max_tokens=int(min(2600, max(400, len(text) * 28))),
            temperature=0.6, top_p=0.9, repeat_penalty=1.1,
            stream=True, stop=srv.STOP_TOKEN_STRINGS,
        )
        n_tok = 0
        for chunk in out:
            if first_ms is None:
                first_ms = (time.time() - t0) * 1000
            n_tok += 1
        total_ms = (time.time() - t0) * 1000
        # estimation duree audio : ~83 tokens audio / s
        audio_s = max(0.1, n_tok / 83.0)
        rtf = (total_ms / 1000.0) / audio_s
        rtfs.append(rtf); firsts.append(first_ms or 0); totals.append(total_ms)
        print(f"  run {i+1}/{runs}: tok={n_tok} first={first_ms:.0f}ms total={total_ms:.0f}ms rtf={rtf:.2f}")

    # decharge
    del srv.STATE.llm
    srv.STATE.llm = None
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass

    return (statistics.mean(rtfs), statistics.mean(firsts), statistics.mean(totals), vram_used)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default=DEFAULT_TEXT)
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()

    available = []
    for q in QUANTS:
        p = MODELS_DIR / f"Orpheus-3b-French-FT-{q}.gguf"
        if p.is_file():
            available.append((q, p))
        else:
            print(f"[skip] {q} : {p.name} introuvable")

    if not available:
        print("Aucun modele a benchmarker. Telecharger au moins 2 quantifications.")
        return 1

    results = []
    for q, p in available:
        size_mb = p.stat().st_size / 1024 / 1024
        print(f"\n=== {q} ({size_mb:.0f} MB) ===")
        try:
            rtf, first, total, vram = _bench_one(p, args.text, args.runs)
            results.append((q, size_mb, rtf, first, total, vram))
        except Exception as e:
            print(f"  ECHEC : {e}")

    print("\n=== RESULTAT ===")
    print(f"{'Quant':8s} {'Size_MB':>8s} {'VRAM_MB':>9s} {'RTF':>6s} {'first_ms':>10s} {'total_ms':>10s}")
    for q, sz, rtf, first, total, vram in results:
        print(f"{q:8s} {sz:8.0f} {vram:9.0f} {rtf:6.2f} {first:10.0f} {total:10.0f}")

    if results:
        # critere : RTF le plus bas avec qualite >= Q5_K_M (Q4_K_M penalise)
        ok = [r for r in results if r[0] != "Q4_K_M" and r[2] < 1.2]
        pool = ok or results
        best = min(pool, key=lambda r: r[2])
        print(f"\nRecommandation : {best[0]} (RTF={best[2]:.2f}, first={best[3]:.0f}ms, VRAM={best[5]:.0f}MB)")

    # J5 (2026-05-14) : export JSON consomme par server_gguf.select_best_model()
    # Schema : { "results": [ { model, rtf, first_chunk(ms), vram(GB), quality_ok } ] }
    # quality_ok : True pour >= Q5_K_M, False pour Q4_K_M (penalise par defaut,
    # car aucun benchmark perceptuel automatique n'est embarque ici).
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "runs_per_model": args.runs,
        "results": [
            {
                "model": q,
                "model_variant": q,
                "path": str(MODELS_DIR / f"Orpheus-3b-French-FT-{q}.gguf"),
                "size_mb": round(_sz, 1),
                "rtf": round(rtf, 4),
                "first_chunk": round(first, 2),
                "total_ms": round(_total, 2),
                "vram": round(vram / 1024.0, 3),  # MB -> GB
                "quality_ok": q != "Q4_K_M",
            }
            for (q, _sz, rtf, first, _total, vram) in results
        ],
    }
    try:
        RESULTS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\n[bench] resultats ecrits : {RESULTS_JSON}")
    except Exception as exc:
        print(f"[bench] echec ecriture JSON ({RESULTS_JSON}): {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
