"""
Tests unitaires — Task Verifier Server (EXO v8)
"""

import sys
from pathlib import Path

import pytest


class TestTaskVerifier:
    """Tests du TaskVerifier."""

    def _make_verifier(self):
        from task_verifier_server import TaskVerifier
        return TaskVerifier()

    def test_create_verifier(self):
        verifier = self._make_verifier()
        assert verifier is not None

    def test_verify_result_success(self):
        verifier = self._make_verifier()
        step = {"tool": "search_web", "description": "Chercher IA"}
        result = {"data": "L'IA est un domaine...", "status": "ok"}
        v = verifier.verify_result(step, result)
        assert "valid" in v
        assert "confidence" in v
        assert isinstance(v["confidence"], float)
        assert 0.0 <= v["confidence"] <= 1.0

    def test_verify_result_empty(self):
        verifier = self._make_verifier()
        step = {"tool": "search_web", "description": "Test"}
        result = {}
        v = verifier.verify_result(step, result)
        assert v["valid"] is False or v["confidence"] < 0.5

    def test_verify_result_none(self):
        verifier = self._make_verifier()
        step = {"tool": "search_web", "description": "Test"}
        v = verifier.verify_result(step, None)
        assert v["valid"] is False or v.get("confidence", 0) < 0.3

    def test_verify_plan_all_valid(self):
        verifier = self._make_verifier()
        plan = {
            "goal": "Test plan",
            "steps": [
                {"tool": "search_web", "description": "Search"},
                {"tool": "get_news", "description": "News"},
            ],
        }
        results = {
            0: {"data": "some results", "status": "ok"},
            1: {"articles": [{"title": "Headline"}], "status": "ok"},
        }
        v = verifier.verify_plan(plan, results)
        assert "overall_valid" in v or "valid" in v

    def test_verify_plan_empty(self):
        verifier = self._make_verifier()
        plan = {"goal": "Empty", "steps": []}
        v = verifier.verify_plan(plan, {})
        assert isinstance(v, dict)

    def test_check_consistency_no_conflicts(self):
        verifier = self._make_verifier()
        results = [
            {"data": "Paris est la capitale", "status": "ok"},
            {"data": "La France est en Europe", "status": "ok"},
        ]
        c = verifier.check_consistency(results)
        assert "consistent" in c
        assert isinstance(c["conflicts"], list)

    def test_verify_tool_specific_search_web(self):
        verifier = self._make_verifier()
        step = {"tool": "search_web"}
        result = {"results": [{"title": "Test", "url": "https://example.com"}]}
        v = verifier.verify_result(step, result)
        assert v["valid"] is True

    def test_verify_tool_specific_calculate(self):
        verifier = self._make_verifier()
        step = {"tool": "calculate"}
        result = {"result": 42.0}
        v = verifier.verify_result(step, result)
        assert v["valid"] is True
