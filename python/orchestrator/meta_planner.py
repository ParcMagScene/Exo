"""
EXO v11 — MetaPlanner (Planification adaptative)
Adapte les plans HTN en fonction de l'apprentissage : choix des méthodes,
ordre des sous-tâches, parallélisation, stratégies alternatives, chemins optimisés.

API:
  adapt_plan(plan)         → dict  (adapted plan)
  adapt_method(method)     → dict
  adapt_strategy(strategy) → dict
  get_stats()              → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("meta_planner")


class MetaPlanner:
    """Planificateur adaptatif EXO v11."""

    def __init__(self, meta_memory, task_optimizer=None):
        """
        Args:
            meta_memory: MetaMemory for learned strategies.
            task_optimizer: v10 TaskOptimizer for tool performance data.
        """
        self._memory = meta_memory
        self._optimizer = task_optimizer
        self._adaptations: list[dict] = []
        self._stats = {
            "plans_adapted": 0,
            "methods_adapted": 0,
            "strategies_adapted": 0,
            "steps_reordered": 0,
            "steps_parallelized": 0,
        }

    def adapt_plan(self, plan: dict) -> dict:
        """Adapt an HTN plan based on learned knowledge.

        plan: dict with 'steps' list, each step has 'tool', 'description',
              'depends_on', 'priority', 'expected_outcome'.
        Returns adapted plan with modifications applied.
        """
        steps = plan.get("steps", [])
        if not steps:
            return plan

        adapted_steps = list(steps)  # shallow copy
        modifications = []

        # 1. Reorder independent steps by learned tool reliability
        adapted_steps, reorder_mods = self._reorder_by_reliability(adapted_steps)
        modifications.extend(reorder_mods)

        # 2. Suggest parallelization for independent steps
        parallel_mods = self._suggest_parallelization(adapted_steps)
        modifications.extend(parallel_mods)

        # 3. Substitute unreliable tools with alternatives
        adapted_steps, sub_mods = self._substitute_tools(adapted_steps)
        modifications.extend(sub_mods)

        # 4. Adjust timeouts based on learned latencies
        adapted_steps, timeout_mods = self._adjust_timeouts(adapted_steps)
        modifications.extend(timeout_mods)

        result = {
            **plan,
            "steps": adapted_steps,
            "adaptations": modifications,
            "adapted_at": time.time(),
        }

        self._adaptations.append({
            "timestamp": time.time(),
            "plan_id": plan.get("plan_id", "unknown"),
            "modification_count": len(modifications),
        })
        if len(self._adaptations) > 200:
            self._adaptations = self._adaptations[-200:]

        self._stats["plans_adapted"] += 1
        log.info("Plan adapted: %d modifications", len(modifications))
        return result

    def _reorder_by_reliability(self, steps: list) -> tuple[list, list]:
        """Reorder independent steps putting most reliable first."""
        modifications = []
        if not self._optimizer:
            return steps, modifications

        # Find independent steps (no depends_on or all deps satisfied)
        independent_indices = []
        for i, step in enumerate(steps):
            deps = step.get("depends_on", [])
            if not deps:
                independent_indices.append(i)

        if len(independent_indices) <= 1:
            return steps, modifications

        # Sort independent steps by tool reliability
        def reliability_key(idx):
            tool = steps[idx].get("tool", "")
            rec = self._optimizer.get_tool_recommendation(tool)
            scores = {"reliable": 0, "moderate": 1, "unreliable": 2,
                      "avoid": 3, "no_data": 1}
            return scores.get(rec, 1)

        sorted_indices = sorted(independent_indices, key=reliability_key)
        if sorted_indices != independent_indices:
            # Build new step list with reordered independent steps
            new_steps = list(steps)
            for new_pos, old_idx in zip(independent_indices, sorted_indices):
                new_steps[new_pos] = steps[old_idx]
            modifications.append({
                "type": "reorder",
                "description": "Reordered independent steps by tool reliability",
            })
            self._stats["steps_reordered"] += 1
            return new_steps, modifications

        return steps, modifications

    def _suggest_parallelization(self, steps: list) -> list[dict]:
        """Identify steps that could run in parallel."""
        modifications = []
        parallel_groups = []
        current_group = []

        for i, step in enumerate(steps):
            deps = step.get("depends_on", [])
            if not deps:
                current_group.append(i)
            else:
                if len(current_group) > 1:
                    parallel_groups.append(list(current_group))
                current_group = []
        if len(current_group) > 1:
            parallel_groups.append(list(current_group))

        for group in parallel_groups:
            modifications.append({
                "type": "parallelize",
                "description": f"Steps {group} can run in parallel",
                "step_indices": group,
            })
            self._stats["steps_parallelized"] += len(group)

        return modifications

    def _substitute_tools(self, steps: list) -> tuple[list, list]:
        """Replace unreliable tools with better alternatives."""
        modifications = []
        # Alternative tool mapping from learned strategies
        alternatives = self._memory.meta_get("strategy")
        alt_map: dict[str, str] = {}
        for entry in alternatives:
            val = entry.get("value", {})
            if isinstance(val, dict) and val.get("feedback_type") == "negative":
                ctx = entry.get("key", "")
                # Simple heuristic: if search_web fails, try get_summary
                if "search_web" in ctx:
                    alt_map["search_web"] = "get_summary"

        if not alt_map:
            return steps, modifications

        new_steps = list(steps)
        for i, step in enumerate(new_steps):
            tool = step.get("tool", "")
            if tool in alt_map:
                new_step = dict(step)
                new_step["tool"] = alt_map[tool]
                new_step["original_tool"] = tool
                new_steps[i] = new_step
                modifications.append({
                    "type": "substitute",
                    "description": f"Replaced {tool} with {alt_map[tool]} at step {i}",
                    "step_index": i,
                })

        return new_steps, modifications

    def _adjust_timeouts(self, steps: list) -> tuple[list, list]:
        """Adjust step timeouts based on observed tool latencies."""
        modifications = []
        if not self._optimizer:
            return steps, modifications

        new_steps = list(steps)
        for i, step in enumerate(new_steps):
            tool = step.get("tool", "")
            stats = self._optimizer.get_stats()
            tool_data = stats.get("tools", {}).get(tool, {})
            avg_lat = tool_data.get("avg_latency_s", 0)

            if avg_lat > 0:
                suggested_timeout = max(5, avg_lat * 2.5)
                current_timeout = step.get("timeout_s", 30)
                if abs(suggested_timeout - current_timeout) > 3:
                    new_step = dict(step)
                    new_step["timeout_s"] = round(suggested_timeout, 1)
                    new_steps[i] = new_step
                    modifications.append({
                        "type": "timeout_adjust",
                        "description": (
                            f"Step {i} timeout adjusted to "
                            f"{suggested_timeout:.1f}s (avg={avg_lat:.1f}s)"
                        ),
                        "step_index": i,
                    })

        return new_steps, modifications

    def adapt_method(self, method: dict) -> dict:
        """Adapt an HTN method based on historical performance."""
        self._stats["methods_adapted"] += 1

        # Check if we have learned better strategies for this method
        method_name = method.get("name", "")
        learned = self._memory.meta_get(method_name)
        if learned:
            best = max(learned, key=lambda x: x.get("confidence", 0))
            return {
                **method,
                "adapted": True,
                "learned_confidence": best.get("confidence", 0),
                "learned_data": best.get("value"),
            }
        return {**method, "adapted": False}

    def adapt_strategy(self, strategy: dict) -> dict:
        """Adapt a strategy based on success/failure history."""
        self._stats["strategies_adapted"] += 1

        strategy_name = strategy.get("name", "")
        learned = self._memory.meta_get(strategy_name)
        successes = sum(1 for e in learned
                        if isinstance(e.get("value"), dict)
                        and e["value"].get("status") == "completed")
        total = len(learned) if learned else 0

        return {
            **strategy,
            "adapted": True,
            "historical_success_rate": successes / max(total, 1),
            "sample_size": total,
        }

    def get_stats(self) -> dict:
        return dict(self._stats)

    def get_adaptations(self, limit: int = 50) -> list[dict]:
        return self._adaptations[-limit:]
