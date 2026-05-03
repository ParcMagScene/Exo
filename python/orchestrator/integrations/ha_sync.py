"""
ha_sync.py — Synchronisation bridge between Home Assistant, Plans module,
and Network Discovery.

- Plans → HA: when a device is repositioned in the 2D/3D view, update its
  HA area assignment and notify the GUI via WebSocket.
- Network → HA: when a new host is discovered on the LAN, attempt to match
  it against the HA device registry by MAC or IP.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .home_bridge import HomeBridge
    from .ha_entities import EntityManager
    from .ha_devices import DeviceManager
    from .ha_areas import AreaManager

logger = logging.getLogger("exo.ha.sync")


class SyncManager:
    """Coordinates data flow between HA, Plans, and Network Discovery."""

    def __init__(
        self,
        bridge: HomeBridge,
        entities: EntityManager,
        devices: DeviceManager,
        areas: AreaManager,
        gui_broadcast: Optional[Any] = None,  # async callable(msg: dict)
    ) -> None:
        self._bridge = bridge
        self._entities = entities
        self._devices = devices
        self._areas = areas
        self._gui_broadcast = gui_broadcast  # Will be set by exo_server.py

        # Wire bridge events relevant to sync
        bridge.bus.on("on_state_changed", self._push_state_to_gui)
        bridge.bus.on("on_new_device", self._push_device_to_gui)
        bridge.bus.on("on_device_removed", self._push_device_to_gui)
        bridge.bus.on("plan_device_moved", self._on_plan_device_moved)

    def set_gui_broadcast(self, fn: Any) -> None:
        """Inject the GUI WebSocket broadcast function after init."""
        self._gui_broadcast = fn

    # ------------------------------------------------------------------
    # Plans → HA sync
    # ------------------------------------------------------------------

    async def on_plan_move(self, device_id: str, x: float, y: float, room: str) -> dict:
        """Called when a device is drag-dropped in the Plans UI.

        Updates HA area, EXO memory, and pushes a GUI notification.
        """
        await self._areas.update_plan_position(device_id, x, y, room)

        update = {
            "type": "plan_update",
            "plan_update": {
                "action": "device_moved",
                "device_id": device_id,
                "x": x,
                "y": y,
                "room": room,
            },
        }
        await self._broadcast(update)
        return {"ok": True}

    async def _on_plan_device_moved(self, data: dict) -> None:
        """Relay plan_device_moved bus events to the GUI."""
        await self._broadcast({
            "type": "plan_update",
            "plan_update": data,
        })

    # ------------------------------------------------------------------
    # Network Discovery → HA matching
    # ------------------------------------------------------------------

    async def match_network_host(self, mac: Optional[str] = None, ip: Optional[str] = None) -> dict:
        """Try to match a discovered network host against HA devices.

        Returns enriched device info if matched, or a suggestion dict.
        """
        device = None
        if mac:
            device = self._devices.match_device_by_mac(mac)
        if not device and ip:
            device = self._devices.match_device_by_ip(ip)

        if device:
            summary = self._devices.summary(device.get("id", ""))
            return {
                "matched": True,
                "device": summary,
                "source": "mac" if mac and self._devices.match_device_by_mac(mac) else "ip",
            }

        return {
            "matched": False,
            "mac": mac,
            "ip": ip,
            "suggestion": "Appareil non intégré à Home Assistant. Ajoutez-le via les intégrations HA.",
        }

    async def sync_network_devices(self, discovered_hosts: list[dict]) -> dict:
        """Batch-match a list of discovered hosts against HA.

        Each host dict should have optional 'mac' and 'ip' keys.
        Returns categorized results.
        """
        matched = []
        unmatched = []

        for host in discovered_hosts:
            result = await self.match_network_host(
                mac=host.get("mac"),
                ip=host.get("ip"),
            )
            if result.get("matched"):
                entry = result["device"]
                entry["network_ip"] = host.get("ip")
                entry["network_mac"] = host.get("mac")
                entry["hostname"] = host.get("hostname")
                matched.append(entry)
            else:
                unmatched.append({
                    "mac": host.get("mac"),
                    "ip": host.get("ip"),
                    "hostname": host.get("hostname"),
                    "integrated": False,
                })

        # Push topology update to GUI
        topology = self._build_topology(matched, unmatched)
        await self._broadcast({"type": "network_topology", "network_topology": topology})

        return {"matched": len(matched), "unmatched": len(unmatched), "details": {"matched": matched, "unmatched": unmatched}}

    # ------------------------------------------------------------------
    # State → GUI push
    # ------------------------------------------------------------------

    async def _push_state_to_gui(self, new_state: dict) -> None:
        eid = new_state.get("entity_id", "")
        attrs = new_state.get("attributes") or {}
        await self._broadcast({
            "type": "device_update",
            "device_update": {
                "entity_id": eid,
                "state": new_state.get("state"),
                "name": attrs.get("friendly_name", eid),
                "last_changed": new_state.get("last_changed"),
            },
        })

    async def _push_device_to_gui(self, data: dict) -> None:
        await self._broadcast({
            "type": "device_update",
            "device_update": data,
        })

    # ------------------------------------------------------------------
    # Full state snapshot for GUI init
    # ------------------------------------------------------------------

    def build_full_snapshot(self) -> dict:
        """Build a complete state snapshot for a newly connected GUI client."""
        return {
            "type": "snapshot",
            "entities": self._entities.all_summaries(),
            "devices": self._devices.all_summaries(),
            "areas": self._areas.all_summaries(),
            "network_topology": self._build_topology([], []),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_topology(self, matched: list, unmatched: list) -> dict:
        """Build a vis-network compatible topology structure."""
        nodes = []
        edges = []

        # Router node (always present)
        nodes.append({"id": "router", "label": "Routeur", "type": "router", "status": "online"})

        for dev in matched:
            nid = dev.get("device_id", dev.get("network_mac", ""))
            nodes.append({
                "id": nid,
                "label": dev.get("name", nid),
                "type": "client",
                "status": "online",
                "ip": dev.get("network_ip"),
                "ha_integrated": True,
            })
            edges.append({"from": "router", "to": nid})

        for host in unmatched:
            nid = host.get("mac") or host.get("ip") or "unknown"
            nodes.append({
                "id": nid,
                "label": host.get("hostname") or host.get("ip") or nid,
                "type": "client",
                "status": "online",
                "ip": host.get("ip"),
                "ha_integrated": False,
            })
            edges.append({"from": "router", "to": nid})

        return {"nodes": nodes, "edges": edges}

    async def _broadcast(self, msg: dict) -> None:
        if self._gui_broadcast:
            try:
                result = self._gui_broadcast(msg)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.warning("GUI broadcast failed", exc_info=True)
