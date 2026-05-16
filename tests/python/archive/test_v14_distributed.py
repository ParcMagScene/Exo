"""
EXO v14 — Tests : Cognition distribuée, agents spécialisés,
communication inter-agents, supervision multi-niveaux, cohérence globale.
"""

import sys
import os
import time
import pytest


# ═══════════════════════════════════════════════════════════
#  1. AgentMessagingBus
# ═══════════════════════════════════════════════════════════

class TestAgentMessagingBus:

    def _make(self):
        from agent_messaging_bus import AgentMessagingBus
        return AgentMessagingBus()

    # -- channels --
    def test_register_channel(self):
        bus = self._make()
        assert bus.register_channel("agent_a") is True
        assert bus.get_stats()["channels_active"] == 1

    def test_register_channel_idempotent(self):
        bus = self._make()
        bus.register_channel("a")
        assert bus.register_channel("a") is True  # already registered

    def test_register_channel_empty_name(self):
        bus = self._make()
        assert bus.register_channel("") is False

    def test_unregister_channel(self):
        bus = self._make()
        bus.register_channel("x")
        assert bus.unregister_channel("x") is True
        assert bus.get_stats()["channels_active"] == 0

    def test_unregister_unknown_channel(self):
        bus = self._make()
        assert bus.unregister_channel("nope") is False

    # -- send --
    def test_send_basic(self):
        bus = self._make()
        bus.register_channel("a")
        bus.register_channel("b")
        result = bus.send("a", "b", {"type": "info", "payload": {"x": 1}})
        assert result["delivered"] is True
        assert "message_id" in result

    def test_send_invalid_type(self):
        bus = self._make()
        bus.register_channel("a")
        bus.register_channel("b")
        result = bus.send("a", "b", {"type": "bad_type"})
        assert result["delivered"] is False
        assert result["reason"] == "invalid_message_type"

    def test_send_unknown_recipient(self):
        bus = self._make()
        bus.register_channel("a")
        result = bus.send("a", "ghost", {"type": "info"})
        assert result["delivered"] is False

    def test_send_updates_stats(self):
        bus = self._make()
        bus.register_channel("a")
        bus.register_channel("b")
        bus.send("a", "b", {"type": "info"})
        assert bus.get_stats()["messages_sent"] == 1

    # -- receive --
    def test_receive_consumes_messages(self):
        bus = self._make()
        bus.register_channel("a")
        bus.register_channel("b")
        bus.send("a", "b", {"type": "info", "payload": {"v": 1}})
        msgs = bus.receive("b")
        assert len(msgs) == 1
        assert msgs[0]["sender"] == "a"
        # second receive is empty
        assert bus.receive("b") == []

    def test_receive_empty_mailbox(self):
        bus = self._make()
        assert bus.receive("nobody") == []

    # -- peek --
    def test_peek_does_not_consume(self):
        bus = self._make()
        bus.register_channel("a")
        bus.register_channel("b")
        bus.send("a", "b", {"type": "info"})
        p = bus.peek("b")
        assert len(p) == 1
        assert len(bus.peek("b")) == 1  # still there

    # -- broadcast --
    def test_broadcast_all_except_sender(self):
        bus = self._make()
        bus.register_channel("a")
        bus.register_channel("b")
        bus.register_channel("c")
        results = bus.broadcast("a", {"type": "alert", "payload": {}})
        delivered = [r for r in results if r.get("delivered")]
        assert len(delivered) == 2
        assert bus.get_stats()["messages_broadcast"] == 1

    # -- message log --
    def test_get_message_log(self):
        bus = self._make()
        bus.register_channel("a")
        bus.register_channel("b")
        bus.send("a", "b", {"type": "info"})
        bus.send("b", "a", {"type": "response"})
        log = bus.get_message_log(10)
        assert len(log) == 2

    # -- health / restart --
    def test_health_check(self):
        bus = self._make()
        h = bus.health_check()
        assert h["service"] == "agent_messaging_bus"
        assert h["status"] == "ok"

    def test_restart_clears(self):
        bus = self._make()
        bus.register_channel("a")
        bus.register_channel("b")
        bus.send("a", "b", {"type": "info"})
        bus.restart()
        assert bus.get_stats()["messages_sent"] == 0
        assert bus.receive("b") == []

    def test_get_stats_keys(self):
        bus = self._make()
        keys = set(bus.get_stats().keys())
        assert "messages_sent" in keys
        assert "channels_active" in keys


