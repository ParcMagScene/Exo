"""
EXO v25 — MultiLevelValidationEngine
Validation multi‑niveaux : logique, contextuelle, temporelle, sécurité, cohérence.

API:
  validate_action(action)      → dict
  validate_decision(decision)  → dict
  explain_validation()         → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("multi_level_validation_engine")


class MultiLevelValidationEngine:
    """Moteur de validation multi‑niveaux EXO v25."""

    LEVELS = ("logic", "context", "temporal", "security", "coherence")

    def __init__(self, governance=None, permissions=None):
        self._governance = governance
        self._permissions = permissions

        self._validations: list[dict] = []
        self._stats = {
            "actions_validated": 0,
            "decisions_validated": 0,
            "explained": 0,
        }

    # ── validate_action ─────────────────────────────────────
    def validate_action(self, action: dict) -> dict:
        """Valider une action à tous les niveaux."""
        self._stats["actions_validated"] += 1

        name = action.get("name", "unknown")
        entity = action.get("entity", "unknown")
        context = action.get("context", {})

        results = {}
        for level in self.LEVELS:
            results[level] = self._check_level(level, action)

        all_valid = all(r["valid"] for r in results.values())
        failed = [l for l, r in results.items() if not r["valid"]]

        record = {
            "id": f"va_{uuid.uuid4().hex[:8]}",
            "validated": all_valid,
            "action": name,
            "entity": entity,
            "levels": results,
            "failed_levels": failed,
            "timestamp": time.time(),
        }
        self._validations.append(record)
        self._trim()

        return record

    # ── validate_decision ───────────────────────────────────
    def validate_decision(self, decision: dict) -> dict:
        """Valider une décision à tous les niveaux."""
        self._stats["decisions_validated"] += 1

        name = decision.get("name", "unknown")
        rationale = decision.get("rationale", "")

        results = {}
        for level in self.LEVELS:
            results[level] = self._check_level(level, decision)

        all_valid = all(r["valid"] for r in results.values())
        failed = [l for l, r in results.items() if not r["valid"]]

        record = {
            "id": f"vd_{uuid.uuid4().hex[:8]}",
            "validated": all_valid,
            "decision": name,
            "rationale": rationale,
            "levels": results,
            "failed_levels": failed,
            "timestamp": time.time(),
        }
        self._validations.append(record)
        self._trim()

        return record

    # ── explain_validation ──────────────────────────────────
    def explain_validation(self) -> dict:
        """Expliquer les résultats de validation récents."""
        self._stats["explained"] += 1

        recent = self._validations[-10:] if self._validations else []
        total = len(self._validations)
        passed = sum(1 for v in self._validations if v.get("validated"))
        failed = total - passed

        return {
            "id": f"vex_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "total_validations": total,
            "passed": passed,
            "failed": failed,
            "recent": recent,
            "timestamp": time.time(),
        }

    # ── internal ────────────────────────────────────────────
    def _check_level(self, level: str, item: dict) -> dict:
        """Vérification par niveau."""
        name = item.get("name", "unknown")
        entity = item.get("entity", "unknown")

        if level == "logic":
            valid = bool(name and name != "unknown")
            return {"valid": valid, "reason": "name required" if not valid else "ok"}

        if level == "context":
            ctx = item.get("context", {})
            valid = isinstance(ctx, dict)
            return {"valid": valid, "reason": "context must be dict" if not valid else "ok"}

        if level == "temporal":
            ts = item.get("timestamp", time.time())
            valid = ts <= time.time() + 1
            return {"valid": valid, "reason": "future timestamp" if not valid else "ok"}

        if level == "security":
            # Vérifier la permission si le système est branché
            if self._permissions and hasattr(self._permissions, "check_permission"):
                perm = self._permissions.check_permission(entity, name)
                return {"valid": perm.get("allowed", True),
                        "reason": "permission denied" if not perm.get("allowed", True) else "ok"}
            return {"valid": True, "reason": "ok"}

        if level == "coherence":
            valid = name != "" and entity != ""
            return {"valid": valid, "reason": "empty fields" if not valid else "ok"}

        return {"valid": True, "reason": "ok"}

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "multi_level_validation_engine",
            "status": "ok",
            "total_validations": len(self._validations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._validations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("MultiLevelValidationEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._validations) > 5000:
            self._validations = self._validations[-2500:]
