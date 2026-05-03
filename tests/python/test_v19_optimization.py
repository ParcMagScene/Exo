"""
Tests EXO v19 — Optimisation cognitive
10 modules × ~7 tests = ~70 tests
"""
import sys, pathlib, pytest

from meta_optimizer import MetaOptimizer
from adaptive_heuristics_engine import AdaptiveHeuristicsEngine
from cognitive_pipeline_optimizer import CognitivePipelineOptimizer
from cognitive_load_reducer import CognitiveLoadReducer
from multi_objective_optimizer import MultiObjectiveOptimizer
from cognitive_profiling_engine import CognitiveProfilingEngine
from plan_optimizer import PlanOptimizer
from simulation_optimizer import SimulationOptimizer
from inference_optimizer import InferenceOptimizer
from optimization_explainability_engine import OptimizationExplainabilityEngine


# ═══════════════════════════════════════════════════════════
# 1. MetaOptimizer
# ═══════════════════════════════════════════════════════════

class TestMetaOptimizer:
    def _make(self):
        return MetaOptimizer()

    def test_analyze_system_basic(self):
        m = self._make()
        r = m.analyze_system()
        assert r["analyzed"] is True
        assert "findings" in r
        assert r["total_components"] == 0  # pas de deps

    def test_detect_inefficiencies_basic(self):
        m = self._make()
        r = m.detect_inefficiencies()
        assert r["detected"] is True
        assert "inefficiencies" in r
        assert r["total"] == 0  # pas de deps

    def test_propose_optimizations_basic(self):
        m = self._make()
        r = m.propose_optimizations()
        assert r["proposed"] is True
        assert "proposals" in r
        assert r["total_proposals"] >= 0

    def test_optimization_history(self):
        m = self._make()
        m.propose_optimizations()
        m.propose_optimizations()
        h = m.get_optimization_history()
        assert len(h) == 2

    def test_health_check(self):
        m = self._make()
        h = m.health_check()
        assert h["service"] == "meta_optimizer"
        assert h["status"] == "ok"

    def test_restart(self):
        m = self._make()
        m.analyze_system()
        m.propose_optimizations()
        m.restart()
        assert m.get_stats()["analyses"] == 0
        assert m.get_optimization_history() == []

    def test_stats_increment(self):
        m = self._make()
        m.analyze_system()
        m.detect_inefficiencies()
        m.propose_optimizations()
        s = m.get_stats()
        assert s["analyses"] == 1
        assert s["inefficiencies_detected"] == 2  # propose also calls detect
        assert s["optimizations_proposed"] == 1


# ═══════════════════════════════════════════════════════════
# 2. AdaptiveHeuristicsEngine
# ═══════════════════════════════════════════════════════════

class TestAdaptiveHeuristicsEngine:
    def _make(self):
        return AdaptiveHeuristicsEngine()

    def test_update_heuristics(self):
        e = self._make()
        r = e.update_heuristics()
        assert r["updated"] is True
        assert "strategies" in r
        assert len(r["strategies"]) == 3

    def test_select_best_strategy_general(self):
        e = self._make()
        r = e.select_best_strategy({"type": "general"})
        assert r["selected"] is True
        assert r["strategy"] in ("speed_first", "accuracy_first", "balanced")

    def test_select_best_strategy_urgent(self):
        e = self._make()
        r = e.select_best_strategy({"type": "command", "urgency": "high"})
        assert r["selected"] is True
        assert r["urgency"] == "high"

    def test_adapt_to_context_normal(self):
        e = self._make()
        r = e.adapt_to_context({"system_load": 0.3, "error_rate": 0.01,
                                "avg_response_ms": 30})
        assert r["adapted"] is True
        assert r["total"] == 0  # tout va bien

    def test_adapt_to_context_stressed(self):
        e = self._make()
        r = e.adapt_to_context({"system_load": 0.9, "error_rate": 0.2,
                                "avg_response_ms": 300})
        assert r["adapted"] is True
        assert r["total"] == 3  # 3 problèmes détectés

    def test_health_check(self):
        e = self._make()
        h = e.health_check()
        assert h["service"] == "adaptive_heuristics"
        assert h["status"] == "ok"

    def test_restart_resets_weights(self):
        e = self._make()
        e.update_heuristics()
        e.restart()
        assert e.get_stats()["heuristic_updates"] == 0