# ═══════════════════════════════════════════════════════════
#  2. AgentRegistry
# ═══════════════════════════════════════════════════════════

class TestAgentRegistry:

    def _make(self):
        from agent_registry import AgentRegistry
        return AgentRegistry()

    def _agent(self, name="test", domain="test"):
        from specialized_agents import SpecializedAgent
        a = SpecializedAgent()
        a.name = name
        a.domain = domain
        return a

    def test_register_agent(self):
        reg = self._make()
        a = self._agent("domo", "domotique")
        assert reg.register_agent(a) is True
        assert reg.get_stats()["agents_active"] == 1

    def test_register_agent_no_name(self):
        reg = self._make()
        a = self._agent("")
        assert reg.register_agent(a) is False

    def test_register_replaces_existing(self):
        reg = self._make()
        a1 = self._agent("domo")
        a2 = self._agent("domo")
        reg.register_agent(a1)
        reg.register_agent(a2)
        assert reg.get_stats()["agents_active"] == 1
        assert reg.get_agent("domo") is a2

    def test_unregister_agent(self):
        reg = self._make()
        reg.register_agent(self._agent("x"))
        assert reg.unregister_agent("x") is True
        assert reg.get_agent("x") is None

    def test_unregister_unknown(self):
        reg = self._make()
        assert reg.unregister_agent("nope") is False

    def test_get_agent(self):
        reg = self._make()
        a = self._agent("abc")
        reg.register_agent(a)
        assert reg.get_agent("abc") is a
        assert reg.get_agent("zzz") is None

    def test_list_agents(self):
        reg = self._make()
        reg.register_agent(self._agent("a", "dom_a"))
        reg.register_agent(self._agent("b", "dom_b"))
        lst = reg.list_agents()
        assert len(lst) == 2
        names = {x["name"] for x in lst}
        assert names == {"a", "b"}

    def test_get_agent_info_found(self):
        reg = self._make()
        a = self._agent("domo", "domotique")
        a.capabilities = ["x", "y"]
        reg.register_agent(a)
        info = reg.get_agent_info("domo")
        assert info["found"] is True
        assert info["domain"] == "domotique"

    def test_get_agent_info_not_found(self):
        reg = self._make()
        info = reg.get_agent_info("ghost")
        assert info["found"] is False

    def test_get_agents_for_domain(self):
        reg = self._make()
        reg.register_agent(self._agent("a1", "dom"))
        reg.register_agent(self._agent("a2", "dom"))
        reg.register_agent(self._agent("a3", "other"))
        result = reg.get_agents_for_domain("dom")
        assert len(result) == 2

    def test_health_check(self):
        reg = self._make()
        h = reg.health_check()
        assert h["service"] == "agent_registry"
        assert h["status"] == "ok"

    def test_restart(self):
        reg = self._make()
        reg.register_agent(self._agent("a"))
        reg.restart()
        assert reg.get_stats()["agents_registered"] == 0

    def test_register_with_bus(self):
        from agent_messaging_bus import AgentMessagingBus
        from agent_registry import AgentRegistry
        bus = AgentMessagingBus()
        reg = AgentRegistry(bus)
        reg.register_agent(self._agent("bot"))
        assert bus.get_stats()["channels_active"] == 1

    def test_unregister_with_bus(self):
        from agent_messaging_bus import AgentMessagingBus
        from agent_registry import AgentRegistry
        bus = AgentMessagingBus()
        reg = AgentRegistry(bus)
        reg.register_agent(self._agent("bot"))
        reg.unregister_agent("bot")
        assert bus.get_stats()["channels_active"] == 0


# ═══════════════════════════════════════════════════════════
#  3. SpecializedAgents
# ═══════════════════════════════════════════════════════════

