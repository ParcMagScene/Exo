#!/usr/bin/env python3
"""
EXO NetworkMap v2 — NetworkMapService (WebSocket) — Port 8790

Moteur réseau complet : ARP + mDNS + SSDP + Ping.
Topologie, classification, vendor lookup, latence, résilience.
Intégration EXO v9 (logs, métriques, traces, superviseur, sécurité).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import websockets

from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9

from network.network_map_manager import NetworkMapManager

log = logging.getLogger("network_map_service")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s")

PORT = 8790

OUI_FILE = os.getenv(
    "EXO_OUI_FILE",
    str(Path(__file__).resolve().parent.parent.parent / "config" / "oui.txt"),
)


class NetworkMapService:
    """Service WebSocket NetworkMap v2 — orchestre le NetworkMapManager."""

    def __init__(self, v9=None) -> None:
        self._mgr = NetworkMapManager(oui_path=OUI_FILE, v9=v9)
        self._v9 = v9

    # ── Delegate to manager ──────────────────────────

    async def scan(self) -> dict:
        """Scan complet (ARP+mDNS+SSDP+Ping+topologie)."""
        return await self._mgr.scan_full()

    async def scan_fast(self) -> dict:
        """Scan rapide (ARP+vendor+classification)."""
        return await self._mgr.scan_fast()

    def list_nodes(self) -> list[dict]:
        return self._mgr.get_devices()

    def list_links(self) -> list[dict]:
        return self._mgr.get_links()

    def get_node_details(self, identifier: str) -> dict | None:
        """Get node by IP or MAC."""
        dev = self._mgr.get_device(identifier)
        if dev:
            return dev
        # Fallback: search by MAC
        for d in self._mgr.get_devices():
            if d.get("mac") == identifier:
                return d
        return None

    def get_topology(self) -> dict:
        return self._mgr.get_topology()

    def get_vendor(self, mac: str) -> str:
        return self._mgr.get_vendor(mac)

    def get_latency(self, ip: str) -> float | None:
        return self._mgr.get_latency(ip)

    def classify_device(self, device: dict) -> str:
        return self._mgr.classify_device(device)

    def export_json(self) -> str:
        return self._mgr.export_json()

    def health_check(self) -> dict:
        return self._mgr.health_check()

    def restart(self) -> dict:
        return self._mgr.restart()

    def capabilities(self) -> list[str]:
        return self._mgr.capabilities()

    def metadata(self) -> dict:
        return self._mgr.metadata()

    def get_metrics(self) -> dict:
        return self._mgr.get_metrics()


async def handle_client(ws, svc: NetworkMapService) -> None:
    await ws.send(json.dumps({
        "type": "ready", "service": "network_map", "version": "v2"
    }))
    try:
        async for raw in ws:
            if not isinstance(raw, str):
                continue
            try:
                msg = json.loads(raw)
            except (ValueError, TypeError) as e:
                log.warning("network_map: invalid JSON dropped (%s): %.80s", e, raw)
                continue
            action = msg.get("action", msg.get("type", ""))
            params = msg.get("params", {})

            if action == "ping":
                await ws.send(json.dumps({"type": "pong"}))
                continue

            # v9 protocol
            if svc._v9:
                v9_resp = await svc._v9.handle_ws_message(ws, raw)
                if v9_resp:
                    await ws.send(v9_resp)
                    continue

            if action == "scan":
                result = await svc.scan()
                await ws.send(json.dumps({"ok": True, "data": result}, default=str))

            elif action == "scan_fast":
                result = await svc.scan_fast()
                await ws.send(json.dumps({"ok": True, "data": result}, default=str))

            elif action == "list_nodes":
                nodes = svc.list_nodes()
                await ws.send(json.dumps({"ok": True, "data": {"nodes": nodes}}, default=str))

            elif action == "list_links":
                links = svc.list_links()
                await ws.send(json.dumps({"ok": True, "data": {"links": links}}, default=str))

            elif action == "get_node":
                node = svc.get_node_details(params.get("id", ""))
                if node:
                    await ws.send(json.dumps({"ok": True, "data": node}, default=str))
                else:
                    await ws.send(json.dumps({"ok": False, "error": "Introuvable"}))

            elif action == "get_topology":
                topo = svc.get_topology()
                await ws.send(json.dumps({"ok": True, "data": topo}, default=str))

            elif action == "get_vendor":
                mac = params.get("mac", "")
                vendor = svc.get_vendor(mac)
                await ws.send(json.dumps({"ok": True, "data": {"vendor": vendor}}))

            elif action == "get_latency":
                ip = params.get("ip", "")
                latency = svc.get_latency(ip)
                await ws.send(json.dumps({"ok": True, "data": {"latency_ms": latency}}))

            elif action == "classify":
                device = params.get("device", {})
                dtype = svc.classify_device(device)
                await ws.send(json.dumps({"ok": True, "data": {"type": dtype}}))

            elif action == "export":
                data = svc.export_json()
                await ws.send(json.dumps({"ok": True, "data": json.loads(data)}, default=str))

            elif action == "health":
                await ws.send(json.dumps({"ok": True, "data": svc.health_check()}))

            elif action == "restart":
                result = svc.restart()
                await ws.send(json.dumps({"ok": True, "data": result}))

            elif action == "metrics":
                await ws.send(json.dumps({"ok": True, "data": svc.get_metrics()}))

            elif action == "capabilities":
                await ws.send(json.dumps({"ok": True, "data": svc.capabilities()}))

            elif action == "metadata":
                await ws.send(json.dumps({"ok": True, "data": svc.metadata()}))

            else:
                await ws.send(json.dumps({"ok": False, "error": f"Unknown: {action}"}))

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        log.error("Handler error: %s", e)


async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="EXO NetworkMap v2 Service")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    ensure_single_instance(args.port, "network_map_service")
    _v9 = init_v9("network_map_service", args.port)

    svc = NetworkMapService(v9=_v9)
    log.info("NetworkMap v2 ready — OUI entries: %d", svc.metadata().get("oui_entries", 0))

    server = await websockets.serve(
        lambda ws: handle_client(ws, svc),
        args.host, args.port,
        ping_interval=None, ping_timeout=None,
    )
    log.info("NetworkMapService v2 on ws://%s:%d", args.host, args.port)
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
