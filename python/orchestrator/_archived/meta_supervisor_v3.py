"""
EXO v13 — MetaSupervisorV3 (Surveillance de la prospective)
Surveille la qualité des simulations, prévisions et plans futurs.
Détecte dérives, anticipations non autorisées, prévisions incohérentes.
Bloque les simulations dangereuses.

API:
  supervise_simulation(simulation)    → dict
  supervise_prediction(prediction)    → dict
  enforce_future_rules()              → dict
  set_future_rules(rules)             → None
  get_alerts(limit)                   → list
  get_stats()                         → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("meta_supervisor_v3")

DEFAULT_FUTURE_RULES: dict[str, Any] = {
    "max_simulation_steps": 100,
    "max_risk_ratio": 0.5,
    "min_success_probability": 0.2,
    "max_predictions": 50,
    "max_pending_plans": 100,
    "forbidden_tools_in_simulation": [],
    "require_governance_check": True,
    "max_anticipation_confidence_gap": 0.7,
}


class MetaSupervisorV3:
    """Moteur de supervision prospective EXO v13."""

    def __init__(self, meta_memory, supervisor_v2=None,
                 simulation_engine=None, governance=None):
        self._memory = meta_memory
        self._supervisor_v2 = supervisor_v2
        self._simulation = simulation_engine
        self._governance = governance
        self._rules = dict(DEFAULT_FUTURE_RULES)
        self._alerts: list[dict] = []
        self._history: list[dict] = []
        self._stats = {
            "simulations_supervised": 0,
            "predictions_supervised": 0,
            "enforcements": 0,
            "blocked": 0,
            "alerts_raised": 0,
        }

    # ── supervise_simulation ────────────────────────────────
    def supervise_simulation(self, simulation: dict) -> dict:
        """Supervise a simulation result for safety and quality."""
        issues: list[dict] = []

        sim_type = simulation.get("type", "")
        step_count = simulation.get("step_count", 0)
        risks = simulation.get("risks", [])
        success_prob = simulation.get("success_probability", 0.5)
        governance_ok = simulation.get("governance_ok", True)

        # Rule: max simulation steps
        max_steps = self._rules.get("max_simulation_steps", 100)
        if step_count > max_steps:
            issues.append({
                "type": "too_many_steps",
                "detail": f"Simulation has {step_count} steps (max {max_steps})",
            })

        # Rule: max risk ratio
        max_risk = self._rules.get("max_risk_ratio", 0.5)
        if step_count > 0:
            risk_ratio = len(risks) / step_count
            if risk_ratio > max_risk:
                issues.append({
                    "type": "high_risk_ratio",
                    "detail": f"Risk ratio {risk_ratio:.0%} exceeds "
                              f"max {max_risk:.0%}",
                })

        # Rule: min success probability
        min_success = self._rules.get("min_success_probability", 0.2)
        if success_prob < min_success:
            issues.append({
                "type": "low_success_probability",
                "detail": f"Success probability {success_prob:.0%} "
                          f"below min {min_success:.0%}",
            })

        # Rule: governance check
        if self._rules.get("require_governance_check", True) and not governance_ok:
            issues.append({
                "type": "governance_violation",
                "detail": "Simulation contains governance-blocked actions",
            })

        # Rule: forbidden tools
        forbidden = set(self._rules.get("forbidden_tools_in_simulation", []))
        if forbidden:
            step_results = simulation.get("step_results", [])
            for sr in step_results:
                tool = sr.get("tool", "").lower()
                if tool in forbidden:
                    issues.append({
                        "type": "forbidden_tool",
                        "detail": f"Tool '{tool}' is forbidden in simulations",
                        "step_index": sr.get("step_index", -1),
                    })

        # Check for dangerous simulations
        dangerous_risks = [r for r in risks
                           if r.get("type") in ("dangerous_tool",
                                                 "governance_blocked")]
        if dangerous_risks:
            issues.append({
                "type": "dangerous_simulation",
                "detail": f"{len(dangerous_risks)} dangerous elements "
                          f"in simulation",
            })

        approved = len(issues) == 0

        # Raise alerts for blocked simulations
        if not approved:
            self._stats["blocked"] += 1
            alert = {
                "type": "simulation_blocked",
                "issues": issues,
                "timestamp": time.time(),
            }
            self._alerts.append(alert)
            self._stats["alerts_raised"] += 1

        self._stats["simulations_supervised"] += 1

        result = {
            "type": "simulation_supervision",
            "sim_type": sim_type,
            "approved": approved,
            "issues": issues,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── supervise_prediction ────────────────────────────────
    def supervise_prediction(self, prediction: dict) -> dict:
        """Supervise a prediction for quality and coherence."""
        issues: list[dict] = []

        pred_type = prediction.get("type", "")
        predictions = prediction.get("predictions", [])
        count = prediction.get("prediction_count", len(predictions))

        # Rule: max predictions
        max_pred = self._rules.get("max_predictions", 50)
        if count > max_pred:
            issues.append({
                "type": "too_many_predictions",
                "detail": f"Prediction count {count} exceeds max {max_pred}",
            })

        # Check confidence distribution
        if predictions:
            confidences = [p.get("confidence", 0) for p in predictions]
            avg_conf = sum(confidences) / len(confidences)
            max_conf = max(confidences)
            min_conf = min(confidences)

            gap = max_conf - min_conf
            max_gap = self._rules.get("max_anticipation_confidence_gap", 0.7)
            if gap > max_gap:
                issues.append({
                    "type": "high_confidence_gap",
                    "detail": f"Confidence gap {gap:.2f} exceeds max {max_gap}",
                })

            # Low average confidence warning
            if avg_conf < 0.3:
                issues.append({
                    "type": "low_confidence",
                    "detail": f"Average confidence {avg_conf:.2f} is very low",
                })

        # Check for contradictory predictions
        contradictions = self._find_contradictory_predictions(predictions)
        issues.extend(contradictions)

        approved = len(issues) == 0

        if not approved:
            alert = {
                "type": "prediction_issue",
                "issues": issues,
                "timestamp": time.time(),
            }
            self._alerts.append(alert)
            self._stats["alerts_raised"] += 1

        self._stats["predictions_supervised"] += 1

        result = {
            "type": "prediction_supervision",
            "pred_type": pred_type,
            "approved": approved,
            "issues": issues,
            "prediction_count": count,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── enforce_future_rules ────────────────────────────────
    def enforce_future_rules(self) -> dict:
        """Enforce future rules across all prospective modules."""
        actions: list[dict] = []

        # Check v2 supervisor if available
        if self._supervisor_v2:
            v2_result = self._supervisor_v2.enforce_meta_rules()
            actions.extend(v2_result.get("actions", []))

        # Check memory for stale future entries
        future_entries = self._memory.meta_get("future")
        now = time.time()
        for entry in future_entries:
            val = entry.get("value", {})
            if isinstance(val, dict):
                t = val.get("time_target", 0)
                if t and t < now:
                    actions.append({
                        "action": "stale_future_entry",
                        "entry_id": entry.get("id", ""),
                        "reason": "Future entry target time has passed",
                    })

        # Check pending plan count limit
        max_pending = self._rules.get("max_pending_plans", 100)
        pending_count = len(self._memory.meta_get("pending_plan"))
        if pending_count > max_pending:
            actions.append({
                "action": "too_many_pending_plans",
                "count": pending_count,
                "max": max_pending,
                "reason": f"{pending_count} pending plans exceeds max {max_pending}",
            })

        self._stats["enforcements"] += 1

        result = {
            "type": "future_enforcement",
            "actions": actions,
            "action_count": len(actions),
            "rules": dict(self._rules),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── rules / alerts ──────────────────────────────────────
    def set_future_rules(self, rules: dict) -> None:
        self._rules.update(rules)
        log.info("Future rules updated: %s", list(rules.keys()))

    def get_alerts(self, limit: int = 20) -> list[dict]:
        return self._alerts[-limit:]

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── private ─────────────────────────────────────────────
    def _find_contradictory_predictions(self, predictions: list) -> list[dict]:
        """Detect contradictory predictions (same target, opposite states)."""
        issues = []
        opposing = {
            "on": "off", "off": "on",
            "open": "close", "close": "open",
            "high_usage": "low_usage", "low_usage": "high_usage",
        }
        seen: dict[str, str] = {}
        for p in predictions:
            key = (p.get("device") or p.get("key") or
                   p.get("need") or p.get("routine") or "")
            state = str(p.get("predicted_state", "")).lower()
            if not key:
                continue
            k = key.lower()
            if k in seen:
                prev_state = seen[k]
                if opposing.get(prev_state) == state:
                    issues.append({
                        "type": "contradictory_prediction",
                        "key": key,
                        "detail": f"Contradictory predictions for '{key}': "
                                  f"'{prev_state}' vs '{state}'",
                    })
            else:
                seen[k] = state
        return issues

    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 500:
            self._history = self._history[-300:]
