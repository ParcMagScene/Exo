#!/usr/bin/env python3
"""
EXO Domotique v2 — CameraService (EZVIZ) (WebSocket) — Port 8786

Connecteur pour caméras EZVIZ.
Expose : list_cameras, get_snapshot, get_stream_url, capabilities, metadata.
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

log = logging.getLogger("camera_service")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s")

PORT = 8786

EZVIZ_APP_KEY = os.getenv("EXO_EZVIZ_APP_KEY", "")
EZVIZ_APP_SECRET = os.getenv("EXO_EZVIZ_APP_SECRET", "")
EZVIZ_ACCESS_TOKEN = os.getenv("EXO_EZVIZ_TOKEN", "")


class CameraService:
    """Connecteur caméras EZVIZ."""

    def __init__(self) -> None:
        self._cameras: dict[str, dict] = {}
        self._access_token = EZVIZ_ACCESS_TOKEN
        self._api_url = "https://open.ezvizlife.com/api"

    @property
    def configured(self) -> bool:
        return bool(self._access_token)

    async def _ezviz_post(self, endpoint: str, data: dict | None = None) -> dict | None:
        if not self.configured:
            return None
        try:
            import aiohttp
            url = f"{self._api_url}/{endpoint}"
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            form_data = {"accessToken": self._access_token}
            if data:
                form_data.update(data)
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=form_data,
                                        timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("code") == "200":
                            return result.get("data")
                    log.warning("EZVIZ %s → %d", endpoint, resp.status)
                    return None
        except Exception as e:
            log.error("EZVIZ error: %s", e)
            return None

    async def list_cameras(self) -> list[dict]:
        """List all EZVIZ cameras."""
        data = await self._ezviz_post("lapp/device/list")
        if not data:
            return list(self._cameras.values())

        cameras = []
        for dev in data:
            serial = dev.get("deviceSerial", "")
            cam = {
                "id_origin": f"ezviz:{serial}",
                "source": "ezviz",
                "type": "camera",
                "name": dev.get("deviceName", serial),
                "capabilities": ["on_off", "snapshot", "stream"],
                "state": {
                    "on": dev.get("status", 0) == 1,
                },
                "online": dev.get("status", 0) == 1,
                "ip": "",
                "mac": "",
            }
            cameras.append(cam)
            self._cameras[serial] = cam
        return cameras

    # Alias for HomeGraph integration
    async def list_devices(self) -> list[dict]:
        return await self.list_cameras()

    async def get_snapshot(self, camera_id: str) -> dict:
        """Get a snapshot URL for a camera."""
        serial = camera_id.replace("ezviz:", "")
        data = await self._ezviz_post("lapp/device/capture", {
            "deviceSerial": serial, "channelNo": "1",
        })
        if data:
            return {"ok": True, "url": data.get("picUrl", ""), "serial": serial}
        return {"ok": False, "error": "Snapshot failed"}

    async def get_stream_url(self, camera_id: str) -> dict:
        """Get RTSP/HLS stream URL."""
        serial = camera_id.replace("ezviz:", "")
        data = await self._ezviz_post("lapp/v2/live/address/get", {
            "deviceSerial": serial, "channelNo": "1",
            "protocol": "2", "quality": "1",
        })
        if data:
            return {"ok": True, "url": data.get("url", ""), "serial": serial}
        return {"ok": False, "error": "Stream URL failed"}

    async def apply_command(self, device_id: str, command: str,
                             **params) -> dict:
        """Apply command to camera."""
        if command == "snapshot":
            return await self.get_snapshot(device_id)
        elif command == "stream":
            return await self.get_stream_url(device_id)
        elif command == "turn_on":
            return {"ok": True, "state": {"on": True}}
        elif command == "turn_off":
            return {"ok": True, "state": {"on": False}}
        return {"ok": False, "error": f"Unknown command: {command}"}

    def capabilities(self) -> list[str]:
        return ["list_devices", "get_snapshot", "get_stream_url",
                "apply_command", "capabilities", "metadata"]

    def metadata(self) -> dict:
        return {
            "name": "camera",
            "version": "v2",
            "backend": "ezviz",
            "configured": self.configured,
            "cameras_count": len(self._cameras),
        }


async def handle_client(ws, svc: CameraService) -> None:
    await ws.send(json.dumps({
        "type": "ready", "service": "camera", "version": "v2"
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

            if action in ("list_cameras", "list_devices"):
                cameras = await svc.list_cameras()
                await ws.send(json.dumps({"ok": True, "data": {"devices": cameras}}))

            elif action == "get_snapshot":
                result = await svc.get_snapshot(params.get("camera_id", ""))
                await ws.send(json.dumps(result))

            elif action == "get_stream_url":
                result = await svc.get_stream_url(params.get("camera_id", ""))
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
    parser = argparse.ArgumentParser(description="EXO Camera Service (EZVIZ)")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    ensure_single_instance(args.port, "camera_service")
    _v9 = init_v9("camera_service", args.port)

    svc = CameraService()
    log.info("EZVIZ configured: %s", svc.configured)

    server = await websockets.serve(
        lambda ws: handle_client(ws, svc),
        args.host, args.port,
        ping_interval=None, ping_timeout=None,
    )
    log.info("CameraService on ws://%s:%d", args.host, args.port)
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
