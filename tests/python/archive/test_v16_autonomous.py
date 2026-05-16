"""
EXO v16 — Tests unifiés : Agents autonomes supervisés, émergence cognitive.
Couvre : CognitiveAuditLog, InitiativeProtocol, CognitiveGovernor,
         AutonomousAgentLayer, EmergentCollaborationBus,
         EmergentReasoningEngine, SelfRegulationEngine, ExplainabilityEngineV6.
"""

import sys
from pathlib import Path

import pytest

from cognitive_audit_log import CognitiveAuditLog
from initiative_protocol import InitiativeProtocol
from cognitive_governor import CognitiveGovernor
from autonomous_agent_layer import AutonomousAgentLayer
from emergent_collaboration_bus import EmergentCollaborationBus
from emergent_reasoning_engine import EmergentReasoningEngine
from self_regulation_engine import SelfRegulationEngine
from explainability_engine_v6 import ExplainabilityEngineV6


# =====================================================================
# CognitiveAuditLog
# =====================================================================

class TestCognitiveAuditLog:
    def _make(self):
        return CognitiveAuditLog()

    def test_health_check(self):
        a = self._make()
        h = a.health_check()
        assert h["service"] == "cognitive_audit_log"
        assert h["status"] == "ok"

    def test_get_stats_initial(self):
        a = self._make()
        s = a.get_stats()
        assert s["total_entries"] == 0
        assert s["initiatives_logged"] == 0
        assert s["rejections_logged"] == 0

    def test_log_initiative(self):
        a = self._make()
        entry = a.log_initiative({
            "agent": "diagnostic",
            "action": "scan_network",
            "confidence": 0.9,
        })
        assert isinstance(entry, dict)
        assert entry["id"].startswith("audit_")
        assert entry["entry_type"] == "initiative_proposed"
        s = a.get_stats()
        assert s["total_entries"] == 1
        assert s["initiatives_logged"] == 1

    def test_log_validation(self):
        a = self._make()
        entry = a.log_validation({
            "initiative_id": "init_123",
            "result": "approved",
        })
        assert isinstance(entry, dict)
        assert entry["id"].startswith("audit_")
        assert a.get_stats()["validations_logged"] == 1

    def test_log_rejection(self):
        a = self._make()
        entry = a.log_rejection({
            "initiative_id": "init_123",
            "reason": "budget_exceeded",
        })
        assert isinstance(entry, dict)
        assert entry["id"].startswith("audit_")
        assert a.get_stats()["rejections_logged"] == 1

    def test_log_emergence(self):
        a = self._make()
        entry = a.log_emergence({
            "type": "pattern_detected",
            "confidence": 0.85,
        })
        assert isinstance(entry, dict)
        assert entry["id"].startswith("audit_")
        assert a.get_stats()["emergences_logged"] == 1

    def test_log_governance(self):
        a = self._make()
        entry = a.log_governance({
            "rule": "safety_first",
            "action": "block",
        })
        assert isinstance(entry, dict)
        assert entry["id"].startswith("audit_")
        assert a.get_stats()["governance_logged"] == 1

    def test_log_regulation(self):
        a = self._make()
        entry = a.log_regulation({
            "agent": "diagnostic",
            "adjustment": "increase_autonomy",
        })
        assert isinstance(entry, dict)
        assert entry["id"].startswith("audit_")
        assert a.get_stats()["regulations_logged"] == 1

    def test_get_audit_trail(self):
        a = self._make()
        a.log_initiative({"agent": "a1", "action": "x"})
        a.log_rejection({"initiative_id": "i1", "reason": "r"})
        trail = a.get_audit_trail(limit=10)
        assert len(trail) == 2

    def test_get_audit_trail_with_filter(self):
        a = self._make()
        a.log_initiative({"agent": "a1", "action": "x"})
        a.log_rejection({"initiative_id": "i1", "reason": "r"})
        trail = a.get_audit_trail(limit=10,
                                  filters={"type": "initiative_proposed"})
        assert len(trail) == 1

    def test_get_summary(self):
        a = self._make()
        a.log_initiative({"agent": "a1", "action": "x"})
        a.log_initiative({"agent": "a2", "action": "y"})
        a.log_rejection({"initiative_id": "i1", "reason": "r"})
        s = a.get_summary()
        assert s["total_entries"] == 3
        assert "by_type" in s

    def test_max_log_size_trim(self):
        from cognitive_audit_log import MAX_LOG_SIZE
        a = self._make()
        for i in range(105):
            a.log_initiative({"agent": f"a{i}", "action": "x"})
        trail = a.get_audit_trail(limit=MAX_LOG_SIZE + 100)
        assert len(trail) <= MAX_LOG_SIZE

    def test_restart(self):
        a = self._make()
        a.log_initiative({"agent": "a1", "action": "x"})
        a.restart()
        assert a.get_stats()["total_entries"] == 0


