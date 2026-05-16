"""
Tests unitaires — EXO v12 Auto-réflexion, méta-raisonnement, auto-cohérence
Couvre: SelfReflectionEngine, MetaReasoningEngine, MetaPlannerV2,
MetaVerifier, SelfConsistencyEngine, MetaSupervisorV2, ExplainabilityEngineV2.
"""

import sys
import time
from pathlib import Path

import pytest



# ═════════════════════════════════════════════════════
#  Helpers
# ═════════════════════════════════════════════════════

def _make_memory(tmp_path):
    from meta_memory import MetaMemory
    return MetaMemory(persist_dir=str(tmp_path))


def _make_governance(meta_memory):
    from auto_governance import AutoGovernance
    return AutoGovernance(meta_memory)


def _sample_reasoning():
    return {
        "steps": [
            {"text": "L'utilisateur demande la météo", "evidence": "voice input"},
            {"text": "Recherche du service météo approprié", "evidence": "config"},
            {"text": "Appel de l'API météo pour Paris", "evidence": "location"},
        ],
        "conclusion": "La météo à Paris est ensoleillée, 22°C",
        "confidence": 0.85,
    }


def _sample_plan():
    return {
        "goal": "Allumer les lumières du salon",
        "steps": [
            {"id": 0, "tool": "ha_light", "description": "Allumer lumière salon", "depends_on": []},
            {"id": 1, "tool": "ha_scene", "description": "Activer scène salon", "depends_on": [0]},
        ],
        "constraints": ["max_brightness: 80%"],
    }


def _sample_decision():
    return {
        "action": "search_web",
        "reason": "L'utilisateur demande une information non disponible localement",
        "alternatives": ["use_cache", "ask_user"],
        "confidence": 0.7,
    }


# ═════════════════════════════════════════════════════
#  SelfReflectionEngine
# ═════════════════════════════════════════════════════

