"""
Tests unitaires — EXO v11 Auto-apprentissage & Auto-optimisation
Couvre: MetaMemory, LearningEngine, FeedbackEngine, OptimizationEngine,
SelfDiagnosisEngine, AutoTuningEngine, MetaPlanner, MetaSupervisor,
AutoExplanation, AutoGovernance.
"""

import sys
import time
from pathlib import Path

import pytest


# ═════════════════════════════════════════════════════
#  MetaMemory
# ═════════════════════════════════════════════════════

class TestMetaMemory:
    """Tests de la mémoire d'apprentissage persistante."""

    def _make(self, tmp_path):
        from meta_memory import MetaMemory
        return MetaMemory(persist_dir=str(tmp_path))

    def test_create(self, tmp_path):
        mem = self._make(tmp_path)
        assert mem is not None

    def test_add_entry(self, tmp_path):
        mem = self._make(tmp_path)
        eid = mem.meta_add({"category": "preference", "key": "lang", "value": "fr"})
        assert eid.startswith("meta_")

    def test_get_entry(self, tmp_path):
        mem = self._make(tmp_path)
        mem.meta_add({"category": "preference", "key": "lang", "value": "fr"})
        results = mem.meta_get("lang")
        assert len(results) >= 1
        assert results[0]["key"] == "lang"
        assert results[0]["value"] == "fr"

    def test_update_entry(self, tmp_path):
        mem = self._make(tmp_path)
        eid = mem.meta_add({"category": "preference", "key": "vol", "value": 50})
        ok = mem.meta_update(eid, {"value": 80})
        assert ok is True
        results = mem.meta_get("vol")
        assert results[0]["value"] == 80

    def test_delete_entry(self, tmp_path):
        mem = self._make(tmp_path)
        eid = mem.meta_add({"category": "pattern", "key": "test", "value": 1})
        ok = mem.meta_delete(eid)
        assert ok is True
        results = mem.meta_get("test")
        assert len(results) == 0

    def test_list_entries(self, tmp_path):
        mem = self._make(tmp_path)
        mem.meta_add({"category": "preference", "key": "a", "value": 1})
        mem.meta_add({"category": "strategy", "key": "b", "value": 2})
        mem.meta_add({"category": "preference", "key": "c", "value": 3})
        prefs = mem.list_entries("preference")
        assert len(prefs) == 2

    def test_stats(self, tmp_path):
        mem = self._make(tmp_path)
        mem.meta_add({"category": "preference", "key": "x", "value": 1})
        mem.meta_add({"category": "pattern", "key": "y", "value": 2})
        stats = mem.get_stats()
        assert stats["total"] == 2
        assert "preference" in stats["by_category"]

    def test_get_preferences(self, tmp_path):
        mem = self._make(tmp_path)
        mem.meta_add({"category": "preference", "key": "k", "value": "v"})
        prefs = mem.get_preferences()
        assert len(prefs) == 1

    def test_get_strategies(self, tmp_path):
        mem = self._make(tmp_path)
        mem.meta_add({"category": "strategy", "key": "s", "value": "v"})
        strats = mem.get_strategies()
        assert len(strats) == 1

    def test_clear_category(self, tmp_path):
        mem = self._make(tmp_path)
        mem.meta_add({"category": "pattern", "key": "a", "value": 1})
        mem.meta_add({"category": "pattern", "key": "b", "value": 2})
        mem.meta_add({"category": "preference", "key": "c", "value": 3})
        removed = mem.clear_category("pattern")
        assert removed == 2
        assert mem.get_stats()["total"] == 1

    def test_persistence(self, tmp_path):
        from meta_memory import MetaMemory
        mem1 = MetaMemory(persist_dir=str(tmp_path))
        mem1.meta_add({"category": "preference", "key": "persist_test", "value": 42})
        # Reload
        mem2 = MetaMemory(persist_dir=str(tmp_path))
        results = mem2.meta_get("persist_test")
        assert len(results) == 1
        assert results[0]["value"] == 42

    def test_update_nonexistent(self, tmp_path):
        mem = self._make(tmp_path)
        ok = mem.meta_update("nonexistent", {"value": 1})
        assert ok is False

    def test_delete_nonexistent(self, tmp_path):
        mem = self._make(tmp_path)
        ok = mem.meta_delete("nonexistent")
        assert ok is False

    def test_search_by_tag(self, tmp_path):
        mem = self._make(tmp_path)
        mem.meta_add({"category": "pattern", "key": "x", "value": 1,
                       "tags": ["important"]})
        results = mem.meta_get("important")
        assert len(results) == 1


