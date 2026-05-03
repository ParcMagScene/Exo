"""
Tests unitaires — v9 Security Manager & Audit Log

Valide la sécurité et l'audit :
 - PERMISSION_DEFAULTS
 - AuditLog (append-only, search, recent)
 - SecurityManager (check_permission, authorize, set_permission)
"""

import json
import time

import pytest

import sys
from pathlib import Path

from shared.security_manager import (
    PERMISSION_DEFAULTS, AuditLog, SecurityManager,
)


# ═══════════════════════════════════════════════════════
#  Permission Defaults
# ═══════════════════════════════════════════════════════

class TestPermissionDefaults:
    def test_modules_present(self):
        for mod in ("domotique", "fichiers", "reseau", "outils"):
            assert mod in PERMISSION_DEFAULTS

    def test_domotique_actions(self):
        dom = PERMISSION_DEFAULTS["domotique"]
        assert dom["ha_turn_on"] == "allow"
        assert dom["camera_snapshot"] == "restricted"

    def test_fichiers_deny_delete(self):
        assert PERMISSION_DEFAULTS["fichiers"]["delete"] == "deny"

    def test_no_invalid_rules(self):
        valid = {"allow", "deny", "restricted"}
        for mod, rules in PERMISSION_DEFAULTS.items():
            for action, rule in rules.items():
                assert rule in valid, f"{mod}.{action} = {rule}"


# ═══════════════════════════════════════════════════════
#  AuditLog
# ═══════════════════════════════════════════════════════

class TestAuditLog:
    def test_record_and_recent(self, tmp_path):
        log = AuditLog(tmp_path / "audit.jsonl")
        log.record("turn_on", "domotique", {"entity": "light.salon"})
        log.record("read", "fichiers", {"path": "/tmp/test"})
        entries = log.recent(10)
        assert len(entries) == 2
        assert entries[0]["action"] == "turn_on"
        assert entries[1]["module"] == "fichiers"

    def test_file_persistence(self, tmp_path):
        path = tmp_path / "audit.jsonl"
        log = AuditLog(path)
        log.record("scan", "reseau")
        assert path.exists()
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["action"] == "scan"

    def test_search_by_module(self, tmp_path):
        log = AuditLog(tmp_path / "audit.jsonl")
        log.record("turn_on", "domotique")
        log.record("read", "fichiers")
        log.record("turn_off", "domotique")
        results = log.search(module="domotique")
        assert len(results) == 2

    def test_search_by_action(self, tmp_path):
        log = AuditLog(tmp_path / "audit.jsonl")
        log.record("read", "fichiers")
        log.record("write", "fichiers")
        log.record("read", "outils")
        results = log.search(action="read")
        assert len(results) == 2

    def test_search_since(self, tmp_path):
        log = AuditLog(tmp_path / "audit.jsonl")
        log.record("old", "domotique")
        cutoff = time.time()
        log.record("new", "domotique")
        results = log.search(since=cutoff)
        assert len(results) == 1
        assert results[0]["action"] == "new"

    def test_memory_capped(self, tmp_path):
        log = AuditLog(tmp_path / "audit.jsonl")
        log._max_memory = 10
        for i in range(20):
            log.record(f"action_{i}", "test")
        assert len(log.recent(100)) == 10


# ═══════════════════════════════════════════════════════
#  SecurityManager
# ═══════════════════════════════════════════════════════

class TestSecurityManager:
    def setup_method(self):
        SecurityManager.reset()

    def test_singleton(self):
        a = SecurityManager.instance()
        b = SecurityManager.instance()
        assert a is b

    def test_check_permission_allow(self):
        sm = SecurityManager.instance()
        assert sm.check_permission("domotique", "ha_turn_on") == "allow"

    def test_check_permission_deny(self):
        sm = SecurityManager.instance()
        assert sm.check_permission("fichiers", "delete") == "deny"

    def test_check_permission_restricted(self):
        sm = SecurityManager.instance()
        assert sm.check_permission("domotique", "camera_snapshot") == "restricted"

    def test_check_unknown_action(self):
        sm = SecurityManager.instance()
        assert sm.check_permission("domotique", "nonexistent") == "deny"

    def test_check_unknown_module(self):
        sm = SecurityManager.instance()
        assert sm.check_permission("unknown", "anything") == "deny"

    def test_is_allowed(self):
        sm = SecurityManager.instance()
        assert sm.is_allowed("domotique", "ha_turn_on") is True
        assert sm.is_allowed("domotique", "camera_snapshot") is True  # restricted = allowed
        assert sm.is_allowed("fichiers", "delete") is False

    def test_authorize_allowed(self):
        sm = SecurityManager.instance()
        result = sm.authorize("domotique", "ha_turn_on", {"entity": "light.salon"})
        assert result is True
        recent = sm.audit.recent(1)
        assert recent[0]["result"] == "allowed"

    def test_authorize_denied(self):
        sm = SecurityManager.instance()
        result = sm.authorize("fichiers", "delete", {"path": "/etc/passwd"})
        assert result is False
        recent = sm.audit.recent(1)
        assert recent[0]["result"] == "denied"

    def test_set_permission(self):
        sm = SecurityManager.instance()
        sm.set_permission("domotique", "ha_turn_on", "deny")
        assert sm.check_permission("domotique", "ha_turn_on") == "deny"

    def test_set_permission_invalid(self):
        sm = SecurityManager.instance()
        with pytest.raises(ValueError):
            sm.set_permission("domotique", "ha_turn_on", "maybe")

    def test_get_permissions_module(self):
        sm = SecurityManager.instance()
        perms = sm.get_permissions("domotique")
        assert "ha_turn_on" in perms

    def test_get_permissions_all(self):
        sm = SecurityManager.instance()
        perms = sm.get_permissions()
        assert "domotique" in perms
        assert "fichiers" in perms

    def test_export_permissions(self, tmp_path):
        sm = SecurityManager.instance()
        path = tmp_path / "perms.json"
        sm.export_permissions(path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert "domotique" in data

    def test_load_permissions(self, tmp_path):
        sm = SecurityManager.instance()
        custom = {"domotique": {"ha_turn_on": "deny"}}
        path = tmp_path / "perms.json"
        path.write_text(json.dumps(custom))
        sm.load_permissions(path)
        assert sm.check_permission("domotique", "ha_turn_on") == "deny"
