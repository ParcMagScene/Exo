"""
EXO v22 — HTNPlusEngine (HTN+)
Extension du planificateur HTN v10 : hiérarchique, conditionnel,
contextuel, multi-agents, optimisé.

API:
  htn_expand(task: dict)      → dict
  htn_optimize(plan: dict)    → dict
  htn_validate(plan: dict)    → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("htn_plus_engine")


class HTNPlusEngine:
    """Moteur HTN+ étendu EXO v22."""

    def __init__(self, governance=None, htn_planner=None):
        self._governance = governance
        self._htn_planner = htn_planner

        self._expansions: list[dict] = []
        self._stats = {
            "expansions": 0,
            "optimizations": 0,
            "validations": 0,
        }

    # ── htn_expand ──────────────────────────────────────────
    def htn_expand(self, task: dict) -> dict:
        """Décomposer une tâche HTN+ en sous-tâches."""
        self._stats["expansions"] += 1

        name = task.get("name", "unnamed")
        task_type = task.get("type", "compound")
        context = task.get("context", {})
        preconditions = task.get("preconditions", [])
        agents = task.get("agents", [])
        max_depth = task.get("max_depth", 5)

        subtasks = []
        if task_type == "compound":
            methods = task.get("methods", [])
            if not methods:
                methods = [{"name": f"{name}_default", "steps": [name]}]
            for m in methods:
                for i, step in enumerate(m.get("steps", [])):
                    subtasks.append({
                        "step": len(subtasks) + 1,
                        "action": step,
                        "method": m.get("name", "default"),
                        "type": "primitive",
                        "agent": agents[i % len(agents)] if agents else None,
                        "status": "expanded",
                    })
        else:
            subtasks.append({
                "step": 1,
                "action": name,
                "method": "direct",
                "type": "primitive",
                "agent": agents[0] if agents else None,
                "status": "ready",
            })

        expansion = {
            "id": f"htn_{uuid.uuid4().hex[:8]}",
            "expanded": True,
            "task": name,
            "task_type": task_type,
            "context": context,
            "preconditions": preconditions,
            "subtasks": subtasks,
            "subtasks_count": len(subtasks),
            "depth": min(max_depth, len(subtasks)),
            "timestamp": time.time(),
        }
        self._expansions.append(expansion)
        self._trim()

        return expansion

    # ── htn_optimize ────────────────────────────────────────
    def htn_optimize(self, plan: dict) -> dict:
        """Optimiser un plan HTN+ (réordonnancement, élagage)."""
        self._stats["optimizations"] += 1

        steps = plan.get("steps", plan.get("subtasks", []))
        strategy = plan.get("optimization_strategy", "cost")

        optimized = list(steps)

        # Remove redundant steps (same action consecutive)
        deduped = []
        prev = None
        removed = 0
        for s in optimized:
            action = s.get("action", "")
            if action != prev:
                deduped.append(s)
                prev = action
            else:
                removed += 1

        # Re-number
        for i, s in enumerate(deduped):
            s["step"] = i + 1

        return {
            "id": f"opt_{uuid.uuid4().hex[:8]}",
            "optimized": True,
            "strategy": strategy,
            "original_steps": len(steps),
            "optimized_steps": len(deduped),
            "steps_removed": removed,
            "steps": deduped,
            "timestamp": time.time(),
        }

    # ── htn_validate ────────────────────────────────────────
    def htn_validate(self, plan: dict) -> dict:
        """Valider un plan HTN+."""
        self._stats["validations"] += 1

        steps = plan.get("steps", plan.get("subtasks", []))
        issues = []

        if not steps:
            issues.append({"type": "empty_plan", "message": "Aucune étape."})

        for i, step in enumerate(steps):
            if not step.get("action"):
                issues.append({
                    "type": "missing_action",
                    "step": i + 1,
                    "message": f"Étape {i+1} sans action.",
                })

        valid = len(issues) == 0

        return {
            "id": f"val_{uuid.uuid4().hex[:8]}",
            "validated": True,
            "valid": valid,
            "steps_count": len(steps),
            "issues": issues,
            "issues_count": len(issues),
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "htn_plus_engine",
            "status": "ok",
            "total_expansions": len(self._expansions),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._expansions.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("HTNPlusEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._expansions) > 5000:
            self._expansions = self._expansions[-2500:]
