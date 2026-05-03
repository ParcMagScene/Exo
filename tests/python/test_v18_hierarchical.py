"""
Tests EXO v18 — Cognition hiérarchique multi-niveaux.
Couvre : MacroAgentLayer, MicroAgentLayer, CognitiveLayerStack,
         VerticalReasoningFlow, HierarchicalSupervisor,
         PriorityEngine, LayeredConsistencyEngine,
         LayeredExplainabilityEngine.
"""

import sys, os, time

import pytest
from macro_agent_layer import MacroAgentLayer
from micro_agent_layer import MicroAgentLayer
from cognitive_layer_stack import CognitiveLayerStack
from vertical_reasoning_flow import VerticalReasoningFlow
from hierarchical_supervisor import HierarchicalSupervisor
from priority_engine import PriorityEngine
from layered_consistency_engine import LayeredConsistencyEngine
from layered_explainability_engine import LayeredExplainabilityEngine


# ── Fixtures ────────────────────────────────────────────────
@pytest.fixture
def macro():
    return MacroAgentLayer()

@pytest.fixture
def micro():
    return MicroAgentLayer()

@pytest.fixture
def stack(macro, micro):
    return CognitiveLayerStack(macro_layer=macro, micro_layer=micro)

@pytest.fixture
def flow(stack):
    return VerticalReasoningFlow(layer_stack=stack)

@pytest.fixture
def supervisor(stack, macro, micro):
    return HierarchicalSupervisor(
        layer_stack=stack, macro_layer=macro, micro_layer=micro)

@pytest.fixture
def priority(stack, macro, micro):
    return PriorityEngine(
        layer_stack=stack, macro_layer=macro, micro_layer=micro)

@pytest.fixture
def consistency(stack, macro, micro, supervisor):
    return LayeredConsistencyEngine(
        layer_stack=stack, macro_layer=macro,
        micro_layer=micro, supervisor=supervisor)

@pytest.fixture
def explainability(stack, macro, micro, flow, supervisor):
    return LayeredExplainabilityEngine(
        layer_stack=stack, macro_layer=macro, micro_layer=micro,
        vertical_flow=flow, supervisor=supervisor)


# ═══════════════════════════════════════════════════════════
# MacroAgentLayer
# ═══════════════════════════════════════════════════════════
class TestMacroAgentLayer:
    def test_macro_handle_domotique(self, macro):
        r = macro.macro_handle({"text": "allume la lumière du salon", "domain": "domotique"})
        assert r["handled"] is True
        assert r["macro_agent"] == "domotique"
        assert r["id"].startswith("mh_")

    def test_macro_handle_unknown_domain(self, macro):
        r = macro.macro_handle({"text": "fais quelque chose"})
        assert r["handled"] is True
        assert "macro_agent" in r

    def test_macro_delegate(self, macro):
        r = macro.macro_delegate({"task": "scan réseau", "macro": "reseau"})
        assert r["delegated"] is True
        assert r["id"].startswith("md_")

    def test_macro_collect(self, macro):
        results = [
            {"macro": "domotique", "result": "ok"},
            {"macro": "réseau", "result": "ok"},
        ]
        r = macro.macro_collect(results)
        assert r["total_results"] == 2
        assert r["id"].startswith("mc_")

    def test_register_macro(self, macro):
        r = macro.register_macro("test_macro", {"domain": "test"})
        assert r["registered"] is True
        macros = macro.list_macros()
        names = [m["name"] for m in macros]
        assert "test_macro" in names

    def test_list_macros_defaults(self, macro):
        macros = macro.list_macros()
        assert len(macros) >= 7
        names = [m["name"] for m in macros]
        assert "domotique" in names

    def test_health_check(self, macro):
        h = macro.health_check()
        assert h["service"] == "macro_agent_layer"
        assert h["status"] == "ok"

    def test_restart(self, macro):
        macro.macro_handle({"text": "test", "domain": "domotique"})
        macro.restart()
        assert macro.get_stats()["intents_handled"] == 0

    def test_stats_increment(self, macro):
        macro.macro_handle({"text": "test"})
        macro.macro_delegate({"task": "x"})
        s = macro.get_stats()
        assert s["intents_handled"] == 1
        assert s["tasks_delegated"] == 1


