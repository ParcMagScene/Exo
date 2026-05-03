"""
EXO v21 — DeductiveReasoner
Raisonnement déductif : modus ponens, modus tollens, syllogismes,
chaînes déductives, vérification logique.

API:
  deduce(query: dict)               → dict
  verify_deduction(chain: dict)     → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("deductive_reasoner")


class DeductiveReasoner:
    """Raisonneur déductif EXO v21."""

    def __init__(self, governance=None, rule_engine=None):
        self._governance = governance
        self._rule_engine = rule_engine

        self._deductions: list[dict] = []
        self._stats = {
            "deductions": 0,
            "verifications": 0,
        }

    # ── deduce ──────────────────────────────────────────────
    def deduce(self, query: dict) -> dict:
        """Appliquer des règles logiques strictes pour déduire."""
        self._stats["deductions"] += 1

        premises = query.get("premises", [])
        rules = query.get("rules", [])
        goal = query.get("goal", "")

        conclusions = []
        chain = []

        for rule in rules:
            rule_type = rule.get("type", "modus_ponens")
            antecedent = rule.get("antecedent", "")
            consequent = rule.get("consequent", "")

            if rule_type == "modus_ponens":
                # If P and P→Q then Q
                if antecedent in premises:
                    conclusions.append(consequent)
                    chain.append({
                        "step": len(chain) + 1,
                        "type": "modus_ponens",
                        "from": antecedent,
                        "derived": consequent,
                    })
                    premises.append(consequent)

            elif rule_type == "modus_tollens":
                # If ¬Q and P→Q then ¬P
                neg_consequent = f"not_{consequent}"
                if neg_consequent in premises:
                    neg_antecedent = f"not_{antecedent}"
                    conclusions.append(neg_antecedent)
                    chain.append({
                        "step": len(chain) + 1,
                        "type": "modus_tollens",
                        "from": neg_consequent,
                        "derived": neg_antecedent,
                    })
                    premises.append(neg_antecedent)

            elif rule_type == "syllogism":
                # If A→B and B→C then A→C
                middle = rule.get("middle", "")
                if antecedent in premises and middle in premises:
                    conclusions.append(consequent)
                    chain.append({
                        "step": len(chain) + 1,
                        "type": "syllogism",
                        "major": antecedent,
                        "middle": middle,
                        "derived": consequent,
                    })
                    premises.append(consequent)

        goal_reached = goal in conclusions if goal else len(conclusions) > 0

        deduction = {
            "id": f"ded_{uuid.uuid4().hex[:8]}",
            "deduced": True,
            "goal": goal,
            "goal_reached": goal_reached,
            "conclusions": conclusions,
            "chain": chain,
            "chain_length": len(chain),
            "timestamp": time.time(),
        }
        self._deductions.append(deduction)
        self._trim()

        return deduction

    # ── verify_deduction ────────────────────────────────────
    def verify_deduction(self, chain: dict) -> dict:
        """Vérifier la validité d'une chaîne déductive."""
        self._stats["verifications"] += 1

        steps = chain.get("steps", [])
        premises = set(chain.get("premises", []))

        valid = True
        issues = []

        for i, step in enumerate(steps):
            step_type = step.get("type", "")
            derived = step.get("derived", "")
            from_premise = step.get("from", "")

            if step_type == "modus_ponens":
                if from_premise not in premises:
                    valid = False
                    issues.append({
                        "step": i + 1,
                        "issue": f"Premise '{from_premise}' not established",
                    })
                else:
                    premises.add(derived)

            elif step_type == "modus_tollens":
                if from_premise not in premises:
                    valid = False
                    issues.append({
                        "step": i + 1,
                        "issue": f"Negated consequent '{from_premise}' "
                                 "not established",
                    })
                else:
                    premises.add(derived)

            elif step_type == "syllogism":
                major = step.get("major", "")
                middle = step.get("middle", "")
                if major not in premises or middle not in premises:
                    valid = False
                    issues.append({
                        "step": i + 1,
                        "issue": "Syllogism premises not established",
                    })
                else:
                    premises.add(derived)

        return {
            "id": f"ver_{uuid.uuid4().hex[:8]}",
            "verified": True,
            "valid": valid,
            "steps_checked": len(steps),
            "issues": issues,
            "timestamp": time.time(),
        }

    def list_deductions(self, limit: int = 50) -> list[dict]:
        return self._deductions[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "deductive_reasoner",
            "status": "ok",
            "total_deductions": len(self._deductions),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._deductions.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("DeductiveReasoner restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._deductions) > 5000:
            self._deductions = self._deductions[-2500:]
