"""
EXO v16 — InitiativeProtocol (Protocole d'initiative autonome)
Contrôle les permissions, budgets et niveaux de validation
requis avant qu'un agent puisse exécuter une initiative.

API:
  check_permissions(agent, action, context)  → dict
  check_budget(agent, cost)                  → dict
  require_validation(initiative)             → dict
  approve(initiative_id)                     → dict
  deny(initiative_id, reason)                → dict
  get_budget(agent)                          → dict
  set_budget(agent, budget)                  → None
  health_check()                             → dict
  restart()                                  → None
  get_stats()                                → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("initiative_protocol")

# Niveaux de validation
VALIDATION_LEVELS = {
    "auto": 0,        # Exécution automatique (faible risque)
    "supervised": 1,  # Superviseur peut intervenir
    "approval": 2,    # Nécessite approbation explicite
    "critical": 3,    # Approbation + confirmation utilisateur
}

# Risques par domaine
DOMAIN_RISK = {
    "diagnostic": "low",
    "optimisation": "low",
    "apprentissage": "low",
    "communication": "medium",
    "planification": "medium",
    "domotique": "high",
    "securite": "critical",
    "reseau": "high",
}

DEFAULT_BUDGET = {
    "max_initiatives_per_hour": 20,
    "max_cost_per_initiative": 100,
    "max_total_cost_per_hour": 500,
    "remaining_initiatives": 20,
    "remaining_cost": 500,
    "last_reset": 0.0,
}


class InitiativeProtocol:
    """Protocole de contrôle d'initiative autonome EXO v16."""

    def __init__(self, audit_log=None, governance=None):
        self._audit = audit_log
        self._governance = governance
        self._budgets: dict[str, dict] = {}
        self._pending: dict[str, dict] = {}  # initiative_id → initiative
        self._stats = {
            "permissions_checked": 0,
            "permissions_granted": 0,
            "permissions_denied": 0,
            "budgets_checked": 0,
            "budgets_ok": 0,
            "budgets_exceeded": 0,
            "validations_required": 0,
            "validations_auto": 0,
            "approvals": 0,
            "denials": 0,
        }

    # ── check_permissions ───────────────────────────────────
    def check_permissions(self, agent: str, action: str,
                          context: dict | None = None) -> dict:
        """Vérifier si un agent a les permissions pour une action."""
        context = context or {}
        self._stats["permissions_checked"] += 1

        # Check governance layer
        if self._governance:
            allowed = self._governance.check_permission(action, context)
            if not allowed:
                self._stats["permissions_denied"] += 1
                if self._audit:
                    self._audit.log_rejection({
                        "initiative_id": f"perm_{uuid.uuid4().hex[:8]}",
                        "rejector": "initiative_protocol",
                        "reason": f"Governance denied: {action}",
                        "severity": "medium",
                    })
                return {
                    "allowed": False,
                    "reason": "governance_denied",
                    "agent": agent,
                    "action": action,
                }

        # Domain risk check
        domain = context.get("domain", "general")
        risk = DOMAIN_RISK.get(domain, "medium")

        self._stats["permissions_granted"] += 1
        return {
            "allowed": True,
            "agent": agent,
            "action": action,
            "domain": domain,
            "risk_level": risk,
            "validation_required": risk in ("high", "critical"),
        }

    # ── check_budget ────────────────────────────────────────
    def check_budget(self, agent: str, cost: float = 1.0) -> dict:
        """Vérifier le budget d'initiative d'un agent."""
        self._stats["budgets_checked"] += 1
        budget = self._get_or_create_budget(agent)

        # Reset hourly budget
        now = time.time()
        if now - budget["last_reset"] > 3600:
            budget["remaining_initiatives"] = budget["max_initiatives_per_hour"]
            budget["remaining_cost"] = budget["max_total_cost_per_hour"]
            budget["last_reset"] = now

        # Check initiative count
        if budget["remaining_initiatives"] <= 0:
            self._stats["budgets_exceeded"] += 1
            return {
                "allowed": False,
                "reason": "initiatives_exhausted",
                "agent": agent,
                "remaining_initiatives": 0,
            }

        # Check cost
        if cost > budget["max_cost_per_initiative"]:
            self._stats["budgets_exceeded"] += 1
            return {
                "allowed": False,
                "reason": "cost_too_high",
                "agent": agent,
                "cost": cost,
                "max_allowed": budget["max_cost_per_initiative"],
            }

        if cost > budget["remaining_cost"]:
            self._stats["budgets_exceeded"] += 1
            return {
                "allowed": False,
                "reason": "budget_exhausted",
                "agent": agent,
                "cost": cost,
                "remaining": budget["remaining_cost"],
            }

        self._stats["budgets_ok"] += 1
        return {
            "allowed": True,
            "agent": agent,
            "cost": cost,
            "remaining_initiatives": budget["remaining_initiatives"],
            "remaining_cost": budget["remaining_cost"],
        }

    # ── require_validation ──────────────────────────────────
    def require_validation(self, initiative: dict) -> dict:
        """Déterminer le niveau de validation requis pour une initiative."""
        self._stats["validations_required"] += 1
        init_id = initiative.get("id", f"init_{uuid.uuid4().hex[:8]}")

        domain = initiative.get("domain", "general")
        risk = DOMAIN_RISK.get(domain, "medium")
        confidence = initiative.get("confidence", 0.5)
        cost = initiative.get("budget_cost", 0)

        # Determine validation level
        if risk == "critical" or cost > 200:
            level = "critical"
        elif risk == "high" or confidence < 0.5:
            level = "approval"
        elif risk == "medium" or confidence < 0.7:
            level = "supervised"
        else:
            level = "auto"
            self._stats["validations_auto"] += 1

        result = {
            "initiative_id": init_id,
            "validation_level": level,
            "validation_level_num": VALIDATION_LEVELS[level],
            "risk": risk,
            "confidence": confidence,
            "auto_approved": level == "auto",
        }

        if level != "auto":
            self._pending[init_id] = {**initiative, "id": init_id,
                                       "validation_level": level,
                                       "requested_at": time.time()}

        if self._audit:
            self._audit.log_initiative({
                **initiative,
                "id": init_id,
                "validation_level": level,
            })

        return result

    # ── approve ─────────────────────────────────────────────
    def approve(self, initiative_id: str) -> dict:
        """Approuver une initiative en attente."""
        self._stats["approvals"] += 1

        initiative = self._pending.pop(initiative_id, None)
        if not initiative:
            return {"approved": False, "reason": "not_found",
                    "initiative_id": initiative_id}

        # Consume budget
        agent = initiative.get("agent", "unknown")
        cost = initiative.get("budget_cost", 1)
        budget = self._get_or_create_budget(agent)
        budget["remaining_initiatives"] -= 1
        budget["remaining_cost"] -= cost

        if self._audit:
            self._audit.log_validation({
                "initiative_id": initiative_id,
                "validator": "initiative_protocol",
                "approval_level": initiative.get("validation_level", "auto"),
            })

        return {"approved": True, "initiative_id": initiative_id,
                "initiative": initiative}

    # ── deny ────────────────────────────────────────────────
    def deny(self, initiative_id: str, reason: str = "") -> dict:
        """Rejeter une initiative en attente."""
        self._stats["denials"] += 1

        initiative = self._pending.pop(initiative_id, None)
        if not initiative:
            return {"denied": False, "reason": "not_found",
                    "initiative_id": initiative_id}

        if self._audit:
            self._audit.log_rejection({
                "initiative_id": initiative_id,
                "rejector": "initiative_protocol",
                "reason": reason,
                "severity": "medium",
            })

        return {"denied": True, "initiative_id": initiative_id,
                "reason": reason}

    # ── get_budget / set_budget ─────────────────────────────
    def get_budget(self, agent: str) -> dict:
        return dict(self._get_or_create_budget(agent))

    def set_budget(self, agent: str, budget: dict) -> None:
        current = self._get_or_create_budget(agent)
        current.update(budget)

    # ── health_check ────────────────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "initiative_protocol",
            "status": "ok",
            "pending_count": len(self._pending),
            "agents_tracked": len(self._budgets),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._pending.clear()
        self._budgets.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("InitiativeProtocol restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _get_or_create_budget(self, agent: str) -> dict:
        if agent not in self._budgets:
            self._budgets[agent] = {**DEFAULT_BUDGET, "last_reset": time.time()}
        return self._budgets[agent]
