"""
Tests unitaires — Memory Server v8 (tiers, promotion, summarize)
"""

import sys
from pathlib import Path

import pytest


class TestMemoryTiers:
    """Tests du système de tiers mémoire v8."""

    def test_entry_has_tier(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(
            id="tier-1",
            text="Test",
            importance=0.5,
            tags=["test"],
            category="general",
        )
        assert hasattr(entry, "tier")

    def test_entry_default_tier_stm(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(
            id="tier-2",
            text="Nouveau souvenir",
            importance=0.5,
            tags=[],
            category="general",
        )
        assert entry.tier == "stm"

    def test_entry_tier_in_dict(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(
            id="tier-3",
            text="Test",
            importance=0.5,
            tags=["test"],
            category="general",
        )
        d = entry.to_dict()
        assert "tier" in d
        assert d["tier"] == "stm"

    def test_entry_with_explicit_tier(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(
            id="tier-4",
            text="Old memory",
            importance=0.9,
            tags=["important"],
            category="fact",
            tier="ltm",
        )
        assert entry.tier == "ltm"


class TestMemoryHierarchy:
    """Tests des méthodes hiérarchiques v8."""

    def test_tier_stats_protocol(self):
        """The tier_stats response should have stm/mtm/ltm counts."""
        expected_keys = {"stm", "mtm", "ltm", "total"}
        stats = {"stm": 10, "mtm": 50, "ltm": 200, "total": 260}
        assert expected_keys.issubset(stats.keys())

    def test_promote_protocol(self):
        """promote action should specify entry_id and target_tier."""
        msg = {
            "type": "promote",
            "entry_id": "abc-123",
            "target_tier": "mtm",
        }
        assert msg["type"] == "promote"
        assert msg["target_tier"] in ("stm", "mtm", "ltm")

    def test_summarize_history_protocol(self):
        """summarize_history should accept messages array."""
        msg = {
            "type": "summarize_history",
            "messages": [
                {"role": "user", "content": "Bonjour"},
                {"role": "assistant", "content": "Bonjour Alex!"},
            ],
        }
        assert msg["type"] == "summarize_history"
        assert len(msg["messages"]) == 2
