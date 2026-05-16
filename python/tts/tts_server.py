#!/usr/bin/env python
"""Shim EXO -- ``python/tts/tts_server.py``.

Ce fichier est un **shim de delegation**. Le veritable serveur TTS WebSocket
d'EXO est implemente dans ``services/orpheus/server_ws.py`` (Orpheus 3B FR
GGUF Q8 + SNAC) et requiert la venv dediee ``services/orpheus/venv`` (qui
embarque ``llama-cpp-python`` CUDA + ``torch`` + ``snac``).

De nombreuses references historiques (tasks.json, launch_exo_silent.ps1,
``python/start_missing_services.py``, ``python/test/exo_test_runner.py``,
``scripts/auto_kill_zombies.py``, ``python/orchestrator/tts_predictive.py``,
documents d'audit) pointent encore vers ce chemin. Ce shim assure la
compatibilite en lancant le vrai serveur dans la bonne venv lorsqu'il est
invoque depuis ``.venv_stt_tts``.

Comportement :
    1. Si le port 8767 est deja ecoute (Orpheus tourne deja), exit 0.
    2. Sinon, lance ``services/orpheus/server_ws.py`` via la venv Orpheus,
       en heritant des variables d'environnement (``ORPHEUS_GGUF_PATH``,
       ``ORPHEUS_WS_HOST``, ``ORPHEUS_WS_PORT`` ...).
    3. Les arguments CLI historiques (``--lang fr --streaming ...``) sont
       acceptes mais ignores : le serveur Orpheus se configure via env vars.

Port d'ecoute (defaut) : ``8767`` -- override via ``ORPHEUS_WS_PORT``.
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[2]
ORPHEUS_DIR: Path = ROOT / "services" / "orpheus"
ORPHEUS_PY: Path = ORPHEUS_DIR / "venv" / "Scripts" / "python.exe"
ORPHEUS_SERVER: Path = ORPHEUS_DIR / "server_ws.py"
ORPHEUS_GGUF: Path = (
    ROOT / "models" / "orpheus_fr_gguf" / "Orpheus-3b-French-FT-Q8_0.gguf"
)
DEFAULT_PORT: int = int(os.environ.get("ORPHEUS_WS_PORT", "8767"))


def _port_busy(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.3)
    try:
        return sock.connect_ex(("127.0.0.1", port)) == 0
    finally:
        sock.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    # Accepte (et ignore) les flags historiques pour compat tasks.json.
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--lang", default="fr")
    parser.add_argument("--streaming", action="store_true")
    parser.add_argument("--chunk-size", type=int, default=16000)
    parser.add_argument("--max-chunk-length", type=int, default=2048)
    parser.add_argument("--latency-optimized", action="store_true")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args, _unknown = parser.parse_known_args(argv)
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    port = int(args.port)

    if _port_busy(port):
        print(
            f"[tts_server shim] port {port} deja occupe ; Orpheus suppose actif. exit 0",
            flush=True,
        )
        return 0

    for path, label in (
        (ORPHEUS_PY, "Orpheus venv Python"),
        (ORPHEUS_SERVER, "services/orpheus/server_ws.py"),
        (ORPHEUS_GGUF, "Orpheus Q8 GGUF"),
    ):
        if not path.exists():
            print(
                f"[tts_server shim] ERREUR : {label} introuvable : {path}",
                file=sys.stderr,
                flush=True,
            )
            return 2

    env = os.environ.copy()
    env.setdefault("ORPHEUS_GGUF_PATH", str(ORPHEUS_GGUF))
    env.setdefault("ORPHEUS_WS_HOST", "0.0.0.0")
    env.setdefault("ORPHEUS_WS_PORT", str(port))
    env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    # ── Propagation config audio (rate, pacing, cache) au serveur Orpheus ──
    # Lit exo_v9.json via ConfigManager pour piloter le pacing TTS sans
    # toucher au code Orpheus si la venv ne partage pas le PYTHONPATH.
    try:
        sys.path.insert(0, str(ROOT / "python"))
        from shared.config_manager import ConfigManager  # type: ignore
        _cm = ConfigManager.instance()
        _rate = _cm.get("tts.rate", None)
        _sent = _cm.get("tts.pacing.sentencePause",
                        _cm.get("tts.pacing.sentence_pause_ms", None))
        _comma = _cm.get("tts.pacing.commaPause",
                         _cm.get("tts.pacing.comma_pause_ms", None))
        _cache_max_tokens = _cm.get("tts.cache.maxTokens",
                                     _cm.get("tts.cache.max_tokens", None))
        if _rate is not None:
            env.setdefault("ORPHEUS_DEFAULT_RATE", f"{float(_rate):.4f}")
        if _sent is not None:
            env.setdefault("ORPHEUS_SENTENCE_PAUSE_MS", str(int(_sent)))
        if _comma is not None:
            env.setdefault("ORPHEUS_COMMA_PAUSE_MS", str(int(_comma)))
        if _cache_max_tokens is not None:
            env.setdefault("ORPHEUS_N_CTX", str(int(_cache_max_tokens)))
    except Exception as exc:
        print(f"[tts_server shim] ConfigManager indisponible : {exc}",
              file=sys.stderr, flush=True)

    print(
        f"[tts_server shim] delegation -> {ORPHEUS_SERVER} (venv Orpheus, port {port})",
        flush=True,
    )
    return subprocess.call(
        [str(ORPHEUS_PY), str(ORPHEUS_SERVER)],
        cwd=str(ORPHEUS_DIR),
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
