"""
Tests EXO v20 — Architecture modulaire ultra-scalable
70 tests couvrant les 9 modules v20.
"""

import sys, os, pytest, time

from modular_cognitive_unit import ModularCognitiveUnit
from plug_and_play_agent_system import PlugAndPlayAgentSystem
from distributed_orchestrator import DistributedOrchestrator
from scalable_cognitive_fabric import ScalableCognitiveFabric
from cognitive_partitioning_engine import CognitivePartitioningEngine
from module_lifecycle_manager import ModuleLifecycleManager
from hot_swap_engine import HotSwapEngine
from module_compatibility_checker import ModuleCompatibilityChecker
from modular_explainability_engine import ModularExplainabilityEngine


# ═══════════════════════════════════════════════════════════════
# ModularCognitiveUnit
# ═══════════════════════════════════════════════════════════════
class TestModularCognitiveUnit:
    def setup_method(self):
        self.mcu = ModularCognitiveUnit()

    def test_mcu_init(self):
        r = self.mcu.mcu_init(name="test_unit", version="2.0.0",
                               capabilities=["nlp", "vision"])
        assert r["initialized"] is True
        assert r["name"] == "test_unit"
        assert r["version"] == "2.0.0"
        assert r["id"].startswith("mcu_")

    def test_mcu_execute(self):
        r = self.mcu.mcu_init(name="exec_unit")
        uid = r["id"]
        result = self.mcu.mcu_execute({"unit_id": uid, "task": "analyze"})
        assert result["executed"] is True
        assert result["unit_id"] == uid
        assert result["task"] == "analyze"

    def test_mcu_execute_not_found(self):
        result = self.mcu.mcu_execute({"unit_id": "nonexistent", "task": "x"})
        assert result["executed"] is False
        assert result["error"] == "unit_not_found"

    def test_mcu_report(self):
        self.mcu.mcu_init(name="u1")
        self.mcu.mcu_init(name="u2")
        r = self.mcu.mcu_report()
        assert r["reported"] is True
        assert r["total_units"] == 2

    def test_mcu_shutdown_single(self):
        r = self.mcu.mcu_init(name="shut")
        uid = r["id"]
        result = self.mcu.mcu_shutdown(uid)
        assert result["shutdown"] is True
        assert self.mcu.get_unit(uid)["state"] == "shutdown"

    def test_mcu_shutdown_all(self):
        self.mcu.mcu_init(name="a")
        self.mcu.mcu_init(name="b")
        result = self.mcu.mcu_shutdown()
        assert result["shutdown"] is True
        assert result["units_shutdown"] == 2

    def test_mcu_shutdown_not_found(self):
        result = self.mcu.mcu_shutdown("bad_id")
        assert result["shutdown"] is False

    def test_mcu_health(self):
        h = self.mcu.health_check()
        assert h["service"] == "modular_cognitive_unit"
        assert h["status"] == "ok"

    def test_mcu_restart(self):
        self.mcu.mcu_init(name="r")
        self.mcu.restart()
        assert self.mcu.get_stats()["units_created"] == 0
        assert self.mcu.list_units() == []

    def test_mcu_list_units(self):
        self.mcu.mcu_init(name="x")
        units = self.mcu.list_units()
        assert len(units) == 1
        assert units[0]["name"] == "x"


# ═══════════════════════════════════════════════════════════════
# PlugAndPlayAgentSystem
# ═══════════════════════════════════════════════════════════════
class TestPlugAndPlayAgentSystem:
    def setup_method(self):
        self.pnp = PlugAndPlayAgentSystem()

    def test_register_agent(self):
        r = self.pnp.register_agent({"name": "agent1", "version": "1.0.0"})
        assert r["registered"] is True
        assert r["name"] == "agent1"

    def test_unregister_agent(self):
        r = self.pnp.register_agent({"name": "a"})
        uid = r["id"]
        result = self.pnp.unregister_agent({"agent_id": uid})
        assert result["unregistered"] is True

    def test_unregister_not_found(self):
        result = self.pnp.unregister_agent({"agent_id": "bad"})
        assert result["unregistered"] is False

    def test_replace_agent(self):
        r = self.pnp.register_agent({"name": "old_agent"})
        uid = r["id"]
        result = self.pnp.replace_agent(
            {"agent_id": uid}, {"name": "new_agent", "version": "2.0.0"})
        assert result["replaced"] is True
        assert result["old_name"] == "old_agent"
        assert result["new_name"] == "new_agent"

    def test_replace_not_found(self):
        result = self.pnp.replace_agent({"agent_id": "bad"}, {"name": "x"})
        assert result["replaced"] is False

    def test_list_agents(self):
        self.pnp.register_agent({"name": "a1"})
        self.pnp.register_agent({"name": "a2"})
        agents = self.pnp.list_agents()
        assert len(agents) == 2

    def test_health(self):
        h = self.pnp.health_check()
        assert h["service"] == "plug_and_play_agent_system"
        assert h["status"] == "ok"

    def test_restart(self):
        self.pnp.register_agent({"name": "a"})
        self.pnp.restart()
        assert self.pnp.list_agents() == []