# ═══════════════════════════════════════════════════════════
# MicroAgentLayer
# ═══════════════════════════════════════════════════════════
class TestMicroAgentLayer:
    def test_micro_execute_known(self, micro):
        r = micro.micro_execute({"action": "scan_network", "params": {}})
        assert r["executed"] is True
        assert r["micro"] == "scan_network"
        assert r["id"].startswith("mx_")

    def test_micro_execute_routed(self, micro):
        r = micro.micro_execute({"text": "éteindre le ventilateur", "domain": "domotique"})
        assert r["executed"] is True
        assert r["micro"] == "toggle_device"

    def test_micro_execute_unknown_action(self, micro):
        r = micro.micro_execute({"action": "nonexistent", "text": "hello"})
        assert r["executed"] is True

    def test_micro_report(self, micro):
        micro.micro_execute({"action": "ping_device"})
        r = micro.micro_report()
        assert r["total_agents"] >= 10
        assert r["id"].startswith("mr_")

    def test_micro_error(self, micro):
        r = micro.micro_error()
        assert "errors" in r
        assert "total_errors" in r

    def test_register_micro(self, micro):
        r = micro.register_micro("custom_micro", {"desc": "test"})
        assert r["registered"] is True
        micros = micro.list_micros()
        names = [m["name"] for m in micros]
        assert "custom_micro" in names

    def test_health_check(self, micro):
        h = micro.health_check()
        assert h["service"] == "micro_agent_layer"
        assert h["status"] == "ok"

    def test_restart(self, micro):
        micro.micro_execute({"action": "scan_network"})
        micro.restart()
        assert micro.get_stats()["tasks_executed"] == 0

    def test_latency_tracking(self, micro):
        micro.micro_execute({"action": "ping_device"})
        micros = micro.list_micros()
        ping = [m for m in micros if m["name"] == "ping_device"][0]
        assert ping["executions"] == 1
        assert ping["avg_latency_ms"] >= 0


# ═══════════════════════════════════════════════════════════
# CognitiveLayerStack
# ═══════════════════════════════════════════════════════════
class TestCognitiveLayerStack:
    def test_push_valid_layer(self, stack):
        r = stack.push_to_layer("perception", {"signal": "audio"})
        assert r["pushed"] is True
        assert r["layer"] == "perception"
        assert r["layer_index"] == 0

    def test_push_invalid_layer(self, stack):
        r = stack.push_to_layer("nonexistent", {"data": "x"})
        assert r["pushed"] is False
        assert "reason" in r

    def test_pull_from_layer(self, stack):
        stack.push_to_layer("extraction", {"data": "entities"})
        r = stack.pull_from_layer("extraction")
        assert r["pulled"] is True
        assert r["count"] >= 1

    def test_pull_invalid_layer(self, stack):
        r = stack.pull_from_layer("fake")
        assert r["pulled"] is False

    def test_propagate_up(self, stack):
        r = stack.propagate_up({"source": "microphone"})
        assert r["direction"] == "up"
        assert r["layers_traversed"] == 9

    def test_propagate_down(self, stack):
        r = stack.propagate_down({"goal": "répondre à l'utilisateur"})
        assert r["direction"] == "down"
        assert r["layers_traversed"] == 9

    def test_list_layers(self, stack):
        layers = stack.list_layers()
        assert len(layers) == 9
        assert layers[0]["name"] == "perception"
        assert layers[-1]["name"] == "supervision"

    def test_get_layer_state(self, stack):
        s = stack.get_layer_state("decision")
        assert s["name"] == "decision"
        assert s["active"] is True

    def test_get_layer_state_invalid(self, stack):
        s = stack.get_layer_state("invalid")
        assert "error" in s

    def test_health_check(self, stack):
        h = stack.health_check()
        assert h["service"] == "cognitive_layer_stack"
        assert h["active_layers"] == 9

    def test_restart(self, stack):
        stack.push_to_layer("perception", {"x": 1})
        stack.restart()
        assert stack.get_stats()["pushes"] == 0


