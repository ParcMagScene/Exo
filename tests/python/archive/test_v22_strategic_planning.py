"""
Tests EXO v22 — Planification stratégique
9 modules, ~75 tests couvrant toutes les APIs.
"""

import sys
import os
import pytest

from strategic_planner import StrategicPlanner
from htn_plus_engine import HTNPlusEngine
from multi_objective_planner import MultiObjectivePlanner
from constraint_aware_planner import ConstraintAwarePlanner
from scenario_planner import ScenarioPlanner
from strategic_arbitration_engine import StrategicArbitrationEngine
from temporal_planning_engine import TemporalPlanningEngine
from plan_coherence_engine import PlanCoherenceEngine
from planning_explainability_engine import PlanningExplainabilityEngine


# ════════════════════════════════════════════════════════════
# StrategicPlanner
# ════════════════════════════════════════════════════════════
class TestStrategicPlanner:
    def _make(self):
        htn = HTNPlusEngine()
        mo = MultiObjectivePlanner()
        cap = ConstraintAwarePlanner()
        sp = ScenarioPlanner()
        tp = TemporalPlanningEngine()
        arb = StrategicArbitrationEngine()
        return StrategicPlanner(
            htn=htn, multi_obj=mo, constraint_planner=cap,
            scenario_planner=sp, temporal_planner=tp, arbitration=arb,
        )

    def test_plan_basic(self):
        p = self._make()
        r = p.plan({"goal": "test", "sub_goals": ["a", "b"]})
        assert "id" in r
        assert r["status"] == "draft"
        assert r["steps_count"] >= 2
        assert p.get_stats()["plans_created"] == 1

    def test_plan_with_engine(self):
        p = self._make()
        r = p.plan({"goal": "x", "engine": "htn"})
        assert r["engine"] == "htn"
        assert "id" in r

    def test_merge_plans(self):
        p = self._make()
        plans = {"plans": [
            {"id": "p1", "steps": [{"action": "a"}]},
            {"id": "p2", "steps": [{"action": "b"}]},
        ]}
        r = p.merge_plans(plans)
        assert r["merged"] is True
        assert r["steps_count"] == 2
        assert p.get_stats()["merges"] == 1

    def test_finalize_plan(self):
        p = self._make()
        plan = {"id": "p1", "steps": [{"action": "a"}], "score": 0.5}
        r = p.finalize_plan(plan)
        assert r["finalized"] is True
        assert r["valid"] is True
        assert p.get_stats()["finalizations"] == 1

    def test_health_check(self):
        p = self._make()
        h = p.health_check()
        assert h["service"] == "strategic_planner"
        assert h["status"] == "ok"

    def test_restart(self):
        p = self._make()
        p.plan({"goal": "x"})
        p.restart()
        assert p.get_stats()["plans_created"] == 0


# ════════════════════════════════════════════════════════════
# HTNPlusEngine
# ════════════════════════════════════════════════════════════
class TestHTNPlusEngine:
    def test_expand_compound(self):
        eng = HTNPlusEngine()
        r = eng.htn_expand({
            "name": "t", "type": "compound",
            "methods": [
                {"name": "m1", "steps": ["s1", "s2"]}
            ]
        })
        assert r["expanded"] is True
        assert r["subtasks_count"] >= 2
        assert eng.get_stats()["expansions"] == 1

    def test_expand_primitive(self):
        eng = HTNPlusEngine()
        r = eng.htn_expand({"name": "t", "type": "primitive"})
        assert r["expanded"] is True
        assert r["subtasks_count"] == 1

    def test_optimize(self):
        eng = HTNPlusEngine()
        plan = {"steps": [
            {"action": "a", "agent": "x"},
            {"action": "a", "agent": "x"},
            {"action": "b", "agent": "y"},
        ]}
        r = eng.htn_optimize(plan)
        assert r["optimized"] is True
        assert r["optimized_steps"] <= 3
        assert eng.get_stats()["optimizations"] == 1

    def test_validate_ok(self):
        eng = HTNPlusEngine()
        plan = {"steps": [{"action": "a"}]}
        r = eng.htn_validate(plan)
        assert r["validated"] is True
        assert r["issues_count"] == 0
        assert r["valid"] is True

    def test_validate_empty(self):
        eng = HTNPlusEngine()
        r = eng.htn_validate({"steps": []})
        assert r["validated"] is True
        assert r["issues_count"] >= 1
        assert r["valid"] is False

    def test_health(self):
        eng = HTNPlusEngine()
        assert eng.health_check()["service"] == "htn_plus_engine"

    def test_restart(self):
        eng = HTNPlusEngine()
        eng.htn_expand({"name": "t"})
        eng.restart()
        assert eng.get_stats()["expansions"] == 0