# =====================================================================
# InitiativeProtocol
# =====================================================================

class TestInitiativeProtocol:
    def _make(self):
        audit = CognitiveAuditLog()
        return InitiativeProtocol(audit)

    def test_health_check(self):
        p = self._make()
        h = p.health_check()
        assert h["service"] == "initiative_protocol"
        assert h["status"] == "ok"

    def test_get_stats_initial(self):
        p = self._make()
        s = p.get_stats()
        assert s["permissions_checked"] == 0
        assert s["budgets_checked"] == 0

    def test_check_permissions_basic(self):
        p = self._make()
        result = p.check_permissions("diagnostic", "scan_network", {})
        assert "allowed" in result
        assert isinstance(result["allowed"], bool)
        assert p.get_stats()["permissions_checked"] == 1

    def test_check_budget(self):
        p = self._make()
        result = p.check_budget("diagnostic", 10.0)
        assert "allowed" in result
        assert p.get_stats()["budgets_checked"] == 1

    def test_budget_exceeded(self):
        p = self._make()
        p.set_budget("agent_x", {
            "max_initiatives_per_hour": 2,
            "max_total_cost_per_hour": 5,
            "remaining_cost": 2,
        })
        # check_budget does NOT deduct — cost > remaining_cost triggers exceed
        result = p.check_budget("agent_x", 3.0)
        assert result["allowed"] is False
        assert p.get_stats()["budgets_exceeded"] >= 1

    def test_require_validation(self):
        p = self._make()
        result = p.require_validation({
            "agent": "domotique",
            "action": "turn_off_all",
            "risk": 0.8,
        })
        assert "validation_level" in result
        assert "initiative_id" in result
        assert p.get_stats()["validations_required"] == 1

    def test_approve(self):
        p = self._make()
        r = p.require_validation({
            "agent": "test",
            "action": "do_something",
            "domain": "securite",
        })
        iid = r["initiative_id"]
        result = p.approve(iid)
        assert result["approved"] is True
        assert p.get_stats()["approvals"] == 1

    def test_deny(self):
        p = self._make()
        r = p.require_validation({
            "agent": "test",
            "action": "do_something",
            "domain": "securite",
        })
        iid = r["initiative_id"]
        result = p.deny(iid, "trop risqué")
        assert result["denied"] is True
        assert p.get_stats()["denials"] == 1

    def test_get_budget(self):
        p = self._make()
        b = p.get_budget("new_agent")
        assert "max_initiatives_per_hour" in b
        assert "max_total_cost_per_hour" in b

    def test_set_budget(self):
        p = self._make()
        p.set_budget("agent_a", {
            "max_initiatives_per_hour": 50,
            "max_total_cost_per_hour": 1000,
        })
        b = p.get_budget("agent_a")
        assert b["max_initiatives_per_hour"] == 50

    def test_restart(self):
        p = self._make()
        p.check_permissions("a", "b", {})
        p.restart()
        assert p.get_stats()["permissions_checked"] == 0


# =====================================================================
# CognitiveGovernor
# =====================================================================