class TestSpecializedAgents:

    def test_handle_task_success(self):
        from specialized_agents import AgentDomotique
        a = AgentDomotique()
        result = a.handle_task({"domain": "domotique", "action": "turn_on",
                                "target": "lamp"})
        assert result["status"] == "success"
        assert result["agent"] == "domotique"

    def test_handle_task_domain_mismatch(self):
        from specialized_agents import AgentDomotique
        a = AgentDomotique()
        result = a.handle_task({"domain": "reseau", "action": "scan"})
        assert result["status"] == "rejected"

    def test_handle_task_no_domain_accepted(self):
        from specialized_agents import AgentReseau
        a = AgentReseau()
        result = a.handle_task({"action": "scan"})
        assert result["status"] == "success"

    def test_report_result(self):
        from specialized_agents import AgentDomotique
        a = AgentDomotique()
        a.handle_task({"domain": "domotique", "action": "test"})
        r = a.report_result()
        assert r["status"] == "success"

    def test_report_result_no_task(self):
        from specialized_agents import AgentDomotique
        a = AgentDomotique()
        r = a.report_result()
        assert r["status"] == "no_result"

    def test_report_error(self):
        from specialized_agents import AgentDomotique
        a = AgentDomotique()
        r = a.report_error("something broke")
        assert r["error"] == "something broke"

    def test_request_assistance_no_bus(self):
        from specialized_agents import AgentDomotique
        a = AgentDomotique()
        r = a.request_assistance("reseau")
        assert r["sent"] is False

    def test_request_assistance_with_bus(self):
        from agent_messaging_bus import AgentMessagingBus
        from specialized_agents import AgentDomotique
        bus = AgentMessagingBus()
        bus.register_channel("domotique")
        bus.register_channel("reseau")
        a = AgentDomotique(messaging_bus=bus)
        r = a.request_assistance("reseau")
        assert r["sent"] is True

    def test_create_default_agents(self):
        from specialized_agents import create_default_agents, DEFAULT_AGENTS
        agents = create_default_agents()
        assert len(agents) == len(DEFAULT_AGENTS)
        names = {a.name for a in agents}
        assert "domotique" in names
        assert "securite" in names

    def test_all_agents_have_unique_names(self):
        from specialized_agents import create_default_agents
        agents = create_default_agents()
        names = [a.name for a in agents]
        assert len(names) == len(set(names))

    def test_all_agents_have_domains(self):
        from specialized_agents import create_default_agents
        for a in create_default_agents():
            assert a.domain, f"{a.name} has no domain"

    def test_health_check(self):
        from specialized_agents import AgentDomotique
        a = AgentDomotique()
        h = a.health_check()
        assert h["status"] == "ok"
        assert "domotique" in h["domain"]

    def test_restart(self):
        from specialized_agents import AgentDomotique
        a = AgentDomotique()
        a.handle_task({"domain": "domotique", "action": "x"})
        a.restart()
        assert a.get_stats()["tasks_handled"] == 0

    def test_get_stats(self):
        from specialized_agents import AgentDomotique
        a = AgentDomotique()
        a.handle_task({"domain": "domotique", "action": "x"})
        s = a.get_stats()
        assert s["tasks_handled"] == 1
        assert s["tasks_succeeded"] == 1

    def test_agent_memoire_store_no_memory(self):
        from specialized_agents import AgentMemoire
        a = AgentMemoire()
        r = a.handle_task({"domain": "memoire", "action": "store",
                           "key": "k", "value": "v"})
        assert r["status"] == "success"

    def test_each_agent_class_handles_own_domain(self):
        from specialized_agents import DEFAULT_AGENTS
        for cls in DEFAULT_AGENTS:
            a = cls()
            r = a.handle_task({"domain": a.domain, "action": "test"})
            assert r["status"] == "success", f"{a.name} failed domain task"


# ═══════════════════════════════════════════════════════════
#  4. ConflictResolver
# ═══════════════════════════════════════════════════════════

