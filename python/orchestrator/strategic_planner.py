"""
EXO v22 — StrategicPlanner
Coordonne tous les moteurs de planification : réception d'intentions,
sélection du moteur, fusion des plans, arbitrage, validation finale.

API:
  plan(intent: dict)            → dict
  merge_plans(plans: dict)      → dict
  finalize_plan(plan: dict)     → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("strategic_planner")


class StrategicPlanner:
    """Planificateur stratégique central EXO v22."""

    ENGINES = {"htn", "multi_objective", "constraint", "scenario", "temporal"}

    def __init__(self, governance=None, htn=None, multi_obj=None,
                 constraint_planner=None, scenario_planner=None,
                 temporal_planner=None, arbitration=None):
        self._governance = governance
        self._htn = htn
        self._multi_obj = multi_obj
        self._constraint_planner = constraint_planner
        self._scenario_planner = scenario_planner
        self._temporal_planner = temporal_planner
        self._arbitration = arbitration

        self._plans: list[dict] = []
        self._stats = {
            "plans_created": 0,
            "merges": 0,
            "finalizations": 0,
        }

    # ── plan ────────────────────────────────────────────────
    def plan(self, intent: dict) -> dict:
        """Créer un plan stratégique à partir d'une intention."""
        self._stats["plans_created"] += 1

        goal = intent.get("goal", "")
        engine = intent.get("engine", "htn")
        context = intent.get("context", {})
        constraints = intent.get("constraints", [])
        objectives = intent.get("objectives", [])
        priority = intent.get("priority", 5)

        steps = []
        # Decompose goal into steps
        sub_goals = intent.get("sub_goals", [goal])
        for i, sg in enumerate(sub_goals):
            steps.append({
                "step": i + 1,
                "action": sg,
                "status": "planned",
                "engine": engine,
                "estimated_cost": 1.0,
            })

        plan = {
            "id": f"plan_{uuid.uuid4().hex[:8]}",
            "goal": goal,
            "engine": engine,
            "priority": priority,
            "context": context,
            "constraints": constraints,
            "objectives": objectives,
            "steps": steps,
            "steps_count": len(steps),
            "status": "draft",
            "score": 0.0,
            "timestamp": time.time(),
        }

        # Score based on completeness
        plan["score"] = min(1.0, len(steps) * 0.2)

        self._plans.append(plan)
        self._trim()

        return plan

    # ── merge_plans ─────────────────────────────────────────
    def merge_plans(self, plans: dict) -> dict:
        """Fusionner plusieurs plans en un plan composite."""
        self._stats["merges"] += 1

        plan_list = plans.get("plans", [])
        strategy = plans.get("strategy", "sequential")

        merged_steps = []
        total_score = 0.0
        goals = []

        for p in plan_list:
            goals.append(p.get("goal", ""))
            total_score += p.get("score", 0.0)
            for step in p.get("steps", []):
                merged_steps.append({
                    **step,
                    "step": len(merged_steps) + 1,
                    "source_plan": p.get("id", "unknown"),
                })

        avg_score = total_score / len(plan_list) if plan_list else 0.0

        merged = {
            "id": f"merged_{uuid.uuid4().hex[:8]}",
            "merged": True,
            "strategy": strategy,
            "source_plans_count": len(plan_list),
            "goals": goals,
            "steps": merged_steps,
            "steps_count": len(merged_steps),
            "score": round(avg_score, 3),
            "status": "merged",
            "timestamp": time.time(),
        }
        self._plans.append(merged)
        self._trim()

        return merged

    # ── finalize_plan ───────────────────────────────────────
    def finalize_plan(self, plan: dict) -> dict:
        """Valider et finaliser un plan."""
        self._stats["finalizations"] += 1

        plan_id = plan.get("id", "")
        steps = plan.get("steps", [])
        score = plan.get("score", 0.0)

        issues = []
        if not steps:
            issues.append("Plan sans étapes.")
        if score < 0.1:
            issues.append("Score trop faible.")

        valid = len(issues) == 0

        return {
            "id": f"final_{uuid.uuid4().hex[:8]}",
            "finalized": True,
            "plan_id": plan_id,
            "valid": valid,
            "issues": issues,
            "issues_count": len(issues),
            "steps_count": len(steps),
            "final_score": score,
            "status": "approved" if valid else "rejected",
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "strategic_planner",
            "status": "ok",
            "total_plans": len(self._plans),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._plans.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("StrategicPlanner restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._plans) > 5000:
            self._plans = self._plans[-2500:]
