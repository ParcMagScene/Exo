"""
EXO v25 — CognitivePermissionSystem
Permissions cognitives : par agent, couche, module et action.

API:
  grant_permission(entity, action)   → dict
  revoke_permission(entity, action)  → dict
  check_permission(entity, action)   → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("cognitive_permission_system")


class CognitivePermissionSystem:
    """Système de permissions cognitives EXO v25."""

    def __init__(self, governance=None):
        self._governance = governance

        # {entity: {action: {granted, timestamp, context}}}
        self._permissions: dict[str, dict[str, dict]] = {}
        self._history: list[dict] = []
        self._stats = {
            "granted": 0,
            "revoked": 0,
            "checked": 0,
        }

    # ── grant_permission ────────────────────────────────────
    def grant_permission(self, entity: str, action: str) -> dict:
        """Accorder une permission à une entité."""
        self._stats["granted"] += 1

        if entity not in self._permissions:
            self._permissions[entity] = {}

        self._permissions[entity][action] = {
            "granted": True,
            "timestamp": time.time(),
        }

        record = {
            "id": f"pgrnt_{uuid.uuid4().hex[:8]}",
            "operation": "grant",
            "entity": entity,
            "action": action,
            "granted": True,
            "total_permissions": sum(
                len(acts) for acts in self._permissions.values()),
            "timestamp": time.time(),
        }
        self._history.append(record)
        self._trim()

        return record

    # ── revoke_permission ───────────────────────────────────
    def revoke_permission(self, entity: str, action: str) -> dict:
        """Révoquer une permission."""
        self._stats["revoked"] += 1

        revoked = False
        if entity in self._permissions and action in self._permissions[entity]:
            del self._permissions[entity][action]
            if not self._permissions[entity]:
                del self._permissions[entity]
            revoked = True

        record = {
            "id": f"prev_{uuid.uuid4().hex[:8]}",
            "operation": "revoke",
            "entity": entity,
            "action": action,
            "revoked": revoked,
            "total_permissions": sum(
                len(acts) for acts in self._permissions.values()),
            "timestamp": time.time(),
        }
        self._history.append(record)
        self._trim()

        return record

    # ── check_permission ────────────────────────────────────
    def check_permission(self, entity: str, action: str) -> dict:
        """Vérifier si une entité a la permission."""
        self._stats["checked"] += 1

        allowed = False
        if entity in self._permissions and action in self._permissions[entity]:
            allowed = self._permissions[entity][action].get("granted", False)

        return {
            "id": f"pchk_{uuid.uuid4().hex[:8]}",
            "entity": entity,
            "action": action,
            "allowed": allowed,
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "cognitive_permission_system",
            "status": "ok",
            "total_entities": len(self._permissions),
            "total_permissions": sum(
                len(acts) for acts in self._permissions.values()),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._permissions.clear()
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("CognitivePermissionSystem restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-2500:]