# ═════════════════════════════════════════════════════
#  AutoGovernance
# ═════════════════════════════════════════════════════

class TestAutoGovernance:
    """Tests de la gouvernance automatique."""

    def _make(self, tmp_path=None):
        from auto_governance import AutoGovernance
        from meta_memory import MetaMemory
        mem = MetaMemory(persist_dir=str(tmp_path)) if tmp_path else None
        return AutoGovernance(mem)

    def test_create(self):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        assert gov is not None

    def test_allow_learn_default(self):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        assert gov.check_permission("learn", {"key": "test"}) is True

    def test_allow_tune_default(self):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        assert gov.check_permission("tune", {"parameter": "cache_ttl_s"}) is True

    def test_deny_disabled_permission(self):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        gov.set_permissions({"learn": False})
        assert gov.check_permission("learn", {}) is False

    def test_deny_blocked_key(self):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        gov.set_rules({"blocked_keys": ["secret_key"]})
        assert gov.check_permission("learn", {"key": "secret_key"}) is False

    def test_deny_blocked_category(self):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        gov.set_rules({"blocked_categories": ["pattern_reseau"]})
        assert gov.check_permission("learn",
                                     {"type": "pattern_reseau"}) is False

    def test_session_limit(self):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        gov.set_limits({"max_learn_per_session": 3})
        for i in range(3):
            assert gov.check_permission("learn", {"key": f"k{i}"}) is True
        assert gov.check_permission("learn", {"key": "overflow"}) is False

    def test_reset_session_counters(self):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        gov.set_limits({"max_learn_per_session": 2})
        gov.check_permission("learn", {"key": "a"})
        gov.check_permission("learn", {"key": "b"})
        assert gov.check_permission("learn", {"key": "c"}) is False
        gov.reset_session_counters()
        assert gov.check_permission("learn", {"key": "c"}) is True

    def test_audit_log(self):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        gov.check_permission("learn", {"key": "test"})
        log = gov.get_audit_log()
        assert len(log) >= 1
        assert log[-1]["action"] == "learn"

    def test_stats(self):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        gov.check_permission("learn", {"key": "a"})
        gov.set_permissions({"tune": False})
        gov.check_permission("tune", {})
        stats = gov.get_stats()
        assert stats["checks"] == 2
        assert stats["allowed"] >= 1
        assert stats["denied"] >= 1

    def test_get_rules(self):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        rules = gov.get_rules()
        assert "allow_learn" in rules

    def test_get_limits(self):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        limits = gov.get_limits()
        assert "max_learn_per_session" in limits

    def test_get_permissions(self):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        perms = gov.get_permissions()
        assert "learn" in perms


# ═════════════════════════════════════════════════════
#  LearningEngine
# ═════════════════════════════════════════════════════