class TestConflictResolver:

    def _make(self):
        from conflict_resolver import ConflictResolver
        return ConflictResolver()

    def test_detect_no_conflict(self):
        cr = self._make()
        result = cr.detect_conflicts([
            {"agent": "a", "result": {"action": "turn_on", "target": "lamp"}},
        ])
        assert result["conflict_count"] == 0

    def test_detect_contradiction(self):
        cr = self._make()
        result = cr.detect_conflicts([
            {"agent": "a", "result": {"action": "enable", "target": "x"}},
            {"agent": "b", "result": {"action": "disable", "target": "x"}},
        ])
        assert result["conflict_count"] >= 1
        assert result["conflicts"][0]["type"] == "contradiction"

    def test_detect_domain_overlap(self):
        cr = self._make()
        result = cr.detect_conflicts([
            {"agent": "a", "result": {"target": "lamp"}},
            {"agent": "b", "result": {"target": "lamp"}},
        ])
        # domain_overlap when multiple agents act on same target
        overlaps = [c for c in result["conflicts"]
                    if c["type"] == "domain_overlap"]
        assert len(overlaps) >= 1

    def test_resolve_no_conflict(self):
        cr = self._make()
        outputs = [{"agent": "a", "result": {"action": "x"}}]
        result = cr.resolve(outputs)
        assert result["resolved"] is True
        assert result["conflicts_found"] == 0

    def test_resolve_contradiction(self):
        cr = self._make()
        outputs = [
            {"agent": "securite", "result": {"action": "lock", "target": "door"}},
            {"agent": "domotique", "result": {"action": "unlock", "target": "door"}},
        ]
        result = cr.resolve(outputs)
        assert result["resolved"] is True
        # securite has higher priority, should be in selected
        selected_agents = [o.get("agent") for o in result["selected_outputs"]]
        assert "securite" in selected_agents

    def test_resolve_stats(self):
        cr = self._make()
        cr.resolve([
            {"agent": "a", "result": {"action": "on", "target": "t"}},
            {"agent": "b", "result": {"action": "off", "target": "t"}},
        ])
        assert cr.get_stats()["resolutions_run"] >= 1

    def test_detect_empty(self):
        cr = self._make()
        result = cr.detect_conflicts([])
        assert result["conflict_count"] == 0

    def test_health_check(self):
        cr = self._make()
        h = cr.health_check()
        assert h["service"] == "conflict_resolver"
        assert h["status"] == "ok"

    def test_restart(self):
        cr = self._make()
        cr.detect_conflicts([
            {"agent": "a", "result": {"action": "on", "target": "t"}},
            {"agent": "b", "result": {"action": "off", "target": "t"}},
        ])
        cr.restart()
        assert cr.get_stats()["conflicts_detected"] == 0


# ═══════════════════════════════════════════════════════════
#  5. CognitiveOrchestrator
# ═══════════════════════════════════════════════════════════

class TestCognitiveOrchestrator:

    def _make_full(self):
        from agent_messaging_bus import AgentMessagingBus
        from agent_registry import AgentRegistry
        from specialized_agents import create_default_agents
        from conflict_resolver import ConflictResolver
        from cognitive_orchestrator import CognitiveOrchestrator

        bus = AgentMessagingBus()
        reg = AgentRegistry(bus)
        for a in create_default_agents(bus):
            reg.register_agent(a)
        cr = ConflictResolver()
        orch = CognitiveOrchestrator(reg, bus, cr)
        return orch, reg, bus

    def test_orchestrate_single_domain(self):
        orch, _, _ = self._make_full()
        result = orch.orchestrate({
            "domain": "domotique",
            "action": "turn_on",
            "params": {"target": "lamp"},
        })
        assert "intent_id" in result
        assert len(result["dispatched"]) >= 1
        assert result["decision"]["status"] == "decided"

    def test_orchestrate_unknown_domain(self):
        orch, _, _ = self._make_full()
        result = orch.orchestrate({
            "domain": "alien",
            "action": "fly",
        })
        # No agent for "alien" → no dispatches
        assert len(result["dispatched"]) == 0

    def test_dispatch_to_agent(self):
        orch, _, _ = self._make_full()
        result = orch.dispatch(
            {"id": "t1", "domain": "domotique", "action": "test"},
            "domotique")
        assert result["status"] == "success"

    def test_dispatch_unknown_agent(self):
        orch, _, _ = self._make_full()
        result = orch.dispatch({"id": "t1"}, "ghost_agent")
        assert result["status"] == "agent_not_found"

    def test_collect(self):
        orch, _, _ = self._make_full()
        collected = orch.collect({"agent": "a", "status": "success"})
        assert len(collected) == 1

    def test_resolve_conflicts_no_resolver(self):
        from cognitive_orchestrator import CognitiveOrchestrator
        orch = CognitiveOrchestrator()
        result = orch.resolve_conflicts([])
        assert result["resolved"] is False

    def test_finalize_decision_no_results(self):
        orch, _, _ = self._make_full()
        d = orch.finalize_decision()
        assert d["status"] == "no_results"

    def test_finalize_decision_with_results(self):
        orch, _, _ = self._make_full()
        orch.collect({"agent": "a", "status": "success",
                      "result": {"x": 1}})
        d = orch.finalize_decision()
        assert d["status"] == "decided"
        assert d["agents_involved"] >= 1

    def test_stats_after_orchestrate(self):
        orch, _, _ = self._make_full()
        orch.orchestrate({"domain": "domotique", "action": "x"})
        s = orch.get_stats()
        assert s["intents_processed"] == 1
        assert s["decisions_finalized"] >= 1

    def test_health_check(self):
        orch, _, _ = self._make_full()
        h = orch.health_check()
        assert h["service"] == "cognitive_orchestrator"
        assert h["status"] == "ok"

    def test_restart(self):
        orch, _, _ = self._make_full()
        orch.orchestrate({"domain": "domotique", "action": "x"})
        orch.restart()
        assert orch.get_stats()["intents_processed"] == 0

    def test_orchestrate_no_registry(self):
        from cognitive_orchestrator import CognitiveOrchestrator
        orch = CognitiveOrchestrator()
        result = orch.orchestrate({"domain": "domotique", "action": "x"})
        assert result["decision"]["status"] == "no_results"


