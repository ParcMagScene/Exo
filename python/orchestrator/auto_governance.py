"""
EXO v11 — AutoGovernance (Gouvernance automatique)
Empêche toute dérive ou apprentissage non désiré.
Définit les règles, limites et permissions de l'auto-apprentissage.

IMPORTANT: LearningEngine et AutoTuningEngine appellent
  governance.check_permission(action, context) → bool

API:
  check_permission(action, context) → bool
  set_rules(rules)                  → None
  set_limits(limits)                → None
  set_permissions(permissions)      → None
  get_rules()                       → dict
  get_audit_log(limit)              → list[dict]
  get_stats()                       → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("auto_governance")

# Default governance rules
DEFAULT_RULES = {
    "allow_learn": True,
    "allow_tune": True,
    "allow_optimize": True,
    "max_confidence_override": False,
    "require_user_validation_for": [],  # list of categories requiring user OK
    "blocked_keys": [],  # keys that cannot be learned
    "blocked_categories": [],  # categories blocked
}

DEFAULT_LIMITS = {
    "max_learn_per_session": 200,
    "max_tune_per_session": 50,
    "max_optimize_per_session": 20,
    "min_confidence": 0.3,
}

DEFAULT_PERMISSIONS = {
    "learn": True,
    "tune": True,
    "optimize": True,
    "rollback": True,
    "explain": True,
}


class AutoGovernance:
    """Moteur de gouvernance automatique EXO v11."""

    def __init__(self, meta_memory=None):
        """
        Args:
            meta_memory: MetaMemory (optional) for persisting governance state.
        """
        self._memory = meta_memory
        self._rules = dict(DEFAULT_RULES)
        self._limits = dict(DEFAULT_LIMITS)
        self._permissions = dict(DEFAULT_PERMISSIONS)
        self._session_counters: dict[str, int] = {
            "learn": 0,
            "tune": 0,
            "optimize": 0,
        }
        self._audit_log: list[dict] = []
        self._stats = {
            "checks": 0,
            "allowed": 0,
            "denied": 0,
        }

    # ── Core check ───────────────────────────────────────────
    def check_permission(self, action: str, context: dict | None = None) -> bool:
        """Check if an action is permitted.

        Called by LearningEngine (action="learn") and
        AutoTuningEngine (action="tune").

        Args:
            action: "learn", "tune", "optimize", "rollback", "explain"
            context: dict with details (type, key, parameter, value, etc.)

        Returns:
            True if permitted, False if denied.
        """
        context = context or {}
        self._stats["checks"] += 1

        # Global permission switch
        if not self._permissions.get(action, False):
            self._deny(action, "permission_disabled", context)
            return False

        # Rule-based checks
        if action == "learn":
            return self._check_learn(context)
        elif action == "tune":
            return self._check_tune(context)
        elif action == "optimize":
            return self._check_optimize(context)
        else:
            # Other actions allowed by default if permission is on
            self._allow(action, context)
            return True

    def _check_learn(self, context: dict) -> bool:
        """Check learning permission."""
        if not self._rules.get("allow_learn", True):
            self._deny("learn", "learning_disabled", context)
            return False

        # Session limit
        if self._session_counters["learn"] >= self._limits["max_learn_per_session"]:
            self._deny("learn", "session_limit_reached", context)
            return False

        # Blocked keys
        key = context.get("key", "")
        if key in self._rules.get("blocked_keys", []):
            self._deny("learn", f"blocked_key:{key}", context)
            return False

        # Blocked categories
        cat = context.get("type", context.get("category", ""))
        if cat in self._rules.get("blocked_categories", []):
            self._deny("learn", f"blocked_category:{cat}", context)
            return False

        # User validation required
        if cat in self._rules.get("require_user_validation_for", []):
            # In production, this would prompt the user.
            # For now, we allow but log it.
            self._audit("learn", "needs_user_validation", context)

        self._session_counters["learn"] += 1
        self._allow("learn", context)
        return True

    def _check_tune(self, context: dict) -> bool:
        """Check tuning permission."""
        if not self._rules.get("allow_tune", True):
            self._deny("tune", "tuning_disabled", context)
            return False

        if self._session_counters["tune"] >= self._limits["max_tune_per_session"]:
            self._deny("tune", "session_limit_reached", context)
            return False

        self._session_counters["tune"] += 1
        self._allow("tune", context)
        return True

    def _check_optimize(self, context: dict) -> bool:
        """Check optimization permission."""
        if not self._rules.get("allow_optimize", True):
            self._deny("optimize", "optimization_disabled", context)
            return False

        if self._session_counters["optimize"] >= self._limits["max_optimize_per_session"]:
            self._deny("optimize", "session_limit_reached", context)
            return False

        self._session_counters["optimize"] += 1
        self._allow("optimize", context)
        return True

    # ── Audit helpers ────────────────────────────────────────
    def _allow(self, action: str, context: dict) -> None:
        self._stats["allowed"] += 1
        self._audit(action, "allowed", context)

    def _deny(self, action: str, reason: str, context: dict) -> None:
        self._stats["denied"] += 1
        self._audit(action, f"denied:{reason}", context)
        log.info("Governance denied %s: %s", action, reason)

    def _audit(self, action: str, result: str, context: dict) -> None:
        entry = {
            "action": action,
            "result": result,
            "context_key": context.get("key", context.get("parameter", "")),
            "timestamp": time.time(),
        }
        self._audit_log.append(entry)
        if len(self._audit_log) > 500:
            self._audit_log = self._audit_log[-500:]

    # ── Configuration ────────────────────────────────────────
    def set_rules(self, rules: dict) -> None:
        """Update governance rules."""
        self._rules.update(rules)
        log.info("Governance rules updated: %s", list(rules.keys()))

    def set_limits(self, limits: dict) -> None:
        """Update governance limits."""
        self._limits.update(limits)
        log.info("Governance limits updated: %s", list(limits.keys()))

    def set_permissions(self, permissions: dict) -> None:
        """Update governance permissions."""
        self._permissions.update(permissions)
        log.info("Governance permissions updated: %s", list(permissions.keys()))

    def reset_session_counters(self) -> None:
        """Reset session counters (call at session start)."""
        self._session_counters = {"learn": 0, "tune": 0, "optimize": 0}

    # ── Accessors ────────────────────────────────────────────
    def get_rules(self) -> dict:
        return dict(self._rules)

    def get_limits(self) -> dict:
        return dict(self._limits)

    def get_permissions(self) -> dict:
        return dict(self._permissions)

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        return self._audit_log[-limit:]

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "session_counters": dict(self._session_counters),
        }
