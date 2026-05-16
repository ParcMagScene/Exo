"""
Tests unitaires — EXO v13 Auto-simulation, prévision, planification prospective
Couvre: SelfSimulationEngine, PredictionEngine, FuturePlanner,
MultiScenarioEngine, TemporalCoherenceEngine, AnticipationEngine,
ExplainabilityEngineV3, MetaSupervisorV3.
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


def _make_governance(mem):
    from auto_governance import AutoGovernance
    return AutoGovernance(mem)


def _sample_plan():
    return {
        "goal": "Allumer les lumières du salon",
        "steps": [
            {"id": 0, "tool": "ha_light", "description": "Allumer lumière salon",
             "depends_on": []},
            {"id": 1, "tool": "ha_scene", "description": "Activer scène salon",
             "depends_on": [0]},
        ],
    }


def _sample_step():
    return {"id": 0, "tool": "ha_light", "description": "Allumer lumière"}


def _sample_scenario():
    return {
        "context": "Soirée cinéma",
        "plans": [_sample_plan()],
    }


# ═════════════════════════════════════════════════════
#  TestSelfSimulationEngine
# ═════════════════════════════════════════════════════

class TestSelfSimulationEngine:

    def _make(self, tmp_path, governance=None):
        from self_simulation_engine import SelfSimulationEngine
        mem = _make_memory(tmp_path)
        gov = governance or _make_governance(mem)
        return SelfSimulationEngine(mem, gov), mem

    def test_simulate_plan_basic(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.simulate_plan(_sample_plan())
        assert "step_results" in result
        assert "risks" in result
        assert "success_probability" in result
        assert isinstance(result["governance_ok"], bool)

    def test_simulate_plan_empty(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.simulate_plan({"goal": "test", "steps": []})
        assert result["step_count"] == 0
        assert result["success_probability"] > 0

    def test_simulate_plan_dangerous_tool(self, tmp_path):
        eng, _ = self._make(tmp_path)
        plan = {
            "goal": "Test danger",
            "steps": [
                {"id": 0, "tool": "delete", "description": "Delete everything",
                 "depends_on": []},
            ],
        }
        result = eng.simulate_plan(plan)
        assert len(result["risks"]) > 0

    def test_simulate_step(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.simulate_step(_sample_step())
        assert result["type"] == "step_simulation"
        assert "simulated_success" in result

    def test_simulate_scenario(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.simulate_scenario(_sample_scenario())
        assert "plan_results" in result
        assert "overall_success_probability" in result

    def test_simulate_outcome(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.simulate_outcome(_sample_plan())
        assert "predicted_state" in result
        assert "consequences" in result
        assert "alternatives" in result

    def test_health_check(self, tmp_path):
        eng, _ = self._make(tmp_path)
        h = eng.health_check()
        assert h["status"] == "ok"

    def test_restart(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.simulate_plan(_sample_plan())
        eng.restart()
        stats = eng.get_stats()
        assert stats["plans_simulated"] == 0

    def test_get_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.simulate_plan(_sample_plan())
        stats = eng.get_stats()
        assert stats["plans_simulated"] >= 1

    def test_contradiction_detection(self, tmp_path):
        eng, _ = self._make(tmp_path)
        plan = {
            "goal": "contradictory",
            "steps": [
                {"id": 0, "tool": "ha_light", "description": "Allumer lumière salon",
                 "depends_on": [], "target": "salon"},
                {"id": 1, "tool": "ha_light", "description": "Éteindre lumière salon",
                 "depends_on": [], "target": "salon"},
            ],
        }
        result = eng.simulate_plan(plan)
        assert "side_effects" in result

    def test_simulate_plan_with_memory_context(self, tmp_path):
        eng, mem = self._make(tmp_path)
        mem.meta_add({"category": "last_action", "key": "last_action", "value": {"tool": "ha_light", "status": "success"}})
        result = eng.simulate_plan(_sample_plan())
        assert result["success_probability"] > 0


# ═════════════════════════════════════════════════════
#  TestPredictionEngine
# ═════════════════════════════════════════════════════

class TestPredictionEngine:

    def _make(self, tmp_path):
        from prediction_engine import PredictionEngine
        mem = _make_memory(tmp_path)
        gov = _make_governance(mem)
        return PredictionEngine(mem, gov), mem

    def test_predict_user_need(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.predict_user_need()
        assert "predictions" in result
        assert "type" in result
        assert result["type"] == "user_need_prediction"

    def test_predict_domotic_state(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.predict_domotic_state()
        assert "predictions" in result
        assert result["type"] == "domotic_prediction"

    def test_predict_network_state(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.predict_network_state()
        assert "predictions" in result
        assert result["type"] == "network_prediction"

    def test_predict_routine(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.predict_routine()
        assert "predictions" in result
        assert result["type"] == "routine_prediction"

    def test_predictions_have_confidence(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.predict_user_need()
        for pred in result["predictions"]:
            assert "confidence" in pred
            assert 0 <= pred["confidence"] <= 1

    def test_health_check(self, tmp_path):
        eng, _ = self._make(tmp_path)
        h = eng.health_check()
        assert h["status"] == "ok"

    def test_restart(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.predict_user_need()
        eng.restart()
        stats = eng.get_stats()
        assert stats["user_need_predictions"] == 0

    def test_get_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.predict_user_need()
        eng.predict_domotic_state()
        stats = eng.get_stats()
        assert stats["user_need_predictions"] >= 1
        assert stats["domotic_predictions"] >= 1

    def test_predict_with_memory_entries(self, tmp_path):
        eng, mem = self._make(tmp_path)
        mem.meta_add({"category": "preference", "key": "light_auto", "value": True})
        result = eng.predict_user_need()
        assert isinstance(result["predictions"], list)

    def test_predict_domotic_includes_devices(self, tmp_path):
        eng, mem = self._make(tmp_path)
        mem.meta_add({"category": "device", "key": "salon_light", "value": "on"})
        result = eng.predict_domotic_state()
        assert result["prediction_count"] >= 0


# ═════════════════════════════════════════════════════
#  TestFuturePlanner
# ═════════════════════════════════════════════════════

class TestFuturePlanner:

    def _make(self, tmp_path):
        from future_planner import FuturePlanner
        mem = _make_memory(tmp_path)
        gov = _make_governance(mem)
        return FuturePlanner(mem, gov), mem

    def test_plan_future_action(self, tmp_path):
        eng, _ = self._make(tmp_path)
        action = {"tool": "ha_light", "description": "Allumer lumière"}
        future_time = time.time() + 3600
        result = eng.plan_future_action(action, future_time)
        assert result["valid"] is True
        assert result["id"].startswith("fp_")

    def test_plan_future_action_past_time(self, tmp_path):
        eng, _ = self._make(tmp_path)
        action = {"tool": "ha_light", "description": "Test"}
        past_time = time.time() - 3600
        result = eng.plan_future_action(action, past_time)
        assert result["valid"] is False

    def test_plan_future_empty_action(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.plan_future_action({}, time.time() + 3600)
        assert result["valid"] is False

    def test_plan_conditional_action(self, tmp_path):
        eng, _ = self._make(tmp_path)
        action = {"tool": "ha_light", "description": "Allumer si pluie"}
        condition = {"type": "weather", "expression": "rain"}
        result = eng.plan_conditional_action(action, condition)
        assert result["valid"] is True
        assert result["id"].startswith("fc_")

    def test_plan_conditional_missing_condition(self, tmp_path):
        eng, _ = self._make(tmp_path)
        action = {"tool": "ha_light", "description": "Test"}
        result = eng.plan_conditional_action(action, {})
        assert result["valid"] is False

    def test_plan_recurrent_action(self, tmp_path):
        eng, _ = self._make(tmp_path)
        action = {"tool": "ha_light", "description": "Allumer chaque matin"}
        schedule = {"frequency": "daily", "time": "08:00"}
        result = eng.plan_recurrent_action(action, schedule)
        assert result["valid"] is True
        assert result["id"].startswith("fr_")

    def test_plan_recurrent_invalid_frequency(self, tmp_path):
        eng, _ = self._make(tmp_path)
        action = {"tool": "ha_light", "description": "Test"}
        schedule = {"frequency": "invalid_freq", "time": "08:00"}
        result = eng.plan_recurrent_action(action, schedule)
        assert result["valid"] is False

    def test_get_pending_plans(self, tmp_path):
        eng, _ = self._make(tmp_path)
        action = {"tool": "ha_light", "description": "Test"}
        eng.plan_future_action(action, time.time() + 3600)
        eng.plan_future_action(action, time.time() + 7200)
        pending = eng.get_pending_plans()
        assert len(pending) == 2

    def test_cancel_plan(self, tmp_path):
        eng, _ = self._make(tmp_path)
        action = {"tool": "ha_light", "description": "Test"}
        result = eng.plan_future_action(action, time.time() + 3600)
        plan_id = result["id"]
        assert eng.cancel_plan(plan_id) is True
        assert len(eng.get_pending_plans()) == 0

    def test_cancel_nonexistent_plan(self, tmp_path):
        eng, _ = self._make(tmp_path)
        assert eng.cancel_plan("fp_nonexistent") is False

    def test_health_check(self, tmp_path):
        eng, _ = self._make(tmp_path)
        h = eng.health_check()
        assert h["status"] == "ok"

    def test_get_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        action = {"tool": "ha_light", "description": "Test"}
        eng.plan_future_action(action, time.time() + 3600)
        stats = eng.get_stats()
        assert stats["future_plans"] >= 1


# ═════════════════════════════════════════════════════
#  TestMultiScenarioEngine
# ═════════════════════════════════════════════════════

class TestMultiScenarioEngine:

    def _make(self, tmp_path, with_simulation=False):
        from multi_scenario_engine import MultiScenarioEngine
        mem = _make_memory(tmp_path)
        gov = _make_governance(mem)
        sim = None
        if with_simulation:
            from self_simulation_engine import SelfSimulationEngine
            sim = SelfSimulationEngine(mem, gov)
        return MultiScenarioEngine(mem, sim, gov), mem

    def test_generate_future_variants(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.generate_future_variants(_sample_plan())
        assert "variants" in result
        assert len(result["variants"]) >= 2

    def test_compare_futures(self, tmp_path):
        eng, _ = self._make(tmp_path)
        variants = eng.generate_future_variants(_sample_plan())
        result = eng.compare_futures(variants["variants"])
        assert "ranking" in result
        assert "best_index" in result

    def test_select_best_future(self, tmp_path):
        eng, _ = self._make(tmp_path)
        variants = eng.generate_future_variants(_sample_plan())
        result = eng.select_best_future(variants["variants"])
        assert "selected" in result
        assert "reason" in result

    def test_compare_empty_futures(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.compare_futures([])
        assert result["ranking"] == []

    def test_select_single_future(self, tmp_path):
        eng, _ = self._make(tmp_path)
        future = {"name": "solo", "steps": [_sample_step()]}
        result = eng.select_best_future([future])
        assert result["selected"] is not None

    def test_with_simulation_engine(self, tmp_path):
        eng, _ = self._make(tmp_path, with_simulation=True)
        result = eng.generate_future_variants(_sample_plan())
        assert len(result["variants"]) >= 2

    def test_get_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.generate_future_variants(_sample_plan())
        stats = eng.get_stats()
        total = sum(stats.values())
        assert total >= 1

    def test_compare_futures_ranking_order(self, tmp_path):
        eng, _ = self._make(tmp_path)
        futures = [
            {"name": "plan_a", "steps": [], "goal": "A"},
            {"name": "plan_b", "steps": [_sample_step()], "goal": "B"},
        ]
        result = eng.compare_futures(futures)
        assert len(result["ranking"]) == 2

    def test_generate_variants_preserves_goal(self, tmp_path):
        eng, _ = self._make(tmp_path)
        plan = _sample_plan()
        result = eng.generate_future_variants(plan)
        for v in result["variants"]:
            assert "goal" in v or "name" in v


# ═════════════════════════════════════════════════════
#  TestTemporalCoherenceEngine
# ═════════════════════════════════════════════════════

class TestTemporalCoherenceEngine:

    def _make(self, tmp_path, with_planner=False):
        from temporal_coherence_engine import TemporalCoherenceEngine
        mem = _make_memory(tmp_path)
        fp = None
        if with_planner:
            from future_planner import FuturePlanner
            gov = _make_governance(mem)
            fp = FuturePlanner(mem, gov)
        return TemporalCoherenceEngine(mem, fp), mem

    def test_no_conflicts_empty(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.check_temporal_conflicts([])
        assert result["coherent"] is True
        assert result["conflicts"] == []

    def test_no_conflicts_distinct_times(self, tmp_path):
        eng, _ = self._make(tmp_path)
        now = time.time() + 3600
        plans = [
            {"plan_id": "p1", "time_target": now, "tool": "ha_light",
             "target": "salon"},
            {"plan_id": "p2", "time_target": now + 300, "tool": "ha_light",
             "target": "chambre"},
        ]
        result = eng.check_temporal_conflicts(plans)
        assert result["coherent"] is True

    def test_detect_time_overlap(self, tmp_path):
        eng, _ = self._make(tmp_path)
        now = time.time() + 3600
        plans = [
            {"plan_id": "p1", "time_target": now, "tool": "ha_light",
             "target": "salon"},
            {"plan_id": "p2", "time_target": now + 10, "tool": "ha_light",
             "target": "salon"},
        ]
        result = eng.check_temporal_conflicts(plans)
        has_overlap = any(c["type"] in ("time_overlap", "action_conflict")
                         for c in result.get("conflicts", []))
        assert has_overlap or len(result.get("warnings", [])) > 0

    def test_detect_dependency_violation(self, tmp_path):
        eng, _ = self._make(tmp_path)
        now = time.time() + 3600
        plans = [
            {"id": "p1", "time_target": now + 600,
             "tool": "ha_light", "target": "salon"},
            {"id": "p2", "time_target": now,
             "tool": "ha_scene", "target": "salon",
             "depends_on": ["p1"]},
        ]
        result = eng.check_temporal_conflicts(plans)
        has_dep = any(c["type"] == "dependency_violation"
                      for c in result.get("conflicts", []))
        assert has_dep

    def test_detect_past_plan(self, tmp_path):
        eng, _ = self._make(tmp_path)
        plans = [
            {"plan_id": "p_old", "time_target": time.time() - 3600,
             "tool": "ha_light", "target": "salon"},
        ]
        result = eng.check_temporal_conflicts(plans)
        has_warn = any("past" in str(w).lower()
                       for w in result.get("warnings", []))
        assert has_warn

    def test_enforce_temporal_coherence_no_planner(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.enforce_temporal_coherence()
        assert "actions" in result

    def test_enforce_temporal_coherence_with_planner(self, tmp_path):
        eng, _ = self._make(tmp_path, with_planner=True)
        result = eng.enforce_temporal_coherence()
        assert "actions" in result
        assert "correction_count" in result

    def test_get_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.check_temporal_conflicts([])
        stats = eng.get_stats()
        assert stats["conflict_checks"] >= 1


# ═════════════════════════════════════════════════════
#  TestAnticipationEngine
# ═════════════════════════════════════════════════════

class TestAnticipationEngine:

    def _make(self, tmp_path, with_prediction=False):
        from anticipation_engine import AnticipationEngine
        mem = _make_memory(tmp_path)
        gov = _make_governance(mem)
        pred = None
        if with_prediction:
            from prediction_engine import PredictionEngine
            pred = PredictionEngine(mem, gov)
        return AnticipationEngine(mem, pred, gov), mem

    def test_anticipate_need(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.anticipate_need()
        assert "needs" in result
        assert isinstance(result["needs"], list)

    def test_anticipate_need_with_prediction(self, tmp_path):
        eng, _ = self._make(tmp_path, with_prediction=True)
        result = eng.anticipate_need()
        assert "needs" in result

    def test_propose_anticipation(self, tmp_path):
        eng, _ = self._make(tmp_path, with_prediction=True)
        result = eng.propose_anticipation()
        assert "proposals" in result
        for prop in result["proposals"]:
            assert prop.get("requires_approval") is True

    def test_proposals_require_approval(self, tmp_path):
        eng, _ = self._make(tmp_path, with_prediction=True)
        result = eng.propose_anticipation()
        for prop in result["proposals"]:
            assert prop["requires_approval"] is True

    def test_prepare_future_context(self, tmp_path):
        eng, _ = self._make(tmp_path, with_prediction=True)
        result = eng.prepare_future_context()
        assert "items" in result

    def test_prepare_future_context_no_prediction(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.prepare_future_context()
        assert "items" in result

    def test_get_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.anticipate_need()
        stats = eng.get_stats()
        assert stats["needs_anticipated"] >= 1

    def test_anticipation_with_memory(self, tmp_path):
        eng, mem = self._make(tmp_path, with_prediction=True)
        mem.meta_add({"category": "preference", "key": "auto_light", "value": True})
        mem.meta_add({"category": "routine", "key": "morning", "value": {"actions": ["light_on"]}})
        result = eng.anticipate_need()
        assert isinstance(result["needs"], list)


# ═════════════════════════════════════════════════════
#  TestExplainabilityEngineV3
# ═════════════════════════════════════════════════════

class TestExplainabilityEngineV3:

    def _make(self, tmp_path):
        from explainability_engine_v3 import ExplainabilityEngineV3
        mem = _make_memory(tmp_path)
        return ExplainabilityEngineV3(mem), mem

    def test_explain_simulation_plan(self, tmp_path):
        eng, _ = self._make(tmp_path)
        sim = {
            "type": "plan_simulation",
            "step_count": 3,
            "risks": [{"type": "dangerous_tool"}],
            "success_probability": 0.75,
            "governance_ok": True,
        }
        text = eng.explain_simulation(sim)
        assert isinstance(text, str)
        assert len(text) > 10

    def test_explain_simulation_outcome(self, tmp_path):
        eng, _ = self._make(tmp_path)
        sim = {
            "type": "outcome_simulation",
            "predicted_state": {"lights": "on"},
            "consequences": [{"severity": "low", "description": "éclairage actif"}],
            "success_probability": 0.8,
        }
        text = eng.explain_simulation(sim)
        assert isinstance(text, str)

    def test_explain_prediction_user_need(self, tmp_path):
        eng, _ = self._make(tmp_path)
        pred = {
            "type": "user_need_prediction",
            "predictions": [
                {"need": "light", "confidence": 0.8},
                {"need": "music", "confidence": 0.5},
            ],
        }
        text = eng.explain_prediction(pred)
        assert isinstance(text, str)
        assert len(text) > 10

    def test_explain_prediction_domotic(self, tmp_path):
        eng, _ = self._make(tmp_path)
        pred = {
            "type": "domotic_prediction",
            "predictions": [
                {"device": "salon_light", "predicted_state": "on",
                 "confidence": 0.9},
            ],
        }
        text = eng.explain_prediction(pred)
        assert isinstance(text, str)

    def test_explain_future_selection(self, tmp_path):
        eng, _ = self._make(tmp_path)
        future = {
            "type": "future_selection",
            "selected": {"name": "plan_optimal"},
            "reason": "Meilleur score",
        }
        text = eng.explain_future(future)
        assert isinstance(text, str)

    def test_explain_future_comparison(self, tmp_path):
        eng, _ = self._make(tmp_path)
        future = {
            "type": "future_comparison",
            "ranking": [
                {"name": "plan_a", "score": 0.9},
                {"name": "plan_b", "score": 0.7},
            ],
        }
        text = eng.explain_future(future)
        assert isinstance(text, str)

    def test_explain_future_variants(self, tmp_path):
        eng, _ = self._make(tmp_path)
        future = {
            "type": "future_variants",
            "variants": [
                {"name": "original"},
                {"name": "optimisé"},
            ],
        }
        text = eng.explain_future(future)
        assert isinstance(text, str)

    def test_explanation_log(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.explain_simulation({"type": "plan_simulation", "step_count": 1,
                                "risks": [], "success_probability": 0.9,
                                "governance_ok": True})
        eng.explain_prediction({"type": "user_need_prediction", "predictions": []})
        log = eng.get_explanation_log(10)
        assert len(log) == 2

    def test_get_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.explain_simulation({"type": "plan_simulation", "step_count": 0,
                                "risks": [], "success_probability": 1.0,
                                "governance_ok": True})
        stats = eng.get_stats()
        assert stats["simulation_explanations"] >= 1


# ═════════════════════════════════════════════════════
#  TestMetaSupervisorV3
# ═════════════════════════════════════════════════════

class TestMetaSupervisorV3:

    def _make(self, tmp_path, with_simulation=False):
        from meta_supervisor_v3 import MetaSupervisorV3
        mem = _make_memory(tmp_path)
        gov = _make_governance(mem)
        sim = None
        if with_simulation:
            from self_simulation_engine import SelfSimulationEngine
            sim = SelfSimulationEngine(mem, gov)
        return MetaSupervisorV3(mem, None, sim, gov), mem

    def test_supervise_simulation_approved(self, tmp_path):
        eng, _ = self._make(tmp_path)
        sim = {
            "type": "plan_simulation",
            "step_count": 3,
            "risks": [],
            "success_probability": 0.85,
            "governance_ok": True,
        }
        result = eng.supervise_simulation(sim)
        assert result["approved"] is True
        assert result["issues"] == []

    def test_supervise_simulation_too_many_steps(self, tmp_path):
        eng, _ = self._make(tmp_path)
        sim = {
            "type": "plan_simulation",
            "step_count": 200,
            "risks": [],
            "success_probability": 0.80,
            "governance_ok": True,
        }
        result = eng.supervise_simulation(sim)
        assert result["approved"] is False
        assert any(i["type"] == "too_many_steps" for i in result["issues"])

    def test_supervise_simulation_low_success(self, tmp_path):
        eng, _ = self._make(tmp_path)
        sim = {
            "type": "plan_simulation",
            "step_count": 3,
            "risks": [],
            "success_probability": 0.05,
            "governance_ok": True,
        }
        result = eng.supervise_simulation(sim)
        assert result["approved"] is False
        assert any(i["type"] == "low_success_probability"
                   for i in result["issues"])

    def test_supervise_simulation_governance_violation(self, tmp_path):
        eng, _ = self._make(tmp_path)
        sim = {
            "type": "plan_simulation",
            "step_count": 2,
            "risks": [],
            "success_probability": 0.9,
            "governance_ok": False,
        }
        result = eng.supervise_simulation(sim)
        assert result["approved"] is False
        assert any(i["type"] == "governance_violation"
                   for i in result["issues"])

    def test_supervise_simulation_high_risk(self, tmp_path):
        eng, _ = self._make(tmp_path)
        sim = {
            "type": "plan_simulation",
            "step_count": 2,
            "risks": [{"type": "dangerous_tool"}, {"type": "side_effect"}],
            "success_probability": 0.7,
            "governance_ok": True,
        }
        result = eng.supervise_simulation(sim)
        assert result["approved"] is False

    def test_supervise_simulation_dangerous(self, tmp_path):
        eng, _ = self._make(tmp_path)
        sim = {
            "type": "plan_simulation",
            "step_count": 2,
            "risks": [{"type": "dangerous_tool"}, {"type": "governance_blocked"}],
            "success_probability": 0.5,
            "governance_ok": True,
        }
        result = eng.supervise_simulation(sim)
        assert any(i["type"] == "dangerous_simulation" for i in result["issues"])

    def test_supervise_prediction_approved(self, tmp_path):
        eng, _ = self._make(tmp_path)
        pred = {
            "type": "user_need",
            "predictions": [
                {"need": "light", "confidence": 0.8},
                {"need": "music", "confidence": 0.7},
            ],
        }
        result = eng.supervise_prediction(pred)
        assert result["approved"] is True

    def test_supervise_prediction_too_many(self, tmp_path):
        eng, _ = self._make(tmp_path)
        preds = [{"need": f"n_{i}", "confidence": 0.5}
                 for i in range(60)]
        pred = {
            "type": "user_need",
            "predictions": preds,
            "prediction_count": 60,
        }
        result = eng.supervise_prediction(pred)
        assert result["approved"] is False
        assert any(i["type"] == "too_many_predictions"
                   for i in result["issues"])

    def test_supervise_prediction_high_confidence_gap(self, tmp_path):
        eng, _ = self._make(tmp_path)
        pred = {
            "type": "user_need",
            "predictions": [
                {"need": "a", "confidence": 1.0},
                {"need": "b", "confidence": 0.1},
            ],
        }
        result = eng.supervise_prediction(pred)
        has_gap = any(i["type"] == "high_confidence_gap"
                      for i in result["issues"])
        assert has_gap

    def test_supervise_prediction_contradictory(self, tmp_path):
        eng, _ = self._make(tmp_path)
        pred = {
            "type": "domotic",
            "predictions": [
                {"device": "light", "predicted_state": "on", "confidence": 0.8},
                {"device": "light", "predicted_state": "off", "confidence": 0.7},
            ],
        }
        result = eng.supervise_prediction(pred)
        has_contradiction = any(i["type"] == "contradictory_prediction"
                                for i in result["issues"])
        assert has_contradiction

    def test_enforce_future_rules(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.enforce_future_rules()
        assert "actions" in result
        assert "rules" in result

    def test_set_future_rules(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.set_future_rules({"max_simulation_steps": 50})
        sim = {
            "type": "plan_simulation",
            "step_count": 60,
            "risks": [],
            "success_probability": 0.9,
            "governance_ok": True,
        }
        result = eng.supervise_simulation(sim)
        assert result["approved"] is False

    def test_get_alerts(self, tmp_path):
        eng, _ = self._make(tmp_path)
        # Trigger a blocked simulation to generate alert
        sim = {
            "step_count": 200,
            "risks": [],
            "success_probability": 0.01,
            "governance_ok": False,
        }
        eng.supervise_simulation(sim)
        alerts = eng.get_alerts()
        assert len(alerts) >= 1

    def test_get_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.supervise_simulation({
            "step_count": 2, "risks": [],
            "success_probability": 0.9, "governance_ok": True,
        })
        eng.supervise_prediction({
            "type": "user_need",
            "predictions": [{"need": "x", "confidence": 0.8}],
        })
        stats = eng.get_stats()
        assert stats["simulations_supervised"] >= 1
        assert stats["predictions_supervised"] >= 1

    def test_forbidden_tools_rule(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.set_future_rules({"forbidden_tools_in_simulation": ["ha_delete"]})
        sim = {
            "step_count": 1,
            "risks": [],
            "success_probability": 0.9,
            "governance_ok": True,
            "step_results": [{"tool": "ha_delete", "step_index": 0}],
        }
        result = eng.supervise_simulation(sim)
        assert result["approved"] is False
        assert any(i["type"] == "forbidden_tool" for i in result["issues"])


# ═════════════════════════════════════════════════════
#  TestV13Integration
# ═════════════════════════════════════════════════════

class TestV13Integration:
    """Tests d'intégration entre modules v13."""

    def _make_all(self, tmp_path):
        from self_simulation_engine import SelfSimulationEngine
        from prediction_engine import PredictionEngine
        from future_planner import FuturePlanner
        from multi_scenario_engine import MultiScenarioEngine
        from temporal_coherence_engine import TemporalCoherenceEngine
        from anticipation_engine import AnticipationEngine
        from explainability_engine_v3 import ExplainabilityEngineV3
        from meta_supervisor_v3 import MetaSupervisorV3

        mem = _make_memory(tmp_path)
        gov = _make_governance(mem)

        sim = SelfSimulationEngine(mem, gov)
        pred = PredictionEngine(mem, gov)
        fp = FuturePlanner(mem, gov)
        multi = MultiScenarioEngine(mem, sim, gov)
        temporal = TemporalCoherenceEngine(mem, fp)
        antic = AnticipationEngine(mem, pred, gov)
        expl = ExplainabilityEngineV3(mem)
        supv = MetaSupervisorV3(mem, None, sim, gov)

        return {
            "simulation": sim,
            "prediction": pred,
            "future_planner": fp,
            "multi_scenario": multi,
            "temporal": temporal,
            "anticipation": antic,
            "explainability_v3": expl,
            "supervisor_v3": supv,
            "memory": mem,
        }

    def test_simulate_then_supervise(self, tmp_path):
        m = self._make_all(tmp_path)
        sim_result = m["simulation"].simulate_plan(_sample_plan())
        sup_result = m["supervisor_v3"].supervise_simulation(sim_result)
        assert "approved" in sup_result

    def test_simulate_then_explain(self, tmp_path):
        m = self._make_all(tmp_path)
        sim_result = m["simulation"].simulate_plan(_sample_plan())
        text = m["explainability_v3"].explain_simulation(sim_result)
        assert len(text) > 0

    def test_predict_then_supervise(self, tmp_path):
        m = self._make_all(tmp_path)
        pred_result = m["prediction"].predict_user_need()
        sup_result = m["supervisor_v3"].supervise_prediction(pred_result)
        assert "approved" in sup_result

    def test_predict_then_explain(self, tmp_path):
        m = self._make_all(tmp_path)
        pred_result = m["prediction"].predict_user_need()
        text = m["explainability_v3"].explain_prediction(pred_result)
        assert len(text) > 0

    def test_plan_then_check_temporal(self, tmp_path):
        m = self._make_all(tmp_path)
        fp = m["future_planner"]
        action = {"tool": "ha_light", "description": "Test"}
        r1 = fp.plan_future_action(action, time.time() + 3600)
        r2 = fp.plan_future_action(action, time.time() + 3601)
        pending = fp.get_pending_plans()
        result = m["temporal"].check_temporal_conflicts(pending)
        assert "coherent" in result

    def test_generate_variants_then_select(self, tmp_path):
        m = self._make_all(tmp_path)
        variants = m["multi_scenario"].generate_future_variants(_sample_plan())
        selected = m["multi_scenario"].select_best_future(
            variants["variants"])
        assert selected["selected"] is not None

    def test_anticipate_then_propose(self, tmp_path):
        m = self._make_all(tmp_path)
        needs = m["anticipation"].anticipate_need()
        proposals = m["anticipation"].propose_anticipation()
        assert isinstance(needs["needs"], list)
        assert isinstance(proposals["proposals"], list)

    def test_full_pipeline_simulate_supervise_explain(self, tmp_path):
        m = self._make_all(tmp_path)
        plan = _sample_plan()

        # 1. Simulate
        sim = m["simulation"].simulate_plan(plan)
        # 2. Supervise
        sup = m["supervisor_v3"].supervise_simulation(sim)
        # 3. Explain
        expl = m["explainability_v3"].explain_simulation(sim)

        assert sup["approved"] is True
        assert len(expl) > 0

    def test_all_modules_have_get_stats(self, tmp_path):
        m = self._make_all(tmp_path)
        for name, mod in m.items():
            if name == "memory":
                continue
            assert hasattr(mod, "get_stats"), f"{name} missing get_stats()"
            stats = mod.get_stats()
            assert isinstance(stats, dict), f"{name}.get_stats() not dict"

    def test_enforce_future_rules_integration(self, tmp_path):
        m = self._make_all(tmp_path)
        result = m["supervisor_v3"].enforce_future_rules()
        assert "actions" in result
        assert "rules" in result
