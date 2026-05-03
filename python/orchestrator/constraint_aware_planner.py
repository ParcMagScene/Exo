"""
EXO v22 — ConstraintAwarePlanner
Intègre les contraintes logiques, temporelles, structurelles,
de dépendance, de ressources et multi-agents dans la planification.

API:
  apply_constraints(plan: dict)     → dict
  validate_constraints(plan: dict)  → dict
  explain_constraints()             → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("constraint_aware_planner")


class ConstraintAwarePlanner:
    """Planificateur avec contraintes EXO v22."""

    CONSTRAINT_TYPES = {
        "logical", "temporal", "dependency",
        "resource", "multi_agent", "structural",
    }

    def __init__(self, governance=None, constraint_solver=None):
        self._governance = governance
        self._constraint_solver = constraint_solver

        self._applications: list[dict] = []
        self._stats = {
            "applied": 0,
            "validated": 0,
            "explanations": 0,
        }

    # ── apply_constraints ───────────────────────────────────
    def apply_constraints(self, plan: dict) -> dict:
        """Appliquer les contraintes à un plan."""
        self._stats["applied"] += 1

        steps = plan.get("steps", [])
        constraints = plan.get("constraints", [])

        applied = []
        violations = []

        for c in constraints:
            c_type = c.get("type", "logical")
            c_name = c.get("name", "unnamed")
            target_step = c.get("step", None)
            condition = c.get("condition", {})

            if c_type not in self.CONSTRAINT_TYPES:
                c_type = "logical"

            satisfied = True
            reason = ""

            if c_type == "dependency":
                dep = condition.get("depends_on")
                if dep is not None and target_step is not None:
                    if dep >= target_step:
                        satisfied = False
                        reason = f"Dépendance circulaire : étape {target_step} dépend de {dep}"

            elif c_type == "temporal":
                max_time = condition.get("max_duration")
                if max_time is not None and max_time <= 0:
                    satisfied = False
                    reason = "Durée maximale invalide"

            elif c_type == "resource":
                available = condition.get("available", 0)
                required = condition.get("required", 0)
                if required > available:
                    satisfied = False
                    reason = f"Ressources insuffisantes : {required} requis, {available} disponibles"

            if satisfied:
                applied.append({
                    "name": c_name, "type": c_type, "status": "applied",
                })
            else:
                violations.append({
                    "name": c_name, "type": c_type, "status": "violated",
                    "reason": reason,
                })

        result = {
            "id": f"cap_{uuid.uuid4().hex[:8]}",
            "applied": True,
            "constraints_applied": len(applied),
            "violations_count": len(violations),
            "applied_list": applied,
            "violations": violations,
            "feasible": len(violations) == 0,
            "timestamp": time.time(),
        }
        self._applications.append(result)
        self._trim()

        return result

    # ── validate_constraints ────────────────────────────────
    def validate_constraints(self, plan: dict) -> dict:
        """Valider que toutes les contraintes sont satisfaites."""
        self._stats["validated"] += 1

        result = self.apply_constraints(plan)

        return {
            "id": f"vcap_{uuid.uuid4().hex[:8]}",
            "validated": True,
            "feasible": result["feasible"],
            "constraints_checked": result["constraints_applied"] + result["violations_count"],
            "violations_count": result["violations_count"],
            "violations": result["violations"],
            "timestamp": time.time(),
        }

    # ── explain_constraints ─────────────────────────────────
    def explain_constraints(self) -> dict:
        """Expliquer les contraintes du dernier plan traité."""
        self._stats["explanations"] += 1

        if not self._applications:
            return {
                "explained": False,
                "error": "no_applications",
                "timestamp": time.time(),
            }

        last = self._applications[-1]
        reasons = [
            f"Contraintes appliquées : {last['constraints_applied']}.",
            f"Violations : {last['violations_count']}.",
        ]
        if last["feasible"]:
            reasons.append("Le plan est faisable — toutes les contraintes sont satisfaites.")
        else:
            reasons.append("Le plan n'est PAS faisable.")
            for v in last["violations"]:
                reasons.append(f"  {v['name']} ({v['type']}) : {v['reason']}.")

        return {
            "id": f"ecap_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "feasible": last["feasible"],
            "reasons": reasons,
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "constraint_aware_planner",
            "status": "ok",
            "total_applications": len(self._applications),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._applications.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ConstraintAwarePlanner restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._applications) > 5000:
            self._applications = self._applications[-2500:]