# ═══════════════════════════════════════════════════════════
#  6. DistributedConsistencyEngine
# ═══════════════════════════════════════════════════════════

class TestDistributedConsistencyEngine:

    def _make_full(self):
        from agent_messaging_bus import AgentMessagingBus
        from agent_registry import AgentRegistry
        from specialized_agents import create_default_agents
        from conflict_resolver import ConflictResolver
        from distributed_consistency_engine import DistributedConsistencyEngine

        bus = AgentMessagingBus()
        reg = AgentRegistry(bus)
        for a in create_default_agents(bus):
            reg.register_agent(a)
        cr = ConflictResolver()
        eng = DistributedConsistencyEngine(reg, bus, cr)
        return eng, reg

    def test_check_global_consistency(self):
        eng, _ = self._make_full()
        result = eng.check_global_consistency()
        assert "consistent" in result
        assert "agents_checked" in result
        assert result["agents_checked"] >= 1

    def test_check_global_no_registry(self):
        from distributed_consistency_engine import DistributedConsistencyEngine
        eng = DistributedConsistencyEngine()
        result = eng.check_global_consistency()
        assert result["consistent"] is True
        assert result["agents_checked"] == 0

    def test_enforce_global_consistency(self):
        eng, _ = self._make_full()
        result = eng.enforce_global_consistency()
        assert result["enforced"] is True
        assert "corrections" in result

    def test_check_agent_consistency(self):
        eng, _ = self._make_full()
        result = eng.check_agent_consistency("domotique")
        assert result["agent"] == "domotique"
        assert result["consistent"] is True

    def test_check_agent_consistency_not_found(self):
        eng, _ = self._make_full()
        result = eng.check_agent_consistency("ghost")
        assert result["consistent"] is False
        assert result["reason"] == "agent_not_found"

    def test_check_agent_no_registry(self):
        from distributed_consistency_engine import DistributedConsistencyEngine
        eng = DistributedConsistencyEngine()
        result = eng.check_agent_consistency("any")
        assert result["consistent"] is True

    def test_stats_increment(self):
        eng, _ = self._make_full()
        eng.check_global_consistency()
        eng.check_global_consistency()
        assert eng.get_stats()["consistency_checks"] == 2

    def test_health_check(self):
        eng, _ = self._make_full()
        h = eng.health_check()
        assert h["service"] == "distributed_consistency"
        assert h["status"] == "ok"

    def test_restart(self):
        eng, _ = self._make_full()
        eng.check_global_consistency()
        eng.restart()
        assert eng.get_stats()["consistency_checks"] == 0


# ═══════════════════════════════════════════════════════════
#  7. MetaSupervisorV4
# ═══════════════════════════════════════════════════════════

