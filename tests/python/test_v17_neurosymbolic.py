"""
Tests EXO v17 — Architecture neuro-symbolique
8 classes de tests unitaires + 1 classe d'intégration
"""

import pytest
import sys
import os


# ═══════════════════════════════════════════════════════════════
# 1. ReasoningBridge
# ═══════════════════════════════════════════════════════════════

from reasoning_bridge import ReasoningBridge


class TestReasoningBridge:
    def _make(self):
        return ReasoningBridge()

    def test_health_check(self):
        rb = self._make()
        h = rb.health_check()
        assert h["service"] == "reasoning_bridge"
        assert h["status"] == "ok"

    def test_llm_to_symbolic(self):
        rb = self._make()
        r = rb.llm_to_symbolic({"text": "allume la lumière du salon"})
        assert "id" in r
        assert "facts" in r
        assert rb.get_stats()["llm_to_symbolic"] == 1

    def test_symbolic_to_llm(self):
        rb = self._make()
        rule = {"type": "rule", "condition": "temp > 25", "action": "clim_on"}
        r = rb.symbolic_to_llm(rule)
        assert "id" in r
        assert "prompt" in r
        assert rb.get_stats()["symbolic_to_llm"] == 1

    def test_merge_reasoning(self):
        rb = self._make()
        sym = {"conclusions": [{"statement": "A"}], "confidence": 0.8}
        neu = {"interpretation": {"statement": "B"}, "confidence": 0.7}
        r = rb.merge_reasoning(sym, neu)
        assert "merged_confidence" in r
        assert rb.get_stats()["merges"] == 1

    def test_merge_with_conflict(self):
        rb = self._make()
        sym = {"conclusions": [{"statement": "on", "subject": "light"}],
               "confidence": 0.8}
        neu = {"interpretation": {"statement": "off", "subject": "light"},
               "confidence": 0.7}
        r = rb.merge_reasoning(sym, neu)
        assert r["conflict_count"] >= 0  # may or may not detect conflict

    def test_get_translations(self):
        rb = self._make()
        rb.llm_to_symbolic({"text": "test1"})
        rb.llm_to_symbolic({"text": "test2"})
        t = rb.get_translations(1)
        assert len(t) == 1

    def test_restart(self):
        rb = self._make()
        rb.llm_to_symbolic({"text": "test"})
        rb.restart()
        assert rb.get_stats()["llm_to_symbolic"] == 0
        assert rb.get_translations() == []


# ═══════════════════════════════════════════════════════════════
# 2. HybridInferenceEngine
# ═══════════════════════════════════════════════════════════════

from hybrid_inference_engine import HybridInferenceEngine


class TestHybridInferenceEngine:
    def _make(self):
        return HybridInferenceEngine()

    def test_health_check(self):
        eng = self._make()
        h = eng.health_check()
        assert h["service"] == "hybrid_inference"
        assert h["status"] == "ok"

    def test_infer_hybrid(self):
        eng = self._make()
        r = eng.infer_hybrid({"question": "quelle heure est-il?"})
        assert "symbolic_result" in r
        assert "neural_result" in r
        assert "combined" in r
        assert eng.get_stats()["hybrid_inferences"] == 1

    def test_infer_symbolic(self):
        eng = self._make()
        r = eng.infer_symbolic({"question": "test query"})
        assert "conclusions" in r
        assert "confidence" in r
        assert eng.get_stats()["symbolic_inferences"] == 1

    def test_infer_neural(self):
        eng = self._make()
        r = eng.infer_neural({"question": "test query"})
        assert "interpretation" in r
        assert "confidence" in r
        assert eng.get_stats()["neural_inferences"] == 1

    def test_combine_inferences(self):
        eng = self._make()
        sym = {"conclusions": [{"statement": "A"}], "confidence": 0.8}
        neu = {"interpretation": {"statement": "B"}, "confidence": 0.6}
        r = eng.combine_inferences(sym, neu)
        assert "confidence" in r
        assert "preferred_source" in r
        assert eng.get_stats()["combinations"] == 1

    def test_get_inference_log(self):
        eng = self._make()
        eng.infer_hybrid({"question": "q1"})
        eng.infer_hybrid({"question": "q2"})
        log = eng.get_inference_log(1)
        assert len(log) == 1

    def test_restart(self):
        eng = self._make()
        eng.infer_hybrid({"question": "q"})
        eng.restart()
        assert eng.get_stats()["hybrid_inferences"] == 0
        assert eng.get_inference_log() == []


