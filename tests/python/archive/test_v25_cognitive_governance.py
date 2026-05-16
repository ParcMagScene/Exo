"""
EXO v25 — Tests de gouvernance cognitive renforcée.
9 modules : CognitivePermissionSystem, MultiLevelValidationEngine,
CognitiveAuditEngine, ComplianceEngine, GovernancePolicyEngine,
ActionControlEngine, DecisionValidationEngine, GovernanceSupervisor,
GovernanceExplainabilityEngine.
"""

import sys
import os
import time
import pytest

from cognitive_permission_system import CognitivePermissionSystem
from multi_level_validation_engine import MultiLevelValidationEngine
from cognitive_audit_engine import CognitiveAuditEngine
from compliance_engine import ComplianceEngine
from governance_policy_engine import GovernancePolicyEngine
from action_control_engine import ActionControlEngine
from decision_validation_engine import DecisionValidationEngine
from governance_supervisor import GovernanceSupervisor
from governance_explainability_engine import GovernanceExplainabilityEngine


# ═══════════════════════════════════════════════════════════
#  1. CognitivePermissionSystem
# ═══════════════════════════════════════════════════════════

class TestCognitivePermissionSystem:
    def _make(self):
        return CognitivePermissionSystem()

    def test_grant_permission(self):
        m = self._make()
        r = m.grant_permission("agent_a", "read_memory")
        assert r["granted"] is True
        assert r["operation"] == "grant"
        assert r["entity"] == "agent_a"
        assert r["action"] == "read_memory"
        assert r["id"].startswith("pgrnt_")
        assert r["total_permissions"] >= 1
        assert "timestamp" in r

    def test_check_permission_after_grant(self):
        m = self._make()
        m.grant_permission("agent_b", "write_memory")
        r = m.check_permission("agent_b", "write_memory")
        assert r["allowed"] is True
        assert r["id"].startswith("pchk_")
        assert r["entity"] == "agent_b"

    def test_check_permission_not_granted(self):
        m = self._make()
        r = m.check_permission("agent_c", "delete")
        assert r["allowed"] is False

    def test_revoke_permission(self):
        m = self._make()
        m.grant_permission("agent_d", "execute")
        r = m.revoke_permission("agent_d", "execute")
        assert r["revoked"] is True
        assert r["id"].startswith("prev_")
        chk = m.check_permission("agent_d", "execute")
        assert chk["allowed"] is False

    def test_revoke_nonexistent(self):
        m = self._make()
        r = m.revoke_permission("ghost", "nope")
        assert r["revoked"] is False

    def test_health_check(self):
        m = self._make()
        h = m.health_check()
        assert h["service"] == "cognitive_permission_system"
        assert h["status"] == "ok"

    def test_restart_clears(self):
        m = self._make()
        m.grant_permission("x", "y")
        m.restart()
        assert m.check_permission("x", "y")["allowed"] is False
        assert m.get_stats()["granted"] == 0

    def test_get_stats(self):
        m = self._make()
        m.grant_permission("a", "b")
        m.revoke_permission("a", "b")
        m.check_permission("a", "b")
        s = m.get_stats()
        assert s["granted"] == 1
        assert s["revoked"] == 1
        assert s["checked"] == 1


# ═══════════════════════════════════════════════════════════
#  2. MultiLevelValidationEngine
# ═══════════════════════════════════════════════════════════

class TestMultiLevelValidationEngine:
    def _make(self):
        return MultiLevelValidationEngine()

    def test_validate_action_pass(self):
        m = self._make()
        r = m.validate_action({"name": "read", "entity": "agent",
                               "context": {}})
        assert r["validated"] is True
        assert r["id"].startswith("va_")
        assert r["action"] == "read"
        assert r["entity"] == "agent"
        assert isinstance(r["levels"], dict)
        assert r["failed_levels"] == []

    def test_validate_action_fail_logic(self):
        m = self._make()
        r = m.validate_action({"entity": "agent"})
        assert r["validated"] is False
        assert "logic" in r["failed_levels"]

    def test_validate_decision_pass(self):
        m = self._make()
        r = m.validate_decision({"name": "decide_x", "entity": "agent",
                                 "rationale": "because"})
        assert r["validated"] is True
        assert r["id"].startswith("vd_")
        assert r["decision"] == "decide_x"
        assert r["rationale"] == "because"

    def test_explain_validation(self):
        m = self._make()
        m.validate_action({"name": "a", "entity": "e"})
        r = m.explain_validation()
        assert r["explained"] is True
        assert r["id"].startswith("vex_")
        assert r["total_validations"] == 1

    def test_levels_present(self):
        m = self._make()
        r = m.validate_action({"name": "a", "entity": "e"})
        for lvl in ("logic", "context", "temporal", "security", "coherence"):
            assert lvl in r["levels"]
            assert "valid" in r["levels"][lvl]
            assert "reason" in r["levels"][lvl]

    def test_health_check(self):
        m = self._make()
        assert m.health_check()["status"] == "ok"

    def test_restart(self):
        m = self._make()
        m.validate_action({"name": "a", "entity": "e"})
        m.restart()
        assert m.get_stats()["actions_validated"] == 0