class TestMetaSupervisorV4:

    def _make_full(self):
        from agent_messaging_bus import AgentMessagingBus
        from agent_registry import AgentRegistry
        from specialized_agents import create_default_agents
        from conflict_resolver import ConflictResolver
        from distributed_consistency_engine import DistributedConsistencyEngine
        from meta_supervisor_v4 import MetaSupervisorV4

        bus = AgentMessagingBus()
        reg = AgentRegistry(bus)
        for a in create_default_agents(bus):
            reg.register_agent(a)
        cr = ConflictResolver()
        cons = DistributedConsistencyEngine(reg, bus, cr)
        sup = MetaSupervisorV4(registry=reg, messaging_bus=bus,
                               consistency_engine=cons)
        return sup, reg, bus

    def test_supervise_agent_ok(self):
        sup, _, _ = self._make_full()
        result = sup.supervise_agent("domotique")
        assert result["approved"] is True
        assert result["agent"] == "domotique"

    def test_supervise_agent_not_found(self):
        sup, _, _ = self._make_full()
        result = sup.supervise_agent("ghost")
        assert result["status"] == "not_found"

    def test_supervise_agent_blocked(self):
        sup, _, _ = self._make_full()
        sup.set_meta_rules({"blocked_agents": ["domotique"]})
        result = sup.supervise_agent("domotique")
        assert result["status"] == "blocked"

    def test_supervise_agent_no_registry(self):
        from meta_supervisor_v4 import MetaSupervisorV4
        sup = MetaSupervisorV4()
        result = sup.supervise_agent("any")
        assert result["status"] == "no_registry"

    def test_supervise_interaction_ok(self):
        sup, _, _ = self._make_full()
        result = sup.supervise_interaction({
            "sender": "domotique",
            "recipient": "securite",
            "type": "info",
        })
        assert result["approved"] is True

    def test_supervise_interaction_blocked_sender(self):
        sup, _, _ = self._make_full()
        sup.set_meta_rules({"blocked_agents": ["domotique"]})
        result = sup.supervise_interaction({
            "sender": "domotique",
            "recipient": "securite",
            "type": "info",
        })
        assert result["approved"] is False

    def test_supervise_interaction_no_type(self):
        sup, _, _ = self._make_full()
        result = sup.supervise_interaction({
            "sender": "a", "recipient": "b",
        })
        assert result["approved"] is False

    def test_supervise_decision_ok(self):
        sup, _, _ = self._make_full()
        result = sup.supervise_decision({
            "status": "decided",
            "agents_involved": 2,
            "failed": 0,
        })
        assert result["approved"] is True

    def test_supervise_decision_failed(self):
        sup, _, _ = self._make_full()
        result = sup.supervise_decision({
            "status": "failed",
            "agents_involved": 1,
            "failed": 1,
        })
        assert result["approved"] is False

    def test_supervise_decision_no_agents(self):
        sup, _, _ = self._make_full()
        result = sup.supervise_decision({
            "status": "decided",
            "agents_involved": 0,
            "failed": 0,
        })
        assert result["approved"] is False

    def test_enforce_meta_rules(self):
        sup, _, _ = self._make_full()
        result = sup.enforce_meta_rules()
        assert result["enforced"] is True
        assert "rules" in result

    def test_set_meta_rules(self):
        sup, _, _ = self._make_full()
        sup.set_meta_rules({"max_agent_failure_rate": 0.9})
        # Should not crash; internal check
        result = sup.enforce_meta_rules()
        assert result["enforced"] is True

    def test_get_alerts(self):
        sup, _, _ = self._make_full()
        alerts = sup.get_alerts()
        assert isinstance(alerts, list)

    def test_stats(self):
        sup, _, _ = self._make_full()
        sup.supervise_agent("domotique")
        s = sup.get_stats()
        assert s["agents_supervised"] >= 1

    def test_health_check(self):
        sup, _, _ = self._make_full()
        h = sup.health_check()
        assert h["service"] == "meta_supervisor_v4"
        assert h["status"] == "ok"

    def test_restart(self):
        sup, _, _ = self._make_full()
        sup.supervise_agent("domotique")
        sup.restart()
        assert sup.get_stats()["agents_supervised"] == 0


# ═══════════════════════════════════════════════════════════
#  8. ExplainabilityEngineV4
# ═══════════════════════════════════════════════════════════

