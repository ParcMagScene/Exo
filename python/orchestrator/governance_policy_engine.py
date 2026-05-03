"""
EXO v25 — GovernancePolicyEngine
Politiques de gouvernance cognitive : sécurité, cohérence, permissions,
validation, supervision.

API:
  load_policies(policies)    → dict
  apply_policy(policy)       → dict
  explain_policy(policy)     → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("governance_policy_engine")


class GovernancePolicyEngine:
    """Moteur de politiques de gouvernance EXO v25."""

    POLICY_TYPES = {
        "security", "coherence", "permissions",
        "validation", "supervision",
    }

    def __init__(self, governance=None):
        self._governance = governance

        self._policies: dict[str, dict] = {}
        self._history: list[dict] = []
        self._stats = {
            "loaded": 0,
            "applied": 0,
            "explained": 0,
        }

    # ── load_policies ───────────────────────────────────────
    def load_policies(self, policies: list[dict]) -> dict:
        """Charger un ensemble de politiques."""
        self._stats["loaded"] += 1

        loaded = []
        for p in policies:
            name = p.get("name", "")
            ptype = p.get("type", "unknown")
            if not name:
                continue
            self._policies[name] = {
                "name": name,
                "type": ptype,
                "rules": p.get("rules", []),
                "enabled": p.get("enabled", True),
                "loaded_at": time.time(),
            }
            loaded.append(name)

        record = {
            "id": f"pl_{uuid.uuid4().hex[:8]}",
            "loaded": True,
            "count": len(loaded),
            "policies": loaded,
            "total_policies": len(self._policies),
            "timestamp": time.time(),
        }
        self._history.append(record)
        self._trim()

        return record

    # ── apply_policy ────────────────────────────────────────
    def apply_policy(self, policy: str) -> dict:
        """Appliquer une politique par nom."""
        self._stats["applied"] += 1

        pol = self._policies.get(policy)
        if pol is None:
            return {
                "id": f"pap_{uuid.uuid4().hex[:8]}",
                "applied": False,
                "policy": policy,
                "error": "policy_not_found",
                "timestamp": time.time(),
            }

        if not pol.get("enabled", True):
            return {
                "id": f"pap_{uuid.uuid4().hex[:8]}",
                "applied": False,
                "policy": policy,
                "error": "policy_disabled",
                "timestamp": time.time(),
            }

        rules = pol.get("rules", [])
        return {
            "id": f"pap_{uuid.uuid4().hex[:8]}",
            "applied": True,
            "policy": policy,
            "type": pol["type"],
            "rules_count": len(rules),
            "timestamp": time.time(),
        }

    # ── explain_policy ──────────────────────────────────────
    def explain_policy(self, policy: str) -> dict:
        """Expliquer une politique."""
        self._stats["explained"] += 1

        pol = self._policies.get(policy)
        if pol is None:
            return {
                "id": f"pex_{uuid.uuid4().hex[:8]}",
                "explained": False,
                "policy": policy,
                "error": "policy_not_found",
                "timestamp": time.time(),
            }

        return {
            "id": f"pex_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "policy": policy,
            "type": pol["type"],
            "enabled": pol["enabled"],
            "rules_count": len(pol.get("rules", [])),
            "rules": pol.get("rules", []),
            "loaded_at": pol["loaded_at"],
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "governance_policy_engine",
            "status": "ok",
            "total_policies": len(self._policies),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._policies.clear()
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("GovernancePolicyEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-2500:]