# ═══════════════════════════════════════════════════════════════
# DistributedOrchestrator
# ═══════════════════════════════════════════════════════════════
class TestDistributedOrchestrator:
    def setup_method(self):
        self.orch = DistributedOrchestrator()

    def test_orchestrate(self):
        r = self.orch.orchestrate({"name": "task1", "modules": ["m1", "m2"]})
        assert r["orchestrated"] is True
        assert r["subtasks_count"] == 2

    def test_distribute(self):
        r = self.orch.distribute({"task_id": "t1", "targets": ["a", "b", "c"],
                                   "strategy": "round_robin"})
        assert r["distributed"] is True
        assert r["assignments_count"] == 3

    def test_collect(self):
        r = self.orch.collect({"task_id": "t1", "results": [
            {"status": "success"}, {"status": "failed"}]})
        assert r["collected"] is True
        assert r["aggregated"]["successful"] == 1
        assert r["aggregated"]["failed"] == 1

    def test_orchestrate_then_collect(self):
        o = self.orch.orchestrate({"name": "full", "modules": ["x"]})
        tid = o["id"]
        c = self.orch.collect({"task_id": tid,
                                "results": [{"status": "success"}]})
        assert c["collected"] is True
        task = self.orch.get_task(tid)
        assert task["state"] == "collected"

    def test_health(self):
        h = self.orch.health_check()
        assert h["service"] == "distributed_orchestrator"

    def test_restart(self):
        self.orch.orchestrate({"name": "t"})
        self.orch.restart()
        assert self.orch.get_stats()["orchestrated"] == 0


# ═══════════════════════════════════════════════════════════════
# ScalableCognitiveFabric
# ═══════════════════════════════════════════════════════════════
class TestScalableCognitiveFabric:
    def setup_method(self):
        self.fab = ScalableCognitiveFabric()

    def test_fabric_register(self):
        r = self.fab.fabric_register({"name": "mod1", "type": "nlp"})
        assert r["registered"] is True
        assert r["name"] == "mod1"

    def test_fabric_route_delivered(self):
        reg = self.fab.fabric_register({"name": "target"})
        uid = reg["id"]
        r = self.fab.fabric_route({"source": "src", "destination": uid})
        assert r["routed"] is True
        assert r["delivered"] is True

    def test_fabric_route_undelivered(self):
        r = self.fab.fabric_route({"source": "s", "destination": "nowhere"})
        assert r["routed"] is True
        assert r["delivered"] is False

    def test_fabric_scale(self):
        r = self.fab.fabric_scale({"type": "horizontal", "factor": 2})
        assert r["scaled"] is True
        assert r["type"] == "horizontal"
        assert r["factor"] == 2

    def test_list_modules(self):
        self.fab.fabric_register({"name": "m1"})
        assert len(self.fab.list_modules()) == 1

    def test_health(self):
        h = self.fab.health_check()
        assert h["service"] == "scalable_cognitive_fabric"

    def test_restart(self):
        self.fab.fabric_register({"name": "x"})
        self.fab.restart()
        assert self.fab.list_modules() == []


