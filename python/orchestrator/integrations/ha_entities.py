"""
ha_entities.py — Entity registry and state management for Home Assistant.

Provides a thread-safe cache of all HA entities with lookup, filtering,
and live-update capabilities wired to the HomeBridge event bus.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .home_bridge import HomeBridge

logger = logging.getLogger("exo.ha.entities")


class EntityManager:
    """Manages the full HA entity state cache for EXO."""

    def __init__(self, bridge: HomeBridge) -> None:
        self._bridge = bridge
        self._entities: dict[str, dict] = {}
        # Wire live updates
        bridge.bus.on("on_state_changed", self._on_state_changed)
        bridge.bus.on("connected", self._on_connected)

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    async def _on_connected(self, _: Any = None) -> None:
        await self.load_entities()

    async def load_entities(self) -> None:
        """(Re)load all entity states from the bridge cache."""
        self._entities = dict(self._bridge.entities)
        logger.info("EntityManager loaded %d entities", len(self._entities))

    # ------------------------------------------------------------------
    # CRUD / queries
    # ------------------------------------------------------------------

    def get_entity(self, entity_id: str) -> Optional[dict]:
        """Return a single entity dict or None."""
        return self._entities.get(entity_id)

    def list_entities(self) -> list[dict]:
        """Return all entities as a list."""
        return list(self._entities.values())

    def list_entities_by_domain(self, domain: str) -> list[dict]:
        """Return entities whose entity_id starts with *domain*."""
        prefix = domain if domain.endswith(".") else domain + "."
        return [e for eid, e in self._entities.items() if eid.startswith(prefix)]

    def list_entities_by_area(self, area_id: str) -> list[dict]:
        """Return entities assigned to a given area."""
        return [
            e for e in self._entities.values()
            if e.get("area_id") == area_id
        ]

    def search(self, query: str) -> list[dict]:
        """Simple text search across entity_id and friendly_name."""
        q = query.lower()
        results = []
        for eid, e in self._entities.items():
            name = (e.get("attributes") or {}).get("friendly_name", "")
            if q in eid.lower() or q in name.lower():
                results.append(e)
        return results

    # ------------------------------------------------------------------
    # Live update
    # ------------------------------------------------------------------

    async def _on_state_changed(self, new_state: dict) -> None:
        eid = new_state.get("entity_id", "")
        if eid:
            self._entities[eid] = new_state

    def update_entity_state(self, event_data: dict) -> None:
        """Manual state update (called from tests or sync)."""
        new_state = event_data.get("new_state")
        if new_state:
            eid = new_state.get("entity_id", "")
            if eid:
                self._entities[eid] = new_state

    # ------------------------------------------------------------------
    # Serialisation helpers (for GUI / LLM)
    # ------------------------------------------------------------------

    def summary(self, entity_id: str) -> Optional[dict]:
        """Return a compact summary suitable for LLM context."""
        e = self._entities.get(entity_id)
        if not e:
            return None
        attrs = e.get("attributes") or {}
        return {
            "entity_id": entity_id,
            "state": e.get("state"),
            "name": attrs.get("friendly_name", entity_id),
            "domain": entity_id.split(".")[0] if "." in entity_id else "",
            "area_id": e.get("area_id"),
            "last_changed": e.get("last_changed"),
        }

    def all_summaries(self, domain: Optional[str] = None) -> list[dict]:
        """List of compact summaries, optionally filtered by domain."""
        entities = self.list_entities_by_domain(domain) if domain else self.list_entities()
        return [self.summary(e.get("entity_id", "")) for e in entities if e.get("entity_id")]
