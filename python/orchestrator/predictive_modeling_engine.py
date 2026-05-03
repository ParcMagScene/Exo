"""
EXO v23 — PredictiveModelingEngine
Prédit les conséquences de plans et événements de manière symbolique,
contextuelle, causale, temporelle et multi-agent.

API:
  predict_outcomes(plan: dict)   → dict
  predict_event(event: dict)     → dict
  explain_prediction()           → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("predictive_modeling_engine")


class PredictiveModelingEngine:
    """Moteur de modélisation prédictive EXO v23."""

    PREDICTION_MODES = {
        "symbolic", "contextual", "causal", "temporal", "multi_agent",
    }

    def __init__(self, governance=None, sandbox=None):
        self._governance = governance
        self._sandbox = sandbox

        self._predictions: list[dict] = []
        self._stats = {
            "outcomes_predicted": 0,
            "events_predicted": 0,
            "explanations": 0,
        }

    # ── predict_outcomes ────────────────────────────────────
    def predict_outcomes(self, plan: dict) -> dict:
        """Prédire les conséquences d'un plan."""
        self._stats["outcomes_predicted"] += 1

        goal = plan.get("goal", "unknown")
        steps = plan.get("steps", [])
        mode = plan.get("mode", "symbolic")

        predictions = []
        for i, step in enumerate(steps):
            action = step.get("action", "noop")
            pred = self._predict_step(action, mode, i)
            predictions.append(pred)

        confidence = self._compute_confidence(predictions)
        self._predictions.extend(predictions)
        self._trim()

        return {
            "id": f"po_{uuid.uuid4().hex[:8]}",
            "predicted": True,
            "goal": goal,
            "mode": mode,
            "predictions": predictions,
            "count": len(predictions),
            "confidence": confidence,
            "timestamp": time.time(),
        }

    # ── predict_event ───────────────────────────────────────
    def predict_event(self, event: dict) -> dict:
        """Prédire les conséquences d'un événement isolé."""
        self._stats["events_predicted"] += 1

        etype = event.get("type", "unknown")
        target = event.get("target", "system")
        severity = event.get("severity", "medium")

        consequences = self._event_consequences(etype, target, severity)

        pred = {
            "id": f"pe_{uuid.uuid4().hex[:8]}",
            "event_type": etype,
            "target": target,
            "severity": severity,
            "consequences": consequences,
            "count": len(consequences),
            "timestamp": time.time(),
        }
        self._predictions.append(pred)
        self._trim()

        return pred

    # ── explain_prediction ──────────────────────────────────
    def explain_prediction(self) -> dict:
        """Expliquer les prédictions les plus récentes."""
        self._stats["explanations"] += 1

        recent = self._predictions[-10:] if self._predictions else []

        explanations = []
        for pred in recent:
            explanations.append({
                "id": pred.get("id", "unknown"),
                "summary": self._summarize_prediction(pred),
            })

        return {
            "id": f"ep_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "count": len(explanations),
            "explanations": explanations,
            "timestamp": time.time(),
        }

    # ── internal helpers ────────────────────────────────────
    def _predict_step(self, action: str, mode: str, idx: int) -> dict:
        """Prédire l'effet d'une étape."""
        impact = "low" if idx < 2 else ("medium" if idx < 5 else "high")
        return {
            "step": idx + 1,
            "action": action,
            "mode": mode,
            "predicted_effect": f"effet prédit ({mode}) pour {action}",
            "impact": impact,
            "reversible": idx < 4,
        }

    def _compute_confidence(self, predictions: list) -> float:
        if not predictions:
            return 0.0
        n = len(predictions)
        base = 0.9
        base -= n * 0.03
        return round(max(0.1, min(1.0, base)), 3)

    def _event_consequences(self, etype: str, target: str, severity: str) -> list:
        sev_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        count = sev_map.get(severity, 2)
        consequences = []
        for i in range(count):
            consequences.append({
                "id": f"csq_{i}",
                "type": etype,
                "target": target,
                "description": f"conséquence {i + 1} de {etype} sur {target}",
                "mitigable": i < 2,
            })
        return consequences

    def _summarize_prediction(self, pred: dict) -> str:
        pid = pred.get("id", "?")
        count = pred.get("count", 0)
        return f"Prédiction {pid}: {count} élément(s) prédits"

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "predictive_modeling_engine",
            "status": "ok",
            "total_predictions": len(self._predictions),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._predictions.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("PredictiveModelingEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._predictions) > 5000:
            self._predictions = self._predictions[-2500:]
