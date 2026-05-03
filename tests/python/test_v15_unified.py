"""
EXO v15 — Tests unifiés : Architecture cognitive complète.
Couvre : ExpertSystemEngine, KnowledgeGraph, InferenceEngine,
         CognitiveAgentCore, MetaCognitionEngine, ProspectiveEngine,
         DistributedCognitionLayer, GlobalSupervisorV5, ExplainabilityEngineV5.
"""

import sys
from pathlib import Path

import pytest

from expert_system_engine import ExpertSystemEngine
from knowledge_graph import KnowledgeGraph
from inference_engine import InferenceEngine
from cognitive_agent_core import CognitiveAgentCore
from meta_cognition_engine import MetaCognitionEngine
from prospective_engine import ProspectiveEngine
from distributed_cognition_layer import DistributedCognitionLayer
from global_supervisor_v5 import GlobalSupervisorV5
from explainability_engine_v5 import ExplainabilityEngineV5


# =====================================================================
# ExpertSystemEngine
# =====================================================================

class TestExpertSystemEngine:
    def _make(self):
        return ExpertSystemEngine()

    def test_health_check(self):
        e = self._make()
        h = e.health_check()
        assert h["service"] == "expert_system"
        assert h["status"] == "ok"

    def test_get_stats_initial(self):
        e = self._make()
        s = e.get_stats()
        assert s["rules_added"] == 0
        assert s["inferences_run"] == 0

    def test_add_rule(self):
        e = self._make()
        rid = e.add_rule({
            "condition": {"field": "temp", "op": ">", "value": 30},
            "action": {"type": "assert", "key": "hot", "value": True},
            "priority": 10,
            "description": "Si temp > 30 alors chaud",
        })
        assert rid.startswith("rule_")
        assert e.get_stats()["rules_added"] == 1

    def test_add_rule_invalid(self):
        e = self._make()
        rid = e.add_rule({})
        assert rid.startswith("rule_")  # engine accepts any dict

    def test_add_fact(self):
        e = self._make()
        fid = e.add_fact({"key": "temp", "value": 35, "domain": "env", "confidence": 0.9})
        assert fid.startswith("fact_")
        assert e.get_stats()["facts_added"] == 1

    def test_add_fact_invalid(self):
        e = self._make()
        fid = e.add_fact({})
        assert fid.startswith("fact_")  # engine accepts any dict

    def test_remove_rule(self):
        e = self._make()
        rid = e.add_rule({
            "condition": {"field": "x", "op": "==", "value": 1},
            "action": {"type": "assert", "key": "y", "value": 2},
        })
        assert e.remove_rule(rid) is True
        assert e.remove_rule("nonexistent") is False

    def test_remove_fact(self):
        e = self._make()
        fid = e.add_fact({"key": "k", "value": "v"})
        assert e.remove_fact(fid) is True
        assert e.remove_fact("nonexistent") is False

    def test_infer_basic(self):
        e = self._make()
        e.add_rule({
            "condition": {"field": "temp", "op": ">", "value": 30},
            "action": {"type": "assert", "key": "hot", "value": True},
            "priority": 5,
        })
        e.add_fact({"key": "temp", "value": 35})
        result = e.infer({})
        assert "matches" in result
        assert e.get_stats()["inferences_run"] == 1

    def test_infer_no_match(self):
        e = self._make()
        e.add_rule({
            "condition": {"field": "temp", "op": ">", "value": 30},
            "action": {"type": "assert", "key": "hot", "value": True},
        })
        e.add_fact({"key": "temp", "value": 10})
        result = e.infer({})
        assert result["fired_rules"] == []

    def test_infer_retract(self):
        e = self._make()
        fid = e.add_fact({"old_data": True})
        e.add_rule({
            "condition": {"field": "old_data", "op": "==", "value": True},
            "action": {"type": "retract", "key": "old_data"},
        })
        e.infer({})
        assert e.get_stats()["rules_fired"] >= 1

    def test_infer_operators(self):
        e = self._make()
        ops = [
            ("==", "x", 5, 5),
            ("!=", "a", 1, 2),
            ("<", "b", 10, 5),
            ("contains", "d", "hello world", "world"),
        ]
        for op, key, value, fact_val in ops:
            e2 = ExpertSystemEngine()
            e2.add_rule({
                "condition": {"field": key, "op": op, "value": value},
                "action": {"type": "assert", "key": f"res_{key}", "value": True},
            })
            if op == "contains":
                e2.add_fact({"key": key, "value": value})
            else:
                e2.add_fact({"key": key, "value": fact_val})
            r = e2.infer({})
            assert "matches" in r

    def test_explain_inference(self):
        e = self._make()
        e.infer({})
        exp = e.explain_inference()
        assert "explanation" in exp
        assert e.get_stats()["explanations"] == 1

    def test_get_rules(self):
        e = self._make()
        e.add_rule({
            "condition": {"field": "x", "op": "==", "value": 1},
            "action": {"type": "assert", "key": "y", "value": 1},
        })
        rules = e.get_rules()
        assert len(rules) == 1

    def test_get_facts(self):
        e = self._make()
        e.add_fact({"key": "a", "value": 1})
        facts = e.get_facts()
        assert len(facts) == 1

    def test_restart(self):
        e = self._make()
        e.add_rule({
            "condition": {"field": "x", "op": "==", "value": 1},
            "action": {"type": "assert", "key": "y", "value": 1},
        })
        e.add_fact({"key": "x", "value": 1})
        e.restart()
        assert e.get_stats()["rules_added"] == 0
        assert len(e.get_rules()) == 0
        assert len(e.get_facts()) == 0


