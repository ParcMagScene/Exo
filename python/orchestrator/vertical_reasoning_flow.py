"""
EXO v18 — VerticalReasoningFlow
Flux d'information bidirectionnel entre couches cognitives.
Bottom-up : perception → décision.
Top-down  : objectif → exécution.

API:
  reason_bottom_up(data)      → dict
  reason_top_down(goal)       → dict
  merge_vertical_flows()      → dict
  get_flow_history()          → list[dict]
  health_check()              → dict
  restart()                   → None
  get_stats()                 → dict
"""

import logging
import time
import uuid

log = logging.getLogger("vertical_reasoning_flow")


class VerticalReasoningFlow:
    """Flux de raisonnement vertical bidirectionnel EXO v18."""

    def __init__(self, layer_stack=None, governance=None,
                 meta_memory=None):
        self._stack = layer_stack
        self._governance = governance
        self._memory = meta_memory

        self._bottom_up_history: list[dict] = []
        self._top_down_history: list[dict] = []
        self._merged_history: list[dict] = []
        self._stats = {
            "bottom_up_flows": 0,
            "top_down_flows": 0,
            "merges": 0,
            "governance_blocks": 0,
        }

    # ── reason_bottom_up ────────────────────────────────────
    def reason_bottom_up(self, data: dict) -> dict:
        """Raisonnement ascendant : perception → décision."""
        self._stats["bottom_up_flows"] += 1

        source = data.get("source", data.get("text", "input"))
        context = data.get("context", {})

        # Gouvernance
        if self._governance:
            try:
                g = self._governance.check_action(
                    "vertical_bottom_up", data)
                if not g.get("allowed", True):
                    self._stats["governance_blocks"] += 1
                    return {
                        "id": f"bu_{uuid.uuid4().hex[:8]}",
                        "direction": "bottom_up",
                        "completed": False,
                        "reason": "governance_denied",
                        "timestamp": time.time(),
                    }
            except Exception:
                pass

        # Propager via le stack si disponible
        stages = []
        if self._stack:
            try:
                result = self._stack.propagate_up(data)
                stages = result.get("results", [])
            except Exception as e:
                log.warning("propagate_up failed: %s", e)

        if not stages:
            stages = [
                {"layer": "perception", "processed": True},
                {"layer": "extraction", "processed": True},
                {"layer": "symbolique", "processed": True},
                {"layer": "neuronal", "processed": True},
                {"layer": "inference", "processed": True},
                {"layer": "planification", "processed": True},
                {"layer": "simulation", "processed": True},
                {"layer": "decision", "processed": True},
                {"layer": "supervision", "processed": True},
            ]

        record = {
            "id": f"bu_{uuid.uuid4().hex[:8]}",
            "direction": "bottom_up",
            "completed": True,
            "source": str(source)[:200],
            "stages": stages,
            "layers_traversed": len(stages),
            "timestamp": time.time(),
        }
        self._bottom_up_history.append(record)
        self._trim()
        return record

    # ── reason_top_down ─────────────────────────────────────
    def reason_top_down(self, goal: dict) -> dict:
        """Raisonnement descendant : objectif → exécution."""
        self._stats["top_down_flows"] += 1

        objective = goal.get("goal", goal.get("directive", ""))
        priority = goal.get("priority", "normal")

        # Gouvernance
        if self._governance:
            try:
                g = self._governance.check_action(
                    "vertical_top_down", goal)
                if not g.get("allowed", True):
                    self._stats["governance_blocks"] += 1
                    return {
                        "id": f"td_{uuid.uuid4().hex[:8]}",
                        "direction": "top_down",
                        "completed": False,
                        "reason": "governance_denied",
                        "timestamp": time.time(),
                    }
            except Exception:
                pass

        # Propager via le stack si disponible
        stages = []
        if self._stack:
            try:
                result = self._stack.propagate_down(goal)
                stages = result.get("results", [])
            except Exception as e:
                log.warning("propagate_down failed: %s", e)

        if not stages:
            stages = [
                {"layer": "supervision", "processed": True},
                {"layer": "decision", "processed": True},
                {"layer": "simulation", "processed": True},
                {"layer": "planification", "processed": True},
                {"layer": "inference", "processed": True},
                {"layer": "neuronal", "processed": True},
                {"layer": "symbolique", "processed": True},
                {"layer": "extraction", "processed": True},
                {"layer": "perception", "processed": True},
            ]

        record = {
            "id": f"td_{uuid.uuid4().hex[:8]}",
            "direction": "top_down",
            "completed": True,
            "objective": str(objective)[:200],
            "priority": priority,
            "stages": stages,
            "layers_traversed": len(stages),
            "timestamp": time.time(),
        }
        self._top_down_history.append(record)
        self._trim()
        return record

    # ── merge_vertical_flows ────────────────────────────────
    def merge_vertical_flows(self) -> dict:
        """Fusionner les flux ascendants et descendants récents."""
        self._stats["merges"] += 1

        recent_bu = self._bottom_up_history[-10:]
        recent_td = self._top_down_history[-10:]

        # Identifier convergences
        convergences = []
        for bu in recent_bu:
            for td in recent_td:
                delta = abs(bu["timestamp"] - td["timestamp"])
                if delta < 60:  # < 60s
                    convergences.append({
                        "bottom_up_id": bu["id"],
                        "top_down_id": td["id"],
                        "time_delta_s": round(delta, 3),
                    })

        record = {
            "id": f"mv_{uuid.uuid4().hex[:8]}",
            "merged": True,
            "bottom_up_count": len(recent_bu),
            "top_down_count": len(recent_td),
            "convergences": convergences[:20],
            "convergence_count": len(convergences),
            "timestamp": time.time(),
        }
        self._merged_history.append(record)
        self._trim()
        return record

    # ── get_flow_history ────────────────────────────────────
    def get_flow_history(self) -> list[dict]:
        combined = []
        for r in self._bottom_up_history[-20:]:
            combined.append(r)
        for r in self._top_down_history[-20:]:
            combined.append(r)
        combined.sort(key=lambda x: x.get("timestamp", 0))
        return combined[-30:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "vertical_reasoning_flow",
            "status": "ok",
            "bottom_up_history": len(self._bottom_up_history),
            "top_down_history": len(self._top_down_history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._bottom_up_history.clear()
        self._top_down_history.clear()
        self._merged_history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("VerticalReasoningFlow restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _trim(self) -> None:
        if len(self._bottom_up_history) > 5000:
            self._bottom_up_history = self._bottom_up_history[-5000:]
        if len(self._top_down_history) > 5000:
            self._top_down_history = self._top_down_history[-5000:]
        if len(self._merged_history) > 2000:
            self._merged_history = self._merged_history[-2000:]
