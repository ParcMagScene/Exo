"""
EXO v25 — GovernanceExplainabilityEngine
Explication des décisions de gouvernance : permissions, validations,
conformité, blocages, arbitrages.

API:
  explain_permission(entity, action)  → dict
  explain_governance_decision()       → dict
  explain_block_reason()              → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("governance_explainability_engine")


class GovernanceExplainabilityEngine:
    """Moteur d'explicabilité de gouvernance EXO v25."""

    def __init__(self, governance=None, permissions=None, validation=None,
                 compliance=None, action_control=None, audit=None):
        self._governance = governance
        self._permissions = permissions
        self._validation = validation
        self._compliance = compliance
        self._action_control = action_control
        self._audit = audit

        self._explanations: list[dict] = []
        self._stats = {
            "permissions_explained": 0,
            "decisions_explained": 0,
            "blocks_explained": 0,
        }

    # ── explain_permission ──────────────────────────────────
    def explain_permission(self, entity: str, action: str) -> dict:
        """Expliquer la permission d'une entité pour une action."""
        self._stats["permissions_explained"] += 1

        allowed = False
        reason = "no permission system"

        if self._permissions and hasattr(self._permissions, "check_permission"):
            perm = self._permissions.check_permission(entity, action)
            allowed = perm.get("allowed", False)
            reason = "granted" if allowed else "not granted or revoked"

        record = {
            "id": f"eperm_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "entity": entity,
            "action": action,
            "allowed": allowed,
            "reason": reason,
            "timestamp": time.time(),
        }
        self._explanations.append(record)
        self._trim()

        return record

    # ── explain_governance_decision ─────────────────────────
    def explain_governance_decision(self) -> dict:
        """Expliquer les décisions de gouvernance récentes."""
        self._stats["decisions_explained"] += 1

        # Collecter les stats de validation
        validation_stats = {}
        if self._validation and hasattr(self._validation, "explain_validation"):
            validation_stats = self._validation.explain_validation()

        # Collecter les stats de conformité
        compliance_stats = {}
        if self._compliance and hasattr(self._compliance, "explain_compliance"):
            compliance_stats = self._compliance.explain_compliance()

        record = {
            "id": f"egov_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "validation": {
                "total": validation_stats.get("total_validations", 0),
                "passed": validation_stats.get("passed", 0),
                "failed": validation_stats.get("failed", 0),
            },
            "compliance": {
                "total": compliance_stats.get("total_checks", 0),
                "compliant": compliance_stats.get("compliant", 0),
                "non_compliant": compliance_stats.get("non_compliant", 0),
            },
            "timestamp": time.time(),
        }
        self._explanations.append(record)
        self._trim()

        return record

    # ── explain_block_reason ────────────────────────────────
    def explain_block_reason(self) -> dict:
        """Expliquer les raisons des blocages récents."""
        self._stats["blocks_explained"] += 1

        block_info = {}
        if self._action_control and hasattr(self._action_control, "explain_block"):
            block_info = self._action_control.explain_block()

        audit_info = {}
        if self._audit and hasattr(self._audit, "audit_query"):
            audit_info = self._audit.audit_query({"category": "rejection", "limit": 10})

        record = {
            "id": f"eblk_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "total_blocks": block_info.get("total_blocks", 0),
            "by_reason": block_info.get("by_reason", {}),
            "recent_rejections": audit_info.get("count", 0),
            "timestamp": time.time(),
        }
        self._explanations.append(record)
        self._trim()

        return record

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "governance_explainability_engine",
            "status": "ok",
            "total_explanations": len(self._explanations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._explanations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("GovernanceExplainabilityEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._explanations) > 5000:
            self._explanations = self._explanations[-2500:]