# =====================================================================
# KnowledgeGraph
# =====================================================================

class TestKnowledgeGraph:
    def _make(self):
        return KnowledgeGraph()

    def test_health_check(self):
        kg = self._make()
        h = kg.health_check()
        assert h["service"] == "knowledge_graph"
        assert h["status"] == "ok"
        assert h["nodes"] == 0

    def test_get_stats_initial(self):
        kg = self._make()
        s = kg.get_stats()
        assert s["nodes_added"] == 0
        assert s["edges_added"] == 0

    def test_kg_add(self):
        kg = self._make()
        eid = kg.kg_add("salon", "contient", "lampe")
        assert eid.startswith("e_")
        assert kg.health_check()["nodes"] == 2
        assert kg.health_check()["edges"] == 1

    def test_kg_add_empty(self):
        kg = self._make()
        eid = kg.kg_add("", "r", "t")
        assert eid == ""

    def test_kg_remove(self):
        kg = self._make()
        eid = kg.kg_add("A", "rel", "B")
        assert kg.kg_remove(eid) is True
        assert kg.kg_remove("nonexistent") is False

    def test_kg_query(self):
        kg = self._make()
        kg.kg_add("salon", "contient", "lampe")
        kg.kg_add("salon", "contient", "tv")
        kg.kg_add("cuisine", "contient", "four")
        results = kg.kg_query({"source": "salon"})
        assert len(results) == 2
        results2 = kg.kg_query({"relation": "contient"})
        assert len(results2) == 3
        results3 = kg.kg_query({"target": "four"})
        assert len(results3) == 1

    def test_kg_query_wildcard(self):
        kg = self._make()
        kg.kg_add("A", "r1", "B")
        kg.kg_add("C", "r2", "D")
        all_edges = kg.kg_query({})
        assert len(all_edges) == 2

    def test_kg_explain(self):
        kg = self._make()
        kg.kg_add("salon", "contient", "lampe")
        exp = kg.kg_explain("salon")
        assert exp["found"] is True
        assert "salon" in exp["explanation"]

    def test_kg_explain_not_found(self):
        kg = self._make()
        exp = kg.kg_explain("inexistant")
        assert exp["found"] is False

    def test_kg_get_node(self):
        kg = self._make()
        kg.kg_add("A", "r", "B")
        node = kg.kg_get_node("A")
        assert node is not None
        assert node["name"] == "A"
        assert kg.kg_get_node("Z") is None

    def test_kg_neighbors(self):
        kg = self._make()
        kg.kg_add("A", "r1", "B")
        kg.kg_add("A", "r2", "C")
        kg.kg_add("D", "r3", "A")
        neighbors = kg.kg_neighbors("A")
        names = {n["node"] for n in neighbors}
        assert "B" in names
        assert "C" in names
        assert "D" in names

    def test_kg_path(self):
        kg = self._make()
        kg.kg_add("A", "r1", "B")
        kg.kg_add("B", "r2", "C")
        kg.kg_add("C", "r3", "D")
        path = kg.kg_path("A", "D")
        assert len(path) == 4
        assert path[0]["node"] == "A"
        assert path[-1]["node"] == "D"

    def test_kg_path_no_route(self):
        kg = self._make()
        kg.kg_add("A", "r", "B")
        kg.kg_add("C", "r", "D")
        path = kg.kg_path("A", "D")
        assert path == []

    def test_kg_path_same_node(self):
        kg = self._make()
        kg.kg_add("A", "r", "B")
        path = kg.kg_path("A", "A")
        assert len(path) == 1

    def test_restart(self):
        kg = self._make()
        kg.kg_add("A", "r", "B")
        kg.restart()
        assert kg.health_check()["nodes"] == 0
        assert kg.get_stats()["edges_added"] == 0


