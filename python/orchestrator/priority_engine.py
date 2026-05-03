"""
EXO v18 — PriorityEngine
Ajustement dynamique des priorités cognitives.
Chaque couche, macro-agent ou micro-agent peut recevoir un niveau
de priorité qui influence l'ordonnancement du traitement.

API:
  set_priority(entity, level)   → dict
  adjust_priority(entity)       → dict
  compute_priority_map()        → dict
  get_entity_priority(entity)   → dict
  reset_priorities()            → dict
  health_check()                → dict
  restart()                     → None
  get_stats()                   → dict
"""

import logging
import time
import uuid

log = logging.getLogger("priority_engine")

PRIORITY_LEVELS = {
    "critical": 5,
    "high": 4,
    "normal": 3,
    "low": 2,
    "idle": 1,
}


class PriorityEngine:
    """Moteur de priorité cognitive EXO v18."""

    def __init__(self, layer_stack=None, macro_layer=None,
                 micro_layer=None, governance=None):
        self._stack = layer_stack
        self._macro = macro_layer
        self._micro = micro_layer
        self._governance = governance

        self._priorities: dict[str, dict] = {}
        self._adjustment_history: list[dict] = []
        self._stats = {
            "priorities_set": 0,
            "priorities_adjusted": 0,
            "maps_computed": 0,
            "resets": 0,
        }

    # ── set_priority ────────────────────────────────────────
    def set_priority(self, entity: dict, level: str) -> dict:
        """Définir la priorité d'une entité (couche/macro/micro)."""
        self._stats["priorities_set"] += 1

        name = entity.get("name", entity.get("entity", "unknown"))
        entity_type = entity.get("type", "generic")

        numeric = PRIORITY_LEVELS.get(level, 3)

        self._priorities[name] = {
            "name": name,
            "type": entity_type,
            "level": level,
            "numeric": numeric,
            "set_at": time.time(),
            "adjustments": 0,
        }

        return {
            "id": f"sp_{uuid.uuid4().hex[:8]}",
            "set": True,
            "entity": name,
            "entity_type": entity_type,
            "level": level,
            "numeric": numeric,
            "timestamp": time.time(),
        }

    # ── adjust_priority ─────────────────────────────────────
    def adjust_priority(self, entity: dict) -> dict:
        """Ajuster dynamiquement la priorité d'une entité."""
        self._stats["priorities_adjusted"] += 1

        name = entity.get("name", entity.get("entity", "unknown"))
        reason = entity.get("reason", "auto")
        direction = entity.get("direction", "up")  # "up" or "down"

        current = self._priorities.get(name)
        if not current:
            # Auto-create at normal
            current = {
                "name": name,
                "type": entity.get("type", "generic"),
                "level": "normal",
                "numeric": 3,
                "set_at": time.time(),
                "adjustments": 0,
            }
            self._priorities[name] = current

        old_numeric = current["numeric"]
        if direction == "up":
            new_numeric = min(old_numeric + 1, 5)
        else:
            new_numeric = max(old_numeric - 1, 1)

        # Reverse lookup level name
        level_name = "normal"
        for lname, lval in PRIORITY_LEVELS.items():
            if lval == new_numeric:
                level_name = lname
                break

        current["numeric"] = new_numeric
        current["level"] = level_name
        current["adjustments"] += 1

        record = {
            "id": f"ap_{uuid.uuid4().hex[:8]}",
            "adjusted": True,
            "entity": name,
            "old_level": old_numeric,
            "new_level": new_numeric,
            "level_name": level_name,
            "direction": direction,
            "reason": reason,
            "timestamp": time.time(),
        }
        self._adjustment_history.append(record)
        self._trim()
        return record

    # ── compute_priority_map ────────────────────────────────
    def compute_priority_map(self) -> dict:
        """Calculer la carte de priorité complète."""
        self._stats["maps_computed"] += 1

        # Enrichir depuis les sous-systèmes existants
        if self._stack and not any(
            p.get("type") == "layer" for p in self._priorities.values()
        ):
            try:
                layers = self._stack.list_layers()
                for L in layers:
                    name = L.get("name", "")
                    if name and name not in self._priorities:
                        self._priorities[name] = {
                            "name": name,
                            "type": "layer",
                            "level": "normal",
                            "numeric": 3,
                            "set_at": time.time(),
                            "adjustments": 0,
                        }
            except Exception:
                pass

        # Construire la carte triée par priorité décroissante
        sorted_items = sorted(
            self._priorities.values(),
            key=lambda x: x.get("numeric", 3),
            reverse=True,
        )

        return {
            "id": f"pm_{uuid.uuid4().hex[:8]}",
            "computed": True,
            "entities": sorted_items,
            "total_entities": len(sorted_items),
            "critical_count": sum(
                1 for p in sorted_items if p.get("numeric", 0) >= 5),
            "high_count": sum(
                1 for p in sorted_items if p.get("numeric", 0) == 4),
            "timestamp": time.time(),
        }

    # ── get_entity_priority ─────────────────────────────────
    def get_entity_priority(self, entity: str) -> dict:
        p = self._priorities.get(entity)
        if not p:
            return {"entity": entity, "found": False}
        return {"entity": entity, "found": True, **p}

    # ── reset_priorities ────────────────────────────────────
    def reset_priorities(self) -> dict:
        self._stats["resets"] += 1
        count = len(self._priorities)
        for p in self._priorities.values():
            p["level"] = "normal"
            p["numeric"] = 3
            p["adjustments"] = 0
        return {
            "reset": True,
            "entities_reset": count,
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "priority_engine",
            "status": "ok",
            "entities_tracked": len(self._priorities),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._priorities.clear()
        self._adjustment_history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("PriorityEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _trim(self) -> None:
        if len(self._adjustment_history) > 5000:
            self._adjustment_history = self._adjustment_history[-5000:]
