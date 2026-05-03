"""
EXO v16 — AutonomousAgentLayer (Couche d'agents autonomes supervisés)
Permet aux agents de proposer, valider, exécuter et annuler des initiatives
sous supervision du CognitiveGovernor et de l'InitiativeProtocol.

API:
  propose_initiative(agent, action, context) → dict
  validate_initiative(initiative_id)         → dict
  execute_initiative(initiative_id)          → dict
  rollback_initiative(initiative_id)         → dict
  list_initiatives(status, limit)            → list[dict]
  get_agent_autonomy(agent)                  → dict
  set_agent_autonomy(agent, level)           → None
  health_check()                             → dict
  restart()                                  → None
  get_stats()                                → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("autonomous_agent_layer")

# Niveaux d'autonomie
AUTONOMY_LEVELS = {
    "passive": 0,       # L'agent ne peut pas proposer d'initiatives
    "observer": 1,      # Observe et signale, pas d'action
    "suggestive": 2,    # Propose des initiatives pour approbation
    "supervised": 3,    # Exécute avec supervision
    "autonomous": 4,    # Exécute librement (dans les limites du budget)
}

# Status d'initiative
INIT_STATUS = {
    "proposed", "validating", "approved", "rejected",
    "executing", "completed", "failed", "rolled_back",
}


class AutonomousAgentLayer:
    """Couche d'agents autonomes supervisés EXO v16."""

    def __init__(self, governor=None, initiative_protocol=None,
                 audit_log=None, meta_memory=None):
        self._governor = governor
        self._protocol = initiative_protocol
        self._audit = audit_log
        self._memory = meta_memory
        self._initiatives: dict[str, dict] = {}
        self._agent_autonomy: dict[str, int] = {}  # agent → level
        self._execution_history: list[dict] = []
        self._stats = {
            "initiatives_proposed": 0,
            "initiatives_validated": 0,
            "initiatives_executed": 0,
            "initiatives_rolled_back": 0,
            "initiatives_rejected": 0,
            "initiatives_failed": 0,
        }

    # ── propose_initiative ──────────────────────────────────
    def propose_initiative(self, agent: str, action: str,
                           context: dict | None = None) -> dict:
        """Un agent propose une initiative autonome."""
        context = context or {}
        self._stats["initiatives_proposed"] += 1
        init_id = f"init_{uuid.uuid4().hex[:10]}"

        autonomy = self._get_autonomy(agent)
        if autonomy < AUTONOMY_LEVELS["suggestive"]:
            self._stats["initiatives_rejected"] += 1
            return {
                "id": init_id,
                "status": "rejected",
                "reason": f"Agent autonomy level too low: {autonomy}",
                "agent": agent,
                "action": action,
            }

        initiative = {
            "id": init_id,
            "agent": agent,
            "action": action,
            "domain": context.get("domain", "general"),
            "confidence": context.get("confidence", 0.5),
            "risk": context.get("risk", 0.0),
            "budget_cost": context.get("budget_cost", 1),
            "reasoning": context.get("reasoning", ""),
            "context": context,
            "status": "proposed",
            "proposed_at": time.time(),
            "autonomy_level": autonomy,
        }

        # Governor supervision
        if self._governor:
            gov_result = self._governor.supervise_initiative(initiative)
            decision = gov_result.get("decision", "blocked")

            if decision == "blocked":
                initiative["status"] = "rejected"
                initiative["rejection_reason"] = gov_result.get(
                    "violations", [{}])[0].get("detail", "governor_blocked") \
                    if gov_result.get("violations") else "governor_blocked"
                self._stats["initiatives_rejected"] += 1
                self._initiatives[init_id] = initiative
                return {
                    "id": init_id,
                    "status": "rejected",
                    "reason": initiative["rejection_reason"],
                    "violations": gov_result.get("violations", []),
                    "agent": agent,
                    "action": action,
                }
            elif decision == "needs_approval":
                initiative["status"] = "validating"
            else:
                initiative["status"] = "approved"
                # Auto-execute if autonomous level
                if autonomy >= AUTONOMY_LEVELS["autonomous"]:
                    initiative["status"] = "approved"
        else:
            initiative["status"] = "approved"

        self._initiatives[init_id] = initiative

        if self._audit:
            self._audit.log_initiative(initiative)

        return {
            "id": init_id,
            "status": initiative["status"],
            "agent": agent,
            "action": action,
            "autonomy_level": autonomy,
            "validation_required": initiative["status"] == "validating",
        }

    # ── validate_initiative ─────────────────────────────────
    def validate_initiative(self, initiative_id: str) -> dict:
        """Valider une initiative en attente d'approbation."""
        initiative = self._initiatives.get(initiative_id)
        if not initiative:
            return {"validated": False, "reason": "not_found",
                    "initiative_id": initiative_id}

        if initiative["status"] not in ("proposed", "validating"):
            return {"validated": False, "reason": "invalid_status",
                    "current_status": initiative["status"],
                    "initiative_id": initiative_id}

        initiative["status"] = "approved"
        initiative["validated_at"] = time.time()
        self._stats["initiatives_validated"] += 1

        if self._protocol:
            self._protocol.approve(initiative_id)

        if self._audit:
            self._audit.log_validation({
                "initiative_id": initiative_id,
                "validator": "autonomous_agent_layer",
                "approval_level": "manual",
            })

        return {"validated": True, "initiative_id": initiative_id,
                "status": "approved"}

    # ── execute_initiative ──────────────────────────────────
    def execute_initiative(self, initiative_id: str) -> dict:
        """Exécuter une initiative approuvée."""
        initiative = self._initiatives.get(initiative_id)
        if not initiative:
            return {"executed": False, "reason": "not_found",
                    "initiative_id": initiative_id}

        if initiative["status"] != "approved":
            return {"executed": False, "reason": "not_approved",
                    "current_status": initiative["status"],
                    "initiative_id": initiative_id}

        initiative["status"] = "executing"
        initiative["execution_started_at"] = time.time()

        # Simulate execution (actual execution delegated to agent)
        try:
            initiative["status"] = "completed"
            initiative["completed_at"] = time.time()
            initiative["execution_time_ms"] = (
                initiative["completed_at"] - initiative["execution_started_at"]
            ) * 1000
            self._stats["initiatives_executed"] += 1

            self._execution_history.append({
                "initiative_id": initiative_id,
                "agent": initiative["agent"],
                "action": initiative["action"],
                "status": "completed",
                "timestamp": time.time(),
            })

            return {
                "executed": True,
                "initiative_id": initiative_id,
                "agent": initiative["agent"],
                "action": initiative["action"],
                "execution_time_ms": initiative["execution_time_ms"],
            }
        except Exception as exc:
            initiative["status"] = "failed"
            initiative["error"] = str(exc)
            self._stats["initiatives_failed"] += 1
            return {"executed": False, "reason": str(exc),
                    "initiative_id": initiative_id}

    # ── rollback_initiative ─────────────────────────────────
    def rollback_initiative(self, initiative_id: str) -> dict:
        """Annuler une initiative exécutée (rollback)."""
        initiative = self._initiatives.get(initiative_id)
        if not initiative:
            return {"rolled_back": False, "reason": "not_found",
                    "initiative_id": initiative_id}

        if initiative["status"] not in ("completed", "executing", "failed"):
            return {"rolled_back": False, "reason": "cannot_rollback",
                    "current_status": initiative["status"],
                    "initiative_id": initiative_id}

        prev_status = initiative["status"]
        initiative["status"] = "rolled_back"
        initiative["rolled_back_at"] = time.time()
        self._stats["initiatives_rolled_back"] += 1

        self._execution_history.append({
            "initiative_id": initiative_id,
            "agent": initiative["agent"],
            "action": initiative["action"],
            "status": "rolled_back",
            "previous_status": prev_status,
            "timestamp": time.time(),
        })

        if self._audit:
            self._audit.log_governance({
                "type": "governance_decision",
                "governor": "autonomous_agent_layer",
                "decision": "rollback",
                "scope": initiative.get("domain", "general"),
                "impact": "high",
            })

        return {"rolled_back": True, "initiative_id": initiative_id,
                "previous_status": prev_status}

    # ── list_initiatives ────────────────────────────────────
    def list_initiatives(self, status: str | None = None,
                         limit: int = 50) -> list[dict]:
        """Lister les initiatives avec filtre optionnel."""
        items = list(self._initiatives.values())
        if status:
            items = [i for i in items if i["status"] == status]
        items.sort(key=lambda x: x.get("proposed_at", 0), reverse=True)
        return items[:limit]

    # ── Autonomy management ─────────────────────────────────
    def get_agent_autonomy(self, agent: str) -> dict:
        level = self._get_autonomy(agent)
        level_name = next(
            (k for k, v in AUTONOMY_LEVELS.items() if v == level),
            "suggestive")
        return {"agent": agent, "level": level, "level_name": level_name}

    def set_agent_autonomy(self, agent: str, level: int | str) -> None:
        if isinstance(level, str):
            level = AUTONOMY_LEVELS.get(level, 2)
        self._agent_autonomy[agent] = max(0, min(4, level))

    # ── health_check ────────────────────────────────────────
    def health_check(self) -> dict:
        status_counts: dict[str, int] = {}
        for init in self._initiatives.values():
            s = init["status"]
            status_counts[s] = status_counts.get(s, 0) + 1

        return {
            "service": "autonomous_agent_layer",
            "status": "ok",
            "total_initiatives": len(self._initiatives),
            "by_status": status_counts,
            "agents_tracked": len(self._agent_autonomy),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._initiatives.clear()
        self._execution_history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("AutonomousAgentLayer restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _get_autonomy(self, agent: str) -> int:
        return self._agent_autonomy.get(
            agent, AUTONOMY_LEVELS["suggestive"])