# =====================================================================
# InferenceEngine
# =====================================================================

class TestInferenceEngine:
    def _make(self):
        kg = KnowledgeGraph()
        es = ExpertSystemEngine()
        return InferenceEngine(kg, es)

    def test_health_check(self):
        ie = self._make()
        h = ie.health_check()
        assert h["service"] == "inference_engine"
        assert h["status"] == "ok"

    def test_get_stats_initial(self):
        ie = self._make()
        s = ie.get_stats()
        assert s["total"] == 0

    def test_infer_logical(self):
        ie = self._make()
        r = ie.infer_logical({"subject": "test"})
        assert r["type"] == "logical"
        assert ie.get_stats()["logical"] == 1

    def test_infer_causal(self):
        ie = self._make()
        chain = [
            {"cause": "rain", "effect": "wet", "probability": 0.9},
            {"cause": "wet", "effect": "slip", "probability": 0.5},
        ]
        r = ie.infer_causal(chain)
        assert r["type"] == "causal"
        assert r["chain_length"] == 2
        assert r["final_confidence"] == pytest.approx(0.45, abs=0.01)

    def test_infer_causal_with_kg(self):
        kg = KnowledgeGraph()
        kg.kg_add("rain", "causes", "wet")
        ie = InferenceEngine(kg, ExpertSystemEngine())
        chain = [{"cause": "rain", "effect": "wet", "probability": 0.8}]
        r = ie.infer_causal(chain)
        assert r["links"][0]["kg_validated"] is True

    def test_infer_temporal(self):
        ie = self._make()
        seq = [
            {"event": "wake_up"},
            {"event": "coffee"},
            {"event": "wake_up"},
            {"event": "work"},
        ]
        r = ie.infer_temporal(seq)
        assert r["type"] == "temporal"
        assert r["sequence_length"] == 4
        assert len(r["patterns"]) > 0

    def test_infer_contextual(self):
        ie = self._make()
        r = ie.infer_contextual({"domain": "domotique", "conditions": {"temp": 25}})
        assert r["type"] == "contextual"
        assert r["domain"] == "domotique"

    def test_get_log(self):
        ie = self._make()
        ie.infer_logical({})
        ie.infer_causal([])
        log = ie.get_log()
        assert len(log) == 2

    def test_restart(self):
        ie = self._make()
        ie.infer_logical({})
        ie.restart()
        assert ie.get_stats()["total"] == 0
        assert ie.get_log() == []

    def test_infer_logical_no_deps(self):
        ie = InferenceEngine()
        r = ie.infer_logical({"subject": "test"})
        assert r["type"] == "logical"


# =====================================================================
# CognitiveAgentCore
# =====================================================================

class TestCognitiveAgentCore:
    def _make(self):
        return CognitiveAgentCore()

    def test_health_check(self):
        a = self._make()
        h = a.health_check()
        assert h["service"] == "cognitive_agent_core"
        assert h["status"] == "ok"

    def test_plan_basic(self):
        a = self._make()
        p = a.plan({"goal": "allumer_lumiere", "domain": "domotique"})
        assert p["goal"] == "allumer_lumiere"
        assert p["status"] == "ready"
        assert len(p["steps"]) == 1

    def test_plan_with_steps(self):
        a = self._make()
        p = a.plan({
            "goal": "morning_routine",
            "steps": [
                {"action": "turn_on_light"},
                {"action": "start_coffee"},
                {"action": "read_news"},
            ],
        })
        assert len(p["steps"]) == 3

    def test_execute(self):
        a = self._make()
        p = a.plan({"goal": "test"})
        r = a.execute(p)
        assert r["status"] == "completed"
        assert r["steps_completed"] == 1

    def test_verify_success(self):
        a = self._make()
        p = a.plan({"goal": "test"})
        r = a.execute(p)
        v = a.verify(r)
        assert v["verified"] is True

    def test_verify_failure(self):
        a = self._make()
        v = a.verify({"status": "failed", "results": []})
        assert v["verified"] is False

    def test_recover(self):
        a = self._make()
        r = a.recover({"type": "timeout", "plan_id": "p1"})
        assert r["strategy"] == "retry_with_backoff"
        assert r["status"] == "recovered"

    def test_recover_unknown(self):
        a = self._make()
        r = a.recover({"type": "exotic_error"})
        assert r["strategy"] == "log_and_skip"

    def test_optimize(self):
        a = self._make()
        p = a.plan({
            "goal": "test",
            "steps": [
                {"action": "a"},
                {"action": "a"},
                {"action": "b"},
            ],
        })
        o = a.optimize(p)
        assert o["optimized_steps"] < o["original_steps"]
        assert o["savings"] >= 1

    def test_get_history(self):
        a = self._make()
        a.plan({"goal": "a"})
        a.plan({"goal": "b"})
        h = a.get_history()
        assert len(h) == 2

    def test_restart(self):
        a = self._make()
        a.plan({"goal": "x"})
        a.restart()
        assert a.get_stats()["plans_created"] == 0
        assert a.get_history() == []