# ═══════════════════════════════════════════════════════════
# VerticalReasoningFlow
# ═══════════════════════════════════════════════════════════
class TestVerticalReasoningFlow:
    def test_reason_bottom_up(self, flow):
        r = flow.reason_bottom_up({"source": "capteur température"})
        assert r["direction"] == "bottom_up"
        assert r["completed"] is True
        assert r["layers_traversed"] == 9

    def test_reason_top_down(self, flow):
        r = flow.reason_top_down({"goal": "éteindre les lumières"})
        assert r["direction"] == "top_down"
        assert r["completed"] is True
        assert r["layers_traversed"] == 9

    def test_merge_vertical_flows(self, flow):
        flow.reason_bottom_up({"source": "audio"})
        flow.reason_top_down({"goal": "répondre"})
        r = flow.merge_vertical_flows()
        assert r["merged"] is True
        assert r["bottom_up_count"] >= 1
        assert r["top_down_count"] >= 1

    def test_get_flow_history(self, flow):
        flow.reason_bottom_up({"source": "test"})
        flow.reason_top_down({"goal": "test"})
        h = flow.get_flow_history()
        assert len(h) >= 2

    def test_health_check(self, flow):
        h = flow.health_check()
        assert h["service"] == "vertical_reasoning_flow"
        assert h["status"] == "ok"

    def test_restart(self, flow):
        flow.reason_bottom_up({"source": "x"})
        flow.restart()
        assert flow.get_stats()["bottom_up_flows"] == 0

    def test_stats_increment(self, flow):
        flow.reason_bottom_up({"source": "a"})
        flow.reason_top_down({"goal": "b"})
        flow.merge_vertical_flows()
        s = flow.get_stats()
        assert s["bottom_up_flows"] == 1
        assert s["top_down_flows"] == 1
        assert s["merges"] == 1


# ═══════════════════════════════════════════════════════════
# HierarchicalSupervisor
# ═══════════════════════════════════════════════════════════
class TestHierarchicalSupervisor:
    def test_supervise_layer(self, supervisor):
        r = supervisor.supervise_layer({"layer": "perception"})
        assert r["supervised"] is True
        assert r["target_type"] == "layer"
        assert r["target"] == "perception"

    def test_supervise_macro(self, supervisor):
        r = supervisor.supervise_macro({"name": "domotique"})
        assert r["supervised"] is True
        assert r["target_type"] == "macro"

    def test_supervise_micro(self, supervisor):
        r = supervisor.supervise_micro({"name": "scan_network"})
        assert r["supervised"] is True
        assert r["target_type"] == "micro"

    def test_enforce_hierarchy_rules(self, supervisor):
        r = supervisor.enforce_hierarchy_rules()
        assert r["enforced"] is True
        assert "rules_checked" in r
        assert r["all_passed"] is True

    def test_get_supervision_report(self, supervisor):
        supervisor.supervise_layer({"layer": "decision"})
        r = supervisor.get_supervision_report()
        assert r["supervision_entries"] >= 1

    def test_health_check(self, supervisor):
        h = supervisor.health_check()
        assert h["service"] == "hierarchical_supervisor"
        assert h["status"] == "ok"

    def test_restart(self, supervisor):
        supervisor.supervise_layer({"layer": "perception"})
        supervisor.restart()
        assert supervisor.get_stats()["layers_supervised"] == 0