class TestCognitiveGovernor:
    def _make(self):
        audit = CognitiveAuditLog()
        proto = InitiativeProtocol(audit)
        return CognitiveGovernor(proto, audit)

    def test_health_check(self):
        g = self._make()
        h = g.health_check()
        assert h["service"] == "cognitive_governor"
        assert h["status"] == "ok"

    def test_get_stats_initial(self):
        g = self._make()
        s = g.get_stats()
        assert s["initiatives_supervised"] == 0
        assert s["emergences_supervised"] == 0

    def test_supervise_initiative_safe(self):
        g = self._make()
        result = g.supervise_initiative({
            "agent": "diagnostic",
            "action": "read_sensor",
            "confidence": 0.9,
            "risk": 0.1,
        })
        assert "decision" in result
        assert result["decision"] in ("approved", "blocked", "needs_approval")
        assert g.get_stats()["initiatives_supervised"] == 1

    def test_supervise_initiative_risky(self):
        g = self._make()
        result = g.supervise_initiative({
            "agent": "securite",
            "action": "disable_alarm",
            "confidence": 0.3,
            "risk": 0.95,
        })
        assert result["decision"] in ("blocked", "needs_approval")

    def test_supervise_emergence(self):
        g = self._make()
        result = g.supervise_emergence({
            "pattern": "new_pattern",
            "novelty_score": 0.5,
            "viability": 0.8,
        })
        assert "decision" in result
        assert g.get_stats()["emergences_supervised"] == 1

    def test_enforce_governance_rules(self):
        g = self._make()
        result = g.enforce_governance_rules({
            "active_initiatives": [],
            "active_emergences": [],
        })
        assert "violations" in result
        assert isinstance(result["violations"], list)

    def test_override_decision(self):
        g = self._make()
        r = g.supervise_initiative({
            "agent": "test",
            "action": "test_action",
            "confidence": 0.5,
            "risk": 0.5,
        })
        did = r.get("id", "")
        if did:
            ov = g.override_decision(did, {"new_decision": "approved",
                                            "reason": "manual"})
            assert isinstance(ov, dict)
            assert g.get_stats()["overrides"] >= 1

    def test_restart(self):
        g = self._make()
        g.supervise_initiative({"agent": "a", "action": "b",
                                "confidence": 0.5, "risk": 0.2})
        g.restart()
        assert g.get_stats()["initiatives_supervised"] == 0


# =====================================================================
# AutonomousAgentLayer
# =====================================================================

class TestAutonomousAgentLayer:
    def _make(self):
        audit = CognitiveAuditLog()
        proto = InitiativeProtocol(audit)
        gov = CognitiveGovernor(proto, audit)
        return AutonomousAgentLayer(gov, proto, audit)

    def test_health_check(self):
        a = self._make()
        h = a.health_check()
        assert h["service"] == "autonomous_agent_layer"
        assert h["status"] == "ok"

    def test_get_stats_initial(self):
        a = self._make()
        s = a.get_stats()
        assert s["initiatives_proposed"] == 0
        assert s["initiatives_executed"] == 0

    def test_propose_initiative(self):
        a = self._make()
        result = a.propose_initiative("diagnostic", "check_system",
                                       {"target": "cpu"})
        assert "id" in result
        assert "status" in result
        assert a.get_stats()["initiatives_proposed"] == 1

    def test_validate_initiative(self):
        a = self._make()
        r = a.propose_initiative("diagnostic", "check_system", {})
        iid = r["id"]
        result = a.validate_initiative(iid)
        assert "validated" in result or "reason" in result

    def test_execute_initiative(self):
        a = self._make()
        r = a.propose_initiative("diagnostic", "check_system",
                                  {"target": "disk"})
        iid = r["id"]
        a.validate_initiative(iid)
        result = a.execute_initiative(iid)
        assert "executed" in result or "reason" in result

    def test_rollback_initiative(self):
        a = self._make()
        r = a.propose_initiative("diagnostic", "check_system", {})
        iid = r["id"]
        result = a.rollback_initiative(iid)
        assert "rolled_back" in result or "reason" in result

    def test_list_initiatives(self):
        a = self._make()
        a.propose_initiative("agent1", "action1", {})
        a.propose_initiative("agent2", "action2", {})
        listed = a.list_initiatives()
        assert len(listed) >= 2

    def test_list_initiatives_by_status(self):
        a = self._make()
        r = a.propose_initiative("agent1", "action1", {})
        status = r["status"]
        listed = a.list_initiatives(status=status)
        assert len(listed) >= 1

    def test_get_agent_autonomy(self):
        a = self._make()
        result = a.get_agent_autonomy("new_agent")
        assert isinstance(result, dict)
        assert "level" in result
        assert 0 <= result["level"] <= 4

    def test_set_agent_autonomy(self):
        a = self._make()
        a.set_agent_autonomy("agent_x", 3)
        result = a.get_agent_autonomy("agent_x")
        assert result["level"] == 3

    def test_set_agent_autonomy_clamp(self):
        a = self._make()
        a.set_agent_autonomy("agent_x", 10)
        result = a.get_agent_autonomy("agent_x")
        assert result["level"] <= 4

    def test_restart(self):
        a = self._make()
        a.propose_initiative("a", "b", {})
        a.restart()
        assert a.get_stats()["initiatives_proposed"] == 0


# =====================================================================
# EmergentCollaborationBus
# =====================================================================