# =====================================================================
# MetaCognitionEngine
# =====================================================================

class TestMetaCognitionEngine:
    def _make(self):
        return MetaCognitionEngine()

    def test_health_check(self):
        m = self._make()
        h = m.health_check()
        assert h["service"] == "meta_cognition_engine"
        assert h["status"] == "ok"

    def test_reflect_simple(self):
        m = self._make()
        r = m.reflect({"steps": [{"confidence": 0.9}]})
        assert r["type"] == "reflection"
        assert r["quality"] == "good"

    def test_reflect_complex(self):
        m = self._make()
        steps = [{"confidence": 0.4, "domain": "dom"} for _ in range(6)]
        r = m.reflect({"steps": steps})
        assert r["quality"] == "needs_review"
        obs_types = {o["type"] for o in r["observations"]}
        assert "complexity" in obs_types
        assert "low_confidence" in obs_types

    def test_reflect_domain_bias(self):
        m = self._make()
        steps = [{"confidence": 0.9, "domain": "same"} for _ in range(3)]
        r = m.reflect({"steps": steps})
        obs_types = {o["type"] for o in r["observations"]}
        assert "domain_bias" in obs_types

    def test_meta_reason(self):
        m = self._make()
        r = m.meta_reason({"steps": [
            {"type": "logical"},
            {"type": "causal"},
        ]})
        assert r["type"] == "meta_reasoning"
        assert r["has_logical"] is True
        assert r["has_causal"] is True

    def test_meta_reason_incomplete(self):
        m = self._make()
        r = m.meta_reason({"steps": [{"type": "logical"}]})
        assert "causal" in r["recommendation"]

    def test_enforce_self_consistency_ok(self):
        m = self._make()
        r = m.enforce_self_consistency({"beliefs": {"a": 1, "b": 2}, "decisions": []})
        assert r["consistent"] is True

    def test_enforce_self_consistency_contradiction(self):
        m = self._make()
        r = m.enforce_self_consistency({
            "beliefs": {"hot": True, "not_hot": False},
            "decisions": [],
        })
        assert r["consistent"] is False

    def test_enforce_self_consistency_decision_conflict(self):
        m = self._make()
        r = m.enforce_self_consistency({
            "beliefs": {},
            "decisions": [
                {"target": "lamp", "action": "on"},
                {"target": "lamp", "action": "off"},
            ],
        })
        assert r["consistent"] is False

    def test_self_critique_approved(self):
        m = self._make()
        r = m.self_critique({
            "action": "turn_on",
            "confidence": 0.9,
            "reasoning": "Temperature drop detected",
            "alternatives": ["turn_off"],
        })
        assert r["approved"] is True

    def test_self_critique_rejected(self):
        m = self._make()
        r = m.self_critique({"action": "x", "confidence": 0.2})
        assert r["approved"] is False
        assert len(r["issues"]) > 0

    def test_self_correct(self):
        m = self._make()
        r = m.self_correct({"type": "contradiction"})
        assert r["corrective_action"] == "remove_weaker_belief"
        assert r["status"] == "applied"

    def test_self_correct_unknown(self):
        m = self._make()
        r = m.self_correct({"type": "weird"})
        assert r["corrective_action"] == "log_and_monitor"

    def test_get_reflections(self):
        m = self._make()
        m.reflect({"steps": []})
        m.meta_reason({"steps": []})
        refs = m.get_reflections()
        assert len(refs) == 2

    def test_restart(self):
        m = self._make()
        m.reflect({"steps": []})
        m.restart()
        assert m.get_stats()["reflections"] == 0
        assert m.get_reflections() == []