# ═══════════════════════════════════════════════════════════
#  3. CognitiveAuditEngine
# ═══════════════════════════════════════════════════════════

class TestCognitiveAuditEngine:
    def _make(self):
        return CognitiveAuditEngine()

    def test_audit_log(self):
        m = self._make()
        r = m.audit_log({"category": "action", "source": "agent_a",
                         "action": "read"})
        assert r["logged"] is True
        assert r["id"].startswith("aud_")
        assert r["category"] == "action"
        assert r["source"] == "agent_a"
        assert r["total_logs"] == 1

    def test_audit_export(self):
        m = self._make()
        m.audit_log({"category": "decision", "source": "agent"})
        r = m.audit_export()
        assert r["exported"] is True
        assert r["id"].startswith("aexp_")
        assert r["total_logs"] == 1
        assert "decision" in r["by_category"]

    def test_audit_query(self):
        m = self._make()
        m.audit_log({"category": "action", "source": "s1"})
        m.audit_log({"category": "decision", "source": "s2"})
        r = m.audit_query({"category": "action"})
        assert r["queried"] is True
        assert r["id"].startswith("aq_")
        assert r["count"] == 1

    def test_audit_query_empty(self):
        m = self._make()
        r = m.audit_query({"category": "anomaly"})
        assert r["count"] == 0

    def test_health_check(self):
        m = self._make()
        h = m.health_check()
        assert h["service"] == "cognitive_audit_engine"
        assert h["status"] == "ok"

    def test_restart(self):
        m = self._make()
        m.audit_log({"category": "action"})
        m.restart()
        assert m.get_stats()["logged"] == 0


# ═══════════════════════════════════════════════════════════
#  4. ComplianceEngine
# ═══════════════════════════════════════════════════════════

class TestComplianceEngine:
    def _make(self):
        perm = CognitivePermissionSystem()
        return ComplianceEngine(permissions=perm), perm

    def test_check_compliance_pass(self):
        m, _ = self._make()
        r = m.check_compliance({"name": "read", "entity": "agent",
                                "context": {}})
        assert r["id"].startswith("cc_")
        assert r["action"] == "read"
        assert r["entity"] == "agent"
        assert isinstance(r["domains"], dict)
        assert isinstance(r["violations"], list)

    def test_check_compliance_violations(self):
        m, _ = self._make()
        r = m.check_compliance({"name": "", "entity": ""})
        assert r["compliant"] is False
        assert len(r["violations"]) > 0

    def test_enforce_compliance(self):
        m, _ = self._make()
        r = m.enforce_compliance({"name": "write", "entity": "agent"})
        assert r["enforced"] is True
        assert r["id"].startswith("ce_")
        assert "allowed" in r
        assert "violations" in r

    def test_explain_compliance(self):
        m, _ = self._make()
        m.check_compliance({"name": "a", "entity": "e"})
        r = m.explain_compliance()
        assert r["explained"] is True
        assert r["id"].startswith("cex_")
        assert "total_checks" in r

    def test_sensitive_action_not_authorized(self):
        m, _ = self._make()
        r = m.check_compliance({"name": "delete_all", "entity": "a",
                                "sensitive": True})
        assert r["compliant"] is False
        assert "security" in r["violations"]

    def test_health_check(self):
        m, _ = self._make()
        assert m.health_check()["service"] == "compliance_engine"

    def test_restart(self):
        m, _ = self._make()
        m.check_compliance({"name": "x", "entity": "y"})
        m.restart()
        assert m.get_stats()["checked"] == 0


# ═══════════════════════════════════════════════════════════
#  5. GovernancePolicyEngine
# ═══════════════════════════════════════════════════════════