class TestEmergentCollaborationBus:
    def _make(self):
        audit = CognitiveAuditLog()
        return EmergentCollaborationBus(audit)

    def test_health_check(self):
        b = self._make()
        h = b.health_check()
        assert h["service"] == "emergent_collaboration_bus"
        assert h["status"] == "ok"

    def test_get_stats_initial(self):
        b = self._make()
        s = b.get_stats()
        assert s["collaborations_started"] == 0
        assert s["observations_shared"] == 0

    def test_collaborate(self):
        b = self._make()
        result = b.collaborate("agent_a", ["agent_b", "agent_c"],
                                {"description": "optimize_energy"})
        assert "id" in result
        assert result["status"] == "active"
        assert b.get_stats()["collaborations_started"] == 1

    def test_share_observation(self):
        b = self._make()
        result = b.share_observation("agent_a", {
            "type": "anomaly",
            "domain": "temperature",
            "value": 42.5,
            "confidence": 0.95,
        })
        assert "id" in result
        assert b.get_stats()["observations_shared"] == 1

    def test_request_support(self):
        b = self._make()
        result = b.request_support("agent_a", {
            "type": "need_data",
            "domain": "humidity",
        })
        assert "id" in result
        assert b.get_stats()["support_requests"] == 1

    def test_get_collaboration_status(self):
        b = self._make()
        r = b.collaborate("a", ["b"], {"description": "goal"})
        cid = r["id"]
        status = b.get_collaboration_status(cid)
        assert status.get("found", True)  # found or has status
        assert status.get("status", "active") == "active"

    def test_complete_collaboration(self):
        b = self._make()
        r = b.collaborate("a", ["b"], {"description": "goal"})
        cid = r["id"]
        result = b.complete_collaboration(cid, {"outcome": "success"})
        assert result["completed"] is True
        assert b.get_stats()["collaborations_completed"] == 1

    def test_get_shared_observations(self):
        b = self._make()
        b.share_observation("a", {"type": "x", "domain": "temp"})
        b.share_observation("b", {"type": "y", "domain": "humidity"})
        obs = b.get_shared_observations()
        assert len(obs) == 2

    def test_get_shared_observations_by_domain(self):
        b = self._make()
        b.share_observation("a", {"type": "x", "domain": "temp"})
        b.share_observation("b", {"type": "y", "domain": "humidity"})
        obs = b.get_shared_observations(domain="temp")
        assert len(obs) == 1

    def test_restart(self):
        b = self._make()
        b.collaborate("a", ["b"], {"description": "g"})
        b.restart()
        assert b.get_stats()["collaborations_started"] == 0


# =====================================================================
# EmergentReasoningEngine
# =====================================================================

class TestEmergentReasoningEngine:
    def _make(self):
        audit = CognitiveAuditLog()
        proto = InitiativeProtocol(audit)
        gov = CognitiveGovernor(proto, audit)
        bus = EmergentCollaborationBus(audit)
        return EmergentReasoningEngine(bus, gov, audit)

    def test_health_check(self):
        e = self._make()
        h = e.health_check()
        assert h["service"] == "emergent_reasoning"
        assert h["status"] == "ok"

    def test_get_stats_initial(self):
        e = self._make()
        s = e.get_stats()
        assert s["solutions_generated"] == 0
        assert s["emergences_detected"] == 0

    def test_generate_emergent_solution(self):
        e = self._make()
        result = e.generate_emergent_solution({
            "problem": "high_energy_consumption",
            "domain": "domotique",
            "observations": [
                {"source": "sensor_a", "value": 3500},
                {"source": "sensor_b", "value": 2800},
            ],
        })
        assert "id" in result
        assert "paths" in result
        assert e.get_stats()["solutions_generated"] == 1

    def test_evaluate_emergent_solution(self):
        e = self._make()
        result = e.evaluate_emergent_solution({
            "solution_id": "sol_test",
            "paths": [{"action": "reduce_heating", "confidence": 0.8}],
        })
        assert "viability" in result or "viable" in result
        assert e.get_stats()["solutions_evaluated"] == 1

    def test_explain_emergent_solution(self):
        e = self._make()
        result = e.explain_emergent_solution({
            "solution_id": "sol_test",
            "paths": [{"action": "dim_lights", "confidence": 0.7}],
        })
        assert "text" in result

    def test_detect_emergence(self):
        e = self._make()
        result = e.detect_emergence([
            {"source": "agent_a", "type": "pattern", "value": "recurring_spike"},
            {"source": "agent_b", "type": "pattern", "value": "recurring_spike"},
            {"source": "agent_c", "type": "anomaly", "value": "unexpected_drop"},
        ])
        assert "emergences" in result
        assert e.get_stats()["emergences_detected"] >= 1

    def test_detect_emergence_empty(self):
        e = self._make()
        result = e.detect_emergence([])
        assert "emergences" in result

    def test_restart(self):
        e = self._make()
        e.generate_emergent_solution({"problem": "test"})
        e.restart()
        assert e.get_stats()["solutions_generated"] == 0


