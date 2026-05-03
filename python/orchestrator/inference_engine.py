"""
EXO v15 — InferenceEngine (Inférence multi-modale)
Moteur d'inférence logique, causale, contextuelle et temporelle.

API:
  infer_logical(query)     → dict  (chaînage logique)
  infer_causal(chain)      → dict  (raisonnement causal)
  infer_temporal(seq)      → dict  (pattern temporel)
  infer_contextual(ctx)    → dict  (contexte actif)
  health_check()           → dict
  restart()                → None
  get_stats()              → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("inference_engine")


class InferenceEngine:
    """Moteur d'inférence multi-modale EXO v15."""

    def __init__(self, knowledge_graph=None, expert_system=None,
                 meta_memory=None):
        self._kg = knowledge_graph
        self._expert = expert_system
        self._memory = meta_memory
        self._inference_log: list[dict] = []
        self._stats = {
            "logical": 0,
            "causal": 0,
            "temporal": 0,
            "contextual": 0,
            "total": 0,
        }

    # ── infer_logical ───────────────────────────────────────
    def infer_logical(self, query: dict) -> dict:
        """Inférence logique : utilise le système expert + KG."""
        self._stats["logical"] += 1
        self._stats["total"] += 1
        trace_id = f"log_{uuid.uuid4().hex[:8]}"

        conclusions = []
        # Phase 1 : système expert
        if self._expert:
            result = self._expert.infer(query)
            conclusions.extend(result.get("fired", []))

        # Phase 2 : KG traversal
        if self._kg and "subject" in query:
            edges = self._kg.kg_query({"source": query["subject"]})
            for e in edges[:10]:
                conclusions.append({
                    "type": "kg_relation",
                    "relation": e["relation"],
                    "target": e["target"],
                })

        entry = {
            "id": trace_id,
            "type": "logical",
            "query": query,
            "conclusions": conclusions,
            "timestamp": time.time(),
        }
        self._inference_log.append(entry)
        return entry

    # ── infer_causal ────────────────────────────────────────
    def infer_causal(self, chain: list[dict]) -> dict:
        """Inférence causale : cause → effet le long d'une chaîne."""
        self._stats["causal"] += 1
        self._stats["total"] += 1
        trace_id = f"caus_{uuid.uuid4().hex[:8]}"

        links = []
        confidence = 1.0
        for i, step in enumerate(chain):
            cause = step.get("cause", "")
            effect = step.get("effect", "")
            prob = step.get("probability", 0.8)
            confidence *= prob
            link = {
                "step": i,
                "cause": cause,
                "effect": effect,
                "probability": prob,
                "cumulative_confidence": round(confidence, 4),
            }
            # KG validation
            if self._kg:
                rels = self._kg.kg_query({
                    "source": cause,
                    "relation": "causes",
                    "target": effect,
                })
                link["kg_validated"] = len(rels) > 0
            links.append(link)

        entry = {
            "id": trace_id,
            "type": "causal",
            "chain_length": len(chain),
            "links": links,
            "final_confidence": round(confidence, 4),
            "timestamp": time.time(),
        }
        self._inference_log.append(entry)
        return entry

    # ── infer_temporal ──────────────────────────────────────
    def infer_temporal(self, sequence: list[dict]) -> dict:
        """Inférence temporelle : détection de patterns dans une séquence."""
        self._stats["temporal"] += 1
        self._stats["total"] += 1
        trace_id = f"temp_{uuid.uuid4().hex[:8]}"

        patterns = []
        # Simple pattern detection: recurring events
        event_types: dict[str, int] = {}
        for evt in sequence:
            et = evt.get("event", "unknown")
            event_types[et] = event_types.get(et, 0) + 1

        for et, count in event_types.items():
            if count >= 2:
                patterns.append({
                    "pattern": "recurring",
                    "event": et,
                    "occurrences": count,
                    "confidence": min(0.5 + count * 0.1, 0.99),
                })

        # Sequence pattern: A always follows B
        if len(sequence) >= 2:
            for i in range(len(sequence) - 1):
                a = sequence[i].get("event", "")
                b = sequence[i + 1].get("event", "")
                if a and b and a != b:
                    patterns.append({
                        "pattern": "sequence",
                        "antecedent": a,
                        "consequent": b,
                        "confidence": 0.6,
                    })

        entry = {
            "id": trace_id,
            "type": "temporal",
            "sequence_length": len(sequence),
            "patterns": patterns,
            "timestamp": time.time(),
        }
        self._inference_log.append(entry)
        return entry

    # ── infer_contextual ────────────────────────────────────
    def infer_contextual(self, context: dict) -> dict:
        """Inférence contextuelle : raisonnement basé sur le contexte actif."""
        self._stats["contextual"] += 1
        self._stats["total"] += 1
        trace_id = f"ctx_{uuid.uuid4().hex[:8]}"

        inferences = []
        domain = context.get("domain", "general")
        conditions = context.get("conditions", {})

        # Expert system inference with context
        if self._expert:
            for key, val in conditions.items():
                self._expert.add_fact({
                    "key": key,
                    "value": val,
                    "domain": domain,
                    "confidence": 0.9,
                })
            result = self._expert.infer({"domain": domain})
            inferences.extend(result.get("fired", []))

        # KG neighborhood
        if self._kg and domain:
            neighbors = self._kg.kg_neighbors(domain)
            for n in neighbors[:5]:
                inferences.append({
                    "type": "contextual_neighbor",
                    "node": n["node"],
                    "relation": n["relation"],
                })

        entry = {
            "id": trace_id,
            "type": "contextual",
            "domain": domain,
            "inferences": inferences,
            "timestamp": time.time(),
        }
        self._inference_log.append(entry)
        return entry

    # ── get_log ─────────────────────────────────────────────
    def get_log(self, limit: int = 20) -> list[dict]:
        return self._inference_log[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "inference_engine",
            "status": "ok",
            "total_inferences": self._stats["total"],
        }

    def restart(self) -> None:
        self._inference_log.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("InferenceEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
