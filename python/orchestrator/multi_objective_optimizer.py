"""
EXO v19 — MultiObjectiveOptimizer
Optimise selon plusieurs objectifs simultanés :
  vitesse, fiabilité, cohérence, coût cognitif, stabilité, précision, sécurité.

API:
  optimize_for(criteria: dict)          → dict
  compute_tradeoffs(criteria: dict)     → dict
  select_optimal_solution()             → dict
  health_check()                        → dict
  restart()                             → None
  get_stats()                           → dict
"""

import logging
import time
import uuid

log = logging.getLogger("multi_objective_optimizer")

_OBJECTIVES = [
    "speed", "reliability", "coherence",
    "cognitive_cost", "stability", "precision", "security",
]


class MultiObjectiveOptimizer:
    """Optimiseur multi-objectifs EXO v19."""

    def __init__(self, meta_optimizer=None, heuristics=None,
                 governance=None):
        self._meta = meta_optimizer
        self._heuristics = heuristics
        self._governance = governance

        self._solutions: list[dict] = []
        self._pareto_front: list[dict] = []
        self._stats = {
            "optimizations": 0,
            "tradeoffs_computed": 0,
            "solutions_selected": 0,
        }

    # ── optimize_for ────────────────────────────────────────
    def optimize_for(self, criteria: dict) -> dict:
        """Optimiser pour des critères pondérés donnés."""
        self._stats["optimizations"] += 1

        weights = {}
        for obj in _OBJECTIVES:
            weights[obj] = criteria.get(obj, 0.5)

        # Normaliser
        total = sum(weights.values())
        if total > 0:
            weights = {k: round(v / total, 4) for k, v in weights.items()}

        # Générer des solutions candidates
        solutions = []
        configs = [
            {"name": "speed_optimized",
             "scores": {"speed": 0.95, "reliability": 0.6,
                        "coherence": 0.7, "cognitive_cost": 0.4,
                        "stability": 0.6, "precision": 0.5,
                        "security": 0.8}},
            {"name": "balanced",
             "scores": {"speed": 0.7, "reliability": 0.7,
                        "coherence": 0.7, "cognitive_cost": 0.7,
                        "stability": 0.7, "precision": 0.7,
                        "security": 0.8}},
            {"name": "precision_optimized",
             "scores": {"speed": 0.5, "reliability": 0.8,
                        "coherence": 0.9, "cognitive_cost": 0.3,
                        "stability": 0.8, "precision": 0.95,
                        "security": 0.85}},
            {"name": "security_optimized",
             "scores": {"speed": 0.5, "reliability": 0.85,
                        "coherence": 0.7, "cognitive_cost": 0.5,
                        "stability": 0.85, "precision": 0.7,
                        "security": 0.98}},
        ]

        for cfg in configs:
            score = sum(
                weights.get(obj, 0) * cfg["scores"].get(obj, 0.5)
                for obj in _OBJECTIVES
            )
            solutions.append({
                "name": cfg["name"],
                "scores": cfg["scores"],
                "weighted_score": round(score, 4),
            })

        solutions.sort(key=lambda s: -s["weighted_score"])

        record = {
            "id": f"mo_{uuid.uuid4().hex[:8]}",
            "optimized": True,
            "weights": weights,
            "solutions": solutions,
            "best": solutions[0]["name"] if solutions else None,
            "best_score": solutions[0]["weighted_score"] if solutions else 0,
            "timestamp": time.time(),
        }
        self._solutions.append(record)
        self._trim()
        return record

    # ── compute_tradeoffs ───────────────────────────────────
    def compute_tradeoffs(self, criteria: dict) -> dict:
        """Calculer les compromis entre objectifs contradictoires."""
        self._stats["tradeoffs_computed"] += 1

        tradeoffs = []

        speed_w = criteria.get("speed", 0.5)
        precision_w = criteria.get("precision", 0.5)
        if speed_w > 0.7 and precision_w > 0.7:
            tradeoffs.append({
                "conflict": ("speed", "precision"),
                "description": "Vitesse et précision sont antagonistes",
                "recommendation": "Réduire l'un ou paralléliser",
                "severity": "high",
            })

        cost_w = criteria.get("cognitive_cost", 0.5)
        reliability_w = criteria.get("reliability", 0.5)
        if cost_w > 0.7 and reliability_w > 0.7:
            tradeoffs.append({
                "conflict": ("cognitive_cost", "reliability"),
                "description": (
                    "Coût cognitif bas et fiabilité haute "
                    "nécessitent plus de ressources"
                ),
                "recommendation": "Optimiser via mise en cache",
                "severity": "medium",
            })

        security_w = criteria.get("security", 0.5)
        if speed_w > 0.7 and security_w > 0.7:
            tradeoffs.append({
                "conflict": ("speed", "security"),
                "description": (
                    "Les vérifications de sécurité ajoutent de la latence"
                ),
                "recommendation": "Sécurité non-négociable, optimiser les checks",
                "severity": "low",
            })

        return {
            "id": f"ct_{uuid.uuid4().hex[:8]}",
            "computed": True,
            "tradeoffs": tradeoffs,
            "total": len(tradeoffs),
            "criteria": criteria,
            "timestamp": time.time(),
        }

    # ── select_optimal_solution ─────────────────────────────
    def select_optimal_solution(self) -> dict:
        """Sélectionner la meilleure solution parmi les optimisations passées."""
        self._stats["solutions_selected"] += 1

        if not self._solutions:
            return {
                "id": f"so_{uuid.uuid4().hex[:8]}",
                "selected": False,
                "reason": "no_solutions_available",
                "timestamp": time.time(),
            }

        latest = self._solutions[-1]
        best = latest.get("best", "balanced")
        score = latest.get("best_score", 0)

        return {
            "id": f"so_{uuid.uuid4().hex[:8]}",
            "selected": True,
            "solution": best,
            "score": score,
            "from_optimization": latest["id"],
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "multi_objective_optimizer",
            "status": "ok",
            "solutions": len(self._solutions),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._solutions.clear()
        self._pareto_front.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("MultiObjectiveOptimizer restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._solutions) > 5000:
            self._solutions = self._solutions[-5000:]
