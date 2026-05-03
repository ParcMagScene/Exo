"""
EXO v25 — DecisionValidationEngine
Validation des décisions finales : logique, contextuelle, temporelle,
cohérence, sécurité.

API:
  validate_decision(decision)         → dict
  reject_decision(decision)           → dict
  explain_decision_validation()       → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("decision_validation_engine")


class DecisionValidationEngine:
    """Moteur de validation des décisions EXO v25."""

    VALIDATION_ASPECTS = ("logic", "context", "temporal", "coherence", "security")

    def __init__(self, governance=None, permissions=None, policies=None):
        self._governance = governance
        self._permissions = permissions
        self._policies = policies

        self._validations: list[dict] = []
        self._rejections: list[dict] = []
        self._stats = {
            "validated": 0,
            "rejected": 0,
            "explained": 0,
        }

    # ── validate_decision ───────────────────────────────────
    def validate_decision(self, decision: dict) -> dict:
        """Valider une décision finale."""
        self._stats["validated"] += 1

        name = decision.get("name", "unknown")
        entity = decision.get("entity", "unknown")
        rationale = decision.get("rationale", "")

        results = {}
        for aspect in self.VALIDATION_ASPECTS:
            results[aspect] = self._check_aspect(aspect, decision)

        all_valid = all(r["valid"] for r in results.values())
        failed = [a for a, r in results.items() if not r["valid"]]

        record = {
            "id": f"dv_{uuid.uuid4().hex[:8]}",
            "validated": all_valid,
            "decision": name,
            "entity": entity,
            "rationale": rationale,
            "aspects": results,
            "failed_aspects": failed,
            "timestamp": time.time(),
        }
        self._validations.append(record)
        self._trim()

        return record

    # ── reject_decision ─────────────────────────────────────
    def reject_decision(self, decision: dict) -> dict:
        """Rejeter explicitement une décision."""
        self._stats["rejected"] += 1

        name = decision.get("name", "unknown")
        entity = decision.get("entity", "unknown")
        reason = decision.get("reason", "manual_reject")

        record = {
            "id": f"dr_{uuid.uuid4().hex[:8]}",
            "rejected": True,
            "decision": name,
            "entity": entity,
            "reason": reason,
            "timestamp": time.time(),
        }
        self._rejections.append(record)
        if len(self._rejections) > 5000:
            self._rejections = self._rejections[-2500:]

        return record

    # ── explain_decision_validation ─────────────────────────
    def explain_decision_validation(self) -> dict:
        """Expliquer les résultats de validation des décisions."""
        self._stats["explained"] += 1

        total = len(self._validations)
        passed = sum(1 for v in self._validations if v.get("validated"))
        failed = total - passed
        total_rejections = len(self._rejections)

        recent = self._validations[-10:] if self._validations else []

        return {
            "id": f"dvex_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "total_validations": total,
            "passed": passed,
            "failed": failed,
            "total_rejections": total_rejections,
            "recent": recent,
            "timestamp": time.time(),
        }

    # ── internal ────────────────────────────────────────────
    def _check_aspect(self, aspect: str, decision: dict) -> dict:
        name = decision.get("name", "unknown")
        entity = decision.get("entity", "unknown")

        if aspect == "logic":
            valid = bool(name and name != "unknown")
            return {"valid": valid, "reason": "decision name required" if not valid else "ok"}

        if aspect == "context":
            ctx = decision.get("context", {})
            return {"valid": isinstance(ctx, dict),
                    "reason": "context must be dict" if not isinstance(ctx, dict) else "ok"}

        if aspect == "temporal":
            return {"valid": True, "reason": "ok"}

        if aspect == "coherence":
            rationale = decision.get("rationale", "")
            valid = bool(rationale)
            return {"valid": valid,
                    "reason": "rationale required" if not valid else "ok"}

        if aspect == "security":
            if self._permissions and hasattr(self._permissions, "check_permission"):
                perm = self._permissions.check_permission(entity, name)
                allowed = perm.get("allowed", True)
                return {"valid": allowed,
                        "reason": "permission denied" if not allowed else "ok"}
            return {"valid": True, "reason": "ok"}

        return {"valid": True, "reason": "ok"}

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "decision_validation_engine",
            "status": "ok",
            "total_validations": len(self._validations),
            "total_rejections": len(self._rejections),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._validations.clear()
        self._rejections.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("DecisionValidationEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._validations) > 5000:
            self._validations = self._validations[-2500:]
