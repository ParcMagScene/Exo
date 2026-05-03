"""
EXO v19 — CognitivePipelineOptimizer
Optimise l'ordre, la structure et la distribution des opérations cognitives.

API:
  optimize_pipeline(pipeline: dict)  → dict
  reorder_steps(steps: dict)         → dict
  optimize_flow(flow: dict)          → dict
  health_check()                     → dict
  restart()                          → None
  get_stats()                        → dict
"""

import logging
import time
import uuid

log = logging.getLogger("cognitive_pipeline_optimizer")


class CognitivePipelineOptimizer:
    """Optimiseur de pipeline cognitif EXO v19."""

    def __init__(self, layer_stack=None, meta_optimizer=None,
                 governance=None):
        self._stack = layer_stack
        self._meta = meta_optimizer
        self._governance = governance

        self._history: list[dict] = []
        self._stats = {
            "pipelines_optimized": 0,
            "steps_reordered": 0,
            "flows_optimized": 0,
        }

    # ── optimize_pipeline ───────────────────────────────────
    def optimize_pipeline(self, pipeline: dict) -> dict:
        """Optimiser un pipeline cognitif complet."""
        self._stats["pipelines_optimized"] += 1

        steps = pipeline.get("steps", [])
        name = pipeline.get("name", "default")

        optimized = []
        removed = []

        for i, step in enumerate(steps):
            cost = step.get("cost", 1.0)
            required = step.get("required", True)

            if not required and cost > 2.0:
                removed.append({
                    "step": step.get("name", f"step_{i}"),
                    "reason": "optional_high_cost",
                    "cost": cost,
                })
            else:
                optimized.append(step)

        # Trier par priorité, puis par coût
        optimized.sort(key=lambda s: (
            -s.get("priority", 0), s.get("cost", 1.0)
        ))

        record = {
            "id": f"op_{uuid.uuid4().hex[:8]}",
            "optimized": True,
            "pipeline_name": name,
            "original_steps": len(steps),
            "optimized_steps": len(optimized),
            "removed_steps": removed,
            "steps": optimized,
            "gain_pct": round(
                (1 - len(optimized) / max(len(steps), 1)) * 100, 1
            ),
            "timestamp": time.time(),
        }
        self._history.append(record)
        self._trim()
        return record

    # ── reorder_steps ───────────────────────────────────────
    def reorder_steps(self, steps: dict) -> dict:
        """Réordonner les étapes d'un pipeline pour efficacité."""
        self._stats["steps_reordered"] += 1

        items = steps.get("items", [])
        strategy = steps.get("strategy", "cost_first")

        if strategy == "cost_first":
            reordered = sorted(items,
                               key=lambda s: s.get("cost", 1.0))
        elif strategy == "priority_first":
            reordered = sorted(items,
                               key=lambda s: -s.get("priority", 0))
        elif strategy == "dependency_first":
            # Les étapes sans dépendances passent en premier
            reordered = sorted(items,
                               key=lambda s: len(s.get("deps", [])))
        else:
            reordered = list(items)

        return {
            "id": f"rs_{uuid.uuid4().hex[:8]}",
            "reordered": True,
            "strategy": strategy,
            "original_count": len(items),
            "reordered_steps": reordered,
            "timestamp": time.time(),
        }

    # ── optimize_flow ───────────────────────────────────────
    def optimize_flow(self, flow: dict) -> dict:
        """Optimiser un flux de données entre composants cognitifs."""
        self._stats["flows_optimized"] += 1

        edges = flow.get("edges", [])
        flow_name = flow.get("name", "default")

        optimized_edges = []
        merged = []

        seen = {}
        for edge in edges:
            key = (edge.get("from"), edge.get("to"))
            if key in seen:
                # Fusionner les données
                merged.append({
                    "edge": key,
                    "reason": "duplicate_eliminated",
                })
            else:
                seen[key] = True
                optimized_edges.append(edge)

        return {
            "id": f"of_{uuid.uuid4().hex[:8]}",
            "optimized": True,
            "flow_name": flow_name,
            "original_edges": len(edges),
            "optimized_edges": len(optimized_edges),
            "merged": merged,
            "edges": optimized_edges,
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "cognitive_pipeline_optimizer",
            "status": "ok",
            "history": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("CognitivePipelineOptimizer restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
