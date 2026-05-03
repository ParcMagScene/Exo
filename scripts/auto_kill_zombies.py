#!/usr/bin/env python3
"""
auto_kill_zombies.py — EXO Zombie Process Cleaner

Detects and kills:
  - Duplicate Python microservice instances
  - Duplicate whisper-server instances
  - Stale Node.js file watchers
  - Excessive VS Code Helper processes

Usage:
  python scripts/auto_kill_zombies.py          # dry-run (report only)
  python scripts/auto_kill_zombies.py --kill   # actually kill duplicates
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
#  EXO microservice registry
# ---------------------------------------------------------------------------

EXO_SERVICES = {
    "exo_server":     {"port": 8765, "script": "exo_server.py"},
    "stt_server":     {"port": 8766, "script": "stt_server.py"},
    "tts_server":     {"port": 8767, "script": "tts_server.py"},
    "vad_server":     {"port": 8768, "script": "vad_server.py"},
    "wakeword_server": {"port": 8770, "script": "wakeword_server.py"},
    "memory_server":  {"port": 8771, "script": "memory_server.py"},
    "nlu_server":     {"port": 8772, "script": "nlu_server.py"},
}

WHISPER_SERVER_EXE = "whisper-server.exe"

# Max allowed Node watchers and Code Helper processes
MAX_NODE_WATCHERS = 3
MAX_CODE_HELPERS = 20


@dataclass
class ProcessInfo:
    pid: int
    name: str
    ram_mb: float
    cmdline: str
    service: str = ""


@dataclass
class CleanupReport:
    python_duplicates: list = field(default_factory=list)
    whisper_duplicates: list = field(default_factory=list)
    node_excess: list = field(default_factory=list)
    code_helper_excess: list = field(default_factory=list)
    killed: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    ram_before_mb: float = 0
    ram_freed_mb: float = 0


# ---------------------------------------------------------------------------
#  Process enumeration (subprocess fallback — no psutil needed)
# ---------------------------------------------------------------------------

def _get_processes() -> list[ProcessInfo]:
    """Get all running processes via WMIC."""
    procs = []
    try:
        result = subprocess.run(
            ["wmic", "process", "get",
             "ProcessId,Name,WorkingSetSize,CommandLine",
             "/format:csv"],
            capture_output=True, text=True, timeout=15,
        )
        for line in result.stdout.strip().splitlines():
            parts = line.split(",")
            if len(parts) < 5:
                continue
            # CSV: Node, CommandLine, Name, ProcessId, WorkingSetSize
            try:
                cmdline = parts[1]
                name = parts[2]
                pid = int(parts[3])
                ram_bytes = int(parts[4]) if parts[4].strip().isdigit() else 0
                procs.append(ProcessInfo(
                    pid=pid,
                    name=name,
                    ram_mb=round(ram_bytes / (1024 * 1024), 1),
                    cmdline=cmdline,
                ))
            except (ValueError, IndexError):
                continue
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # Fallback to tasklist
        result = subprocess.run(
            ["tasklist", "/v", "/fo", "csv"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.strip().splitlines()[1:]:
            parts = line.strip('"').split('","')
            if len(parts) < 5:
                continue
            try:
                name = parts[0]
                pid = int(parts[1])
                ram_str = parts[4].replace("\xa0", "").replace(",", "").replace(" K", "")
                ram_kb = int(re.sub(r"[^\d]", "", ram_str)) if ram_str else 0
                procs.append(ProcessInfo(
                    pid=pid,
                    name=name,
                    ram_mb=round(ram_kb / 1024, 1),
                    cmdline="",
                ))
            except (ValueError, IndexError):
                continue
    return procs


def _kill_process(pid: int) -> bool:
    """Kill a process by PID. Returns True on success."""
    try:
        subprocess.run(
            ["taskkill", "/pid", str(pid), "/f"],
            capture_output=True, timeout=5,
        )
        return True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False


# ---------------------------------------------------------------------------
#  Analysis
# ---------------------------------------------------------------------------

def _identify_service(proc: ProcessInfo) -> str:
    """Match a process to an EXO service name."""
    cmd = proc.cmdline.lower()
    for svc_name, info in EXO_SERVICES.items():
        if info["script"].lower() in cmd:
            return svc_name
    return ""


def _analyze(procs: list[ProcessInfo]) -> CleanupReport:
    """Analyze processes for duplicates and excess."""
    report = CleanupReport()

    # --- Python microservice duplicates ---
    # NOTE: On Windows, venv shim processes (.venv\Scripts\python.exe) spawn
    # the real interpreter (e.g. Python311\python.exe) as a child process.
    # Both share the same command line. The shim stays alive at ~4 MB.
    # We exclude shims (< 10 MB with ".venv" in path) from duplicate detection
    # because killing a shim kills the real child process too.
    service_groups: dict[str, list[ProcessInfo]] = defaultdict(list)
    for p in procs:
        if p.name.lower() != "python.exe":
            continue
        # Skip venv shim/stub processes (tiny RAM, .venv in executable path)
        if p.ram_mb < 10 and ".venv" in p.cmdline:
            continue
        svc = _identify_service(p)
        if svc:
            p.service = svc
            service_groups[svc].append(p)

    for svc_name, group in service_groups.items():
        if len(group) > 1:
            # Keep the one with highest RAM (likely the active one)
            group.sort(key=lambda x: x.ram_mb, reverse=True)
            keeper = group[0]
            for dup in group[1:]:
                report.python_duplicates.append(dup)

    # --- Whisper-server duplicates ---
    whisper_procs = [p for p in procs
                     if WHISPER_SERVER_EXE.lower() in p.name.lower()]
    if len(whisper_procs) > 1:
        # Keep the one using most RAM (has the loaded model)
        whisper_procs.sort(key=lambda x: x.ram_mb, reverse=True)
        for dup in whisper_procs[1:]:
            report.whisper_duplicates.append(dup)

    # --- Excess Node watchers ---
    node_procs = [p for p in procs if p.name.lower() == "node.exe"]
    watcher_procs = [p for p in node_procs
                     if any(kw in p.cmdline.lower()
                            for kw in ("watcherservice", "filewatch",
                                       "chokidar", "nodemon"))]
    if len(watcher_procs) > MAX_NODE_WATCHERS:
        watcher_procs.sort(key=lambda x: x.ram_mb)
        for excess in watcher_procs[:-MAX_NODE_WATCHERS]:
            report.node_excess.append(excess)

    # --- Excess Code Helper ---
    helper_procs = [p for p in procs
                    if "code helper" in p.name.lower()
                    or "code - helper" in p.name.lower()]
    if len(helper_procs) > MAX_CODE_HELPERS:
        helper_procs.sort(key=lambda x: x.ram_mb)
        for excess in helper_procs[:-MAX_CODE_HELPERS]:
            report.code_helper_excess.append(excess)

    # Total RAM of targets
    all_targets = (report.python_duplicates + report.whisper_duplicates +
                   report.node_excess + report.code_helper_excess)
    report.ram_before_mb = sum(p.ram_mb for p in all_targets)

    return report


# ---------------------------------------------------------------------------
#  Execution
# ---------------------------------------------------------------------------

def _execute_cleanup(report: CleanupReport, do_kill: bool) -> None:
    """Kill identified targets if do_kill is True."""
    all_targets = (report.python_duplicates + report.whisper_duplicates +
                   report.node_excess + report.code_helper_excess)

    if not all_targets:
        return

    for proc in all_targets:
        if do_kill:
            ok = _kill_process(proc.pid)
            if ok:
                report.killed.append(proc)
                report.ram_freed_mb += proc.ram_mb
            else:
                report.errors.append(f"Failed to kill PID {proc.pid} ({proc.service or proc.name})")


# ---------------------------------------------------------------------------
#  Reporting
# ---------------------------------------------------------------------------

def _print_report(report: CleanupReport, do_kill: bool) -> None:
    """Print a human-readable report."""
    print()
    print("=" * 70)
    print("  EXO ZOMBIE PROCESS REPORT")
    print("=" * 70)

    def _section(title: str, items: list[ProcessInfo]) -> None:
        if not items:
            print(f"\n  {title}: (none)")
            return
        print(f"\n  {title}: {len(items)} found")
        for p in items:
            status = ""
            if do_kill and p in report.killed:
                status = " [KILLED]"
            elif do_kill and p not in report.killed:
                status = " [FAILED]"
            print(f"    PID {p.pid:>6}  {p.ram_mb:>8.1f} MB  "
                  f"{p.service or p.name}{status}")

    _section("Python duplicates", report.python_duplicates)
    _section("Whisper-server duplicates", report.whisper_duplicates)
    _section("Excess Node watchers", report.node_excess)
    _section("Excess Code Helpers", report.code_helper_excess)

    total = (len(report.python_duplicates) + len(report.whisper_duplicates) +
             len(report.node_excess) + len(report.code_helper_excess))

    print()
    print("-" * 70)
    print(f"  Total zombie/duplicate processes: {total}")
    print(f"  Total RAM occupied: {report.ram_before_mb:.0f} MB "
          f"({report.ram_before_mb / 1024:.1f} GB)")

    if do_kill:
        print(f"  Processes killed: {len(report.killed)}")
        print(f"  RAM freed: {report.ram_freed_mb:.0f} MB "
              f"({report.ram_freed_mb / 1024:.1f} GB)")
        if report.errors:
            print(f"  Errors: {len(report.errors)}")
            for err in report.errors:
                print(f"    - {err}")
    else:
        print()
        print("  ** DRY RUN — no processes killed **")
        print("  Run with --kill to actually clean up.")

    print("=" * 70)
    print()


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="EXO Zombie Process Cleaner — detect and kill duplicate microservices",
    )
    parser.add_argument("--kill", action="store_true",
                        help="Actually kill duplicate/zombie processes (default: dry-run)")
    args = parser.parse_args()

    print("Scanning processes...")
    procs = _get_processes()
    print(f"Found {len(procs)} total processes")

    report = _analyze(procs)
    _execute_cleanup(report, do_kill=args.kill)
    _print_report(report, do_kill=args.kill)

    # Exit code: 0 if clean, 1 if zombies found
    total = (len(report.python_duplicates) + len(report.whisper_duplicates) +
             len(report.node_excess) + len(report.code_helper_excess))
    sys.exit(0 if total == 0 else 1)


if __name__ == "__main__":
    main()