# ═══════════════════════════════════════════════════════════
# 3. CognitivePipelineOptimizer
# ═══════════════════════════════════════════════════════════

class TestCognitivePipelineOptimizer:
    def _make(self):
        return CognitivePipelineOptimizer()

    def test_optimize_pipeline_basic(self):
        p = self._make()
        r = p.optimize_pipeline({"name": "test", "steps": [
            {"name": "s1", "cost": 1.0, "required": True, "priority": 1},
            {"name": "s2", "cost": 5.0, "required": False, "priority": 0},
        ]})
        assert r["optimized"] is True
        assert r["original_steps"] == 2
        # s2 is optional with cost > 2.0 so removed
        assert r["optimized_steps"] == 1

    def test_optimize_pipeline_keeps_required(self):
        p = self._make()
        r = p.optimize_pipeline({"name": "test", "steps": [
            {"name": "s1", "cost": 10.0, "required": True, "priority": 5},
        ]})
        assert r["optimized_steps"] == 1

    def test_reorder_steps_cost_first(self):
        p = self._make()
        r = p.reorder_steps({
            "strategy": "cost_first",
            "items": [
                {"name": "a", "cost": 5.0},
                {"name": "b", "cost": 1.0},
                {"name": "c", "cost": 3.0},
            ]
        })
        assert r["reordered"] is True
        assert r["reordered_steps"][0]["name"] == "b"

    def test_reorder_steps_priority_first(self):
        p = self._make()
        r = p.reorder_steps({
            "strategy": "priority_first",
            "items": [
                {"name": "a", "priority": 1},
                {"name": "b", "priority": 10},
            ]
        })
        assert r["reordered_steps"][0]["name"] == "b"

    def test_optimize_flow_dedup(self):
        p = self._make()
        r = p.optimize_flow({"name": "f1", "edges": [
            {"from": "A", "to": "B"},
            {"from": "A", "to": "B"},
            {"from": "B", "to": "C"},
        ]})
        assert r["optimized"] is True
        assert r["original_edges"] == 3
        assert r["optimized_edges"] == 2

    def test_health_check(self):
        p = self._make()
        h = p.health_check()
        assert h["service"] == "cognitive_pipeline_optimizer"
        assert h["status"] == "ok"

    def test_restart(self):
        p = self._make()
        p.optimize_pipeline({"steps": []})
        p.restart()
        assert p.get_stats()["pipelines_optimized"] == 0


# ═══════════════════════════════════════════════════════════
# 4. CognitiveLoadReducer
# ═══════════════════════════════════════════════════════════

class TestCognitiveLoadReducer:
    def _make(self):
        return CognitiveLoadReducer()

    def test_remove_redundancies_empty(self):
        r = self._make().remove_redundancies()
        assert r["removed"] is True
        assert r["total"] == 0

    def test_reduce_llm_calls(self):
        r = self._make().reduce_llm_calls()
        assert r["reduced"] is True
        assert r["total_strategies"] == 4
        assert r["estimated_total_reduction_pct"] <= 70

    def test_simplify_pipeline(self):
        r = self._make().simplify_pipeline()
        assert r["simplified"] is True
        assert r["total_suggestions"] == 3

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "cognitive_load_reducer"
        assert h["status"] == "ok"

    def test_restart(self):
        e = self._make()
        e.remove_redundancies()
        e.restart()
        assert e.get_stats()["redundancies_removed"] == 0

    def test_stats(self):
        e = self._make()
        e.reduce_llm_calls()
        e.simplify_pipeline()
        s = e.get_stats()
        assert s["llm_calls_reduced"] == 1
        assert s["pipelines_simplified"] == 1


# ═══════════════════════════════════════════════════════════
# 5. MultiObjectiveOptimizer
# ═══════════════════════════════════════════════════════════

