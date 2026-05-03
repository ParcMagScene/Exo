"""
EXO v22 — MultiObjectivePlanner
Gère plusieurs objectifs simultanément : rapidité, fiabilité,
sécurité, coût cognitif, cohérence, précision, stabilité.

API:
  plan_multi_objectives(intent, objectives) → dict
  compute_tradeoffs(plan)                   → dict
  select_best_compromise()                  → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("multi_objective_planner")


class MultiObjectivePlanner:
    """Planificateur multi-objectifs EXO v22."""

    VALID_OBJECTIVES = {
        "speed", "reliability", "security", "cognitive_cost",
        "coherence", "precision", "stability",
    }

    def __init__(self, governance=None):
        self._governance = governance

        self._plans: list[dict] = []
        self._tradeoffs: list[dict] = []
        self._stats = {
            "plans_created": 0,
            "tradeoffs_computed": 0,
            "compromises_selected": 0,
        }

    # ── plan_multi_objectives ───────────────────────────────
    def plan_multi_objectives(self, intent: dict, objectives: dict) -> dict:
        """Créer un plan multi-objectifs."""
        self._stats["plans_created"] += 1

        goal = intent.get("goal", "")
        steps = intent.get("steps", [])
        obj_list = objectives.get("objectives", [])
        weights = objectives.get("weights", {})

        scored_objectives = []
        total_score = 0.0

        for obj in obj_list:
            name = obj if isinstance(obj, str) else obj.get("name", "")
            weight = weights.get(name, 1.0)
            # Deterministic scoring based on step count and objective type
            base_score = min(1.0, len(steps) * 0.15 + 0.3)
            if name == "security":
                base_score = min(1.0, base_score + 0.1)
            elif name == "speed":
                base_score = max(0.1, base_score - len(steps) * 0.05)

            weighted = round(base_score * weight, 3)
            scored_objectives.append({
                "name": name,
                "weight": weight,
                "score": round(base_score, 3),
                "weighted_score": weighted,
            })
            total_score += weighted

        avg = total_score / len(scored_objectives) if scored_objectives else 0.0

        plan = {
            "id": f"mop_{uuid.uuid4().hex[:8]}",
            "planned": True,
            "goal": goal,
            "steps_count": len(steps),
            "objectives": scored_objectives,
            "objectives_count": len(scored_objectives),
            "aggregate_score": round(avg, 3),
            "status": "evaluated",
            "timestamp": time.time(),
        }
        self._plans.append(plan)
        self._trim()

        return plan

    # ── compute_tradeoffs ───────────────────────────────────
    def compute_tradeoffs(self, plan: dict) -> dict:
        """Calculer les compromis entre objectifs."""
        self._stats["tradeoffs_computed"] += 1

        objectives = plan.get("objectives", [])
        tradeoffs = []

        for i, obj_a in enumerate(objectives):
            for obj_b in objectives[i + 1:]:
                conflict = abs(obj_a.get("score", 0) - obj_b.get("score", 0))
                tradeoffs.append({
                    "pair": [obj_a["name"], obj_b["name"]],
                    "conflict_level": round(conflict, 3),
                    "dominant": obj_a["name"] if obj_a.get("weighted_score", 0) >= obj_b.get("weighted_score", 0) else obj_b["name"],
                })

        result = {
            "id": f"trf_{uuid.uuid4().hex[:8]}",
            "computed": True,
            "tradeoffs": tradeoffs,
            "tradeoffs_count": len(tradeoffs),
            "max_conflict": max((t["conflict_level"] for t in tradeoffs), default=0.0),
            "timestamp": time.time(),
        }
        self._tradeoffs.append(result)
        self._trim_tradeoffs()

        return result

    # ── select_best_compromise ──────────────────────────────
    def select_best_compromise(self) -> dict:
        """Sélectionner le meilleur plan compromis."""
        self._stats["compromises_selected"] += 1

        if not self._plans:
            return {
                "selected": False,
                "error": "no_plans",
                "timestamp": time.time(),
            }

        best = max(self._plans, key=lambda p: p.get("aggregate_score", 0))

        return {
            "id": f"comp_{uuid.uuid4().hex[:8]}",
            "selected": True,
            "best_plan_id": best["id"],
            "aggregate_score": best.get("aggregate_score", 0),
            "objectives_count": best.get("objectives_count", 0),
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "multi_objective_planner",
            "status": "ok",
            "total_plans": len(self._plans),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._plans.clear()
        self._tradeoffs.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("MultiObjectivePlanner restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._plans) > 5000:
            self._plans = self._plans[-2500:]

    def _trim_tradeoffs(self) -> None:
        if len(self._tradeoffs) > 5000:
            self._tradeoffs = self._tradeoffs[-2500:]
