"""
Tests unitaires — EXO v10 Agentification
Couvre: IntentEngine v3, TaskPlanner v10, TaskExecutor v10,
TaskVerifier v10, ContextEngine v3, TaskRecovery, TaskOptimizer,
TaskMemory, AgentStateMachine, AgentManager.
"""

import asyncio
import sys
import time
from pathlib import Path

import pytest



# ═════════════════════════════════════════════════════
#  IntentEngine v3 (NLU)
# ═════════════════════════════════════════════════════

class TestIntentEngineV3:
    """Tests du moteur d'intentions v3."""

    def _make_engine(self):
        from nlu_server import IntentEngine, RegexNLU
        return IntentEngine(RegexNLU())

    def test_create_engine(self):
        engine = self._make_engine()
        assert engine is not None

    def test_parse_simple_intent(self):
        engine = self._make_engine()
        intent = engine.parse_intent("Quel temps fait-il ?")
        assert intent is not None
        assert hasattr(intent, "text")
        assert hasattr(intent, "intent_type")
        assert intent.text == "Quel temps fait-il ?"

    def test_parse_intent_to_dict(self):
        engine = self._make_engine()
        intent = engine.parse_intent("Bonjour")
        d = intent.to_dict()
        assert isinstance(d, dict)
        assert "text" in d
        assert "intent_type" in d
        assert "goals" in d
        assert "constraints" in d

    def test_detect_multi_step_intent(self):
        engine = self._make_engine()
        intent = engine.parse_intent("D'abord cherche la météo, puis envoie un résumé")
        assert intent.intent_type in ("multi_step", "action_complex", "scenario")

    def test_detect_conditional_intent(self):
        engine = self._make_engine()
        intent = engine.parse_intent("Si il pleut alors rappelle-moi de prendre un parapluie")
        assert intent.intent_type in ("conditional", "action_complex")

    def test_detect_parallel_intent(self):
        engine = self._make_engine()
        intent = engine.parse_intent("En même temps cherche les news et la météo")
        assert intent.intent_type in ("parallel", "action_complex")

    def test_extract_goals(self):
        engine = self._make_engine()
        goals = engine.extract_goals("Cherche les actualités et envoie un email")
        assert isinstance(goals, list)

    def test_extract_constraints(self):
        engine = self._make_engine()
        constraints = engine.extract_constraints("Trouve un restaurant pas trop cher avant 20h")
        assert isinstance(constraints, list)

    def test_extract_preferences(self):
        engine = self._make_engine()
        prefs = engine.extract_preferences("Je préfère la cuisine italienne")
        assert isinstance(prefs, list)

    def test_simple_intent_type(self):
        engine = self._make_engine()
        intent = engine.parse_intent("Bonjour")
        assert intent.intent_type == "action_simple"

    def test_intent_has_engine_field(self):
        engine = self._make_engine()
        intent = engine.parse_intent("Bonjour")
        assert intent.engine == "regex"


# ═════════════════════════════════════════════════════
#  IntentType Enum
# ═════════════════════════════════════════════════════

class TestIntentType:

    def test_all_types_exist(self):
        from nlu_server import IntentType
        expected = {"action_simple", "action_complex", "scenario", "multi_step",
                    "conditional", "parallel", "recurring"}
        actual = {e.value for e in IntentType}
        assert expected == actual


# ═════════════════════════════════════════════════════
#  TaskPlanner v10
# ═════════════════════════════════════════════════════

class TestTaskPlannerV10:

    def _make_planner(self):
        from task_planner_server import TaskPlanner
        return TaskPlanner()

    def test_plan_step_has_expected_outcome(self):
        from task_planner_server import PlanStep
        step = PlanStep(index=0, description="test", tool="search_web")
        assert hasattr(step, "expected_outcome")
        assert hasattr(step, "conditions")
        assert step.expected_outcome == ""
        assert step.conditions == []

    def test_plan_step_to_dict_includes_new_fields(self):
        from task_planner_server import PlanStep
        step = PlanStep(
            index=0, description="test", tool="search_web",
            expected_outcome="found results",
            conditions=["internet available"],
        )
        d = step.to_dict()
        assert d["expected_outcome"] == "found results"
        assert d["conditions"] == ["internet available"]

    def test_create_plan_with_expected_outcome(self):
        planner = self._make_planner()
        plan = planner.create_plan("test goal", [
            {"description": "step1", "tool": "search_web",
             "expected_outcome": "results found"},
        ])
        assert plan is not None
        steps = plan.steps
        assert len(steps) >= 1
        assert steps[0].expected_outcome == "results found"

    def test_refine_method_exists(self):
        planner = self._make_planner()
        assert hasattr(planner, "refine")

    def test_refine_updates_plan(self):
        planner = self._make_planner()
        plan = planner.create_plan("test goal", [
            {"description": "step1", "tool": "search_web"},
        ])
        result = planner.refine(plan.plan_id, {
            "expected_outcomes": {0: "better outcome"},
            "priorities": {0: 10},
        })
        assert result is True
        assert plan.steps[0].expected_outcome == "better outcome"
        assert plan.steps[0].priority == 10

    def test_refine_nonexistent_plan(self):
        planner = self._make_planner()
        result = planner.refine("nonexistent", {})
        assert result is False


