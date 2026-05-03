"""
EXO v23 — Tests de simulation contextuelle
Couvre les 8 modules :
  ContextSimulationSandbox, MultiScenarioSimulationEngine,
  PredictiveModelingEngine, OutcomeAnalysisEngine,
  TemporalSimulationEngine, SimulationCoherenceEngine,
  SimulationGovernanceEngine, SimulationExplainabilityEngine
"""

import sys, os, time

import pytest

from context_simulation_sandbox import ContextSimulationSandbox
from multi_scenario_simulation_engine import MultiScenarioSimulationEngine
from predictive_modeling_engine import PredictiveModelingEngine
from outcome_analysis_engine import OutcomeAnalysisEngine
from temporal_simulation_engine import TemporalSimulationEngine
from simulation_coherence_engine import SimulationCoherenceEngine
from simulation_governance_engine import SimulationGovernanceEngine
from simulation_explainability_engine import SimulationExplainabilityEngine


# ═══════════════════════════════════════════════════════════
# 1. ContextSimulationSandbox
# ═══════════════════════════════════════════════════════════

class TestContextSimulationSandbox:

    def _make(self):
        return ContextSimulationSandbox()

    def test_health_check(self):
        sb = self._make()
        h = sb.health_check()
        assert h["service"] == "context_simulation_sandbox"
        assert h["status"] == "ok"

    def test_sandbox_init(self):
        sb = self._make()
        r = sb.sandbox_init({"variables": {"x": 1}, "agents": ["a1"]})
        assert r["initialized"] is True
        assert r["id"].startswith("sbox_")

    def test_sandbox_run(self):
        sb = self._make()
        sb.sandbox_init({"variables": {"x": 10}})
        plan = {
            "steps": [
                {"action": "set", "target": "x", "value": 42},
                {"action": "increment", "target": "x", "value": 5},
            ]
        }
        r = sb.sandbox_run(plan)
        assert r["executed"] is True
        assert r["steps_executed"] == 2
        # x was set to 42 then incremented by 5 → 47
        snap = sb.sandbox_snapshot()
        assert snap["state"]["variables"]["x"] == 47

    def test_sandbox_snapshot(self):
        sb = self._make()
        sb.sandbox_init({"variables": {"a": 1}})
        snap = sb.sandbox_snapshot()
        assert snap["id"].startswith("snap_")
        assert "state" in snap

    def test_sandbox_isolation(self):
        sb = self._make()
        sb.sandbox_init({"variables": {"v": 100}})
        sb.sandbox_run({"steps": [{"action": "set", "target": "v", "value": 0}]})
        # A new init should reset
        sb.sandbox_init({"variables": {"v": 200}})
        snap = sb.sandbox_snapshot()
        assert snap["state"]["variables"]["v"] == 200

    def test_sandbox_restart(self):
        sb = self._make()
        sb.sandbox_init({"variables": {"x": 1}})
        sb.restart()
        stats = sb.get_stats()
        assert stats["inits"] == 0

    def test_sandbox_add_agent(self):
        sb = self._make()
        sb.sandbox_init({"variables": {}, "agents": ["a1"]})
        plan = {"steps": [{"action": "add_agent", "target": "a2"}]}
        sb.sandbox_run(plan)
        snap = sb.sandbox_snapshot()
        assert "a2" in snap["state"]["agents"]

    def test_sandbox_remove_agent(self):
        sb = self._make()
        sb.sandbox_init({"variables": {}, "agents": ["a1", "a2"]})
        plan = {"steps": [{"action": "remove_agent", "target": "a1"}]}
        sb.sandbox_run(plan)
        snap = sb.sandbox_snapshot()
        assert "a1" not in snap["state"]["agents"]

    def test_sandbox_add_constraint(self):
        sb = self._make()
        sb.sandbox_init({"variables": {}})
        plan = {"steps": [{"action": "add_constraint", "target": "c1"}]}
        sb.sandbox_run(plan)
        snap = sb.sandbox_snapshot()
        names = [c["name"] if isinstance(c, dict) else c for c in snap["state"]["constraints"]]
        assert "c1" in names

    def test_sandbox_noop(self):
        sb = self._make()
        sb.sandbox_init({"variables": {"x": 5}})
        plan = {"steps": [{"action": "noop"}]}
        r = sb.sandbox_run(plan)
        assert r["steps_executed"] == 1
        snap = sb.sandbox_snapshot()
        assert snap["state"]["variables"]["x"] == 5


