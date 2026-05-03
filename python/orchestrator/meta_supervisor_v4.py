"""
EXO v14 — MetaSupervisorV4 (Supervision distribuée)
Supervise tous les agents et leurs interactions :
qualité, cohérence inter-agents, communication, décisions.
Bloque agents défaillants, isole agents instables, valide décisions finales.

API:
  supervise_agent(agent_name)         → dict
  supervise_interaction(message)      → dict
  supervise_decision(decision)        → dict
  enforce_meta_rules()                → dict
  set_meta_rules(rules)               → None
  get_alerts(limit)                   → list
  health_check()                      → dict
  restart()                           → None
  get_stats()                         → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("meta_supervisor_v4")

DEFAULT_META_RULES: dict[str, Any] = {
    "max_agent_failure_rate": 0.5,
    "max_pending_messages": 200,
    "max_conflicts_per_cycle": 10,
    "require_decision_validation": True,
    "auto_restart_unhealthy": True,
    "blocked_agents": [],
    "max_dispatch_per_intent": 20,
}


class MetaSupervisorV4:
    """Superviseur distribué EXO v14."""

    def __init__(self, meta_memory=None, registry=None,
                 messaging_bus=None, consistency_engine=None,
                 supervisor_v3=None, governance=None):
        self._memory = meta_memory
        self._registry = registry
        self._bus = messaging_bus
        self._consistency = consistency_engine
        self._supervisor_v3 = supervisor_v3
        self._governance = governance
        self._rules = dict(DEFAULT_META_RULES)
        self._alerts: list[dict] = []
        self._history: list[dict] = []
        self._stats = {
            "agents_supervised": 0,
            "interactions_supervised": 0,
            "decisions_supervised": 0,
            "enforcements": 0,
            "agents_blocked": 0,
            "agents_restarted": 0,
            "alerts_raised": 0,
        }

    # ── supervise_agent ─────────────────────────────────────
    def supervise_agent(self, agent_name: str) -> dict:
        """Supervise a single agent: check health, stats, behavior."""
        self._stats["agents_supervised"] += 1

        if agent_name in self._rules.get("blocked_agents", []):
            return {
                "agent": agent_name,
                "status": "blocked",
                "reason": "in_blocked_list",
            }

        if not self._registry:
            return {"agent": agent_name, "status": "no_registry"}

        agent = self._registry.get_agent(agent_name)
        if not agent:
            return {"agent": agent_name, "status": "not_found"}

        issues: list[dict] = []

        # Health check
        if hasattr(agent, "health_check"):
            health = agent.health_check()
            if health.get("status") != "ok":
                issues.append({
                    "type": "unhealthy",
                    "detail": health,
                })

        # Stats check
        if hasattr(agent, "get_stats"):
            stats = agent.get_stats()
            total = stats.get("tasks_handled", 0)
            failed = stats.get("tasks_failed", 0)
            if total > 0:
                rate = failed / total
                if rate > self._rules["max_agent_failure_rate"]:
                    issues.append({
                        "type": "high_failure_rate",
                        "rate": rate,
                        "threshold": self._rules["max_agent_failure_rate"],
                    })

        # Auto-restart if unhealthy
        if issues and self._rules.get("auto_restart_unhealthy"):
            if hasattr(agent, "restart"):
                agent.restart()
                self._stats["agents_restarted"] += 1

        approved = len(issues) == 0
        if not approved:
            self._add_alert("agent_issue", agent_name, issues)

        result = {
            "agent": agent_name,
            "status": "approved" if approved else "issues_found",
            "approved": approved,
            "issues": issues,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── supervise_interaction ───────────────────────────────
    def supervise_interaction(self, message: dict) -> dict:
        """Supervise an inter-agent message."""
        self._stats["interactions_supervised"] += 1
        issues: list[dict] = []

        sender = message.get("sender", "")
        recipient = message.get("recipient", "")
        msg_type = message.get("type", "")

        # Check blocked agents
        blocked = self._rules.get("blocked_agents", [])
        if sender in blocked:
            issues.append({
                "type": "blocked_sender",
                "agent": sender,
            })
        if recipient in blocked:
            issues.append({
                "type": "blocked_recipient",
                "agent": recipient,
            })

        # Check message type validity
        if not msg_type:
            issues.append({"type": "missing_message_type"})

        approved = len(issues) == 0
        if not approved:
            self._add_alert("interaction_issue", f"{sender}→{recipient}",
                            issues)

        result = {
            "approved": approved,
            "sender": sender,
            "recipient": recipient,
            "issues": issues,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── supervise_decision ──────────────────────────────────
    def supervise_decision(self, decision: dict) -> dict:
        """Validate a final decision before execution."""
        self._stats["decisions_supervised"] += 1
        issues: list[dict] = []

        status = decision.get("status", "")
        agents_involved = decision.get("agents_involved", 0)
        failed = decision.get("failed", 0)

        if status == "failed":
            issues.append({
                "type": "decision_failed",
                "detail": "All agents failed",
            })

        if agents_involved == 0:
            issues.append({
                "type": "no_agents",
                "detail": "No agents were involved in the decision",
            })

        if failed > 0 and agents_involved > 0:
            if failed / agents_involved > 0.5:
                issues.append({
                    "type": "high_agent_failure",
                    "rate": failed / agents_involved,
                })

        approved = len(issues) == 0
        if not approved:
            self._add_alert("decision_issue", "orchestrator", issues)

        result = {
            "approved": approved,
            "decision_status": status,
            "issues": issues,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── enforce_meta_rules ──────────────────────────────────
    def enforce_meta_rules(self) -> dict:
        """Enforce supervision rules across all agents."""
        self._stats["enforcements"] += 1
        actions: list[dict] = []
        rules = list(self._rules.keys())

        # Check all agents
        if self._registry:
            for info in self._registry.list_agents():
                name = info["name"]
                sup = self.supervise_agent(name)
                if not sup.get("approved"):
                    actions.append({
                        "rule": "agent_quality",
                        "agent": name,
                        "action": "flagged",
                    })

        # Check messaging bus
        if self._bus:
            pending = sum(len(v) for v in self._bus._mailboxes.values())
            if pending > self._rules["max_pending_messages"]:
                actions.append({
                    "rule": "max_pending_messages",
                    "pending": pending,
                    "action": "warning",
                })

        # Check global consistency
        if self._consistency:
            check = self._consistency.check_global_consistency()
            if not check.get("consistent"):
                actions.append({
                    "rule": "global_consistency",
                    "issues": check.get("issue_count", 0),
                    "action": "enforce_consistency",
                })

        result = {
            "enforced": True,
            "actions": actions,
            "rules": rules,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── set_meta_rules ──────────────────────────────────────
    def set_meta_rules(self, rules: dict) -> None:
        """Update supervision rules."""
        self._rules.update(rules)
        log.info("MetaSupervisorV4 rules updated: %s", list(rules.keys()))

    # ── alerts ──────────────────────────────────────────────
    def get_alerts(self, limit: int = 20) -> list[dict]:
        return self._alerts[-limit:]

    def _add_alert(self, alert_type: str, source: str,
                   details: list[dict]) -> None:
        self._alerts.append({
            "type": alert_type,
            "source": source,
            "details": details,
            "timestamp": time.time(),
        })
        self._stats["alerts_raised"] += 1
        if len(self._alerts) > 1000:
            self._alerts = self._alerts[-500:]

    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 500:
            self._history = self._history[-300:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "meta_supervisor_v4",
            "status": "ok",
            "alerts": len(self._alerts),
            "agents_supervised": self._stats["agents_supervised"],
        }

    def restart(self) -> None:
        self._alerts.clear()
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("MetaSupervisorV4 restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
