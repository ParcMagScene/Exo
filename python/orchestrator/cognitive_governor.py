"""
EXO v16 — CognitiveGovernor (Gouverneur cognitif)
Supervise initiatives autonomes et émergences cognitives.
Point de contrôle central pour autonomie, sécurité et cohérence.

API:
  supervise_initiative(initiative)    → dict
  supervise_emergence(emergence)      → dict
  enforce_governance_rules(state)     → dict
  override_decision(decision_id, override) → dict
  get_governance_log(limit)           → list[dict]
  health_check()                      → dict
  restart()                           → None
  get_stats()                         → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("cognitive_governor")

# Règles de gouvernance globales
GOVERNANCE_RULES = [
    {"id": "safety_first", "rule": "Bloquer toute initiative dangereuse",
     "severity": "critical", "auto_enforce": True},
    {"id": "budget_limit", "rule": "Respecter les budgets d'initiative",
     "severity": "high", "auto_enforce": True},
    {"id": "coherence", "rule": "L'initiative doit être cohérente avec l'état",
     "severity": "high", "auto_enforce": True},
    {"id": "explainability", "rule": "Toute décision doit être explicable",
     "severity": "medium", "auto_enforce": False},
    {"id": "user_respect", "rule": "Respecter les préférences utilisateur",
     "severity": "high", "auto_enforce": True},
    {"id": "novelty_caution",
     "rule": "Émergences très nouvelles nécessitent validation",
     "severity": "medium", "auto_enforce": True},
]

# Seuils
CONFIDENCE_THRESHOLD = 0.6
RISK_THRESHOLD = 0.7
NOVELTY_THRESHOLD = 0.8
MAX_PENDING = 50


class CognitiveGovernor:
    """Gouverneur cognitif central EXO v16."""

    def __init__(self, initiative_protocol=None, audit_log=None,
                 governance=None, meta_memory=None):
        self._protocol = initiative_protocol
        self._audit = audit_log
        self._governance = governance
        self._memory = meta_memory
        self._governance_log: list[dict] = []
        self._overrides: dict[str, dict] = {}
        self._stats = {
            "initiatives_supervised": 0,
            "initiatives_approved": 0,
            "initiatives_blocked": 0,
            "emergences_supervised": 0,
            "emergences_approved": 0,
            "emergences_blocked": 0,
            "rules_enforced": 0,
            "violations_detected": 0,
            "overrides": 0,
        }

    # ── supervise_initiative ────────────────────────────────
    def supervise_initiative(self, initiative: dict) -> dict:
        """Superviser et arbitrer une initiative autonome."""
        self._stats["initiatives_supervised"] += 1
        gov_id = f"gov_{uuid.uuid4().hex[:8]}"

        agent = initiative.get("agent", "unknown")
        action = initiative.get("action", "unknown")
        domain = initiative.get("domain", "general")
        confidence = initiative.get("confidence", 0.5)
        risk = initiative.get("risk", 0.0)
        cost = initiative.get("budget_cost", 1)

        violations = []
        decision = "approved"

        # Rule 1: Safety check
        if risk > RISK_THRESHOLD:
            violations.append({
                "rule": "safety_first",
                "detail": f"Risk {risk:.2f} exceeds threshold {RISK_THRESHOLD}",
                "severity": "critical",
            })
            decision = "blocked"

        # Rule 2: Confidence check
        if confidence < CONFIDENCE_THRESHOLD and domain != "diagnostic":
            violations.append({
                "rule": "coherence",
                "detail": f"Confidence {confidence:.2f} below {CONFIDENCE_THRESHOLD}",
                "severity": "high",
            })
            if confidence < 0.3:
                decision = "blocked"
            else:
                decision = "needs_approval"

        # Rule 3: Budget check via protocol
        if self._protocol:
            budget_check = self._protocol.check_budget(agent, cost)
            if not budget_check.get("allowed", True):
                violations.append({
                    "rule": "budget_limit",
                    "detail": budget_check.get("reason", "budget_exceeded"),
                    "severity": "high",
                })
                decision = "blocked"

            # Permission check
            perm_check = self._protocol.check_permissions(
                agent, action, {"domain": domain})
            if not perm_check.get("allowed", True):
                violations.append({
                    "rule": "safety_first",
                    "detail": perm_check.get("reason", "permission_denied"),
                    "severity": "critical",
                })
                decision = "blocked"

        # Rule 4: Governance layer
        if self._governance:
            allowed = self._governance.check_permission(
                action, {"domain": domain, "agent": agent})
            if not allowed:
                violations.append({
                    "rule": "user_respect",
                    "detail": f"Governance denied: {action}",
                    "severity": "high",
                })
                decision = "blocked"

        self._stats["violations_detected"] += len(violations)

        if decision == "approved":
            self._stats["initiatives_approved"] += 1
            # Auto-approve via protocol
            if self._protocol:
                validation = self._protocol.require_validation(initiative)
                if validation.get("auto_approved"):
                    self._protocol.approve(validation["initiative_id"])
        else:
            self._stats["initiatives_blocked"] += 1

        result = {
            "id": gov_id,
            "type": "initiative_supervision",
            "initiative": {"agent": agent, "action": action,
                           "domain": domain},
            "decision": decision,
            "violations": violations,
            "violations_count": len(violations),
            "confidence": confidence,
            "risk": risk,
            "timestamp": time.time(),
        }

        self._governance_log.append(result)
        self._trim_log()

        if self._audit:
            self._audit.log_governance({
                "type": "governance_decision",
                "governor": "cognitive_governor",
                "decision": decision,
                "scope": domain,
                "impact": "high" if violations else "low",
                "initiative_agent": agent,
                "initiative_action": action,
            })

        return result

    # ── supervise_emergence ─────────────────────────────────
    def supervise_emergence(self, emergence: dict) -> dict:
        """Superviser une émergence cognitive."""
        self._stats["emergences_supervised"] += 1
        gov_id = f"govem_{uuid.uuid4().hex[:8]}"

        pattern = emergence.get("pattern", "unknown")
        novelty = emergence.get("novelty_score", 0.0)
        viability = emergence.get("viability", 0.0)
        agents = emergence.get("agents_involved", [])
        risk = emergence.get("risk", 0.0)

        decision = "approved"
        violations = []

        # High novelty → caution
        if novelty > NOVELTY_THRESHOLD:
            violations.append({
                "rule": "novelty_caution",
                "detail": f"Novelty {novelty:.2f} exceeds {NOVELTY_THRESHOLD}",
                "severity": "medium",
            })
            decision = "needs_approval"

        # Low viability → block
        if viability < 0.3:
            violations.append({
                "rule": "coherence",
                "detail": f"Viability {viability:.2f} too low",
                "severity": "high",
            })
            decision = "blocked"

        # Safety
        if risk > RISK_THRESHOLD:
            violations.append({
                "rule": "safety_first",
                "detail": f"Emergence risk {risk:.2f} too high",
                "severity": "critical",
            })
            decision = "blocked"

        self._stats["violations_detected"] += len(violations)

        if decision == "approved":
            self._stats["emergences_approved"] += 1
        else:
            self._stats["emergences_blocked"] += 1

        result = {
            "id": gov_id,
            "type": "emergence_supervision",
            "pattern": pattern,
            "decision": decision,
            "violations": violations,
            "novelty_score": novelty,
            "viability": viability,
            "agents_involved": agents,
            "timestamp": time.time(),
        }

        self._governance_log.append(result)
        self._trim_log()

        if self._audit:
            self._audit.log_governance({
                "type": "governance_decision",
                "governor": "cognitive_governor",
                "decision": decision,
                "scope": "emergence",
                "impact": "high" if violations else "medium",
            })

        return result

    # ── enforce_governance_rules ────────────────────────────
    def enforce_governance_rules(self, state: dict) -> dict:
        """Appliquer les règles de gouvernance sur l'état système."""
        self._stats["rules_enforced"] += 1
        enf_id = f"enf_{uuid.uuid4().hex[:8]}"

        violations = []
        actions_taken = []

        # Check active initiatives
        active = state.get("active_initiatives", [])
        for init in active:
            risk = init.get("risk", 0.0)
            if risk > RISK_THRESHOLD:
                violations.append({
                    "rule": "safety_first",
                    "initiative": init.get("id", "?"),
                    "action": "block",
                })
                actions_taken.append({
                    "type": "block_initiative",
                    "initiative": init.get("id"),
                    "reason": "risk_exceeded",
                })

        # Check emergences
        emergences = state.get("active_emergences", [])
        for em in emergences:
            if em.get("viability", 1.0) < 0.2:
                violations.append({
                    "rule": "coherence",
                    "emergence": em.get("id", "?"),
                    "action": "discard",
                })
                actions_taken.append({
                    "type": "discard_emergence",
                    "emergence": em.get("id"),
                    "reason": "low_viability",
                })

        self._stats["violations_detected"] += len(violations)

        result = {
            "id": enf_id,
            "type": "governance_enforcement",
            "rules_checked": len(GOVERNANCE_RULES),
            "violations": violations,
            "actions_taken": actions_taken,
            "compliant": len(violations) == 0,
            "timestamp": time.time(),
        }

        self._governance_log.append(result)
        return result

    # ── override_decision ───────────────────────────────────
    def override_decision(self, decision_id: str,
                          override: dict) -> dict:
        """Surcharger une décision du gouverneur (usage superviseur)."""
        self._stats["overrides"] += 1
        self._overrides[decision_id] = {
            "original_id": decision_id,
            "override": override,
            "timestamp": time.time(),
        }

        if self._audit:
            self._audit.log_governance({
                "type": "governance_override",
                "governor": "cognitive_governor",
                "decision": decision_id,
                "scope": "manual_override",
                "impact": "high",
            })

        return {"overridden": True, "decision_id": decision_id,
                "new_decision": override}

    # ── get_governance_log ──────────────────────────────────
    def get_governance_log(self, limit: int = 50) -> list[dict]:
        return self._governance_log[-limit:]

    # ── health_check ────────────────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "cognitive_governor",
            "status": "ok",
            "log_entries": len(self._governance_log),
            "overrides_active": len(self._overrides),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._governance_log.clear()
        self._overrides.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("CognitiveGovernor restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim_log(self) -> None:
        if len(self._governance_log) > 5000:
            self._governance_log = self._governance_log[-5000:]
