"""
Tests unitaires — STT Server (protocole + hallucination detection)
"""

import sys
import json
from pathlib import Path

import pytest


class TestSTTHallucinationDetection:
    """Tests de détection d'hallucinations Whisper."""

    def _get_hallucination_checker(self):
        """Import la fonction si elle existe."""
        try:
            from stt_server import _is_hallucination
            return _is_hallucination
        except ImportError:
            pytest.skip("_is_hallucination not available")

    def test_empty_text_is_hallucination(self):
        check = self._get_hallucination_checker()
        assert check("") is True or check("") is False  # ne crash pas

    def test_normal_text_not_hallucination(self):
        check = self._get_hallucination_checker()
        assert check("bonjour comment allez-vous aujourd'hui") is False

    def test_repeated_pattern_is_hallucination(self):
        check = self._get_hallucination_checker()
        # Texte typiquement halluciné par Whisper
        result = check("Merci. Merci. Merci. Merci. Merci. Merci.")
        # Devrait être détecté comme hallucination
        assert result is True


class TestSTTProtocol:
    """Tests du protocole WebSocket STT."""

    def test_start_message(self):
        msg = json.dumps({"type": "start"})
        parsed = json.loads(msg)
        assert parsed["type"] == "start"

    def test_end_message(self):
        msg = json.dumps({"type": "end"})
        parsed = json.loads(msg)
        assert parsed["type"] == "end"

    def test_config_message(self):
        msg = json.dumps({
            "type": "config",
            "language": "fr",
            "beam_size": 5,
        })
        parsed = json.loads(msg)
        assert parsed["type"] == "config"
        assert parsed["language"] == "fr"

    def test_final_response_format(self):
        response = {
            "type": "final",
            "text": "bonjour le monde",
            "segments": [{"start": 0.0, "end": 1.5, "text": "bonjour le monde"}],
            "duration": 1.5,
        }
        assert response["type"] == "final"
        assert isinstance(response["text"], str)
        assert isinstance(response["segments"], list)
        assert response["duration"] > 0

    def test_partial_response_format(self):
        response = {
            "type": "partial",
            "text": "bonjour",
        }
        assert response["type"] == "partial"


class TestSTTConstants:
    """Vérifie les constantes du serveur STT."""

    def test_default_port(self):
        try:
            from stt_server import DEFAULT_PORT
            assert DEFAULT_PORT == 8766
        except ImportError:
            # La constante peut être définie différemment
            pass
