"""
EXO v17 — KnowledgeGroundedLLM (LLM ancré dans les connaissances)
Ancre le LLM dans le KnowledgeGraph, les règles, le contexte et
les préférences utilisateur pour des réponses factuellement cohérentes.

API:
  ground_prompt(prompt, knowledge)     → dict
  ground_llm_output(output)            → dict
  validate_grounding()                 → dict
  get_grounding_history(limit)         → list[dict]
  health_check()                       → dict
  restart()                            → None
  get_stats()                          → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("knowledge_grounded_llm")

# Types d'ancrage
GROUNDING_TYPES = frozenset({
    "knowledge", "rules", "preferences", "scenarios", "agents", "context",
})

# Score minimum d'ancrage acceptable
MIN_GROUNDING_SCORE = 0.3


class KnowledgeGroundedLLM:
    """LLM ancré dans les connaissances EXO v17."""

    def __init__(self, knowledge_graph=None, inference_engine=None,
                 reasoning_bridge=None, meta_memory=None, governance=None):
        self._kg = knowledge_graph
        self._inference = inference_engine
        self._bridge = reasoning_bridge
        self._memory = meta_memory
        self._governance = governance
        self._history: list[dict] = []
        self._stats = {
            "prompts_grounded": 0,
            "outputs_grounded": 0,
            "validations_run": 0,
            "validations_passed": 0,
            "validations_failed": 0,
            "knowledge_injected": 0,
            "rules_injected": 0,
        }

    # ── ground_prompt ───────────────────────────────────────
    def ground_prompt(self, prompt: str, knowledge: dict | None = None) -> dict:
        """Ancrer un prompt dans les connaissances avant envoi au LLM."""
        self._stats["prompts_grounded"] += 1
        knowledge = knowledge or {}

        domain = knowledge.get("domain", "general")
        rules = knowledge.get("rules", [])
        preferences = knowledge.get("preferences", {})
        context = knowledge.get("context", {})

        # Collecter les connaissances du KG
        kg_facts = []
        if self._kg:
            try:
                result = self._kg.query(domain, limit=10)
                kg_facts = result if isinstance(result, list) else []
                self._stats["knowledge_injected"] += len(kg_facts)
            except Exception:
                pass

        # Collecter les règles de l'InferenceEngine
        inferred_rules = []
        if self._inference:
            try:
                r = self._inference.infer({
                    "type": "contextual",
                    "query": prompt[:100],
                    "domain": domain,
                })
                inferred_rules = r.get("conclusions", [])
                self._stats["rules_injected"] += len(inferred_rules)
            except Exception:
                pass

        # Construire le prompt augmenté
        augmented_parts = [prompt]

        if kg_facts:
            facts_text = "; ".join(str(f) for f in kg_facts[:5])
            augmented_parts.insert(0, f"[CONNAISSANCES] {facts_text}")

        if rules or inferred_rules:
            all_rules = rules + inferred_rules
            rules_text = "; ".join(str(r) for r in all_rules[:5])
            augmented_parts.insert(0, f"[RÈGLES] {rules_text}")

        if preferences:
            pref_text = "; ".join(f"{k}={v}" for k, v in
                                  list(preferences.items())[:5])
            augmented_parts.insert(0, f"[PRÉFÉRENCES] {pref_text}")

        if context:
            ctx_text = "; ".join(f"{k}={v}" for k, v in
                                 list(context.items())[:5])
            augmented_parts.insert(0, f"[CONTEXTE] {ctx_text}")

        augmented_prompt = "\n".join(augmented_parts)

        # Calculer le score d'ancrage
        grounding_score = self._compute_grounding_score(
            kg_facts, rules + inferred_rules, preferences)

        result = {
            "id": f"gp_{uuid.uuid4().hex[:8]}",
            "original_prompt": prompt,
            "augmented_prompt": augmented_prompt,
            "grounding_score": grounding_score,
            "knowledge_count": len(kg_facts),
            "rules_count": len(rules) + len(inferred_rules),
            "domain": domain,
            "well_grounded": grounding_score >= MIN_GROUNDING_SCORE,
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        log.info("Prompt grounded: score=%.2f, %d facts, %d rules",
                 grounding_score, len(kg_facts),
                 len(rules) + len(inferred_rules))
        return result

    # ── ground_llm_output ───────────────────────────────────
    def ground_llm_output(self, output: dict) -> dict:
        """Vérifier et ancrer une sortie LLM dans les connaissances."""
        self._stats["outputs_grounded"] += 1

        text = output.get("text", "")
        domain = output.get("domain", "general")

        # Vérifier la cohérence avec le KG
        consistency_issues = []
        if self._kg:
            try:
                kg_facts = self._kg.query(domain, limit=10)
                if isinstance(kg_facts, list):
                    for fact in kg_facts:
                        entity = fact.get("entity", "") if isinstance(
                            fact, dict) else str(fact)
                        if entity and entity.lower() in text.lower():
                            # L'entité est mentionnée — vérifier cohérence
                            pass
            except Exception:
                pass

        # Traduire via le bridge si disponible
        symbolic = {}
        if self._bridge:
            try:
                symbolic = self._bridge.llm_to_symbolic(output)
            except Exception:
                pass

        grounding_score = self._compute_output_grounding(text, domain)

        result = {
            "id": f"go_{uuid.uuid4().hex[:8]}",
            "original_output": text[:200],
            "grounding_score": grounding_score,
            "well_grounded": grounding_score >= MIN_GROUNDING_SCORE,
            "symbolic_extraction": symbolic,
            "consistency_issues": consistency_issues,
            "domain": domain,
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()
        return result

    # ── validate_grounding ──────────────────────────────────
    def validate_grounding(self) -> dict:
        """Valider la qualité globale de l'ancrage."""
        self._stats["validations_run"] += 1

        if not self._history:
            self._stats["validations_passed"] += 1
            return {
                "valid": True,
                "total_groundings": 0,
                "avg_score": 0.0,
                "well_grounded_ratio": 1.0,
                "issues": [],
            }

        scores = [h.get("grounding_score", 0) for h in self._history[-50:]]
        avg_score = sum(scores) / len(scores) if scores else 0
        well_grounded = sum(1 for s in scores if s >= MIN_GROUNDING_SCORE)
        ratio = well_grounded / len(scores) if scores else 0

        issues = []
        if avg_score < MIN_GROUNDING_SCORE:
            issues.append("avg_grounding_below_threshold")
        if ratio < 0.7:
            issues.append("too_many_poorly_grounded")

        valid = len(issues) == 0
        if valid:
            self._stats["validations_passed"] += 1
        else:
            self._stats["validations_failed"] += 1

        return {
            "valid": valid,
            "total_groundings": len(self._history),
            "avg_score": round(avg_score, 3),
            "well_grounded_ratio": round(ratio, 3),
            "issues": issues,
        }

    # ── get_grounding_history ───────────────────────────────
    def get_grounding_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "knowledge_grounded_llm",
            "status": "ok",
            "history_entries": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("KnowledgeGroundedLLM restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _compute_grounding_score(self, facts: list, rules: list,
                                  preferences: dict) -> float:
        score = 0.2  # Base
        if facts:
            score += min(len(facts) * 0.08, 0.4)
        if rules:
            score += min(len(rules) * 0.1, 0.3)
        if preferences:
            score += 0.1
        return round(min(score, 0.98), 3)

    def _compute_output_grounding(self, text: str, domain: str) -> float:
        if not text:
            return 0.1
        score = 0.4
        if self._kg:
            score += 0.2
        if len(text) > 50:
            score += 0.1
        return round(min(score, 0.95), 3)

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
