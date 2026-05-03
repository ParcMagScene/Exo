"""
Tests unitaires — Task Planner Server (EXO v7)
Testable sans WebSocket ni dépendances lourdes.
"""

import sys
from pathlib import Path

import pytest


class TestPlanStep:
    """Tests de la structure PlanStep."""

    def test_create_step(self):
        from task_planner_server import PlanStep, StepStatus
        step = PlanStep(
            index=0,
            description="Chercher la météo",
            tool="get_weather",
            params={"city": "Paris"},
        )
        assert step.index == 0
        assert step.tool == "get_weather"
        assert step.status == StepStatus.PENDING
        assert step.result is None

    def test_step_to_dict(self):
        from task_planner_server import PlanStep
        step = PlanStep(index=1, description="Test", tool="search_web")
        d = step.to_dict()
        assert d["index"] == 1
        assert d["tool"] == "search_web"
        assert d["status"] == "pending"
        assert d["duration_s"] is None


class TestTaskPlan:
    """Tests de la structure TaskPlan."""

    def test_create_plan(self):
        from task_planner_server import TaskPlan, PlanStep, PlanStatus
        plan = TaskPlan(plan_id="abc", goal="Test goal")
        assert plan.plan_id == "abc"
        assert plan.status == PlanStatus.PENDING

    def test_plan_progress_empty(self):
        from task_planner_server import TaskPlan
        plan = TaskPlan(plan_id="x", goal="empty")
        p = plan._progress()
        assert p["total"] == 0
        assert p["pct"] == 0

    def test_plan_progress_partial(self):
        from task_planner_server import TaskPlan, PlanStep, StepStatus
        plan = TaskPlan(plan_id="x", goal="test", steps=[
            PlanStep(0, "step 0", "t0"),
            PlanStep(1, "step 1", "t1"),
        ])
        plan.steps[0].status = StepStatus.COMPLETED
        p = plan._progress()
        assert p["total"] == 2
        assert p["completed"] == 1
        assert p["pct"] == 50

    def test_update_status_all_completed(self):
        from task_planner_server import TaskPlan, PlanStep, StepStatus, PlanStatus
        plan = TaskPlan(plan_id="x", goal="test", steps=[
            PlanStep(0, "a", "t"),
            PlanStep(1, "b", "t"),
        ])
        plan.steps[0].status = StepStatus.COMPLETED
        plan.steps[1].status = StepStatus.COMPLETED
        plan.update_status()
        assert plan.status == PlanStatus.COMPLETED

    def test_update_status_partial(self):
        from task_planner_server import TaskPlan, PlanStep, StepStatus, PlanStatus
        plan = TaskPlan(plan_id="x", goal="test", steps=[
            PlanStep(0, "a", "t"),
            PlanStep(1, "b", "t"),
        ])
        plan.steps[0].status = StepStatus.COMPLETED
        plan.steps[1].status = StepStatus.FAILED
        plan.update_status()
        assert plan.status == PlanStatus.PARTIAL


