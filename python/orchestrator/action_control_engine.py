"""
EXO v25 — ActionControlEngine
Contrôle des actions : blocage actions interdites, incohérentes,
non conformes, non validées, non permises.

API:
  control_action(action)   → dict
  block_action(action)     → dict
  explain_block()          → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("action_control_engine")


class ActionControlEngine:
    """Moteur de contrôle des actions EXO v25."""

    def __init__(self, governance=None, permissions=None,
                 validation=None, compliance=None):
        self._governance = governance
        self._permissions = permissions
        self._validation = validation
        self._compliance = compliance

        self._controls: list[dict] = []
        self._blocks: list[dict] = []
        self._stats = {
            "controlled": 0,
            "blocked": 0,
            "explained": 0,
        }

    # ── control_action ──────────────────────────────────────
    def control_action(self, action: dict) -> dict:
        """Contrôler une action (vérifier permissions, validation, conformité)."""
        self._stats["controlled"] += 1

        name = action.get("name", "unknown")
        entity = action.get("entity", "unknown")
        reasons = []

        # 1. Vérifier permission
        perm_ok = True
        if self._permissions and hasattr(self._permissions, "check_permission"):
            perm = self._permissions.check_permission(entity, name)
            perm_ok = perm.get("allowed", True)
            if not perm_ok:
                reasons.append("permission_denied")

        # 2. Vérifier validation
        valid_ok = True
        if self._validation and hasattr(self._validation, "validate_action"):
            val = self._validation.validate_action(action)
            valid_ok = val.get("validated", True)
            if not valid_ok:
                reasons.append("validation_failed")

        # 3. Vérifier conformité
        comp_ok = True
        if self._compliance and hasattr(self._compliance, "check_compliance"):
            comp = self._compliance.check_compliance(action)
            comp_ok = comp.get("compliant", True)
            if not comp_ok:
                reasons.append("compliance_violation")

        allowed = perm_ok and valid_ok and comp_ok

        record = {
            "id": f"ctrl_{uuid.uuid4().hex[:8]}",
            "controlled": True,
            "allowed": allowed,
            "action": name,
            "entity": entity,
            "block_reasons": reasons,
            "timestamp": time.time(),
        }
        self._controls.append(record)
        self._trim_controls()

        if not allowed:
            self._blocks.append(record)
            self._stats["blocked"] += 1
            if len(self._blocks) > 5000:
                self._blocks = self._blocks[-2500:]

        return record

    # ── block_action ────────────────────────────────────────
    def block_action(self, action: dict) -> dict:
        """Bloquer explicitement une action."""
        self._stats["blocked"] += 1

        name = action.get("name", "unknown")
        entity = action.get("entity", "unknown")
        reason = action.get("reason", "manual_block")

        record = {
            "id": f"blk_{uuid.uuid4().hex[:8]}",
            "blocked": True,
            "action": name,
            "entity": entity,
            "reason": reason,
            "timestamp": time.time(),
        }
        self._blocks.append(record)
        if len(self._blocks) > 5000:
            self._blocks = self._blocks[-2500:]

        return record

    # ── explain_block ───────────────────────────────────────
    def explain_block(self) -> dict:
        """Expliquer les blocages récents."""
        self._stats["explained"] += 1

        recent = self._blocks[-10:] if self._blocks else []
        total = len(self._blocks)

        by_reason: dict[str, int] = {}
        for b in self._blocks:
            for r in (b.get("block_reasons", []) or [b.get("reason", "unknown")]):
                by_reason[r] = by_reason.get(r, 0) + 1

        return {
            "id": f"bex_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "total_blocks": total,
            "by_reason": by_reason,
            "recent": recent,
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "action_control_engine",
            "status": "ok",
            "total_controls": len(self._controls),
            "total_blocks": len(self._blocks),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._controls.clear()
        self._blocks.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ActionControlEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim_controls(self) -> None:
        if len(self._controls) > 5000:
            self._controls = self._controls[-2500:]
