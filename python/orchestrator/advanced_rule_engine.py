"""
EXO v21 — AdvancedRuleEngine
Moteur de règles avancé : conditionnelles complexes, hiérarchiques,
contextuelles, temporelles, probabilistes, multi-agents.

API:
  add_rule(rule: dict)                → dict
  evaluate_rules(context: dict)       → dict
  explain_rule(rule: dict)            → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("advanced_rule_engine")


class AdvancedRuleEngine:
    """Moteur de règles avancé EXO v21."""

    def __init__(self, governance=None, knowledge_graph=None):
        self._governance = governance
        self._kg = knowledge_graph

        self._rules: dict[str, dict] = {}
        self._evaluations: list[dict] = []
        self._stats = {
            "rules_added": 0,
            "evaluations": 0,
            "explanations": 0,
        }

    # ── add_rule ────────────────────────────────────────────
    def add_rule(self, rule: dict) -> dict:
        """Ajouter une règle avancée au moteur."""
        self._stats["rules_added"] += 1

        name = rule.get("name", "unnamed")
        rule_type = rule.get("type", "conditional")
        conditions = rule.get("conditions", [])
        actions = rule.get("actions", [])
        priority = rule.get("priority", 5)
        context_scope = rule.get("context_scope", "global")
        probability = rule.get("probability", 1.0)
        temporal = rule.get("temporal", None)

        rid = f"rule_{uuid.uuid4().hex[:8]}"
        entry = {
            "id": rid,
            "name": name,
            "type": rule_type,
            "conditions": conditions,
            "actions": actions,
            "priority": priority,
            "context_scope": context_scope,
            "probability": probability,
            "temporal": temporal,
            "state": "active",
            "created_at": time.time(),
            "fired_count": 0,
        }
        self._rules[rid] = entry
        self._trim()

        return {
            "id": rid,
            "added": True,
            "name": name,
            "type": rule_type,
            "priority": priority,
            "timestamp": time.time(),
        }

    # ── evaluate_rules ──────────────────────────────────────
    def evaluate_rules(self, context: dict) -> dict:
        """Évaluer toutes les règles actives contre un contexte."""
        self._stats["evaluations"] += 1

        scope = context.get("scope", "global")
        facts = context.get("facts", {})
        now = time.time()

        fired = []
        skipped = []

        # Sort by priority (higher first)
        sorted_rules = sorted(
            self._rules.values(),
            key=lambda r: r["priority"],
            reverse=True,
        )

        for rule in sorted_rules:
            if rule["state"] != "active":
                continue
            if rule["context_scope"] != "global" and rule["context_scope"] != scope:
                skipped.append({"id": rule["id"], "reason": "scope_mismatch"})
                continue

            # Check temporal validity
            if rule["temporal"]:
                valid_from = rule["temporal"].get("valid_from", 0)
                valid_until = rule["temporal"].get("valid_until", float("inf"))
                if not (valid_from <= now <= valid_until):
                    skipped.append({"id": rule["id"], "reason": "temporal_expired"})
                    continue

            # Evaluate conditions against facts
            matched = self._match_conditions(rule["conditions"], facts)
            if matched:
                rule["fired_count"] += 1
                fired.append({
                    "id": rule["id"],
                    "name": rule["name"],
                    "type": rule["type"],
                    "actions": rule["actions"],
                    "probability": rule["probability"],
                    "priority": rule["priority"],
                })

        evaluation = {
            "id": f"eval_{uuid.uuid4().hex[:8]}",
            "evaluated": True,
            "scope": scope,
            "total_rules": len(self._rules),
            "fired_count": len(fired),
            "skipped_count": len(skipped),
            "fired": fired,
            "skipped": skipped,
            "timestamp": time.time(),
        }
        self._evaluations.append(evaluation)

        return evaluation

    # ── explain_rule ────────────────────────────────────────
    def explain_rule(self, rule: dict) -> dict:
        """Expliquer une règle et sa logique."""
        self._stats["explanations"] += 1

        rule_id = rule.get("rule_id", "")
        entry = self._rules.get(rule_id)

        if not entry:
            return {
                "explained": False,
                "error": "rule_not_found",
                "rule_id": rule_id,
                "timestamp": time.time(),
            }

        reasons = [
            f"Règle '{entry['name']}' de type '{entry['type']}'.",
            f"Priorité : {entry['priority']}.",
            f"Portée : {entry['context_scope']}.",
            f"Probabilité : {entry['probability']}.",
            f"Déclenchée {entry['fired_count']} fois.",
        ]
        if entry["conditions"]:
            reasons.append(
                f"Conditions : {len(entry['conditions'])} clause(s).")
        if entry["temporal"]:
            reasons.append("Contrainte temporelle active.")

        return {
            "id": f"exp_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "rule_id": rule_id,
            "name": entry["name"],
            "reasons": reasons,
            "timestamp": time.time(),
        }

    def list_rules(self) -> list[dict]:
        return [
            {"id": rid, "name": r["name"], "type": r["type"],
             "priority": r["priority"], "state": r["state"],
             "fired_count": r["fired_count"]}
            for rid, r in self._rules.items()
        ]

    # ── internals ───────────────────────────────────────────
    def _match_conditions(self, conditions: list, facts: dict) -> bool:
        """Évaluer les conditions contre les faits."""
        if not conditions:
            return True
        for cond in conditions:
            key = cond.get("key", "")
            op = cond.get("op", "eq")
            value = cond.get("value")
            fact_val = facts.get(key)
            if fact_val is None:
                return False
            if op == "eq" and fact_val != value:
                return False
            if op == "neq" and fact_val == value:
                return False
            if op == "gt" and not (fact_val > value):
                return False
            if op == "lt" and not (fact_val < value):
                return False
            if op == "gte" and not (fact_val >= value):
                return False
            if op == "lte" and not (fact_val <= value):
                return False
            if op == "in" and fact_val not in value:
                return False
            if op == "contains" and value not in fact_val:
                return False
        return True

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "advanced_rule_engine",
            "status": "ok",
            "total_rules": len(self._rules),
            "active_rules": sum(1 for r in self._rules.values()
                                if r["state"] == "active"),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._rules.clear()
        self._evaluations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("AdvancedRuleEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._evaluations) > 5000:
            self._evaluations = self._evaluations[-2500:]
