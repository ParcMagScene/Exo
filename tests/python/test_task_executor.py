"""
Tests unitaires — Task Executor Server (EXO v8)
Testable sans WebSocket ni services actifs.
"""

import sys
from pathlib import Path

import pytest


class TestExecutionState:
    """Tests de la classe ExecutionState."""

    def test_create_state(self):
        from task_executor_server import ExecutionState
        state = ExecutionState(plan_id="test-123", plan={"goal": "test"})
        assert state.plan_id == "test-123"
        assert state.status == "running"
        assert state.aborted is False

    def test_state_to_dict(self):
        from task_executor_server import ExecutionState
        state = ExecutionState(plan_id="test", plan={"goal": "test", "steps": [1, 2, 3]})
        d = state.to_dict()
        assert d["plan_id"] == "test"
        assert "status" in d


class TestToolServiceMap:
    """Tests du mapping outil → service."""

    def test_tool_map_exists(self):
        from task_executor_server import TOOL_SERVICE_MAP
        assert isinstance(TOOL_SERVICE_MAP, dict)
        assert len(TOOL_SERVICE_MAP) > 0

    def test_known_tools_mapped(self):
        from task_executor_server import TOOL_SERVICE_MAP
        expected_tools = ["search_web", "get_news", "recall_info"]
        for tool in expected_tools:
            assert tool in TOOL_SERVICE_MAP, f"{tool} not in TOOL_SERVICE_MAP"

    def test_tool_map_entries_format(self):
        from task_executor_server import TOOL_SERVICE_MAP
        for tool, (service, port) in TOOL_SERVICE_MAP.items():
            assert isinstance(service, str), f"{tool}: service should be str"
            assert isinstance(port, int), f"{tool}: port should be int"
            assert 1024 <= port <= 65535, f"{tool}: port {port} out of range"


class TestTaskExecutor:
    """Tests du TaskExecutor."""

    def test_create_executor(self):
        from task_executor_server import TaskExecutor
        executor = TaskExecutor()
        assert executor is not None
        assert hasattr(executor, "_executions")

    def test_no_active_executions_initially(self):
        from task_executor_server import TaskExecutor
        executor = TaskExecutor()
        assert len(executor._executions) == 0