class TestSelfReflectionEngine:
    def _make(self, tmp_path):
        from self_reflection_engine import SelfReflectionEngine
        mem = _make_memory(tmp_path)
        return SelfReflectionEngine(mem)

    def test_create(self, tmp_path):
        eng = self._make(tmp_path)
        assert eng is not None

    def test_reflect_on_reasoning(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.reflect_on_reasoning(_sample_reasoning())
        assert result["type"] == "reasoning_reflection"
        assert "quality" in result
        assert "issues" in result
        assert "strengths" in result
        assert result["step_count"] == 3

    def test_reflect_on_reasoning_empty(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.reflect_on_reasoning({"steps": [], "conclusion": "", "confidence": 0.1})
        assert result["type"] == "reasoning_reflection"
        assert any(i["type"] == "missing_conclusion" for i in result["issues"])

    def test_reflect_on_reasoning_weak_hypothesis(self, tmp_path):
        eng = self._make(tmp_path)
        trace = {
            "steps": [{"text": "Peut-être que l'utilisateur veut la météo"}],
            "conclusion": "Météo demandée",
            "confidence": 0.5,
        }
        result = eng.reflect_on_reasoning(trace)
        assert any(i["type"] == "weak_hypothesis" for i in result["issues"])

    def test_reflect_on_reasoning_overconfidence(self, tmp_path):
        eng = self._make(tmp_path)
        trace = {
            "steps": [{"text": "Réponse immédiate"}],
            "conclusion": "Oui",
            "confidence": 0.99,
        }
        result = eng.reflect_on_reasoning(trace)
        assert any(i["type"] == "overconfidence" for i in result["issues"])

    def test_reflect_on_reasoning_redundant(self, tmp_path):
        eng = self._make(tmp_path)
        trace = {
            "steps": [
                {"text": "Vérifier l'entrée"},
                {"text": "Vérifier l'entrée"},
            ],
            "conclusion": "OK",
            "confidence": 0.7,
        }
        result = eng.reflect_on_reasoning(trace)
        assert any(i["type"] == "redundant_step" for i in result["issues"])

    def test_reflect_on_plan(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.reflect_on_plan(_sample_plan())
        assert result["type"] == "plan_reflection"
        assert "quality" in result
        assert result["step_count"] == 2

    def test_reflect_on_plan_no_goal(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.reflect_on_plan({"steps": [{"tool": "x", "description": "y"}]})
        assert any(i["type"] == "missing_goal" for i in result["issues"])

    def test_reflect_on_plan_dangerous(self, tmp_path):
        eng = self._make(tmp_path)
        plan = {
            "goal": "Cleanup",
            "steps": [{"tool": "rm", "description": "delete all files"}],
        }
        result = eng.reflect_on_plan(plan)
        assert any(i["type"] == "dangerous_shortcut" for i in result["issues"])

    def test_reflect_on_decision(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.reflect_on_decision(_sample_decision())
        assert result["type"] == "decision_reflection"
        assert result["action"] == "search_web"

    def test_reflect_on_decision_no_reason(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.reflect_on_decision({"action": "test", "confidence": 0.5})
        assert any(i["type"] == "missing_reason" for i in result["issues"])

    def test_reflect_on_decision_no_alternatives(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.reflect_on_decision({
            "action": "test",
            "reason": "because",
            "confidence": 0.5,
        })
        assert any(i["type"] == "no_alternatives" for i in result["issues"])

    def test_health_check(self, tmp_path):
        eng = self._make(tmp_path)
        health = eng.health_check()
        assert health["service"] == "self_reflection"
        assert health["status"] == "ok"

    def test_restart(self, tmp_path):
        eng = self._make(tmp_path)
        eng.reflect_on_reasoning(_sample_reasoning())
        assert eng.get_stats()["reasoning_reflections"] == 1
        eng.restart()
        assert eng.get_stats()["reasoning_reflections"] == 0

    def test_stats(self, tmp_path):
        eng = self._make(tmp_path)
        eng.reflect_on_reasoning(_sample_reasoning())
        eng.reflect_on_plan(_sample_plan())
        eng.reflect_on_decision(_sample_decision())
        stats = eng.get_stats()
        assert stats["reasoning_reflections"] == 1
        assert stats["plan_reflections"] == 1
        assert stats["decision_reflections"] == 1


# ═════════════════════════════════════════════════════
#  MetaReasoningEngine
# ═════════════════════════════════════════════════════

class TestMetaReasoningEngine:
    def _make(self, tmp_path):
        from meta_reasoning_engine import MetaReasoningEngine
        mem = _make_memory(tmp_path)
        return MetaReasoningEngine(mem)

    def test_create(self, tmp_path):
        eng = self._make(tmp_path)
        assert eng is not None

    def test_meta_reason(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.meta_reason(_sample_reasoning())
        assert result["type"] == "meta_reasoning"
        assert "quality" in result
        assert "improvements" in result
        assert "biases" in result

    def test_evaluate_reasoning_quality(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.evaluate_reasoning_quality(_sample_reasoning())
        assert "logical_structure" in result
        assert "argument_strength" in result
        assert "step_relevance" in result
        assert "global_coherence" in result
        assert "overall" in result
        assert 0.0 <= result["overall"] <= 1.0

    def test_evaluate_empty_reasoning(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.evaluate_reasoning_quality({"steps": [], "conclusion": ""})
        assert result["overall"] <= 0.5

    def test_propose_improvements(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.propose_reasoning_improvements(_sample_reasoning())
        assert "improvements" in result
        assert "count" in result
        assert isinstance(result["improvements"], list)

    def test_propose_improvements_few_steps(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.propose_reasoning_improvements({
            "steps": [{"text": "ok"}],
            "conclusion": "done",
            "confidence": 0.3,
        })
        assert any(i["type"] == "add_steps" for i in result["improvements"])

    def test_detect_confirmation_bias(self, tmp_path):
        eng = self._make(tmp_path)
        trace = {
            "steps": [
                {"text": "Le résultat est positif"},
                {"text": "Le test confirme le positif"},
                {"text": "Tout est positif"},
            ],
            "conclusion": "Résultat positif confirmé",
            "confidence": 0.9,
        }
        result = eng.meta_reason(trace)
        assert any(b["type"] == "confirmation_bias" for b in result["biases"])

    def test_detect_overconfidence_bias(self, tmp_path):
        eng = self._make(tmp_path)
        trace = {
            "steps": [{"text": "Réponse rapide"}],
            "conclusion": "Oui",
            "confidence": 0.99,
        }
        result = eng.meta_reason(trace)
        assert any(b["type"] == "overconfidence_bias" for b in result["biases"])

    def test_health_check(self, tmp_path):
        eng = self._make(tmp_path)
        health = eng.health_check()
        assert health["service"] == "meta_reasoning"
        assert health["status"] == "ok"

    def test_restart(self, tmp_path):
        eng = self._make(tmp_path)
        eng.meta_reason(_sample_reasoning())
        assert eng.get_stats()["meta_reasonings"] == 1
        eng.restart()
        assert eng.get_stats()["meta_reasonings"] == 0

    def test_stats(self, tmp_path):
        eng = self._make(tmp_path)
        eng.meta_reason(_sample_reasoning())
        stats = eng.get_stats()
        assert stats["meta_reasonings"] == 1
        assert stats["quality_evaluations"] == 1
        assert stats["improvements_proposed"] >= 0


# ═════════════════════════════════════════════════════
#  MetaPlannerV2
# ═════════════════════════════════════════════════════

class TestMetaPlannerV2:
    def _make(self, tmp_path):
        from meta_planner_v2 import MetaPlannerV2
        mem = _make_memory(tmp_path)
        return MetaPlannerV2(mem)

    def test_create(self, tmp_path):
        eng = self._make(tmp_path)
        assert eng is not None

    def test_evaluate_plan(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.evaluate_plan(_sample_plan())
        assert result["type"] == "plan_evaluation"
        assert "scores" in result
        scores = result["scores"]
        assert "completeness" in scores
        assert "efficiency" in scores
        assert "robustness" in scores
        assert "alignment" in scores
        assert "overall" in scores

    def test_evaluate_empty_plan(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.evaluate_plan({"steps": [], "goal": ""})
        assert result["scores"]["overall"] <= 0.5

    def test_compare_plans(self, tmp_path):
        eng = self._make(tmp_path)
        plans = [
            _sample_plan(),
            {"goal": "Test", "steps": [{"tool": "x", "description": "y"}]},
        ]
        result = eng.compare_plans(plans)
        assert result["type"] == "plan_comparison"
        assert len(result["ranking"]) == 2
        assert result["best_index"] in (0, 1)

    def test_compare_empty_plans(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.compare_plans([])
        assert result["best_index"] == -1

    def test_improve_plan(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.improve_plan(_sample_plan())
        assert result["type"] == "plan_improvement"
        assert "changes" in result
        assert "improved_plan" in result

    def test_improve_plan_no_goal(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.improve_plan({"steps": [{"tool": "x", "description": "y"}]})
        assert any(c["type"] == "add_goal" for c in result["changes"])

    def test_improve_plan_empty_steps(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.improve_plan({
            "goal": "Test",
            "steps": [{"tool": "a", "description": "b"}, {}],
        })
        assert any(c["type"] == "remove_empty_step" for c in result["changes"])

    def test_health_check(self, tmp_path):
        eng = self._make(tmp_path)
        health = eng.health_check()
        assert health["service"] == "meta_planner_v2"
        assert health["status"] == "ok"

    def test_restart(self, tmp_path):
        eng = self._make(tmp_path)
        eng.evaluate_plan(_sample_plan())
        assert eng.get_stats()["plans_evaluated"] == 1
        eng.restart()
        assert eng.get_stats()["plans_evaluated"] == 0

    def test_stats(self, tmp_path):
        eng = self._make(tmp_path)
        eng.evaluate_plan(_sample_plan())
        eng.improve_plan(_sample_plan())
        stats = eng.get_stats()
        assert stats["plans_evaluated"] >= 1
        assert stats["plans_improved"] == 1

    def test_with_v11_planner(self, tmp_path):
        from meta_planner import MetaPlanner
        from meta_planner_v2 import MetaPlannerV2
        mem = _make_memory(tmp_path)
        v1 = MetaPlanner(mem)
        eng = MetaPlannerV2(mem, meta_planner_v1=v1)
        result = eng.improve_plan(_sample_plan())
        assert result["type"] == "plan_improvement"


# ═════════════════════════════════════════════════════
#  MetaVerifier
# ═════════════════════════════════════════════════════

class TestMetaVerifier:
    def _make(self, tmp_path):
        from meta_verifier import MetaVerifier
        mem = _make_memory(tmp_path)
        return MetaVerifier(mem)

    def test_create(self, tmp_path):
        eng = self._make(tmp_path)
        assert eng is not None

    def test_verify_valid_plan(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.meta_verify(_sample_plan())
        assert result["type"] == "plan_verification"
        assert result["valid"] is True

    def test_verify_plan_forward_dep(self, tmp_path):
        eng = self._make(tmp_path)
        plan = {
            "goal": "Test",
            "steps": [
                {"id": 0, "tool": "a", "description": "x", "depends_on": [1]},
                {"id": 1, "tool": "b", "description": "y", "depends_on": []},
            ],
        }
        result = eng.meta_verify(plan)
        assert any(i["type"] == "forward_dependency" for i in result["issues"])

    def test_verify_empty_plan(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.meta_verify({"steps": [], "goal": "Test"})
        assert result["valid"] is True  # no steps = no issues

    def test_verify_reasoning(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.meta_verify_reasoning(_sample_reasoning())
        assert result["type"] == "reasoning_verification"
        assert result["valid"] is True

    def test_verify_reasoning_empty_step(self, tmp_path):
        eng = self._make(tmp_path)
        trace = {
            "steps": [{"text": ""}, {"text": "Valid step"}],
            "conclusion": "OK",
            "confidence": 0.5,
        }
        result = eng.meta_verify_reasoning(trace)
        assert any(i["type"] == "empty_reasoning_step" for i in result["issues"])

    def test_verify_reasoning_unsupported_conclusion(self, tmp_path):
        eng = self._make(tmp_path)
        trace = {
            "steps": [],
            "conclusion": "Important conclusion",
            "confidence": 0.8,
        }
        result = eng.meta_verify_reasoning(trace)
        assert any(i["type"] == "unsupported_conclusion" for i in result["issues"])

    def test_verify_with_governance(self, tmp_path):
        from meta_verifier import MetaVerifier
        mem = _make_memory(tmp_path)
        gov = _make_governance(mem)
        eng = MetaVerifier(mem, governance=gov)
        result = eng.meta_verify(_sample_plan())
        assert result["type"] == "plan_verification"

    def test_stats(self, tmp_path):
        eng = self._make(tmp_path)
        eng.meta_verify(_sample_plan())
        eng.meta_verify_reasoning(_sample_reasoning())
        stats = eng.get_stats()
        assert stats["plans_verified"] == 1
        assert stats["reasonings_verified"] == 1


# ═════════════════════════════════════════════════════
#  SelfConsistencyEngine
# ═════════════════════════════════════════════════════

class TestSelfConsistencyEngine:
    def _make(self, tmp_path):
        from self_consistency_engine import SelfConsistencyEngine
        mem = _make_memory(tmp_path)
        return SelfConsistencyEngine(mem)

    def test_create(self, tmp_path):
        eng = self._make(tmp_path)
        assert eng is not None

    def test_check_consistency_plan(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.check_consistency(_sample_plan())
        assert result["type"] == "plan_consistency"
        assert result["consistent"] is True

    def test_check_consistency_conflicting_actions(self, tmp_path):
        eng = self._make(tmp_path)
        plan = {
            "goal": "Test",
            "steps": [
                {"tool": "enable", "target": "light", "description": "enable light"},
                {"tool": "disable", "target": "light", "description": "disable light"},
            ],
        }
        result = eng.check_consistency(plan)
        assert any(i["type"] == "conflicting_actions" for i in result["inconsistencies"])

    def test_check_consistency_circular_deps(self, tmp_path):
        eng = self._make(tmp_path)
        plan = {
            "goal": "Test",
            "steps": [
                {"id": "a", "tool": "x", "description": "step a", "depends_on": ["b"]},
                {"id": "b", "tool": "y", "description": "step b", "depends_on": ["a"]},
            ],
        }
        result = eng.check_consistency(plan)
        assert any(i["type"] == "circular_dependency" for i in result["inconsistencies"])

    def test_check_consistency_reasoning(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.check_consistency_reasoning(_sample_reasoning())
        assert result["type"] == "reasoning_consistency"
        assert result["consistent"] is True

    def test_check_consistency_reasoning_contradiction(self, tmp_path):
        eng = self._make(tmp_path)
        trace = {
            "steps": [
                {"text": "Le résultat est vrai pour le test principal"},
                {"text": "Le résultat est faux pour le test principal"},
            ],
            "conclusion": "Incertain",
            "confidence": 0.3,
        }
        result = eng.check_consistency_reasoning(trace)
        assert any(
            i["type"] == "step_contradiction"
            for i in result["inconsistencies"]
        )

    def test_enforce_consistency(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.enforce_consistency()
        assert result["type"] == "consistency_enforcement"
        assert "actions" in result
        assert "entries_checked" in result

    def test_enforce_consistency_duplicates(self, tmp_path):
        from self_consistency_engine import SelfConsistencyEngine
        mem = _make_memory(tmp_path)
        mem.meta_add({"category": "preference", "key": "lang", "value": "fr"})
        mem.meta_add({"category": "preference", "key": "lang", "value": "en"})
        eng = SelfConsistencyEngine(mem)
        result = eng.enforce_consistency()
        assert any(
            a["action"] in ("duplicate_detected", "conflicting_preferences")
            for a in result["actions"]
        )

    def test_with_verifier(self, tmp_path):
        from self_consistency_engine import SelfConsistencyEngine
        from meta_verifier import MetaVerifier
        mem = _make_memory(tmp_path)
        verifier = MetaVerifier(mem)
        eng = SelfConsistencyEngine(mem, meta_verifier=verifier)
        result = eng.check_consistency(_sample_plan())
        assert result["verification"] is not None

    def test_stats(self, tmp_path):
        eng = self._make(tmp_path)
        eng.check_consistency(_sample_plan())
        eng.check_consistency_reasoning(_sample_reasoning())
        stats = eng.get_stats()
        assert stats["plan_checks"] == 1
        assert stats["reasoning_checks"] == 1


# ═════════════════════════════════════════════════════
#  MetaSupervisorV2
# ═════════════════════════════════════════════════════

class TestMetaSupervisorV2:
    def _make(self, tmp_path):
        from meta_supervisor_v2 import MetaSupervisorV2
        mem = _make_memory(tmp_path)
        return MetaSupervisorV2(mem)

    def test_create(self, tmp_path):
        eng = self._make(tmp_path)
        assert eng is not None

    def test_supervise_reasoning(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.supervise_reasoning(_sample_reasoning())
        assert result["type"] == "reasoning_supervision"
        assert result["approved"] is True

    def test_supervise_reasoning_too_many_steps(self, tmp_path):
        eng = self._make(tmp_path)
        eng.set_meta_rules({"max_reasoning_steps": 2})
        result = eng.supervise_reasoning(_sample_reasoning())
        assert any(i["type"] == "too_many_steps" for i in result["issues"])
        assert result["approved"] is False

    def test_supervise_reasoning_missing_conclusion(self, tmp_path):
        eng = self._make(tmp_path)
        trace = {"steps": [{"text": "test"}], "confidence": 0.5}
        result = eng.supervise_reasoning(trace)
        assert any(i["type"] == "missing_conclusion" for i in result["issues"])

    def test_supervise_reasoning_forbidden_action(self, tmp_path):
        eng = self._make(tmp_path)
        eng.set_meta_rules({"forbidden_actions": ["dangerous_op"]})
        trace = {
            "steps": [{"text": "exec", "action": "dangerous_op"}],
            "conclusion": "done",
            "confidence": 0.5,
        }
        result = eng.supervise_reasoning(trace)
        assert any(i["type"] == "forbidden_action" for i in result["issues"])
        assert result["approved"] is False

    def test_supervise_planning(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.supervise_planning(_sample_plan())
        assert result["type"] == "planning_supervision"
        assert result["approved"] is True

    def test_supervise_planning_too_many_steps(self, tmp_path):
        eng = self._make(tmp_path)
        eng.set_meta_rules({"max_plan_steps": 1})
        result = eng.supervise_planning(_sample_plan())
        assert any(i["type"] == "too_many_steps" for i in result["issues"])
        assert result["approved"] is False

    def test_supervise_planning_no_goal(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.supervise_planning({"steps": [{"tool": "x"}]})
        assert any(i["type"] == "missing_goal" for i in result["issues"])

    def test_enforce_meta_rules(self, tmp_path):
        eng = self._make(tmp_path)
        result = eng.enforce_meta_rules()
        assert result["type"] == "meta_enforcement"
        assert "actions" in result

    def test_enforce_with_v1(self, tmp_path):
        from meta_supervisor import MetaSupervisor
        from meta_supervisor_v2 import MetaSupervisorV2
        mem = _make_memory(tmp_path)
        v1 = MetaSupervisor(mem)
        eng = MetaSupervisorV2(mem, meta_supervisor_v1=v1)
        result = eng.enforce_meta_rules()
        assert result["type"] == "meta_enforcement"

    def test_with_reflection(self, tmp_path):
        from meta_supervisor_v2 import MetaSupervisorV2
        from self_reflection_engine import SelfReflectionEngine
        mem = _make_memory(tmp_path)
        reflection = SelfReflectionEngine(mem)
        eng = MetaSupervisorV2(mem, self_reflection=reflection)
        result = eng.supervise_reasoning(_sample_reasoning())
        assert result["reflection"] is not None

    def test_with_meta_reasoning(self, tmp_path):
        from meta_supervisor_v2 import MetaSupervisorV2
        from meta_reasoning_engine import MetaReasoningEngine
        mem = _make_memory(tmp_path)
        reasoning = MetaReasoningEngine(mem)
        eng = MetaSupervisorV2(mem, meta_reasoning=reasoning)
        result = eng.supervise_reasoning(_sample_reasoning())
        assert result["meta_analysis"] is not None

    def test_alerts(self, tmp_path):
        eng = self._make(tmp_path)
        eng.set_meta_rules({"max_reasoning_steps": 1})
        eng.supervise_reasoning(_sample_reasoning())
        alerts = eng.get_alerts()
        assert len(alerts) >= 1

    def test_stats(self, tmp_path):
        eng = self._make(tmp_path)
        eng.supervise_reasoning(_sample_reasoning())
        eng.supervise_planning(_sample_plan())
        stats = eng.get_stats()
        assert stats["reasoning_supervisions"] == 1
        assert stats["planning_supervisions"] == 1


# ═════════════════════════════════════════════════════
#  ExplainabilityEngineV2
# ═════════════════════════════════════════════════════

class TestExplainabilityEngineV2:
    def _make(self, tmp_path):
        from explainability_engine_v2 import ExplainabilityEngineV2
        mem = _make_memory(tmp_path)
        return ExplainabilityEngineV2(mem)

    def test_create(self, tmp_path):
        eng = self._make(tmp_path)
        assert eng is not None

    def test_explain_plan(self, tmp_path):
        eng = self._make(tmp_path)
        text = eng.explain_plan(_sample_plan())
        assert isinstance(text, str)
        assert "Objectif" in text
        assert "lumière" in text.lower() or "salon" in text.lower()

    def test_explain_plan_no_goal(self, tmp_path):
        eng = self._make(tmp_path)
        text = eng.explain_plan({"steps": [{"tool": "x"}]})
        assert "sans objectif" in text.lower()

    def test_explain_plan_empty(self, tmp_path):
        eng = self._make(tmp_path)
        text = eng.explain_plan({"goal": "Test", "steps": []})
        assert "aucune étape" in text.lower()

    def test_explain_reasoning(self, tmp_path):
        eng = self._make(tmp_path)
        text = eng.explain_reasoning(_sample_reasoning())
        assert isinstance(text, str)
        assert "Raisonnement" in text
        assert "85" in text  # confidence

    def test_explain_reasoning_no_conclusion(self, tmp_path):
        eng = self._make(tmp_path)
        text = eng.explain_reasoning({"steps": [{"text": "test"}], "confidence": 0.5})
        assert "conclusion" in text.lower()

    def test_explain_meta_decision_approved(self, tmp_path):
        eng = self._make(tmp_path)
        decision = {
            "type": "reasoning_supervision",
            "approved": True,
            "issues": [],
        }
        text = eng.explain_meta_decision(decision)
        assert "APPROUVÉ" in text

    def test_explain_meta_decision_rejected(self, tmp_path):
        eng = self._make(tmp_path)
        decision = {
            "type": "planning_supervision",
            "approved": False,
            "issues": [
                {"type": "too_many_steps", "detail": "50 steps (max 20)"},
            ],
        }
        text = eng.explain_meta_decision(decision)
        assert "REFUSÉ" in text
        assert "too_many_steps" in text

    def test_explain_meta_decision_with_reflection(self, tmp_path):
        eng = self._make(tmp_path)
        decision = {
            "type": "reasoning_supervision",
            "approved": True,
            "issues": [],
            "reflection": {"quality": 0.85},
        }
        text = eng.explain_meta_decision(decision)
        assert "85" in text

    def test_with_v1(self, tmp_path):
        from explainability_engine_v2 import ExplainabilityEngineV2
        from auto_explanation import AutoExplanation
        mem = _make_memory(tmp_path)
        v1 = AutoExplanation(mem)
        eng = ExplainabilityEngineV2(mem, auto_explanation_v1=v1)
        text = eng.explain_meta_decision({
            "type": "reasoning_supervision",
            "approved": True,
            "issues": [],
        })
        assert isinstance(text, str)

    def test_explanation_log(self, tmp_path):
        eng = self._make(tmp_path)
        eng.explain_plan(_sample_plan())
        eng.explain_reasoning(_sample_reasoning())
        log = eng.get_explanation_log()
        assert len(log) == 2

    def test_stats(self, tmp_path):
        eng = self._make(tmp_path)
        eng.explain_plan(_sample_plan())
        eng.explain_reasoning(_sample_reasoning())
        eng.explain_meta_decision({"type": "test", "approved": True, "issues": []})
        stats = eng.get_stats()
        assert stats["plan_explanations"] == 1
        assert stats["reasoning_explanations"] == 1
        assert stats["meta_decision_explanations"] == 1


# ═════════════════════════════════════════════════════
#  V12 Integration
# ═════════════════════════════════════════════════════

class TestV12Integration:
    """Tests d'intégration bout-en-bout v12."""

    def _make_all(self, tmp_path):
        from meta_memory import MetaMemory
        from auto_governance import AutoGovernance
        from meta_planner import MetaPlanner
        from meta_supervisor import MetaSupervisor
        from auto_explanation import AutoExplanation
        from self_reflection_engine import SelfReflectionEngine
        from meta_reasoning_engine import MetaReasoningEngine
        from meta_planner_v2 import MetaPlannerV2
        from meta_verifier import MetaVerifier
        from self_consistency_engine import SelfConsistencyEngine
        from meta_supervisor_v2 import MetaSupervisorV2
        from explainability_engine_v2 import ExplainabilityEngineV2

        mem = MetaMemory(persist_dir=str(tmp_path))
        gov = AutoGovernance(mem)
        planner_v1 = MetaPlanner(mem)
        supervisor_v1 = MetaSupervisor(mem)
        explanation_v1 = AutoExplanation(mem)

        reflection = SelfReflectionEngine(mem, gov)
        reasoning = MetaReasoningEngine(mem, gov)
        planner_v2 = MetaPlannerV2(mem, planner_v1, reflection)
        verifier = MetaVerifier(mem, gov)
        consistency = SelfConsistencyEngine(mem, verifier, gov)
        supervisor_v2 = MetaSupervisorV2(
            mem, supervisor_v1, reflection, reasoning, gov)
        explainability_v2 = ExplainabilityEngineV2(mem, explanation_v1)

        return {
            "memory": mem,
            "governance": gov,
            "reflection": reflection,
            "reasoning": reasoning,
            "planner_v2": planner_v2,
            "verifier": verifier,
            "consistency": consistency,
            "supervisor_v2": supervisor_v2,
            "explainability_v2": explainability_v2,
        }

    def test_full_pipeline_reasoning(self, tmp_path):
        """Full v12 pipeline: reason → reflect → verify → supervise → explain."""
        mods = self._make_all(tmp_path)
        trace = _sample_reasoning()

        # 1. Meta-reason
        meta = mods["reasoning"].meta_reason(trace)
        assert meta["type"] == "meta_reasoning"

        # 2. Reflect
        refl = mods["reflection"].reflect_on_reasoning(trace)
        assert refl["type"] == "reasoning_reflection"

        # 3. Verify
        verif = mods["verifier"].meta_verify_reasoning(trace)
        assert verif["type"] == "reasoning_verification"

        # 4. Supervise
        sup = mods["supervisor_v2"].supervise_reasoning(trace)
        assert sup["type"] == "reasoning_supervision"
        assert sup["approved"] is True

        # 5. Explain
        text = mods["explainability_v2"].explain_reasoning(trace)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_full_pipeline_planning(self, tmp_path):
        """Full v12 pipeline: evaluate → improve → verify → supervise → explain."""
        mods = self._make_all(tmp_path)
        plan = _sample_plan()

        # 1. Evaluate
        ev = mods["planner_v2"].evaluate_plan(plan)
        assert ev["type"] == "plan_evaluation"

        # 2. Improve
        imp = mods["planner_v2"].improve_plan(plan)
        improved = imp["improved_plan"]

        # 3. Verify
        verif = mods["verifier"].meta_verify(improved)
        assert verif["type"] == "plan_verification"

        # 4. Consistency
        cons = mods["consistency"].check_consistency(improved)
        assert cons["type"] == "plan_consistency"

        # 5. Supervise
        sup = mods["supervisor_v2"].supervise_planning(improved)
        assert sup["type"] == "planning_supervision"

        # 6. Explain
        text = mods["explainability_v2"].explain_plan(improved)
        assert isinstance(text, str)

    def test_all_modules_have_stats(self, tmp_path):
        mods = self._make_all(tmp_path)
        for name, mod in mods.items():
            if name in ("memory", "governance"):
                continue  # v11 modules
            assert hasattr(mod, "get_stats"), f"{name} missing get_stats()"
            stats = mod.get_stats()
            assert isinstance(stats, dict), f"{name}.get_stats() should return dict"

    def test_reflection_health_restart(self, tmp_path):
        mods = self._make_all(tmp_path)
        for name in ("reflection", "reasoning", "planner_v2"):
            mod = mods[name]
            health = mod.health_check()
            assert health["status"] == "ok", f"{name} health not ok"
            mod.restart()
            stats = mod.get_stats()
            assert all(v == 0 for v in stats.values()), f"{name} not reset after restart"

    def test_cross_module_consistency(self, tmp_path):
        """Test that modules correctly share MetaMemory."""
        mods = self._make_all(tmp_path)
        # Add something via memory (tag "strategy" so meta_get finds it)
        mods["memory"].meta_add({
            "category": "strategy",
            "key": "search_web",
            "value": {"feedback_type": "negative"},
            "source": "test",
            "tags": ["strategy"],
        })
        # Consistency engine should detect it
        plan = {
            "goal": "Test",
            "steps": [{"tool": "search_web", "description": "search"}],
        }
        result = mods["consistency"].check_consistency(plan)
        # Should detect known-failure tool
        assert any(
            i["type"] == "known_failure_tool"
            for i in result["inconsistencies"]
        )

    def test_supervisor_blocks_with_governance(self, tmp_path):
        """Test governance integration in MetaSupervisorV2."""
        mods = self._make_all(tmp_path)
        # Set forbidden action via supervisor rules
        mods["supervisor_v2"].set_meta_rules({"forbidden_actions": ["admin_delete"]})
        trace = {
            "steps": [{"text": "delete data", "action": "admin_delete"}],
            "conclusion": "deleted",
            "confidence": 0.9,
        }
        result = mods["supervisor_v2"].supervise_reasoning(trace)
        assert result["approved"] is False
        assert any(i["type"] == "forbidden_action" for i in result["issues"])

    def test_explainability_covers_all_types(self, tmp_path):
        """Test that ExplainabilityEngineV2 can explain all meta-decision types."""
        mods = self._make_all(tmp_path)
        types = [
            "reasoning_supervision",
            "planning_supervision",
            "plan_verification",
            "reasoning_verification",
        ]
        for t in types:
            text = mods["explainability_v2"].explain_meta_decision({
                "type": t,
                "approved": True,
                "issues": [],
            })
            assert isinstance(text, str)
            assert len(text) > 0