class TestGovernancePolicyEngine:
    def _make(self):
        return GovernancePolicyEngine()

    def test_load_policies(self):
        m = self._make()
        r = m.load_policies([
            {"name": "sec_policy", "type": "security", "rules": ["r1"]},
            {"name": "val_policy", "type": "validation"},
        ])
        assert r["loaded"] is True
        assert r["id"].startswith("pl_")
        assert r["count"] == 2
        assert r["total_policies"] == 2

    def test_apply_policy(self):
        m = self._make()
        m.load_policies([{"name": "p1", "type": "security", "rules": ["r"]}])
        r = m.apply_policy("p1")
        assert r["applied"] is True
        assert r["id"].startswith("pap_")
        assert r["type"] == "security"
        assert r["rules_count"] == 1

    def test_apply_policy_not_found(self):
        m = self._make()
        r = m.apply_policy("ghost")
        assert r["applied"] is False
        assert r["error"] == "policy_not_found"

    def test_explain_policy(self):
        m = self._make()
        m.load_policies([{"name": "xp", "type": "coherence",
                          "rules": ["a", "b"]}])
        r = m.explain_policy("xp")
        assert r["explained"] is True
        assert r["id"].startswith("pex_")
        assert r["policy"] == "xp"
        assert r["rules_count"] == 2

    def test_explain_policy_not_found(self):
        m = self._make()
        r = m.explain_policy("no_such")
        assert r["explained"] is False

    def test_health_check(self):
        m = self._make()
        assert m.health_check()["service"] == "governance_policy_engine"

    def test_restart(self):
        m = self._make()
        m.load_policies([{"name": "p", "type": "security"}])
        m.restart()
        assert m.get_stats()["loaded"] == 0


# ═══════════════════════════════════════════════════════════
#  6. ActionControlEngine
# ═══════════════════════════════════════════════════════════

class TestActionControlEngine:
    def _make(self):
        perm = CognitivePermissionSystem()
        val = MultiLevelValidationEngine(permissions=perm)
        comp = ComplianceEngine(permissions=perm)
        ctrl = ActionControlEngine(
            permissions=perm, validation=val, compliance=comp)
        return ctrl, perm

    def test_control_action_allowed(self):
        ctrl, perm = self._make()
        perm.grant_permission("agent", "read")
        r = ctrl.control_action({"name": "read", "entity": "agent",
                                 "context": {}})
        assert r["controlled"] is True
        assert r["allowed"] is True
        assert r["id"].startswith("ctrl_")
        assert r["block_reasons"] == []

    def test_control_action_blocked_no_permission(self):
        ctrl, _ = self._make()
        r = ctrl.control_action({"name": "write", "entity": "agent"})
        assert r["allowed"] is False
        assert "permission_denied" in r["block_reasons"]

    def test_block_action_manual(self):
        ctrl, _ = self._make()
        r = ctrl.block_action({"name": "dangerous", "entity": "x",
                               "reason": "forbidden"})
        assert r["blocked"] is True
        assert r["id"].startswith("blk_")
        assert r["reason"] == "forbidden"

    def test_explain_block(self):
        ctrl, _ = self._make()
        ctrl.block_action({"name": "a", "entity": "e"})
        r = ctrl.explain_block()
        assert r["explained"] is True
        assert r["id"].startswith("bex_")
        assert r["total_blocks"] >= 1

    def test_health_check(self):
        ctrl, _ = self._make()
        assert ctrl.health_check()["service"] == "action_control_engine"

    def test_restart(self):
        ctrl, _ = self._make()
        ctrl.block_action({"name": "a", "entity": "e"})
        ctrl.restart()
        assert ctrl.get_stats()["blocked"] == 0


# ═══════════════════════════════════════════════════════════
#  7. DecisionValidationEngine
# ═══════════════════════════════════════════════════════════

class TestDecisionValidationEngine:
    def _make(self):
        return DecisionValidationEngine()

    def test_validate_decision_pass(self):
        m = self._make()
        r = m.validate_decision({"name": "decide_x", "entity": "agent",
                                 "rationale": "justified"})
        assert r["validated"] is True
        assert r["id"].startswith("dv_")
        assert r["decision"] == "decide_x"
        assert r["rationale"] == "justified"
        assert r["failed_aspects"] == []

    def test_validate_decision_fail_coherence_no_rationale(self):
        m = self._make()
        r = m.validate_decision({"name": "decide_y", "entity": "agent"})
        assert r["validated"] is False
        assert "coherence" in r["failed_aspects"]

    def test_aspects_present(self):
        m = self._make()
        r = m.validate_decision({"name": "d", "entity": "e",
                                 "rationale": "r"})
        for asp in ("logic", "context", "temporal", "coherence", "security"):
            assert asp in r["aspects"]

    def test_reject_decision(self):
        m = self._make()
        r = m.reject_decision({"name": "bad_call", "entity": "a",
                               "reason": "not aligned"})
        assert r["rejected"] is True
        assert r["id"].startswith("dr_")
        assert r["reason"] == "not aligned"

    def test_explain_decision_validation(self):
        m = self._make()
        m.validate_decision({"name": "d", "entity": "e", "rationale": "r"})
        m.reject_decision({"name": "b", "entity": "e"})
        r = m.explain_decision_validation()
        assert r["explained"] is True
        assert r["id"].startswith("dvex_")
        assert r["total_validations"] == 1
        assert r["total_rejections"] == 1

    def test_health_check(self):
        m = self._make()
        assert m.health_check()["service"] == "decision_validation_engine"

    def test_restart(self):
        m = self._make()
        m.validate_decision({"name": "d", "entity": "e", "rationale": "r"})
        m.restart()
        assert m.get_stats()["validated"] == 0


