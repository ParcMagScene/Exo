"""
ha_devices.py — Device registry management for Home Assistant.

Tracks HA devices, maps device→entities, and enables MAC/IP matching
for network discovery synchronisation.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .home_bridge import HomeBridge

logger = logging.getLogger("exo.ha.devices")

_CACHE_DIR = Path(os.environ.get("EXO_FILES_DIR", r"D:\EXO\files"))
_DEVICES_FILE = _CACHE_DIR / "ha_devices.json"


class DeviceManager:
    """Manages the HA device registry and provides lookup helpers."""

    def __init__(self, bridge: HomeBridge) -> None:
        self._bridge = bridge
        self._devices: dict[str, dict] = {}
        self._device_entities: dict[str, list[str]] = {}  # device_id → [entity_ids]

        bridge.bus.on("on_new_device", self._on_device_event)
        bridge.bus.on("on_device_removed", self._on_device_event)
        bridge.bus.on("on_device_updated", self._on_device_event)
        bridge.bus.on("connected", self._on_connected)

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    async def _on_connected(self, _: Any = None) -> None:
        await self.load_devices()

    async def load_devices(self) -> None:
        """Load devices from bridge cache and build entity mapping."""
        self._devices = dict(self._bridge.devices)
        self._build_entity_map()
        self._persist()
        logger.info("DeviceManager loaded %d devices", len(self._devices))

    def _build_entity_map(self) -> None:
        self._device_entities.clear()
        for eid, entity in self._bridge.entities.items():
            did = entity.get("device_id")
            if did:
                self._device_entities.setdefault(did, []).append(eid)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_device(self, device_id: str) -> Optional[dict]:
        return self._devices.get(device_id)

    def list_devices(self) -> list[dict]:
        return list(self._devices.values())

    def get_entities_for_device(self, device_id: str) -> list[str]:
        return self._device_entities.get(device_id, [])

    def match_device_by_mac(self, mac: str) -> Optional[dict]:
        """Search for a device whose connections include the given MAC."""
        mac_lower = mac.lower().replace("-", ":").strip()
        for dev in self._devices.values():
            connections = dev.get("connections", [])
            for conn_type, conn_val in connections:
                if conn_type == "mac" and conn_val.lower() == mac_lower:
                    return dev
        return None

    def match_device_by_ip(self, ip: str) -> Optional[dict]:
        """Match a device by IP stored in its configuration_url or identifiers."""
        for dev in self._devices.values():
            config_url = dev.get("configuration_url", "") or ""
            if ip in config_url:
                return dev
            for id_domain, id_val in dev.get("identifiers", []):
                if ip in str(id_val):
                    return dev
        return None

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [
            d for d in self._devices.values()
            if q in (d.get("name") or "").lower()
            or q in (d.get("manufacturer") or "").lower()
            or q in (d.get("model") or "").lower()
        ]

    # ------------------------------------------------------------------
    # Serialisation for GUI / LLM
    # ------------------------------------------------------------------

    def summary(self, device_id: str) -> Optional[dict]:
        d = self._devices.get(device_id)
        if not d:
            return None
        return {
            "device_id": device_id,
            "name": d.get("name") or d.get("name_by_user") or "Unknown",
            "manufacturer": d.get("manufacturer"),
            "model": d.get("model"),
            "area_id": d.get("area_id"),
            "entities": self._device_entities.get(device_id, []),
            "via_device_id": d.get("via_device_id"),
        }

    def all_summaries(self) -> list[dict]:
        return [self.summary(did) for did in self._devices if self.summary(did)]

    # ------------------------------------------------------------------
    # Live events
    # ------------------------------------------------------------------

    async def _on_device_event(self, data: Any) -> None:
        # Refresh the whole list from bridge (already updated by bridge)
        self._devices = dict(self._bridge.devices)
        self._build_entity_map()
        self._persist()

    # ------------------------------------------------------------------
    # Persistence (JSON file for offline reference)
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = _DEVICES_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.all_summaries(), indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(_DEVICES_FILE)
        except OSError:
            logger.warning("Could not persist device cache")

    def load_from_cache(self) -> list[dict]:
        """Load previously persisted device summaries (offline fallback)."""
        if _DEVICES_FILE.exists():
            try:
                return json.loads(_DEVICES_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return []