# =====================================================================
# ProspectiveEngine
# =====================================================================

class TestProspectiveEngine:
    def _make(self):
        return ProspectiveEngine()

    def test_health_check(self):
        p = self._make()
        h = p.health_check()
        assert h["service"] == "prospective_engine"
        assert h["status"] == "ok"

    def test_simulate(self):
        p = self._make()
        r = p.simulate({"id": "p1", "steps": [
            {"action": "a", "risk": 0.1},
            {"action": "b", "risk": 0.2},
        ]})
        assert r["total_risk"] > 0
        assert r["viable"] is True

    def test_simulate_high_risk(self):
        p = self._make()
        r = p.simulate({"steps": [
            {"action": "x", "risk": 0.6},
            {"action": "y", "risk": 0.6},
        ]})
        assert r["viable"] is False

    def test_predict(self):
        p = self._make()
        r = p.predict({"domain": "meteo", "state": {"temp": 20}, "horizon": 3})
        assert len(r["predictions"]) == 3
        assert r["avg_confidence"] > 0

    def test_predict_default_horizon(self):
        p = self._make()
        r = p.predict({"domain": "test"})
        assert len(r["predictions"]) == 3

    def test_generate_futures(self):
        p = self._make()
        r = p.generate_futures({"id": "p1", "steps": [{"action": "a", "risk": 0.1}]}, n=3)
        assert r["futures_count"] == 3
        assert "best_scenario" in r

    def test_compare_futures(self):
        p = self._make()
        futures = [
            {"label": "opt", "risk": 0.1},
            {"label": "pess", "risk": 0.8},
            {"label": "mid", "risk": 0.4},
        ]
        r = p.compare_futures(futures)
        assert r["best"]["label"] == "opt"
        assert r["worst"]["label"] == "pess"
        assert r["spread"] == pytest.approx(0.7, abs=0.01)

    def test_compare_futures_empty(self):
        p = self._make()
        r = p.compare_futures([])
        assert r["comparison"] == "no_futures"

    def test_restart(self):
        p = self._make()
        p.simulate({"steps": []})
        p.restart()
        assert p.get_stats()["simulations"] == 0


# =====================================================================
# DistributedCognitionLayer
# =====================================================================

class TestDistributedCognitionLayer:
    def _make(self):
        return DistributedCognitionLayer()

    def test_health_check(self):
        d = self._make()
        h = d.health_check()
        assert h["service"] == "distributed_cognition"
        assert h["status"] == "ok"
        assert h["agents_total"] == 13

    def test_get_all_agents(self):
        d = self._make()
        agents = d.get_all_agents()
        assert len(agents) == 13
        names = {a["name"] for a in agents}
        assert "domotique" in names
        assert "supervision" in names

    def test_dispatch_known_domain(self):
        d = self._make()
        r = d.dispatch({"domain": "domotique", "action": "allumer"})
        assert r["agent"] == "domotique"
        assert r["status"] == "dispatched"

    def test_dispatch_unknown_domain(self):
        d = self._make()
        r = d.dispatch({"domain": "alien", "action": "fly"})
        assert r["status"] == "dispatched"
        assert r["agent"] is not None

    def test_coordinate(self):
        d = self._make()
        r = d.coordinate(["domotique", "securite", "reseau"], "secure_home")
        assert r["agents_count"] == 3
        assert r["status"] == "coordinated"

    def test_coordinate_empty(self):
        d = self._make()
        r = d.coordinate([], "nothing")
        assert r["status"] == "no_participants"

    def test_consensus(self):
        d = self._make()
        r = d.consensus(["domotique", "securite"], "should_lock?")
        assert r["reached"] is True
        assert r["agreement_ratio"] > 0.5

    def test_consensus_empty(self):
        d = self._make()
        r = d.consensus([], "q")
        assert r["reached"] is False

    def test_share_knowledge(self):
        d = self._make()
        r = d.share_knowledge("domotique", "securite", {"type": "fact", "data": "door_open"})
        assert r["status"] == "shared"

    def test_share_knowledge_unknown_agent(self):
        d = self._make()
        r = d.share_knowledge("unknown", "securite", {})
        assert r["status"] == "agent_not_found"

    def test_get_agent_status(self):
        d = self._make()
        s = d.get_agent_status("domotique")
        assert s["name"] == "domotique"
        assert s["status"] == "active"

    def test_get_agent_status_unknown(self):
        d = self._make()
        s = d.get_agent_status("unknown")
        assert s["status"] == "unknown"

    def test_restart(self):
        d = self._make()
        d.dispatch({"domain": "domotique", "action": "x"})
        d.restart()
        assert d.get_stats()["dispatches"] == 0