class TestExplainabilityEngineV4:

    def _make_full(self):
        from agent_messaging_bus import AgentMessagingBus
        from agent_registry import AgentRegistry
        from specialized_agents import create_default_agents
        from explainability_engine_v4 import ExplainabilityEngineV4

        bus = AgentMessagingBus()
        reg = AgentRegistry(bus)
        for a in create_default_agents(bus):
            reg.register_agent(a)
        eng = ExplainabilityEngineV4(registry=reg)
        return eng, reg

    def test_explain_agent_decision_found(self):
        eng, reg = self._make_full()
        # Run a task first
        agent = reg.get_agent("domotique")
        agent.handle_task({"domain": "domotique", "action": "turn_on"})
        result = eng.explain_agent_decision("domotique")
        assert result["found"] is True
        assert "domotique" in result["explanation"]

    def test_explain_agent_decision_not_found(self):
        eng, _ = self._make_full()
        result = eng.explain_agent_decision("ghost")
        assert result["found"] is False

    def test_explain_global_decision(self):
        eng, _ = self._make_full()
        result = eng.explain_global_decision({
            "status": "decided",
            "agent_names": ["domotique", "securite"],
            "successful": 2,
            "failed": 0,
            "merged_result": {"action": "on"},
        })
        assert "explanation" in result
        assert result["decision_status"] == "decided"

    def test_explain_global_decision_failed(self):
        eng, _ = self._make_full()
        result = eng.explain_global_decision({
            "status": "failed",
            "agent_names": [],
            "successful": 0,
            "failed": 1,
        })
        assert "échoué" in result["explanation"]

    def test_explain_conflict_resolution(self):
        eng, _ = self._make_full()
        result = eng.explain_conflict_resolution({
            "conflicts_found": 1,
            "resolution_method": "priority_arbitration",
            "conflicts": [{
                "type": "contradiction",
                "agent_a": "domo",
                "agent_b": "secu",
                "action_a": "unlock",
                "action_b": "lock",
                "target": "door",
            }],
            "selected_outputs": [{"agent": "secu"}],
            "dropped_outputs": [{"agent": "domo"}],
        })
        assert result["conflicts_found"] == 1
        assert result["selected_count"] == 1

    def test_explain_conflict_no_conflicts(self):
        eng, _ = self._make_full()
        result = eng.explain_conflict_resolution({
            "conflicts_found": 0,
            "resolution_method": "no_conflict",
            "conflicts": [],
            "selected_outputs": [],
            "dropped_outputs": [],
        })
        assert result["conflicts_found"] == 0

    def test_explain_orchestration(self):
        eng, _ = self._make_full()
        result = eng.explain_orchestration({
            "intent": {"domain": "domotique", "action": "turn_on"},
            "dispatched": [{"agent": "domotique"}],
            "collected": [{"status": "success"}],
            "resolution": {"conflicts_found": 0},
            "decision": {"status": "decided", "agents_involved": 1},
        })
        assert "explanation" in result
        assert result["dispatched_count"] == 1

    def test_stats(self):
        eng, _ = self._make_full()
        eng.explain_agent_decision("domotique")
        eng.explain_global_decision({"status": "decided"})
        s = eng.get_stats()
        assert s["agent_explanations"] == 1
        assert s["global_explanations"] == 1

    def test_health_check(self):
        eng, _ = self._make_full()
        h = eng.health_check()
        assert h["service"] == "explainability_v4"
        assert h["status"] == "ok"

    def test_restart(self):
        eng, _ = self._make_full()
        eng.explain_agent_decision("domotique")
        eng.restart()
        assert eng.get_stats()["agent_explanations"] == 0


# ═══════════════════════════════════════════════════════════
#  9. Intégration complète du pipeline v14
# ═══════════════════════════════════════════════════════════

