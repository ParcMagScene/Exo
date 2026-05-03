"""
EXO v18 — CognitiveLayerStack
Organise l'ensemble d'EXO en couches cognitives hiérarchiques :
  perception → extraction → symbolique → neuronal → inférence →
  planification → simulation → décision → supervision

API:
  push_to_layer(layer, data)    → dict
  pull_from_layer(layer)        → dict
  propagate_up(data)            → dict
  propagate_down(data)          → dict
  get_layer_state(layer)        → dict
  list_layers()                 → list[dict]
  health_check()                → dict
  restart()                     → None
  get_stats()                   → dict
"""

import logging
import time
import uuid

log = logging.getLogger("cognitive_layer_stack")

COGNITIVE_LAYERS = [
    "perception",
    "extraction",
    "symbolique",
    "neuronal",
    "inference",
    "planification",
    "simulation",
    "decision",
    "supervision",
]


class CognitiveLayerStack:
    """Pile de couches cognitives hiérarchiques EXO v18."""

    def __init__(self, macro_layer=None, micro_layer=None,
                 governance=None, meta_memory=None):
        self._macro = macro_layer
        self._micro = micro_layer
        self._governance = governance
        self._memory = meta_memory

        # Chaque couche maintient un buffer
        self._layers: dict[str, dict] = {}
        for layer in COGNITIVE_LAYERS:
            self._layers[layer] = {
                "name": layer,
                "index": COGNITIVE_LAYERS.index(layer),
                "buffer": [],
                "active": True,
                "push_count": 0,
                "pull_count": 0,
            }

        self._propagation_history: list[dict] = []
        self._stats = {
            "pushes": 0,
            "pulls": 0,
            "propagations_up": 0,
            "propagations_down": 0,
            "invalid_layers": 0,
        }

    # ── push_to_layer ───────────────────────────────────────
    def push_to_layer(self, layer: str, data: dict) -> dict:
        """Pousser des données vers une couche cognitive."""
        if layer not in self._layers:
            self._stats["invalid_layers"] += 1
            return {
                "id": f"cp_{uuid.uuid4().hex[:8]}",
                "pushed": False,
                "reason": "unknown_layer",
                "layer": layer,
                "valid_layers": COGNITIVE_LAYERS,
                "timestamp": time.time(),
            }

        self._stats["pushes"] += 1
        entry = {
            "id": f"ce_{uuid.uuid4().hex[:8]}",
            "data": data,
            "pushed_at": time.time(),
        }
        self._layers[layer]["buffer"].append(entry)
        self._layers[layer]["push_count"] += 1

        # Trim buffer
        if len(self._layers[layer]["buffer"]) > 500:
            self._layers[layer]["buffer"] = \
                self._layers[layer]["buffer"][-500:]

        return {
            "id": entry["id"],
            "pushed": True,
            "layer": layer,
            "layer_index": self._layers[layer]["index"],
            "buffer_size": len(self._layers[layer]["buffer"]),
            "timestamp": time.time(),
        }

    # ── pull_from_layer ─────────────────────────────────────
    def pull_from_layer(self, layer: str) -> dict:
        """Extraire les données d'une couche cognitive."""
        if layer not in self._layers:
            self._stats["invalid_layers"] += 1
            return {
                "id": f"cl_{uuid.uuid4().hex[:8]}",
                "pulled": False,
                "reason": "unknown_layer",
                "layer": layer,
                "timestamp": time.time(),
            }

        self._stats["pulls"] += 1
        self._layers[layer]["pull_count"] += 1
        items = self._layers[layer]["buffer"][-20:]

        return {
            "id": f"cl_{uuid.uuid4().hex[:8]}",
            "pulled": True,
            "layer": layer,
            "items": items,
            "count": len(items),
            "total_buffer": len(self._layers[layer]["buffer"]),
            "timestamp": time.time(),
        }

    # ── propagate_up ────────────────────────────────────────
    def propagate_up(self, data: dict) -> dict:
        """Propagation ascendante : perception → supervision."""
        self._stats["propagations_up"] += 1
        results = []
        source = data.get("source", data.get("text", ""))

        for layer_name in COGNITIVE_LAYERS:
            layer = self._layers[layer_name]
            if not layer["active"]:
                continue
            entry = {
                "id": f"pu_{uuid.uuid4().hex[:8]}",
                "direction": "up",
                "layer": layer_name,
                "index": layer["index"],
                "input_summary": str(source)[:100],
                "processed": True,
                "timestamp": time.time(),
            }
            layer["buffer"].append(entry)
            layer["push_count"] += 1
            results.append({
                "layer": layer_name,
                "index": layer["index"],
                "processed": True,
            })

        record = {
            "id": f"pu_{uuid.uuid4().hex[:8]}",
            "direction": "up",
            "layers_traversed": len(results),
            "results": results,
            "timestamp": time.time(),
        }
        self._propagation_history.append(record)
        self._trim()
        return record

    # ── propagate_down ──────────────────────────────────────
    def propagate_down(self, data: dict) -> dict:
        """Propagation descendante : supervision → perception."""
        self._stats["propagations_down"] += 1
        results = []
        goal = data.get("goal", data.get("directive", ""))

        for layer_name in reversed(COGNITIVE_LAYERS):
            layer = self._layers[layer_name]
            if not layer["active"]:
                continue
            entry = {
                "id": f"pd_{uuid.uuid4().hex[:8]}",
                "direction": "down",
                "layer": layer_name,
                "index": layer["index"],
                "goal_summary": str(goal)[:100],
                "processed": True,
                "timestamp": time.time(),
            }
            layer["buffer"].append(entry)
            layer["push_count"] += 1
            results.append({
                "layer": layer_name,
                "index": layer["index"],
                "processed": True,
            })

        record = {
            "id": f"pd_{uuid.uuid4().hex[:8]}",
            "direction": "down",
            "layers_traversed": len(results),
            "results": results,
            "timestamp": time.time(),
        }
        self._propagation_history.append(record)
        self._trim()
        return record

    # ── get_layer_state ─────────────────────────────────────
    def get_layer_state(self, layer: str) -> dict:
        """Obtenir l'état d'une couche cognitive."""
        if layer not in self._layers:
            return {"error": "unknown_layer", "layer": layer}
        L = self._layers[layer]
        return {
            "name": L["name"],
            "index": L["index"],
            "active": L["active"],
            "buffer_size": len(L["buffer"]),
            "push_count": L["push_count"],
            "pull_count": L["pull_count"],
        }

    # ── list_layers ─────────────────────────────────────────
    def list_layers(self) -> list[dict]:
        return [self.get_layer_state(n) for n in COGNITIVE_LAYERS]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "cognitive_layer_stack",
            "status": "ok",
            "layers_count": len(COGNITIVE_LAYERS),
            "active_layers": sum(1 for L in self._layers.values()
                                 if L["active"]),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        for L in self._layers.values():
            L["buffer"].clear()
            L["push_count"] = 0
            L["pull_count"] = 0
        self._propagation_history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("CognitiveLayerStack restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _trim(self) -> None:
        if len(self._propagation_history) > 5000:
            self._propagation_history = self._propagation_history[-5000:]
        for L in self._layers.values():
            if len(L["buffer"]) > 500:
                L["buffer"] = L["buffer"][-500:]
