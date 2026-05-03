"""
EXO v13 — TemporalCoherenceEngine (Cohérence temporelle)
Garantit la cohérence des plans dans le temps : détection de
conflits temporels, chevauchements, dépendances non respectées,
correction automatique.

API:
  check_temporal_conflicts(plans)   → dict
  enforce_temporal_coherence()      → dict
  get_stats()                       → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("temporal_coherence")


class TemporalCoherenceEngine:
    """Moteur de cohérence temporelle EXO v13."""

    def __init__(self, meta_memory, future_planner=None):
        self._memory = meta_memory
        self._planner = future_planner
        self._history: list[dict] = []
        self._stats = {
            "conflict_checks": 0,
            "conflicts_found": 0,
            "enforcements": 0,
            "corrections_applied": 0,
        }

    # ── check_temporal_conflicts ────────────────────────────
    def check_temporal_conflicts(self, plans: list[dict]) -> dict:
        """Check a list of future plans for temporal conflicts.

        Each plan should have: 'id', 'time_target' (or 'schedule'),
        'action' with 'tool'/'target'.
        """
        conflicts: list[dict] = []
        warnings: list[dict] = []

        # 1. Detect time overlaps among fixed-time plans
        timed_plans = [
            p for p in plans
            if isinstance(p, dict) and p.get("time_target")
        ]
        timed_plans.sort(key=lambda p: p.get("time_target", 0))

        for i in range(len(timed_plans)):
            for j in range(i + 1, len(timed_plans)):
                pa, pb = timed_plans[i], timed_plans[j]
                ta = pa.get("time_target", 0)
                tb = pb.get("time_target", 0)
                # Same minute window = overlap
                if abs(ta - tb) < 60:
                    conflicts.append({
                        "type": "time_overlap",
                        "plan_a": pa.get("id", f"plan_{i}"),
                        "plan_b": pb.get("id", f"plan_{j}"),
                        "detail": f"Plans overlap within 60s window "
                                  f"(delta={abs(ta - tb):.0f}s)",
                    })

        # 2. Detect conflicting actions on same target
        for i in range(len(plans)):
            for j in range(i + 1, len(plans)):
                if not isinstance(plans[i], dict) or not isinstance(plans[j], dict):
                    continue
                conflict = self._check_action_conflict(plans[i], plans[j])
                if conflict:
                    conflicts.append(conflict)

        # 3. Detect dependency violations
        dep_issues = self._check_dependencies(plans)
        conflicts.extend(dep_issues)

        # 4. Detect plans in the past
        now = time.time()
        for p in plans:
            if not isinstance(p, dict):
                continue
            t = p.get("time_target", 0)
            if t and t < now:
                warnings.append({
                    "type": "past_plan",
                    "plan_id": p.get("id", "unknown"),
                    "detail": "Plan targets a time in the past",
                })

        self._stats["conflict_checks"] += 1
        self._stats["conflicts_found"] += len(conflicts)

        result = {
            "type": "temporal_conflict_check",
            "plan_count": len(plans),
            "conflicts": conflicts,
            "warnings": warnings,
            "coherent": len(conflicts) == 0,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── enforce_temporal_coherence ──────────────────────────
    def enforce_temporal_coherence(self) -> dict:
        """Enforce temporal coherence on pending plans.

        If FuturePlanner is available, checks and corrects its pending plans.
        """
        actions: list[dict] = []

        if self._planner:
            pending = self._planner.get_pending_plans()
            check = self.check_temporal_conflicts(pending)

            # Cancel conflicting plans
            cancelled_ids: set[str] = set()
            for conflict in check.get("conflicts", []):
                # Cancel the later plan in conflicts
                plan_b_id = conflict.get("plan_b", "")
                if plan_b_id and plan_b_id not in cancelled_ids:
                    ok = self._planner.cancel_plan(plan_b_id)
                    if ok:
                        cancelled_ids.add(plan_b_id)
                        actions.append({
                            "action": "cancel_conflicting",
                            "plan_id": plan_b_id,
                            "reason": conflict.get("detail", ""),
                        })

            # Cancel past plans
            for warning in check.get("warnings", []):
                if warning.get("type") == "past_plan":
                    pid = warning.get("plan_id", "")
                    if pid and pid not in cancelled_ids:
                        ok = self._planner.cancel_plan(pid)
                        if ok:
                            cancelled_ids.add(pid)
                            actions.append({
                                "action": "cancel_past",
                                "plan_id": pid,
                                "reason": "Plan in the past",
                            })
        else:
            # No planner — check MetaMemory for temporal data
            entries = self._memory.meta_get("future")
            for e in entries:
                val = e.get("value", {})
                if isinstance(val, dict) and val.get("time_target", 0) < time.time():
                    actions.append({
                        "action": "stale_entry",
                        "entry_id": e.get("id", ""),
                        "reason": "Future entry is now in the past",
                    })

        self._stats["enforcements"] += 1
        self._stats["corrections_applied"] += len(actions)

        result = {
            "type": "temporal_enforcement",
            "actions": actions,
            "correction_count": len(actions),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── stats ───────────────────────────────────────────────
    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── private ─────────────────────────────────────────────
    def _check_action_conflict(self, plan_a: dict,
                               plan_b: dict) -> dict | None:
        """Check if two plans have conflicting actions on same target."""
        act_a = plan_a.get("action", {})
        act_b = plan_b.get("action", {})
        if not isinstance(act_a, dict) or not isinstance(act_b, dict):
            return None

        target_a = act_a.get("target", "").lower()
        target_b = act_b.get("target", "").lower()
        tool_a = act_a.get("tool", "").lower()
        tool_b = act_b.get("tool", "").lower()

        if not target_a or not target_b or target_a != target_b:
            return None

        opposing = [
            ("enable", "disable"), ("start", "stop"), ("open", "close"),
            ("lock", "unlock"), ("on", "off"),
        ]
        for pos, neg in opposing:
            if ((pos in tool_a and neg in tool_b) or
                    (neg in tool_a and pos in tool_b)):
                return {
                    "type": "action_conflict",
                    "plan_a": plan_a.get("id", "?"),
                    "plan_b": plan_b.get("id", "?"),
                    "detail": f"Conflicting actions on target '{target_a}': "
                              f"'{tool_a}' vs '{tool_b}'",
                }
        return None

    def _check_dependencies(self, plans: list) -> list[dict]:
        """Check dependency ordering."""
        issues = []
        id_to_time: dict[str, float] = {}
        for p in plans:
            if not isinstance(p, dict):
                continue
            pid = p.get("id", "")
            t = p.get("time_target", 0)
            if pid and t:
                id_to_time[pid] = t

        for p in plans:
            if not isinstance(p, dict):
                continue
            deps = p.get("depends_on", [])
            pid = p.get("id", "")
            t = p.get("time_target", 0)
            for dep_id in deps:
                dep_t = id_to_time.get(dep_id, 0)
                if dep_t and t and dep_t >= t:
                    issues.append({
                        "type": "dependency_violation",
                        "plan_id": pid,
                        "depends_on": dep_id,
                        "detail": f"Plan '{pid}' depends on '{dep_id}' "
                                  f"which executes at same time or later",
                    })
        return issues

    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 500:
            self._history = self._history[-300:]