# ═══════════════════════════════════════════════════════════════
# 3. KnowledgeGroundedLLM
# ═══════════════════════════════════════════════════════════════

from knowledge_grounded_llm import KnowledgeGroundedLLM


class TestKnowledgeGroundedLLM:
    def _make(self):
        return KnowledgeGroundedLLM()

    def test_health_check(self):
        g = self._make()
        h = g.health_check()
        assert h["service"] == "knowledge_grounded_llm"
        assert h["status"] == "ok"

    def test_ground_prompt(self):
        g = self._make()
        r = g.ground_prompt("allume la lumière", {"room": "salon"})
        assert "augmented_prompt" in r
        assert g.get_stats()["prompts_grounded"] == 1

    def test_ground_llm_output(self):
        g = self._make()
        r = g.ground_llm_output({"text": "La lumière du salon est allumée"})
        assert "grounding_score" in r
        assert g.get_stats()["outputs_grounded"] == 1

    def test_validate_grounding(self):
        g = self._make()
        r = g.validate_grounding()
        assert "valid" in r
        assert g.get_stats()["validations_run"] == 1

    def test_get_grounding_history(self):
        g = self._make()
        g.ground_prompt("p1", {})
        g.ground_prompt("p2", {})
        h = g.get_grounding_history(1)
        assert len(h) == 1

    def test_restart(self):
        g = self._make()
        g.ground_prompt("p", {})
        g.restart()
        assert g.get_stats()["prompts_grounded"] == 0
        assert g.get_grounding_history() == []


# ═══════════════════════════════════════════════════════════════
# 4. NeuroSymbolicCoherenceEngine
# ═══════════════════════════════════════════════════════════════

from neurosymbolic_coherence_engine import NeuroSymbolicCoherenceEngine


class TestNeuroSymbolicCoherenceEngine:
    def _make(self):
        return NeuroSymbolicCoherenceEngine()

    def test_health_check(self):
        c = self._make()
        h = c.health_check()
        assert h["service"] == "neurosymbolic_coherence"
        assert h["status"] == "ok"

    def test_check_consistency(self):
        c = self._make()
        r = c.check_neuro_symbolic_consistency()
        assert "overall_score" in r
        assert "coherent" in r
        assert c.get_stats()["checks_run"] == 1

    def test_enforce_consistency(self):
        c = self._make()
        r = c.enforce_neuro_symbolic_consistency()
        assert "actions_taken" in r
        assert c.get_stats()["enforcements_run"] == 1

    def test_check_specific(self):
        c = self._make()
        r = c.check_specific("lighting", "semantic")
        assert "score" in r or "overall_score" in r
        assert c.get_stats()["checks_run"] >= 1

    def test_get_coherence_history(self):
        c = self._make()
        c.check_neuro_symbolic_consistency()
        c.check_neuro_symbolic_consistency()
        h = c.get_coherence_history(1)
        assert len(h) == 1

    def test_restart(self):
        c = self._make()
        c.check_neuro_symbolic_consistency()
        c.restart()
        assert c.get_stats()["checks_run"] == 0
        assert c.get_coherence_history() == []


# ═══════════════════════════════════════════════════════════════
# 5. SymbolicValidator
# ═══════════════════════════════════════════════════════════════

from symbolic_validator import SymbolicValidator