class TestMultiObjectiveOptimizer:
    def _make(self):
        return MultiObjectiveOptimizer()

    def test_optimize_for_speed(self):
        r = self._make().optimize_for({
            "speed": 1.0, "precision": 0.1, "reliability": 0.1,
            "coherence": 0.1, "cognitive_cost": 0.1,
            "stability": 0.1, "security": 0.1,
        })
        assert r["optimized"] is True
        assert r["best"] == "speed_optimized"
        assert len(r["solutions"]) == 4

    def test_optimize_for_balanced(self):
        r = self._make().optimize_for({})
        assert r["optimized"] is True
        assert r["best"] is not None

    def test_compute_tradeoffs_conflict(self):
        r = self._make().compute_tradeoffs({"speed": 0.9, "precision": 0.9})
        assert r["computed"] is True
        assert r["total"] >= 1

    def test_compute_tradeoffs_no_conflict(self):
        r = self._make().compute_tradeoffs({"speed": 0.3, "precision": 0.3})
        assert r["computed"] is True
        assert r["total"] == 0

    def test_select_optimal_no_data(self):
        r = self._make().select_optimal_solution()
        assert r["selected"] is False
        assert r["reason"] == "no_solutions_available"

    def test_select_optimal_with_data(self):
        e = self._make()
        e.optimize_for({"speed": 0.8})
        r = e.select_optimal_solution()
        assert r["selected"] is True
        assert "solution" in r

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "multi_objective_optimizer"
        assert h["status"] == "ok"

    def test_restart(self):
        e = self._make()
        e.optimize_for({})
        e.restart()
        assert e.get_stats()["optimizations"] == 0


# ═══════════════════════════════════════════════════════════
# 6. CognitiveProfilingEngine
# ═══════════════════════════════════════════════════════════

class TestCognitiveProfilingEngine:
    def _make(self):
        return CognitiveProfilingEngine()

    def test_profile_system_empty(self):
        r = self._make().profile_system()
        assert r["profiled"] is True
        assert r["total_layers"] == 0
        assert r["total_agents"] == 0

    def test_profile_agent_normal(self):
        r = self._make().profile_agent({
            "name": "test_agent", "type": "micro",
            "executions": 100, "failures": 2,
            "avg_latency_ms": 10.0, "max_latency_ms": 50.0,
        })
        assert r["profiled"] is True
        assert r["is_bottleneck"] is False
        assert r["efficiency"] > 0.9

    def test_profile_agent_bottleneck(self):
        r = self._make().profile_agent({
            "name": "slow_agent", "type": "micro",
            "executions": 100, "failures": 30,
            "avg_latency_ms": 200.0,
        })
        assert r["profiled"] is True
        assert r["is_bottleneck"] is True

    def test_profile_layer_normal(self):
        r = self._make().profile_layer({
            "name": "test_layer", "push_count": 50, "pull_count": 40,
        })
        assert r["profiled"] is True
        assert r["is_underutilized"] is False

    def test_profile_layer_underutilized(self):
        r = self._make().profile_layer({
            "name": "dead_layer", "push_count": 100, "pull_count": 0,
        })
        assert r["profiled"] is True
        assert r["is_underutilized"] is True

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "cognitive_profiling"
        assert h["status"] == "ok"

    def test_restart(self):
        e = self._make()
        e.profile_system()
        e.restart()
        assert e.get_stats()["system_profiles"] == 0


# ═══════════════════════════════════════════════════════════
# 7. PlanOptimizer
# ═══════════════════════════════════════════════════════════

