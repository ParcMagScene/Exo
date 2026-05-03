"""
EXO v16 — SelfRegulationEngine (Moteur d'auto-régulation)
Ajuste dynamiquement les niveaux d'autonomie, budgets et seuils
en fonction des performances et de la sécurité du système.

API:
  adjust_autonomy(agent, metrics)    → dict
  adjust_budget(agent, metrics)      → dict
  regulate_all(system_state)         → dict
  get_regulation_history(limit)      → list[dict]
  set_regulation_policy(policy)      → None
  get_regulation_policy()            → dict
  health_check()                     → dict
  restart()                          → None
  get_stats()                        → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("self_regulation")

# Politique de régulation par défaut
DEFAULT_POLICY = {
    "autonomy_increase_threshold": 0.8,   # Success rate pour augmenter
    "autonomy_decrease_threshold": 0.4,   # Success rate pour diminuer
    "budget_increase_factor": 1.2,
    "budget_decrease_factor": 0.7,
    "min_observations": 5,                 # Min observations avant ajustement
    "max_autonomy_level": 4,
    "min_autonomy_level": 0,
    "cooldown_sec": 300,                   # Cooldown entre ajustements
    "emergency_threshold": 0.2,            # En dessous = urgence
}


class SelfRegulationEngine:
    """Moteur d'auto-régulation EXO v16."""

    def __init__(self, governor=None, audit_log=None,
                 initiative_protocol=None, meta_memory=None):
        self._governor = governor
        self._audit = audit_log
        self._protocol = initiative_protocol
        self._memory = meta_memory
        self._policy = dict(DEFAULT_POLICY)
        self._history: list[dict] = []
        self._last_adjustment: dict[str, float] = {}  # agent → timestamp
        self._stats = {
            "autonomy_adjustments": 0,
            "autonomy_increases": 0,
            "autonomy_decreases": 0,
            "budget_adjustments": 0,
            "budget_increases": 0,
            "budget_decreases": 0,
            "regulations_run": 0,
            "emergency_regulations": 0,
        }

    # ── adjust_autonomy ─────────────────────────────────────
    def adjust_autonomy(self, agent: str, metrics: dict) -> dict:
        """Ajuster le niveau d'autonomie d'un agent."""
        self._stats["autonomy_adjustments"] += 1
        adj_id = f"adj_{uuid.uuid4().hex[:8]}"

        # Cooldown check
        now = time.time()
        last = self._last_adjustment.get(agent, 0)
        if now - last < self._policy["cooldown_sec"]:
            return {
                "id": adj_id,
                "adjusted": False,
                "reason": "cooldown",
                "agent": agent,
                "remaining_sec": round(
                    self._policy["cooldown_sec"] - (now - last)),
            }

        success_rate = metrics.get("success_rate", 0.5)
        total_actions = metrics.get("total_actions", 0)
        violations = metrics.get("violations", 0)
        rollbacks = metrics.get("rollbacks", 0)

        # Need minimum observations
        if total_actions < self._policy["min_observations"]:
            return {
                "id": adj_id,
                "adjusted": False,
                "reason": "insufficient_data",
                "agent": agent,
                "total_actions": total_actions,
                "min_required": self._policy["min_observations"],
            }

        # Current autonomy
        current_level = 2  # default: suggestive
        if self._governor:
            # Get autonomy from autonomous layer if available
            pass

        direction = "none"
        new_level = current_level

        # Emergency: too many failures
        if success_rate < self._policy["emergency_threshold"]:
            new_level = max(self._policy["min_autonomy_level"],
                            current_level - 2)
            direction = "emergency_decrease"
            self._stats["emergency_regulations"] += 1

        # Decrease: poor performance or violations
        elif (success_rate < self._policy["autonomy_decrease_threshold"]
              or violations > total_actions * 0.3):
            new_level = max(self._policy["min_autonomy_level"],
                            current_level - 1)
            direction = "decrease"
            self._stats["autonomy_decreases"] += 1

        # Increase: good performance
        elif (success_rate > self._policy["autonomy_increase_threshold"]
              and violations == 0 and rollbacks == 0):
            new_level = min(self._policy["max_autonomy_level"],
                            current_level + 1)
            direction = "increase"
            self._stats["autonomy_increases"] += 1

        self._last_adjustment[agent] = now

        result = {
            "id": adj_id,
            "adjusted": direction != "none",
            "agent": agent,
            "direction": direction,
            "previous_level": current_level,
            "new_level": new_level,
            "metrics": {
                "success_rate": success_rate,
                "total_actions": total_actions,
                "violations": violations,
                "rollbacks": rollbacks,
            },
            "timestamp": now,
        }

        self._history.append(result)
        self._trim_history()

        if direction != "none" and self._audit:
            self._audit.log_regulation({
                "type": "regulation_adjustment",
                "parameter": "autonomy_level",
                "old_value": current_level,
                "new_value": new_level,
                "reason": f"{direction}: success_rate={success_rate:.2f}",
            })

        return result

    # ── adjust_budget ───────────────────────────────────────
    def adjust_budget(self, agent: str, metrics: dict) -> dict:
        """Ajuster le budget d'initiative d'un agent."""
        self._stats["budget_adjustments"] += 1
        adj_id = f"budg_{uuid.uuid4().hex[:8]}"

        success_rate = metrics.get("success_rate", 0.5)
        usage_rate = metrics.get("budget_usage_rate", 0.0)
        efficiency = metrics.get("efficiency", 0.5)

        # Get current budget from protocol
        current_budget = {"max_initiatives_per_hour": 20,
                          "max_total_cost_per_hour": 500}
        if self._protocol:
            current_budget = self._protocol.get_budget(agent)

        direction = "none"
        new_max_init = current_budget.get("max_initiatives_per_hour", 20)
        new_max_cost = current_budget.get("max_total_cost_per_hour", 500)
        old_max_init = new_max_init
        old_max_cost = new_max_cost

        # High success + high usage → increase budget
        if (success_rate > 0.8 and usage_rate > 0.7
                and efficiency > 0.6):
            factor = self._policy["budget_increase_factor"]
            new_max_init = int(new_max_init * factor)
            new_max_cost = int(new_max_cost * factor)
            direction = "increase"
            self._stats["budget_increases"] += 1

        # Low success or many violations → decrease budget
        elif success_rate < 0.4 or efficiency < 0.3:
            factor = self._policy["budget_decrease_factor"]
            new_max_init = max(5, int(new_max_init * factor))
            new_max_cost = max(100, int(new_max_cost * factor))
            direction = "decrease"
            self._stats["budget_decreases"] += 1

        # Apply new budget
        if direction != "none" and self._protocol:
            self._protocol.set_budget(agent, {
                "max_initiatives_per_hour": new_max_init,
                "max_total_cost_per_hour": new_max_cost,
            })

        result = {
            "id": adj_id,
            "adjusted": direction != "none",
            "agent": agent,
            "direction": direction,
            "previous_budget": {
                "max_initiatives_per_hour": old_max_init,
                "max_total_cost_per_hour": old_max_cost,
            },
            "new_budget": {
                "max_initiatives_per_hour": new_max_init,
                "max_total_cost_per_hour": new_max_cost,
            },
            "metrics": {
                "success_rate": success_rate,
                "usage_rate": usage_rate,
                "efficiency": efficiency,
            },
            "timestamp": time.time(),
        }

        self._history.append(result)

        if direction != "none" and self._audit:
            self._audit.log_regulation({
                "type": "regulation_adjustment",
                "parameter": "budget",
                "old_value": {"init": old_max_init, "cost": old_max_cost},
                "new_value": {"init": new_max_init, "cost": new_max_cost},
                "reason": f"{direction}: success_rate={success_rate:.2f}",
            })

        return result

    # ── regulate_all ────────────────────────────────────────
    def regulate_all(self, system_state: dict) -> dict:
        """Régulation globale du système."""
        self._stats["regulations_run"] += 1
        reg_id = f"reg_{uuid.uuid4().hex[:8]}"

        agents_metrics = system_state.get("agents", {})
        adjustments = []

        for agent_name, metrics in agents_metrics.items():
            # Autonomy adjustment
            auto_adj = self.adjust_autonomy(agent_name, metrics)
            if auto_adj.get("adjusted"):
                adjustments.append({
                    "agent": agent_name,
                    "type": "autonomy",
                    **auto_adj,
                })

            # Budget adjustment
            budget_adj = self.adjust_budget(agent_name, metrics)
            if budget_adj.get("adjusted"):
                adjustments.append({
                    "agent": agent_name,
                    "type": "budget",
                    **budget_adj,
                })

        # System-level checks
        system_health = system_state.get("health", "ok")
        alerts = []

        if system_health == "degraded":
            alerts.append({
                "type": "system_degradation",
                "action": "reduce_all_budgets",
                "severity": "high",
            })

        # Governor enforcement
        if self._governor:
            enforcement = self._governor.enforce_governance_rules(system_state)
            if not enforcement.get("compliant", True):
                alerts.append({
                    "type": "governance_violation",
                    "violations": enforcement.get("violations", []),
                    "severity": "high",
                })

        result = {
            "id": reg_id,
            "type": "full_regulation",
            "agents_evaluated": len(agents_metrics),
            "adjustments": adjustments,
            "adjustments_count": len(adjustments),
            "alerts": alerts,
            "system_compliant": len(alerts) == 0,
            "timestamp": time.time(),
        }

        self._history.append(result)
        return result

    # ── regulation policy ───────────────────────────────────
    def get_regulation_policy(self) -> dict:
        return dict(self._policy)

    def set_regulation_policy(self, policy: dict) -> None:
        self._policy.update(policy)

    # ── get_regulation_history ──────────────────────────────
    def get_regulation_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]

    # ── health_check ────────────────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "self_regulation",
            "status": "ok",
            "history_entries": len(self._history),
            "agents_tracked": len(self._last_adjustment),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        self._last_adjustment.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("SelfRegulationEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim_history(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
