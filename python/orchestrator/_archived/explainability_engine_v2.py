"""
EXO v12 — ExplainabilityEngineV2 (Explicabilité avancée)
Étend AutoExplanation v11 avec explication des plans, raisonnements
et méta-décisions.

API:
  explain_plan(plan)                    → str
  explain_reasoning(reasoning_trace)    → str
  explain_meta_decision(meta_decision)  → str
  get_explanation_log(limit)            → list[dict]
  get_stats()                           → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("explainability_v2")


class ExplainabilityEngineV2:
    """Moteur d'explicabilité avancé EXO v12."""

    def __init__(self, meta_memory, auto_explanation_v1=None):
        """
        Args:
            meta_memory: MetaMemory instance.
            auto_explanation_v1: AutoExplanation v11 (optional).
        """
        self._memory = meta_memory
        self._v1 = auto_explanation_v1
        self._log: list[dict] = []
        self._stats = {
            "plan_explanations": 0,
            "reasoning_explanations": 0,
            "meta_decision_explanations": 0,
        }

    # ── Plan explanation ─────────────────────────────────────
    def explain_plan(self, plan: dict) -> str:
        """Explain a plan in natural language.

        Describes goal, steps, dependencies, and rationale.
        """
        goal = plan.get("goal", "")
        steps = plan.get("steps", [])
        constraints = plan.get("constraints", [])
        adaptations = plan.get("adaptations", [])

        parts = []

        # Goal
        if goal:
            parts.append(f"Objectif du plan : {goal}.")
        else:
            parts.append("Plan sans objectif explicite.")

        # Steps summary
        if steps:
            parts.append(f"Le plan comporte {len(steps)} étape(s) :")
            for i, step in enumerate(steps[:5]):  # limit display
                if isinstance(step, dict):
                    tool = step.get("tool", "")
                    desc = step.get("description", "")
                    deps = step.get("depends_on", [])
                    line = f"  {i + 1}. "
                    if tool:
                        line += f"[{tool}] "
                    if desc:
                        line += desc
                    if deps:
                        line += f" (dépend de : {deps})"
                    parts.append(line)
                else:
                    parts.append(f"  {i + 1}. {step}")
            if len(steps) > 5:
                parts.append(f"  ... et {len(steps) - 5} étape(s) supplémentaire(s).")
        else:
            parts.append("Le plan ne contient aucune étape.")

        # Constraints
        if constraints:
            parts.append(f"Contraintes : {', '.join(str(c) for c in constraints)}.")

        # Adaptations (from v11 MetaPlanner)
        if adaptations:
            parts.append(f"{len(adaptations)} adaptation(s) appliquée(s) :")
            for a in adaptations[:3]:
                parts.append(f"  - {a.get('description', a.get('type', '?'))}")

        # Lookup learned context
        if goal:
            learned = self._memory.meta_get(goal)
            relevant = [e for e in learned if e.get("category") == "strategy"]
            if relevant:
                parts.append(
                    f"Contexte appris : {len(relevant)} stratégie(s) liée(s) trouvée(s)."
                )

        explanation = "\n".join(parts)
        self._stats["plan_explanations"] += 1
        return self._record("plan", goal or "unknown", explanation)

    # ── Reasoning explanation ────────────────────────────────
    def explain_reasoning(self, reasoning_trace: dict) -> str:
        """Explain a reasoning trace in natural language.

        Describes the reasoning process, quality, and conclusion.
        """
        steps = reasoning_trace.get("steps", [])
        conclusion = reasoning_trace.get("conclusion", "")
        confidence = reasoning_trace.get("confidence", 0.5)

        parts = []

        parts.append(f"Raisonnement en {len(steps)} étape(s) "
                      f"(confiance : {confidence:.0%}) :")

        for i, step in enumerate(steps[:5]):
            text = step.get("text", "") if isinstance(step, dict) else str(step)
            evidence = step.get("evidence", "") if isinstance(step, dict) else ""
            line = f"  {i + 1}. {text}"
            if evidence:
                line += f" [preuve : {evidence}]"
            parts.append(line)

        if len(steps) > 5:
            parts.append(f"  ... et {len(steps) - 5} étape(s) supplémentaire(s).")

        if conclusion:
            parts.append(f"Conclusion : {conclusion}.")
        else:
            parts.append("Aucune conclusion formulée.")

        # Quality assessment
        if confidence >= 0.8:
            parts.append("Le raisonnement est de haute confiance.")
        elif confidence >= 0.5:
            parts.append("Le raisonnement a un niveau de confiance modéré.")
        else:
            parts.append("Le raisonnement a une confiance faible — "
                          "des preuves supplémentaires seraient utiles.")

        explanation = "\n".join(parts)
        self._stats["reasoning_explanations"] += 1
        return self._record("reasoning", conclusion or "unknown", explanation)

    # ── Meta-decision explanation ────────────────────────────
    def explain_meta_decision(self, meta_decision: dict) -> str:
        """Explain a meta-level decision (supervision, reflection, verification).

        meta_decision: dict with 'type', 'approved'/'valid', 'issues', etc.
        """
        decision_type = meta_decision.get("type", "unknown")
        approved = meta_decision.get("approved", meta_decision.get("valid", True))
        issues = meta_decision.get("issues", [])
        reflection = meta_decision.get("reflection")

        parts = []

        # Decision type
        type_labels = {
            "reasoning_supervision": "Supervision du raisonnement",
            "planning_supervision": "Supervision de la planification",
            "plan_verification": "Vérification du plan",
            "reasoning_verification": "Vérification du raisonnement",
            "reasoning_reflection": "Réflexion sur le raisonnement",
            "plan_reflection": "Réflexion sur le plan",
            "decision_reflection": "Réflexion sur la décision",
        }
        label = type_labels.get(decision_type, decision_type)
        parts.append(f"Méta-décision : {label}.")

        # Approval status
        if approved:
            parts.append("Résultat : APPROUVÉ.")
        else:
            parts.append("Résultat : REFUSÉ.")

        # Issues
        if issues:
            parts.append(f"{len(issues)} problème(s) identifié(s) :")
            for issue in issues[:5]:
                issue_type = issue.get("type", "?")
                detail = issue.get("detail", "")
                parts.append(f"  - [{issue_type}] {detail}")
            if len(issues) > 5:
                parts.append(f"  ... et {len(issues) - 5} autre(s).")
        else:
            parts.append("Aucun problème détecté.")

        # Reflection context
        if reflection:
            quality = reflection.get("quality", 0)
            parts.append(f"Qualité évaluée : {quality:.0%}.")

        # Use v1 for additional context
        if self._v1 and hasattr(self._v1, "explain_decision"):
            action = meta_decision.get("action", decision_type)
            v1_text = self._v1.explain_decision(action, meta_decision)
            if v1_text:
                parts.append(f"Contexte v11 : {v1_text}")

        explanation = "\n".join(parts)
        self._stats["meta_decision_explanations"] += 1
        return self._record("meta_decision", decision_type, explanation)

    # ── Accessors ────────────────────────────────────────────
    def get_explanation_log(self, limit: int = 50) -> list[dict]:
        return self._log[-limit:]

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ─────────────────────────────────────────────
    def _record(self, kind: str, subject: str, explanation: str) -> str:
        self._log.append({
            "kind": kind,
            "subject": subject,
            "explanation": explanation,
            "timestamp": time.time(),
        })
        if len(self._log) > 300:
            self._log = self._log[-300:]
        return explanation