class TestPlanOptimizer:
    def _make(self):
        return PlanOptimizer()

    def test_optimize_plan_eliminates_costly(self):
        r = self._make().optimize_plan({"goal": "test", "steps": [
            {"name": "good", "cost": 1.0, "effect": 1.0},
            {"name": "bad", "cost": 5.0, "effect": 0.1},
        ]})
        assert r["optimized"] is True
        assert r["original_steps"] == 2
        assert r["optimized_steps"] == 1
        assert r["gain_pct"] > 0

    def test_optimize_plan_keeps_efficient(self):
        r = self._make().optimize_plan({"goal": "test", "steps": [
            {"name": "a", "cost": 1.0, "effect": 5.0},
            {"name": "b", "cost": 2.0, "effect": 4.0},
        ]})
        assert r["optimized_steps"] == 2

    def test_simplify_plan_merges(self):
        r = self._make().simplify_plan({"goal": "test", "steps": [
            {"name": "s1", "type": "action", "cost": 1.0},
            {"name": "s2", "type": "action", "cost": 2.0},
            {"name": "s3", "type": "query", "cost": 1.0},
        ]})
        assert r["simplified"] is True
        assert r["merges"] >= 1
        assert r["simplified_steps"] < r["original_steps"]

    def test_generate_alternative_plans(self):
        r = self._make().generate_alternative_plans({"goal": "test", "steps": [
            {"name": "a", "cost": 1.0, "effect": 1.0, "required": True},
            {"name": "b", "cost": 2.0, "effect": 0.5, "required": False},
            {"name": "c", "cost": 1.5, "effect": 0.8, "required": True},
        ]})
        assert r["generated"] is True
        assert r["total_alternatives"] >= 2  # reversed + minimal + required_only

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "plan_optimizer"
        assert h["status"] == "ok"

    def test_restart(self):
        e = self._make()
        e.optimize_plan({"steps": []})
        e.restart()
        assert e.get_stats()["plans_optimized"] == 0


# ═══════════════════════════════════════════════════════════
# 8. SimulationOptimizer
# ═══════════════════════════════════════════════════════════

class TestSimulationOptimizer:
    def _make(self):
        return SimulationOptimizer()

    def test_optimize_simulation_prunes(self):
        r = self._make().optimize_simulation({"name": "test", "scenarios": [
            {"name": "likely", "probability": 0.8, "depth": 2},
            {"name": "unlikely_deep", "probability": 0.01, "depth": 5},
            {"name": "negligible", "probability": 0.005},
        ]})
        assert r["optimized"] is True
        assert r["optimized_scenarios"] == 1  # only "likely" kept
        assert r["cost_reduction_pct"] > 0

    def test_prune_simulation_tree(self):
        r = self._make().prune_simulation_tree({"prune_threshold": 0.3, "nodes": [
            {"name": "n1", "value": 0.5},
            {"name": "n2", "value": 0.1},
            {"name": "n3", "value": 0.9},
        ]})
        assert r["pruned"] is True
        assert r["kept_nodes"] == 2
        assert r["total_pruned"] == 1

    def test_select_relevant_scenarios(self):
        r = self._make().select_relevant_scenarios()
        assert r["selected"] is True
        assert r["total"] == 4
        assert r["coverage_pct"] > 50

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "simulation_optimizer"
        assert h["status"] == "ok"

    def test_restart(self):
        e = self._make()
        e.optimize_simulation({"scenarios": []})
        e.restart()
        assert e.get_stats()["simulations_optimized"] == 0


# ═══════════════════════════════════════════════════════════
# 9. InferenceOptimizer
# ═══════════════════════════════════════════════════════════

class TestInferenceOptimizer:
    def _make(self):
        return InferenceOptimizer()

    def test_optimize_inference_dedup(self):
        r = self._make().optimize_inference({
            "question": "test",
            "rules": [
                {"id": "r1"}, {"id": "r2"}, {"id": "r1"},  # r1 duplicate
            ],
            "chain_length": 3,
        })
        assert r["optimized"] is True
        assert r["original_rules"] == 3
        assert r["optimized_rules"] == 2

    def test_optimize_inference_long_chain(self):
        r = self._make().optimize_inference({
            "question": "complex",
            "rules": [],
            "chain_length": 10,
        })
        assert r["optimized"] is True
        assert any(o["type"] == "shorten_chain"
                    for o in r["optimizations"])

    def test_simplify_rules(self):
        r = self._make().simplify_rules()
        assert r["simplified"] is True
        assert r["total_suggestions"] == 3

    def test_compress_knowledge_graph(self):
        r = self._make().compress_knowledge_graph()
        assert r["compressed"] is True
        assert r["total_strategies"] == 3

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "inference_optimizer"
        assert h["status"] == "ok"

    def test_restart(self):
        e = self._make()
        e.optimize_inference({"rules": [], "chain_length": 1})
        e.restart()
        assert e.get_stats()["inferences_optimized"] == 0


# ═══════════════════════════════════════════════════════════
# 10. OptimizationExplainabilityEngine
# ═══════════════════════════════════════════════════════════

