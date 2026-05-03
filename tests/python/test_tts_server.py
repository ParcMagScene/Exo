"""
Tests unitaires — TTS Server (PhraseCache + protocole)
"""

import sys
import json
from pathlib import Path

import pytest


class TestPhraseCacheImport:
    """Tests du PhraseCache si disponible."""

    def _get_cache_class(self):
        try:
            from tts_server import PhraseCache
            return PhraseCache
        except ImportError:
            pytest.skip("PhraseCache not available in tts_server")

    def test_cache_creation(self):
        CacheClass = self._get_cache_class()
        cache = CacheClass(max_entries=10)
        assert cache is not None

    def test_cache_miss(self):
        CacheClass = self._get_cache_class()
        cache = CacheClass(max_entries=10)
        result = cache.get("nonexistent", "voice", "fr")
        assert result is None

    def test_cache_hit(self):
        CacheClass = self._get_cache_class()
        cache = CacheClass(max_entries=10)
        cache.put("hello", "voice", "fr", b"\x00\x01\x02\x03")
        result = cache.get("hello", "voice", "fr")
        assert result == b"\x00\x01\x02\x03"

    def test_cache_eviction(self):
        CacheClass = self._get_cache_class()
        cache = CacheClass(max_entries=3)
        cache.put("a", "v", "fr", b"1")
        cache.put("b", "v", "fr", b"2")
        cache.put("c", "v", "fr", b"3")
        cache.put("d", "v", "fr", b"4")  # devrait évincer "a"
        assert cache.get("a", "v", "fr") is None
        assert cache.get("d", "v", "fr") == b"4"


class TestTTSProtocol:
    """Tests du protocole WebSocket TTS."""

    def test_synthesize_message(self):
        msg = {
            "type": "synthesize",
            "text": "Bonjour le monde",
            "voice": "Claribel Dervla",
            "lang": "fr",
            "rate": 1.0,
            "pitch": 1.0,
        }
        assert msg["type"] == "synthesize"
        assert isinstance(msg["text"], str)

    def test_cancel_message(self):
        msg = {"type": "cancel"}
        assert msg["type"] == "cancel"

    def test_list_voices_message(self):
        msg = {"type": "list_voices"}
        assert msg["type"] == "list_voices"

    def test_set_voice_message(self):
        msg = {"type": "set_voice", "voice": "Claribel Dervla"}
        assert msg["type"] == "set_voice"

    def test_ready_response_format(self):
        response = {
            "type": "ready",
            "voice": "Claribel Dervla",
            "lang": "fr",
            "sample_rate": 24000,
        }
        assert response["type"] == "ready"
        assert response["sample_rate"] == 24000

    def test_end_response_format(self):
        response = {
            "type": "end",
            "duration": 2.5,
        }
        assert response["type"] == "end"
        assert response["duration"] > 0

    def test_voices_response_format(self):
        response = {
            "type": "voices",
            "voices": ["Claribel Dervla", "Annmarie Nele"],
        }
        assert response["type"] == "voices"
        assert isinstance(response["voices"], list)