class TestV14Integration:
    """Tests de bout-en-bout reliant tous les modules v14."""

    def _make_pipeline(self):
        from agent_messaging_bus import AgentMessagingBus
        from agent_registry import AgentRegistry
        from specialized_agents import create_default_agents
        from conflict_resolver import ConflictResolver
        from cognitive_orchestrator import CognitiveOrchestrator
        from distributed_consistency_engine import DistributedConsistencyEngine
        from meta_supervisor_v4 import MetaSupervisorV4
        from explainability_engine_v4 import ExplainabilityEngineV4

        bus = AgentMessagingBus()
        reg = AgentRegistry(bus)
        agents = create_default_agents(bus)
        for a in agents:
            reg.register_agent(a)
        cr = ConflictResolver()
        orch = CognitiveOrchestrator(reg, bus, cr)
        cons = DistributedConsistencyEngine(reg, bus, cr)
        sup = MetaSupervisorV4(registry=reg, messaging_bus=bus,
                               consistency_engine=cons)
        expl = ExplainabilityEngineV4(registry=reg)
        return {
            "bus": bus, "registry": reg, "agents": agents,
            "conflict_resolver": cr, "orchestrator": orch,
            "consistency": cons, "supervisor": sup,
            "explainability": expl,
        }

    def test_full_orchestration_cycle(self):
        p = self._make_pipeline()
        result = p["orchestrator"].orchestrate({
            "domain": "domotique",
            "action": "turn_on",
            "params": {"target": "lamp"},
        })
        assert result["decision"]["status"] == "decided"
        # Explain it
        expl = p["explainability"].explain_orchestration(result)
        assert "explanation" in expl
        # Supervise decision
        sup = p["supervisor"].supervise_decision(result["decision"])
        assert sup["approved"] is True

    def test_conflict_detection_and_resolution_pipeline(self):
        p = self._make_pipeline()
        # Create conflicting outputs
        outputs = [
            {"agent": "domotique",
             "result": {"action": "unlock", "target": "door"}},
            {"agent": "securite",
             "result": {"action": "lock", "target": "door"}},
        ]
        detection = p["conflict_resolver"].detect_conflicts(outputs)
        assert detection["conflict_count"] >= 1

        resolution = p["conflict_resolver"].resolve(outputs)
        assert resolution["resolved"] is True

        expl = p["explainability"].explain_conflict_resolution(resolution)
        assert expl["conflicts_found"] >= 1

    def test_consistency_check_after_tasks(self):
        p = self._make_pipeline()
        # Run tasks on several agents
        for name in ["domotique", "reseau", "securite"]:
            agent = p["registry"].get_agent(name)
            agent.handle_task({"domain": name, "action": "check"})

        result = p["consistency"].check_global_consistency()
        assert "consistent" in result
        assert result["agents_checked"] >= 3

    def test_supervision_of_all_agents(self):
        p = self._make_pipeline()
        for info in p["registry"].list_agents():
            result = p["supervisor"].supervise_agent(info["name"])
            assert result["approved"] is True

    def test_messaging_between_agents(self):
        p = self._make_pipeline()
        # domotique sends to securite
        result = p["bus"].send("domotique", "securite", {
            "type": "query",
            "payload": {"question": "is_door_locked"},
        })
        assert result["delivered"] is True

        msgs = p["bus"].receive("securite")
        assert len(msgs) == 1
        assert msgs[0]["sender"] == "domotique"

    def test_broadcast_alert(self):
        p = self._make_pipeline()
        results = p["bus"].broadcast("securite", {
            "type": "alert",
            "payload": {"level": "high", "message": "intrusion"},
        })
        delivered = [r for r in results if r.get("delivered")]
        # All agents except securite
        assert len(delivered) >= 10

    def test_full_explain_cycle(self):
        p = self._make_pipeline()
        # Run task
        agent = p["registry"].get_agent("domotique")
        agent.handle_task({"domain": "domotique", "action": "x"})

        # Explain agent
        r = p["explainability"].explain_agent_decision("domotique")
        assert r["found"] is True

        # Orchestrate → explain
        orch = p["orchestrator"].orchestrate({
            "domain": "securite", "action": "audit"
        })
        r2 = p["explainability"].explain_orchestration(orch)
        assert r2["dispatched_count"] >= 1

    def test_enforce_meta_rules_pipeline(self):
        p = self._make_pipeline()
        result = p["supervisor"].enforce_meta_rules()
        assert result["enforced"] is True

    def test_v14_modules_dict_structure(self):
        """Verify that modules dict matches what exo_server.py expects."""
        p = self._make_pipeline()
        v14 = {
            "messaging_bus": p["bus"],
            "registry": p["registry"],
            "conflict_resolver": p["conflict_resolver"],
            "orchestrator": p["orchestrator"],
            "consistency": p["consistency"],
            "supervisor_v4": p["supervisor"],
            "explainability_v4": p["explainability"],
        }
        assert len(v14) == 7
        for name, mod in v14.items():
            assert hasattr(mod, "get_stats"), f"{name} missing get_stats"
            assert hasattr(mod, "health_check"), f"{name} missing health_check"

    def test_all_stats_after_pipeline_run(self):
        p = self._make_pipeline()
        # Run a full cycle
        p["orchestrator"].orchestrate({
            "domain": "domotique", "action": "test"
        })
        p["consistency"].check_global_consistency()
        p["supervisor"].enforce_meta_rules()
        p["explainability"].explain_agent_decision("domotique")

        # Check all stats are non-zero
        assert p["orchestrator"].get_stats()["intents_processed"] >= 1
        assert p["consistency"].get_stats()["consistency_checks"] >= 1
        assert p["explainability"].get_stats()["agent_explanations"] == 1

    def test_agent_assistance_via_bus(self):
        p = self._make_pipeline()
        agent = p["registry"].get_agent("domotique")
        result = agent.request_assistance("securite")
        assert result["sent"] is True
        msgs = p["bus"].receive("securite")
        assert len(msgs) == 1
        assert msgs[0]["type"] == "assistance_request"

    def test_multi_domain_orchestration(self):
        p = self._make_pipeline()
        result = p["orchestrator"].orchestrate({
            "domains": ["domotique", "securite"],
            "action": "check_all",
        })
        assert result["decision"]["agents_involved"] >= 2
