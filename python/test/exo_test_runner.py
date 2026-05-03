#!/usr/bin/env python3
"""
EXO Stability Test Runner
==========================
Connects directly to each Python microservice via WebSocket,
sends application-level pings, measures latency, detects
timeouts / disconnections / flapping, and loops until stable.

Usage:
    python python/test/exo_test_runner.py [--loops N] [--timeout MS]
    python python/test/exo_test_runner.py --autoheal --loops 10 --timeout 5000
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import websockets
    from websockets.exceptions import (
        ConnectionClosed,
        InvalidURI,
        WebSocketException,
    )
except ImportError:
    print("websockets not installed – pip install websockets>=12", file=sys.stderr)
    sys.exit(1)

# ── Service registry (mirrors config/services.json) ─────────────
SERVICES: dict[str, int] = {
    "stt":       8766,
    "tts":       8767,
    "vad":       8768,
    "wakeword":  8770,
    "memory":    8771,
    "nlu":       8772,
    "context":   8777,
    "planner":   8778,
    "network":   8790,
    "domotic":   8785,
    "homegraph": 8784,
}

PING_TIMEOUT_MS   = 5000   # max wait for pong
FLAP_WINDOW_S     = 30     # seconds to track flaps
FLAP_THRESHOLD    = 3      # transitions within window = flapping
MAX_LOOPS_DEFAULT = 10


# ── Data ─────────────────────────────────────────────────────────
@dataclass
class ServiceResult:
    status: str = "unknown"          # ok | timeout | down | flapping | error
    latency_ms: float = -1
    error: str | None = None
    transitions: list[float] = field(default_factory=list)


@dataclass
class TestReport:
    timestamp: str = ""
    loop: int = 0
    services: dict[str, dict[str, Any]] = field(default_factory=dict)
    all_green: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "loop": self.loop,
            "services": self.services,
            "all_green": self.all_green,
            "errors": self.errors,
        }


# ── Helpers ──────────────────────────────────────────────────────

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _color(text: str, code: int) -> str:
    return f"\033[{code}m{text}\033[0m"


def _green(t: str) -> str:   return _color(t, 32)
def _red(t: str) -> str:     return _color(t, 31)
def _yellow(t: str) -> str:  return _color(t, 33)
def _cyan(t: str) -> str:    return _color(t, 36)


# ── Ping one service ─────────────────────────────────────────────

async def ping_service(name: str, port: int, timeout_ms: int) -> ServiceResult:
    """Open WS, send ping, wait for pong, close."""
    result = ServiceResult()
    uri = f"ws://localhost:{port}"

    try:
        async with websockets.connect(
            uri,
            open_timeout=timeout_ms / 1000,
            close_timeout=1,
            ping_interval=None,
            ping_timeout=None,
        ) as ws:
            # Some servers send a "ready" message first — drain it
            try:
                await asyncio.wait_for(ws.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                pass

            # Build ping payload (NLU uses "action" key)
            if name == "nlu":
                payload = json.dumps({"action": "ping"})
            else:
                payload = json.dumps({"type": "ping"})

            t0 = time.perf_counter()
            await ws.send(payload)

            # Wait for pong
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout_ms / 1000)
                t1 = time.perf_counter()
                latency = (t1 - t0) * 1000

                msg = json.loads(raw)
                if msg.get("type") == "pong":
                    result.status = "ok"
                    result.latency_ms = round(latency, 1)
                else:
                    # Got something but not pong
                    result.status = "ok"
                    result.latency_ms = round(latency, 1)

            except asyncio.TimeoutError:
                result.status = "timeout"
                result.error = f"no pong within {timeout_ms}ms"

    except asyncio.TimeoutError:
        result.status = "timeout"
        result.error = f"open timeout on {uri}"
    except asyncio.CancelledError:
        result.status = "cancelled"
        result.error = f"task cancelled for {uri}"
    except (ConnectionRefusedError, OSError):
        result.status = "down"
        result.error = f"connection refused on {uri}"
    except ConnectionClosed as e:
        result.status = "down"
        result.error = f"connection closed: {e}"
    except WebSocketException as e:
        result.status = "error"
        result.error = str(e)
    except Exception as e:
        result.status = "error"
        result.error = f"{type(e).__name__}: {e}"

    return result


# ── Flap detection ───────────────────────────────────────────────

class FlapTracker:
    """Track status transitions per service to detect flapping."""

    def __init__(self) -> None:
        self._history: dict[str, list[tuple[float, str]]] = {}

    def record(self, name: str, status: str) -> bool:
        """Record status, return True if flapping detected."""
        now = time.time()
        hist = self._history.setdefault(name, [])
        hist.append((now, status))

        # Trim to window
        cutoff = now - FLAP_WINDOW_S
        hist[:] = [(t, s) for t, s in hist if t >= cutoff]

        # Count transitions
        transitions = 0
        for i in range(1, len(hist)):
            if hist[i][1] != hist[i - 1][1]:
                transitions += 1

        return transitions >= FLAP_THRESHOLD


# ── Full test run ────────────────────────────────────────────────

async def run_all_tests(
    loop_num: int,
    flap_tracker: FlapTracker,
    timeout_ms: int,
) -> TestReport:
    """Ping all services concurrently, build report."""
    report = TestReport(timestamp=_now_iso(), loop=loop_num)

    # Ping all services in parallel
    tasks = {
        name: asyncio.create_task(ping_service(name, port, timeout_ms))
        for name, port in SERVICES.items()
    }

    results: dict[str, ServiceResult] = {}
    for name, task in tasks.items():
        try:
            results[name] = await task
        except asyncio.CancelledError:
            results[name] = ServiceResult(status="cancelled", error="task cancelled")
        except Exception as e:
            results[name] = ServiceResult(status="error", error=f"{type(e).__name__}: {e}")

    # Check for flapping
    for name, res in results.items():
        is_flapping = flap_tracker.record(name, res.status)
        if is_flapping and res.status != "down":
            res.status = "flapping"

    # Build report
    all_ok = True
    for name, res in results.items():
        entry: dict[str, Any] = {"status": res.status}
        if res.latency_ms >= 0:
            entry["latency_ms"] = res.latency_ms
        if res.error:
            entry["error"] = res.error
            report.errors.append(f"{name}: {res.error}")
        if res.status != "ok":
            all_ok = False
        report.services[name] = entry

    report.all_green = all_ok
    return report


# ── Pretty print ─────────────────────────────────────────────────

def print_report(report: TestReport) -> None:
    """Print a human-readable summary."""
    print(f"\n{'═' * 60}")
    print(f"  EXO Stability Test — Loop #{report.loop}  ({report.timestamp})")
    print(f"{'═' * 60}")

    col_w = 14
    for name in sorted(report.services):
        entry = report.services[name]
        status = entry["status"]
        latency = entry.get("latency_ms", "")

        if status == "ok":
            tag = _green(f"{'OK':>8}")
            lat = f"  {latency:>6.0f} ms" if latency != "" else ""
        elif status == "timeout":
            tag = _yellow(f"{'TIMEOUT':>8}")
            lat = ""
        elif status == "down":
            tag = _red(f"{'DOWN':>8}")
            lat = ""
        elif status == "flapping":
            tag = _yellow(f"{'FLAP':>8}")
            lat = f"  {latency:>6.0f} ms" if latency != "" else ""
        elif status == "cancelled":
            tag = _yellow(f"{'CANCEL':>8}")
            lat = ""
        else:
            tag = _red(f"{'ERROR':>8}")
            lat = ""

        error = f"  ({entry.get('error', '')})" if entry.get("error") else ""
        print(f"  {name:<{col_w}} {tag}{lat}{error}")

    if report.all_green:
        print(f"\n  {'─' * 40}")
        print(f"  {_green('EXO stable ✔')}")
    else:
        print(f"\n  {'─' * 40}")
        print(f"  {_red(f'Instable ❌ — {len(report.errors)} erreur(s)')}")

    print()


# ── Save report to JSON ─────────────────────────────────────────

def save_report(report: TestReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = report.timestamp.replace(":", "-").replace("+", "_")
    path = out_dir / f"stability_{ts}_loop{report.loop}.json"
    path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ── Service script mapping (from config/services.json) ──────────

SERVICE_SCRIPTS: dict[str, dict[str, str]] = {
    "context":   {"script": "python/context/context_engine.py",       "venv": ".venv_stt_tts"},
    "planner":   {"script": "python/planner/task_planner_server.py",  "venv": ".venv_stt_tts"},
    "domotic":   {"script": "python/domotique/domotic_service.py",    "venv": ".venv_stt_tts"},
    "homegraph": {"script": "python/domotique/homegraph_server.py",   "venv": ".venv_stt_tts"},
    "network":   {"script": "python/network/network_map_service.py",  "venv": ".venv_stt_tts"},
    "stt":       {"script": "python/stt/stt_server.py",               "venv": ".venv_stt_tts"},
    "tts":       {"script": "python/tts/tts_server.py",               "venv": ".venv_stt_tts"},
    "vad":       {"script": "python/vad/vad_server.py",               "venv": ".venv_stt_tts"},
    "wakeword":  {"script": "python/wakeword/wakeword_server.py",     "venv": ".venv_stt_tts"},
    "memory":    {"script": "python/memory/memory_server.py",         "venv": ".venv_stt_tts"},
    "nlu":       {"script": "python/nlu/nlu_server.py",               "venv": ".venv_stt_tts"},
}


# ── Detect DOWN services ────────────────────────────────────────

def detect_down_services(report: TestReport) -> list[str]:
    """Return list of service names that are DOWN in the report."""
    return [
        name for name, entry in report.services.items()
        if entry.get("status") in ("down", "timeout", "error")
    ]


# ── Autoheal: start missing services ────────────────────────────

async def start_missing_services(down_services: list[str]) -> list[str]:
    """Start DOWN services, return list of services that were launched."""
    project_root = Path(__file__).resolve().parent.parent.parent
    started: list[str] = []

    for name in down_services:
        info = SERVICE_SCRIPTS.get(name)
        if not info:
            print(f"  {_yellow(f'⚠ Pas de script connu pour {name!r}, skip')}")
            continue

        script = project_root / info["script"]
        if not script.exists():
            print(f"  {_red(f'✗ Script introuvable: {script}')}")
            continue

        venv = info["venv"]
        if sys.platform == "win32":
            python = project_root / venv / "Scripts" / "python.exe"
        else:
            python = project_root / venv / "bin" / "python"

        if not python.exists():
            print(f"  {_red(f'✗ Python introuvable: {python}')}")
            continue

        port = SERVICES.get(name)
        if port and _port_is_open(port):
            print(f"  {_green(f'✔ {name} déjà actif sur :{port}')}")
            continue

        print(f"  Démarrage de {name} ({script.name}) …")
        try:
            env = dict(__import__("os").environ)
            env.setdefault("EXO_WHISPER_MODELS", r"D:\EXO\models\whisper")
            env.setdefault("EXO_WHISPERCPP_BIN", r"D:\EXO\whispercpp\build_vk\bin\Release")
            env.setdefault("EXO_COSYVOICE_MODELS", r"D:\EXO\models\cosyvoice")
            env.setdefault("EXO_FAISS_DIR", r"D:\EXO\faiss\semantic_memory")
            env.setdefault("EXO_WAKEWORD_MODELS", r"D:\EXO\models\wakeword")
            env.setdefault("HF_HOME", r"D:\EXO\cache\huggingface")
            env.setdefault("TRANSFORMERS_CACHE", r"D:\EXO\cache\huggingface\hub")

            subprocess.Popen(
                [str(python), str(script)],
                cwd=str(project_root),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            started.append(name)
        except Exception as e:
            print(f"  {_red(f'✗ Échec démarrage {name}: {e}')}")

    # Wait for ports to open (up to 5 seconds)
    if started:
        print(f"\n  Attente disponibilité ({len(started)} services) …")
        for attempt in range(10):
            await asyncio.sleep(0.5)
            all_up = True
            for name in started:
                port = SERVICES.get(name, 0)
                if not _port_is_open(port):
                    all_up = False
                    break
            if all_up:
                print(f"  {_green(f'✔ Tous les services démarrés ({(attempt + 1) * 0.5:.1f}s)')}")
                break
        else:
            still_down = [n for n in started if not _port_is_open(SERVICES.get(n, 0))]
            if still_down:
                print(f"  {_yellow('Timeout: ' + ', '.join(still_down) + ' toujours DOWN après 5s')}")

    return started


def _port_is_open(port: int) -> bool:
    """Check if a TCP port is open on localhost."""
    import socket
    try:
        with socket.create_connection(("localhost", port), timeout=0.5):
            return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False


# ── Main loop ────────────────────────────────────────────────────

async def main_loop(max_loops: int, timeout_ms: int, autoheal: bool = False) -> bool:
    """Run tests in a loop until stable or max_loops reached."""
    flap_tracker = FlapTracker()
    out_dir = Path("logs/stability")

    mode = "autoheal" if autoheal else "standard"
    print(_cyan(f"\n  EXO Stability Test Runner  [{mode}]"))
    print(_cyan(f"  Services: {', '.join(sorted(SERVICES))}"))
    print(_cyan(f"  Timeout: {timeout_ms} ms  |  Max loops: {max_loops}\n"))

    healed_once = False

    for loop_num in range(1, max_loops + 1):
        try:
            report = await run_all_tests(loop_num, flap_tracker, timeout_ms)
        except asyncio.CancelledError:
            print(_red("\n  Loop annulée (CancelledError). Arrêt."))
            return False
        print_report(report)

        saved = save_report(report, out_dir)
        print(f"  Report saved: {saved}")

        if report.all_green:
            print(_green(f"\n  ╔══════════════════════════════════════════╗"))
            print(_green(f"  ║  EXO fully stable ✔️  ({loop_num} itération(s))  ║"))
            print(_green(f"  ╚══════════════════════════════════════════╝"))
            return True

        # ── Autoheal: start missing services ──
        if autoheal and not healed_once:
            down = detect_down_services(report)
            if down:
                msg = f"[autoheal] {len(down)} service(s) DOWN: " + ", ".join(down)
                print(f"\n  {_cyan(msg)}")
                launched = await start_missing_services(down)
                if launched:
                    healed_once = True
                    print(f"  {_cyan('[autoheal] Pause 2s avant re-test …')}\n")
                    await asyncio.sleep(2)
                    continue  # retry immediately without counting as a failed loop

        if loop_num < max_loops:
            print(f"  Nouvelle tentative dans 3 s …\n")
            await asyncio.sleep(3)

    print(_red(f"\n  ╔══════════════════════════════════════════╗"))
    print(_red(f"  ║  EXO partially stable ❌                 ║"))
    print(_red(f"  ╚══════════════════════════════════════════╝"))
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="EXO Stability Test Runner")
    parser.add_argument("--loops", type=int, default=MAX_LOOPS_DEFAULT,
                        help=f"Max test loops (default {MAX_LOOPS_DEFAULT})")
    parser.add_argument("--timeout", type=int, default=PING_TIMEOUT_MS,
                        help=f"Ping timeout in ms (default {PING_TIMEOUT_MS})")
    parser.add_argument("--autoheal", action="store_true",
                        help="Auto-start DOWN services before retesting")
    args = parser.parse_args()

    try:
        stable = asyncio.run(main_loop(args.loops, args.timeout, args.autoheal))
    except KeyboardInterrupt:
        print("\n  Interrompu par l'utilisateur.")
        sys.exit(130)
    sys.exit(0 if stable else 1)


if __name__ == "__main__":
    main()