# ═══════════════════════════════════════════════════════════
# 2. MultiScenarioSimulationEngine
# ═══════════════════════════════════════════════════════════

class TestMultiScenarioSimulationEngine:

    def _make(self):
        return MultiScenarioSimulationEngine()

    def test_health_check(self):
        eng = self._make()
        h = eng.health_check()
        assert h["service"] == "multi_scenario_simulation_engine"
        assert h["status"] == "ok"

    def test_generate_scenarios(self):
        eng = self._make()
        plan = {
            "goal": "test",
            "steps": [{"action": "a1"}, {"action": "a2"}],
            "scenario_types": ["deterministic", "optimized"],
        }
        r = eng.generate_scenarios(plan)
        assert r["generated"] is True
        assert r["count"] == 2
        assert len(r["scenarios"]) == 2
        for sc in r["scenarios"]:
            assert "id" in sc
            assert "score" in sc

    def test_simulate_scenarios(self):
        eng = self._make()
        scenarios = [
            {"id": "sc1", "type": "deterministic", "steps": [{"action": "a"}], "score": 0.8},
            {"id": "sc2", "type": "optimized", "steps": [{"action": "b"}], "score": 0.6},
        ]
        r = eng.simulate_scenarios(scenarios)
        assert r["simulated"] is True
        assert r["count"] == 2
        for res in r["results"]:
            assert res["success"] is True
            assert "effects" in res

    def test_compare_scenarios(self):
        eng = self._make()
        scenarios = [
            {"id": "sc1", "score": 0.6, "steps": [{"action": "a"}]},
            {"id": "sc2", "score": 0.9, "steps": [{"action": "b"}]},
        ]
        r = eng.compare_scenarios(scenarios)
        assert r["compared"] is True
        assert r["best"]["id"] == "sc2"
        assert r["ranking"][0]["rank"] == 1

    def test_generate_unknown_type_ignored(self):
        eng = self._make()
        r = eng.generate_scenarios({
            "goal": "x",
            "steps": [{"action": "a"}],
            "scenario_types": ["unknown_type"],
        })
        assert r["count"] == 0

    def test_restart(self):
        eng = self._make()
        eng.generate_scenarios({"goal": "g", "steps": [{"action": "a"}]})
        eng.restart()
        assert eng.get_stats()["generated"] == 0


# ═══════════════════════════════════════════════════════════
# 3. PredictiveModelingEngine
# ═══════════════════════════════════════════════════════════

class TestPredictiveModelingEngine:

    def _make(self):
        return PredictiveModelingEngine()

    def test_health_check(self):
        eng = self._make()
        h = eng.health_check()
        assert h["service"] == "predictive_modeling_engine"
        assert h["status"] == "ok"

    def test_predict_outcomes(self):
        eng = self._make()
        r = eng.predict_outcomes({
            "goal": "test",
            "steps": [{"action": "a"}, {"action": "b"}, {"action": "c"}],
            "mode": "causal",
        })
        assert r["predicted"] is True
        assert r["count"] == 3
        assert r["mode"] == "causal"
        assert 0 < r["confidence"] <= 1.0
        for p in r["predictions"]:
            assert "impact" in p
            assert "reversible" in p

    def test_predict_event(self):
        eng = self._make()
        r = eng.predict_event({"type": "failure", "target": "network", "severity": "high"})
        assert "consequences" in r
        assert r["count"] == 3  # high → 3 consequences
        assert r["severity"] == "high"

    def test_predict_event_critical(self):
        eng = self._make()
        r = eng.predict_event({"type": "crash", "severity": "critical"})
        assert r["count"] == 4  # critical → 4

    def test_explain_prediction(self):
        eng = self._make()
        eng.predict_outcomes({"goal": "g", "steps": [{"action": "a"}]})
        r = eng.explain_prediction()
        assert r["explained"] is True
        assert r["count"] >= 1

    def test_restart(self):
        eng = self._make()
        eng.predict_event({"type": "t"})
        eng.restart()
        assert eng.get_stats()["events_predicted"] == 0


# ═══════════════════════════════════════════════════════════
# 4. OutcomeAnalysisEngine
# ═══════════════════════════════════════════════════════════

