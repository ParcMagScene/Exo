"""
Tests unitaires — Memory Server (MemoryEntry + protocole)
Ce qui est testable sans FAISS/SentenceTransformers.
"""

import sys
import json
import uuid
import time
from pathlib import Path

import pytest


class TestMemoryEntry:
    """Tests de la structure MemoryEntry."""

    def test_create_entry(self):
        from memory_hierarchy import MemoryEntry

        entry = MemoryEntry(
            id="test-id-123",
            text="Le ciel est bleu",
            importance=0.8,
            tags=["test", "couleur"],
            category="fact",
        )
        assert entry.text == "Le ciel est bleu"
        assert entry.importance == 0.8
        assert "test" in entry.tags
        assert entry.category == "fact"

    def test_entry_to_dict(self):
        from memory_hierarchy import MemoryEntry

        entry = MemoryEntry(
            id="abc123",
            text="test memory",
            importance=0.5,
            tags=["tag1"],
            category="general",
        )
        d = entry.to_dict()
        assert d["id"] == "abc123"
        assert d["text"] == "test memory"
        assert d["importance"] == 0.5


class TestMemoryProtocol:
    """Tests du protocole WS memory."""

    def test_add_message_format(self):
        msg = {
            "type": "add",
            "text": "souvenir important",
            "importance": 0.9,
            "tags": ["personnel"],
            "category": "experience",
        }
        assert msg["type"] == "add"
        assert isinstance(msg["importance"], float)

    def test_search_message_format(self):
        msg = {
            "type": "search",
            "query": "quel était le souvenir ?",
            "top_k": 5,
        }
        assert msg["type"] == "search"
        assert msg["top_k"] == 5

    def test_stats_response_format(self):
        response = {
            "type": "stats",
            "count": 42,
            "model": "all-MiniLM-L6-v2",
        }
        assert response["type"] == "stats"
        assert isinstance(response["count"], int)

    def test_error_response_format(self):
        response = {
            "type": "error",
            "message": "Memory not found",
        }
        assert response["type"] == "error"
        assert "not found" in response["message"].lower()
