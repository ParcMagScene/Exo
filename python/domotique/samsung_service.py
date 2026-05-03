#!/usr/bin/env python3
"""
EXO Domotique v2 — SamsungService (WebSocket) — Port 8787

Connecteur pour appareils Samsung (TV, soundbar).
Utilise l'API locale Samsung SmartThings ou Wake-on-LAN.
v2: capabilities, metadata, events.
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

log = logging.getLogger("samsung_service")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s")

PORT = 8787

# Samsung SmartThings config
ST_TOKEN = os.getenv("EXO_SMARTTHINGS_TOKEN", "")
ST_API = "https://api.smartthings.com/v1"


class SamsungService:
    """Connecteur appareils Samsung (TV, soundbar, etc.)."""

    def __init__(self) -> None:
        self._token = ST_TOKEN
        self._devices: dict[str, dict] = {}

    @property
    def configured(self) -> bool:
        return bool(self._token)

    async def _st_get(self, endpoint: str) -> dict | None:
        if not self.configured:
            return None
        try:
            import aiohttp
            url = f"{ST_API}/{endpoint}"
            headers = {"Authorization": f"Bearer {self._token}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers,
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return None
        except Exception as e:
            log.error("SmartThings error: %s", e)
            return None

    async def _st_post(self, endpoint: str, data: dict) -> dict | None:
        if not self.configured:
            return None
        try:
            import aiohttp
            url = f"{ST_API}/{endpoint}"
            headers = {
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data,
                                        timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status in (200, 201):
                        return await resp.json()
                    return None
        except Exception as e:
            log.error("SmartThings POST error: %s", e)
            return None

    async def list_devices(self) -> list[dict]:
        """List Samsung devices via SmartThings."""
        data = await self._st_get("devices")
        if not data:
            return list(self._devices.values())

        devices = []
        for item in data.get("items", []):
            did = item.get("deviceId", "")
            label = item.get("label", item.get("name", "Samsung"))
            # Detect type
            categories = [c.get("name", "") for c in item.get("categories", [])]
            dtype = "unknown"
            caps = ["on_off"]
            if "Television" in categories or "TV" in categories:
                dtype = "tv"
                caps.extend(["volume", "source", "mute"])
            elif "Speaker" in categories or "Soundbar" in categories:
                dtype = "soundbar"
                caps.extend(["volume", "source", "mute"])

            dev = {
                "id_origin": f"samsung:{did}",
                "source": "samsung",
                "type": dtype,
                "name": label,
                "capabilities": caps,
                "state": {"on": True},
                "online": item.get("status", "") == "ONLINE",
            }
            devices.append(dev)
            self._devices[did] = dev
        return devices

    async def get_state(self, device_id: str) -> dict | None:
        """Get device status."""
        did = device_id.replace("samsung:", "")
        data = await self._st_get(f"devices/{did}/status")
        if not data:
            return None
        # Parse components
        main_comp = data.get("components", {}).get("main", {})
        state = {"on": True}
        # Switch
        switch = main_comp.get("switch", {}).get("switch", {})
        if switch.get("value"):
            state["on"] = switch["value"] == "on"
        # Volume
        vol = main_comp.get("audioVolume", {}).get("volume", {})
        if vol.get("value") is not None:
            state["volume"] = vol["value"]
        # Mute
        mute = main_comp.get("audioMute", {}).get("mute", {})
        if mute.get("value"):
            state["mute"] = mute["value"] == "muted"
        # Input source
        src = main_comp.get("mediaInputSource", {}).get("inputSource", {})
        if src.get("value"):
            state["source"] = src["value"]

        return {"id_origin": f"samsung:{did}", "state": state}

    async def set_state(self, device_id: str, payload: dict) -> dict:
        """Send command to Samsung device."""
        did = device_id.replace("samsung:", "")

        commands = []
        if "on" in payload:
            commands.append({
                "component": "main",
                "capability": "switch",
                "command": "on" if payload["on"] else "off",
            })
        if "volume" in payload:
            commands.append({
                "component": "main",
                "capability": "audioVolume",
                "command": "setVolume",
                "arguments": [payload["volume"]],
            })
        if "mute" in payload:
            commands.append({
                "component": "main",
                "capability": "audioMute",
                "command": "mute" if payload["mute"] else "unmute",
            })
        if "source" in payload:
            commands.append({
                "component": "main",
                "capability": "mediaInputSource",
                "command": "setInputSource",
                "arguments": [payload["source"]],
            })

        if not commands:
            return {"ok": False, "error": "No valid commands"}

        result = await self._st_post(f"devices/{did}/commands", {"commands": commands})
        if result is not None:
            return {"ok": True, "state": payload}
        return {"ok": False, "error": "Command failed"}

    async def apply_command(self, device_id: str, command: str,
                             **params) -> dict:
        cmd_map = {
            "turn_on": {"on": True},
            "turn_off": {"on": False},
            "set_volume": {"volume": params.get("value", 30)},
            "set_source": {"source": params.get("value", "HDMI1")},
            "mute": {"mute": True},
            "unmute": {"mute": False},
        }
        payload = cmd_map.get(command, params)
        return await self.set_state(device_id, payload)

    def capabilities(self) -> list[str]:
        return ["list_devices", "get_state", "set_state", "apply_command",
                "capabilities", "metadata"]

    def metadata(self) -> dict:
        return {
            "name": "samsung",
            "version": "v2",
            "backend": "smartthings",
            "configured": self.configured,
            "devices_count": len(self._devices),
        }


async def handle_client(ws, svc: SamsungService) -> None:
    await ws.send(json.dumps({
        "type": "ready", "service": "samsung", "version": "v2"
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
                devices = await svc.list_devices()
                await ws.send(json.dumps({"ok": True, "data": {"devices": devices}}))

            elif action == "get_state":
                state = await svc.get_state(params.get("device_id", ""))
                if state:
                    await ws.send(json.dumps({"ok": True, "data": state}))
                else:
                    await ws.send(json.dumps({"ok": False, "error": "Not found"}))

            elif action == "set_state":
                result = await svc.set_state(
                    params.get("device_id", ""),
                    params.get("payload", {}),
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
    parser = argparse.ArgumentParser(description="EXO Samsung Service")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    ensure_single_instance(args.port, "samsung_service")
    _v9 = init_v9("samsung_service", args.port)

    svc = SamsungService()
    log.info("SmartThings configured: %s", svc.configured)

    server = await websockets.serve(
        lambda ws: handle_client(ws, svc),
        args.host, args.port,
        ping_interval=None, ping_timeout=None,
    )
    log.info("SamsungService on ws://%s:%d", args.host, args.port)
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
