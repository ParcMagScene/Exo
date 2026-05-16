#!/usr/bin/env python3
"""
EXO Domotique v2 — HomeGraphManager (WebSocket) — Port 8784

Modèle unifié de la maison : appareils, pièces, liens réseau.
Fusionne les données des services d'intégration (Domotic, Camera, Samsung,
Voltalis, Echo) et du NetworkMap.

v2: DomoticCache, DiscoveryManager, EventManager, ScenarioManager,
    capabilities/metadata, refresh par device, list_by_type, get_vendor.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

import websockets

from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9

from domotique.models import (
    Capability, Device, DeviceSource, DeviceType,
    Link, LinkType, Room,
)
from domotique.domotic_cache import DomoticCache
from domotique.event_manager import EventManager
from domotique.scenario_manager import ScenarioManager
from domotique.discovery_manager import DiscoveryManager

log = logging.getLogger("homegraph")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s")

PORT = 8784

# Timeouts pour les connecteurs (secondes)
CONNECTOR_TIMEOUT = 10


class HomeGraphManager:
    """Modèle unifié de la maison connectée — v2."""

    def __init__(self) -> None:
        self._devices: dict[str, Device] = {}
        self._rooms: dict[str, Room] = {}
        self._links: list[Link] = []
        self._connector_urls: dict[str, str] = {
            "domotic":  os.getenv("EXO_DOMOTIC_URL", "ws://localhost:8785"),
            "camera":   os.getenv("EXO_CAMERA_URL", "ws://localhost:8786"),
            "samsung":  os.getenv("EXO_SAMSUNG_URL", "ws://localhost:8787"),
            "voltalis": os.getenv("EXO_VOLTALIS_URL", "ws://localhost:8788"),
            "echo":     os.getenv("EXO_ECHO_URL", "ws://localhost:8789"),
            "network":  os.getenv("EXO_NETWORK_URL", "ws://localhost:8790"),
        }
        # v2 modules
        self._cache = DomoticCache(default_ttl=30.0)
        self._events = EventManager()
        self._scenarios = ScenarioManager()
        self._discovery = DiscoveryManager()

        # Wire scenario executor to apply_command
        self._scenarios.set_executor(self._scenario_executor)

    async def _scenario_executor(self, device_id: str, command: str,
                                  **params: object) -> dict:
        """Executor pour le ScenarioManager."""
        return await self.apply_command(device_id, command, params)

    # ── Public API ──────────────────────────────────

    def list_devices(self) -> list[dict]:
        return [d.to_dict() for d in self._devices.values()]

    def list_devices_by_room(self, room_id: str) -> list[dict]:
        room = self._rooms.get(room_id)
        if not room:
            return []
        return [
            self._devices[did].to_dict()
            for did in room.device_ids
            if did in self._devices
        ]

    def list_rooms(self) -> list[dict]:
        return [r.to_dict() for r in self._rooms.values()]

    def get_device(self, id_exo: str) -> dict | None:
        dev = self._devices.get(id_exo)
        return dev.to_dict() if dev else None

    def update_device_state(self, id_exo: str, new_state: dict) -> bool:
        dev = self._devices.get(id_exo)
        if not dev:
            return False
        old_state = dict(dev.state)
        dev.state.update(new_state)
        dev.last_seen = time.time()
        # v2: update cache + emit event
        self._cache.set_state(id_exo, dev.state)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._events.on_event(id_exo, dev.state))
        except RuntimeError:
            pass  # no running loop (sync context)
        return True

    def get_network_links(self) -> list[dict]:
        return [lnk.to_dict() for lnk in self._links]

    def find_device_by_name(self, name: str) -> list[dict]:
        """Recherche fuzzy par nom (case-insensitive substring)."""
        q = name.lower()
        return [
            d.to_dict() for d in self._devices.values()
            if q in d.name.lower()
        ]

    def find_devices_by_type(self, device_type: str) -> list[dict]:
        """Recherche par type d'appareil."""
        try:
            dt = DeviceType(device_type)
        except ValueError:
            return []
        return [d.to_dict() for d in self._devices.values() if d.type == dt]

    # ── v2 API ──────────────────────────────────────

    def list_devices_by_type(self, device_type: str) -> list[dict]:
        """Alias v2 pour find_devices_by_type."""
        return self.find_devices_by_type(device_type)

    def get_capabilities(self, id_exo: str) -> list[str] | None:
        """Retourne les capabilities d'un device."""
        dev = self._devices.get(id_exo)
        if not dev:
            return None
        return [c.value for c in dev.capabilities]

    def get_vendor(self, id_exo: str) -> str | None:
        """Retourne le vendor d'un device."""
        dev = self._devices.get(id_exo)
        if not dev:
            return None
        return dev.vendor

    def get_cache_stats(self) -> dict:
        """Retourne les stats du cache domotique."""
        return self._cache.stats()

    def get_event_stats(self) -> dict:
        """Retourne les stats de l'EventManager."""
        return self._events.stats()

    def list_scenarios(self) -> list[dict]:
        """Retourne la liste des scénarios disponibles."""
        return self._scenarios.list_scenarios()

    async def run_scenario(self, name: str, devices: list[str] | None = None) -> dict:
        """Exécute un scénario."""
        return await self._scenarios.run_scenario(name, devices or list(self._devices.keys()))

    async def run_discovery(self) -> dict:
        """Lance un scan réseau complet via le DiscoveryManager."""
        return await self._discovery.full_scan()

    async def run_network_scan(self) -> dict:
        """Lance un scan réseau complet via NetworkMap v2 (connecteur WS)."""
        resp = await self._query_connector("network", "scan")
        if resp and resp.get("ok"):
            data = resp.get("data", {})
            # Merge topology nodes
            devices = data.get("devices", [])
            if devices:
                self.merge_devices("network", devices)
            # Merge topology links
            topo = data.get("topology", {})
            links = topo.get("links", [])
            if links:
                self.merge_links(links)
            return {"ok": True, "data": data}
        return {"ok": False, "error": "Network scan unreachable"}

    def get_network_topology(self) -> dict:
        """Retourne la topologie réseau depuis la dernière intégration."""
        return {
            "links": [lnk.to_dict() for lnk in self._links],
            "devices_count": len(self._devices),
        }

    async def refresh_device(self, id_exo: str) -> dict:
        """Refresh un device individuel via son connecteur."""
        dev = self._devices.get(id_exo)
        if not dev:
            return {"ok": False, "error": f"Device not found: {id_exo}"}
        connector_map = {
            DeviceSource.HUE: "domotic", DeviceSource.TAPO: "domotic",
            DeviceSource.IKEA: "domotic", DeviceSource.TPLINK: "domotic",
            DeviceSource.EZVIZ: "camera", DeviceSource.SAMSUNG: "samsung",
            DeviceSource.VOLTALIS: "voltalis", DeviceSource.ECHO: "echo",
        }
        connector = connector_map.get(dev.source, "domotic")
        resp = await self._query_connector(connector, "get_state", {"device_id": dev.id_origin})
        if resp and resp.get("ok"):
            new_state = resp.get("data", {}).get("state", {})
            if new_state:
                dev.state.update(new_state)
                dev.last_seen = time.time()
                self._cache.set_state(id_exo, dev.state)
            return {"ok": True, "data": dev.to_dict()}
        return {"ok": False, "error": "Connector unreachable"}

    def capabilities(self) -> list[str]:
        return [
            "list_devices", "list_rooms", "get_device", "find_device",
            "update_state", "apply_command", "refresh_all", "refresh_device",
            "add_room", "assign_room", "get_network_links",
            "domotic_action", "domotic_query",
            "list_scenarios", "run_scenario", "discovery",
            "network_scan", "network_topology",
            "cache_stats", "event_stats",
            "capabilities", "metadata",
        ]

    def metadata(self) -> dict:
        return {
            "name": "homegraph",
            "version": "v2",
            "devices_count": len(self._devices),
            "rooms_count": len(self._rooms),
            "links_count": len(self._links),
            "cache": self._cache.stats(),
            "scenarios": len(self._scenarios.list_scenarios()),
        }

    def add_room(self, room_id: str, name: str) -> dict:
        room = Room(id=room_id, name=name)
        self._rooms[room_id] = room
        return room.to_dict()

    def assign_device_to_room(self, id_exo: str, room_id: str) -> bool:
        dev = self._devices.get(id_exo)
        room = self._rooms.get(room_id)
        if not dev or not room:
            return False
        # Remove from old room
        if dev.room_id and dev.room_id in self._rooms:
            old = self._rooms[dev.room_id]
            if id_exo in old.device_ids:
                old.device_ids.remove(id_exo)
        dev.room_id = room_id
        if id_exo not in room.device_ids:
            room.device_ids.append(id_exo)
        return True

    # ── Integration: merge devices from connectors ──

    def merge_devices(self, source: str, devices: list[dict]) -> int:
        """Merge a list of device dicts from a connector into the HomeGraph.
        Returns number of devices added or updated."""
        count = 0
        try:
            src = DeviceSource(source)
        except ValueError:
            src = DeviceSource.OTHER

        for raw in devices:
            origin_id = raw.get("id_origin", "")
            if not origin_id:
                continue

            # Find existing by origin id
            existing = None
            for dev in self._devices.values():
                if dev.id_origin == origin_id and dev.source == src:
                    existing = dev
                    break

            if existing:
                # Update
                existing.state.update(raw.get("state", {}))
                existing.online = raw.get("online", True)
                existing.last_seen = time.time()
                if raw.get("ip"):
                    existing.ip = raw["ip"]
                if raw.get("mac"):
                    existing.mac = raw["mac"]
                if raw.get("name"):
                    existing.name = raw["name"]
            else:
                # Create
                id_exo = f"{src.value}_{uuid.uuid4().hex[:8]}"
                try:
                    dtype = DeviceType(raw.get("type", "unknown"))
                except ValueError:
                    dtype = DeviceType.UNKNOWN

                caps = set()
                for c in raw.get("capabilities", []):
                    try:
                        caps.add(Capability(c))
                    except ValueError:
                        pass

                dev = Device(
                    id_exo=id_exo,
                    id_origin=origin_id,
                    source=src,
                    type=dtype,
                    name=raw.get("name", origin_id),
                    room_id=raw.get("room_id", ""),
                    capabilities=caps,
                    state=raw.get("state", {}),
                    ip=raw.get("ip", ""),
                    mac=raw.get("mac", ""),
                    vendor=raw.get("vendor", ""),
                    online=raw.get("online", True),
                )
                self._devices[id_exo] = dev

                # Auto-assign to room if specified
                if dev.room_id and dev.room_id in self._rooms:
                    room = self._rooms[dev.room_id]
                    if id_exo not in room.device_ids:
                        room.device_ids.append(id_exo)

            count += 1
        return count

    def merge_links(self, links: list[dict]) -> int:
        """Merge network links into the HomeGraph."""
        count = 0
        for raw in links:
            from_id = raw.get("from_id", "")
            to_id = raw.get("to_id", "")
            if not from_id or not to_id:
                continue
            try:
                lt = LinkType(raw.get("type", "unknown"))
            except ValueError:
                lt = LinkType.UNKNOWN

            # Avoid duplicates
            exists = any(
                lnk.from_id == from_id and lnk.to_id == to_id
                for lnk in self._links
            )
            if not exists:
                self._links.append(Link(from_id=from_id, to_id=to_id, type=lt))
                count += 1
        return count

    def merge_rooms(self, rooms: list[dict]) -> int:
        """Merge rooms from connectors."""
        count = 0
        for raw in rooms:
            rid = raw.get("id", "")
            name = raw.get("name", "")
            if not rid:
                continue
            if rid not in self._rooms:
                self._rooms[rid] = Room(id=rid, name=name)
                count += 1
            else:
                self._rooms[rid].name = name or self._rooms[rid].name
        return count

    # ── Connector communication ─────────────────────

    async def _query_connector(self, name: str, action: str,
                                params: dict | None = None) -> dict | None:
        """Send action to a connector and return the response."""
        url = self._connector_urls.get(name)
        if not url:
            return None
        try:
            async with websockets.connect(
                url, open_timeout=CONNECTOR_TIMEOUT
            ) as ws:
                # Consume ready message
                await asyncio.wait_for(ws.recv(), timeout=5)
                msg = {"action": action}
                if params:
                    msg["params"] = params
                await ws.send(json.dumps(msg))
                raw = await asyncio.wait_for(ws.recv(), timeout=CONNECTOR_TIMEOUT)
                return json.loads(raw)
        except Exception as e:
            log.warning("Connector %s (%s) unreachable: %s", name, action, e)
            return None

    async def refresh_all(self) -> dict:
        """Refresh from all connectors in parallel."""
        results = {}
        connectors = ["domotic", "camera", "samsung", "voltalis", "echo"]

        tasks = [self._query_connector(c, "list_devices") for c in connectors]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for name, resp in zip(connectors, responses):
            if isinstance(resp, Exception) or resp is None:
                results[name] = {"status": "unreachable"}
                continue
            if resp.get("ok"):
                devices = resp.get("data", {}).get("devices", [])
                rooms = resp.get("data", {}).get("rooms", [])
                merged = self.merge_devices(name, devices)
                if rooms:
                    self.merge_rooms(rooms)
                results[name] = {"status": "ok", "merged": merged}
            else:
                results[name] = {"status": "error", "msg": resp.get("error", "")}

        # Network scan
        net_resp = await self._query_connector("network", "scan")
        if net_resp and net_resp.get("ok"):
            nodes = net_resp.get("data", {}).get("nodes", [])
            links = net_resp.get("data", {}).get("links", [])
            self.merge_devices("network", nodes)
            self.merge_links(links)
            results["network"] = {"status": "ok", "nodes": len(nodes)}
        else:
            results["network"] = {"status": "unreachable"}

        log.info("Refresh complete: %d devices, %d rooms, %d links",
                 len(self._devices), len(self._rooms), len(self._links))
        return results

    async def apply_command(self, id_exo: str, command: str,
                             params: dict | None = None) -> dict:
        """Send a command to a device via its connector."""
        dev = self._devices.get(id_exo)
        if not dev:
            return {"ok": False, "error": f"Device not found: {id_exo}"}

        # Route to correct connector
        connector_map = {
            DeviceSource.HUE: "domotic",
            DeviceSource.TAPO: "domotic",
            DeviceSource.IKEA: "domotic",
            DeviceSource.TPLINK: "domotic",
            DeviceSource.EZVIZ: "camera",
            DeviceSource.SAMSUNG: "samsung",
            DeviceSource.VOLTALIS: "voltalis",
            DeviceSource.ECHO: "echo",
        }
        connector = connector_map.get(dev.source, "domotic")

        resp = await self._query_connector(connector, "apply_command", {
            "device_id": dev.id_origin,
            "command": command,
            **(params or {}),
        })
        if resp and resp.get("ok"):
            # Update local state
            new_state = resp.get("data", {}).get("state", {})
            if new_state:
                dev.state.update(new_state)
                dev.last_seen = time.time()
                self._cache.set_state(id_exo, dev.state)
                asyncio.get_running_loop().create_task(
                    self._events.on_event(id_exo, dev.state)
                )
            return {"ok": True, "state": dev.state}
        return {"ok": False, "error": resp.get("error", "Command failed") if resp else "Unreachable"}


