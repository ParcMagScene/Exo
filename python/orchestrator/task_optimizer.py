"""
EXO v10 — TaskOptimizer
Module d'optimisation des plans d'exécution basé sur l'apprentissage.

Enregistre les résultats d'exécution (latences, succès/échecs)
et utilise ces données pour optimiser les plans futurs.

API:
  optimize(plan)                → dict (plan optimisé)
  record_outcome(step, result)  → None
  get_stats()                   → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("task_optimizer")


class TaskOptimizer:
    """Optimizes task plans based on historical execution data."""

    def __init__(self) -> None:
        # tool → list of {success, latency_s, timestamp}
        self._tool_history: dict[str, list[dict]] = {}
        # tool → cached stats
        self._tool_stats: dict[str, dict] = {}

    def optimize(self, plan: dict) -> dict:
        """Optimize a plan based on historical performance data.

        Reorders steps for efficiency, adjusts timeouts, and
        flags unreliable tools. Returns the optimized plan.
        """
        steps = plan.get("steps", [])
        if not steps:
            return plan

        optimized_steps = []
        for step in steps:
            opt_step = dict(step)
            tool = step.get("tool", "")

            stats = self._get_tool_stats(tool)
            if stats:
                # Adjust timeout based on observed latency
                avg_latency = stats.get("avg_latency_s", 30.0)
                opt_step["timeout"] = max(5.0, avg_latency * 2.0)

                # Adjust priority based on reliability
                success_rate = stats.get("success_rate", 1.0)
                if success_rate < 0.5:
                    opt_step["reliability_warning"] = True
                    opt_step["priority"] = max(1, step.get("priority", 5) - 1)

                # Add performance hints
                opt_step["performance"] = {
                    "avg_latency_s": round(avg_latency, 3),
                    "success_rate": round(success_rate, 3),
                    "sample_count": stats.get("count", 0),
                }

            optimized_steps.append(opt_step)

        # Reorder: put fast, reliable steps first (when no dependency conflicts)
        optimized_steps = self._reorder_for_efficiency(optimized_steps)

        optimized = dict(plan)
        optimized["steps"] = optimized_steps
        optimized["optimized"] = True
        return optimized

    def record_outcome(self, step: dict, success: bool,
                       latency_s: float = 0.0, error: str = "") -> None:
        """Record the outcome of a step execution for future optimization."""
        tool = step.get("tool", "")
        if not tool:
            return

        record = {
            "success": success,
            "latency_s": latency_s,
            "timestamp": time.time(),
            "error": error,
        }

        if tool not in self._tool_history:
            self._tool_history[tool] = []

        self._tool_history[tool].append(record)

        # Keep only last 100 records per tool
        if len(self._tool_history[tool]) > 100:
            self._tool_history[tool] = self._tool_history[tool][-100:]

        # Invalidate cached stats
        self._tool_stats.pop(tool, None)

        log.info("Recorded outcome for %s: success=%s latency=%.3fs",
                 tool, success, latency_s)

    def get_stats(self) -> dict:
        """Get overall optimization statistics."""
        all_tools: dict[str, dict] = {}
        for tool in self._tool_history:
            all_tools[tool] = self._get_tool_stats(tool)

        total_records = sum(len(h) for h in self._tool_history.values())

        return {
            "total_records": total_records,
            "tools_tracked": len(self._tool_history),
            "tools": all_tools,
        }

    def get_tool_recommendation(self, tool: str) -> dict:
        """Get recommendation for a specific tool based on history."""
        stats = self._get_tool_stats(tool)
        if not stats:
            return {"tool": tool, "recommendation": "no_data", "confidence": 0.0}

        sr = stats.get("success_rate", 0.0)
        if sr >= 0.9:
            rec = "reliable"
        elif sr >= 0.7:
            rec = "moderate"
        elif sr >= 0.4:
            rec = "unreliable"
        else:
            rec = "avoid"

        return {
            "tool": tool,
            "recommendation": rec,
            "confidence": min(1.0, stats.get("count", 0) / 10),
            "stats": stats,
        }

    # ── Internal ─────────────────────────────────────

    def _get_tool_stats(self, tool: str) -> dict:
        """Compute stats for a tool (cached)."""
        if tool in self._tool_stats:
            return self._tool_stats[tool]

        history = self._tool_history.get(tool, [])
        if not history:
            return {}

        successes = sum(1 for r in history if r["success"])
        latencies = [r["latency_s"] for r in history if r["latency_s"] > 0]

        stats = {
            "count": len(history),
            "success_rate": successes / len(history),
            "avg_latency_s": sum(latencies) / len(latencies) if latencies else 0.0,
            "min_latency_s": min(latencies) if latencies else 0.0,
            "max_latency_s": max(latencies) if latencies else 0.0,
            "recent_success_rate": self._recent_success_rate(history),
        }

        self._tool_stats[tool] = stats
        return stats

    def _recent_success_rate(self, history: list[dict], last_n: int = 10) -> float:
        """Success rate over the most recent N executions."""
        recent = history[-last_n:]
        if not recent:
            return 0.0
        return sum(1 for r in recent if r["success"]) / len(recent)

    def _reorder_for_efficiency(self, steps: list[dict]) -> list[dict]:
        """Reorder steps for efficiency without breaking dependencies.

        Steps with no dependencies are sorted by estimated latency (fastest first).
        Steps with dependencies keep their relative order.
        """
        independent = []
        dependent = []

        for step in steps:
            deps = step.get("depends_on", [])
            if deps:
                dependent.append(step)
            else:
                independent.append(step)

        # Sort independent steps: fast + reliable first
        independent.sort(key=lambda s: s.get("timeout", 30.0))

        # Merge: independent first, then dependent in original order
        return independent + dependent