# =====================================================================
# SelfRegulationEngine
# =====================================================================

class TestSelfRegulationEngine:
    def _make(self):
        audit = CognitiveAuditLog()
        proto = InitiativeProtocol(audit)
        gov = CognitiveGovernor(proto, audit)
        return SelfRegulationEngine(gov, audit, proto)

    def test_health_check(self):
        r = self._make()
        h = r.health_check()
        assert h["service"] == "self_regulation"
        assert h["status"] == "ok"

    def test_get_stats_initial(self):
        r = self._make()
        s = r.get_stats()
        assert s["autonomy_adjustments"] == 0
        assert s["budget_adjustments"] == 0

    def test_adjust_autonomy_good_performance(self):
        r = self._make()
        result = r.adjust_autonomy("agent_a", {
            "success_rate": 0.95,
            "risk_incidents": 0,
            "initiatives_count": 50,
        })
        assert "adjusted" in result or "direction" in result
        assert r.get_stats()["autonomy_adjustments"] == 1

    def test_adjust_autonomy_poor_performance(self):
        r = self._make()
        result = r.adjust_autonomy("agent_a", {
            "success_rate": 0.3,
            "risk_incidents": 5,
            "initiatives_count": 20,
        })
        assert "adjusted" in result or "direction" in result

    def test_adjust_budget(self):
        r = self._make()
        result = r.adjust_budget("agent_a", {
            "utilization": 0.5,
            "success_rate": 0.9,
        })
        assert "adjusted" in result or "direction" in result
        assert r.get_stats()["budget_adjustments"] == 1

    def test_regulate_all(self):
        r = self._make()
        result = r.regulate_all({
            "agents": {
                "agent_a": {"success_rate": 0.9, "risk_incidents": 0,
                            "initiatives_count": 30},
                "agent_b": {"success_rate": 0.4, "risk_incidents": 3,
                            "initiatives_count": 10},
            }
        })
        assert "adjustments" in result
        assert r.get_stats()["regulations_run"] == 1

    def test_get_regulation_policy(self):
        r = self._make()
        policy = r.get_regulation_policy()
        assert "autonomy_increase_threshold" in policy
        assert "autonomy_decrease_threshold" in policy

    def test_set_regulation_policy(self):
        r = self._make()
        r.set_regulation_policy({"autonomy_increase_threshold": 0.9,
                                  "autonomy_decrease_threshold": 0.3})
        policy = r.get_regulation_policy()
        assert policy["autonomy_increase_threshold"] == 0.9

    def test_restart(self):
        r = self._make()
        r.adjust_autonomy("a", {"success_rate": 0.8})
        r.restart()
        assert r.get_stats()["autonomy_adjustments"] == 0


# =====================================================================
# ExplainabilityEngineV6
# =====================================================================

class TestExplainabilityEngineV6:
    def _make(self):
        audit = CognitiveAuditLog()
        return ExplainabilityEngineV6(audit_log=audit)

    def test_health_check(self):
        e = self._make()
        h = e.health_check()
        assert h["service"] == "explainability_v6"
        assert h["status"] == "ok"

    def test_get_stats_initial(self):
        e = self._make()
        s = e.get_stats()
        assert s["initiatives_explained"] == 0
        assert s["emergences_explained"] == 0

    def test_explain_initiative(self):
        e = self._make()
        result = e.explain_initiative({
            "agent": "diagnostic",
            "action": "scan_network",
            "confidence": 0.9,
            "decision": "approved",
        })
        assert "text" in result
        assert e.get_stats()["initiatives_explained"] == 1

    def test_explain_emergence(self):
        e = self._make()
        result = e.explain_emergence({
            "type": "pattern_detected",
            "sources": ["agent_a", "agent_b"],
            "confidence": 0.85,
        })
        assert "text" in result
        assert e.get_stats()["emergences_explained"] == 1

    def test_explain_governor_decision(self):
        e = self._make()
        result = e.explain_governor_decision({
            "initiative": {"agent": "test", "action": "x"},
            "decision": "denied",
            "reasons": ["high_risk"],
        })
        assert "text" in result
        assert e.get_stats()["governor_decisions_explained"] == 1

    def test_explain_regulation(self):
        e = self._make()
        result = e.explain_regulation({
            "agent": "agent_a",
            "adjustment": "decrease_autonomy",
            "reason": "low_success_rate",
        })
        assert "text" in result
        assert e.get_stats()["regulations_explained"] == 1

    def test_explain_collaboration(self):
        e = self._make()
        result = e.explain_collaboration({
            "initiator": "agent_a",
            "participants": ["agent_b"],
            "goal": "optimize",
            "outcome": "success",
        })
        assert "text" in result
        assert e.get_stats()["collaborations_explained"] == 1

    def test_explain_full_v16(self):
        e = self._make()
        result = e.explain_full_v16({
            "initiatives": [{"agent": "a", "action": "x"}],
            "emergences": [],
            "regulations": [],
        })
        assert "text" in result
        assert e.get_stats()["full_explanations"] == 1

    def test_restart(self):
        e = self._make()
        e.explain_initiative({"agent": "a", "action": "b", "decision": "ok"})
        e.restart()
        assert e.get_stats()["initiatives_explained"] == 0


