"""
ha_areas.py — Area (room/zone) management for Home Assistant.

Tracks HA areas, manages device/entity assignments, and exposes
plan-position sync helpers for the 2D/3D Plans module.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .home_bridge import HomeBridge

logger = logging.getLogger("exo.ha.areas")


class AreaManager:
    """Manages the HA area registry for EXO."""

    def __init__(self, bridge: HomeBridge) -> None:
        self._bridge = bridge
        self._areas: dict[str, dict] = {}  # area_id → area dict
        self._area_devices: dict[str, list[str]] = {}  # area_id → [device_ids]
        self._area_entities: dict[str, list[str]] = {}  # area_id → [entity_ids]

        bridge.bus.on("on_area_updated", self._on_area_updated)
        bridge.bus.on("connected", self._on_connected)

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    async def _on_connected(self, _: Any = None) -> None:
        await self.load_areas()

    async def load_areas(self) -> None:
        self._areas = dict(self._bridge.areas)
        self._rebuild_mappings()
        logger.info("AreaManager loaded %d areas", len(self._areas))

    def _rebuild_mappings(self) -> None:
        self._area_devices.clear()
        self._area_entities.clear()

        for did, dev in self._bridge.devices.items():
            area = dev.get("area_id")
            if area:
                self._area_devices.setdefault(area, []).append(did)

        for eid, entity in self._bridge.entities.items():
            area = entity.get("area_id")
            if area:
                self._area_entities.setdefault(area, []).append(eid)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_area(self, area_id: str) -> Optional[dict]:
        return self._areas.get(area_id)

    def list_areas(self) -> list[dict]:
        return list(self._areas.values())

    def get_devices_in_area(self, area_id: str) -> list[str]:
        return self._area_devices.get(area_id, [])

    def get_entities_in_area(self, area_id: str) -> list[str]:
        return self._area_entities.get(area_id, [])

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [a for a in self._areas.values() if q in (a.get("name") or "").lower()]

    # ------------------------------------------------------------------
    # Assignment helpers (via HA WebSocket)
    # ------------------------------------------------------------------

    async def assign_device_to_area(self, device_id: str, area_id: str) -> dict:
        """Move a device to a different area in HA."""
        result = await self._bridge.ws_command(
            "config/device_registry/update",
            device_id=device_id,
            area_id=area_id,
        )
        logger.info("Assigned device %s → area %s", device_id, area_id)
        return result

    async def assign_entity_to_area(self, entity_id: str, area_id: str) -> dict:
        """Move an entity to a different area in HA."""
        result = await self._bridge.ws_command(
            "config/entity_registry/update",
            entity_id=entity_id,
            area_id=area_id,
        )
        logger.info("Assigned entity %s → area %s", entity_id, area_id)
        return result

    # ------------------------------------------------------------------
    # Plans synchronisation
    # ------------------------------------------------------------------

    async def update_plan_position(self, device_id: str, x: float, y: float, room: str) -> None:
        """Called when a device is drag-dropped in the Plans view.

        - Updates the corresponding HA area if *room* maps to a known area.
        - Emits a bus event for the GUI to pick up.
        """
        target_area = self._find_area_by_name(room)
        if target_area:
            aid = target_area.get("area_id", "")
            dev = self._bridge.devices.get(device_id)
            if dev and dev.get("area_id") != aid:
                await self.assign_device_to_area(device_id, aid)

        await self._bridge.bus.emit("plan_device_moved", {
            "device_id": device_id,
            "x": x,
            "y": y,
            "room": room,
        })

    def _find_area_by_name(self, name: str) -> Optional[dict]:
        n = name.lower().strip()
        for a in self._areas.values():
            if (a.get("name") or "").lower().strip() == n:
                return a
        return None

    # ------------------------------------------------------------------
    # Serialisation for GUI / LLM
    # ------------------------------------------------------------------

    def summary(self, area_id: str) -> Optional[dict]:
        a = self._areas.get(area_id)
        if not a:
            return None
        return {
            "area_id": area_id,
            "name": a.get("name"),
            "devices": self._area_devices.get(area_id, []),
            "entities": self._area_entities.get(area_id, []),
        }

    def all_summaries(self) -> list[dict]:
        return [self.summary(aid) for aid in self._areas if self.summary(aid)]

    # ------------------------------------------------------------------
    # Live events
    # ------------------------------------------------------------------

    async def _on_area_updated(self, data: Any) -> None:
        self._areas = dict(self._bridge.areas)
        self._rebuild_mappings()
