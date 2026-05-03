"""
EXO v15 — ExpertSystemEngine (Système expert)
Moteur de règles, de faits et d'inférences symboliques.

API:
  add_rule(rule)              → str  (rule_id)
  add_fact(fact)              → str  (fact_id)
  remove_rule(rule_id)        → bool
  remove_fact(fact_id)        → bool
  infer(query)                → dict
  explain_inference()         → dict
  get_rules(limit)            → list[dict]
  get_facts(limit)            → list[dict]
  health_check()              → dict
  restart()                   → None
  get_stats()                 → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("expert_system")


class ExpertSystemEngine:
    """Moteur expert symbolique EXO v15."""

    def __init__(self, meta_memory=None, governance=None):
        self._memory = meta_memory
        self._governance = governance
        self._rules: dict[str, dict] = {}   # id → rule
        self._facts: dict[str, dict] = {}   # id → fact
        self._inference_log: list[dict] = []
        self._stats = {
            "rules_added": 0,
            "facts_added": 0,
            "inferences_run": 0,
            "rules_fired": 0,
            "explanations": 0,
        }

    # ── add_rule ────────────────────────────────────────────
    def add_rule(self, rule: dict) -> str:
        """Add an inference rule.

        rule = {
            "condition": {"field": ..., "op": "=="|"!="|">"|"<"|"in"|"contains", "value": ...},
            "action": {"type": "assert"|"retract"|"set", ...},
            "priority": int (default 0),
            "description": str,
        }
        """
        rule_id = rule.get("id", f"rule_{uuid.uuid4().hex[:8]}")
        rule.setdefault("priority", 0)
        rule.setdefault("description", "")
        rule["id"] = rule_id
        rule["created"] = time.time()
        self._rules[rule_id] = rule
        self._stats["rules_added"] += 1
        log.info("Rule added: %s", rule_id)
        return rule_id

    # ── add_fact ────────────────────────────────────────────
    def add_fact(self, fact: dict) -> str:
        """Add a fact to the knowledge base.

        fact = {"key": ..., "value": ..., "domain": ..., "confidence": float}
        """
        fact_id = fact.get("id", f"fact_{uuid.uuid4().hex[:8]}")
        fact["id"] = fact_id
        fact.setdefault("confidence", 1.0)
        fact.setdefault("domain", "general")
        fact["created"] = time.time()
        self._facts[fact_id] = fact
        self._stats["facts_added"] += 1
        return fact_id

    # ── remove ──────────────────────────────────────────────
    def remove_rule(self, rule_id: str) -> bool:
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def remove_fact(self, fact_id: str) -> bool:
        if fact_id in self._facts:
            del self._facts[fact_id]
            return True
        return False

    # ── infer ───────────────────────────────────────────────
    def infer(self, query: dict) -> dict:
        """Run forward-chaining inference against current facts/rules.

        query = {"field": ..., "value": ...}  — matches facts or derived.
        """
        self._stats["inferences_run"] += 1
        fired: list[dict] = []
        derived_facts: list[dict] = []

        # Sort rules by priority (high first)
        sorted_rules = sorted(self._rules.values(),
                              key=lambda r: r.get("priority", 0),
                              reverse=True)

        for rule in sorted_rules:
            match = self._evaluate_condition(rule.get("condition", {}))
            if match:
                action = rule.get("action", {})
                derived = self._fire_rule(rule, action)
                fired.append({
                    "rule_id": rule["id"],
                    "description": rule.get("description", ""),
                    "action": action,
                })
                if derived:
                    derived_facts.append(derived)
                self._stats["rules_fired"] += 1

        # Match query against facts + derived
        matches = self._match_query(query)

        result = {
            "query": query,
            "matches": matches,
            "rules_fired": len(fired),
            "fired_rules": fired,
            "derived_facts": derived_facts,
            "total_facts": len(self._facts),
            "total_rules": len(self._rules),
            "timestamp": time.time(),
        }
        self._inference_log.append(result)
        self._trim_log()
        return result

    # ── explain_inference ───────────────────────────────────
    def explain_inference(self) -> dict:
        """Explain the last inference run."""
        self._stats["explanations"] += 1
        if not self._inference_log:
            return {"explanation": "Aucune inférence exécutée.",
                    "has_log": False}

        last = self._inference_log[-1]
        lines = [
            f"Dernière inférence:",
            f"  Requête: {last.get('query', {})}",
            f"  Correspondances: {len(last.get('matches', []))}",
            f"  Règles déclenchées: {last.get('rules_fired', 0)}",
        ]
        for fr in last.get("fired_rules", [])[:10]:
            lines.append(
                f"  → Règle {fr['rule_id']}: {fr.get('description', '')}")

        return {
            "explanation": "\n".join(lines),
            "has_log": True,
            "last_query": last.get("query", {}),
            "matches_count": len(last.get("matches", [])),
            "timestamp": time.time(),
        }

    # ── get_rules / get_facts ───────────────────────────────
    def get_rules(self, limit: int = 50) -> list[dict]:
        return list(self._rules.values())[-limit:]

    def get_facts(self, limit: int = 50) -> list[dict]:
        return list(self._facts.values())[-limit:]

    # ── internal ────────────────────────────────────────────
    def _evaluate_condition(self, condition: dict) -> bool:
        """Evaluate a rule condition against current facts."""
        if not condition:
            return True  # empty condition always matches

        field = condition.get("field", "")
        op = condition.get("op", "==")
        value = condition.get("value")

        for fact in self._facts.values():
            fact_val = fact.get(field, fact.get("key", ""))
            if self._compare(fact_val, op, value):
                return True
        return False

    @staticmethod
    def _compare(fact_val: Any, op: str, value: Any) -> bool:
        try:
            if op == "==":
                return fact_val == value
            if op == "!=":
                return fact_val != value
            if op == ">":
                return fact_val > value
            if op == "<":
                return fact_val < value
            if op == "in":
                return fact_val in value
            if op == "contains":
                return value in fact_val
        except (TypeError, ValueError):
            return False
        return False

    def _fire_rule(self, rule: dict, action: dict) -> dict | None:
        """Execute a rule action (e.g. assert new fact)."""
        act_type = action.get("type", "")
        if act_type == "assert":
            new_fact = {
                "key": action.get("key", ""),
                "value": action.get("value"),
                "domain": action.get("domain", "derived"),
                "confidence": action.get("confidence", 0.8),
                "derived_from": rule["id"],
            }
            self.add_fact(new_fact)
            return new_fact
        if act_type == "retract":
            key = action.get("key", "")
            to_remove = [fid for fid, f in self._facts.items()
                         if f.get("key") == key]
            for fid in to_remove:
                self.remove_fact(fid)
        return None

    def _match_query(self, query: dict) -> list[dict]:
        """Find facts matching a query."""
        if not query:
            return list(self._facts.values())[:20]

        matches = []
        for fact in self._facts.values():
            match = True
            for k, v in query.items():
                if k in ("field", "op", "value"):
                    continue
                if fact.get(k) != v:
                    match = False
                    break
            if match and query.get("field"):
                field = query["field"]
                val = query.get("value")
                if fact.get(field) != val and fact.get("key") != val:
                    match = False
            if match:
                matches.append(fact)
        return matches

    def _trim_log(self) -> None:
        if len(self._inference_log) > 500:
            self._inference_log = self._inference_log[-300:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "expert_system",
            "status": "ok",
            "rules": len(self._rules),
            "facts": len(self._facts),
        }

    def restart(self) -> None:
        self._rules.clear()
        self._facts.clear()
        self._inference_log.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ExpertSystemEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
