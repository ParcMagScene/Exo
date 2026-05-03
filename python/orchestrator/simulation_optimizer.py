"""
EXO v19 — SimulationOptimizer
Réduit le coût de simulation en élaguant l'arbre et en sélectionnant
les scénarios pertinents.

API:
  optimize_simulation(sim: dict)         → dict
  prune_simulation_tree(tree: dict)      → dict
  select_relevant_scenarios()            → dict
  health_check()                         → dict
  restart()                              → None
  get_stats()                            → dict
"""

import logging
import time
import uuid

log = logging.getLogger("simulation_optimizer")


class SimulationOptimizer:
    """Optimiseur de simulations EXO v19."""

    def __init__(self, meta_optimizer=None, profiling=None,
                 governance=None):
        self._meta = meta_optimizer
        self._profiling = profiling
        self._governance = governance

        self._history: list[dict] = []
        self._stats = {
            "simulations_optimized": 0,
            "trees_pruned": 0,
            "scenarios_selected": 0,
        }

    # ── optimize_simulation ─────────────────────────────────
    def optimize_simulation(self, sim: dict) -> dict:
        """Optimiser une simulation pour réduire le coût."""
        self._stats["simulations_optimized"] += 1

        scenarios = sim.get("scenarios", [])
        sim_name = sim.get("name", "default")
        max_depth = sim.get("max_depth", 10)

        optimized = []
        skipped = []

        for scenario in scenarios:
            probability = scenario.get("probability", 0.5)
            depth = scenario.get("depth", 1)

            # Élaguer les scénarios improbables à grande profondeur
            if probability < 0.05 and depth > 3:
                skipped.append({
                    "scenario": scenario.get("name", "?"),
                    "reason": "low_probability_deep",
                    "probability": probability,
                    "depth": depth,
                })
            elif probability < 0.01:
                skipped.append({
                    "scenario": scenario.get("name", "?"),
                    "reason": "negligible_probability",
                    "probability": probability,
                })
            else:
                optimized.append(scenario)

        # Limiter la profondeur maximale
        effective_depth = min(max_depth, 8)

        record = {
            "id": f"os_{uuid.uuid4().hex[:8]}",
            "optimized": True,
            "simulation_name": sim_name,
            "original_scenarios": len(scenarios),
            "optimized_scenarios": len(optimized),
            "skipped": skipped,
            "max_depth": effective_depth,
            "scenarios": optimized,
            "cost_reduction_pct": round(
                (1 - len(optimized) / max(len(scenarios), 1)) * 100, 1
            ),
            "timestamp": time.time(),
        }
        self._history.append(record)
        self._trim()
        return record

    # ── prune_simulation_tree ───────────────────────────────
    def prune_simulation_tree(self, tree: dict) -> dict:
        """Élaguer un arbre de simulation."""
        self._stats["trees_pruned"] += 1

        nodes = tree.get("nodes", [])
        threshold = tree.get("prune_threshold", 0.1)

        kept = []
        pruned = []

        for node in nodes:
            value = node.get("value", 0.5)
            if value < threshold:
                pruned.append({
                    "node": node.get("name", "?"),
                    "value": value,
                    "threshold": threshold,
                })
            else:
                kept.append(node)

        return {
            "id": f"pt_{uuid.uuid4().hex[:8]}",
            "pruned": True,
            "original_nodes": len(nodes),
            "kept_nodes": len(kept),
            "pruned_nodes": pruned,
            "total_pruned": len(pruned),
            "nodes": kept,
            "reduction_pct": round(
                (1 - len(kept) / max(len(nodes), 1)) * 100, 1
            ),
            "timestamp": time.time(),
        }

    # ── select_relevant_scenarios ───────────────────────────
    def select_relevant_scenarios(self) -> dict:
        """Sélectionner les scénarios de simulation les plus pertinents."""
        self._stats["scenarios_selected"] += 1

        # Scénarios par défaut pertinents pour un assistant vocal
        scenarios = [
            {
                "name": "commande_simple",
                "description": "Commande vocale directe (allumer/éteindre)",
                "priority": "high",
                "probability": 0.7,
                "depth": 2,
            },
            {
                "name": "question_complexe",
                "description": "Question nécessitant raisonnement multi-étapes",
                "priority": "medium",
                "probability": 0.2,
                "depth": 5,
            },
            {
                "name": "dialogue_multi_tours",
                "description": "Conversation contextuelle multi-tours",
                "priority": "medium",
                "probability": 0.08,
                "depth": 8,
            },
            {
                "name": "erreur_et_correction",
                "description": "Mauvaise compréhension et correction",
                "priority": "high",
                "probability": 0.15,
                "depth": 3,
            },
        ]

        return {
            "id": f"sr_{uuid.uuid4().hex[:8]}",
            "selected": True,
            "scenarios": scenarios,
            "total": len(scenarios),
            "coverage_pct": round(
                sum(s["probability"] for s in scenarios) * 100, 1
            ),
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "simulation_optimizer",
            "status": "ok",
            "history": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("SimulationOptimizer restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