# ═══════════════════════════════════════════════════════
#  WebSocket Handler
# ═══════════════════════════════════════════════════════

async def handle_client(ws, hg: HomeGraphManager) -> None:
    await ws.send(json.dumps({
        "type": "ready", "service": "homegraph", "version": "v2"
    }))
    try:
        async for raw in ws:
            if not isinstance(raw, str):
                continue
            try:
                msg = json.loads(raw)
            except (ValueError, TypeError) as e:
                log.warning("homegraph: invalid JSON dropped (%s): %.80s", e, raw)
                continue
            action = msg.get("action", msg.get("type", ""))
            params = msg.get("params", {})

            if action == "ping":
                await ws.send(json.dumps({"type": "pong"}))
                continue

            if action == "list_devices":
                data = hg.list_devices()
                await ws.send(json.dumps({"ok": True, "data": {"devices": data, "count": len(data)}}))

            elif action == "list_devices_by_room":
                data = hg.list_devices_by_room(params.get("room_id", ""))
                await ws.send(json.dumps({"ok": True, "data": {"devices": data}}))

            elif action == "list_rooms":
                data = hg.list_rooms()
                await ws.send(json.dumps({"ok": True, "data": {"rooms": data}}))

            elif action == "get_device":
                dev = hg.get_device(params.get("id_exo", ""))
                if dev:
                    await ws.send(json.dumps({"ok": True, "data": dev}))
                else:
                    await ws.send(json.dumps({"ok": False, "error": "Device not found"}))

            elif action == "find_device":
                name = params.get("name", "")
                dtype = params.get("type", "")
                if name:
                    results = hg.find_device_by_name(name)
                elif dtype:
                    results = hg.find_devices_by_type(dtype)
                else:
                    results = []
                await ws.send(json.dumps({"ok": True, "data": {"devices": results}}))

            elif action == "update_state":
                ok = hg.update_device_state(params.get("id_exo", ""), params.get("state", {}))
                await ws.send(json.dumps({"ok": ok}))

            elif action == "apply_command":
                result = await hg.apply_command(
                    params.get("id_exo", ""),
                    params.get("command", ""),
                    params.get("params"),
                )
                await ws.send(json.dumps(result))

            elif action == "refresh_all":
                result = await hg.refresh_all()
                await ws.send(json.dumps({"ok": True, "data": result}))

            elif action == "add_room":
                room = hg.add_room(params.get("id", ""), params.get("name", ""))
                await ws.send(json.dumps({"ok": True, "data": room}))

            elif action == "assign_room":
                ok = hg.assign_device_to_room(params.get("id_exo", ""), params.get("room_id", ""))
                await ws.send(json.dumps({"ok": ok}))

            elif action == "get_network_links":
                links = hg.get_network_links()
                await ws.send(json.dumps({"ok": True, "data": {"links": links}}))

            elif action == "domotic_action":
                # Agent integration: unified action endpoint
                target = params.get("target", "")
                cmd = params.get("command", params.get("action", ""))
                cmd_params = params.get("params", {})

                # Resolve target: could be id_exo, name, or room
                devices = []
                if target in hg._devices:
                    devices = [target]
                else:
                    found = hg.find_device_by_name(target)
                    devices = [d["id_exo"] for d in found]

                results = []
                for did in devices:
                    r = await hg.apply_command(did, cmd, cmd_params)
                    results.append({"device": did, **r})
                await ws.send(json.dumps({
                    "ok": len(results) > 0,
                    "data": {"results": results, "count": len(results)},
                }))

            elif action == "domotic_query":
                # Agent integration: query devices by natural language fragments
                query = params.get("query", "")
                results = hg.find_device_by_name(query)
                if not results:
                    results = hg.find_devices_by_type(query)
                await ws.send(json.dumps({
                    "ok": True,
                    "data": {"devices": results, "count": len(results)},
                }))

            # ── v2 actions ──────────────────────────────

            elif action == "refresh_device":
                result = await hg.refresh_device(params.get("id_exo", ""))
                await ws.send(json.dumps(result))

            elif action == "list_by_type":
                data = hg.list_devices_by_type(params.get("type", ""))
                await ws.send(json.dumps({"ok": True, "data": {"devices": data}}))

            elif action == "get_capabilities":
                caps = hg.get_capabilities(params.get("id_exo", ""))
                if caps is not None:
                    await ws.send(json.dumps({"ok": True, "data": caps}))
                else:
                    await ws.send(json.dumps({"ok": False, "error": "Device not found"}))

            elif action == "get_vendor":
                vendor = hg.get_vendor(params.get("id_exo", ""))
                if vendor is not None:
                    await ws.send(json.dumps({"ok": True, "data": {"vendor": vendor}}))
                else:
                    await ws.send(json.dumps({"ok": False, "error": "Device not found"}))

            elif action == "list_scenarios":
                data = hg.list_scenarios()
                await ws.send(json.dumps({"ok": True, "data": {"scenarios": data}}))

            elif action == "run_scenario":
                result = await hg.run_scenario(
                    params.get("name", ""),
                    params.get("devices"),
                )
                await ws.send(json.dumps({"ok": True, "data": result}))

            elif action == "discovery":
                result = await hg.run_discovery()
                await ws.send(json.dumps({"ok": True, "data": result}))

            elif action == "network_scan":
                result = await hg.run_network_scan()
                await ws.send(json.dumps(result, default=str))

            elif action == "network_topology":
                data = hg.get_network_topology()
                await ws.send(json.dumps({"ok": True, "data": data}))

            elif action == "cache_stats":
                await ws.send(json.dumps({"ok": True, "data": hg.get_cache_stats()}))

            elif action == "event_stats":
                await ws.send(json.dumps({"ok": True, "data": hg.get_event_stats()}))

            elif action == "capabilities":
                await ws.send(json.dumps({"ok": True, "data": hg.capabilities()}))

            elif action == "metadata":
                await ws.send(json.dumps({"ok": True, "data": hg.metadata()}))

            elif action == "gui_state":
                # Composite action for GUI: returns devices + rooms + scenarios
                await ws.send(json.dumps({
                    "ok": True,
                    "data": {
                        "devices": hg.list_devices(),
                        "rooms": hg.list_rooms(),
                        "scenarios": hg.list_scenarios(),
                    },
                }))

            else:
                await ws.send(json.dumps({"ok": False, "error": f"Unknown action: {action}"}))

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        log.error("Handler error: %s", e)


async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="EXO HomeGraph Manager")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    ensure_single_instance(args.port, "homegraph")
    _v9 = init_v9("homegraph", args.port)

    hg = HomeGraphManager()

    server = await websockets.serve(
        lambda ws: handle_client(ws, hg),
        args.host, args.port,
        ping_interval=None, ping_timeout=None,
    )
    log.info("HomeGraph running on ws://%s:%d", args.host, args.port)
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