# ═════════════════════════════════════════════════════
#  TaskExecutor v10
# ═════════════════════════════════════════════════════

class TestTaskExecutorV10:

    def _make_executor(self):
        from task_executor_server import TaskExecutor
        return TaskExecutor()

    def test_create_executor(self):
        executor = self._make_executor()
        assert executor is not None

    def test_pause_nonexistent(self):
        executor = self._make_executor()
        assert executor.pause("nonexistent") is False

    def test_resume_nonexistent(self):
        executor = self._make_executor()
        assert executor.resume("nonexistent") is False

    def test_execution_state_has_pause(self):
        from task_executor_server import ExecutionState
        state = ExecutionState("test", {"steps": []})
        assert hasattr(state, "paused")
        assert state.paused is False
        assert hasattr(state, "_pause_event")

    def test_pause_resume_cycle(self):
        from task_executor_server import ExecutionState
        executor = self._make_executor()
        state = ExecutionState("test_plan", {"steps": []})
        executor._executions["test_plan"] = state
        state.status = "running"

        assert executor.pause("test_plan") is True
        assert state.paused is True
        assert state.status == "paused"

        assert executor.resume("test_plan") is True
        assert state.paused is False
        assert state.status == "running"

    def test_abort_unblocks_pause(self):
        from task_executor_server import ExecutionState
        executor = self._make_executor()
        state = ExecutionState("test_plan", {"steps": []})
        executor._executions["test_plan"] = state
        state.status = "running"

        executor.pause("test_plan")
        assert state._pause_event.is_set() is False

        executor.abort("test_plan")
        assert state._pause_event.is_set() is True  # unblocked


# ═════════════════════════════════════════════════════
#  TaskVerifier v10
# ═════════════════════════════════════════════════════

class TestTaskVerifierV10:

    def _make_verifier(self):
        from task_verifier_server import TaskVerifier
        return TaskVerifier()

    def test_validate_state_method_exists(self):
        verifier = self._make_verifier()
        assert hasattr(verifier, "validate_state")

    def test_validate_state_domotique(self):
        verifier = self._make_verifier()
        result = verifier.validate_state("lamp_01", {
            "category": "domotique",
            "status": "on",
        })
        assert "valid" in result
        assert "device_id" in result
        assert result["device_id"] == "lamp_01"
        assert result["category"] == "domotique"
        assert isinstance(result["mismatches"], list)

    def test_validate_state_network(self):
        verifier = self._make_verifier()
        result = verifier.validate_state("router_01", {
            "category": "network",
            "status": "up",
        })
        assert result["valid"] is True

    def test_validate_state_logic(self):
        verifier = self._make_verifier()
        result = verifier.validate_state("check_01", {
            "category": "logic",
            "assertion": "x > 0",
        })
        assert "valid" in result

    def test_validate_state_mismatch(self):
        verifier = self._make_verifier()
        result = verifier.validate_state("lamp_01", {
            "category": "domotique",
            "status": "off",  # actual returns "on"
        })
        assert result["valid"] is False
        assert len(result["mismatches"]) > 0


# ═════════════════════════════════════════════════════
#  ContextEngine v3
# ═════════════════════════════════════════════════════

