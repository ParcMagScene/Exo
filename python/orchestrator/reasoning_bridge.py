"""
EXO v17 — ReasoningBridge (Pont neuro-symbolique)
Traduit entre raisonnement symbolique (règles, graphes, inférences)
et raisonnement neuronal (LLM, embeddings, sémantique).

API:
  llm_to_symbolic(llm_output)          → dict
  symbolic_to_llm(rule)                → dict
  merge_reasoning(symbolic, neural)    → dict
  get_translations(limit)              → list[dict]
  health_check()                       → dict
  restart()                            → None
  get_stats()                          → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("reasoning_bridge")

# Types de traduction
TRANSLATION_TYPES = frozenset({
    "llm_to_facts", "llm_to_rules", "llm_to_graph",
    "rule_to_prompt", "fact_to_prompt", "graph_to_prompt",
})

# Patterns d'extraction symbolique
FACT_PATTERNS = {
    "entity": r"(?:est|is)\s+(?:un|une|a|an)\s+",
    "relation": r"(?:possède|has|contient|contains)\s+",
    "property": r"(?:vaut|equals|mesure|measures)\s+",
}


class ReasoningBridge:
    """Pont neuro-symbolique EXO v17."""

    def __init__(self, knowledge_graph=None, inference_engine=None,
                 meta_memory=None, governance=None):
        self._kg = knowledge_graph
        self._inference = inference_engine
        self._memory = meta_memory
        self._governance = governance
        self._translations: list[dict] = []
        self._stats = {
            "llm_to_symbolic": 0,
            "symbolic_to_llm": 0,
            "merges": 0,
            "facts_extracted": 0,
            "rules_translated": 0,
            "merge_conflicts": 0,
        }

    # ── llm_to_symbolic ─────────────────────────────────────
    def llm_to_symbolic(self, llm_output: dict) -> dict:
        """Traduire une sortie LLM en faits symboliques."""
        self._stats["llm_to_symbolic"] += 1

        text = llm_output.get("text", "")
        context = llm_output.get("context", {})
        domain = llm_output.get("domain", "general")

        # Extraire les faits depuis le texte LLM
        facts = self._extract_facts(text, domain)
        rules = self._extract_rules(text)
        relations = self._extract_relations(text)

        self._stats["facts_extracted"] += len(facts)

        result = {
            "id": f"t2s_{uuid.uuid4().hex[:8]}",
            "direction": "llm_to_symbolic",
            "facts": facts,
            "rules": rules,
            "relations": relations,
            "domain": domain,
            "confidence": self._compute_confidence(facts, rules),
            "timestamp": time.time(),
        }

        self._translations.append(result)
        self._trim()

        # Inject into KG if available
        if self._kg and facts:
            for fact in facts:
                try:
                    self._kg.add_node(fact.get("entity", "unknown"),
                                      fact.get("type", "fact"), fact)
                except Exception:
                    pass

        if self._memory:
            try:
                self._memory.store("reasoning_bridge",
                                   f"llm_to_symbolic:{domain}",
                                   {"facts_count": len(facts)})
            except Exception:
                pass

        log.info("LLM→Symbolic: %d facts, %d rules, %d relations",
                 len(facts), len(rules), len(relations))
        return result

    # ── symbolic_to_llm ─────────────────────────────────────
    def symbolic_to_llm(self, rule: dict) -> dict:
        """Traduire une règle/fait symbolique en instruction LLM."""
        self._stats["symbolic_to_llm"] += 1
        self._stats["rules_translated"] += 1

        rule_type = rule.get("type", "fact")
        content = rule.get("content", "")
        conditions = rule.get("conditions", [])
        actions = rule.get("actions", [])
        domain = rule.get("domain", "general")

        # Construire le prompt structuré
        prompt_parts = []

        if rule_type == "rule":
            prompt_parts.append(f"[RÈGLE] Domaine: {domain}")
            if conditions:
                prompt_parts.append("Conditions: " + "; ".join(
                    str(c) for c in conditions))
            if actions:
                prompt_parts.append("Actions: " + "; ".join(
                    str(a) for a in actions))
        elif rule_type == "fact":
            prompt_parts.append(f"[FAIT] {content}")
        elif rule_type == "constraint":
            prompt_parts.append(f"[CONTRAINTE] {content}")
            if conditions:
                prompt_parts.append("Limites: " + "; ".join(
                    str(c) for c in conditions))
        else:
            prompt_parts.append(f"[{rule_type.upper()}] {content}")

        # Enrichir avec le KG si disponible
        kg_context = []
        if self._kg:
            try:
                related = self._kg.query(domain, limit=5)
                kg_context = [str(r) for r in related] if related else []
            except Exception:
                pass

        prompt = "\n".join(prompt_parts)
        if kg_context:
            prompt += "\n[CONTEXTE] " + "; ".join(kg_context[:3])

        result = {
            "id": f"s2l_{uuid.uuid4().hex[:8]}",
            "direction": "symbolic_to_llm",
            "prompt": prompt,
            "structured_prompt": {
                "system_context": f"Domaine: {domain}",
                "rules": conditions,
                "actions": actions,
                "constraints": [content] if rule_type == "constraint" else [],
            },
            "domain": domain,
            "rule_type": rule_type,
            "timestamp": time.time(),
        }

        self._translations.append(result)
        self._trim()

        log.info("Symbolic→LLM: type=%s, domain=%s", rule_type, domain)
        return result

    # ── merge_reasoning ─────────────────────────────────────
    def merge_reasoning(self, symbolic: dict, neural: dict) -> dict:
        """Fusionner résultats symbolique + neuronal avec détection de conflit."""
        self._stats["merges"] += 1

        sym_confidence = symbolic.get("confidence", 0.5)
        neu_confidence = neural.get("confidence", 0.5)
        sym_facts = symbolic.get("facts", [])
        neu_facts = neural.get("facts", [])

        # Détecter les conflits
        conflicts = self._detect_conflicts(sym_facts, neu_facts)
        if conflicts:
            self._stats["merge_conflicts"] += len(conflicts)

        # Résoudre par confiance pondérée
        merged_facts = list(sym_facts)
        for nf in neu_facts:
            if not any(self._facts_conflict(nf, sf) for sf in sym_facts):
                merged_facts.append(nf)

        # Score de confiance fusionné
        merged_confidence = (sym_confidence * 0.6 + neu_confidence * 0.4)
        if conflicts:
            merged_confidence *= 0.8  # Pénalité conflits

        # Gouvernance
        governed = True
        if self._governance:
            try:
                governed = self._governance.check_permission(
                    "merge_reasoning", {"conflicts": len(conflicts)})
            except Exception:
                pass

        result = {
            "id": f"mrg_{uuid.uuid4().hex[:8]}",
            "merged_facts": merged_facts,
            "symbolic_confidence": sym_confidence,
            "neural_confidence": neu_confidence,
            "merged_confidence": merged_confidence,
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
            "resolution": "weighted_confidence",
            "governed": governed,
            "timestamp": time.time(),
        }

        self._translations.append(result)
        self._trim()

        log.info("Merge: %d sym + %d neu → %d merged, %d conflicts",
                 len(sym_facts), len(neu_facts), len(merged_facts),
                 len(conflicts))
        return result

    # ── get_translations ────────────────────────────────────
    def get_translations(self, limit: int = 50) -> list[dict]:
        return self._translations[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "reasoning_bridge",
            "status": "ok",
            "translations_count": len(self._translations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._translations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ReasoningBridge restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _extract_facts(self, text: str, domain: str) -> list[dict]:
        """Extraire des faits structurés depuis un texte LLM."""
        facts = []
        if not text:
            return facts
        sentences = [s.strip() for s in text.replace("\n", ".").split(".")
                     if s.strip()]
        for sent in sentences[:20]:  # Limiter
            words = sent.split()
            if len(words) >= 3:
                facts.append({
                    "entity": words[0],
                    "predicate": words[1] if len(words) > 1 else "is",
                    "value": " ".join(words[2:]),
                    "domain": domain,
                    "source": "llm",
                })
        return facts

    def _extract_rules(self, text: str) -> list[dict]:
        """Extraire des règles SI/ALORS depuis un texte."""
        rules = []
        if not text:
            return rules
        lower = text.lower()
        for keyword in ("si ", "if ", "quand ", "when ", "lorsque "):
            if keyword in lower:
                idx = lower.index(keyword)
                snippet = text[idx:idx + 200]
                rules.append({
                    "type": "conditional",
                    "raw": snippet.strip(),
                    "source": "llm",
                })
        return rules

    def _extract_relations(self, text: str) -> list[dict]:
        """Extraire des relations entre entités."""
        relations = []
        if not text:
            return relations
        for keyword in (" est ", " a ", " possède ", " contient ",
                        " is ", " has ", " contains "):
            if keyword in text.lower():
                relations.append({
                    "type": "relation",
                    "keyword": keyword.strip(),
                    "source": "llm",
                })
        return relations

    def _compute_confidence(self, facts: list, rules: list) -> float:
        """Score de confiance basé sur la quantité extraite."""
        if not facts and not rules:
            return 0.1
        base = min(0.5 + len(facts) * 0.05 + len(rules) * 0.1, 0.95)
        return round(base, 3)

    def _detect_conflicts(self, sym_facts: list, neu_facts: list) -> list[dict]:
        """Détecter les faits contradictoires."""
        conflicts = []
        for sf in sym_facts:
            for nf in neu_facts:
                if self._facts_conflict(sf, nf):
                    conflicts.append({
                        "symbolic": sf,
                        "neural": nf,
                        "type": "contradiction",
                    })
        return conflicts

    def _facts_conflict(self, a: dict, b: dict) -> bool:
        """Deux faits sont en conflit si même entité+prédicat, valeur ≠."""
        return (a.get("entity") == b.get("entity")
                and a.get("predicate") == b.get("predicate")
                and a.get("value") != b.get("value")
                and a.get("entity") is not None)

    def _trim(self) -> None:
        if len(self._translations) > 5000:
            self._translations = self._translations[-5000:]
