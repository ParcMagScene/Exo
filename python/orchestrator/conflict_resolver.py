"""
EXO v14 — ConflictResolver (Résolution de conflits)
Détecte et résout les divergences entre agents spécialisés :
contradictions, incohérences, conflits temporels.

API:
  detect_conflicts(agent_outputs)       → dict
  resolve(agent_outputs)                → dict
  health_check()                        → dict
  restart()                             → None
  get_stats()                           → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("conflict_resolver")

# Paires d'actions contradictoires
_CONTRADICTIONS = [
    ("enable", "disable"), ("start", "stop"), ("on", "off"),
    ("open", "close"), ("lock", "unlock"), ("create", "delete"),
    ("activate", "deactivate"), ("allow", "deny"),
]


class ConflictResolver:
    """Résolveur de conflits inter-agents EXO v14."""

    def __init__(self, meta_memory=None, governance=None):
        self._memory = meta_memory
        self._governance = governance
        self._history: list[dict] = []
        self._stats = {
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "detections_run": 0,
            "resolutions_run": 0,
        }

    # ── detect_conflicts ────────────────────────────────────
    def detect_conflicts(self, agent_outputs: list[dict]) -> dict:
        """Detect conflicts among multiple agent outputs."""
        self._stats["detections_run"] += 1
        conflicts: list[dict] = []

        if len(agent_outputs) < 2:
            result = {
                "conflicts": [],
                "conflict_count": 0,
                "timestamp": time.time(),
            }
            self._record(result)
            return result

        # 1) Contradictory actions on the same target
        for i, out_a in enumerate(agent_outputs):
            for j, out_b in enumerate(agent_outputs):
                if j <= i:
                    continue
                conflict = self._check_contradiction(out_a, out_b)
                if conflict:
                    conflicts.append(conflict)

        # 2) Temporal conflicts (same target, overlapping times)
        temporal = self._check_temporal_conflicts(agent_outputs)
        conflicts.extend(temporal)

        # 3) Domain overlap (multiple agents acting on same target)
        overlap = self._check_domain_overlap(agent_outputs)
        conflicts.extend(overlap)

        self._stats["conflicts_detected"] += len(conflicts)

        result = {
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── resolve ─────────────────────────────────────────────
    def resolve(self, agent_outputs: list[dict]) -> dict:
        """Detect conflicts and resolve them by selecting optimal outputs."""
        self._stats["resolutions_run"] += 1
        detection = self.detect_conflicts(agent_outputs)
        conflicts = detection["conflicts"]

        if not conflicts:
            return {
                "resolved": True,
                "conflicts_found": 0,
                "selected_outputs": agent_outputs,
                "dropped_outputs": [],
                "resolution_method": "no_conflict",
                "timestamp": time.time(),
            }

        # Resolution strategy: priority-based arbitration
        selected, dropped = self._arbitrate(agent_outputs, conflicts)
        self._stats["conflicts_resolved"] += len(conflicts)

        result = {
            "resolved": True,
            "conflicts_found": len(conflicts),
            "conflicts": conflicts,
            "selected_outputs": selected,
            "dropped_outputs": dropped,
            "resolution_method": "priority_arbitration",
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── internal detection ──────────────────────────────────
    def _check_contradiction(self, out_a: dict, out_b: dict) -> dict | None:
        """Check if two outputs are contradictory."""
        action_a = self._extract_action(out_a)
        action_b = self._extract_action(out_b)
        target_a = self._extract_target(out_a)
        target_b = self._extract_target(out_b)

        if not (action_a and action_b):
            return None
        if target_a and target_b and target_a != target_b:
            return None  # Different targets, no conflict

        for pair in _CONTRADICTIONS:
            if ((action_a in pair and action_b in pair)
                    and action_a != action_b):
                return {
                    "type": "contradiction",
                    "agent_a": out_a.get("agent", "?"),
                    "agent_b": out_b.get("agent", "?"),
                    "action_a": action_a,
                    "action_b": action_b,
                    "target": target_a or target_b or "",
                    "severity": "high",
                }
        return None

    def _check_temporal_conflicts(self,
                                  outputs: list[dict]) -> list[dict]:
        """Check for temporal conflicts (same target, different times)."""
        conflicts = []
        timed = [(o, o.get("time_target", 0)) for o in outputs
                 if o.get("time_target")]
        for i, (oa, ta) in enumerate(timed):
            for j, (ob, tb) in enumerate(timed):
                if j <= i:
                    continue
                target_a = self._extract_target(oa)
                target_b = self._extract_target(ob)
                if target_a and target_a == target_b and abs(ta - tb) < 60:
                    conflicts.append({
                        "type": "temporal_conflict",
                        "agent_a": oa.get("agent", "?"),
                        "agent_b": ob.get("agent", "?"),
                        "target": target_a,
                        "time_diff": abs(ta - tb),
                        "severity": "medium",
                    })
        return conflicts

    def _check_domain_overlap(self, outputs: list[dict]) -> list[dict]:
        """Check for multiple agents acting on the same target/domain."""
        conflicts = []
        target_agents: dict[str, list[str]] = {}
        for o in outputs:
            target = self._extract_target(o)
            agent = o.get("agent", "")
            if target and agent:
                target_agents.setdefault(target, []).append(agent)
        for target, agents in target_agents.items():
            if len(agents) > 1:
                conflicts.append({
                    "type": "domain_overlap",
                    "target": target,
                    "agents": agents,
                    "severity": "low",
                })
        return conflicts

    # ── arbitration ─────────────────────────────────────────
    _PRIORITY = {
        "securite": 100,
        "domotique": 80,
        "planification": 70,
        "simulation": 60,
        "prevision": 50,
        "optimisation": 40,
        "memoire": 30,
        "contexte": 20,
        "reseau": 20,
        "audio": 10,
        "gui": 10,
        "scenarios": 10,
        "routines": 10,
    }

    def _arbitrate(self, outputs: list[dict],
                   conflicts: list[dict]) -> tuple[list[dict], list[dict]]:
        """Arbitrate conflicts by agent priority."""
        conflicting_agents: set[str] = set()
        for c in conflicts:
            if c.get("agent_a"):
                conflicting_agents.add(c["agent_a"])
            if c.get("agent_b"):
                conflicting_agents.add(c["agent_b"])

        # Score outputs
        scored = []
        for o in outputs:
            agent = o.get("agent", "")
            priority = self._PRIORITY.get(agent, 0)
            confidence = o.get("confidence", 0.5)
            score = priority + confidence * 10
            scored.append((score, o))
        scored.sort(key=lambda x: x[0], reverse=True)

        selected = []
        dropped = []
        seen_targets: set[str] = set()

        for score, o in scored:
            agent = o.get("agent", "")
            target = self._extract_target(o)
            key = f"{target}_{self._extract_action(o)}"

            if agent in conflicting_agents and key in seen_targets:
                dropped.append(o)
            else:
                selected.append(o)
                if target:
                    seen_targets.add(key)

        return selected, dropped

    # ── helpers ─────────────────────────────────────────────
    @staticmethod
    def _extract_action(output: dict) -> str:
        r = output.get("result", {})
        if isinstance(r, dict):
            return r.get("action", output.get("action", ""))
        return output.get("action", "")

    @staticmethod
    def _extract_target(output: dict) -> str:
        r = output.get("result", {})
        if isinstance(r, dict):
            return r.get("target", output.get("target", ""))
        return output.get("target", "")

    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 500:
            self._history = self._history[-300:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "conflict_resolver",
            "status": "ok",
            "conflicts_detected": self._stats["conflicts_detected"],
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ConflictResolver restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