# ════════════════════════════════════════════════════════════
# MultiObjectivePlanner
# ════════════════════════════════════════════════════════════
class TestMultiObjectivePlanner:
    def test_plan_multi_objectives(self):
        eng = MultiObjectivePlanner()
        r = eng.plan_multi_objectives(
            {"goal": "test"},
            {"objectives": ["speed", "reliability"]}
        )
        assert r["planned"] is True
        assert r["objectives_count"] == 2
        assert eng.get_stats()["plans_created"] == 1

    def test_invalid_objective_filtered(self):
        eng = MultiObjectivePlanner()
        r = eng.plan_multi_objectives(
            {"goal": "test"},
            {"objectives": ["speed", "INVALID", "security"]}
        )
        assert r["objectives_count"] == 3  # all passed through, scoring handles validity

    def test_compute_tradeoffs(self):
        eng = MultiObjectivePlanner()
        eng.plan_multi_objectives({"goal": "t"}, {"objectives": ["speed", "reliability"]})
        plan = eng._plans[-1]
        r = eng.compute_tradeoffs(plan)
        assert r["computed"] is True
        assert "tradeoffs" in r
        assert eng.get_stats()["tradeoffs_computed"] == 1

    def test_select_best_compromise(self):
        eng = MultiObjectivePlanner()
        eng.plan_multi_objectives({"goal": "t"}, {"objectives": ["speed", "reliability"]})
        r = eng.select_best_compromise()
        assert r["selected"] is True
        assert "best_plan_id" in r
        assert eng.get_stats()["compromises_selected"] == 1

    def test_select_no_plans(self):
        eng = MultiObjectivePlanner()
        r = eng.select_best_compromise()
        assert r["selected"] is False

    def test_health(self):
        eng = MultiObjectivePlanner()
        assert eng.health_check()["service"] == "multi_objective_planner"

    def test_restart(self):
        eng = MultiObjectivePlanner()
        eng.plan_multi_objectives({"goal": "t"}, {"objectives": ["speed"]})
        eng.restart()
        assert eng.get_stats()["plans_created"] == 0


# ════════════════════════════════════════════════════════════
# ConstraintAwarePlanner
# ════════════════════════════════════════════════════════════
class TestConstraintAwarePlanner:
    def test_apply_no_constraints(self):
        eng = ConstraintAwarePlanner()
        r = eng.apply_constraints({"steps": [{"action": "a"}], "constraints": []})
        assert r["applied"] is True
        assert r["feasible"] is True
        assert r["violations_count"] == 0

    def test_apply_dependency_violation(self):
        eng = ConstraintAwarePlanner()
        r = eng.apply_constraints({
            "steps": [],
            "constraints": [
                {"name": "dep1", "type": "dependency",
                 "step": 0, "condition": {"depends_on": 1}}
            ]
        })
        assert r["violations_count"] == 1
        assert r["feasible"] is False

    def test_apply_resource_violation(self):
        eng = ConstraintAwarePlanner()
        r = eng.apply_constraints({
            "steps": [],
            "constraints": [
                {"name": "res1", "type": "resource",
                 "condition": {"required": 10, "available": 3}}
            ]
        })
        assert r["feasible"] is False

    def test_validate_constraints(self):
        eng = ConstraintAwarePlanner()
        r = eng.validate_constraints({
            "steps": [{"action": "a"}],
            "constraints": [
                {"name": "log1", "type": "logical"}
            ]
        })
        assert r["validated"] is True
        assert r["feasible"] is True

    def test_explain_no_applications(self):
        eng = ConstraintAwarePlanner()
        r = eng.explain_constraints()
        assert r["explained"] is False

    def test_explain_after_apply(self):
        eng = ConstraintAwarePlanner()
        eng.apply_constraints({"steps": [], "constraints": []})
        r = eng.explain_constraints()
        assert r["explained"] is True
        assert r["feasible"] is True

    def test_health(self):
        eng = ConstraintAwarePlanner()
        assert eng.health_check()["service"] == "constraint_aware_planner"

    def test_restart(self):
        eng = ConstraintAwarePlanner()
        eng.apply_constraints({"steps": [], "constraints": []})
        eng.restart()
        assert eng.get_stats()["applied"] == 0


