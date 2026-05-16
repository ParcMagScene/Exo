#!/usr/bin/env python3
"""
Start Missing EXO Services
===========================
Standalone script that reads a list of DOWN service names from stdin
or CLI arguments and starts the corresponding Python servers.

Usage:
    python python/start_missing_services.py context planner domotic homegraph network
    echo "context planner" | python python/start_missing_services.py --stdin
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_EXO_ROOT = Path(os.environ.get("EXO_ROOT", r"D:\EXO"))

# Service → script mapping (from config/services.json)
SERVICE_REGISTRY: dict[str, dict] = {
    "context":   {"port": 8777, "script": "python/context/context_engine.py",       "venv": ".venv_stt_tts"},
    "planner":   {"port": 8778, "script": "python/planner/task_planner_server.py",  "venv": ".venv_stt_tts"},
    "domotic":   {"port": 8785, "script": "python/domotique/domotic_service.py",    "venv": ".venv_stt_tts"},
    "homegraph": {"port": 8784, "script": "python/domotique/homegraph_server.py",   "venv": ".venv_stt_tts"},
    "network":   {"port": 8790, "script": "python/network/network_map_service.py",  "venv": ".venv_stt_tts"},
    "stt":       {"port": 8766, "script": "python/stt/stt_server.py",               "venv": ".venv_stt_tts"},
    "tts":       {"port": 8767, "script": "python/tts/tts_server.py",               "venv": ".venv_stt_tts"},
    "vad":       {"port": 8768, "script": "python/vad/vad_server.py",               "venv": ".venv_stt_tts"},
    "wakeword":  {"port": 8770, "script": "python/wakeword/wakeword_server.py",     "venv": ".venv_stt_tts"},
    "memory":    {"port": 8771, "script": "python/memory/memory_server.py",         "venv": ".venv_stt_tts"},
    "nlu":       {"port": 8772, "script": "python/nlu/nlu_server.py",               "venv": ".venv_stt_tts"},
}

# Environment variables for EXO services (derived from EXO_ROOT)
EXO_ENV = {
    "EXO_WHISPER_MODELS":   str(_EXO_ROOT / "models" / "whisper"),
    "EXO_WHISPERCPP_BIN":   str(_EXO_ROOT / "whispercpp" / "build_vk" / "bin" / "Release"),
    "EXO_ORPHEUS_MODELS":   str(_EXO_ROOT / "models" / "orpheus_fr_gguf"),
    "EXO_FAISS_DIR":        str(_EXO_ROOT / "faiss" / "semantic_memory"),
    "EXO_WAKEWORD_MODELS":  str(_EXO_ROOT / "models" / "wakeword"),
    "HF_HOME":              str(_EXO_ROOT / "cache" / "huggingface"),
    "TRANSFORMERS_CACHE":   str(_EXO_ROOT / "cache" / "huggingface" / "hub"),
}


def port_is_open(port: int) -> bool:
    try:
        with socket.create_connection(("localhost", port), timeout=0.5):
            return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False


def start_service(name: str) -> bool:
    """Start a single service. Returns True if launched."""
    info = SERVICE_REGISTRY.get(name)
    if not info:
        print(f"  ✗ Service inconnu: {name}")
        return False

    port = info["port"]
    if port_is_open(port):
        print(f"  ✔ {name} déjà actif sur :{port}")
        return False

    script = PROJECT_ROOT / info["script"]
    if not script.exists():
        print(f"  ✗ Script introuvable: {script}")
        return False

    venv = info["venv"]
    if sys.platform == "win32":
        python = PROJECT_ROOT / venv / "Scripts" / "python.exe"
    else:
        python = PROJECT_ROOT / venv / "bin" / "python"

    if not python.exists():
        print(f"  ✗ Python introuvable: {python}")
        return False

    env = dict(os.environ)
    for k, v in EXO_ENV.items():
        env.setdefault(k, v)

    print(f"  → Démarrage {name} ({script.name}, port {port}) …")
    try:
        subprocess.Popen(
            [str(python), str(script)],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return True
    except Exception as e:
        print(f"  ✗ Échec: {e}")
        return False


def wait_for_ports(services: list[str], max_wait: float = 5.0) -> list[str]:
    """Wait up to max_wait seconds for services to open their ports.
    Returns list of services still DOWN."""
    deadline = time.time() + max_wait
    remaining = list(services)

    while remaining and time.time() < deadline:
        time.sleep(0.5)
        remaining = [
            n for n in remaining
            if not port_is_open(SERVICE_REGISTRY[n]["port"])
        ]

    return remaining


def main() -> None:
    parser = argparse.ArgumentParser(description="Start missing EXO services")
    parser.add_argument("services", nargs="*", help="Service names to start")
    parser.add_argument("--stdin", action="store_true",
                        help="Read service names from stdin (space-separated)")
    args = parser.parse_args()

    names: list[str] = list(args.services)
    if args.stdin:
        names.extend(sys.stdin.read().split())

    if not names:
        print("Aucun service spécifié.")
        print(f"Services disponibles: {', '.join(sorted(SERVICE_REGISTRY))}")
        sys.exit(1)

    print(f"\n  EXO — Démarrage de {len(names)} service(s)\n")

    launched = [n for n in names if start_service(n)]

    if launched:
        print(f"\n  Attente disponibilité …")
        still_down = wait_for_ports(launched)
        if still_down:
            print(f"  ⚠ Toujours DOWN après 5s: {', '.join(still_down)}")
            sys.exit(1)
        else:
            print(f"  ✔ Tous les services démarrés avec succès.")
    else:
        print(f"\n  Aucun service à démarrer.")

    sys.exit(0)


if __name__ == "__main__":
    main()