# =====================================================================
# GlobalSupervisorV5
# =====================================================================

class TestGlobalSupervisorV5:
    def _make(self):
        mc = MetaCognitionEngine()
        dc = DistributedCognitionLayer()
        return GlobalSupervisorV5(meta_cognition=mc, distributed_cognition=dc)

    def test_health_check(self):
        s = self._make()
        h = s.health_check()
        assert h["service"] == "global_supervisor_v5"
        assert h["status"] == "ok"

    def test_supervise_all(self):
        s = self._make()
        r = s.supervise_all()
        assert r["overall_status"] == "healthy"
        assert r["subsystems_checked"] == 2

    def test_supervise_all_no_deps(self):
        s = GlobalSupervisorV5()
        r = s.supervise_all()
        assert r["subsystems_checked"] == 0

    def test_enforce_global_rules_compliant(self):
        s = self._make()
        r = s.enforce_global_rules({"actions": [], "decisions": []})
        assert r["compliant"] is True

    def test_enforce_global_rules_high_risk(self):
        s = self._make()
        r = s.enforce_global_rules({
            "actions": [{"action": "delete_all", "risk": 0.95}],
            "decisions": [],
        })
        assert r["compliant"] is False
        assert any(v["rule"] == "safety_first" for v in r["violations"])

    def test_enforce_global_rules_no_reasoning(self):
        s = self._make()
        r = s.enforce_global_rules({
            "actions": [],
            "decisions": [{"action": "x"}],
        })
        assert r["compliant"] is False

    def test_resolve_global_conflicts(self):
        s = self._make()
        r = s.resolve_global_conflicts([
            {"type": "contradiction"},
            {"type": "decision_conflict"},
        ])
        assert r["all_resolved"] is True
        assert len(r["resolutions"]) == 2

    def test_resolve_global_conflicts_empty(self):
        s = self._make()
        r = s.resolve_global_conflicts([])
        assert r["all_resolved"] is True

    def test_validate_decision_approved(self):
        s = self._make()
        r = s.validate_decision({
            "action": "turn_on",
            "confidence": 0.9,
            "risk": 0.1,
            "reasoning": "cold room",
        })
        assert r["approved"] is True

    def test_validate_decision_rejected_low_confidence(self):
        s = self._make()
        r = s.validate_decision({
            "action": "x",
            "confidence": 0.1,
            "risk": 0.1,
            "reasoning": "test",
        })
        assert r["approved"] is False

    def test_validate_decision_rejected_high_risk(self):
        s = self._make()
        r = s.validate_decision({
            "action": "x",
            "confidence": 0.9,
            "risk": 0.9,
            "reasoning": "test",
        })
        assert r["approved"] is False

    def test_get_supervision_log(self):
        s = self._make()
        s.supervise_all()
        log = s.get_supervision_log()
        assert len(log) == 1

    def test_restart(self):
        s = self._make()
        s.supervise_all()
        s.restart()
        assert s.get_stats()["supervisions"] == 0


# =====================================================================
# ExplainabilityEngineV5
# =====================================================================

