"""
ha_actions.py — Domotic actions exposed to BrainEngine (LLM Function Calling).

Each public function validates its inputs, calls Home Assistant via the bridge,
and returns a clean dict suitable for LLM consumption.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .home_bridge import HomeBridge
    from .ha_entities import EntityManager
    from .ha_devices import DeviceManager
    from .ha_areas import AreaManager

logger = logging.getLogger("exo.ha.actions")


# ---------------------------------------------------------------------------
# Tool definitions for BrainEngine (Claude Function Calling schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "ha_turn_on",
        "description": "Allume une entité Home Assistant (lumière, prise, switch…)",
        "input_schema": {
            "type": "object",
            "properties": {"entity_id": {"type": "string", "description": "ID de l'entité HA (ex: light.salon)"}},
            "required": ["entity_id"],
        },
    },
    {
        "name": "ha_turn_off",
        "description": "Éteint une entité Home Assistant",
        "input_schema": {
            "type": "object",
            "properties": {"entity_id": {"type": "string", "description": "ID de l'entité HA"}},
            "required": ["entity_id"],
        },
    },
    {
        "name": "ha_toggle",
        "description": "Bascule l'état d'une entité Home Assistant (on↔off)",
        "input_schema": {
            "type": "object",
            "properties": {"entity_id": {"type": "string", "description": "ID de l'entité HA"}},
            "required": ["entity_id"],
        },
    },
    {
        "name": "ha_set_brightness",
        "description": "Règle la luminosité d'une lumière Home Assistant (0-255)",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "brightness": {"type": "integer", "minimum": 0, "maximum": 255},
            },
            "required": ["entity_id", "brightness"],
        },
    },
    {
        "name": "ha_set_color",
        "description": "Définit la couleur RGB d'une lumière Home Assistant",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "r": {"type": "integer", "minimum": 0, "maximum": 255},
                "g": {"type": "integer", "minimum": 0, "maximum": 255},
                "b": {"type": "integer", "minimum": 0, "maximum": 255},
            },
            "required": ["entity_id", "r", "g", "b"],
        },
    },
    {
        "name": "ha_set_temperature",
        "description": "Règle la température d'un thermostat Home Assistant (°C)",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "temperature": {"type": "number"},
            },
            "required": ["entity_id", "temperature"],
        },
    },
    {
        "name": "ha_play_media",
        "description": "Lance la lecture d'un média sur un lecteur Home Assistant",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "media_url": {"type": "string"},
                "media_type": {"type": "string", "default": "music"},
            },
            "required": ["entity_id", "media_url"],
        },
    },
    {
        "name": "ha_pause_media",
        "description": "Met en pause un lecteur média Home Assistant",
        "input_schema": {
            "type": "object",
            "properties": {"entity_id": {"type": "string"}},
            "required": ["entity_id"],
        },
    },
    {
        "name": "ha_stop_media",
        "description": "Arrête la lecture d'un lecteur média Home Assistant",
        "input_schema": {
            "type": "object",
            "properties": {"entity_id": {"type": "string"}},
            "required": ["entity_id"],
        },
    },
    {
        "name": "ha_get_state",
        "description": "Récupère l'état actuel d'une entité Home Assistant",
        "input_schema": {
            "type": "object",
            "properties": {"entity_id": {"type": "string"}},
            "required": ["entity_id"],
        },
    },
    {
        "name": "ha_list_devices",
        "description": "Liste tous les appareils Home Assistant détectés",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ha_list_entities",
        "description": "Liste toutes les entités Home Assistant, optionnellement filtrées par domaine",
        "input_schema": {
            "type": "object",
            "properties": {"domain": {"type": "string", "description": "Domaine optionnel (light, switch, sensor…)"}},
        },
    },
    {
        "name": "ha_list_areas",
        "description": "Liste toutes les pièces définies dans Home Assistant",
        "input_schema": {"type": "object", "properties": {}},
    },
]


# ---------------------------------------------------------------------------
# Action dispatcher
# ---------------------------------------------------------------------------

class ActionDispatcher:
    """Executes HA actions requested by the LLM and returns structured results."""

    def __init__(
        self,
        bridge: HomeBridge,
        entities: EntityManager,
        devices: DeviceManager,
        areas: AreaManager,
    ) -> None:
        self._bridge = bridge
        self._entities = entities
        self._devices = devices
        self._areas = areas

        # Build dispatch table
        self._handlers: dict[str, Any] = {
            "ha_turn_on": self.turn_on,
            "ha_turn_off": self.turn_off,
            "ha_toggle": self.toggle,
            "ha_set_brightness": self.set_brightness,
            "ha_set_color": self.set_color,
            "ha_set_temperature": self.set_temperature,
            "ha_play_media": self.play_media,
            "ha_pause_media": self.pause_media,
            "ha_stop_media": self.stop_media,
            "ha_get_state": self.get_state,
            "ha_list_devices": self.list_devices,
            "ha_list_entities": self.list_entities,
            "ha_list_areas": self.list_areas,
        }

    # ------------------------------------------------------------------
    # Dispatch entry point (called by BrainEngine)
    # ------------------------------------------------------------------

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        handler = self._handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown HA action: {tool_name}"}
        try:
            return await handler(**arguments)
        except Exception as exc:
            logger.exception("HA action %s failed", tool_name)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Service call helpers
    # ------------------------------------------------------------------

    def _domain_of(self, entity_id: str) -> str:
        return entity_id.split(".")[0] if "." in entity_id else ""

    async def _call(self, domain: str, service: str, entity_id: str, **extra: Any) -> dict:
        data = {"entity_id": entity_id, **extra}
        await self._bridge.call_service(domain, service, data)
        return {"ok": True, "entity_id": entity_id, "service": f"{domain}.{service}"}

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def turn_on(self, entity_id: str) -> dict:
        domain = self._domain_of(entity_id)
        return await self._call(domain or "homeassistant", "turn_on", entity_id)

    async def turn_off(self, entity_id: str) -> dict:
        domain = self._domain_of(entity_id)
        return await self._call(domain or "homeassistant", "turn_off", entity_id)

    async def toggle(self, entity_id: str) -> dict:
        domain = self._domain_of(entity_id)
        return await self._call(domain or "homeassistant", "toggle", entity_id)

    async def set_brightness(self, entity_id: str, brightness: int) -> dict:
        brightness = max(0, min(255, int(brightness)))
        return await self._call("light", "turn_on", entity_id, brightness=brightness)

    async def set_color(self, entity_id: str, r: int, g: int, b: int) -> dict:
        rgb = [max(0, min(255, int(c))) for c in (r, g, b)]
        return await self._call("light", "turn_on", entity_id, rgb_color=rgb)

    async def set_temperature(self, entity_id: str, temperature: float) -> dict:
        return await self._call("climate", "set_temperature", entity_id, temperature=float(temperature))

    async def play_media(self, entity_id: str, media_url: str, media_type: str = "music") -> dict:
        return await self._call(
            "media_player", "play_media", entity_id,
            media_content_id=media_url,
            media_content_type=media_type,
        )

    async def pause_media(self, entity_id: str) -> dict:
        return await self._call("media_player", "media_pause", entity_id)

    async def stop_media(self, entity_id: str) -> dict:
        return await self._call("media_player", "media_stop", entity_id)

    async def get_state(self, entity_id: str) -> dict:
        summary = self._entities.summary(entity_id)
        if summary:
            return summary
        # Fallback: fetch directly from HA
        states = await self._bridge.rest_get(f"/api/states/{entity_id}")
        return states if isinstance(states, dict) else {"error": f"Entity {entity_id} not found"}

    async def list_devices(self) -> dict:
        return {"devices": self._devices.all_summaries()}

    async def list_entities(self, domain: Optional[str] = None) -> dict:
        return {"entities": self._entities.all_summaries(domain)}

    async def list_areas(self) -> dict:
        return {"areas": self._areas.all_summaries()}
