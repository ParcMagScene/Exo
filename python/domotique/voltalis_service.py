#!/usr/bin/env python3
"""

# Patch global EXO : forcer le working directory à D:/EXO/ pour tous les services
import os
os.chdir("D:/EXO/")
EXO Domotique v2 — VoltalisService (WebSocket) — Port 8788

Connecteur pour appareils Voltalis (radiateurs éco-pilotés).
Utilise l'API REST Voltalis (ou stub si non configuré).
v2: capabilities, metadata, energy tracking.
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

log = logging.getLogger("voltalis_service")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s")

PORT = 8788

VOLTALIS_EMAIL = os.getenv("EXO_VOLTALIS_EMAIL", "")
VOLTALIS_PASS = os.getenv("EXO_VOLTALIS_PASS", "")
VOLTALIS_API = "https://api.voltalis.com"


class VoltalisService:
    """Connecteur radiateurs Voltalis éco-pilotés."""

    def __init__(self) -> None:
        self._email = VOLTALIS_EMAIL
        self._password = VOLTALIS_PASS
        self._token: str | None = None
        self._token_expiry: float = 0
        self._devices: dict[str, dict] = {}

    @property
    def configured(self) -> bool:
        return bool(self._email and self._password)

    async def _auth(self) -> str | None:
        """Authenticate and return session token."""
        if self._token and time.time() < self._token_expiry:
            return self._token
        if not self.configured:
            return None
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{VOLTALIS_API}/auth/login",
                    json={"email": self._email, "password": self._password},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._token = data.get("token", "")
                        self._token_expiry = time.time() + 3500
                        return self._token
        except Exception as e:
            log.error("Voltalis auth error: %s", e)
        return None

    async def _api_get(self, endpoint: str) -> dict | None:
        token = await self._auth()
        if not token:
            return None
        try:
            import aiohttp
            headers = {"Authorization": f"Bearer {token}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{VOLTALIS_API}/{endpoint}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            log.error("Voltalis GET error: %s", e)
        return None

    async def _api_post(self, endpoint: str, data: dict) -> dict | None:
        token = await self._auth()
        if not token:
            return None
        try:
            import aiohttp
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{VOLTALIS_API}/{endpoint}",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status in (200, 201):
                        return await resp.json()
        except Exception as e:
            log.error("Voltalis POST error: %s", e)
        return None

    async def list_devices(self) -> list[dict]:
        """List Voltalis heater modulators."""
        data = await self._api_get("modulators")
        if not data:
            return list(self._devices.values())

        devices = []
        for item in data if isinstance(data, list) else data.get("modulators", []):
            mid = str(item.get("id", ""))
            name = item.get("name", "Voltalis")
            mode = item.get("mode", "auto")
            temp = item.get("temperature")
            consumption = item.get("consumption")

            dev = {
                "id_origin": f"voltalis:{mid}",
                "source": "voltalis",
                "type": "heater",
                "name": name,
                "capabilities": ["mode", "temp", "energy"],
                "state": {
                    "mode": mode,
                    "temperature": temp,
                    "consumption_wh": consumption,
                    "on": mode != "off",
                },
                "online": True,
            }
            devices.append(dev)
            self._devices[mid] = dev
        return devices

    async def get_state(self, device_id: str) -> dict | None:
        """Get modulator state."""
        mid = device_id.replace("voltalis:", "")
        data = await self._api_get(f"modulators/{mid}")
        if not data:
            return self._devices.get(mid)
        return {
            "id_origin": f"voltalis:{mid}",
            "state": {
                "mode": data.get("mode", "auto"),
                "temperature": data.get("temperature"),
                "consumption_wh": data.get("consumption"),
                "on": data.get("mode", "auto") != "off",
            },
        }

    async def get_consumption(self, device_id: str,
                               period: str = "day") -> dict | None:
        """Get energy consumption data."""
        mid = device_id.replace("voltalis:", "")
        data = await self._api_get(f"modulators/{mid}/consumption?period={period}")
        if data:
            return {"id_origin": f"voltalis:{mid}", "consumption": data}
        return None

    async def set_mode(self, device_id: str, mode: str) -> dict:
        """Set heater mode (auto, comfort, eco, anti_freeze, off)."""
        mid = device_id.replace("voltalis:", "")
        result = await self._api_post(
            f"modulators/{mid}/mode", {"mode": mode}
        )
        if result is not None:
            return {"ok": True, "state": {"mode": mode, "on": mode != "off"}}
        return {"ok": False, "error": "Échec de la définition du mode"}

    async def apply_command(self, device_id: str, command: str,
                             **params) -> dict:
        cmd_map = {
            "set_mode": lambda: self.set_mode(device_id, params.get("value", "auto")),
            "turn_on": lambda: self.set_mode(device_id, "auto"),
            "turn_off": lambda: self.set_mode(device_id, "off"),
            "set_eco": lambda: self.set_mode(device_id, "eco"),
            "set_comfort": lambda: self.set_mode(device_id, "comfort"),
            "set_anti_freeze": lambda: self.set_mode(device_id, "anti_freeze"),
        }
        handler = cmd_map.get(command)
        if handler:
            return await handler()
        return {"ok": False, "error": f"Unknown command: {command}"}

    def capabilities(self) -> list[str]:
        return ["list_devices", "get_state", "set_mode", "get_consumption",
                "apply_command", "capabilities", "metadata"]

    def metadata(self) -> dict:
        return {
            "name": "voltalis",
            "version": "v2",
            "backend": "voltalis_api",
            "configured": self.configured,
            "devices_count": len(self._devices),
        }


async def handle_client(ws, svc: VoltalisService) -> None:
    await ws.send(json.dumps({
        "type": "ready", "service": "voltalis", "version": "v2"
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
                    await ws.send(json.dumps({"ok": False, "error": "Introuvable"}))

            elif action == "set_mode":
                result = await svc.set_mode(
                    params.get("device_id", ""),
                    params.get("mode", "auto"),
                )
                await ws.send(json.dumps(result))

            elif action == "get_consumption":
                result = await svc.get_consumption(
                    params.get("device_id", ""),
                    params.get("period", "day"),
                )
                if result:
                    await ws.send(json.dumps({"ok": True, "data": result}))
                else:
                    await ws.send(json.dumps({"ok": False, "error": "Non disponible"}))

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
    parser = argparse.ArgumentParser(description="EXO Voltalis Service")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    ensure_single_instance(args.port, "voltalis_service")
    _v9 = init_v9("voltalis_service", args.port)

    svc = VoltalisService()
    log.info("Voltalis configured: %s", svc.configured)

    server = await websockets.serve(
        lambda ws: handle_client(ws, svc),
        args.host, args.port,
        ping_interval=None, ping_timeout=None,
    )
    log.info("VoltalisService on ws://%s:%d", args.host, args.port)
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
