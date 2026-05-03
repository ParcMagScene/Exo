"""
EXO v25 — ComplianceEngine
Conformité cognitive : règles, sécurité, permissions, cohérence, contexte.

API:
  check_compliance(action)     → dict
  enforce_compliance(action)   → dict
  explain_compliance()         → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("compliance_engine")


class ComplianceEngine:
    """Moteur de conformité EXO v25."""

    COMPLIANCE_DOMAINS = (
        "rules", "security", "permissions", "coherence", "context",
    )

    def __init__(self, governance=None, permissions=None, policies=None):
        self._governance = governance
        self._permissions = permissions
        self._policies = policies

        self._checks: list[dict] = []
        self._enforcements: list[dict] = []
        self._stats = {
            "checked": 0,
            "enforced": 0,
            "explained": 0,
        }

    # ── check_compliance ────────────────────────────────────
    def check_compliance(self, action: dict) -> dict:
        """Vérifier la conformité d'une action."""
        self._stats["checked"] += 1

        name = action.get("name", "unknown")
        entity = action.get("entity", "unknown")

        results = {}
        for domain in self.COMPLIANCE_DOMAINS:
            results[domain] = self._check_domain(domain, action)

        compliant = all(r["compliant"] for r in results.values())
        violations = [d for d, r in results.items() if not r["compliant"]]

        record = {
            "id": f"cc_{uuid.uuid4().hex[:8]}",
            "compliant": compliant,
            "action": name,
            "entity": entity,
            "domains": results,
            "violations": violations,
            "timestamp": time.time(),
        }
        self._checks.append(record)
        self._trim_checks()

        return record

    # ── enforce_compliance ──────────────────────────────────
    def enforce_compliance(self, action: dict) -> dict:
        """Appliquer les règles de conformité (bloquer si non conforme)."""
        self._stats["enforced"] += 1

        check = self.check_compliance(action)
        allowed = check["compliant"]

        record = {
            "id": f"ce_{uuid.uuid4().hex[:8]}",
            "enforced": True,
            "allowed": allowed,
            "action": action.get("name", "unknown"),
            "violations": check["violations"],
            "timestamp": time.time(),
        }
        self._enforcements.append(record)
        if len(self._enforcements) > 5000:
            self._enforcements = self._enforcements[-2500:]

        return record

    # ── explain_compliance ──────────────────────────────────
    def explain_compliance(self) -> dict:
        """Expliquer l'état de conformité."""
        self._stats["explained"] += 1

        total = len(self._checks)
        compliant = sum(1 for c in self._checks if c.get("compliant"))
        non_compliant = total - compliant

        violations_count: dict[str, int] = {}
        for c in self._checks:
            for v in c.get("violations", []):
                violations_count[v] = violations_count.get(v, 0) + 1

        return {
            "id": f"cex_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "total_checks": total,
            "compliant": compliant,
            "non_compliant": non_compliant,
            "violations_by_domain": violations_count,
            "timestamp": time.time(),
        }

    # ── internal ────────────────────────────────────────────
    def _check_domain(self, domain: str, action: dict) -> dict:
        name = action.get("name", "unknown")
        entity = action.get("entity", "unknown")

        if domain == "rules":
            valid = bool(name and name != "unknown")
            return {"compliant": valid,
                    "reason": "action name required" if not valid else "ok"}

        if domain == "security":
            sensitive = action.get("sensitive", False)
            if sensitive and not action.get("authorized", False):
                return {"compliant": False, "reason": "sensitive action not authorized"}
            return {"compliant": True, "reason": "ok"}

        if domain == "permissions":
            if self._permissions and hasattr(self._permissions, "check_permission"):
                perm = self._permissions.check_permission(entity, name)
                allowed = perm.get("allowed", True)
                return {"compliant": allowed,
                        "reason": "permission denied" if not allowed else "ok"}
            return {"compliant": True, "reason": "ok"}

        if domain == "coherence":
            valid = entity != "" and name != ""
            return {"compliant": valid,
                    "reason": "empty fields" if not valid else "ok"}

        if domain == "context":
            ctx = action.get("context", {})
            return {"compliant": isinstance(ctx, dict),
                    "reason": "context must be dict" if not isinstance(ctx, dict) else "ok"}

        return {"compliant": True, "reason": "ok"}

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "compliance_engine",
            "status": "ok",
            "total_checks": len(self._checks),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._checks.clear()
        self._enforcements.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ComplianceEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim_checks(self) -> None:
        if len(self._checks) > 5000:
            self._checks = self._checks[-2500:]
