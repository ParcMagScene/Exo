"""
EXO v17 — HybridInferenceEngine (Moteur d'inférence hybride)
Combine inférence logique/symbolique et raisonnement neuronal
pour produire des inférences hybrides cohérentes.

API:
  infer_hybrid(query)                     → dict
  infer_symbolic(query)                   → dict
  infer_neural(query)                     → dict
  combine_inferences(symbolic, neural)    → dict
  get_inference_log(limit)                → list[dict]
  health_check()                          → dict
  restart()                               → None
  get_stats()                             → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("hybrid_inference")

# Types d'inférence
INFERENCE_TYPES = frozenset({
    "logical", "semantic", "contextual", "causal", "hybrid",
})

# Poids par défaut pour la fusion
DEFAULT_WEIGHTS = {
    "symbolic": 0.55,
    "neural": 0.45,
}


class HybridInferenceEngine:
    """Moteur d'inférence hybride EXO v17."""

    def __init__(self, reasoning_bridge=None, knowledge_graph=None,
                 inference_engine=None, meta_memory=None, governance=None):
        self._bridge = reasoning_bridge
        self._kg = knowledge_graph
        self._inference = inference_engine
        self._memory = meta_memory
        self._governance = governance
        self._log: list[dict] = []
        self._weights = dict(DEFAULT_WEIGHTS)
        self._stats = {
            "hybrid_inferences": 0,
            "symbolic_inferences": 0,
            "neural_inferences": 0,
            "combinations": 0,
            "symbolic_preferred": 0,
            "neural_preferred": 0,
            "conflicts_resolved": 0,
        }

    # ── infer_hybrid ────────────────────────────────────────
    def infer_hybrid(self, query: dict) -> dict:
        """Inférence hybride combinant symbolique + neuronal."""
        self._stats["hybrid_inferences"] += 1

        question = query.get("question", "")
        domain = query.get("domain", "general")
        context = query.get("context", {})

        # Phase symbolique
        sym_result = self.infer_symbolic({
            "question": question, "domain": domain, "context": context,
        })

        # Phase neuronale
        neu_result = self.infer_neural({
            "question": question, "domain": domain, "context": context,
        })

        # Combiner
        combined = self.combine_inferences(sym_result, neu_result)

        entry = {
            "id": f"hyb_{uuid.uuid4().hex[:8]}",
            "type": "hybrid",
            "question": question,
            "domain": domain,
            "symbolic_result": sym_result,
            "neural_result": neu_result,
            "combined": combined,
            "timestamp": time.time(),
        }
        self._log.append(entry)
        self._trim()

        log.info("Hybrid inference: domain=%s, confidence=%.2f",
                 domain, combined.get("confidence", 0))
        return entry

    # ── infer_symbolic ──────────────────────────────────────
    def infer_symbolic(self, query: dict) -> dict:
        """Inférence purement symbolique (règles, graphe, logique)."""
        self._stats["symbolic_inferences"] += 1

        question = query.get("question", "")
        domain = query.get("domain", "general")

        conclusions = []
        confidence = 0.5

        # Interroger le KG
        kg_facts = []
        if self._kg:
            try:
                kg_facts = self._kg.query(domain, limit=10)
                if kg_facts:
                    confidence += 0.1
            except Exception:
                pass

        # Interroger l'InferenceEngine v15
        inference_results = []
        if self._inference:
            try:
                r = self._inference.infer({
                    "type": "logical",
                    "query": question,
                    "domain": domain,
                })
                inference_results = r.get("conclusions", [])
                if inference_results:
                    confidence += 0.15
            except Exception:
                pass

        conclusions = inference_results or [{
            "statement": f"Aucune conclusion symbolique pour: {question[:80]}",
            "source": "default",
        }]

        return {
            "type": "symbolic",
            "conclusions": conclusions,
            "kg_facts": kg_facts if isinstance(kg_facts, list) else [],
            "confidence": min(round(confidence, 3), 0.95),
            "domain": domain,
        }

    # ── infer_neural ────────────────────────────────────────
    def infer_neural(self, query: dict) -> dict:
        """Inférence neuronale (LLM, embeddings, sémantique)."""
        self._stats["neural_inferences"] += 1

        question = query.get("question", "")
        domain = query.get("domain", "general")
        context = query.get("context", {})

        # Simuler l'inférence neuronale (le LLM réel est externe)
        # Le bridge peut fournir des instructions structurées
        neural_context = {}
        if self._bridge:
            try:
                sym_rule = {"type": "fact", "content": question, "domain": domain}
                neural_context = self._bridge.symbolic_to_llm(sym_rule)
            except Exception:
                pass

        confidence = 0.6
        interpretation = {
            "statement": f"Interprétation neuronale de: {question[:80]}",
            "domain": domain,
            "source": "neural",
        }

        if neural_context.get("prompt"):
            confidence += 0.1
            interpretation["grounded"] = True

        return {
            "type": "neural",
            "interpretation": interpretation,
            "neural_context": neural_context,
            "confidence": min(round(confidence, 3), 0.95),
            "domain": domain,
        }

    # ── combine_inferences ──────────────────────────────────
    def combine_inferences(self, symbolic: dict, neural: dict) -> dict:
        """Combiner les résultats symbolique et neuronal."""
        self._stats["combinations"] += 1

        sym_conf = symbolic.get("confidence", 0.5)
        neu_conf = neural.get("confidence", 0.5)

        w_sym = self._weights["symbolic"]
        w_neu = self._weights["neural"]

        merged_confidence = round(sym_conf * w_sym + neu_conf * w_neu, 3)

        # Déterminer quelle source domine
        if sym_conf > neu_conf:
            self._stats["symbolic_preferred"] += 1
            preferred = "symbolic"
        else:
            self._stats["neural_preferred"] += 1
            preferred = "neural"

        # Fusionner les conclusions
        sym_conclusions = symbolic.get("conclusions", [])
        neu_interpretation = neural.get("interpretation", {})

        merged_conclusions = list(sym_conclusions)
        if neu_interpretation:
            merged_conclusions.append(neu_interpretation)

        # Détection de conflit
        conflict = self._detect_inference_conflict(symbolic, neural)
        if conflict:
            self._stats["conflicts_resolved"] += 1
            merged_confidence *= 0.85

        return {
            "conclusions": merged_conclusions,
            "confidence": merged_confidence,
            "preferred_source": preferred,
            "symbolic_confidence": sym_conf,
            "neural_confidence": neu_conf,
            "conflict_detected": conflict,
            "weights": dict(self._weights),
        }

    # ── get_inference_log ───────────────────────────────────
    def get_inference_log(self, limit: int = 50) -> list[dict]:
        return self._log[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "hybrid_inference",
            "status": "ok",
            "log_entries": len(self._log),
            "weights": dict(self._weights),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._log.clear()
        self._weights = dict(DEFAULT_WEIGHTS)
        for k in self._stats:
            self._stats[k] = 0
        log.info("HybridInferenceEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _detect_inference_conflict(self, sym: dict, neu: dict) -> bool:
        """Détecter si les inférences symbolique et neuronale se contredisent."""
        sym_conclusions = sym.get("conclusions", [])
        neu_interp = neu.get("interpretation", {})
        if not sym_conclusions or not neu_interp:
            return False
        # Conflit si confiance très divergente et sources différentes
        diff = abs(sym.get("confidence", 0.5) - neu.get("confidence", 0.5))
        return diff > 0.3

    def _trim(self) -> None:
        if len(self._log) > 5000:
            self._log = self._log[-5000:]