class TestOutcomeAnalysisEngine:

    def _make(self):
        return OutcomeAnalysisEngine()

    def test_health_check(self):
        eng = self._make()
        h = eng.health_check()
        assert h["service"] == "outcome_analysis_engine"
        assert h["status"] == "ok"

    def test_analyze_outcomes(self):
        eng = self._make()
        r = eng.analyze_outcomes({
            "results": [
                {"scenario_id": "s1", "score": 0.9, "effects": [1, 2], "success": True},
                {"scenario_id": "s2", "score": 0.3, "effects": [1], "success": False},
            ]
        })
        assert r["analyzed"] is True
        assert r["count"] == 2
        assert "aggregated" in r
        assert r["aggregated"]["total"] == 2

    def test_classify_risks(self):
        eng = self._make()
        r = eng.classify_risks({
            "results": [
                {"scenario_id": "s1", "score": 0.9},
                {"scenario_id": "s2", "score": 0.1},
            ]
        })
        assert r["classified"] is True
        assert r["count"] == 2
        assert r["risk_counts"]["low"] == 1
        assert r["risk_counts"]["critical"] == 1

    def test_compute_best_outcome_empty(self):
        eng = self._make()
        r = eng.compute_best_outcome()
        assert r["found"] is False

    def test_compute_best_outcome(self):
        eng = self._make()
        eng.analyze_outcomes({"results": [
            {"scenario_id": "a", "score": 0.5, "effects": [], "success": True},
        ]})
        eng.analyze_outcomes({"results": [
            {"scenario_id": "b", "score": 0.9, "effects": [], "success": True},
        ]})
        r = eng.compute_best_outcome()
        assert r["found"] is True
        assert r["best_score"] > 0

    def test_restart(self):
        eng = self._make()
        eng.analyze_outcomes({"results": [{"score": 0.5}]})
        eng.restart()
        assert eng.get_stats()["analyzed"] == 0


# ═══════════════════════════════════════════════════════════
# 5. TemporalSimulationEngine
# ═══════════════════════════════════════════════════════════

class TestTemporalSimulationEngine:

    def _make(self):
        return TemporalSimulationEngine()

    def test_health_check(self):
        eng = self._make()
        h = eng.health_check()
        assert h["service"] == "temporal_simulation_engine"
        assert h["status"] == "ok"

    def test_simulate_temporal_flow(self):
        eng = self._make()
        r = eng.simulate_temporal_flow({
            "steps": [
                {"action": "a", "duration": 2.0},
                {"action": "b", "duration": 3.0},
                {"action": "c", "duration": 1.0, "depends_on": [0]},
            ]
        })
        assert r["simulated"] is True
        assert r["steps_count"] == 3
        assert r["total_duration"] > 0
        # Step c depends on step 0 (a), which ends at 2.0
        timeline = r["timeline"]
        assert timeline[2]["start_time"] >= timeline[0]["end_time"]

    def test_enforce_temporal_constraints_clean(self):
        eng = self._make()
        eng.simulate_temporal_flow({
            "steps": [{"action": "a", "duration": 1.0}]
        })
        r = eng.enforce_temporal_constraints()
        assert r["coherent"] is True
        assert r["violations_count"] == 0

    def test_restart(self):
        eng = self._make()
        eng.simulate_temporal_flow({"steps": [{"action": "a"}]})
        eng.restart()
        assert eng.get_stats()["flows_simulated"] == 0


# ═══════════════════════════════════════════════════════════
# 6. SimulationCoherenceEngine
# ═══════════════════════════════════════════════════════════

class TestSimulationCoherenceEngine:

    def _make(self):
        return SimulationCoherenceEngine()

    def test_health_check(self):
        eng = self._make()
        h = eng.health_check()
        assert h["service"] == "simulation_coherence_engine"
        assert h["status"] == "ok"

    def test_check_coherence_clean(self):
        eng = self._make()
        r = eng.check_simulation_coherence({
            "results": [
                {"scenario_id": "s1", "score": 0.8, "effects": [
                    {"step": 1}, {"step": 2}
                ]},
            ]
        })
        assert r["coherent"] is True
        assert r["issues_count"] == 0

    def test_check_coherence_duplicate_id(self):
        eng = self._make()
        r = eng.check_simulation_coherence({
            "results": [
                {"scenario_id": "s1", "score": 0.5, "effects": []},
                {"scenario_id": "s1", "score": 0.6, "effects": []},
            ]
        })
        assert r["coherent"] is False
        assert r["issues_count"] >= 1

    def test_check_coherence_bad_score(self):
        eng = self._make()
        r = eng.check_simulation_coherence({
            "results": [
                {"scenario_id": "s1", "score": 1.5, "effects": []},
            ]
        })
        assert r["coherent"] is False

    def test_enforce_coherence(self):
        eng = self._make()
        r = eng.enforce_simulation_coherence({
            "results": [
                {"scenario_id": "s1", "score": 0.5, "effects": []},
                {"scenario_id": "s1", "score": 0.5, "effects": []},
            ]
        })
        assert r["enforced"] is True
        assert r["coherent_after"] is True

    def test_restart(self):
        eng = self._make()
        eng.check_simulation_coherence({"results": []})
        eng.restart()
        assert eng.get_stats()["checked"] == 0