class TestOptimizationExplainabilityEngine:
    def _make(self):
        meta = MetaOptimizer()
        multi = MultiObjectiveOptimizer(meta_optimizer=meta)
        prof = CognitiveProfilingEngine(meta_optimizer=meta)
        return OptimizationExplainabilityEngine(
            meta_optimizer=meta, multi_objective=multi, profiling=prof)

    def test_explain_optimization_empty(self):
        r = self._make().explain_optimization()
        assert r["explained"] is True
        # meta has no history yet → some explanations from multi_objective
        assert "explanations" in r

    def test_explain_optimization_with_history(self):
        meta = MetaOptimizer()
        meta.propose_optimizations()
        multi = MultiObjectiveOptimizer(meta_optimizer=meta)
        e = OptimizationExplainabilityEngine(
            meta_optimizer=meta, multi_objective=multi)
        r = e.explain_optimization()
        assert r["explained"] is True

    def test_explain_tradeoffs(self):
        r = self._make().explain_tradeoffs()
        assert r["explained"] is True
        assert r["total"] == 3
        assert "non-négociable" in r["principle"]

    def test_explain_performance_gain(self):
        r = self._make().explain_performance_gain()
        assert r["explained"] is True
        assert "gains" in r

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "optimization_explainability"
        assert h["status"] == "ok"

    def test_restart(self):
        e = self._make()
        e.explain_optimization()
        e.restart()
        assert e.get_stats()["optimizations_explained"] == 0


# ═══════════════════════════════════════════════════════════
# Integration — cross-module wiring
# ═══════════════════════════════════════════════════════════

class TestV19Integration:
    def _build(self):
        meta = MetaOptimizer()
        heur = AdaptiveHeuristicsEngine(meta_optimizer=meta)
        pipe = CognitivePipelineOptimizer(meta_optimizer=meta)
        load = CognitiveLoadReducer(pipeline_optimizer=pipe)
        multi = MultiObjectiveOptimizer(
            meta_optimizer=meta, heuristics=heur)
        prof = CognitiveProfilingEngine(meta_optimizer=meta)
        plan = PlanOptimizer(
            meta_optimizer=meta, pipeline_optimizer=pipe)
        sim = SimulationOptimizer(
            meta_optimizer=meta, profiling=prof)
        inf = InferenceOptimizer(meta_optimizer=meta)
        explain = OptimizationExplainabilityEngine(
            meta_optimizer=meta, multi_objective=multi, profiling=prof)
        return {
            "meta_optimizer": meta,
            "adaptive_heuristics": heur,
            "pipeline_optimizer": pipe,
            "load_reducer": load,
            "multi_objective": multi,
            "profiling": prof,
            "plan_optimizer": plan,
            "simulation_optimizer": sim,
            "inference_optimizer": inf,
            "optimization_explainability": explain,
        }

    def test_all_modules_created(self):
        mods = self._build()
        assert len(mods) == 10

    def test_all_health_checks(self):
        mods = self._build()
        for name, mod in mods.items():
            h = mod.health_check()
            assert h["status"] == "ok", f"{name} health failed"

    def test_all_restarts(self):
        mods = self._build()
        for name, mod in mods.items():
            mod.restart()
            assert mod.get_stats() is not None

    def test_meta_analyze_then_explain(self):
        mods = self._build()
        mods["meta_optimizer"].analyze_system()
        mods["meta_optimizer"].propose_optimizations()
        r = mods["optimization_explainability"].explain_optimization()
        assert r["explained"] is True

    def test_full_optimization_flow(self):
        """Flux complet: profiling → detect → propose → optimize_for → explain"""
        mods = self._build()
        # 1. Profiler
        mods["profiling"].profile_system()
        # 2. Analyser
        mods["meta_optimizer"].analyze_system()
        # 3. Détecter les inefficacités
        mods["meta_optimizer"].detect_inefficiencies()
        # 4. Proposer des optimisations
        mods["meta_optimizer"].propose_optimizations()
        # 5. Multi-objectifs
        r = mods["multi_objective"].optimize_for({"speed": 0.8, "precision": 0.5})
        assert r["best"] is not None
        # 6. Expliquer
        e = mods["optimization_explainability"].explain_performance_gain()
        assert e["explained"] is True
