"""Telecharge le modele Orpheus 3B FR + le codec SNAC dans D:\\EXO\\models.

Usage :
    python download_model.py                           # defaut
    python download_model.py --repo <hf_repo_id>       # override
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_REPO = "canopylabs/3b-fr-ft-research_release"
DEFAULT_DIR = r"D:\EXO\models\orpheus_fr"
SNAC_REPO = "hubertsiuzdak/snac_24khz"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=DEFAULT_REPO, help="HuggingFace repo id du modele Orpheus FR")
    p.add_argument("--dir", default=DEFAULT_DIR, help="Dossier local cible")
    p.add_argument("--token", default=os.environ.get("HF_TOKEN"), help="Token HF (si modele gated)")
    args = p.parse_args()

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("[err] installer huggingface_hub : pip install huggingface_hub", file=sys.stderr)
        return 2

    target = Path(args.dir)
    target.mkdir(parents=True, exist_ok=True)

    print(f"[Orpheus] telechargement {args.repo} -> {target}")
    snapshot_download(
        repo_id=args.repo,
        local_dir=str(target),
        local_dir_use_symlinks=False,
        token=args.token,
        allow_patterns=[
            "*.json", "*.safetensors", "*.bin", "*.model",
            "tokenizer*", "vocab*", "merges*", "special_tokens*",
        ],
    )

    # Verifications minimales
    must = ["config.json", "tokenizer.json"]
    missing = [m for m in must if not (target / m).exists()]
    if missing:
        print(f"[warn] fichiers manquants : {missing}")
    else:
        print("[ok] fichiers cles presents")

    # Pre-cache SNAC (sera recharge depuis HF_HOME au demarrage du serveur)
    print(f"[Orpheus] pre-cache codec {SNAC_REPO}")
    try:
        snapshot_download(repo_id=SNAC_REPO, token=args.token)
        print("[ok] SNAC en cache")
    except Exception as e:
        print(f"[warn] SNAC non pre-cache (sera telecharge au 1er run): {e}")

    print(f"[done] modele pret dans {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