# ═══════════════════════════════════════════════════════════
# 7. SimulationGovernanceEngine
# ═══════════════════════════════════════════════════════════

class TestSimulationGovernanceEngine:

    def _make(self):
        return SimulationGovernanceEngine()

    def test_health_check(self):
        eng = self._make()
        h = eng.health_check()
        assert h["service"] == "simulation_governance_engine"
        assert h["status"] == "ok"

    def test_validate_simulation_ok(self):
        eng = self._make()
        r = eng.validate_simulation({
            "steps": [{"action": "a"}],
            "depth": 2,
        })
        assert r["valid"] is True
        assert r["violations_count"] == 0

    def test_validate_simulation_too_many_steps(self):
        eng = self._make()
        steps = [{"action": f"s{i}"} for i in range(250)]
        r = eng.validate_simulation({"steps": steps, "depth": 1})
        assert r["valid"] is False
        viol_types = [v["type"] for v in r["violations"]]
        assert "max_steps_exceeded" in viol_types

    def test_validate_simulation_too_deep(self):
        eng = self._make()
        r = eng.validate_simulation({"steps": [], "depth": 100})
        assert r["valid"] is False
        viol_types = [v["type"] for v in r["violations"]]
        assert "max_depth_exceeded" in viol_types

    def test_block_simulation(self):
        eng = self._make()
        r = eng.block_simulation({"id": "sim1", "block_reason": "unsafe"})
        assert r["blocked"] is True
        assert r["reason"] == "unsafe"

    def test_audit_simulation(self):
        eng = self._make()
        r = eng.audit_simulation({
            "id": "sim1",
            "steps": [{"action": "a"}],
            "results": [],
            "depth": 2,
        })
        assert r["audited"] is True
        assert r["compliant"] is True

    def test_audit_simulation_non_compliant(self):
        eng = self._make()
        steps = [{"action": f"s{i}"} for i in range(250)]
        r = eng.audit_simulation({
            "id": "sim2",
            "steps": steps,
            "results": [],
            "depth": 2,
        })
        assert r["audited"] is True
        assert r["compliant"] is False

    def test_restart(self):
        eng = self._make()
        eng.validate_simulation({"steps": []})
        eng.restart()
        assert eng.get_stats()["validated"] == 0


# ═══════════════════════════════════════════════════════════
# 8. SimulationExplainabilityEngine
# ═══════════════════════════════════════════════════════════

class TestSimulationExplainabilityEngine:

    def _make(self):
        return SimulationExplainabilityEngine()

    def test_health_check(self):
        eng = self._make()
        h = eng.health_check()
        assert h["service"] == "simulation_explainability_engine"
        assert h["status"] == "ok"

    def test_explain_simulation(self):
        eng = self._make()
        r = eng.explain_simulation({
            "id": "sim1",
            "steps": [{"action": "a"}],
            "results": [
                {"scenario_id": "s1", "score": 0.7, "effects_count": 2, "success": True},
            ],
        })
        assert r["explained"] is True
        assert r["parts_count"] >= 2  # structure + 1 result
        assert r["simulation_id"] == "sim1"

    def test_explain_outcome(self):
        eng = self._make()
        r = eng.explain_outcome({
            "analysis": [
                {"scenario_id": "s1", "score": 0.8, "risk_level": "low", "success": True},
            ],
            "aggregated": {"avg_score": 0.8, "success_rate": 1.0, "total": 1},
        })
        assert r["explained"] is True
        assert r["parts_count"] >= 2  # aggregation + 1 detail

    def test_explain_temporal_flow_empty(self):
        eng = self._make()
        r = eng.explain_temporal_flow()
        assert r["explained"] is True
        assert r["count"] >= 1  # at least the "none" entry

    def test_explain_temporal_flow_with_data(self):
        eng = self._make()
        eng.explain_simulation({"id": "sim1", "steps": [], "results": []})
        r = eng.explain_temporal_flow()
        assert r["explained"] is True
        assert r["count"] >= 1

    def test_restart(self):
        eng = self._make()
        eng.explain_simulation({"id": "x", "steps": [], "results": []})
        eng.restart()
        assert eng.get_stats()["simulations_explained"] == 0