# ═══════════════════════════════════════════════════════════
# PriorityEngine
# ═══════════════════════════════════════════════════════════
class TestPriorityEngine:
    def test_set_priority(self, priority):
        r = priority.set_priority({"name": "perception", "type": "layer"}, "high")
        assert r["set"] is True
        assert r["level"] == "high"
        assert r["numeric"] == 4

    def test_adjust_priority_up(self, priority):
        priority.set_priority({"name": "extraction", "type": "layer"}, "normal")
        r = priority.adjust_priority({"name": "extraction", "direction": "up"})
        assert r["adjusted"] is True
        assert r["new_level"] == 4
        assert r["level_name"] == "high"

    def test_adjust_priority_down(self, priority):
        priority.set_priority({"name": "test_e", "type": "layer"}, "high")
        r = priority.adjust_priority({"name": "test_e", "direction": "down"})
        assert r["adjusted"] is True
        assert r["new_level"] == 3

    def test_adjust_auto_create(self, priority):
        r = priority.adjust_priority({"name": "new_entity", "direction": "up"})
        assert r["adjusted"] is True

    def test_compute_priority_map(self, priority):
        priority.set_priority({"name": "a", "type": "layer"}, "critical")
        priority.set_priority({"name": "b", "type": "macro"}, "low")
        r = priority.compute_priority_map()
        assert r["computed"] is True
        assert r["total_entities"] >= 2
        assert r["critical_count"] >= 1

    def test_get_entity_priority(self, priority):
        priority.set_priority({"name": "test_p", "type": "layer"}, "high")
        r = priority.get_entity_priority("test_p")
        assert r["found"] is True
        assert r["level"] == "high"

    def test_get_entity_not_found(self, priority):
        r = priority.get_entity_priority("nonexistent")
        assert r["found"] is False

    def test_reset_priorities(self, priority):
        priority.set_priority({"name": "x", "type": "layer"}, "critical")
        r = priority.reset_priorities()
        assert r["reset"] is True
        p = priority.get_entity_priority("x")
        assert p["level"] == "normal"

    def test_health_check(self, priority):
        h = priority.health_check()
        assert h["service"] == "priority_engine"
        assert h["status"] == "ok"

    def test_restart(self, priority):
        priority.set_priority({"name": "a"}, "high")
        priority.restart()
        assert priority.get_stats()["priorities_set"] == 0


# ═══════════════════════════════════════════════════════════
# LayeredConsistencyEngine
# ═══════════════════════════════════════════════════════════
class TestLayeredConsistencyEngine:
    def test_check_layer_consistency(self, consistency):
        r = consistency.check_layer_consistency()
        assert r["checked"] is True
        assert r["all_consistent"] is True
        assert r["total_checks"] >= 1

    def test_enforce_layer_consistency(self, consistency):
        r = consistency.enforce_layer_consistency()
        assert r["enforced"] is True

    def test_check_cross_level(self, consistency):
        r = consistency.check_cross_level()
        assert r["checked"] is True
        assert r["all_consistent"] is True

    def test_get_consistency_report(self, consistency):
        consistency.check_layer_consistency()
        r = consistency.get_consistency_report()
        assert r["checks_total"] >= 1

    def test_health_check(self, consistency):
        h = consistency.health_check()
        assert h["service"] == "layered_consistency"
        assert h["status"] == "ok"

    def test_restart(self, consistency):
        consistency.check_layer_consistency()
        consistency.restart()
        assert consistency.get_stats()["checks_performed"] == 0


