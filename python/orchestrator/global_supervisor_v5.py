"""
EXO v15 — GlobalSupervisorV5 (Supervision multi-niveaux)
Surveille agents, inférences, simulations, cohérence et sécurité.
Arbitre conflits, valide décisions.

API:
  supervise_all()               → dict
  enforce_global_rules(state)   → dict
  resolve_global_conflicts(conflicts) → dict
  validate_decision(decision)   → dict
  get_supervision_log(limit)    → list[dict]
  health_check()                → dict
  restart()                     → None
  get_stats()                   → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("global_supervisor_v5")


class GlobalSupervisorV5:
    """Supervision multi-niveaux EXO v15."""

    GLOBAL_RULES = [
        {"id": "safety_first", "rule": "Toute action doit être sûre",
         "severity": "critical"},
        {"id": "consistency", "rule": "Les décisions doivent être cohérentes",
         "severity": "high"},
        {"id": "explainability", "rule": "Toute décision doit être explicable",
         "severity": "medium"},
        {"id": "efficiency", "rule": "Préférer les solutions efficaces",
         "severity": "low"},
    ]

    def __init__(self, meta_memory=None, governance=None,
                 meta_cognition=None, distributed_cognition=None):
        self._memory = meta_memory
        self._governance = governance
        self._meta_cog = meta_cognition
        self._distrib = distributed_cognition
        self._supervision_log: list[dict] = []
        self._stats = {
            "supervisions": 0,
            "rules_enforced": 0,
            "conflicts_resolved": 0,
            "decisions_validated": 0,
            "violations_detected": 0,
        }

    # ── supervise_all ───────────────────────────────────────
    def supervise_all(self) -> dict:
        """Superviser l'ensemble du système cognitif."""
        self._stats["supervisions"] += 1
        sup_id = f"sup_{uuid.uuid4().hex[:8]}"

        reports = []

        # Check distributed agents
        if self._distrib:
            hc = self._distrib.health_check()
            reports.append({
                "subsystem": "distributed_cognition",
                "status": hc.get("status", "unknown"),
                "agents_active": hc.get("agents_active", 0),
            })

        # Check meta-cognition
        if self._meta_cog:
            hc = self._meta_cog.health_check()
            reports.append({
                "subsystem": "meta_cognition",
                "status": hc.get("status", "unknown"),
                "reflections": hc.get("reflections_count", 0),
            })

        all_ok = all(r.get("status") == "ok" for r in reports)

        supervision = {
            "id": sup_id,
            "type": "full_supervision",
            "subsystems_checked": len(reports),
            "reports": reports,
            "overall_status": "healthy" if all_ok else "degraded",
            "timestamp": time.time(),
        }
        self._supervision_log.append(supervision)
        return supervision

    # ── enforce_global_rules ────────────────────────────────
    def enforce_global_rules(self, state: dict) -> dict:
        """Appliquer les règles globales sur l'état courant."""
        self._stats["rules_enforced"] += 1
        enf_id = f"enf_{uuid.uuid4().hex[:8]}"

        violations = []
        decisions = state.get("decisions", [])
        actions = state.get("actions", [])

        # Safety rule
        for a in actions:
            if a.get("risk", 0) > 0.8:
                violations.append({
                    "rule": "safety_first",
                    "severity": "critical",
                    "detail": f"Action risquée: {a.get('action', '?')} "
                              f"(risk={a.get('risk')})",
                    "action": "block",
                })
                self._stats["violations_detected"] += 1

        # Consistency rule
        if self._meta_cog:
            consistency = self._meta_cog.enforce_self_consistency(state)
            if not consistency.get("consistent", True):
                for c in consistency.get("conflicts", []):
                    violations.append({
                        "rule": "consistency",
                        "severity": "high",
                        "detail": c.get("detail", "Conflit détecté"),
                        "action": "review",
                    })
                    self._stats["violations_detected"] += 1

        # Explainability rule
        for d in decisions:
            if not d.get("reasoning"):
                violations.append({
                    "rule": "explainability",
                    "severity": "medium",
                    "detail": f"Décision sans raisonnement: "
                              f"{d.get('action', '?')}",
                    "action": "require_explanation",
                })
                self._stats["violations_detected"] += 1

        result = {
            "id": enf_id,
            "type": "rules_enforcement",
            "rules_checked": len(self.GLOBAL_RULES),
            "violations": violations,
            "compliant": len(violations) == 0,
            "timestamp": time.time(),
        }
        self._supervision_log.append(result)
        return result

    # ── resolve_global_conflicts ────────────────────────────
    def resolve_global_conflicts(self, conflicts: list[dict]) -> dict:
        """Arbitrer des conflits au niveau global."""
        self._stats["conflicts_resolved"] += 1
        res_id = f"res_{uuid.uuid4().hex[:8]}"

        resolutions = []
        for conflict in conflicts:
            ctype = conflict.get("type", "unknown")
            resolution = {
                "conflict": ctype,
                "resolution": "prefer_safe_option",
                "detail": "",
            }

            if ctype == "contradiction":
                resolution["resolution"] = "remove_weaker"
                resolution["detail"] = ("Supprimer la croyance "
                                        "la moins confiante")
            elif ctype == "decision_conflict":
                resolution["resolution"] = "prefer_conservative"
                resolution["detail"] = ("Préférer l'action la plus "
                                        "conservative")
            elif ctype == "resource_contention":
                resolution["resolution"] = "priority_based"
                resolution["detail"] = "Allouer selon la priorité"

            resolutions.append(resolution)

        result = {
            "id": res_id,
            "type": "conflict_resolution",
            "conflicts_count": len(conflicts),
            "resolutions": resolutions,
            "all_resolved": True,
            "timestamp": time.time(),
        }
        self._supervision_log.append(result)
        return result

    # ── validate_decision ───────────────────────────────────
    def validate_decision(self, decision: dict) -> dict:
        """Valider une décision avant exécution."""
        self._stats["decisions_validated"] += 1
        val_id = f"val_{uuid.uuid4().hex[:8]}"

        issues = []
        confidence = decision.get("confidence", 0.5)
        risk = decision.get("risk", 0.1)

        if confidence < 0.3:
            issues.append("Confiance insuffisante (<0.3)")
        if risk > 0.7:
            issues.append("Risque trop élevé (>0.7)")
        if not decision.get("reasoning"):
            issues.append("Pas de raisonnement fourni")

        # Governance check
        if self._governance:
            perm = self._governance.check_permission(
                "learn",
                {"action": "validate_decision",
                 "decision": decision.get("action")})
            if not perm.get("allowed", True):
                issues.append(f"Gouvernance: {perm.get('reason', 'refusé')}")

        validation = {
            "id": val_id,
            "type": "decision_validation",
            "decision": decision.get("action", "unknown"),
            "approved": len(issues) == 0,
            "issues": issues,
            "confidence": confidence,
            "risk": risk,
            "timestamp": time.time(),
        }
        self._supervision_log.append(validation)
        return validation

    # ── get_supervision_log ─────────────────────────────────
    def get_supervision_log(self, limit: int = 20) -> list[dict]:
        return self._supervision_log[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "global_supervisor_v5",
            "status": "ok",
            "log_size": len(self._supervision_log),
            "violations": self._stats["violations_detected"],
        }

    def restart(self) -> None:
        self._supervision_log.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("GlobalSupervisorV5 restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
