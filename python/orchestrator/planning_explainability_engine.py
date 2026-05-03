"""
EXO v22 — PlanningExplainabilityEngine
Explique de manière déterministe les plans, arbitrages,
contraintes et scénarios de la planification stratégique.

API:
  explain_plan(plan: dict)           → dict
  explain_scenario(scenario: dict)   → dict
  explain_decision()                 → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("planning_explainability_engine")


class PlanningExplainabilityEngine:
    """Moteur d'explicabilité de planification EXO v22."""

    def __init__(self, governance=None, arbitration=None, coherence=None):
        self._governance = governance
        self._arbitration = arbitration
        self._coherence = coherence

        self._explanations: list[dict] = []
        self._stats = {
            "plan_explanations": 0,
            "scenario_explanations": 0,
            "decision_explanations": 0,
        }

    # ── explain_plan ────────────────────────────────────────
    def explain_plan(self, plan: dict) -> dict:
        """Expliquer la structure et la logique d'un plan."""
        self._stats["plan_explanations"] += 1

        steps = plan.get("steps", [])
        plan_id = plan.get("id", "unknown")
        goal = plan.get("goal", "unknown")

        reasons = [
            f"Plan '{plan_id}' visant l'objectif : {goal}.",
            f"Nombre d'étapes : {len(steps)}.",
        ]

        for i, step in enumerate(steps):
            action = step.get("action", "inconnue")
            target = step.get("target", "non spécifié")
            reasons.append(f"  Étape {i + 1} : {action} → {target}.")

        if plan.get("feasible") is not None:
            if plan["feasible"]:
                reasons.append("Le plan est jugé faisable.")
            else:
                reasons.append("Le plan n'est PAS faisable.")

        result = {
            "id": f"ep_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "plan_id": plan_id,
            "reasons": reasons,
            "timestamp": time.time(),
        }
        self._explanations.append(result)
        self._trim()

        return result

    # ── explain_scenario ────────────────────────────────────
    def explain_scenario(self, scenario: dict) -> dict:
        """Expliquer un scénario donné."""
        self._stats["scenario_explanations"] += 1

        sc_id = scenario.get("id", "unknown")
        sc_type = scenario.get("type", "unknown")
        score = scenario.get("score", 0.0)
        steps = scenario.get("steps", [])

        reasons = [
            f"Scénario '{sc_id}' de type '{sc_type}'.",
            f"Score : {score}.",
            f"Nombre d'étapes : {len(steps)}.",
        ]

        for i, step in enumerate(steps):
            action = step.get("action", "inconnue")
            reasons.append(f"  Étape {i + 1} : {action}.")

        result = {
            "id": f"es_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "scenario_id": sc_id,
            "reasons": reasons,
            "timestamp": time.time(),
        }
        self._explanations.append(result)
        self._trim()

        return result

    # ── explain_decision ────────────────────────────────────
    def explain_decision(self) -> dict:
        """Expliquer la dernière décision de planification."""
        self._stats["decision_explanations"] += 1

        reasons = []

        # Tirer du contexte d'arbitrage
        if self._arbitration is not None:
            arb_stats = self._arbitration.get_stats()
            reasons.append(
                f"Arbitrages effectués : {arb_stats.get('arbitrations', 0)}."
            )

        # Tirer du contexte de cohérence
        if self._coherence is not None:
            coh_stats = self._coherence.get_stats()
            reasons.append(
                f"Vérifications de cohérence : {coh_stats.get('checks', 0)}."
            )

        if not reasons:
            reasons.append("Aucun contexte de décision disponible.")

        reasons.append(f"Explications totales produites : {len(self._explanations)}.")

        result = {
            "id": f"ed_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "reasons": reasons,
            "timestamp": time.time(),
        }
        self._explanations.append(result)
        self._trim()

        return result

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "planning_explainability_engine",
            "status": "ok",
            "total_explanations": len(self._explanations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._explanations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("PlanningExplainabilityEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._explanations) > 5000:
            self._explanations = self._explanations[-2500:]
