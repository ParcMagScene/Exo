"""
Tests unitaires — Task Planner v8 (HTN decomposition, strategies, replan)
"""

import sys
from pathlib import Path

import pytest


class TestExecutionStrategy:
    """Tests de l'enum ExecutionStrategy v8."""

    def test_strategies_exist(self):
        from task_planner_server import ExecutionStrategy
        assert ExecutionStrategy.SEQUENTIAL is not None
        assert ExecutionStrategy.PARALLEL is not None
        assert ExecutionStrategy.ADAPTIVE is not None


class TestPlanStepHTN:
    """Tests des champs HTN ajoutés à PlanStep."""

    def test_step_has_htn_fields(self):
        from task_planner_server import PlanStep
        step = PlanStep(index=0, description="Test", tool="t")
        assert hasattr(step, "priority")
        assert hasattr(step, "retries")
        assert hasattr(step, "max_retries")
        assert hasattr(step, "sub_steps")
        assert hasattr(step, "parent_step")
        assert hasattr(step, "is_composite")

    def test_step_defaults(self):
        from task_planner_server import PlanStep
        step = PlanStep(index=0, description="Test", tool="t")
        assert step.priority == 0
        assert step.retries == 0
        assert step.max_retries == 3
        assert step.sub_steps == []
        assert step.parent_step is None
        assert step.is_composite is False

    def test_composite_step(self):
        from task_planner_server import PlanStep
        parent = PlanStep(index=0, description="Parent", tool="composite")
        parent.is_composite = True
        child1 = PlanStep(index=1, description="Child 1", tool="t1")
        child1.parent_step = 0
        child2 = PlanStep(index=2, description="Child 2", tool="t2")
        child2.parent_step = 0
        parent.sub_steps = [1, 2]
        assert parent.is_composite
        assert len(parent.sub_steps) == 2

    def test_step_to_dict_htn_fields(self):
        from task_planner_server import PlanStep
        step = PlanStep(index=0, description="Test", tool="t")
        step.priority = 5
        step.is_composite = True
        step.sub_steps = [1, 2]
        d = step.to_dict()
        assert d["priority"] == 5
        assert d["is_composite"] is True
        assert d["sub_steps"] == [1, 2]


class TestTaskPlanV8:
    """Tests des champs v8 TaskPlan."""

    def test_plan_has_strategy(self):
        from task_planner_server import TaskPlan, ExecutionStrategy
        plan = TaskPlan(plan_id="x", goal="test")
        assert hasattr(plan, "strategy")
        assert plan.strategy == ExecutionStrategy.SEQUENTIAL

    def test_plan_has_replanned(self):
        from task_planner_server import TaskPlan
        plan = TaskPlan(plan_id="x", goal="test")
        assert hasattr(plan, "replanned")
        assert plan.replanned is False

    def test_plan_to_dict_has_dag(self):
        from task_planner_server import TaskPlan, PlanStep
        plan = TaskPlan(plan_id="x", goal="test", steps=[
            PlanStep(0, "A", "t", depends_on=[]),
            PlanStep(1, "B", "t", depends_on=[0]),
            PlanStep(2, "C", "t", depends_on=[0]),
        ])
        d = plan.to_dict()
        assert isinstance(d, dict)
        assert "steps" in d

    def test_progress_counts_all(self):
        from task_planner_server import TaskPlan, PlanStep, StepStatus
        plan = TaskPlan(plan_id="x", goal="test", steps=[
            PlanStep(0, "Parent", "composite"),
            PlanStep(1, "Child 1", "t"),
            PlanStep(2, "Child 2", "t"),
        ])
        plan.steps[0].is_composite = True
        plan.steps[1].status = StepStatus.COMPLETED
        p = plan._progress()
        # Progress counts all steps including composites
        assert p["total"] == 3
        assert p["completed"] == 1