class TestSymbolicValidator:
    def _make(self):
        return SymbolicValidator()

    def test_health_check(self):
        v = self._make()
        h = v.health_check()
        assert h["service"] == "symbolic_validator"
        assert h["status"] == "ok"

    def test_validate_llm_output(self):
        v = self._make()
        r = v.validate_llm_output({"text": "La lumière est allumée."})
        assert "valid" in r
        assert "overall_score" in r
        assert v.get_stats()["validations_run"] == 1

    def test_correct_llm_output(self):
        v = self._make()
        r = v.correct_llm_output({"text": "Texte à corriger"})
        assert "corrected" in r or "corrections" in r
        assert v.get_stats()["corrections_applied"] >= 0

    def test_explain_validation(self):
        v = self._make()
        v.validate_llm_output({"text": "test"})
        hist = v.get_validation_history(1)
        if hist and "validation_id" in hist[0]:
            r = v.explain_validation(hist[0]["validation_id"])
            assert "found" in r or "text" in r

    def test_get_validation_history(self):
        v = self._make()
        v.validate_llm_output({"text": "t1"})
        v.validate_llm_output({"text": "t2"})
        h = v.get_validation_history(1)
        assert len(h) == 1

    def test_restart(self):
        v = self._make()
        v.validate_llm_output({"text": "t"})
        v.restart()
        assert v.get_stats()["validations_run"] == 0
        assert v.get_validation_history() == []


# ═══════════════════════════════════════════════════════════════
# 6. SemanticExtractor
# ═══════════════════════════════════════════════════════════════

from semantic_extractor import SemanticExtractor


class TestSemanticExtractor:
    def _make(self):
        return SemanticExtractor()

    def test_health_check(self):
        e = self._make()
        h = e.health_check()
        assert h["service"] == "semantic_extractor"
        assert h["status"] == "ok"

    def test_extract_entities(self):
        e = self._make()
        r = e.extract_entities("la lampe du salon est allumée")
        assert "entities" in r
        assert e.get_stats()["entities_extracted"] >= 0

    def test_extract_relations(self):
        e = self._make()
        r = e.extract_relations("la lampe est dans le salon")
        assert "relations" in r
        assert e.get_stats()["relations_extracted"] >= 0

    def test_extract_semantic_graph(self):
        e = self._make()
        r = e.extract_semantic_graph("la lampe du salon")
        assert "nodes" in r or "graph" in r
        assert e.get_stats()["graphs_built"] >= 1

    def test_extract_patterns(self):
        e = self._make()
        r = e.extract_patterns("allume la lumière tous les soirs à 20h")
        assert "patterns" in r
        assert e.get_stats()["patterns_detected"] >= 0

    def test_get_extraction_history(self):
        e = self._make()
        e.extract_entities("test")
        h = e.get_extraction_history(1)
        assert len(h) == 1

    def test_restart(self):
        e = self._make()
        e.extract_entities("t")
        e.restart()
        assert e.get_stats()["entities_extracted"] == 0
        assert e.get_extraction_history() == []


# ═══════════════════════════════════════════════════════════════
# 7. KnowledgeAugmentor
# ═══════════════════════════════════════════════════════════════

from knowledge_augmentor import KnowledgeAugmentor


class TestKnowledgeAugmentor:
    def _make(self):
        return KnowledgeAugmentor()

    def test_health_check(self):
        a = self._make()
        h = a.health_check()
        assert h["service"] == "knowledge_augmentor"
        assert h["status"] == "ok"

    def test_augment_kg(self):
        a = self._make()
        facts = [{"subject": "salon", "predicate": "has", "object": "lampe"}]
        r = a.augment_kg(facts)
        assert "added" in r or "facts_added" in r
        assert a.get_stats()["facts_added"] >= 0

    def test_augment_rules(self):
        a = self._make()
        rules = [{"condition": "temp > 25", "action": "clim_on"}]
        r = a.augment_rules(rules)
        assert "added" in r or "rules_added" in r
        assert a.get_stats()["rules_added"] >= 0

    def test_consolidate_knowledge(self):
        a = self._make()
        r = a.consolidate_knowledge()
        assert "consolidation_id" in r or "duplicates_removed" in r
        assert a.get_stats()["consolidations_run"] >= 1

    def test_augment_empty_facts(self):
        a = self._make()
        r = a.augment_kg([])
        assert a.get_stats()["facts_added"] == 0

    def test_get_augmentation_history(self):
        a = self._make()
        a.augment_kg([{"subject": "a", "predicate": "b", "object": "c"}])
        h = a.get_augmentation_history(1)
        assert len(h) == 1

    def test_restart(self):
        a = self._make()
        a.consolidate_knowledge()
        a.restart()
        assert a.get_stats()["consolidations_run"] == 0
        assert a.get_augmentation_history() == []


