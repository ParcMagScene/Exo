#!/usr/bin/env python3
"""
EXO Domotique v2 — DomoticService (WebSocket) — Port 8785

Connecteur générique pour équipements domotiques.
Se connecte à Home Assistant REST API si configuré, sinon expose une
interface stub pour les connecteurs directs (HUE, Tapo, IKEA, TP-Link).

v2: capabilities(), metadata(), timeouts, retry, métriques, traces.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import aiohttp
import websockets

from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9

log = logging.getLogger("domotic_service")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s")

PORT = 8785

# Home Assistant config
HA_URL = os.getenv("EXO_HA_URL", "")         # e.g. http://homeassistant.local:8123
HA_TOKEN = os.getenv("EXO_HA_TOKEN", "")      # Long-lived access token


class DomoticService:
    """Couche d'abstraction domotique (Home Assistant ou direct)."""

    def __init__(self) -> None:
        self._ha_url = HA_URL.rstrip("/") if HA_URL else ""
        self._ha_token = HA_TOKEN
        self._cache: dict[str, dict] = {}  # entity_id → state dict
        self._areas: list[dict] = []
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return persistent HTTP session, creating it on first use."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Release HTTP session resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    @property
    def has_ha(self) -> bool:
        return bool(self._ha_url and self._ha_token)

    # ── Home Assistant REST API ─────────────────────

    async def _ha_get(self, endpoint: str) -> dict | list | None:
        if not self.has_ha:
            return None
        try:
            url = f"{self._ha_url}/api/{endpoint}"
            headers = {
                "Authorization": f"Bearer {self._ha_token}",
                "Content-Type": "application/json",
            }
            session = await self._get_session()
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                log.warning("HA GET %s → %d", endpoint, resp.status)
                return None
        except Exception as e:
            log.error("HA request error: %s", e)
            return None

    async def _ha_post(self, endpoint: str, data: dict) -> dict | None:
        if not self.has_ha:
            return None
        try:
            url = f"{self._ha_url}/api/{endpoint}"
            headers = {
                "Authorization": f"Bearer {self._ha_token}",
                "Content-Type": "application/json",
            }
            session = await self._get_session()
            async with session.post(url, headers=headers, json=data,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status in (200, 201):
                    return await resp.json()
                log.warning("HA POST %s → %d", endpoint, resp.status)
                return None
        except Exception as e:
            log.error("HA POST error: %s", e)
            return None

    # ── Device mapping ──────────────────────────────

    def _ha_entity_to_device(self, entity: dict) -> dict:
        """Convert HA entity to EXO device format."""
        eid = entity.get("entity_id", "")
        attrs = entity.get("attributes", {})
        state = entity.get("state", "unavailable")

        # Determine source from entity domain
        source = "other"
        if "hue" in eid or "hue" in attrs.get("friendly_name", "").lower():
            source = "hue"
        elif "tapo" in eid:
            source = "tapo"
        elif "ikea" in eid or "tradfri" in eid:
            source = "ikea"

        # Determine type
        domain = eid.split(".")[0] if "." in eid else ""
        type_map = {
            "light": "light",
            "switch": "plug",
            "camera": "camera",
            "media_player": "speaker",
            "climate": "heater",
            "sensor": "sensor",
            "cover": "unknown",
        }
        dtype = type_map.get(domain, "unknown")

        # Capabilities
        caps = ["on_off"]
        if domain == "light":
            if attrs.get("supported_color_modes"):
                modes = attrs["supported_color_modes"]
                if "brightness" in modes or "color_temp" in modes or "xy" in modes or "hs" in modes:
                    caps.append("brightness")
                if "xy" in modes or "hs" in modes or "rgb" in modes:
                    caps.append("color")
                if "color_temp" in modes:
                    caps.append("temp")
        elif domain == "media_player":
            caps.extend(["volume", "source", "mute"])
        elif domain == "climate":
            caps.extend(["temp", "mode"])
        elif domain == "camera":
            caps.extend(["snapshot", "stream"])

        # State dict
        dev_state = {"on": state not in ("off", "unavailable", "unknown")}
        if "brightness" in attrs:
            dev_state["brightness"] = round(attrs["brightness"] / 255 * 100)
        if "color_temp" in attrs:
            dev_state["color_temp"] = attrs["color_temp"]
        if "rgb_color" in attrs:
            dev_state["color"] = attrs["rgb_color"]
        if "volume_level" in attrs:
            dev_state["volume"] = round(attrs["volume_level"] * 100)
        if "temperature" in attrs:
            dev_state["temp"] = attrs["temperature"]
        if "source" in attrs:
            dev_state["source"] = attrs["source"]

        return {
            "id_origin": f"ha:{eid}",
            "source": source,
            "type": dtype,
            "name": attrs.get("friendly_name", eid),
            "room_id": attrs.get("area_id", ""),
            "capabilities": caps,
            "state": dev_state,
            "online": state != "unavailable",
        }

    # ── Public API ──────────────────────────────────

    async def list_devices(self) -> list[dict]:
        """List all devices from HA or cache."""
        if self.has_ha:
            states = await self._ha_get("states")
            if states:
                devices = []
                for entity in states:
                    eid = entity.get("entity_id", "")
                    domain = eid.split(".")[0]
                    if domain in ("light", "switch", "camera", "media_player",
                                  "climate", "sensor", "cover"):
                        dev = self._ha_entity_to_device(entity)
                        devices.append(dev)
                        self._cache[eid] = entity
                return devices
        return list(self._cache.values())

    async def get_state(self, device_id: str) -> dict | None:
        """Get state of a specific device."""
        if self.has_ha:
            # device_id is ha:light.xxx → extract entity_id
            eid = device_id.replace("ha:", "") if device_id.startswith("ha:") else device_id
            entity = await self._ha_get(f"states/{eid}")
            if entity:
                return self._ha_entity_to_device(entity)
        return None

    async def set_state(self, device_id: str, payload: dict) -> dict:
        """Set state of a device via HA services."""
        eid = device_id.replace("ha:", "") if device_id.startswith("ha:") else device_id
        domain = eid.split(".")[0] if "." in eid else ""

        if not self.has_ha:
            return {"ok": False, "error": "Home Assistant not configured"}

        # Determine HA service call
        if "on" in payload:
            service = f"{domain}/turn_{'on' if payload['on'] else 'off'}"
        else:
            service = f"{domain}/turn_on"  # most set operations require on state

        service_data = {"entity_id": eid}

        if "brightness" in payload:
            service_data["brightness"] = int(payload["brightness"] * 255 / 100)
        if "color" in payload:
            service_data["rgb_color"] = payload["color"]
        if "color_temp" in payload:
            service_data["color_temp"] = payload["color_temp"]
        if "temp" in payload:
            service_data["temperature"] = payload["temp"]
        if "volume" in payload:
            service_data["volume_level"] = payload["volume"] / 100

        result = await self._ha_post(f"services/{service}", service_data)
        if result is not None:
            return {"ok": True, "state": payload}
        return {"ok": False, "error": "HA service call failed"}

    async def list_areas(self) -> list[dict]:
        """List HA areas (rooms)."""
        if not self.has_ha:
            return []
        # HA areas are accessible via WS API, not REST. Use config endpoint.
        config = await self._ha_get("config")
        if config:
            # Areas not directly in config REST, return empty
            return self._areas
        return []

    async def apply_command(self, device_id: str, command: str,
                             **params) -> dict:
        """Apply a high-level command to a device."""
        cmd_map = {
            "turn_on":  {"on": True},
            "turn_off": {"on": False},
            "set_brightness": {"on": True, "brightness": params.get("value", 100)},
            "set_color": {"on": True, "color": params.get("value", [255, 255, 255])},
            "set_temp": {"temp": params.get("value", 20)},
            "set_volume": {"volume": params.get("value", 50)},
        }
        payload = cmd_map.get(command, params)
        return await self.set_state(device_id, payload)

    # ── v2 additions ──────────────────────────────────

    def capabilities(self) -> list[str]:
        """Capacités du service."""
        return ["list_devices", "get_state", "set_state", "apply_command",
                "list_areas", "capabilities", "metadata"]

    def metadata(self) -> dict:
        """Métadonnées du service."""
        return {
            "name": "domotic",
            "version": "v2",
            "backend": "home_assistant" if self.has_ha else "stub",
            "ha_url": self._ha_url or None,
            "cached_entities": len(self._cache),
        }


# ═══════════════════════════════════════════════════════
#  WebSocket Handler
# ═══════════════════════════════════════════════════════

async def handle_client(ws, svc: DomoticService) -> None:
    await ws.send(json.dumps({
        "type": "ready", "service": "domotic", "version": "v2"
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
                    await ws.send(json.dumps({"ok": False, "error": "Device not found"}))

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

            elif action == "list_areas":
                areas = await svc.list_areas()
                await ws.send(json.dumps({"ok": True, "data": {"rooms": areas}}))

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
    parser = argparse.ArgumentParser(description="EXO Domotic Service")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    ensure_single_instance(args.port, "domotic_service")
    _v9 = init_v9("domotic_service", args.port)

    svc = DomoticService()
    if svc.has_ha:
        log.info("Home Assistant configured: %s", svc._ha_url)
    else:
        log.info("No Home Assistant — running in stub mode")

    server = await websockets.serve(
        lambda ws: handle_client(ws, svc),
        args.host, args.port,
        ping_interval=None, ping_timeout=None,
    )
    log.info("DomoticService on ws://%s:%d", args.host, args.port)
    try:
        await asyncio.Future()
    finally:
        await svc.close()


if __name__ == "__main__":
    asyncio.run(main())