# ═══════════════════════════════════════════════════════════════
# CognitivePartitioningEngine
# ═══════════════════════════════════════════════════════════════
class TestCognitivePartitioningEngine:
    def setup_method(self):
        self.pe = CognitivePartitioningEngine()

    def test_partition_cognition(self):
        r = self.pe.partition_cognition({"name": "nlp_partition",
                                          "type": "domain",
                                          "modules": ["m1", "m2"]})
        assert r["partitioned"] is True
        assert r["modules_count"] == 2

    def test_reassign_partition(self):
        p1 = self.pe.partition_cognition({"name": "p1", "modules": ["m1"]})
        p2 = self.pe.partition_cognition({"name": "p2", "modules": []})
        r = self.pe.reassign_partition({
            "module_id": "m1",
            "source_partition": p1["id"],
            "target_partition": p2["id"],
        })
        assert r["reassigned"] is True

    def test_reassign_not_found(self):
        r = self.pe.reassign_partition({
            "module_id": "m",
            "source_partition": "bad",
            "target_partition": "bad2",
        })
        assert r["reassigned"] is False

    def test_merge_partitions(self):
        p1 = self.pe.partition_cognition({"name": "a", "modules": ["m1"]})
        p2 = self.pe.partition_cognition({"name": "b", "modules": ["m2"]})
        r = self.pe.merge_partitions([p1["id"], p2["id"]])
        assert r["merged"] is True
        assert r["total_modules"] == 2

    def test_merge_too_few(self):
        p1 = self.pe.partition_cognition({"name": "single"})
        r = self.pe.merge_partitions([p1["id"]])
        assert r["merged"] is False

    def test_list_partitions(self):
        self.pe.partition_cognition({"name": "p"})
        assert len(self.pe.list_partitions()) == 1

    def test_health(self):
        assert self.pe.health_check()["service"] == "cognitive_partitioning"

    def test_restart(self):
        self.pe.partition_cognition({"name": "x"})
        self.pe.restart()
        assert self.pe.list_partitions() == []


# ═══════════════════════════════════════════════════════════════
# ModuleLifecycleManager
# ═══════════════════════════════════════════════════════════════
class TestModuleLifecycleManager:
    def setup_method(self):
        self.lm = ModuleLifecycleManager()

    def test_install_module(self):
        r = self.lm.install_module({"name": "mod_a", "version": "1.2.0"})
        assert r["installed"] is True
        assert r["state"] == "active"

    def test_update_module(self):
        r = self.lm.install_module({"name": "mod_b", "version": "1.0.0"})
        uid = r["id"]
        upd = self.lm.update_module({"module_id": uid, "version": "2.0.0"})
        assert upd["updated"] is True
        assert upd["new_version"] == "2.0.0"

    def test_update_not_found(self):
        r = self.lm.update_module({"module_id": "bad"})
        assert r["updated"] is False

    def test_remove_module(self):
        r = self.lm.install_module({"name": "rem"})
        uid = r["id"]
        result = self.lm.remove_module({"module_id": uid})
        assert result["removed"] is True
        assert self.lm.get_module(uid) is None

    def test_remove_not_found(self):
        r = self.lm.remove_module({"module_id": "bad"})
        assert r["removed"] is False

    def test_list_modules(self):
        self.lm.install_module({"name": "a"})
        self.lm.install_module({"name": "b"})
        assert len(self.lm.list_modules()) == 2

    def test_health(self):
        assert self.lm.health_check()["service"] == "module_lifecycle_manager"

    def test_restart(self):
        self.lm.install_module({"name": "x"})
        self.lm.restart()
        assert self.lm.list_modules() == []


# ═══════════════════════════════════════════════════════════════
# HotSwapEngine
# ═══════════════════════════════════════════════════════════════
class TestHotSwapEngine:
    def setup_method(self):
        self.hs = HotSwapEngine()

    def test_validate_swap_compatible(self):
        r = self.hs.validate_swap(
            {"name": "old", "capabilities": ["a", "b"]},
            {"name": "new", "capabilities": ["a", "b", "c"]},
        )
        assert r["validated"] is True
        assert r["compatible"] is True

    def test_validate_swap_incompatible(self):
        r = self.hs.validate_swap(
            {"name": "old", "capabilities": ["a", "b"]},
            {"name": "new", "capabilities": ["a"]},
        )
        assert r["compatible"] is False
        assert len(r["issues"]) > 0

    def test_hotswap(self):
        r = self.hs.hotswap(
            {"module_id": "m1", "name": "old_mod"},
            {"name": "new_mod", "version": "2.0.0"},
        )
        assert r["swapped"] is True
        assert r["rollback_available"] is True

    def test_rollback(self):
        swap = self.hs.hotswap({"name": "old"}, {"name": "new"})
        r = self.hs.rollback({"swap_id": swap["id"]})
        assert r["rolled_back"] is True

    def test_rollback_not_found(self):
        r = self.hs.rollback({"swap_id": "bad"})
        assert r["rolled_back"] is False

    def test_list_swaps(self):
        self.hs.hotswap({"name": "a"}, {"name": "b"})
        assert len(self.hs.list_swaps()) == 1

    def test_health(self):
        assert self.hs.health_check()["service"] == "hot_swap_engine"

    def test_restart(self):
        self.hs.hotswap({"name": "a"}, {"name": "b"})
        self.hs.restart()
        assert self.hs.list_swaps() == []


