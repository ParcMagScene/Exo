"""J2 (2026-05-16) - Validation auditive A/B Q5_K_M vs Q8_0.

Genere des WAV pour la meme phrase avec chaque modele, dans
D:/EXO/logs/orpheus_ab_j2/. Chaque generation utilise les meme
parametres (voix=pierre, speed=1.0).

Pas de modification du modele actif d'EXO : ce script charge directement
chaque GGUF en isolant l'etat global de server_gguf entre les deux passes.
"""
from __future__ import annotations

import gc
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
SVC = ROOT / "services" / "orpheus"
MODELS_DIR = ROOT / "models" / "orpheus_fr_gguf"
OUT_DIR = ROOT / "logs" / "orpheus_ab_j2"

PHRASES = [
    ("p1_court",   "Bonjour, je suis EXO."),
    ("p2_moyen",   "Voici la meteo : seize degres a Paris, vent leger d'ouest."),
    ("p3_long",    "Je peux allumer les lumieres du salon, lancer ta playlist preferee, "
                   "ou te lire les dernieres actualites. Que veux-tu faire maintenant ?"),
]

VARIANTS = [
    ("Q5_K_M", MODELS_DIR / "Orpheus-3b-French-FT-Q5_K_M.gguf"),
    ("Q8_0",   MODELS_DIR / "Orpheus-3b-French-FT-Q8_0.gguf"),
]


def _reload_server(gguf: Path):
    os.environ["ORPHEUS_GGUF_PATH"] = str(gguf)
    for mod in list(sys.modules):
        if mod.startswith("server_gguf") or mod.startswith("llama_cpp"):
            del sys.modules[mod]
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass
    sys.path.insert(0, str(SVC))
    import server_gguf as srv  # type: ignore
    srv.load_models()
    return srv


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = []
    for quant, gguf in VARIANTS:
        if not gguf.is_file():
            print(f"[skip] {quant} : {gguf} introuvable")
            continue
        print(f"\n=== {quant} ===")
        srv = _reload_server(gguf)
        for tag, text in PHRASES:
            t0 = time.time()
            audio = srv.synthesize(text=text, voice="pierre", speed=1.0)
            dt = time.time() - t0
            dur = len(audio) / float(srv.SAMPLE_RATE)
            rtf = dt / max(dur, 1e-6)
            out = OUT_DIR / f"{tag}_{quant}.wav"
            sf.write(str(out), audio.astype(np.float32), srv.SAMPLE_RATE)
            print(f"  {tag}: dur={dur:.2f}s gen={dt:.2f}s rtf={rtf:.2f} -> {out.name}")
            summary.append((quant, tag, round(dur, 2), round(dt, 2), round(rtf, 3), str(out)))
        try:
            del srv.STATE.llm
            srv.STATE.llm = None
        except Exception:
            pass
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass

    print("\n=== A/B pairs (ecoute requise) ===")
    print(f"Output dir: {OUT_DIR}")
    for q, tag, dur, dt, rtf, path in summary:
        print(f"  [{q}] {tag}: dur={dur}s rtf={rtf}  ({path})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