class TestTaskPlannerV8:
    """Tests des nouvelles méthodes v8 du TaskPlanner."""

    def _make_planner(self):
        from task_planner_server import TaskPlanner
        return TaskPlanner()

    def test_create_plan_with_strategy(self):
        from task_planner_server import ExecutionStrategy
        planner = self._make_planner()
        plan = planner.create_plan(
            "test",
            [{"description": "a", "tool": "t"}],
            strategy="parallel",
        )
        assert plan.strategy == ExecutionStrategy.PARALLEL

    def test_create_plan_adaptive_strategy(self):
        from task_planner_server import ExecutionStrategy
        planner = self._make_planner()
        plan = planner.create_plan(
            "test",
            [{"description": "a", "tool": "t"}],
            strategy="adaptive",
        )
        # Adaptive gets resolved to a concrete strategy
        assert plan.strategy in (
            ExecutionStrategy.SEQUENTIAL,
            ExecutionStrategy.PARALLEL,
        )

    def test_decompose_step(self):
        planner = self._make_planner()
        plan = planner.create_plan("test", [
            {"description": "Rechercher et résumer", "tool": "search_and_summarize"},
        ])
        result = planner.decompose(plan.plan_id, 0, [
            {"description": "Rechercher", "tool": "search_web", "params": {"query": "IA"}},
            {"description": "Résumer", "tool": "get_summary", "params": {}},
        ])
        assert result is True
        # Original step should now be composite
        assert plan.steps[0].is_composite is True
        assert len(plan.steps[0].sub_steps) >= 2

    def test_decompose_nonexistent_plan(self):
        planner = self._make_planner()
        result = planner.decompose("nope", 0, [
            {"description": "a", "tool": "t"},
        ])
        assert result is False

    def test_get_next_executable_sequential(self):
        from task_planner_server import StepStatus, ExecutionStrategy
        planner = self._make_planner()
        plan = planner.create_plan("test", [
            {"description": "a", "tool": "t1"},
            {"description": "b", "tool": "t2"},
        ], strategy="sequential")
        batch = planner.get_next_executable(plan.plan_id)
        assert len(batch) >= 1
        assert batch[0].index == 0

    def test_get_next_executable_parallel(self):
        planner = self._make_planner()
        plan = planner.create_plan("test", [
            {"description": "a", "tool": "t1"},
            {"description": "b", "tool": "t2"},
        ], strategy="parallel")
        batch = planner.get_next_executable(plan.plan_id)
        # Both steps should be executable in parallel (no deps)
        assert len(batch) == 2

    def test_get_next_executable_respects_deps(self):
        planner = self._make_planner()
        plan = planner.create_plan("test", [
            {"description": "a", "tool": "t1"},
            {"description": "b", "tool": "t2", "depends_on": [0]},
        ], strategy="parallel")
        batch = planner.get_next_executable(plan.plan_id)
        # Only step 0 is executable (step 1 depends on 0)
        assert len(batch) == 1
        assert batch[0].index == 0

    def test_replan_skip(self):
        from task_planner_server import StepStatus
        planner = self._make_planner()
        plan = planner.create_plan("test", [
            {"description": "a", "tool": "t1"},
            {"description": "b", "tool": "t2"},
        ])
        planner.mark_step_running(plan.plan_id, 0)
        planner.complete_step(plan.plan_id, 0, error="failed")
        result = planner.replan(plan.plan_id, 0, strategy="skip")
        assert result is True
        assert plan.steps[0].status == StepStatus.SKIPPED

    def test_replan_retry(self):
        from task_planner_server import StepStatus
        planner = self._make_planner()
        plan = planner.create_plan("test", [
            {"description": "a", "tool": "t1"},
        ])
        planner.mark_step_running(plan.plan_id, 0)
        planner.complete_step(plan.plan_id, 0, error="timeout")
        result = planner.replan(plan.plan_id, 0, strategy="retry")
        assert result is True
        assert plan.steps[0].status == StepStatus.PENDING
        assert plan.steps[0].retries == 1

    def test_replan_nonexistent(self):
        planner = self._make_planner()
        result = planner.replan("nope", 0, strategy="skip")
        assert result is False

    def test_detect_strategy(self):
        planner = self._make_planner()
        from task_planner_server import PlanStep, ExecutionStrategy
        # Steps with deps → sequential
        steps = [
            PlanStep(0, "a", "t1"),
            PlanStep(1, "b", "t2", depends_on=[0]),
        ]
        s = planner._detect_strategy(steps)
        assert s == ExecutionStrategy.SEQUENTIAL

    def test_detect_strategy_parallel(self):
        planner = self._make_planner()
        from task_planner_server import PlanStep, ExecutionStrategy
        steps = [
            PlanStep(0, "a", "t1"),
            PlanStep(1, "b", "t2"),
            PlanStep(2, "c", "t3"),
        ]
        s = planner._detect_strategy(steps)
        assert s == ExecutionStrategy.PARALLEL
