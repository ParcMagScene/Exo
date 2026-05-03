"""
EXO v21 — InductiveReasoner
Raisonnement inductif : extraction de patterns, généralisation
symbolique, induction contextuelle et multi-agents.

API:
  induce(patterns: dict)        → dict
  generalize(examples: dict)    → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid
from collections import Counter

log = logging.getLogger("inductive_reasoner")


class InductiveReasoner:
    """Raisonneur inductif EXO v21."""

    def __init__(self, governance=None, knowledge_graph=None):
        self._governance = governance
        self._kg = knowledge_graph

        self._inductions: list[dict] = []
        self._stats = {
            "inductions": 0,
            "generalizations": 0,
        }

    # ── induce ──────────────────────────────────────────────
    def induce(self, patterns: dict) -> dict:
        """Extraire des patterns et induire des règles générales."""
        self._stats["inductions"] += 1

        observations = patterns.get("observations", [])
        context = patterns.get("context", "general")
        min_support = patterns.get("min_support", 2)

        # Extract recurring patterns
        property_counts: dict[str, Counter] = {}
        for obs in observations:
            for key, value in obs.items():
                if key.startswith("_"):
                    continue
                if key not in property_counts:
                    property_counts[key] = Counter()
                property_counts[key][str(value)] += 1

        induced_rules = []
        for prop, counts in property_counts.items():
            for value, count in counts.items():
                if count >= min_support:
                    confidence = count / len(observations) if observations else 0
                    induced_rules.append({
                        "property": prop,
                        "value": value,
                        "support": count,
                        "confidence": round(confidence, 3),
                        "type": "pattern",
                    })

        # Sort by confidence
        induced_rules.sort(key=lambda r: r["confidence"], reverse=True)

        induction = {
            "id": f"ind_{uuid.uuid4().hex[:8]}",
            "induced": True,
            "context": context,
            "observations_count": len(observations),
            "rules": induced_rules,
            "rules_count": len(induced_rules),
            "timestamp": time.time(),
        }
        self._inductions.append(induction)
        self._trim()

        return induction

    # ── generalize ──────────────────────────────────────────
    def generalize(self, examples: dict) -> dict:
        """Généraliser à partir d'exemples spécifiques."""
        self._stats["generalizations"] += 1

        items = examples.get("examples", [])
        target_property = examples.get("target", "")
        context = examples.get("context", "general")

        if not items:
            return {
                "id": f"gen_{uuid.uuid4().hex[:8]}",
                "generalized": False,
                "error": "no_examples",
                "timestamp": time.time(),
            }

        # Find common properties across examples
        common_keys = set(items[0].keys()) if items else set()
        for item in items[1:]:
            common_keys &= set(item.keys())

        # Find constant properties
        constants = {}
        for key in common_keys:
            values = [item.get(key) for item in items]
            if len(set(str(v) for v in values)) == 1:
                constants[key] = values[0]

        # Find varying properties
        varying = list(common_keys - set(constants.keys()))

        generalization = {
            "id": f"gen_{uuid.uuid4().hex[:8]}",
            "generalized": True,
            "context": context,
            "target_property": target_property,
            "examples_count": len(items),
            "common_properties": list(common_keys),
            "constants": constants,
            "varying_properties": varying,
            "rule": {
                "type": "generalization",
                "when": constants,
                "varies": varying,
                "confidence": round(
                    len(constants) / max(len(common_keys), 1), 3),
            },
            "timestamp": time.time(),
        }
        self._inductions.append(generalization)

        return generalization

    def list_inductions(self, limit: int = 50) -> list[dict]:
        return self._inductions[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "inductive_reasoner",
            "status": "ok",
            "total_inductions": len(self._inductions),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._inductions.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("InductiveReasoner restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._inductions) > 5000:
            self._inductions = self._inductions[-2500:]