class TestContextEngineV3:

    def _make_engine(self):
        from context_engine import ContextEngine
        return ContextEngine()

    def test_build_agent_context(self):
        engine = self._make_engine()
        ctx = engine.build_agent_context("Quel temps fait-il ?")
        assert isinstance(ctx, dict)
        assert "temporal" in ctx
        assert "tasks" in ctx
        assert "agent_state" in ctx
        assert "intent" in ctx

    def test_build_agent_context_empty_intent(self):
        engine = self._make_engine()
        ctx = engine.build_agent_context()
        assert "intent" in ctx
        assert ctx["intent"] == {}

    def test_inject_context(self):
        engine = self._make_engine()
        enriched = engine.inject_context("Dis-moi la météo")
        assert isinstance(enriched, str)
        assert "[Contexte:" in enriched
        assert "Dis-moi la météo" in enriched

    def test_inject_context_includes_location(self):
        engine = self._make_engine()
        engine.set_location("Lyon", "FR")
        enriched = engine.inject_context("Test")
        assert "Lyon" in enriched

    def test_set_agent_state(self):
        engine = self._make_engine()
        engine.set_agent_state("planning")
        ctx = engine.build_agent_context()
        assert ctx["agent_state"] == "planning"

    def test_add_task_history(self):
        engine = self._make_engine()
        engine.add_task_history({"goal": "test", "status": "completed"})
        ctx = engine.build_agent_context()
        history = ctx["tasks"]["recent_history"]
        assert len(history) == 1
        assert history[0]["goal"] == "test"


# ═════════════════════════════════════════════════════
#  TaskRecovery
# ═════════════════════════════════════════════════════