class TestExplainabilityEngineV5:
    def _make(self):
        kg = KnowledgeGraph()
        ie = InferenceEngine(kg)
        return ExplainabilityEngineV5(knowledge_graph=kg, inference_engine=ie)

    def test_health_check(self):
        e = self._make()
        h = e.health_check()
        assert h["service"] == "explainability_v5"
        assert h["status"] == "ok"

    def test_explain_decision(self):
        e = self._make()
        r = e.explain_decision({
            "action": "allumer_lampe",
            "reasoning": "Il fait sombre",
            "confidence": 0.85,
        })
        assert r["type"] == "decision"
        assert "allumer_lampe" in r["text"]

    def test_explain_decision_with_alternatives(self):
        e = self._make()
        r = e.explain_decision({
            "action": "heat",
            "reasoning": "cold",
            "confidence": 0.7,
            "alternatives": ["open_window", "blanket"],
        })
        assert "Alternatives" in r["text"]

    def test_explain_inference_logical(self):
        e = self._make()
        r = e.explain_inference({"type": "logical", "conclusions": [{"fact": "hot"}]})
        assert r["type"] == "inference"
        assert r["inference_type"] == "logical"

    def test_explain_inference_causal(self):
        e = self._make()
        r = e.explain_inference({
            "type": "causal",
            "links": [{"cause": "rain", "effect": "wet", "probability": 0.9}],
        })
        assert "rain" in r["text"]

    def test_explain_inference_temporal(self):
        e = self._make()
        r = e.explain_inference({
            "type": "temporal",
            "patterns": [{"pattern": "recurring", "event": "wake_up"}],
        })
        assert "temporal" in r["inference_type"]

    def test_explain_future(self):
        e = self._make()
        r = e.explain_future({
            "label": "optimiste",
            "risk": 0.15,
            "viable": True,
        })
        assert r["type"] == "future"
        assert "optimiste" in r["text"]

    def test_explain_future_with_steps(self):
        e = self._make()
        r = e.explain_future({
            "label": "x",
            "risk": 0.5,
            "viable": True,
            "steps": [{"step": 0, "action": "do_thing", "cumulative_risk": 0.1}],
        })
        assert "do_thing" in r["text"]

    def test_explain_conflict(self):
        e = self._make()
        r = e.explain_conflict({
            "type": "contradiction",
            "detail": "A vs B",
            "resolution": "remove_weaker",
            "severity": "high",
        })
        assert r["type"] == "conflict"
        assert "contradiction" in r["text"]

    def test_explain_full(self):
        e = self._make()
        r = e.explain_full({
            "decisions": [{"action": "x", "reasoning": "y", "confidence": 0.8}],
            "inferences": [{"type": "logical", "conclusions": []}],
            "futures": [{"label": "f", "risk": 0.1, "viable": True}],
            "conflicts": [{"type": "t", "resolution": "r"}],
        })
        assert r["type"] == "full"
        assert r["sections"] == 4

    def test_explain_full_empty(self):
        e = self._make()
        r = e.explain_full({})
        assert r["sections"] == 0

    def test_get_explanations(self):
        e = self._make()
        e.explain_decision({"action": "a", "confidence": 0.5})
        e.explain_decision({"action": "b", "confidence": 0.6})
        exps = e.get_explanations()
        assert len(exps) == 2

    def test_restart(self):
        e = self._make()
        e.explain_decision({"action": "x", "confidence": 0.5})
        e.restart()
        assert e.get_stats()["decisions_explained"] == 0
        assert e.get_explanations() == []


# =====================================================================
# Tests d'intégration inter-modules v15
# =====================================================================

