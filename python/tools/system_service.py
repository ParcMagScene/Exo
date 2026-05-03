#!/usr/bin/env python3
"""
EXO v8 — SystemService (WebSocket)
Port 8783 — Informations système pour l'agent autonome

Fournit des infos système (CPU, RAM, disque, réseau, processus)
pour permettre à l'assistant de diagnostiquer des problèmes.

Protocol WebSocket :
  → {"action":"system_info"}
  ← {"ok":true,"data":{"cpu_percent":23.5,"ram_percent":65.2,"disk":{...},...}}

  → {"action":"system_processes","params":{"top_n":10}}
  ← {"ok":true,"data":{"processes":[...]}}

  → {"action":"system_network"}
  ← {"ok":true,"data":{"interfaces":[...],"connections":42}}
"""

import asyncio
import json
import logging
import os
import platform
import sys
from datetime import datetime
from pathlib import Path

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9

logging.basicConfig(level=logging.INFO, format="%(asctime)s [System] %(message)s")
log = logging.getLogger("system_service")

PORT = 8783


class SystemService:
    """System information service."""

    def system_info(self) -> dict:
        info = {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "hostname": platform.node(),
            "processor": platform.processor(),
            "architecture": platform.machine(),
            "timestamp": datetime.now().isoformat(),
        }

        if HAS_PSUTIL:
            info["cpu_percent"] = psutil.cpu_percent(interval=0.5)
            info["cpu_count"] = psutil.cpu_count()
            info["cpu_freq_mhz"] = (
                round(psutil.cpu_freq().current) if psutil.cpu_freq() else None
            )

            mem = psutil.virtual_memory()
            info["ram_total_gb"] = round(mem.total / (1024 ** 3), 1)
            info["ram_used_gb"] = round(mem.used / (1024 ** 3), 1)
            info["ram_percent"] = mem.percent

            disks = []
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disks.append({
                        "mountpoint": part.mountpoint,
                        "device": part.device,
                        "fstype": part.fstype,
                        "total_gb": round(usage.total / (1024 ** 3), 1),
                        "used_gb": round(usage.used / (1024 ** 3), 1),
                        "percent": usage.percent,
                    })
                except PermissionError:
                    pass
            info["disks"] = disks

            boot = datetime.fromtimestamp(psutil.boot_time())
            info["uptime"] = str(datetime.now() - boot).split(".")[0]

        return info

    def processes(self, top_n: int = 10) -> dict:
        if not HAS_PSUTIL:
            return {"processes": [], "error": "psutil not installed"}

        procs = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu_percent": round(info["cpu_percent"] or 0, 1),
                    "memory_percent": round(info["memory_percent"] or 0, 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Sort by CPU then memory
        procs.sort(key=lambda p: (p["cpu_percent"], p["memory_percent"]), reverse=True)
        return {"processes": procs[:top_n], "total": len(procs)}

    def network(self) -> dict:
        if not HAS_PSUTIL:
            return {"interfaces": [], "error": "psutil not installed"}

        interfaces = []
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()

        for name, addr_list in addrs.items():
            iface = {"name": name, "addresses": [], "is_up": False}
            if name in stats:
                iface["is_up"] = stats[name].isup
                iface["speed_mbps"] = stats[name].speed

            for addr in addr_list:
                if addr.family.name in ("AF_INET", "AF_INET6"):
                    iface["addresses"].append({
                        "family": addr.family.name,
                        "address": addr.address,
                    })

            if iface["addresses"]:
                interfaces.append(iface)

        net_io = psutil.net_io_counters()
        return {
            "interfaces": interfaces,
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "connections": len(psutil.net_connections()),
        }


# ─────────────────────────────────────────────────────
#  WebSocket Handler
# ─────────────────────────────────────────────────────

async def handle_client(ws, service: SystemService) -> None:
    log.info("System client connected")
    await ws.send(json.dumps({
        "type": "ready", "service": "system_service", "version": "v8",
        "has_psutil": HAS_PSUTIL,
    }))

    try:
        async for raw in ws:
            if not isinstance(raw, str):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action", msg.get("type", ""))
            params = msg.get("params", {})

            if action == "ping":
                await ws.send(json.dumps({"type": "pong"}))
                continue

            try:
                if action == "system_info":
                    data = service.system_info()
                    await ws.send(json.dumps({"ok": True, "data": data}))

                elif action == "system_processes":
                    data = service.processes(top_n=params.get("top_n", 10))
                    await ws.send(json.dumps({"ok": True, "data": data}))

                elif action == "system_network":
                    data = service.network()
                    await ws.send(json.dumps({"ok": True, "data": data}))

                else:
                    await ws.send(json.dumps({
                        "ok": False,
                        "error": f"Unknown action: {action}",
                    }))

            except Exception as e:
                log.error("System error: %s", e, exc_info=True)
                await ws.send(json.dumps({"ok": False, "error": "Erreur interne du service system"}))

    except Exception as e:
        log.error("System session error: %s", e)
    finally:
        log.info("System client disconnected")


async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="EXO v8 System Service")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    ensure_single_instance(args.port, "system_service")
    _v9 = init_v9("system_service", args.port)

    service = SystemService()
    log.info("SystemService initialized (psutil: %s)", HAS_PSUTIL)

    async def handler(ws):
        await handle_client(ws, service)

    server = await websockets.serve(
        handler, args.host, args.port,
        ping_interval=None, ping_timeout=None,
    )
    log.info("System Service running on ws://%s:%d", args.host, args.port)

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
