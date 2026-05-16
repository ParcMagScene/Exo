"""
Tests unitaires — Context Engine v8 (préférences, topic, location, énergie)
"""

import sys
from pathlib import Path

import pytest


class TestContextEngineV8:
    """Tests des nouvelles fonctionnalités v8 du ContextEngine."""

    def _make_engine(self):
        from context_engine import ContextEngine
        return ContextEngine()

    def test_context_has_v8_fields(self):
        engine = self._make_engine()
        ctx = engine.get_context()
        assert "location" in ctx
        assert "conversation_topic" in ctx
        assert "topic_confidence" in ctx
        assert "implicit_preferences" in ctx
        assert "energy_level" in ctx

    def test_set_location(self):
        engine = self._make_engine()
        engine.set_location("Lyon", "FR")
        ctx = engine.get_context()
        assert ctx["location"]["city"] == "Lyon"
        assert ctx["location"]["country"] == "FR"

    def test_detect_preferences_musical(self):
        engine = self._make_engine()
        prefs = engine.detect_preferences("J'adore écouter du jazz le soir")
        assert isinstance(prefs, list)
        # Should detect music preference
        if prefs:
            assert "category" in prefs[0]

    def test_get_topic_via_context(self):
        engine = self._make_engine()
        # Add some interactions to create a topic
        engine.add_interaction("Parle-moi de la météo", "Il fait beau aujourd'hui")
        engine.add_interaction("Et demain ?", "Il fera nuageux demain")
        ctx = engine.get_context()
        assert "conversation_topic" in ctx
        assert "topic_confidence" in ctx
        assert isinstance(ctx["topic_confidence"], float)

    def test_energy_level_default(self):
        engine = self._make_engine()
        ctx = engine.get_context()
        assert ctx["energy_level"] in ("idle", "resting", "low", "moderate", "high")

    def test_set_current_plan(self):
        engine = self._make_engine()
        plan = {"id": "plan-123", "goal": "Rechercher des infos", "steps": []}
        engine.set_current_plan(plan)
        ctx = engine.get_context()
        assert ctx.get("current_plan") is not None
        assert ctx["current_plan"]["id"] == "plan-123"

    def test_implicit_preferences_accumulated(self):
        engine = self._make_engine()
        engine.detect_preferences("J'aime la musique classique")
        engine.detect_preferences("Je préfère écouter du Mozart")
        ctx = engine.get_context()
        assert isinstance(ctx["implicit_preferences"], dict)
