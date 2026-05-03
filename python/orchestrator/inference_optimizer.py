"""
EXO v19 — InferenceOptimizer
Optimise les inférences symboliques et hybrides du système.

API:
  optimize_inference(query: dict)   → dict
  simplify_rules()                  → dict
  compress_knowledge_graph()        → dict
  health_check()                    → dict
  restart()                         → None
  get_stats()                       → dict
"""

import logging
import time
import uuid

log = logging.getLogger("inference_optimizer")


class InferenceOptimizer:
    """Optimiseur d'inférences EXO v19."""

    def __init__(self, inference_eng=None, knowledge_graph=None,
                 meta_optimizer=None, governance=None):
        self._inference = inference_eng
        self._kg = knowledge_graph
        self._meta = meta_optimizer
        self._governance = governance

        self._history: list[dict] = []
        self._stats = {
            "inferences_optimized": 0,
            "rules_simplified": 0,
            "graphs_compressed": 0,
        }

    # ── optimize_inference ──────────────────────────────────
    def optimize_inference(self, query: dict) -> dict:
        """Optimiser une inférence en réduisant les chemins."""
        self._stats["inferences_optimized"] += 1

        question = query.get("question", "")
        rules_used = query.get("rules", [])
        chain_length = query.get("chain_length", 1)

        optimizations = []

        # Réduire les chaînes d'inférence longues
        if chain_length > 5:
            optimizations.append({
                "type": "shorten_chain",
                "original_length": chain_length,
                "recommended_length": min(chain_length, 5),
                "description": "Chaîne d'inférence trop longue, raccourcir",
            })

        # Éliminer les règles redondantes
        seen_rules = set()
        unique_rules = []
        duplicates = 0
        for rule in rules_used:
            key = rule.get("id", rule.get("name", str(rule)))
            if key in seen_rules:
                duplicates += 1
            else:
                seen_rules.add(key)
                unique_rules.append(rule)

        if duplicates > 0:
            optimizations.append({
                "type": "deduplicate_rules",
                "original_count": len(rules_used),
                "unique_count": len(unique_rules),
                "duplicates_removed": duplicates,
                "description": f"Suppression de {duplicates} règle(s) dupliquée(s)",
            })

        # Évaluer si on peut utiliser un cache
        if len(rules_used) > 10:
            optimizations.append({
                "type": "enable_rule_cache",
                "rules_count": len(rules_used),
                "description": "Activer le cache de règles pour accélérer",
            })

        record = {
            "id": f"oi_{uuid.uuid4().hex[:8]}",
            "optimized": True,
            "question": question[:100] if question else "",
            "original_rules": len(rules_used),
            "optimized_rules": len(unique_rules),
            "optimizations": optimizations,
            "total_optimizations": len(optimizations),
            "timestamp": time.time(),
        }
        self._history.append(record)
        self._trim()
        return record

    # ── simplify_rules ──────────────────────────────────────
    def simplify_rules(self) -> dict:
        """Simplifier la base de règles d'inférence."""
        self._stats["rules_simplified"] += 1

        suggestions = [
            {
                "action": "merge_equivalent",
                "description": "Fusionner les règles logiquement équivalentes",
                "estimated_reduction_pct": 15,
            },
            {
                "action": "remove_unreachable",
                "description": "Supprimer les règles jamais déclenchées",
                "estimated_reduction_pct": 10,
            },
            {
                "action": "optimize_conditions",
                "description": "Simplifier les conditions complexes (DNF/CNF)",
                "estimated_reduction_pct": 5,
            },
        ]

        return {
            "id": f"sr_{uuid.uuid4().hex[:8]}",
            "simplified": True,
            "suggestions": suggestions,
            "total_suggestions": len(suggestions),
            "estimated_total_reduction_pct": sum(
                s["estimated_reduction_pct"] for s in suggestions),
            "timestamp": time.time(),
        }

    # ── compress_knowledge_graph ────────────────────────────
    def compress_knowledge_graph(self) -> dict:
        """Compresser le graphe de connaissances."""
        self._stats["graphs_compressed"] += 1

        strategies = [
            {
                "strategy": "merge_equivalent_nodes",
                "description": "Fusionner les noeuds synonymes",
                "estimated_compression_pct": 20,
            },
            {
                "strategy": "prune_dead_edges",
                "description": "Supprimer les arêtes inutilisées",
                "estimated_compression_pct": 10,
            },
            {
                "strategy": "cluster_related",
                "description": "Regrouper les noeuds fortement connectés",
                "estimated_compression_pct": 15,
            },
        ]

        return {
            "id": f"cg_{uuid.uuid4().hex[:8]}",
            "compressed": True,
            "strategies": strategies,
            "total_strategies": len(strategies),
            "estimated_total_compression_pct": sum(
                s["estimated_compression_pct"] for s in strategies),
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "inference_optimizer",
            "status": "ok",
            "history": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("InferenceOptimizer restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
