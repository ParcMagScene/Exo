"""
EXO v12 — MetaPlannerV2 (Planification avancée)
Étend MetaPlanner v11 avec évaluation automatique, comparaison et
amélioration de plans.

API:
  evaluate_plan(plan)       → dict
  compare_plans(plans)      → dict
  improve_plan(plan)        → dict
  health_check()            → dict
  restart()                 → None
  get_stats()               → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("meta_planner_v2")


class MetaPlannerV2:
    """Planificateur avancé EXO v12 — étend MetaPlanner v11."""

    def __init__(self, meta_memory, meta_planner_v1=None, self_reflection=None):
        """
        Args:
            meta_memory: MetaMemory instance.
            meta_planner_v1: MetaPlanner v11 (optional) for adaptation.
            self_reflection: SelfReflectionEngine (optional) for reflection.
        """
        self._memory = meta_memory
        self._v1 = meta_planner_v1
        self._reflection = self_reflection
        self._history: list[dict] = []
        self._stats = {
            "plans_evaluated": 0,
            "plans_compared": 0,
            "plans_improved": 0,
        }

    # ── Evaluate plan ────────────────────────────────────────
    def evaluate_plan(self, plan: dict) -> dict:
        """Evaluate plan quality with multi-criteria scoring.

        Returns scores for completeness, efficiency, robustness, alignment.
        """
        steps = plan.get("steps", [])
        goal = plan.get("goal", "")
        constraints = plan.get("constraints", [])

        completeness = self._eval_completeness(steps, goal)
        efficiency = self._eval_efficiency(steps)
        robustness = self._eval_robustness(steps)
        alignment = self._eval_alignment(steps, goal, constraints)

        overall = (
            completeness * 0.3
            + efficiency * 0.25
            + robustness * 0.25
            + alignment * 0.2
        )

        # Use reflection if available
        reflection = None
        if self._reflection:
            reflection = self._reflection.reflect_on_plan(plan)

        self._stats["plans_evaluated"] += 1

        result = {
            "type": "plan_evaluation",
            "scores": {
                "completeness": round(completeness, 2),
                "efficiency": round(efficiency, 2),
                "robustness": round(robustness, 2),
                "alignment": round(alignment, 2),
                "overall": round(overall, 2),
            },
            "reflection": reflection,
            "step_count": len(steps),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Compare plans ────────────────────────────────────────
    def compare_plans(self, plans: list[dict]) -> dict:
        """Compare multiple plans and rank them.

        plans: list of plan dicts.
        Returns ranking with scores.
        """
        if not plans:
            return {"ranking": [], "best_index": -1}

        evaluations = []
        for i, plan in enumerate(plans):
            ev = self.evaluate_plan(plan)
            evaluations.append({
                "index": i,
                "goal": plan.get("goal", ""),
                "scores": ev["scores"],
                "step_count": ev["step_count"],
            })

        # Sort by overall score descending
        ranking = sorted(evaluations, key=lambda x: x["scores"]["overall"],
                         reverse=True)

        self._stats["plans_compared"] += 1

        result = {
            "type": "plan_comparison",
            "ranking": ranking,
            "best_index": ranking[0]["index"] if ranking else -1,
            "plan_count": len(plans),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Improve plan ─────────────────────────────────────────
    def improve_plan(self, plan: dict) -> dict:
        """Propose an improved version of a plan.

        Analyzes weaknesses and applies improvements.
        Returns improved plan with changelog.
        """
        steps = list(plan.get("steps", []))
        goal = plan.get("goal", "")
        changes = []

        # 1. Add missing goal
        improved_plan = dict(plan)
        if not goal:
            improved_plan["goal"] = "undefined — needs specification"
            changes.append({
                "type": "add_goal",
                "detail": "Added placeholder goal",
            })

        # 2. Remove empty steps
        non_empty = []
        for i, step in enumerate(steps):
            if isinstance(step, dict):
                desc = step.get("description", "")
                tool = step.get("tool", "")
                if desc or tool:
                    non_empty.append(step)
                else:
                    changes.append({
                        "type": "remove_empty_step",
                        "step_index": i,
                        "detail": f"Removed empty step {i}",
                    })
            else:
                non_empty.append(step)

        # 3. Add error handling steps where missing
        enhanced = []
        for i, step in enumerate(non_empty):
            enhanced.append(step)
            if isinstance(step, dict) and not step.get("error_handling"):
                tool = step.get("tool", "")
                if tool:
                    # Suggest error handling
                    enhanced_step = dict(step)
                    enhanced_step["error_handling"] = f"retry_or_skip:{tool}"
                    enhanced[-1] = enhanced_step
                    changes.append({
                        "type": "add_error_handling",
                        "step_index": i,
                        "detail": f"Added error handling for step {i} ({tool})",
                    })

        # 4. Apply v11 adaptations if available
        if self._v1:
            adapted = self._v1.adapt_plan({"steps": enhanced})
            v1_adaptations = adapted.get("adaptations", [])
            if v1_adaptations:
                enhanced = adapted.get("steps", enhanced)
                changes.extend([
                    {"type": "v11_adaptation", "detail": a.get("description", "")}
                    for a in v1_adaptations
                ])

        improved_plan["steps"] = enhanced
        improved_plan["improvements"] = changes
        improved_plan["improved_at"] = time.time()

        self._stats["plans_improved"] += 1

        result = {
            "type": "plan_improvement",
            "original_step_count": len(plan.get("steps", [])),
            "improved_step_count": len(enhanced),
            "changes": changes,
            "change_count": len(changes),
            "improved_plan": improved_plan,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Health / restart (v9 integration) ────────────────────
    def health_check(self) -> dict:
        return {
            "service": "meta_planner_v2",
            "status": "ok",
            "stats": dict(self._stats),
            "history_size": len(self._history),
        }

    def restart(self) -> None:
        self._history.clear()
        self._stats = {k: 0 for k in self._stats}
        log.info("MetaPlannerV2 restarted")

    # ── Stats ────────────────────────────────────────────────
    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal scoring ─────────────────────────────────────
    def _eval_completeness(self, steps: list, goal: str) -> float:
        score = 0.2
        if goal:
            score += 0.2
        if steps:
            score += 0.2
        if len(steps) >= 3:
            score += 0.2
        # Check if steps cover different aspects
        tools = set()
        for s in steps:
            if isinstance(s, dict) and s.get("tool"):
                tools.add(s["tool"])
        if len(tools) >= 2:
            score += 0.2
        return min(1.0, score)

    def _eval_efficiency(self, steps: list) -> float:
        if not steps:
            return 0.3
        score = 0.5
        # Penalty for redundant steps
        descriptions = []
        for s in steps:
            desc = s.get("description", "") if isinstance(s, dict) else str(s)
            descriptions.append(desc.strip().lower())
        unique = len(set(descriptions))
        if len(descriptions) > 0:
            ratio = unique / len(descriptions)
            score += 0.3 * ratio
        # Bonus for parallelizable steps
        independent = sum(
            1 for s in steps
            if isinstance(s, dict) and not s.get("depends_on")
        )
        if independent >= 2 and len(steps) >= 3:
            score += 0.1
        return min(1.0, score)

    def _eval_robustness(self, steps: list) -> float:
        score = 0.4
        # Check for error handling
        with_error_handling = sum(
            1 for s in steps
            if isinstance(s, dict) and s.get("error_handling")
        )
        if steps:
            score += 0.4 * (with_error_handling / len(steps))
        # Check for fallbacks
        with_fallback = sum(
            1 for s in steps
            if isinstance(s, dict) and s.get("fallback")
        )
        if with_fallback:
            score += 0.2
        return min(1.0, score)

    def _eval_alignment(self, steps: list, goal: str, constraints: list) -> float:
        score = 0.3
        if goal:
            score += 0.2
            # Check step-goal word overlap
            goal_words = set(goal.lower().split())
            relevant = 0
            for s in steps:
                desc = s.get("description", "") if isinstance(s, dict) else str(s)
                if set(desc.lower().split()) & goal_words:
                    relevant += 1
            if steps:
                score += 0.3 * (relevant / len(steps))
        if constraints:
            score += 0.1
        return min(1.0, score)

    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 300:
            self._history = self._history[-300:]
