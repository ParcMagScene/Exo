"""
EXO v22 — StrategicArbitrationEngine
Arbitre entre plusieurs plans candidats selon des critères multiples :
multi-critères, contextuel, sécurité, cohérence, performance.

API:
  arbitrate(plans: list)        → dict
  explain_arbitration()         → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("strategic_arbitration_engine")


class StrategicArbitrationEngine:
    """Moteur d'arbitrage stratégique EXO v22."""

    CRITERIA = {
        "feasibility": 0.25,
        "coherence": 0.20,
        "security": 0.20,
        "performance": 0.15,
        "simplicity": 0.10,
        "explainability": 0.10,
    }

    def __init__(self, governance=None):
        self._governance = governance

        self._arbitrations: list[dict] = []
        self._stats = {
            "arbitrations": 0,
            "explanations": 0,
        }

    # ── arbitrate ───────────────────────────────────────────
    def arbitrate(self, plans: list) -> dict:
        """Arbitrer entre plusieurs plans candidats."""
        self._stats["arbitrations"] += 1

        if not plans:
            return {
                "arbitrated": False,
                "error": "no_plans",
                "timestamp": time.time(),
            }

        scored = []
        for plan in plans:
            scores = self._evaluate_plan(plan)
            weighted = sum(
                scores.get(c, 0.0) * w
                for c, w in self.CRITERIA.items()
            )
            scored.append({
                "plan_id": plan.get("id", f"plan_{uuid.uuid4().hex[:6]}"),
                "criteria_scores": scores,
                "weighted_score": round(weighted, 4),
            })

        scored.sort(key=lambda s: s["weighted_score"], reverse=True)

        result = {
            "id": f"arb_{uuid.uuid4().hex[:8]}",
            "arbitrated": True,
            "candidates_count": len(scored),
            "ranking": scored,
            "winner": scored[0],
            "timestamp": time.time(),
        }
        self._arbitrations.append(result)
        self._trim()

        return result

    # ── explain_arbitration ─────────────────────────────────
    def explain_arbitration(self) -> dict:
        """Expliquer la dernière décision d'arbitrage."""
        self._stats["explanations"] += 1

        if not self._arbitrations:
            return {
                "explained": False,
                "error": "no_arbitrations",
                "timestamp": time.time(),
            }

        last = self._arbitrations[-1]
        winner = last["winner"]
        reasons = [
            f"Plan gagnant : {winner['plan_id']} "
            f"(score pondéré : {winner['weighted_score']}).",
        ]

        for c, w in self.CRITERIA.items():
            val = winner["criteria_scores"].get(c, 0.0)
            reasons.append(
                f"  {c} : {val:.2f} (poids {w:.0%})."
            )

        reasons.append(
            f"Total candidats évalués : {last['candidates_count']}."
        )

        return {
            "id": f"earb_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "winner": winner["plan_id"],
            "reasons": reasons,
            "timestamp": time.time(),
        }

    # ── internal helpers ────────────────────────────────────
    def _evaluate_plan(self, plan: dict) -> dict:
        """Évaluation déterministe d'un plan sur chaque critère."""
        steps = plan.get("steps", [])
        n = len(steps)

        feasibility = 1.0 if plan.get("feasible", True) else 0.3

        coherence = max(0.0, 1.0 - n * 0.03)

        security = 1.0
        for step in steps:
            if "externe" in step.get("action", ""):
                security -= 0.15

        performance = max(0.2, 1.0 - n * 0.05)

        simplicity = max(0.0, 1.0 - n * 0.08)

        explainability = 1.0 if n <= 5 else max(0.3, 1.0 - (n - 5) * 0.1)

        return {
            "feasibility": round(max(0.0, feasibility), 3),
            "coherence": round(max(0.0, coherence), 3),
            "security": round(max(0.0, min(1.0, security)), 3),
            "performance": round(max(0.0, performance), 3),
            "simplicity": round(max(0.0, simplicity), 3),
            "explainability": round(max(0.0, explainability), 3),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "strategic_arbitration_engine",
            "status": "ok",
            "total_arbitrations": len(self._arbitrations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._arbitrations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("StrategicArbitrationEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._arbitrations) > 5000:
            self._arbitrations = self._arbitrations[-2500:]