# =====================================================================
# Integration tests — Module interactions
# =====================================================================

class TestV16Integration:
    """Tests d'intégration entre modules v16."""

    def _make_stack(self):
        audit = CognitiveAuditLog()
        proto = InitiativeProtocol(audit)
        gov = CognitiveGovernor(proto, audit)
        layer = AutonomousAgentLayer(gov, proto, audit)
        bus = EmergentCollaborationBus(audit)
        reasoning = EmergentReasoningEngine(bus, gov, audit)
        regulation = SelfRegulationEngine(gov, audit, proto)
        explain = ExplainabilityEngineV6(audit_log=audit)
        return {
            "audit": audit,
            "protocol": proto,
            "governor": gov,
            "layer": layer,
            "bus": bus,
            "reasoning": reasoning,
            "regulation": regulation,
            "explain": explain,
        }

    def test_full_initiative_flow(self):
        """Propose → Validate → Execute → Audit trail."""
        s = self._make_stack()
        r = s["layer"].propose_initiative("diagnostic", "check_cpu",
                                           {"target": "cpu"})
        iid = r["id"]
        s["layer"].validate_initiative(iid)
        s["layer"].execute_initiative(iid)
        trail = s["audit"].get_audit_trail(limit=50)
        assert len(trail) >= 1

    def test_collaboration_then_emergence(self):
        """Collaborate → Share observations → Detect emergence."""
        s = self._make_stack()
        s["bus"].collaborate("a", ["b", "c"], {"description": "find_anomaly"})
        s["bus"].share_observation("a", {"type": "spike", "domain": "energy",
                                          "value": 100})
        s["bus"].share_observation("b", {"type": "spike", "domain": "energy",
                                          "value": 110})
        obs = s["bus"].get_shared_observations(domain="energy")
        result = s["reasoning"].detect_emergence(obs)
        assert "emergences" in result

    def test_regulation_after_poor_performance(self):
        """Regulate agent with poor metrics → autonomy adjusted."""
        s = self._make_stack()
        s["layer"].set_agent_autonomy("bad_agent", 3)
        result = s["regulation"].adjust_autonomy("bad_agent", {
            "success_rate": 0.2,
            "risk_incidents": 10,
            "initiatives_count": 5,
        })
        assert "adjusted" in result or "direction" in result

    def test_explain_full_pipeline(self):
        """Explain a full v16 session."""
        s = self._make_stack()
        r = s["layer"].propose_initiative("diag", "scan", {})
        s["layer"].validate_initiative(r["id"])
        s["bus"].share_observation("diag", {"type": "result",
                                             "domain": "network"})
        result = s["explain"].explain_full_v16({
            "initiatives": [{"agent": "diag", "action": "scan"}],
            "emergences": [],
            "regulations": [],
        })
        assert "text" in result

    def test_all_modules_health(self):
        """All 8 modules report healthy."""
        s = self._make_stack()
        for name, mod in s.items():
            h = mod.health_check()
            assert h["status"] == "ok", f"{name} unhealthy: {h}"

    def test_all_modules_restart(self):
        """All 8 modules can restart cleanly."""
        s = self._make_stack()
        for name, mod in s.items():
            mod.restart()
            h = mod.health_check()
            assert h["status"] == "ok", f"{name} unhealthy after restart: {h}"