class TestTaskRecovery:

    def _make_recovery(self):
        from task_recovery import TaskRecovery
        return TaskRecovery()

    def test_create_recovery(self):
        recovery = self._make_recovery()
        assert recovery is not None

    def test_recover_timeout(self):
        recovery = self._make_recovery()
        result = recovery.recover(
            {"description": "Search web", "tool": "search_web"},
            "Connection timed out"
        )
        assert result.error_category.value == "timeout"
        assert result.strategy.value == "retry"
        assert result.success is True

    def test_recover_service_down(self):
        recovery = self._make_recovery()
        result = recovery.recover(
            {"description": "Get news", "tool": "get_news"},
            "Connection refused — service not available"
        )
        assert result.error_category.value == "service_down"

    def test_recover_permission(self):
        recovery = self._make_recovery()
        result = recovery.recover(
            {"description": "Delete file", "tool": "delete"},
            "Permission denied — forbidden"
        )
        assert result.error_category.value == "permission"
        assert result.strategy.value == "escalate"

    def test_rollback(self):
        recovery = self._make_recovery()
        ok = recovery.rollback({"description": "Test", "tool": "remember_info"})
        assert ok is True

    def test_escalate(self):
        recovery = self._make_recovery()
        result = recovery.escalate("Service critical failure")
        assert result.level in ("user", "admin", "critical")
        assert result.reason != ""

    def test_recovery_result_to_dict(self):
        from task_recovery import RecoveryResult, RecoveryStrategy, ErrorCategory
        result = RecoveryResult(
            success=True,
            strategy=RecoveryStrategy.RETRY,
            error_category=ErrorCategory.TIMEOUT,
            message="Retrying",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["strategy"] == "retry"
        assert d["error_category"] == "timeout"

    def test_recovery_log(self):
        recovery = self._make_recovery()
        recovery.recover({"description": "t1", "tool": "x"}, "timeout error")
        recovery.recover({"description": "t2", "tool": "y"}, "not found — 404")
        log = recovery.get_recovery_log()
        assert len(log) == 2

    def test_recovery_stats(self):
        recovery = self._make_recovery()
        recovery.recover({"description": "t", "tool": "x"}, "timed out")
        stats = recovery.get_stats()
        assert stats["total_recoveries"] == 1
        assert "by_category" in stats

    def test_alternative_tool_recovery(self):
        recovery = self._make_recovery()
        result = recovery.recover(
            {"description": "Search", "tool": "search_web", "retries": 2},
            "Service 503 not available"
        )
        # After 1 retry, should try alternative
        assert result.strategy.value == "alternative"
        assert result.corrected_step is not None
        assert result.corrected_step["tool"] == "get_summary"


# ═════════════════════════════════════════════════════
#  TaskOptimizer
# ═════════════════════════════════════════════════════

class TestTaskOptimizer:

    def _make_optimizer(self):
        from task_optimizer import TaskOptimizer
        return TaskOptimizer()

    def test_create_optimizer(self):
        opt = self._make_optimizer()
        assert opt is not None

    def test_optimize_empty_plan(self):
        opt = self._make_optimizer()
        plan = {"goal": "test", "steps": []}
        result = opt.optimize(plan)
        assert result["steps"] == []

    def test_optimize_with_history(self):
        opt = self._make_optimizer()
        # Record some history
        opt.record_outcome(
            {"tool": "search_web"}, success=True, latency_s=0.5
        )
        opt.record_outcome(
            {"tool": "search_web"}, success=True, latency_s=0.8
        )
        opt.record_outcome(
            {"tool": "get_news"}, success=False, latency_s=2.0, error="slow"
        )

        plan = {
            "goal": "test",
            "steps": [
                {"tool": "search_web", "description": "search"},
                {"tool": "get_news", "description": "news"},
            ],
        }
        result = opt.optimize(plan)
        assert result.get("optimized") is True
        # search_web should have performance hints
        search_step = result["steps"][0]
        assert "performance" in search_step

    def test_record_outcome(self):
        opt = self._make_optimizer()
        opt.record_outcome({"tool": "search_web"}, success=True, latency_s=0.3)
        stats = opt.get_stats()
        assert stats["total_records"] == 1
        assert "search_web" in stats["tools"]

    def test_get_tool_recommendation(self):
        opt = self._make_optimizer()
        for _ in range(10):
            opt.record_outcome({"tool": "search_web"}, success=True, latency_s=0.5)
        rec = opt.get_tool_recommendation("search_web")
        assert rec["recommendation"] == "reliable"

    def test_get_tool_recommendation_no_data(self):
        opt = self._make_optimizer()
        rec = opt.get_tool_recommendation("unknown_tool")
        assert rec["recommendation"] == "no_data"

    def test_unreliable_tool_detection(self):
        opt = self._make_optimizer()
        for i in range(10):
            opt.record_outcome(
                {"tool": "bad_tool"},
                success=(i < 3),  # 30% success
                latency_s=1.0,
            )
        rec = opt.get_tool_recommendation("bad_tool")
        assert rec["recommendation"] in ("unreliable", "avoid")

    def test_optimization_reorder(self):
        opt = self._make_optimizer()
        # fast tool
        for _ in range(5):
            opt.record_outcome({"tool": "fast_tool"}, success=True, latency_s=0.1)
        # slow tool
        for _ in range(5):
            opt.record_outcome({"tool": "slow_tool"}, success=True, latency_s=5.0)

        plan = {
            "goal": "test",
            "steps": [
                {"tool": "slow_tool", "description": "slow"},
                {"tool": "fast_tool", "description": "fast"},
            ],
        }
        result = opt.optimize(plan)
        # Fast tool should come first (no dependencies)
        assert result["steps"][0]["tool"] == "fast_tool"


# ═════════════════════════════════════════════════════
#  TaskMemory
# ═════════════════════════════════════════════════════

class TestTaskMemory:

    def _make_memory(self):
        from task_memory import TaskMemory
        return TaskMemory(persist_path=":none:")  # no persistence

    def test_create_memory(self):
        mem = self._make_memory()
        assert mem is not None

    def test_add_task(self):
        mem = self._make_memory()
        task_id = mem.add_task({"goal": "Test task"})
        assert task_id.startswith("task_")

    def test_get_task(self):
        mem = self._make_memory()
        task_id = mem.add_task({"goal": "Test task"})
        task = mem.get_task(task_id)
        assert task is not None
        assert task["goal"] == "Test task"
        assert task["status"] == "pending"

    def test_update_task(self):
        mem = self._make_memory()
        task_id = mem.add_task({"goal": "Test"})
        ok = mem.update_task(task_id, {"status": "running"})
        assert ok is True
        task = mem.get_task(task_id)
        assert task["status"] == "running"

    def test_update_task_completed(self):
        mem = self._make_memory()
        task_id = mem.add_task({"goal": "Test"})
        ok = mem.update_task(task_id, {"status": "completed"})
        assert ok is True
        task = mem.get_task(task_id)
        assert task["completed_at"] is not None
        assert task["elapsed_s"] >= 0

    def test_update_nonexistent(self):
        mem = self._make_memory()
        ok = mem.update_task("nonexistent", {"status": "done"})
        assert ok is False

    def test_list_tasks(self):
        mem = self._make_memory()
        mem.add_task({"goal": "Task 1"})
        mem.add_task({"goal": "Task 2"})
        tasks = mem.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_with_filter(self):
        mem = self._make_memory()
        t1 = mem.add_task({"goal": "Task 1"})
        t2 = mem.add_task({"goal": "Task 2"})
        mem.update_task(t1, {"status": "completed"})
        completed = mem.list_tasks(status_filter="completed")
        assert len(completed) == 1
        pending = mem.list_tasks(status_filter="pending")
        assert len(pending) == 1

    def test_search_tasks(self):
        mem = self._make_memory()
        mem.add_task({"goal": "Chercher la météo"})
        mem.add_task({"goal": "Envoyer un email"})
        results = mem.search_tasks("météo")
        assert len(results) == 1
        assert results[0]["goal"] == "Chercher la météo"

    def test_get_stats(self):
        mem = self._make_memory()
        mem.add_task({"goal": "Task 1"})
        t2 = mem.add_task({"goal": "Task 2"})
        mem.update_task(t2, {"status": "completed"})
        stats = mem.get_stats()
        assert stats["total_tasks"] == 2
        assert "pending" in stats["by_status"]
        assert "completed" in stats["by_status"]

    def test_list_tasks_limit(self):
        mem = self._make_memory()
        for i in range(10):
            mem.add_task({"goal": f"Task {i}"})
        tasks = mem.list_tasks(limit=3)
        assert len(tasks) == 3

    def test_clear_old(self):
        mem = self._make_memory()
        task_id = mem.add_task({"goal": "Old task"})
        # Force an old completed_at timestamp
        mem._tasks[task_id]["completed_at"] = time.time() - 86400 * 30
        removed = mem.clear_old(max_age_s=86400)
        assert removed == 1
        assert mem.get_task(task_id) is None


# ═════════════════════════════════════════════════════
#  AgentStateMachine
# ═════════════════════════════════════════════════════

class TestAgentStateMachine:

    def _make_sm(self):
        from agent_state_machine import AgentStateMachine
        return AgentStateMachine()

    def test_initial_state_idle(self):
        sm = self._make_sm()
        assert sm.state.value == "idle"

    def test_valid_transition_idle_to_listening(self):
        sm = self._make_sm()
        from agent_state_machine import AgentState
        assert sm.can_transition(AgentState.LISTENING) is True
        assert sm.set_state(AgentState.LISTENING) is True
        assert sm.state == AgentState.LISTENING

    def test_invalid_transition_idle_to_executing(self):
        sm = self._make_sm()
        from agent_state_machine import AgentState
        assert sm.can_transition(AgentState.EXECUTING) is False
        assert sm.set_state(AgentState.EXECUTING) is False
        assert sm.state.value == "idle"

    def test_full_cognitive_cycle(self):
        from agent_state_machine import AgentState
        sm = self._make_sm()
        transitions = [
            AgentState.LISTENING,
            AgentState.THINKING,
            AgentState.PLANNING,
            AgentState.EXECUTING,
            AgentState.VERIFYING,
            AgentState.OPTIMIZING,
            AgentState.IDLE,
        ]
        for target in transitions:
            assert sm.set_state(target) is True, \
                f"Failed: {sm.state.value} → {target.value}"

    def test_recovery_cycle(self):
        from agent_state_machine import AgentState
        sm = self._make_sm()
        sm.set_state(AgentState.LISTENING)
        sm.set_state(AgentState.THINKING)
        sm.set_state(AgentState.PLANNING)
        sm.set_state(AgentState.EXECUTING)
        sm.set_state(AgentState.RECOVERING)
        # Can go back to executing or planning
        assert sm.can_transition(AgentState.EXECUTING) is True
        assert sm.can_transition(AgentState.PLANNING) is True
        assert sm.can_transition(AgentState.IDLE) is True

    def test_force_state(self):
        from agent_state_machine import AgentState
        sm = self._make_sm()
        sm.force_state(AgentState.RECOVERING)
        assert sm.state == AgentState.RECOVERING

    def test_get_state_dict(self):
        sm = self._make_sm()
        d = sm.get_state()
        assert "state" in d
        assert "since" in d
        assert "duration_s" in d

    def test_history_tracking(self):
        from agent_state_machine import AgentState
        sm = self._make_sm()
        sm.set_state(AgentState.LISTENING)
        sm.set_state(AgentState.THINKING)
        history = sm.get_history()
        assert len(history) == 2
        assert history[0]["from"] == "idle"
        assert history[0]["to"] == "listening"

    def test_no_op_same_state(self):
        from agent_state_machine import AgentState
        sm = self._make_sm()
        assert sm.set_state(AgentState.IDLE) is True  # same state, no-op

    def test_string_state_transition(self):
        sm = self._make_sm()
        assert sm.set_state("listening") is True
        assert sm.state.value == "listening"

    def test_invalid_string_state(self):
        sm = self._make_sm()
        assert sm.set_state("nonexistent") is False

    def test_stats(self):
        from agent_state_machine import AgentState
        sm = self._make_sm()
        sm.set_state(AgentState.LISTENING)
        sm.set_state(AgentState.THINKING)
        sm.set_state(AgentState.IDLE)
        stats = sm.get_stats()
        assert stats["total_transitions"] == 3
        assert stats["current_state"] == "idle"
        assert "idle" in stats["state_counts"]


# ═════════════════════════════════════════════════════
#  AgentState Enum
# ═════════════════════════════════════════════════════

class TestAgentState:

    def test_all_states_exist(self):
        from agent_state_machine import AgentState
        expected = {"idle", "listening", "thinking", "planning",
                    "executing", "verifying", "recovering", "optimizing"}
        actual = {s.value for s in AgentState}
        assert expected == actual


# ═════════════════════════════════════════════════════
#  AgentManager
# ═════════════════════════════════════════════════════

class TestAgentManager:

    def _make_manager(self):
        from agent_manager import AgentManager
        return AgentManager()

    def test_create_manager(self):
        mgr = self._make_manager()
        assert mgr is not None
        assert mgr.state_machine is not None
        assert mgr.recovery is not None
        assert mgr.optimizer is not None
        assert mgr.memory is not None

    def test_get_state(self):
        mgr = self._make_manager()
        state = mgr.get_state()
        assert "state_machine" in state
        assert "memory_stats" in state
        assert "optimizer_stats" in state
        assert "recovery_stats" in state

    def test_get_metrics(self):
        mgr = self._make_manager()
        metrics = mgr.get_metrics()
        assert "agent" in metrics
        assert "memory" in metrics
        assert "optimizer" in metrics
        assert "recovery" in metrics

    def test_process_intent_returns_dict(self):
        mgr = self._make_manager()
        result = asyncio.get_event_loop().run_until_complete(
            mgr.process_intent("Bonjour")
        )
        assert isinstance(result, dict)
        assert "input" in result
        assert result["input"] == "Bonjour"

    def test_health_check_returns_dict(self):
        mgr = self._make_manager()
        result = asyncio.get_event_loop().run_until_complete(
            mgr.health_check()
        )
        assert isinstance(result, dict)
        assert "services" in result
        assert "uptime_s" in result
        # Local modules should be up
        assert result["services"]["recovery"]["status"] == "up"
        assert result["services"]["optimizer"]["status"] == "up"
        assert result["services"]["memory"]["status"] == "up"
        assert result["services"]["state_machine"]["status"] == "up"


# ═════════════════════════════════════════════════════
#  RecoveryStrategy & ErrorCategory Enums
# ═════════════════════════════════════════════════════

class TestRecoveryEnums:

    def test_recovery_strategies(self):
        from task_recovery import RecoveryStrategy
        expected = {"retry", "alternative", "skip", "rollback", "escalate"}
        actual = {s.value for s in RecoveryStrategy}
        assert expected == actual

    def test_error_categories(self):
        from task_recovery import ErrorCategory
        expected = {"timeout", "service_down", "invalid_result",
                    "permission", "resource", "logic", "unknown"}
        actual = {c.value for c in ErrorCategory}
        assert expected == actual


# ═════════════════════════════════════════════════════
#  EscalationResult
# ═════════════════════════════════════════════════════

class TestEscalationResult:

    def test_to_dict(self):
        from task_recovery import EscalationResult
        result = EscalationResult(
            level="user",
            reason="Test",
            suggested_action="Do something",
        )
        d = result.to_dict()
        assert d["level"] == "user"
        assert d["reason"] == "Test"
        assert d["suggested_action"] == "Do something"


# ═════════════════════════════════════════════════════
#  VALID_TRANSITIONS coverage
# ═════════════════════════════════════════════════════

class TestValidTransitions:

    def test_all_states_have_transitions(self):
        from agent_state_machine import VALID_TRANSITIONS, AgentState
        for state in AgentState:
            assert state in VALID_TRANSITIONS, \
                f"State {state.value} has no defined transitions"

    def test_every_state_can_reach_idle(self):
        from agent_state_machine import VALID_TRANSITIONS, AgentState
        for state in AgentState:
            if state == AgentState.IDLE:
                continue
            targets = VALID_TRANSITIONS[state]
            assert AgentState.IDLE in targets, \
                f"State {state.value} cannot transition to idle"