class TestV15Integration:
    """Tests d'intégration entre les modules v15."""

    def _make_all(self):
        es = ExpertSystemEngine()
        kg = KnowledgeGraph()
        ie = InferenceEngine(kg, es)
        ca = CognitiveAgentCore(inference_engine=ie)
        mc = MetaCognitionEngine()
        pe = ProspectiveEngine(inference_engine=ie)
        dc = DistributedCognitionLayer()
        sv = GlobalSupervisorV5(meta_cognition=mc, distributed_cognition=dc)
        ev = ExplainabilityEngineV5(knowledge_graph=kg, inference_engine=ie)
        return es, kg, ie, ca, mc, pe, dc, sv, ev

    def test_full_pipeline_plan_simulate_explain(self):
        """Plan → Simulate → Explain end-to-end."""
        es, kg, ie, ca, mc, pe, dc, sv, ev = self._make_all()

        plan = ca.plan({"goal": "sécuriser_maison", "steps": [
            {"action": "verrouiller_portes", "risk": 0.05},
            {"action": "activer_alarme", "risk": 0.1},
        ]})
        assert plan["status"] == "ready"

        sim = pe.simulate(plan)
        assert sim["viable"] is True

        result = ca.execute(plan)
        assert result["status"] == "completed"

        verification = ca.verify(result)
        assert verification["verified"] is True

        explanation = ev.explain_decision({
            "action": plan["goal"],
            "reasoning": "Night mode",
            "confidence": 0.9,
        })
        assert "sécuriser_maison" in explanation["text"]

    def test_kg_inference_chain(self):
        """KG → Inference → Explain."""
        _, kg, ie, _, _, _, _, _, ev = self._make_all()

        kg.kg_add("pluie", "causes", "sol_mouillé")
        kg.kg_add("sol_mouillé", "causes", "glissade")

        causal = ie.infer_causal([
            {"cause": "pluie", "effect": "sol_mouillé", "probability": 0.9},
            {"cause": "sol_mouillé", "effect": "glissade", "probability": 0.6},
        ])
        assert causal["links"][0]["kg_validated"] is True
        assert causal["final_confidence"] < 0.6

        exp = ev.explain_inference(causal)
        assert "pluie" in exp["text"]

    def test_metacognition_supervision_loop(self):
        """MetaCog → Supervisor → Resolve."""
        _, _, _, _, mc, _, _, sv, _ = self._make_all()

        reflection = mc.reflect({"steps": [
            {"confidence": 0.3, "domain": "x"},
            {"confidence": 0.4, "domain": "x"},
            {"confidence": 0.35, "domain": "x"},
        ]})
        assert reflection["quality"] == "needs_review"

        supervision = sv.supervise_all()
        assert supervision["overall_status"] == "healthy"

        validation = sv.validate_decision({
            "action": "risky_move",
            "confidence": 0.2,
            "risk": 0.8,
            "reasoning": "test",
        })
        assert validation["approved"] is False

    def test_distributed_dispatch_and_consensus(self):
        """Dispatch → Coordinate → Consensus."""
        _, _, _, _, _, _, dc, _, _ = self._make_all()

        r1 = dc.dispatch({"domain": "domotique", "action": "turn_on"})
        assert r1["status"] == "dispatched"

        coord = dc.coordinate(["domotique", "securite"], "protect_home")
        assert coord["status"] == "coordinated"

        cons = dc.consensus(["domotique", "securite", "reseau"], "enable_firewall?")
        assert cons["reached"] is True

    def test_futures_comparison_with_explain(self):
        """Generate futures → Compare → Explain best."""
        _, _, _, _, _, pe, _, _, ev = self._make_all()

        futures_result = pe.generate_futures({
            "id": "p1",
            "steps": [{"action": "a", "risk": 0.2}],
        }, n=3)
        assert futures_result["futures_count"] == 3

        comparison = pe.compare_futures(futures_result["futures"])
        best = comparison["best"]

        exp = ev.explain_future({
            "label": best["label"],
            "risk": best["risk"],
            "viable": True,
        })
        assert exp["type"] == "future"

    def test_expert_inference_explainability(self):
        """Expert system → Inference → Explain."""
        es, _, ie, _, _, _, _, _, ev = self._make_all()

        es.add_rule({
            "condition": {"field": "humidity", "op": ">", "value": 80},
            "action": {"type": "assert", "key": "dehumidify", "value": True},
            "priority": 10,
        })
        es.add_fact({"humidity": 90})
        expert_result = es.infer({})
        assert len(expert_result["fired_rules"]) > 0

        logical = ie.infer_logical({"subject": "humidity"})
        assert logical["type"] == "logical"

        exp = ev.explain_inference(logical)
        assert exp["type"] == "inference"

    def test_all_modules_health_check(self):
        """Tous les modules v15 passent le health_check."""
        modules = self._make_all()
        for mod in modules:
            h = mod.health_check()
            assert h["status"] == "ok", f"{type(mod).__name__} health failed"

    def test_all_modules_restart(self):
        """Tous les modules v15 supportent restart."""
        modules = self._make_all()
        for mod in modules:
            mod.restart()
            stats = mod.get_stats()
            for v in stats.values():
                assert v == 0, f"{type(mod).__name__} stats not reset"

    def test_self_consistency_to_correction(self):
        """Consistency check → Self-critique → Self-correction."""
        _, _, _, _, mc, _, _, _, _ = self._make_all()

        state = {
            "beliefs": {"safe": True, "not_safe": True},
            "decisions": [],
        }
        consistency = mc.enforce_self_consistency(state)
        assert consistency["consistent"] is False

        for conflict in consistency["conflicts"]:
            correction = mc.self_correct(conflict)
            assert correction["status"] == "applied"

    def test_full_explain_session(self):
        """explain_full with all section types."""
        _, _, _, ca, _, pe, _, _, ev = self._make_all()

        plan = ca.plan({"goal": "test"})
        result = ca.execute(plan)
        sim = pe.simulate(plan)

        session = {
            "decisions": [{"action": "test", "reasoning": "r", "confidence": 0.8}],
            "inferences": [{"type": "logical", "conclusions": ["a"]}],
            "futures": [{"label": "f", "risk": 0.1, "viable": True}],
            "conflicts": [{"type": "c", "resolution": "r"}],
        }
        full = ev.explain_full(session)
        assert full["sections"] == 4
        assert full["type"] == "full"
