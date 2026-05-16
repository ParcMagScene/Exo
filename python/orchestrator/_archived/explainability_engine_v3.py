"""
EXO v13 — ExplainabilityEngineV3 (Explication prospective)
Explique les simulations, prévisions, futurs choisis et anticipations
en langage naturel.

API:
  explain_future(future)             → str
  explain_simulation(simulation)     → str
  explain_prediction(prediction)     → str
  get_explanation_log(limit)         → list
  get_stats()                        → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("explainability_v3")


class ExplainabilityEngineV3:
    """Moteur d'explication prospective EXO v13."""

    def __init__(self, meta_memory, explainability_v2=None):
        self._memory = meta_memory
        self._v2 = explainability_v2
        self._log: list[dict] = []
        self._stats = {
            "future_explanations": 0,
            "simulation_explanations": 0,
            "prediction_explanations": 0,
        }

    # ── explain_future ──────────────────────────────────────
    def explain_future(self, future: dict) -> str:
        """Explain why a future scenario was selected or rejected."""
        parts: list[str] = []

        f_type = future.get("type", "unknown")
        parts.append(f"=== Explication du futur ({f_type}) ===")

        # Selection explanation
        if f_type == "future_selection":
            selected = future.get("selected", {})
            name = selected.get("name", "inconnu") if selected else "aucun"
            reason = future.get("reason", "")
            parts.append(f"\nFutur sélectionné : {name}")
            if reason:
                parts.append(f"Justification : {reason}")

            ranking = future.get("ranking", [])
            if ranking:
                parts.append(f"Classement des variantes : {ranking}")

        # Variant comparison explanation
        elif f_type == "future_comparison":
            comp = future.get("comparison", [])
            parts.append(f"\n{len(comp)} variantes comparées :")
            for c in comp:
                parts.append(
                    f"  - {c.get('name', '?')}: score={c.get('score', 0):.2f}, "
                    f"risques={c.get('risk_count', 0)}, "
                    f"succès={c.get('success_probability', 0):.0%}"
                )
            best = future.get("best_index", -1)
            if best >= 0:
                parts.append(f"Meilleur choix : variante #{best}")

        # Variant generation explanation
        elif f_type == "future_variants":
            variants = future.get("variants", [])
            parts.append(f"\n{len(variants)} variantes générées pour "
                         f"l'objectif '{future.get('goal', '?')}' :")
            for v in variants:
                desc = v.get("description", "")
                sim = v.get("simulation", {})
                success = sim.get("success_probability", "?")
                parts.append(f"  - {v.get('name', '?')}: {desc} "
                             f"(succès: {success})")

        else:
            parts.append(f"Données du futur : {future}")

        text = "\n".join(parts)
        self._stats["future_explanations"] += 1
        self._log_entry("future", text)
        return text

    # ── explain_simulation ──────────────────────────────────
    def explain_simulation(self, simulation: dict) -> str:
        """Explain a simulation result."""
        parts: list[str] = []

        sim_type = simulation.get("type", "unknown")
        parts.append(f"=== Explication de la simulation ({sim_type}) ===")

        if sim_type == "plan_simulation":
            goal = simulation.get("goal", "non défini")
            parts.append(f"\nObjectif simulé : {goal}")
            parts.append(f"Nombre d'étapes : {simulation.get('step_count', 0)}")

            success = simulation.get("success_probability", 0)
            parts.append(f"Probabilité de succès : {success:.0%}")

            risks = simulation.get("risks", [])
            if risks:
                parts.append(f"\nRisques détectés ({len(risks)}) :")
                for r in risks:
                    parts.append(f"  ⚠ [{r.get('type', '?')}] {r.get('detail', '')}")
            else:
                parts.append("Aucun risque détecté.")

            side_effects = simulation.get("side_effects", [])
            if side_effects:
                parts.append(f"\nEffets secondaires ({len(side_effects)}) :")
                for se in side_effects:
                    parts.append(f"  → {se.get('description', '')}")

            gov = simulation.get("governance_ok", True)
            if not gov:
                parts.append("\n⛔ La gouvernance a bloqué certaines actions.")

        elif sim_type == "outcome_simulation":
            parts.append(f"\nProbabilité de succès : "
                         f"{simulation.get('success_probability', 0):.0%}")

            consequences = simulation.get("consequences", [])
            if consequences:
                parts.append(f"\nConséquences prévues ({len(consequences)}) :")
                for c in consequences:
                    parts.append(f"  [{c.get('severity', '?')}] {c.get('description', '')}")

            alts = simulation.get("alternatives", [])
            if alts:
                parts.append(f"\nAlternatives proposées ({len(alts)}) :")
                for a in alts:
                    parts.append(f"  - {a.get('type', '?')}: "
                                 f"{a.get('removed_risky_steps', 0)} étapes risquées retirées")

        elif sim_type == "step_simulation":
            tool = simulation.get("tool", "?")
            success = simulation.get("simulated_success", 0)
            parts.append(f"\nÉtape simulée : outil '{tool}'")
            parts.append(f"Succès estimé : {success:.0%}")

        elif sim_type == "scenario_simulation":
            name = simulation.get("name", "?")
            parts.append(f"\nScénario : {name}")
            parts.append(f"Plans simulés : {simulation.get('plan_count', 0)}")
            parts.append(f"Succès global : "
                         f"{simulation.get('overall_success_probability', 0):.0%}")

        else:
            parts.append(f"Données : {simulation}")

        text = "\n".join(parts)
        self._stats["simulation_explanations"] += 1
        self._log_entry("simulation", text)
        return text

    # ── explain_prediction ──────────────────────────────────
    def explain_prediction(self, prediction: dict) -> str:
        """Explain a prediction result."""
        parts: list[str] = []

        pred_type = prediction.get("type", "unknown")
        type_labels = {
            "user_need_prediction": "Prévision de besoin utilisateur",
            "domotic_prediction": "Prévision domotique",
            "network_prediction": "Prévision réseau",
            "routine_prediction": "Prévision de routine",
        }
        label = type_labels.get(pred_type, pred_type)
        parts.append(f"=== {label} ===")

        predictions = prediction.get("predictions", [])
        if not predictions:
            parts.append("Aucune prévision disponible.")
        else:
            parts.append(f"\n{len(predictions)} prévision(s) :")
            for p in predictions:
                conf = p.get("confidence", 0)
                name = (p.get("need") or p.get("device") or
                        p.get("routine") or p.get("key") or "?")
                desc = (p.get("description") or p.get("predicted_state") or
                        p.get("details") or "")
                parts.append(
                    f"  - {name}: {desc} (confiance: {conf:.0%})"
                )

        text = "\n".join(parts)
        self._stats["prediction_explanations"] += 1
        self._log_entry("prediction", text)
        return text

    # ── log / stats ─────────────────────────────────────────
    def get_explanation_log(self, limit: int = 20) -> list[dict]:
        return self._log[-limit:]

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── private ─────────────────────────────────────────────
    def _log_entry(self, kind: str, text: str) -> None:
        self._log.append({
            "kind": kind,
            "text": text,
            "timestamp": time.time(),
        })
        if len(self._log) > 500:
            self._log = self._log[-300:]