# ═══════════════════════════════════════════════════════════
# 9. Cross-module integration
# ═══════════════════════════════════════════════════════════

class TestV23Integration:

    def test_full_pipeline(self):
        """Test du pipeline complet : sandbox → multi-scénario → prédiction → analyse → cohérence → gouvernance → explicabilité."""
        gov = SimulationGovernanceEngine()
        sandbox = ContextSimulationSandbox(governance=gov)
        multi = MultiScenarioSimulationEngine(governance=gov, sandbox=sandbox)
        pred = PredictiveModelingEngine(governance=gov, sandbox=sandbox)
        outcome = OutcomeAnalysisEngine(governance=gov, sandbox=sandbox)
        temporal = TemporalSimulationEngine(governance=gov, sandbox=sandbox)
        coherence = SimulationCoherenceEngine(governance=gov, sandbox=sandbox)
        explain = SimulationExplainabilityEngine(governance=gov, sandbox=sandbox)

        # 1. Init sandbox
        sandbox.sandbox_init({"variables": {"goal": "test"}})

        # 2. Generate & simulate scenarios
        gen = multi.generate_scenarios({
            "goal": "test_pipeline",
            "steps": [{"action": "step1"}, {"action": "step2"}],
            "scenario_types": ["deterministic", "contextual"],
        })
        assert gen["count"] == 2

        sim = multi.simulate_scenarios(gen["scenarios"])
        assert sim["simulated"] is True

        # 3. Predict
        pred_r = pred.predict_outcomes({
            "goal": "test",
            "steps": [{"action": "step1"}],
        })
        assert pred_r["predicted"] is True

        # 4. Analyze
        analysis = outcome.analyze_outcomes(sim)
        assert analysis["analyzed"] is True

        # 5. Classify risks
        risks = outcome.classify_risks(sim)
        assert risks["classified"] is True

        # 6. Best outcome
        best = outcome.compute_best_outcome()
        assert best["found"] is True

        # 7. Temporal
        tf = temporal.simulate_temporal_flow({
            "steps": [{"action": "a", "duration": 1.0}, {"action": "b", "duration": 2.0}]
        })
        assert tf["simulated"] is True

        # 8. Coherence
        coh = coherence.check_simulation_coherence(sim)
        assert coh["coherent"] is True

        # 9. Governance
        val = gov.validate_simulation({"steps": [{"action": "a"}], "depth": 1})
        assert val["valid"] is True

        # 10. Explain
        exp = explain.explain_simulation({
            "id": "pipeline_sim",
            "steps": [{"action": "a"}],
            "results": sim["results"],
        })
        assert exp["explained"] is True

    def test_all_health_checks(self):
        """Tous les modules v23 retournent un health_check OK."""
        modules = [
            ContextSimulationSandbox(),
            MultiScenarioSimulationEngine(),
            PredictiveModelingEngine(),
            OutcomeAnalysisEngine(),
            TemporalSimulationEngine(),
            SimulationCoherenceEngine(),
            SimulationGovernanceEngine(),
            SimulationExplainabilityEngine(),
        ]
        for mod in modules:
            h = mod.health_check()
            assert h["status"] == "ok", f"{h['service']} health check failed"

    def test_all_restarts(self):
        """Tous les modules v23 se réinitialisent proprement."""
        modules = [
            ContextSimulationSandbox(),
            MultiScenarioSimulationEngine(),
            PredictiveModelingEngine(),
            OutcomeAnalysisEngine(),
            TemporalSimulationEngine(),
            SimulationCoherenceEngine(),
            SimulationGovernanceEngine(),
            SimulationExplainabilityEngine(),
        ]
        for mod in modules:
            mod.restart()
            stats = mod.get_stats()
            assert all(v == 0 for v in stats.values()), \
                f"{mod.__class__.__name__} stats not zeroed after restart"
