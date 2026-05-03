"""
EXO v13 — FuturePlanner (Planification prospective)
Planifie des actions futures, conditionnelles, programmées ou récurrentes.

API:
  plan_future_action(action, time_target)  → dict
  plan_conditional_action(action, cond)    → dict
  plan_recurrent_action(action, schedule)  → dict
  get_pending_plans()                      → list
  cancel_plan(plan_id)                     → bool
  health_check()                           → dict
  restart()                                → None
  get_stats()                              → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("future_planner")


class FuturePlanner:
    """Moteur de planification prospective EXO v13."""

    def __init__(self, meta_memory, governance=None):
        self._memory = meta_memory
        self._governance = governance
        self._pending: dict[str, dict] = {}
        self._history: list[dict] = []
        self._stats = {
            "future_plans": 0,
            "conditional_plans": 0,
            "recurrent_plans": 0,
            "plans_cancelled": 0,
        }

    # ── plan_future_action ──────────────────────────────────
    def plan_future_action(self, action: dict, time_target: float) -> dict:
        """Plan an action for a specific future time.

        Args:
            action: dict with 'tool', 'description', 'target', etc.
            time_target: UNIX timestamp for execution.
        Returns:
            Plan record with id and validation status.
        """
        plan_id = f"fp_{uuid.uuid4().hex[:8]}"

        issues: list[dict] = []

        # Validate time_target
        now = time.time()
        if time_target <= now:
            issues.append({
                "type": "past_time",
                "detail": "Target time is in the past",
            })

        # Validate action
        if not action.get("tool") and not action.get("description"):
            issues.append({
                "type": "empty_action",
                "detail": "Action has no tool or description",
            })

        # Governance check
        valid = len(issues) == 0

        record = {
            "id": plan_id,
            "type": "future_action",
            "action": action,
            "time_target": time_target,
            "created_at": now,
            "valid": valid,
            "issues": issues,
            "status": "pending" if valid else "rejected",
        }

        if valid:
            self._pending[plan_id] = record

        self._stats["future_plans"] += 1
        self._record(record)
        return record

    # ── plan_conditional_action ─────────────────────────────
    def plan_conditional_action(self, action: dict,
                                condition: dict) -> dict:
        """Plan an action triggered by a condition.

        Args:
            action: dict with 'tool', 'description', etc.
            condition: dict with 'type' (e.g. 'state', 'time', 'event'),
                       'expression', 'value'.
        """
        plan_id = f"fc_{uuid.uuid4().hex[:8]}"
        issues: list[dict] = []

        if not condition.get("type"):
            issues.append({"type": "missing_condition_type",
                           "detail": "Condition must have a type"})
        if not condition.get("expression"):
            issues.append({"type": "missing_expression",
                           "detail": "Condition must have an expression"})
        if not action.get("tool") and not action.get("description"):
            issues.append({"type": "empty_action",
                           "detail": "Action has no tool or description"})

        valid = len(issues) == 0

        record = {
            "id": plan_id,
            "type": "conditional_action",
            "action": action,
            "condition": condition,
            "created_at": time.time(),
            "valid": valid,
            "issues": issues,
            "status": "pending" if valid else "rejected",
        }

        if valid:
            self._pending[plan_id] = record

        self._stats["conditional_plans"] += 1
        self._record(record)
        return record

    # ── plan_recurrent_action ───────────────────────────────
    def plan_recurrent_action(self, action: dict,
                              schedule: dict) -> dict:
        """Plan a recurring action.

        Args:
            action: dict with 'tool', 'description', etc.
            schedule: dict with 'frequency' (daily/weekly/hourly),
                      'time' (HH:MM), 'days' (list of int 0-6 for weekly).
        """
        plan_id = f"fr_{uuid.uuid4().hex[:8]}"
        issues: list[dict] = []

        freq = schedule.get("frequency", "")
        if freq not in ("hourly", "daily", "weekly", "monthly"):
            issues.append({
                "type": "invalid_frequency",
                "detail": f"Frequency '{freq}' not supported",
            })

        if not action.get("tool") and not action.get("description"):
            issues.append({"type": "empty_action",
                           "detail": "Action has no tool or description"})

        valid = len(issues) == 0

        record = {
            "id": plan_id,
            "type": "recurrent_action",
            "action": action,
            "schedule": schedule,
            "created_at": time.time(),
            "valid": valid,
            "issues": issues,
            "status": "pending" if valid else "rejected",
        }

        if valid:
            self._pending[plan_id] = record

        self._stats["recurrent_plans"] += 1
        self._record(record)
        return record

    # ── get / cancel ────────────────────────────────────────
    def get_pending_plans(self) -> list[dict]:
        return list(self._pending.values())

    def cancel_plan(self, plan_id: str) -> bool:
        if plan_id in self._pending:
            self._pending[plan_id]["status"] = "cancelled"
            del self._pending[plan_id]
            self._stats["plans_cancelled"] += 1
            return True
        return False

    # ── health_check / restart / stats ──────────────────────
    def health_check(self) -> dict:
        return {
            "service": "future_planner",
            "status": "ok",
            "pending_count": len(self._pending),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._pending.clear()
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("FuturePlanner restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── private ─────────────────────────────────────────────
    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 500:
            self._history = self._history[-300:]
