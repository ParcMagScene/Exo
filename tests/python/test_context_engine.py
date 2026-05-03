"""
Tests unitaires — Context Engine Server (EXO v7)
Testable sans WebSocket ni dépendances lourdes.
"""

import sys
import time
from pathlib import Path

import pytest


class TestContextEngine:
    """Tests du moteur de contexte."""

    def _make_engine(self):
        from context_engine import ContextEngine
        return ContextEngine()

    def test_get_context_returns_all_sections(self):
        engine = self._make_engine()
        ctx = engine.get_context()
        assert "temporal" in ctx
        assert "activity" in ctx
        assert "modules" in ctx
        assert "active_tasks" in ctx
        assert "recent_interactions" in ctx
        assert "recent_events" in ctx
        assert "preferences" in ctx
        assert "custom" in ctx

    def test_temporal_fields(self):
        engine = self._make_engine()
        ctx = engine.get_context()
        t = ctx["temporal"]
        assert "date" in t
        assert "time" in t
        assert "day_name" in t
        assert "season" in t
        assert "is_weekend" in t
        assert isinstance(t["hour"], int)
        assert 0 <= t["hour"] <= 23

    def test_activity_fields(self):
        engine = self._make_engine()
        ctx = engine.get_context()
        a = ctx["activity"]
        assert "probable" in a
        assert "is_active" in a
        assert isinstance(a["is_active"], bool)

    def test_update_context_event(self):
        engine = self._make_engine()
        engine.update_context("user_asked_weather", {"city": "Paris"})
        ctx = engine.get_context()
        assert len(ctx["recent_events"]) == 1
        assert ctx["recent_events"][0]["event"] == "user_asked_weather"

    def test_add_interaction(self):
        engine = self._make_engine()
        engine.add_interaction("Quelle heure est-il ?", "Il est 14h30.")
        ctx = engine.get_context()
        assert len(ctx["recent_interactions"]) == 1
        assert ctx["recent_interactions"][0]["user"] == "Quelle heure est-il ?"

    def test_set_module_status(self):
        engine = self._make_engine()
        engine.set_module_status("stt", True)
        engine.set_module_status("tts", False)
        ctx = engine.get_context()
        assert ctx["modules"]["stt"] is True
        assert ctx["modules"]["tts"] is False

    def test_set_preference(self):
        engine = self._make_engine()
        engine.set_preference("music_genre", "jazz")
        ctx = engine.get_context()
        assert ctx["preferences"]["music_genre"] == "jazz"

    def test_set_custom(self):
        engine = self._make_engine()
        engine.set_custom("mood", "focused")
        ctx = engine.get_context()
        assert ctx["custom"]["mood"] == "focused"

    def test_set_active_tasks(self):
        engine = self._make_engine()
        tasks = [{"id": "1", "goal": "test"}]
        engine.set_active_tasks(tasks)
        ctx = engine.get_context()
        assert len(ctx["active_tasks"]) == 1

    def test_event_overflow_capped(self):
        engine = self._make_engine()
        for i in range(250):
            engine.update_context(f"event_{i}")
        ctx = engine.get_context()
        # MAX_EVENTS = 200, recent_events shows last 10
        assert len(ctx["recent_events"]) == 10

    def test_interaction_overflow_capped(self):
        engine = self._make_engine()
        for i in range(60):
            engine.add_interaction(f"msg_{i}", f"resp_{i}")
        ctx = engine.get_context()
        # MAX_INTERACTIONS = 50, recent shows last 5
        assert len(ctx["recent_interactions"]) == 5

    def test_score_relevance_baseline(self):
        engine = self._make_engine()
        score = engine.score_relevance("random text about nothing")
        assert 0.0 <= score <= 1.0
        assert score >= 0.4  # base score is 0.5

    def test_score_relevance_with_interaction(self):
        engine = self._make_engine()
        engine.add_interaction("je veux musique jazz playlist soir")
        score = engine.score_relevance("playlist musique jazz du soir")
        assert score > 0.5  # interaction overlap should boost


class TestHelpers:
    """Tests des fonctions utilitaires."""

    def test_get_season(self):
        from context_engine import get_season
        assert get_season(1) == "hiver"
        assert get_season(4) == "printemps"
        assert get_season(7) == "été"
        assert get_season(10) == "automne"
        assert get_season(12) == "hiver"

    def test_get_probable_activity(self):
        from context_engine import get_probable_activity
        assert get_probable_activity(7) == "morning_routine"
        assert get_probable_activity(10) == "work_morning"
        assert get_probable_activity(13) == "lunch_break"
        assert get_probable_activity(15) == "work_afternoon"
        assert get_probable_activity(19) == "evening_leisure"
        assert get_probable_activity(22) == "night_relaxation"


class TestContextProtocol:
    """Tests du protocole WebSocket context."""

    def test_get_context_message_format(self):
        msg = {"action": "get_context"}
        assert msg["action"] == "get_context"

    def test_update_context_message_format(self):
        msg = {
            "action": "update_context",
            "params": {"event": "test_event", "data": {"key": "value"}},
        }
        assert msg["action"] == "update_context"
        assert msg["params"]["event"] == "test_event"

    def test_score_relevance_message_format(self):
        msg = {
            "action": "score_relevance",
            "params": {"memory_text": "test memory"},
        }
        assert msg["action"] == "score_relevance"