# ═══════════════════════════════════════════════════════════════
# ModuleCompatibilityChecker
# ═══════════════════════════════════════════════════════════════
class TestModuleCompatibilityChecker:
    def setup_method(self):
        self.cc = ModuleCompatibilityChecker()

    def test_check_api_compatible(self):
        r = self.cc.check_api({
            "name": "mod",
            "required_apis": ["init", "run"],
            "provided_apis": ["init", "run", "stop"],
        })
        assert r["compatible"] is True
        assert r["missing"] == []

    def test_check_api_incompatible(self):
        r = self.cc.check_api({
            "name": "mod",
            "required_apis": ["init", "run", "stop"],
            "provided_apis": ["init"],
        })
        assert r["compatible"] is False
        assert "run" in r["missing"]

    def test_check_version_compatible(self):
        r = self.cc.check_version({
            "name": "mod",
            "current_version": "2.1.0",
            "required_version": "1.5.0",
        })
        assert r["compatible"] is True

    def test_check_version_incompatible(self):
        r = self.cc.check_version({
            "name": "mod",
            "current_version": "1.0.0",
            "required_version": "2.0.0",
        })
        assert r["compatible"] is False

    def test_check_dependencies_satisfied(self):
        r = self.cc.check_dependencies({
            "name": "mod",
            "dependencies": ["a", "b"],
            "available_modules": ["a", "b", "c"],
        })
        assert r["satisfied"] is True

    def test_check_dependencies_missing(self):
        r = self.cc.check_dependencies({
            "name": "mod",
            "dependencies": ["a", "d"],
            "available_modules": ["a", "b"],
        })
        assert r["satisfied"] is False
        assert "d" in r["missing"]

    def test_health(self):
        assert self.cc.health_check()["service"] == "module_compatibility_checker"

    def test_restart(self):
        self.cc.check_api({"name": "x", "required_apis": [], "provided_apis": []})
        self.cc.restart()
        assert self.cc.get_stats()["api_checks"] == 0


# ═══════════════════════════════════════════════════════════════
# ModularExplainabilityEngine
# ═══════════════════════════════════════════════════════════════
class TestModularExplainabilityEngine:
    def setup_method(self):
        self.pe = CognitivePartitioningEngine()
        self.me = ModularExplainabilityEngine(partitioning=self.pe)

    def test_explain_module_active(self):
        r = self.me.explain_module({"name": "mod1", "state": "active",
                                     "version": "1.0.0"})
        assert r["type"] == "module"
        assert r["module_name"] == "mod1"
        assert any("actif" in reason for reason in r["reasons"])

    def test_explain_module_inactive(self):
        r = self.me.explain_module({"name": "mod2", "state": "inactive"})
        assert any("inactif" in reason for reason in r["reasons"])

    def test_explain_module_shutdown(self):
        r = self.me.explain_module({"name": "mod3", "state": "shutdown"})
        assert any("arrêté" in reason for reason in r["reasons"])

    def test_explain_swap_upgrade(self):
        r = self.me.explain_swap(
            {"name": "old", "version": "1.0", "swap_reason": "upgrade"},
            {"name": "new", "version": "2.0"},
        )
        assert r["type"] == "swap"
        assert any("mise à jour" in reason for reason in r["reasons"])

    def test_explain_swap_failure(self):
        r = self.me.explain_swap(
            {"name": "old", "version": "1.0", "swap_reason": "failure"},
            {"name": "new", "version": "2.0"},
        )
        assert any("défaillant" in reason for reason in r["reasons"])

    def test_explain_partitioning_empty(self):
        r = self.me.explain_partitioning()
        assert r["type"] == "partitioning"
        assert r["total_partitions"] == 0
        assert any("Aucune" in reason for reason in r["reasons"])

    def test_explain_partitioning_with_data(self):
        self.pe.partition_cognition({"name": "p1", "modules": ["m1"]})
        r = self.me.explain_partitioning()
        assert r["total_partitions"] == 1

    def test_health(self):
        assert self.me.health_check()["service"] == "modular_explainability"

    def test_restart(self):
        self.me.explain_module({"name": "x", "state": "active"})
        self.me.restart()
        assert self.me.get_stats()["module_explanations"] == 0

    def test_list_explanations(self):
        self.me.explain_module({"name": "a", "state": "active"})
        self.me.explain_module({"name": "b", "state": "inactive"})
        assert len(self.me.list_explanations()) == 2
