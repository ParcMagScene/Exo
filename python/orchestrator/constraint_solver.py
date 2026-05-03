"""
EXO v21 — ConstraintSolver
Solveur de contraintes : logiques, temporelles, de dépendance,
de ressources, multi-agents.

API:
  solve_constraints(constraint_set: dict)   → dict
  check_constraints(constraint_set: dict)   → dict
  explain_constraints()                     → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("constraint_solver")


class ConstraintSolver:
    """Solveur de contraintes EXO v21."""

    def __init__(self, governance=None, rule_engine=None):
        self._governance = governance
        self._rule_engine = rule_engine

        self._constraints: list[dict] = []
        self._solutions: list[dict] = []
        self._stats = {
            "solved": 0,
            "checked": 0,
            "explanations": 0,
        }

    # ── solve_constraints ───────────────────────────────────
    def solve_constraints(self, constraint_set: dict) -> dict:
        """Résoudre un ensemble de contraintes."""
        self._stats["solved"] += 1

        constraints = constraint_set.get("constraints", [])
        variables = constraint_set.get("variables", {})
        strategy = constraint_set.get("strategy", "backtrack")

        satisfied = []
        violated = []
        assignments = dict(variables)

        for c in constraints:
            c_type = c.get("type", "logical")
            c_name = c.get("name", "unnamed")
            var = c.get("variable", "")
            op = c.get("op", "eq")
            value = c.get("value")

            var_val = assignments.get(var)

            if var_val is None:
                # Assign default value from constraint
                if op == "eq":
                    assignments[var] = value
                    satisfied.append({
                        "name": c_name, "type": c_type,
                        "status": "satisfied_by_assignment",
                    })
                else:
                    violated.append({
                        "name": c_name, "type": c_type,
                        "status": "unresolvable",
                        "reason": f"Variable '{var}' unassigned",
                    })
                continue

            met = self._check_op(var_val, op, value)
            if met:
                satisfied.append({
                    "name": c_name, "type": c_type, "status": "satisfied",
                })
            else:
                violated.append({
                    "name": c_name, "type": c_type, "status": "violated",
                    "reason": f"{var}={var_val} does not satisfy {op} {value}",
                })

        solvable = len(violated) == 0

        solution = {
            "id": f"sol_{uuid.uuid4().hex[:8]}",
            "solved": True,
            "solvable": solvable,
            "strategy": strategy,
            "assignments": assignments,
            "satisfied_count": len(satisfied),
            "violated_count": len(violated),
            "satisfied": satisfied,
            "violated": violated,
            "timestamp": time.time(),
        }
        self._solutions.append(solution)
        self._trim()

        return solution

    # ── check_constraints ───────────────────────────────────
    def check_constraints(self, constraint_set: dict) -> dict:
        """Vérifier si un ensemble de contraintes est satisfaisable."""
        self._stats["checked"] += 1

        constraints = constraint_set.get("constraints", [])
        variables = constraint_set.get("variables", {})

        violations = []
        for c in constraints:
            var = c.get("variable", "")
            op = c.get("op", "eq")
            value = c.get("value")
            var_val = variables.get(var)

            if var_val is not None and not self._check_op(var_val, op, value):
                violations.append({
                    "name": c.get("name", "unnamed"),
                    "variable": var,
                    "expected": f"{op} {value}",
                    "actual": var_val,
                })

        return {
            "id": f"chk_{uuid.uuid4().hex[:8]}",
            "checked": True,
            "consistent": len(violations) == 0,
            "total_constraints": len(constraints),
            "violations_count": len(violations),
            "violations": violations,
            "timestamp": time.time(),
        }

    # ── explain_constraints ─────────────────────────────────
    def explain_constraints(self) -> dict:
        """Expliquer le dernier ensemble de contraintes résolu."""
        self._stats["explanations"] += 1

        if not self._solutions:
            return {
                "explained": False,
                "error": "no_solutions",
                "timestamp": time.time(),
            }

        last = self._solutions[-1]
        reasons = [
            f"Stratégie : {last['strategy']}.",
            f"Contraintes satisfaites : {last['satisfied_count']}.",
            f"Contraintes violées : {last['violated_count']}.",
        ]
        if last["solvable"]:
            reasons.append("Le système est solvable — toutes les contraintes sont satisfaites.")
        else:
            reasons.append("Le système n'est pas solvable — des contraintes sont violées.")
            for v in last["violated"]:
                reasons.append(f"  Violation : {v['name']} — {v['reason']}.")

        return {
            "id": f"exp_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "solvable": last["solvable"],
            "reasons": reasons,
            "timestamp": time.time(),
        }

    # ── internals ───────────────────────────────────────────
    @staticmethod
    def _check_op(val, op: str, target) -> bool:
        if op == "eq":
            return val == target
        if op == "neq":
            return val != target
        if op == "gt":
            return val > target
        if op == "lt":
            return val < target
        if op == "gte":
            return val >= target
        if op == "lte":
            return val <= target
        if op == "in":
            return val in target
        return False

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "constraint_solver",
            "status": "ok",
            "total_solutions": len(self._solutions),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._constraints.clear()
        self._solutions.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ConstraintSolver restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._solutions) > 5000:
            self._solutions = self._solutions[-2500:]
