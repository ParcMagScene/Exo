"""
EXO v25 — GovernanceSupervisor
Superviseur de gouvernance cognitive : permissions, validations,
conformité, audit, actions.

API:
  supervise_governance()        → dict
  enforce_governance_rules()    → dict
  governance_health_check()     → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("governance_supervisor")


class GovernanceSupervisor:
    """Superviseur de gouvernance EXO v25."""

    def __init__(self, governance=None, permissions=None, validation=None,
                 audit=None, compliance=None, policies=None,
                 action_control=None, decision_validation=None):
        self._governance = governance
        self._permissions = permissions
        self._validation = validation
        self._audit = audit
        self._compliance = compliance
        self._policies = policies
        self._action_control = action_control
        self._decision_validation = decision_validation

        self._reports: list[dict] = []
        self._stats = {
            "supervised": 0,
            "enforced": 0,
            "health_checked": 0,
        }

    # ── supervise_governance ────────────────────────────────
    def supervise_governance(self) -> dict:
        """Superviser l'ensemble de la gouvernance."""
        self._stats["supervised"] += 1

        modules_status = {}
        for name, mod in self._all_modules().items():
            if hasattr(mod, "health_check"):
                h = mod.health_check()
                modules_status[name] = {
                    "status": h.get("status", "unknown"),
                    "service": h.get("service", name),
                }
            else:
                modules_status[name] = {"status": "no_health_check"}

        all_ok = all(s["status"] == "ok" for s in modules_status.values())
        degraded = [n for n, s in modules_status.items() if s["status"] != "ok"]

        record = {
            "id": f"sup_{uuid.uuid4().hex[:8]}",
            "supervised": True,
            "overall_status": "healthy" if all_ok else "degraded",
            "modules_count": len(modules_status),
            "modules": modules_status,
            "degraded": degraded,
            "timestamp": time.time(),
        }
        self._reports.append(record)
        self._trim()

        return record

    # ── enforce_governance_rules ────────────────────────────
    def enforce_governance_rules(self) -> dict:
        """Appliquer les règles de gouvernance globales."""
        self._stats["enforced"] += 1

        actions = []

        # Vérifier que tous les modules sont opérationnels
        for name, mod in self._all_modules().items():
            if hasattr(mod, "health_check"):
                h = mod.health_check()
                if h.get("status") != "ok":
                    if hasattr(mod, "restart"):
                        mod.restart()
                        actions.append({
                            "module": name,
                            "action": "restarted",
                            "reason": f"status was {h.get('status')}",
                        })

        return {
            "id": f"enf_{uuid.uuid4().hex[:8]}",
            "enforced": True,
            "actions_taken": len(actions),
            "actions": actions,
            "timestamp": time.time(),
        }

    # ── governance_health_check ─────────────────────────────
    def governance_health_check(self) -> dict:
        """Bilan de santé global de la gouvernance."""
        self._stats["health_checked"] += 1

        stats_all = {}
        for name, mod in self._all_modules().items():
            if hasattr(mod, "get_stats"):
                stats_all[name] = mod.get_stats()

        return {
            "id": f"ghc_{uuid.uuid4().hex[:8]}",
            "governance_healthy": True,
            "modules_count": len(stats_all),
            "module_stats": stats_all,
            "timestamp": time.time(),
        }

    # ── internal ────────────────────────────────────────────
    def _all_modules(self) -> dict:
        mods = {}
        if self._permissions:
            mods["permissions"] = self._permissions
        if self._validation:
            mods["validation"] = self._validation
        if self._audit:
            mods["audit"] = self._audit
        if self._compliance:
            mods["compliance"] = self._compliance
        if self._policies:
            mods["policies"] = self._policies
        if self._action_control:
            mods["action_control"] = self._action_control
        if self._decision_validation:
            mods["decision_validation"] = self._decision_validation
        return mods

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "governance_supervisor",
            "status": "ok",
            "total_reports": len(self._reports),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._reports.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("GovernanceSupervisor restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._reports) > 5000:
            self._reports = self._reports[-2500:]
