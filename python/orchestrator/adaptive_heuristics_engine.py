"""
EXO v19 — AdaptiveHeuristicsEngine
Adapte dynamiquement les stratégies cognitives selon les performances observées.

API:
  update_heuristics()                  → dict
  select_best_strategy(task: dict)     → dict
  adapt_to_context(context: dict)      → dict
  health_check()                       → dict
  restart()                            → None
  get_stats()                          → dict
"""

import logging
import time
import uuid

log = logging.getLogger("adaptive_heuristics_engine")


class AdaptiveHeuristicsEngine:
    """Moteur d'heuristiques adaptatives EXO v19."""

    def __init__(self, meta_optimizer=None, priority_engine=None,
                 governance=None):
        self._meta = meta_optimizer
        self._priority = priority_engine
        self._governance = governance

        self._strategies: list[dict] = [
            {"name": "speed_first", "weight": 0.5,
             "description": "Privilégier la vitesse de réponse"},
            {"name": "accuracy_first", "weight": 0.3,
             "description": "Privilégier la précision"},
            {"name": "balanced", "weight": 0.2,
             "description": "Équilibre vitesse/précision"},
        ]
        self._history: list[dict] = []
        self._stats = {
            "heuristic_updates": 0,
            "strategy_selections": 0,
            "context_adaptations": 0,
        }

    # ── update_heuristics ───────────────────────────────────
    def update_heuristics(self) -> dict:
        """Mettre à jour les poids des heuristiques selon les données."""
        self._stats["heuristic_updates"] += 1

        adjustments = []
        # Si le meta_optimizer signale des latences élevées,
        # augmenter le poids de speed_first
        if self._meta:
            try:
                ineff = self._meta.detect_inefficiencies()
                bottlenecks = ineff.get("bottlenecks", 0)
                if bottlenecks > 0:
                    for s in self._strategies:
                        if s["name"] == "speed_first":
                            old_w = s["weight"]
                            s["weight"] = min(0.9, s["weight"] + 0.1)
                            adjustments.append({
                                "strategy": s["name"],
                                "old_weight": old_w,
                                "new_weight": s["weight"],
                                "reason": f"{bottlenecks} bottleneck(s) detected",
                            })
                        elif s["name"] == "accuracy_first":
                            old_w = s["weight"]
                            s["weight"] = max(0.05, s["weight"] - 0.05)
                            adjustments.append({
                                "strategy": s["name"],
                                "old_weight": old_w,
                                "new_weight": s["weight"],
                                "reason": "adjusted for bottleneck compensation",
                            })
            except Exception:
                log.debug("strategy weight adjustment failed", exc_info=True)

        # Normaliser les poids
        total = sum(s["weight"] for s in self._strategies)
        if total > 0:
            for s in self._strategies:
                s["weight"] = round(s["weight"] / total, 4)

        record = {
            "id": f"hu_{uuid.uuid4().hex[:8]}",
            "updated": True,
            "adjustments": adjustments,
            "strategies": [dict(s) for s in self._strategies],
            "timestamp": time.time(),
        }
        self._history.append(record)
        self._trim()
        return record

    # ── select_best_strategy ────────────────────────────────
    def select_best_strategy(self, task: dict) -> dict:
        """Sélectionner la meilleure stratégie pour une tâche."""
        self._stats["strategy_selections"] += 1

        task_type = task.get("type", "general")
        urgency = task.get("urgency", "normal")

        # Sélection par poids + contexte
        candidates = list(self._strategies)

        if urgency == "high":
            # Favoriser speed_first pour les tâches urgentes
            for c in candidates:
                if c["name"] == "speed_first":
                    c = dict(c)
                    c["weight"] = c["weight"] * 2.0
        elif task_type in ("analysis", "reasoning"):
            # Favoriser accuracy_first pour l'analyse
            for c in candidates:
                if c["name"] == "accuracy_first":
                    c = dict(c)
                    c["weight"] = c["weight"] * 1.5

        best = max(candidates, key=lambda s: s["weight"])

        return {
            "id": f"ss_{uuid.uuid4().hex[:8]}",
            "selected": True,
            "strategy": best["name"],
            "weight": best["weight"],
            "task_type": task_type,
            "urgency": urgency,
            "description": best["description"],
            "timestamp": time.time(),
        }

    # ── adapt_to_context ────────────────────────────────────
    def adapt_to_context(self, context: dict) -> dict:
        """Adapter les heuristiques en fonction du contexte actuel."""
        self._stats["context_adaptations"] += 1

        load = context.get("system_load", 0.5)
        error_rate = context.get("error_rate", 0.0)
        response_time_ms = context.get("avg_response_ms", 50)

        adaptations = []

        if load > 0.8:
            adaptations.append({
                "action": "reduce_complexity",
                "reason": f"System load high ({load:.2f})",
                "recommendation": "Simplifier les pipelines actifs",
            })
        if error_rate > 0.1:
            adaptations.append({
                "action": "increase_reliability",
                "reason": f"Error rate elevated ({error_rate:.2%})",
                "recommendation": "Activer fallbacks et retries",
            })
        if response_time_ms > 200:
            adaptations.append({
                "action": "optimize_speed",
                "reason": f"Response time high ({response_time_ms}ms)",
                "recommendation": "Réduire le nombre d'étapes cognitives",
            })

        return {
            "id": f"ac_{uuid.uuid4().hex[:8]}",
            "adapted": True,
            "adaptations": adaptations,
            "total": len(adaptations),
            "context_summary": {
                "load": load,
                "error_rate": error_rate,
                "response_time_ms": response_time_ms,
            },
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "adaptive_heuristics",
            "status": "ok",
            "strategies": len(self._strategies),
            "history": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._strategies = [
            {"name": "speed_first", "weight": 0.5,
             "description": "Privilégier la vitesse de réponse"},
            {"name": "accuracy_first", "weight": 0.3,
             "description": "Privilégier la précision"},
            {"name": "balanced", "weight": 0.2,
             "description": "Équilibre vitesse/précision"},
        ]
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("AdaptiveHeuristicsEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