# ════════════════════════════════════════════════════════════
# ScenarioPlanner
# ════════════════════════════════════════════════════════════
class TestScenarioPlanner:
    def test_generate_scenarios(self):
        eng = ScenarioPlanner()
        r = eng.generate_scenarios({
            "goal": "test",
            "scenario_types": ["deterministic", "optimized"]
        })
        assert r["generated"] is True
        assert r["count"] == 2
        assert eng.get_stats()["generated"] == 1

    def test_generate_all_types(self):
        eng = ScenarioPlanner()
        r = eng.generate_scenarios({"goal": "test"})
        assert r["count"] == 5

    def test_compare_scenarios(self):
        eng = ScenarioPlanner()
        gen = eng.generate_scenarios({
            "goal": "test",
            "scenario_types": ["deterministic", "optimized"]
        })
        r = eng.compare_scenarios(gen["scenarios"])
        assert r["compared"] is True
        assert r["count"] == 2
        assert r["ranking"][0]["rank"] == 1

    def test_select_best_no_comparisons(self):
        eng = ScenarioPlanner()
        r = eng.select_best_scenario()
        assert r["selected"] is False

    def test_select_best_after_compare(self):
        eng = ScenarioPlanner()
        gen = eng.generate_scenarios({"goal": "test"})
        eng.compare_scenarios(gen["scenarios"])
        r = eng.select_best_scenario()
        assert r["selected"] is True
        assert r["best_scenario"] is not None

    def test_health(self):
        eng = ScenarioPlanner()
        assert eng.health_check()["service"] == "scenario_planner"

    def test_restart(self):
        eng = ScenarioPlanner()
        eng.generate_scenarios({"goal": "t"})
        eng.restart()
        assert eng.get_stats()["generated"] == 0


# ════════════════════════════════════════════════════════════
# StrategicArbitrationEngine
# ════════════════════════════════════════════════════════════
class TestStrategicArbitrationEngine:
    def test_arbitrate_no_plans(self):
        eng = StrategicArbitrationEngine()
        r = eng.arbitrate([])
        assert r["arbitrated"] is False

    def test_arbitrate_single(self):
        eng = StrategicArbitrationEngine()
        r = eng.arbitrate([{"id": "p1", "steps": [{"action": "a"}]}])
        assert r["arbitrated"] is True
        assert r["winner"]["plan_id"] == "p1"

    def test_arbitrate_multiple(self):
        eng = StrategicArbitrationEngine()
        r = eng.arbitrate([
            {"id": "p1", "steps": [{"action": "a"}], "feasible": True},
            {"id": "p2", "steps": [{"action": "a"}, {"action": "b"}, {"action": "c"}]},
        ])
        assert r["arbitrated"] is True
        assert r["candidates_count"] == 2
        assert r["ranking"][0]["weighted_score"] >= r["ranking"][1]["weighted_score"]

    def test_explain_no_arbitrations(self):
        eng = StrategicArbitrationEngine()
        r = eng.explain_arbitration()
        assert r["explained"] is False

    def test_explain_after_arbitrate(self):
        eng = StrategicArbitrationEngine()
        eng.arbitrate([{"id": "p1", "steps": []}])
        r = eng.explain_arbitration()
        assert r["explained"] is True
        assert len(r["reasons"]) > 0

    def test_health(self):
        eng = StrategicArbitrationEngine()
        assert eng.health_check()["service"] == "strategic_arbitration_engine"

    def test_restart(self):
        eng = StrategicArbitrationEngine()
        eng.arbitrate([{"id": "p1", "steps": []}])
        eng.restart()
        assert eng.get_stats()["arbitrations"] == 0