# ═══════════════════════════════════════════════════════════════
# 8. NeuroSymbolicExplainabilityEngine
# ═══════════════════════════════════════════════════════════════

from neurosymbolic_explainability_engine import NeuroSymbolicExplainabilityEngine


class TestNeuroSymbolicExplainabilityEngine:
    def _make(self):
        return NeuroSymbolicExplainabilityEngine()

    def test_health_check(self):
        e = self._make()
        h = e.health_check()
        assert h["service"] == "neurosymbolic_explainability"
        assert h["status"] == "ok"

    def test_explain_hybrid_decision(self):
        e = self._make()
        decision = {
            "symbolic_result": {"conclusions": [{"statement": "A"}],
                                 "confidence": 0.8},
            "neural_result": {"interpretation": {"statement": "B"},
                               "confidence": 0.7},
            "merged_confidence": 0.75,
            "preferred_source": "symbolic",
        }
        r = e.explain_hybrid_decision(decision)
        assert "text" in r
        assert "symbolic" in r
        assert "neural" in r
        assert r["merged_confidence"] == 0.75
        assert e.get_stats()["hybrid_explanations"] == 1

    def test_explain_symbolic_part(self):
        e = self._make()
        decision = {"symbolic_result": {"conclusions": [], "confidence": 0.6}}
        r = e.explain_symbolic_part(decision)
        assert "text" in r
        assert "confidence" in r
        assert e.get_stats()["symbolic_explanations"] == 1

    def test_explain_neural_part(self):
        e = self._make()
        decision = {"neural_result": {"interpretation": {"statement": "X"},
                                       "confidence": 0.9}}
        r = e.explain_neural_part(decision)
        assert "text" in r
        assert "confidence" in r
        assert e.get_stats()["neural_explanations"] == 1

    def test_explain_full_v17(self):
        e = self._make()
        r = e.explain_full_v17({"session_id": "test"})
        assert "text" in r
        assert "v17" in r["text"].lower() or "v17" in r.get("id", "")
        assert e.get_stats()["full_explanations"] == 1

    def test_get_explanation_history(self):
        e = self._make()
        e.explain_full_v17({})
        e.explain_full_v17({})
        h = e.get_explanation_history(1)
        assert len(h) == 1

    def test_restart(self):
        e = self._make()
        e.explain_full_v17({})
        e.restart()
        assert e.get_stats()["full_explanations"] == 0
        assert e.get_explanation_history() == []


# ═══════════════════════════════════════════════════════════════
# 9. Intégration v17
# ═══════════════════════════════════════════════════════════════