# ═══════════════════════════════════════════════════════════
#  8. GovernanceSupervisor
# ═══════════════════════════════════════════════════════════

class TestGovernanceSupervisor:
    def _make(self):
        perm = CognitivePermissionSystem()
        val = MultiLevelValidationEngine(permissions=perm)
        audit = CognitiveAuditEngine()
        comp = ComplianceEngine(permissions=perm)
        policies = GovernancePolicyEngine()
        act = ActionControlEngine(permissions=perm, validation=val,
                                  compliance=comp)
        dec = DecisionValidationEngine(permissions=perm, policies=policies)
        sup = GovernanceSupervisor(
            permissions=perm, validation=val, audit=audit,
            compliance=comp, policies=policies,
            action_control=act, decision_validation=dec)
        return sup

    def test_supervise_governance_healthy(self):
        s = self._make()
        r = s.supervise_governance()
        assert r["supervised"] is True
        assert r["id"].startswith("sup_")
        assert r["overall_status"] == "healthy"
        assert r["degraded"] == []
        assert r["modules_count"] == 7

    def test_enforce_governance_rules_no_issues(self):
        s = self._make()
        r = s.enforce_governance_rules()
        assert r["enforced"] is True
        assert r["id"].startswith("enf_")
        assert r["actions_taken"] == 0

    def test_governance_health_check(self):
        s = self._make()
        r = s.governance_health_check()
        assert r["governance_healthy"] is True
        assert r["id"].startswith("ghc_")
        assert r["modules_count"] == 7
        assert "module_stats" in r

    def test_health_check(self):
        s = self._make()
        assert s.health_check()["service"] == "governance_supervisor"

    def test_restart(self):
        s = self._make()
        s.supervise_governance()
        s.restart()
        assert s.get_stats()["supervised"] == 0


# ═══════════════════════════════════════════════════════════
#  9. GovernanceExplainabilityEngine
# ═══════════════════════════════════════════════════════════

class TestGovernanceExplainabilityEngine:
    def _make(self):
        perm = CognitivePermissionSystem()
        val = MultiLevelValidationEngine(permissions=perm)
        comp = ComplianceEngine(permissions=perm)
        act = ActionControlEngine(permissions=perm, validation=val,
                                  compliance=comp)
        audit = CognitiveAuditEngine()
        expl = GovernanceExplainabilityEngine(
            permissions=perm, validation=val, compliance=comp,
            action_control=act, audit=audit)
        return expl, perm

    def test_explain_permission_not_granted(self):
        e, _ = self._make()
        r = e.explain_permission("agent_x", "read")
        assert r["explained"] is True
        assert r["id"].startswith("eperm_")
        assert r["allowed"] is False

    def test_explain_permission_granted(self):
        e, perm = self._make()
        perm.grant_permission("agent_y", "write")
        r = e.explain_permission("agent_y", "write")
        assert r["allowed"] is True
        assert r["reason"] == "granted"

    def test_explain_governance_decision(self):
        e, _ = self._make()
        r = e.explain_governance_decision()
        assert r["explained"] is True
        assert r["id"].startswith("egov_")
        assert "validation" in r
        assert "compliance" in r

    def test_explain_block_reason(self):
        e, _ = self._make()
        r = e.explain_block_reason()
        assert r["explained"] is True
        assert r["id"].startswith("eblk_")
        assert "total_blocks" in r
        assert "by_reason" in r

    def test_health_check(self):
        e, _ = self._make()
        h = e.health_check()
        assert h["service"] == "governance_explainability_engine"
        assert h["status"] == "ok"

    def test_restart(self):
        e, _ = self._make()
        e.explain_permission("a", "b")
        e.restart()
        assert e.get_stats()["permissions_explained"] == 0

    def test_get_stats(self):
        e, _ = self._make()
        e.explain_permission("a", "b")
        e.explain_governance_decision()
        e.explain_block_reason()
        s = e.get_stats()
        assert s["permissions_explained"] == 1
        assert s["decisions_explained"] == 1
        assert s["blocks_explained"] == 1
