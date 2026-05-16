#!/usr/bin/env python3
"""
EXO Domotique v2 — EchoService (WebSocket) — Port 8789

Connecteur pour enceintes Amazon Echo (Alexa).
Utilise l'API locale ou le SDK Alexa Voice Service.
v2: capabilities, metadata.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

import websockets

from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9

log = logging.getLogger("echo_service")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s")

PORT = 8789

# Echo discovery config
ECHO_DEVICES_FILE = os.getenv(
    "EXO_ECHO_DEVICES",
    str(Path(__file__).resolve().parent.parent.parent / "config" / "echo_devices.json"),
)


class EchoService:
    """Connecteur enceintes Amazon Echo / Alexa."""

    def __init__(self) -> None:
        self._devices: dict[str, dict] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load discovered Echo devices from config file."""
        cfg = Path(ECHO_DEVICES_FILE)
        if cfg.exists():
            try:
                data = json.loads(cfg.read_text(encoding="utf-8"))
                for item in data if isinstance(data, list) else data.get("devices", []):
                    did = item.get("id", item.get("serial", ""))
                    self._devices[did] = {
                        "id_origin": f"echo:{did}",
                        "source": "echo",
                        "type": "speaker",
                        "name": item.get("name", "Echo"),
                        "capabilities": ["volume", "mute", "tts"],
                        "state": {
                            "on": True,
                            "volume": item.get("volume", 50),
                            "mute": False,
                        },
                        "ip": item.get("ip", ""),
                        "online": True,
                    }
                log.info("Loaded %d Echo devices from config", len(self._devices))
            except Exception as e:
                log.warning("Failed to load echo config: %s", e)

    def list_devices(self) -> list[dict]:
        """List known Echo devices."""
        return list(self._devices.values())

    async def get_state(self, device_id: str) -> dict | None:
        """Get Echo device state."""
        did = device_id.replace("echo:", "")
        dev = self._devices.get(did)
        if not dev:
            return None
        return {"id_origin": f"echo:{did}", "state": dev.get("state", {})}

    async def send_tts(self, device_id: str, text: str,
                       lang: str = "fr-FR") -> dict:
        """Send TTS announcement to an Echo device."""
        did = device_id.replace("echo:", "")
        dev = self._devices.get(did)
        if not dev:
            return {"ok": False, "error": "Appareil introuvable"}

        ip = dev.get("ip", "")
        if not ip:
            return {"ok": False, "error": "Aucune IP configurée pour l'appareil"}

        # Send via Echo's local API (Alexa HTTP proxy / ha-alexa-api)
        try:
            import aiohttp
            url = f"http://{ip}:8091/alexa/tts"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"text": text, "lang": lang},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        return {"ok": True, "spoken": text}
                    return {"ok": False, "error": f"HTTP {resp.status}"}
        except Exception as e:
            log.warning("Echo TTS fallback (no local API): %s", e)
            return {"ok": False, "error": "Impossible de contacter l'API locale Echo"}

    async def set_volume(self, device_id: str, volume: int) -> dict:
        """Set volume on Echo device."""
        did = device_id.replace("echo:", "")
        dev = self._devices.get(did)
        if not dev:
            return {"ok": False, "error": "Appareil introuvable"}

        dev["state"]["volume"] = max(0, min(100, volume))
        return {"ok": True, "state": dev["state"]}

    async def set_state(self, device_id: str, payload: dict) -> dict:
        """Generic state update."""
        did = device_id.replace("echo:", "")
        dev = self._devices.get(did)
        if not dev:
            return {"ok": False, "error": "Appareil introuvable"}

        if "volume" in payload:
            dev["state"]["volume"] = max(0, min(100, payload["volume"]))
        if "mute" in payload:
            dev["state"]["mute"] = bool(payload["mute"])
        return {"ok": True, "state": dev["state"]}

    async def apply_command(self, device_id: str, command: str,
                             **params) -> dict:
        if command == "tts":
            return await self.send_tts(device_id, params.get("text", ""), params.get("lang", "fr-FR"))
        elif command == "set_volume":
            return await self.set_volume(device_id, int(params.get("value", 50)))
        elif command == "mute":
            return await self.set_state(device_id, {"mute": True})
        elif command == "unmute":
            return await self.set_state(device_id, {"mute": False})
        return {"ok": False, "error": f"Unknown command: {command}"}

    def capabilities(self) -> list[str]:
        return ["list_devices", "get_state", "set_state", "send_tts",
                "set_volume", "apply_command", "capabilities", "metadata"]

    def metadata(self) -> dict:
        return {
            "name": "echo",
            "version": "v2",
            "backend": "alexa_local",
            "devices_count": len(self._devices),
        }


async def handle_client(ws, svc: EchoService) -> None:
    await ws.send(json.dumps({
        "type": "ready", "service": "echo", "version": "v2"
    }))
    try:
        async for raw in ws:
            if not isinstance(raw, str):
                continue
            msg = json.loads(raw)
            action = msg.get("action", msg.get("type", ""))
            params = msg.get("params", {})

            if action == "ping":
                await ws.send(json.dumps({"type": "pong"}))
                continue

            if action == "list_devices":
                devices = svc.list_devices()
                await ws.send(json.dumps({"ok": True, "data": {"devices": devices}}))

            elif action == "get_state":
                state = await svc.get_state(params.get("device_id", ""))
                if state:
                    await ws.send(json.dumps({"ok": True, "data": state}))
                else:
                    await ws.send(json.dumps({"ok": False, "error": "Introuvable"}))

            elif action == "set_state":
                result = await svc.set_state(
                    params.get("device_id", ""),
                    params.get("payload", {}),
                )
                await ws.send(json.dumps(result))

            elif action == "send_tts":
                result = await svc.send_tts(
                    params.get("device_id", ""),
                    params.get("text", ""),
                    params.get("lang", "fr-FR"),
                )
                await ws.send(json.dumps(result))

            elif action == "apply_command":
                result = await svc.apply_command(
                    params.get("device_id", ""),
                    params.get("command", ""),
                    **params.get("params", {}),
                )
                await ws.send(json.dumps(result))

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
    parser = argparse.ArgumentParser(description="EXO Echo Service")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    ensure_single_instance(args.port, "echo_service")
    _v9 = init_v9("echo_service", args.port)

    svc = EchoService()
    log.info("Echo devices loaded: %d", len(svc._devices))

    server = await websockets.serve(
        lambda ws: handle_client(ws, svc),
        args.host, args.port,
        ping_interval=None, ping_timeout=None,
    )
    log.info("EchoService on ws://%s:%d", args.host, args.port)
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
