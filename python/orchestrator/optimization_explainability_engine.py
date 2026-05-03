"""
EXO v19 — OptimizationExplainabilityEngine
Explique les optimisations appliquées, les compromis et les gains.

API:
  explain_optimization()          → dict
  explain_tradeoffs()             → dict
  explain_performance_gain()      → dict
  health_check()                  → dict
  restart()                       → None
  get_stats()                     → dict
"""

import logging
import time
import uuid

log = logging.getLogger("optimization_explainability_engine")


class OptimizationExplainabilityEngine:
    """Moteur d'explicabilité des optimisations EXO v19."""

    def __init__(self, meta_optimizer=None, multi_objective=None,
                 profiling=None, governance=None):
        self._meta = meta_optimizer
        self._multi = multi_objective
        self._profiling = profiling
        self._governance = governance

        self._explanations: list[dict] = []
        self._stats = {
            "optimizations_explained": 0,
            "tradeoffs_explained": 0,
            "gains_explained": 0,
        }

    # ── explain_optimization ────────────────────────────────
    def explain_optimization(self) -> dict:
        """Expliquer les dernières optimisations appliquées."""
        self._stats["optimizations_explained"] += 1

        explanations = []

        # Récupérer l'historique du meta_optimizer
        if self._meta:
            try:
                history = self._meta.get_optimization_history()
                for opt in history[-5:]:
                    proposals = opt.get("proposals", [])
                    for p in proposals[:3]:
                        explanations.append({
                            "source": "meta_optimizer",
                            "optimization_id": opt.get("id", "?"),
                            "target": p.get("target", "?"),
                            "action": p.get("action", "?"),
                            "description": p.get("description", "?"),
                            "priority": p.get("priority", "medium"),
                            "estimated_gain_pct": p.get(
                                "estimated_gain_pct", 0),
                        })
            except Exception:
                pass

        # Récupérer la dernière solution multi-objectifs
        if self._multi:
            try:
                sol = self._multi.select_optimal_solution()
                if sol.get("selected"):
                    explanations.append({
                        "source": "multi_objective_optimizer",
                        "optimization_id": sol.get("id", "?"),
                        "target": "system",
                        "action": "select_solution",
                        "description": (
                            f"Solution '{sol['solution']}' sélectionnée "
                            f"(score: {sol['score']})"
                        ),
                        "priority": "high",
                    })
            except Exception:
                pass

        record = {
            "id": f"eo_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "explanations": explanations,
            "total": len(explanations),
            "timestamp": time.time(),
        }
        self._explanations.append(record)
        self._trim()
        return record

    # ── explain_tradeoffs ───────────────────────────────────
    def explain_tradeoffs(self) -> dict:
        """Expliquer les compromis faits entre objectifs."""
        self._stats["tradeoffs_explained"] += 1

        tradeoff_explanations = [
            {
                "tradeoff": "speed_vs_precision",
                "explanation": (
                    "Une optimisation de vitesse réduit le nombre d'étapes "
                    "de raisonnement, ce qui peut diminuer la précision. "
                    "EXO compense via le cache et les heuristiques adaptatives."
                ),
                "mitigation": "Cache local + fallback symbolique",
            },
            {
                "tradeoff": "cost_vs_reliability",
                "explanation": (
                    "Réduire le coût cognitif (moins d'appels LLM) peut "
                    "augmenter le risque d'erreur. EXO utilise des règles "
                    "locales comme filet de sécurité."
                ),
                "mitigation": "Règles symboliques v14 + gouvernance v11",
            },
            {
                "tradeoff": "speed_vs_security",
                "explanation": (
                    "Les vérifications de sécurité ajoutent de la latence. "
                    "EXO ne compromet jamais la sécurité."
                ),
                "mitigation": "Sécurité non-négociable (v11 governance)",
            },
        ]

        return {
            "id": f"et_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "tradeoffs": tradeoff_explanations,
            "total": len(tradeoff_explanations),
            "principle": (
                "Sécurité et gouvernance (v11) sont toujours prioritaires "
                "et non-négociables."
            ),
            "timestamp": time.time(),
        }

    # ── explain_performance_gain ────────────────────────────
    def explain_performance_gain(self) -> dict:
        """Expliquer les gains de performance obtenus."""
        self._stats["gains_explained"] += 1

        gains = []

        # Récupérer le profil système
        if self._profiling:
            try:
                profile = self._profiling.profile_system()
                hotspots = profile.get("hotspots", [])
                if hotspots:
                    gains.append({
                        "area": "hotspot_detection",
                        "description": (
                            f"{len(hotspots)} point(s) chaud(s) identifié(s)"
                        ),
                        "action_taken": "Profilage et priorisation",
                        "estimated_improvement_pct": 10 * len(hotspots),
                    })
            except Exception:
                pass

        # Récupérer les stats du meta-optimizer
        if self._meta:
            try:
                stats = self._meta.get_stats()
                opt_count = stats.get("optimizations_proposed", 0)
                if opt_count > 0:
                    gains.append({
                        "area": "optimizations_proposed",
                        "description": (
                            f"{opt_count} optimisation(s) proposée(s)"
                        ),
                        "action_taken": "Analyse globale du système",
                        "estimated_improvement_pct": min(opt_count * 5, 50),
                    })
            except Exception:
                pass

        total_gain = sum(g.get("estimated_improvement_pct", 0)
                         for g in gains)

        return {
            "id": f"eg_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "gains": gains,
            "total_gains": len(gains),
            "estimated_total_improvement_pct": min(total_gain, 80),
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "optimization_explainability",
            "status": "ok",
            "explanations": len(self._explanations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._explanations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("OptimizationExplainabilityEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._explanations) > 5000:
            self._explanations = self._explanations[-5000:]