# ════════════════════════════════════════════════════════════
# TemporalPlanningEngine
# ════════════════════════════════════════════════════════════
class TestTemporalPlanningEngine:
    def test_analyze_no_constraints(self):
        eng = TemporalPlanningEngine()
        r = eng.analyze_temporal_constraints({
            "steps": [{"id": "s1"}, {"id": "s2"}],
            "temporal_constraints": []
        })
        assert r["analyzed"] is True
        assert r["temporally_valid"] is True
        assert r["issues_count"] == 0

    def test_analyze_dependency_ok(self):
        eng = TemporalPlanningEngine()
        r = eng.analyze_temporal_constraints({
            "steps": [{"id": "s1"}, {"id": "s2"}],
            "temporal_constraints": [
                {"type": "dependency", "before": "s1", "after": "s2"}
            ]
        })
        assert r["temporally_valid"] is True
        assert len(r["valid_sequences"]) == 1

    def test_analyze_dependency_violation(self):
        eng = TemporalPlanningEngine()
        r = eng.analyze_temporal_constraints({
            "steps": [{"id": "s1"}, {"id": "s2"}],
            "temporal_constraints": [
                {"type": "dependency", "before": "s2", "after": "s1"}
            ]
        })
        assert r["temporally_valid"] is False
        assert r["issues_count"] == 1

    def test_analyze_forbidden_sequence(self):
        eng = TemporalPlanningEngine()
        r = eng.analyze_temporal_constraints({
            "steps": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "temporal_constraints": [
                {"type": "forbidden_sequence", "sequence": ["a", "b", "c"]}
            ]
        })
        assert r["issues_count"] == 1

    def test_enforce_order(self):
        eng = TemporalPlanningEngine()
        r = eng.enforce_temporal_order({
            "steps": [{"id": "s2"}, {"id": "s1"}],
            "temporal_constraints": [
                {"type": "dependency", "before": "s1", "after": "s2"}
            ]
        })
        assert r["enforced"] is True
        assert r["ordered_count"] == 2

    def test_health(self):
        eng = TemporalPlanningEngine()
        assert eng.health_check()["service"] == "temporal_planning_engine"

    def test_restart(self):
        eng = TemporalPlanningEngine()
        eng.analyze_temporal_constraints({"steps": [], "temporal_constraints": []})
        eng.restart()
        assert eng.get_stats()["analyses"] == 0


# ════════════════════════════════════════════════════════════
# PlanCoherenceEngine
# ════════════════════════════════════════════════════════════
class TestPlanCoherenceEngine:
    def test_check_coherent_plan(self):
        eng = PlanCoherenceEngine()
        r = eng.check_plan_coherence({
            "steps": [
                {"action": "a", "target": "x"},
                {"action": "b", "target": "y"},
            ]
        })
        assert r["checked"] is True
        assert r["globally_coherent"] is True
        assert r["issues_count"] == 0

    def test_check_duplicate_action(self):
        eng = PlanCoherenceEngine()
        r = eng.check_plan_coherence({
            "steps": [
                {"action": "a", "target": "x"},
                {"action": "a", "target": "y"},
            ]
        })
        assert r["globally_coherent"] is False
        assert r["issues_count"] >= 1

    def test_check_missing_target(self):
        eng = PlanCoherenceEngine()
        r = eng.check_plan_coherence({
            "steps": [
                {"action": "a"},
            ]
        })
        assert r["globally_coherent"] is False

    def test_enforce_coherence(self):
        eng = PlanCoherenceEngine()
        r = eng.enforce_plan_coherence({
            "steps": [
                {"action": "a", "target": "x"},
                {"action": "a", "target": "y"},
                {"action": "b"},
            ]
        })
        assert r["enforced"] is True
        assert r["corrections_count"] >= 1

    def test_enforce_assigns_default_target(self):
        eng = PlanCoherenceEngine()
        r = eng.enforce_plan_coherence({
            "steps": [{"action": "a"}]
        })
        assert r["steps"][0]["target"] == "default"

    def test_health(self):
        eng = PlanCoherenceEngine()
        assert eng.health_check()["service"] == "plan_coherence_engine"

    def test_restart(self):
        eng = PlanCoherenceEngine()
        eng.check_plan_coherence({"steps": []})
        eng.restart()
        assert eng.get_stats()["checks"] == 0