class TestTaskPlanner:
    """Tests du TaskPlanner."""

    def _make_planner(self):
        from task_planner_server import TaskPlanner
        return TaskPlanner()

    def test_create_plan(self):
        planner = self._make_planner()
        plan = planner.create_plan(
            "Rechercher et résumer un sujet",
            [
                {"description": "Rechercher sur le web", "tool": "search_web", "params": {"query": "IA"}},
                {"description": "Résumer les résultats", "tool": "get_summary", "params": {"topic": "IA"}},
            ],
        )
        assert plan.goal == "Rechercher et résumer un sujet"
        assert len(plan.steps) == 2
        assert plan.steps[0].tool == "search_web"

    def test_get_plan(self):
        planner = self._make_planner()
        plan = planner.create_plan("test", [{"description": "a", "tool": "t"}])
        retrieved = planner.get_plan(plan.plan_id)
        assert retrieved is not None
        assert retrieved.plan_id == plan.plan_id

    def test_get_plan_not_found(self):
        planner = self._make_planner()
        assert planner.get_plan("nonexistent") is None

    def test_list_plans(self):
        planner = self._make_planner()
        planner.create_plan("plan 1", [{"description": "a", "tool": "t"}])
        planner.create_plan("plan 2", [{"description": "b", "tool": "t"}])
        plans = planner.list_plans()
        assert len(plans) == 2

    def test_mark_step_running(self):
        from task_planner_server import StepStatus
        planner = self._make_planner()
        plan = planner.create_plan("test", [{"description": "a", "tool": "t"}])
        step = planner.mark_step_running(plan.plan_id, 0)
        assert step is not None
        assert step.status == StepStatus.RUNNING
        assert step.started_at is not None

    def test_mark_step_running_deps_not_met(self):
        planner = self._make_planner()
        plan = planner.create_plan("test", [
            {"description": "a", "tool": "t"},
            {"description": "b", "tool": "t", "depends_on": [0]},
        ])
        # Can't run step 1 because step 0 is still pending
        step = planner.mark_step_running(plan.plan_id, 1)
        assert step is None

    def test_complete_step_success(self):
        from task_planner_server import StepStatus
        planner = self._make_planner()
        plan = planner.create_plan("test", [{"description": "a", "tool": "t"}])
        planner.mark_step_running(plan.plan_id, 0)
        planner.complete_step(plan.plan_id, 0, result={"data": "ok"})
        assert plan.steps[0].status == StepStatus.COMPLETED
        assert plan.steps[0].result == {"data": "ok"}

    def test_complete_step_failure(self):
        from task_planner_server import StepStatus
        planner = self._make_planner()
        plan = planner.create_plan("test", [{"description": "a", "tool": "t"}])
        planner.mark_step_running(plan.plan_id, 0)
        planner.complete_step(plan.plan_id, 0, error="timeout")
        assert plan.steps[0].status == StepStatus.FAILED
        assert plan.steps[0].error == "timeout"

    def test_cancel_plan(self):
        from task_planner_server import PlanStatus, StepStatus
        planner = self._make_planner()
        plan = planner.create_plan("test", [
            {"description": "a", "tool": "t"},
            {"description": "b", "tool": "t"},
        ])
        assert planner.cancel_plan(plan.plan_id) is True
        assert plan.status == PlanStatus.CANCELLED
        assert plan.steps[0].status == StepStatus.SKIPPED

    def test_cancel_plan_not_found(self):
        planner = self._make_planner()
        assert planner.cancel_plan("nope") is False

    def test_get_next_step(self):
        planner = self._make_planner()
        plan = planner.create_plan("test", [
            {"description": "a", "tool": "t"},
            {"description": "b", "tool": "t", "depends_on": [0]},
        ])
        next_step = planner.get_next_step(plan.plan_id)
        assert next_step is not None
        assert next_step.index == 0

    def test_get_next_step_after_completion(self):
        from task_planner_server import StepStatus
        planner = self._make_planner()
        plan = planner.create_plan("test", [
            {"description": "a", "tool": "t"},
            {"description": "b", "tool": "t", "depends_on": [0]},
        ])
        planner.mark_step_running(plan.plan_id, 0)
        planner.complete_step(plan.plan_id, 0, result={})
        next_step = planner.get_next_step(plan.plan_id)
        assert next_step is not None
        assert next_step.index == 1

    def test_get_next_step_none_left(self):
        from task_planner_server import StepStatus
        planner = self._make_planner()
        plan = planner.create_plan("test", [{"description": "a", "tool": "t"}])
        planner.mark_step_running(plan.plan_id, 0)
        planner.complete_step(plan.plan_id, 0, result={})
        assert planner.get_next_step(plan.plan_id) is None

    def test_eviction(self):
        from task_planner_server import PlanStatus
        planner = self._make_planner()
        # Create more than MAX_PLANS
        for i in range(55):
            p = planner.create_plan(f"plan {i}", [{"description": "a", "tool": "t"}])
            p.status = PlanStatus.COMPLETED
        # Should evict old completed plans
        assert len(planner._plans) <= 50

    def test_max_steps_capped(self):
        planner = self._make_planner()
        steps = [{"description": f"s{i}", "tool": "t"} for i in range(30)]
        plan = planner.create_plan("big plan", steps)
        assert len(plan.steps) == 20  # MAX_STEPS = 20


class TestPlannerProtocol:
    """Tests du protocole WebSocket planner."""

    def test_create_plan_message(self):
        msg = {
            "action": "create_plan",
            "params": {
                "goal": "Rechercher et résumer",
                "steps": [
                    {"description": "Rechercher", "tool": "search_web", "params": {"query": "test"}},
                ],
            },
        }
        assert msg["action"] == "create_plan"
        assert len(msg["params"]["steps"]) == 1

    def test_execute_step_message(self):
        msg = {
            "action": "execute_step",
            "params": {"plan_id": "abc123", "step_index": 0},
        }
        assert msg["params"]["step_index"] == 0

    def test_cancel_plan_message(self):
        msg = {
            "action": "cancel_plan",
            "params": {"plan_id": "abc123"},
        }
        assert msg["action"] == "cancel_plan"