class TestLearningEngine:
    """Tests du moteur d'apprentissage."""

    def _make(self, tmp_path, governance=None):
        from meta_memory import MetaMemory
        from learning_engine import LearningEngine
        mem = MetaMemory(persist_dir=str(tmp_path))
        return LearningEngine(mem, governance), mem

    def test_create(self, tmp_path):
        eng, _ = self._make(tmp_path)
        assert eng is not None

    def test_learn_event(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eid = eng.learn({"type": "preference", "key": "theme", "value": "dark"})
        assert eid is not None
        assert eid.startswith("meta_")

    def test_learn_preference(self, tmp_path):
        eng, mem = self._make(tmp_path)
        eid = eng.learn_preference("volume", 80)
        assert eid is not None
        prefs = mem.get_preferences()
        assert any(p["key"] == "volume" for p in prefs)

    def test_learn_pattern(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eid = eng.learn_pattern({
            "name": "morning_routine",
            "description": "Lights on at 7am",
            "frequency": "daily",
            "type": "pattern_domotique",
        })
        assert eid is not None

    def test_learn_strategy(self, tmp_path):
        eng, mem = self._make(tmp_path)
        eid = eng.learn_strategy({
            "name": "use_ha_light_on",
            "description": "Preferred tool for lights",
            "success_rate": 0.95,
        })
        assert eid is not None
        strats = mem.get_strategies()
        assert len(strats) >= 1

    def test_learn_from_task_success(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eid = eng.learn_from_task_result({
            "status": "completed",
            "goal": "turn on kitchen light",
            "elapsed_s": 1.2,
        })
        assert eid is not None

    def test_learn_from_task_failure(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eid = eng.learn_from_task_result({
            "status": "failed",
            "goal": "play music",
            "error": "speaker offline",
        })
        assert eid is not None

    def test_learn_unknown_status(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eid = eng.learn_from_task_result({"status": "pending"})
        assert eid is None

    def test_governance_rejection(self, tmp_path):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        gov.set_permissions({"learn": False})
        eng, _ = self._make(tmp_path, governance=gov)
        eid = eng.learn({"key": "blocked"})
        assert eid is None

    def test_get_learned(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.learn_preference("a", 1)
        eng.learn_preference("b", 2)
        entries = eng.get_learned("preference")
        assert len(entries) >= 2

    def test_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.learn({"key": "x", "value": 1})
        stats = eng.get_stats()
        assert stats["total_learned"] == 1

    def test_session_events(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.learn({"key": "s1", "value": "v1"})
        events = eng.get_session_events()
        assert len(events) == 1


# ═════════════════════════════════════════════════════
#  FeedbackEngine
# ═════════════════════════════════════════════════════

class TestFeedbackEngine:
    """Tests du moteur de feedback."""

    def _make(self, tmp_path):
        from meta_memory import MetaMemory
        from learning_engine import LearningEngine
        from feedback_engine import FeedbackEngine
        mem = MetaMemory(persist_dir=str(tmp_path))
        learning = LearningEngine(mem)
        return FeedbackEngine(learning), mem

    def test_create(self, tmp_path):
        eng, _ = self._make(tmp_path)
        assert eng is not None

    def test_positive_feedback(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.feedback_positive({"key": "good_response", "value": "correct"})
        stats = eng.get_stats()
        assert stats["by_type"]["positive"] == 1

    def test_negative_feedback(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.feedback_negative({"key": "bad_response", "value": "wrong"})
        stats = eng.get_stats()
        assert stats["by_type"]["negative"] == 1

    def test_correction(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.feedback_correction({"key": "fix_answer", "value": "corrected"})
        stats = eng.get_stats()
        assert stats["by_type"]["correction"] == 1

    def test_preference(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.feedback_preference("volume", 90)
        history = eng.get_feedback_history()
        assert len(history) >= 1

    def test_reject(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.feedback_reject({"key": "unwanted", "value": "no"})
        stats = eng.get_stats()
        assert stats["by_type"]["reject"] == 1

    def test_validate(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.feedback_validate({"key": "confirmed", "value": "yes"})
        stats = eng.get_stats()
        assert stats["by_type"]["validate"] == 1

    def test_positive_rate(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.feedback_positive({"key": "g1"})
        eng.feedback_positive({"key": "g2"})
        eng.feedback_negative({"key": "b1"})
        stats = eng.get_stats()
        assert 0.5 < stats["positive_rate"] < 0.8

    def test_history_limit(self, tmp_path):
        eng, _ = self._make(tmp_path)
        for i in range(10):
            eng.feedback_positive({"key": f"item_{i}"})
        history = eng.get_feedback_history(5)
        assert len(history) == 5


# ═════════════════════════════════════════════════════
#  OptimizationEngine
# ═════════════════════════════════════════════════════

class TestOptimizationEngine:
    """Tests du moteur d'optimisation."""

    def _make(self, tmp_path):
        from meta_memory import MetaMemory
        from optimization_engine import OptimizationEngine
        mem = MetaMemory(persist_dir=str(tmp_path))
        return OptimizationEngine(mem), mem

    def test_create(self, tmp_path):
        eng, _ = self._make(tmp_path)
        assert eng is not None

    def test_optimize_pipeline(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.optimize_pipeline()
        assert "improvements" in result

    def test_optimize_plans(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.optimize_plans()
        assert "improvements" in result

    def test_optimize_domotics(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.optimize_domotics()
        assert "improvements" in result

    def test_optimize_network(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.optimize_network()
        assert "improvements" in result

    def test_optimize_caches(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.optimize_caches()
        assert "improvements" in result

    def test_optimize_all(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.optimize_all()
        assert "pipeline" in result
        assert "plans" in result

    def test_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.optimize_pipeline()
        stats = eng.get_stats()
        assert stats["optimizations_run"] >= 1

    def test_history(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.optimize_pipeline()
        history = eng.get_history()
        assert len(history) >= 1


# ═════════════════════════════════════════════════════
#  SelfDiagnosisEngine
# ═════════════════════════════════════════════════════

class TestSelfDiagnosisEngine:
    """Tests du moteur d'auto-diagnostic."""

    def _make(self, tmp_path):
        from meta_memory import MetaMemory
        from self_diagnosis_engine import SelfDiagnosisEngine
        mem = MetaMemory(persist_dir=str(tmp_path))
        return SelfDiagnosisEngine(mem), mem

    def test_create(self, tmp_path):
        eng, _ = self._make(tmp_path)
        assert eng is not None

    def test_diagnose_healthy(self, tmp_path):
        eng, _ = self._make(tmp_path)
        report = eng.diagnose()
        assert report["overall_health"] in ("healthy", "degraded", "critical")

    def test_detect_anomalies(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.detect_anomalies()
        assert isinstance(result, dict)
        assert "anomalies" in result
        assert isinstance(result["anomalies"], list)

    def test_detect_regressions(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.detect_regressions()
        assert isinstance(result, dict)
        assert "regressions" in result

    def test_detect_instabilities(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.detect_instabilities()
        assert isinstance(result, dict)
        assert "instabilities" in result

    def test_health_check(self, tmp_path):
        eng, _ = self._make(tmp_path)
        hc = eng.health_check()
        assert "status" in hc

    def test_diagnose_with_data(self, tmp_path):
        eng, mem = self._make(tmp_path)
        # Add some task failures to trigger anomalies
        for i in range(5):
            mem.meta_add({
                "category": "optimization",
                "key": f"task_failure:test_{i}",
                "value": {"error": "timeout", "status": "failed"},
                "tags": ["task", "failure"],
            })
        report = eng.diagnose()
        assert "anomalies" in report
        assert "overall_health" in report

    def test_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.diagnose()
        stats = eng.get_stats()
        assert stats["diagnoses_run"] >= 1

    def test_history(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.diagnose()
        history = eng.get_history()
        assert len(history) >= 1


# ═════════════════════════════════════════════════════
#  AutoTuningEngine
# ═════════════════════════════════════════════════════

class TestAutoTuningEngine:
    """Tests du moteur d'auto-réglage."""

    def _make(self, tmp_path, governance=None):
        from meta_memory import MetaMemory
        from auto_tuning_engine import AutoTuningEngine
        mem = MetaMemory(persist_dir=str(tmp_path))
        return AutoTuningEngine(mem, governance), mem

    def test_create(self, tmp_path):
        eng, _ = self._make(tmp_path)
        assert eng is not None

    def test_tune_valid(self, tmp_path):
        eng, _ = self._make(tmp_path)
        ok = eng.tune("cache_ttl_s", 600)
        assert ok is True
        assert eng.get_value("cache_ttl_s") == 600

    def test_tune_out_of_range(self, tmp_path):
        eng, _ = self._make(tmp_path)
        ok = eng.tune("cache_ttl_s", 99999)
        assert ok is False

    def test_tune_unknown_param(self, tmp_path):
        eng, _ = self._make(tmp_path)
        ok = eng.tune("nonexistent_param", 42)
        assert ok is False

    def test_tune_governance_reject(self, tmp_path):
        from auto_governance import AutoGovernance
        gov = AutoGovernance()
        gov.set_permissions({"tune": False})
        eng, _ = self._make(tmp_path, governance=gov)
        ok = eng.tune("cache_ttl_s", 600)
        assert ok is False

    def test_auto_tune_all(self, tmp_path):
        eng, _ = self._make(tmp_path)
        result = eng.auto_tune_all()
        assert "adjustments" in result
        assert "current_params" in result

    def test_get_tunings(self, tmp_path):
        eng, _ = self._make(tmp_path)
        tunings = eng.get_tunings()
        assert "cache_ttl_s" in tunings
        assert "llm_temperature" in tunings

    def test_get_value(self, tmp_path):
        eng, _ = self._make(tmp_path)
        val = eng.get_value("retry_max")
        assert val == 3  # default

    def test_get_value_nonexistent(self, tmp_path):
        eng, _ = self._make(tmp_path)
        val = eng.get_value("nope")
        assert val is None

    def test_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.tune("cache_ttl_s", 120)
        stats = eng.get_stats()
        assert stats["tunings_applied"] >= 1

    def test_history(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.tune("retry_max", 4)
        history = eng.get_history()
        assert len(history) >= 1
        assert history[-1]["parameter"] == "retry_max"

    def test_persistence(self, tmp_path):
        from meta_memory import MetaMemory
        from auto_tuning_engine import AutoTuningEngine
        mem = MetaMemory(persist_dir=str(tmp_path))
        eng1 = AutoTuningEngine(mem)
        eng1.tune("cache_ttl_s", 999)
        # Reload
        mem2 = MetaMemory(persist_dir=str(tmp_path))
        eng2 = AutoTuningEngine(mem2)
        assert eng2.get_value("cache_ttl_s") == 999


# ═════════════════════════════════════════════════════
#  MetaPlanner
# ═════════════════════════════════════════════════════

class TestMetaPlanner:
    """Tests du méta-planificateur adaptatif."""

    def _make(self, tmp_path):
        from meta_memory import MetaMemory
        from meta_planner import MetaPlanner
        mem = MetaMemory(persist_dir=str(tmp_path))
        return MetaPlanner(mem), mem

    def test_create(self, tmp_path):
        eng, _ = self._make(tmp_path)
        assert eng is not None

    def test_adapt_plan(self, tmp_path):
        eng, _ = self._make(tmp_path)
        plan = {
            "goal": "turn on lights",
            "steps": [
                {"tool": "ha_light_on", "args": {"entity": "light.salon"}},
                {"tool": "ha_light_on", "args": {"entity": "light.cuisine"}},
            ],
        }
        adapted = eng.adapt_plan(plan)
        assert "steps" in adapted
        assert "adaptations" in adapted

    def test_adapt_empty_plan(self, tmp_path):
        eng, _ = self._make(tmp_path)
        plan = {"goal": "nothing", "steps": []}
        adapted = eng.adapt_plan(plan)
        assert adapted["steps"] == []

    def test_adapt_method(self, tmp_path):
        eng, _ = self._make(tmp_path)
        method = {"name": "control_light", "tool": "ha_light_on"}
        adapted = eng.adapt_method(method)
        assert isinstance(adapted, dict)

    def test_adapt_strategy(self, tmp_path):
        eng, mem = self._make(tmp_path)
        # Add some learned strategies
        mem.meta_add({
            "category": "strategy",
            "key": "use_ha_light",
            "value": {"success_rate": 0.9},
        })
        strategy = {"name": "light_control", "primary_tool": "ha_light_on"}
        adapted = eng.adapt_strategy(strategy)
        assert isinstance(adapted, dict)

    def test_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.adapt_plan({"goal": "test", "steps": [{"tool": "t"}]})
        stats = eng.get_stats()
        assert stats["plans_adapted"] >= 1

    def test_adaptations_history(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.adapt_plan({"goal": "test", "steps": [{"tool": "t"}]})
        history = eng.get_adaptations()
        assert len(history) >= 1


# ═════════════════════════════════════════════════════
#  MetaSupervisor
# ═════════════════════════════════════════════════════

class TestMetaSupervisor:
    """Tests du superviseur d'apprentissage."""

    def _make(self, tmp_path):
        from meta_memory import MetaMemory
        from meta_supervisor import MetaSupervisor
        mem = MetaMemory(persist_dir=str(tmp_path))
        return MetaSupervisor(mem), mem

    def test_create(self, tmp_path):
        eng, _ = self._make(tmp_path)
        assert eng is not None

    def test_validate_valid_entry(self, tmp_path):
        eng, _ = self._make(tmp_path)
        ok = eng.validate_learning({
            "category": "preference",
            "key": "theme",
            "confidence": 0.9,
            "source": "user",
        })
        assert ok is True

    def test_reject_low_confidence(self, tmp_path):
        eng, _ = self._make(tmp_path)
        ok = eng.validate_learning({
            "category": "pattern",
            "key": "weak",
            "confidence": 0.1,
            "source": "observation",
        })
        assert ok is False

    def test_reject_forbidden_category(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.set_rules({"forbidden_categories": ["pattern_reseau"]})
        ok = eng.validate_learning({
            "category": "pattern_reseau",
            "key": "scan",
            "confidence": 0.9,
            "source": "system",
        })
        assert ok is False

    def test_reject_missing_source(self, tmp_path):
        eng, _ = self._make(tmp_path)
        ok = eng.validate_learning({
            "category": "pattern",
            "key": "no_source",
            "confidence": 0.8,
        })
        assert ok is False

    def test_rate_limit(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.set_rules({"max_learning_rate_per_min": 3})
        for i in range(3):
            ok = eng.validate_learning({
                "category": "pattern", "key": f"k{i}",
                "confidence": 0.9, "source": "test",
            })
            assert ok is True
        ok = eng.validate_learning({
            "category": "pattern", "key": "overflow",
            "confidence": 0.9, "source": "test",
        })
        assert ok is False

    def test_rollback(self, tmp_path):
        eng, mem = self._make(tmp_path)
        eid = mem.meta_add({"category": "pattern", "key": "to_remove", "value": 1})
        ok = eng.rollback_learning(eid)
        assert ok is True
        assert mem.meta_get("to_remove") == []

    def test_rollback_nonexistent(self, tmp_path):
        eng, _ = self._make(tmp_path)
        ok = eng.rollback_learning("nonexistent_id")
        assert ok is False

    def test_enforce_rules(self, tmp_path):
        eng, mem = self._make(tmp_path)
        # Add low-confidence entry
        mem.meta_add({"category": "pattern", "key": "weak_entry",
                       "value": 1, "confidence": 0.1})
        result = eng.enforce_rules()
        assert "actions" in result

    def test_drift_report(self, tmp_path):
        eng, mem = self._make(tmp_path)
        for i in range(25):
            mem.meta_add({"category": "pattern", "key": f"p{i}", "value": i})
        report = eng.get_drift_report()
        assert "total_entries" in report
        assert "warnings" in report

    def test_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.validate_learning({
            "category": "pattern", "key": "x",
            "confidence": 0.8, "source": "test",
        })
        stats = eng.get_stats()
        assert stats["validations"] >= 1

    def test_alerts(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.validate_learning({
            "category": "pattern", "key": "low",
            "confidence": 0.1, "source": "test",
        })
        alerts = eng.get_alerts()
        assert len(alerts) >= 1


# ═════════════════════════════════════════════════════
#  AutoExplanation
# ═════════════════════════════════════════════════════

class TestAutoExplanation:
    """Tests du moteur d'auto-explication."""

    def _make(self, tmp_path):
        from meta_memory import MetaMemory
        from auto_explanation import AutoExplanation
        mem = MetaMemory(persist_dir=str(tmp_path))
        return AutoExplanation(mem), mem

    def test_create(self, tmp_path):
        eng, _ = self._make(tmp_path)
        assert eng is not None

    def test_explain_decision(self, tmp_path):
        eng, _ = self._make(tmp_path)
        text = eng.explain_decision("allumer la lumière")
        assert "allumer la lumière" in text

    def test_explain_decision_with_strategy(self, tmp_path):
        eng, mem = self._make(tmp_path)
        mem.meta_add({
            "category": "strategy",
            "key": "ha_light_on",
            "value": {"success_rate": 0.95},
        })
        text = eng.explain_decision("ha_light_on")
        assert "stratégie" in text.lower() or "ha_light_on" in text

    def test_explain_learning_found(self, tmp_path):
        eng, mem = self._make(tmp_path)
        eid = mem.meta_add({
            "category": "preference",
            "key": "volume",
            "value": 80,
            "source": "user",
            "confidence": 1.0,
        })
        text = eng.explain_learning(eid)
        assert "volume" in text

    def test_explain_learning_not_found(self, tmp_path):
        eng, _ = self._make(tmp_path)
        text = eng.explain_learning("nonexistent_id")
        assert "non trouvée" in text

    def test_explain_optimization(self, tmp_path):
        eng, _ = self._make(tmp_path)
        text = eng.explain_optimization({
            "type": "pipeline",
            "improvements": [
                {"parameter": "llm_max_tokens", "old_value": 1024, "new_value": 512},
            ],
        })
        assert "pipeline" in text.lower()

    def test_explain_optimization_empty(self, tmp_path):
        eng, _ = self._make(tmp_path)
        text = eng.explain_optimization({"type": "caches", "improvements": []})
        assert "aucune" in text.lower()

    def test_explain_tuning(self, tmp_path):
        eng, mem = self._make(tmp_path)
        mem.meta_add({
            "category": "tuning",
            "key": "tuning:cache_ttl_s",
            "value": 600,
        })
        text = eng.explain_tuning("cache_ttl_s")
        assert "cache_ttl_s" in text

    def test_explain_tuning_no_history(self, tmp_path):
        eng, _ = self._make(tmp_path)
        text = eng.explain_tuning("unknown_param")
        assert "aucun" in text.lower()

    def test_explain_diagnosis(self, tmp_path):
        eng, _ = self._make(tmp_path)
        text = eng.explain_diagnosis({
            "health": "healthy",
            "issues": [],
            "anomalies": [],
            "regressions": [],
        })
        assert "healthy" in text

    def test_explain_diagnosis_with_issues(self, tmp_path):
        eng, _ = self._make(tmp_path)
        text = eng.explain_diagnosis({
            "health": "degraded",
            "issues": [{"type": "high_latency", "detail": "STT > 5s"}],
            "anomalies": [],
            "regressions": [],
        })
        assert "problème" in text

    def test_explanation_log(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.explain_decision("test_action")
        log = eng.get_explanation_log()
        assert len(log) >= 1
        assert log[-1]["kind"] == "decision"

    def test_stats(self, tmp_path):
        eng, _ = self._make(tmp_path)
        eng.explain_decision("a")
        eng.explain_tuning("b")
        stats = eng.get_stats()
        assert stats["explanations_generated"] == 2


# ═════════════════════════════════════════════════════
#  Intégration inter-modules v11
# ═════════════════════════════════════════════════════

class TestV11Integration:
    """Tests d'intégration entre les modules v11."""

    def _make_all(self, tmp_path):
        from meta_memory import MetaMemory
        from auto_governance import AutoGovernance
        from learning_engine import LearningEngine
        from feedback_engine import FeedbackEngine
        from self_diagnosis_engine import SelfDiagnosisEngine
        from optimization_engine import OptimizationEngine
        from auto_tuning_engine import AutoTuningEngine
        from meta_planner import MetaPlanner
        from meta_supervisor import MetaSupervisor
        from auto_explanation import AutoExplanation

        mem = MetaMemory(persist_dir=str(tmp_path))
        gov = AutoGovernance(mem)
        learning = LearningEngine(mem, gov)
        feedback = FeedbackEngine(learning)
        diagnosis = SelfDiagnosisEngine(mem)
        optimization = OptimizationEngine(mem, diagnosis)
        tuning = AutoTuningEngine(mem, gov)
        planner = MetaPlanner(mem)
        supervisor = MetaSupervisor(mem, learning, gov)
        explanation = AutoExplanation(mem)

        return {
            "memory": mem, "governance": gov, "learning": learning,
            "feedback": feedback, "diagnosis": diagnosis,
            "optimization": optimization, "tuning": tuning,
            "planner": planner, "supervisor": supervisor,
            "explanation": explanation,
        }

    def test_full_pipeline_create(self, tmp_path):
        """All v11 modules can be instantiated together."""
        modules = self._make_all(tmp_path)
        assert len(modules) == 10

    def test_learn_then_explain(self, tmp_path):
        """Learning + Explanation integration."""
        m = self._make_all(tmp_path)
        eid = m["learning"].learn_preference("theme", "dark")
        text = m["explanation"].explain_learning(eid)
        assert "theme" in text

    def test_feedback_propagates_to_memory(self, tmp_path):
        """Feedback → Learning → MetaMemory chain."""
        m = self._make_all(tmp_path)
        m["feedback"].feedback_positive({"context": "good_answer", "detail": "ok"})
        results = m["memory"].meta_get("feedback:positive")
        assert len(results) >= 1

    def test_governance_blocks_learning(self, tmp_path):
        """Governance blocks learning when disabled."""
        m = self._make_all(tmp_path)
        m["governance"].set_rules({"blocked_keys": ["secret"]})
        eid = m["learning"].learn({"key": "secret", "value": "data"})
        assert eid is None

    def test_supervisor_validates_then_learn(self, tmp_path):
        """Supervisor validates before learning."""
        m = self._make_all(tmp_path)
        entry = {
            "category": "preference", "key": "color",
            "value": "blue", "confidence": 0.9, "source": "user",
        }
        ok = m["supervisor"].validate_learning(entry)
        assert ok is True
        eid = m["learning"].learn(entry)
        assert eid is not None

    def test_supervisor_rejects_low_confidence(self, tmp_path):
        """Supervisor rejects low-confidence learning."""
        m = self._make_all(tmp_path)
        entry = {
            "category": "pattern", "key": "weak",
            "confidence": 0.05, "source": "system",
        }
        ok = m["supervisor"].validate_learning(entry)
        assert ok is False

    def test_diagnose_then_explain(self, tmp_path):
        """Diagnosis + Explanation integration."""
        m = self._make_all(tmp_path)
        report = m["diagnosis"].diagnose()
        text = m["explanation"].explain_diagnosis(report)
        assert len(text) > 0

    def test_tune_then_explain(self, tmp_path):
        """Tuning + Explanation integration."""
        m = self._make_all(tmp_path)
        m["tuning"].tune("cache_ttl_s", 500)
        text = m["explanation"].explain_tuning("cache_ttl_s")
        assert "cache_ttl_s" in text

    def test_optimize_then_diagnose(self, tmp_path):
        """Optimization then Diagnosis."""
        m = self._make_all(tmp_path)
        m["optimization"].optimize_all()
        report = m["diagnosis"].diagnose()
        assert "overall_health" in report

    def test_all_stats(self, tmp_path):
        """All modules return stats."""
        m = self._make_all(tmp_path)
        for name, mod in m.items():
            if hasattr(mod, "get_stats"):
                stats = mod.get_stats()
                assert isinstance(stats, dict), f"{name}.get_stats() should return dict"

    def test_planner_with_learned_strategies(self, tmp_path):
        """MetaPlanner uses learned strategies."""
        m = self._make_all(tmp_path)
        m["learning"].learn_strategy({
            "name": "ha_light_on",
            "description": "Best light tool",
            "success_rate": 0.98,
        })
        plan = {"goal": "lights", "steps": [{"tool": "ha_light_on"}]}
        adapted = m["planner"].adapt_plan(plan)
        assert "steps" in adapted

    def test_governance_tune_limit(self, tmp_path):
        """Governance enforces tuning session limits."""
        m = self._make_all(tmp_path)
        m["governance"].set_limits({"max_tune_per_session": 2})
        assert m["tuning"].tune("cache_ttl_s", 100) is True
        assert m["tuning"].tune("retry_max", 4) is True
        assert m["tuning"].tune("llm_temperature", 0.5) is False