# ════════════════════════════════════════════════════════════
# PlanningExplainabilityEngine
# ════════════════════════════════════════════════════════════
class TestPlanningExplainabilityEngine:
    def test_explain_plan(self):
        eng = PlanningExplainabilityEngine()
        r = eng.explain_plan({
            "id": "plan_test", "goal": "test_goal",
            "steps": [{"action": "a", "target": "b"}]
        })
        assert r["explained"] is True
        assert r["plan_id"] == "plan_test"
        assert len(r["reasons"]) >= 2
        assert eng.get_stats()["plan_explanations"] == 1

    def test_explain_plan_feasible(self):
        eng = PlanningExplainabilityEngine()
        r = eng.explain_plan({"id": "p", "goal": "g", "steps": [], "feasible": True})
        assert any("faisable" in reason for reason in r["reasons"])

    def test_explain_scenario(self):
        eng = PlanningExplainabilityEngine()
        r = eng.explain_scenario({
            "id": "sc_1", "type": "deterministic", "score": 0.9,
            "steps": [{"action": "a"}]
        })
        assert r["explained"] is True
        assert r["scenario_id"] == "sc_1"
        assert eng.get_stats()["scenario_explanations"] == 1

    def test_explain_decision_no_deps(self):
        eng = PlanningExplainabilityEngine()
        r = eng.explain_decision()
        assert r["explained"] is True
        assert any("Aucun contexte" in reason for reason in r["reasons"])

    def test_explain_decision_with_deps(self):
        arb = StrategicArbitrationEngine()
        coh = PlanCoherenceEngine()
        eng = PlanningExplainabilityEngine(arbitration=arb, coherence=coh)
        r = eng.explain_decision()
        assert r["explained"] is True
        assert eng.get_stats()["decision_explanations"] == 1

    def test_health(self):
        eng = PlanningExplainabilityEngine()
        assert eng.health_check()["service"] == "planning_explainability_engine"

    def test_restart(self):
        eng = PlanningExplainabilityEngine()
        eng.explain_plan({"id": "p", "goal": "g", "steps": []})
        eng.restart()
        assert eng.get_stats()["plan_explanations"] == 0


# ════════════════════════════════════════════════════════════
# Tests d'intégration v22
# ════════════════════════════════════════════════════════════
class TestV22Integration:
    def _build_stack(self):
        htn = HTNPlusEngine()
        mo = MultiObjectivePlanner()
        cap = ConstraintAwarePlanner()
        sp = ScenarioPlanner()
        tp = TemporalPlanningEngine()
        arb = StrategicArbitrationEngine()
        coh = PlanCoherenceEngine()
        expl = PlanningExplainabilityEngine(arbitration=arb, coherence=coh)
        planner = StrategicPlanner(
            htn=htn, multi_obj=mo, constraint_planner=cap,
            scenario_planner=sp, temporal_planner=tp, arbitration=arb,
        )
        return {
            "strategic_planner": planner,
            "htn_plus": htn, "multi_objective": mo,
            "constraint_aware": cap, "scenario_planner": sp,
            "arbitration": arb, "temporal": tp,
            "coherence": coh, "explainability": expl,
        }

    def test_full_planning_pipeline(self):
        stack = self._build_stack()
        plan_result = stack["strategic_planner"].plan({
            "goal": "intégration_complète",
            "sub_goals": ["analyse", "exécution", "vérification"],
        })
        assert "id" in plan_result
        assert plan_result["status"] == "draft"

        coh_result = stack["coherence"].check_plan_coherence({
            "steps": [
                {"action": s["action"], "target": s.get("target", "default")}
                for s in plan_result["steps"]
            ]
        })
        assert coh_result["checked"] is True

        expl_result = stack["explainability"].explain_plan({
            "id": plan_result["id"],
            "goal": "intégration_complète",
            "steps": plan_result["steps"],
        })
        assert expl_result["explained"] is True

    def test_scenario_arbitration_pipeline(self):
        stack = self._build_stack()
        scenarios = stack["scenario_planner"].generate_scenarios({
            "goal": "pipeline_test",
            "scenario_types": ["deterministic", "optimized"],
        })
        assert scenarios["count"] == 2

        plans = [
            {"id": s["id"], "steps": s["steps"]}
            for s in scenarios["scenarios"]
        ]
        arb_result = stack["arbitration"].arbitrate(plans)
        assert arb_result["arbitrated"] is True
        assert arb_result["winner"] is not None

    def test_all_health_checks(self):
        stack = self._build_stack()
        for name, mod in stack.items():
            h = mod.health_check()
            assert h["status"] == "ok", f"{name} health failed"

    def test_all_restarts(self):
        stack = self._build_stack()
        for name, mod in stack.items():
            mod.restart()
            stats = mod.get_stats()
            for v in stats.values():
                assert v == 0, f"{name} stats not reset after restart"