# ═══════════════════════════════════════════════════════════
# LayeredExplainabilityEngine
# ═══════════════════════════════════════════════════════════
class TestLayeredExplainabilityEngine:
    def test_explain_layer(self, explainability):
        r = explainability.explain_layer({"layer": "perception"})
        assert r["type"] == "layer"
        assert r["target"] == "perception"
        assert "explanation" in r

    def test_explain_macro(self, explainability):
        r = explainability.explain_macro({"name": "domotique", "domain": "domotique"})
        assert r["type"] == "macro"
        assert "explanation" in r

    def test_explain_micro(self, explainability):
        r = explainability.explain_micro({"name": "scan_network"})
        assert r["type"] == "micro"
        assert "explanation" in r

    def test_explain_vertical_flow(self, explainability):
        r = explainability.explain_vertical_flow()
        assert r["type"] == "vertical_flow"
        assert "explanation" in r

    def test_explain_decision(self, explainability):
        r = explainability.explain_decision({
            "action": "allumer_salon",
            "source": "macro_domotique",
            "reason": "utilisateur a demandé",
        })
        assert r["type"] == "decision"
        assert "explanation" in r

    def test_get_explanation_history(self, explainability):
        explainability.explain_layer({"layer": "perception"})
        explainability.explain_macro({"name": "réseau"})
        h = explainability.get_explanation_history()
        assert len(h) >= 2

    def test_health_check(self, explainability):
        h = explainability.health_check()
        assert h["service"] == "layered_explainability"
        assert h["status"] == "ok"

    def test_restart(self, explainability):
        explainability.explain_layer({"layer": "perception"})
        explainability.restart()
        assert explainability.get_stats()["layer_explanations"] == 0

    def test_stats_track_all(self, explainability):
        explainability.explain_layer({"layer": "perception"})
        explainability.explain_macro({"name": "test"})
        explainability.explain_micro({"name": "test"})
        explainability.explain_vertical_flow()
        explainability.explain_decision({"action": "x"})
        s = explainability.get_stats()
        assert s["layer_explanations"] == 1
        assert s["macro_explanations"] == 1
        assert s["micro_explanations"] == 1
        assert s["flow_explanations"] == 1
        assert s["decision_explanations"] == 1


# ═══════════════════════════════════════════════════════════
# Cross-module integration
# ═══════════════════════════════════════════════════════════
class TestV18Integration:
    def test_full_pipeline_bottom_up(self, macro, micro, stack, flow,
                                      supervisor, explainability):
        """Pipeline complet : micro → macro → stack → flow → explain."""
        # 1. Micro exécute
        mr = micro.micro_execute({"action": "read_sensor", "domain": "domotique"})
        assert mr["executed"] is True

        # 2. Macro traite
        mh = macro.macro_handle({"text": "température détectée", "domain": "domotique"})
        assert mh["handled"] is True

        # 3. Stack push
        sp = stack.push_to_layer("perception", {"signal": "temp_28C"})
        assert sp["pushed"] is True

        # 4. Flow bottom-up
        bu = flow.reason_bottom_up({"source": "temp_sensor"})
        assert bu["completed"] is True

        # 5. Superviser
        sv = supervisor.supervise_layer({"layer": "perception"})
        assert sv["supervised"] is True

        # 6. Expliquer
        ex = explainability.explain_layer({"layer": "perception"})
        assert "explanation" in ex

    def test_full_pipeline_top_down(self, macro, stack, flow,
                                     supervisor, priority):
        """Pipeline descendant : goal → flow → stack → macro."""
        # 1. Set priority
        pr = priority.set_priority(
            {"name": "decision", "type": "layer"}, "critical")
        assert pr["set"] is True

        # 2. Flow top-down
        td = flow.reason_top_down({"goal": "éteindre toutes les lumières"})
        assert td["completed"] is True

        # 3. Stack propagate down
        pd = stack.propagate_down({"directive": "extinction générale"})
        assert pd["direction"] == "down"

        # 4. Macro delegate
        md = macro.macro_delegate({"task": "extinction", "macro": "domotique"})
        assert md["delegated"] is True

        # 5. Enforce rules
        hr = supervisor.enforce_hierarchy_rules()
        assert hr["enforced"] is True

    def test_consistency_after_operations(self, macro, micro, stack,
                                           consistency):
        """Après opérations, la cohérence reste intacte."""
        macro.macro_handle({"text": "test", "domain": "cognition"})
        micro.micro_execute({"action": "scan_network"})
        stack.push_to_layer("extraction", {"data": "test"})

        r = consistency.check_layer_consistency()
        assert r["all_consistent"] is True

        xl = consistency.check_cross_level()
        assert xl["all_consistent"] is True
