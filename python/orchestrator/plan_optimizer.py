"""
EXO v19 — PlanOptimizer
Optimise les plans HTN issus d'EXO v10.

API:
  optimize_plan(plan: dict)                → dict
  simplify_plan(plan: dict)                → dict
  generate_alternative_plans(plan: dict)   → dict
  health_check()                           → dict
  restart()                                → None
  get_stats()                              → dict
"""

import logging
import time
import uuid

log = logging.getLogger("plan_optimizer")


class PlanOptimizer:
    """Optimiseur de plans HTN EXO v19."""

    def __init__(self, meta_optimizer=None, pipeline_optimizer=None,
                 governance=None):
        self._meta = meta_optimizer
        self._pipeline = pipeline_optimizer
        self._governance = governance

        self._history: list[dict] = []
        self._stats = {
            "plans_optimized": 0,
            "plans_simplified": 0,
            "alternatives_generated": 0,
        }

    # ── optimize_plan ───────────────────────────────────────
    def optimize_plan(self, plan: dict) -> dict:
        """Optimiser un plan HTN pour réduire le coût et la latence."""
        self._stats["plans_optimized"] += 1

        steps = plan.get("steps", [])
        goal = plan.get("goal", "unknown")

        optimized = []
        eliminated = []

        for step in steps:
            cost = step.get("cost", 1.0)
            effect = step.get("effect", 1.0)

            # Éliminer les étapes à coût élevé et effet faible
            if cost > 3.0 and effect < 0.3:
                eliminated.append({
                    "step": step.get("name", "?"),
                    "reason": "high_cost_low_effect",
                    "cost": cost,
                    "effect": effect,
                })
            else:
                optimized.append(step)

        # Trier par ratio effet/coût décroissant
        optimized.sort(
            key=lambda s: s.get("effect", 1) / max(s.get("cost", 1), 0.01),
            reverse=True,
        )

        original_cost = sum(s.get("cost", 1) for s in steps)
        optimized_cost = sum(s.get("cost", 1) for s in optimized)

        record = {
            "id": f"po_{uuid.uuid4().hex[:8]}",
            "optimized": True,
            "goal": goal,
            "original_steps": len(steps),
            "optimized_steps": len(optimized),
            "eliminated": eliminated,
            "steps": optimized,
            "original_cost": round(original_cost, 2),
            "optimized_cost": round(optimized_cost, 2),
            "gain_pct": round(
                (1 - optimized_cost / max(original_cost, 0.01)) * 100, 1
            ),
            "timestamp": time.time(),
        }
        self._history.append(record)
        self._trim()
        return record

    # ── simplify_plan ───────────────────────────────────────
    def simplify_plan(self, plan: dict) -> dict:
        """Simplifier un plan en fusionnant les étapes consécutives."""
        self._stats["plans_simplified"] += 1

        steps = plan.get("steps", [])
        goal = plan.get("goal", "unknown")

        simplified = []
        i = 0
        merges = 0

        while i < len(steps):
            current = dict(steps[i])

            # Fusionner avec la suivante si même type
            if (i + 1 < len(steps)
                    and steps[i].get("type") == steps[i + 1].get("type")):
                current["name"] = (
                    f"{steps[i].get('name', '?')}+"
                    f"{steps[i+1].get('name', '?')}"
                )
                current["cost"] = (
                    steps[i].get("cost", 1) + steps[i + 1].get("cost", 1)
                ) * 0.8  # gain de fusion
                current["merged"] = True
                merges += 1
                i += 2
            else:
                i += 1

            simplified.append(current)

        return {
            "id": f"si_{uuid.uuid4().hex[:8]}",
            "simplified": True,
            "goal": goal,
            "original_steps": len(steps),
            "simplified_steps": len(simplified),
            "merges": merges,
            "steps": simplified,
            "timestamp": time.time(),
        }

    # ── generate_alternative_plans ──────────────────────────
    def generate_alternative_plans(self, plan: dict) -> dict:
        """Générer des plans alternatifs pour le même objectif."""
        self._stats["alternatives_generated"] += 1

        goal = plan.get("goal", "unknown")
        steps = plan.get("steps", [])

        alternatives = []

        # Alternative 1 : plan inversé (tester un autre ordre)
        if len(steps) > 1:
            reversed_steps = list(reversed(steps))
            cost = sum(s.get("cost", 1) for s in reversed_steps)
            alternatives.append({
                "name": "reversed_order",
                "steps": reversed_steps,
                "total_cost": round(cost, 2),
                "description": "Ordre inversé des étapes",
            })

        # Alternative 2 : plan minimal (garder les 50% les plus efficaces)
        if len(steps) > 2:
            sorted_steps = sorted(
                steps,
                key=lambda s: s.get("effect", 1) / max(s.get("cost", 1), 0.01),
                reverse=True,
            )
            half = sorted_steps[:max(len(sorted_steps) // 2, 1)]
            cost = sum(s.get("cost", 1) for s in half)
            alternatives.append({
                "name": "minimal_plan",
                "steps": half,
                "total_cost": round(cost, 2),
                "description": "50% des étapes les plus efficaces",
            })

        # Alternative 3 : plan sans étapes optionnelles
        required = [s for s in steps if s.get("required", True)]
        if len(required) < len(steps):
            cost = sum(s.get("cost", 1) for s in required)
            alternatives.append({
                "name": "required_only",
                "steps": required,
                "total_cost": round(cost, 2),
                "description": "Uniquement les étapes obligatoires",
            })

        return {
            "id": f"ap_{uuid.uuid4().hex[:8]}",
            "generated": True,
            "goal": goal,
            "original_steps": len(steps),
            "alternatives": alternatives,
            "total_alternatives": len(alternatives),
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "plan_optimizer",
            "status": "ok",
            "history": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("PlanOptimizer restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