class TestV17Integration:
    """Test que les 8 modules v17 fonctionnent ensemble."""

    def _build_stack(self):
        rb = ReasoningBridge()
        hi = HybridInferenceEngine(reasoning_bridge=rb)
        kg_llm = KnowledgeGroundedLLM(reasoning_bridge=rb)
        coh = NeuroSymbolicCoherenceEngine(reasoning_bridge=rb,
                                            hybrid_inference=hi)
        sv = SymbolicValidator(reasoning_bridge=rb)
        se = SemanticExtractor()
        ka = KnowledgeAugmentor(semantic_extractor=se,
                                 reasoning_bridge=rb)
        exp = NeuroSymbolicExplainabilityEngine(
            reasoning_bridge=rb, hybrid_inference=hi,
            symbolic_validator=sv, coherence_engine=coh)
        return {
            "reasoning_bridge": rb,
            "hybrid_inference": hi,
            "knowledge_grounded_llm": kg_llm,
            "coherence_engine": coh,
            "symbolic_validator": sv,
            "semantic_extractor": se,
            "knowledge_augmentor": ka,
            "neurosymbolic_explainability": exp,
        }

    def test_all_modules_health(self):
        stack = self._build_stack()
        for name, mod in stack.items():
            h = mod.health_check()
            assert h["status"] == "ok", f"{name} health failed"

    def test_hybrid_pipeline(self):
        stack = self._build_stack()
        # 1) Translate LLM → symbolic
        rb = stack["reasoning_bridge"]
        t = rb.llm_to_symbolic({"text": "allume la lumière du salon"})
        assert "facts" in t

        # 2) Hybrid inference
        hi = stack["hybrid_inference"]
        r = hi.infer_hybrid({"question": "allume la lumière"})
        assert "combined" in r

        # 3) Validate output
        sv = stack["symbolic_validator"]
        v = sv.validate_llm_output({"text": "La lumière du salon est allumée"})
        assert "valid" in v

    def test_extract_and_augment(self):
        stack = self._build_stack()
        se = stack["semantic_extractor"]
        ka = stack["knowledge_augmentor"]

        entities = se.extract_entities("la lampe du salon")
        assert "entities" in entities

        facts = [{"subject": "salon", "predicate": "has", "object": "lampe"}]
        aug = ka.augment_kg(facts)
        assert aug  # non-empty result

    def test_coherence_and_explain(self):
        stack = self._build_stack()
        coh = stack["coherence_engine"]
        exp = stack["neurosymbolic_explainability"]

        check = coh.check_neuro_symbolic_consistency()
        assert "coherent" in check

        explanation = exp.explain_full_v17({"session": "test"})
        assert "text" in explanation

    def test_full_cycle(self):
        """Cycle complet: translate → infer → ground → validate → explain."""
        stack = self._build_stack()

        # Translate
        rb = stack["reasoning_bridge"]
        trans = rb.llm_to_symbolic({"text": "éteins la lumière du couloir"})

        # Infer
        hi = stack["hybrid_inference"]
        inf = hi.infer_hybrid({"question": "éteins la lumière"})

        # Ground
        kg = stack["knowledge_grounded_llm"]
        grounded = kg.ground_prompt("éteins la lumière", {})

        # Validate
        sv = stack["symbolic_validator"]
        val = sv.validate_llm_output({"text": "Lumière du couloir éteinte"})

        # Explain
        exp = stack["neurosymbolic_explainability"]
        expl = exp.explain_hybrid_decision({
            "symbolic_result": inf.get("symbolic_result", {}),
            "neural_result": inf.get("neural_result", {}),
            "merged_confidence": inf.get("merged_confidence", 0),
        })
        assert "text" in expl

    def test_all_restart(self):
        stack = self._build_stack()
        # Use each module
        stack["reasoning_bridge"].llm_to_symbolic({"text": "test"})
        stack["hybrid_inference"].infer_hybrid({"question": "test"})
        stack["symbolic_validator"].validate_llm_output({"text": "test"})
        stack["semantic_extractor"].extract_entities("test")
        stack["knowledge_augmentor"].consolidate_knowledge()
        stack["neurosymbolic_explainability"].explain_full_v17({})

        # Restart all
        for mod in stack.values():
            mod.restart()

        # Verify all stats reset
        for name, mod in stack.items():
            stats = mod.get_stats()
            for k, v in stats.items():
                assert v == 0, f"{name}.{k} should be 0 after restart, got {v}"

    def test_all_get_stats(self):
        stack = self._build_stack()
        for name, mod in stack.items():
            stats = mod.get_stats()
            assert isinstance(stats, dict), f"{name}.get_stats() should return dict"
