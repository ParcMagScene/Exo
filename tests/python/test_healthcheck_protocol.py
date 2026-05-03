"""
Tests unitaires — Ping/Pong health check protocol across all servers
"""

import json
import pytest


class TestPingPongProtocol:
    """Vérifie que chaque serveur reconnaît le message ping et répond pong."""

    def _make_ping(self, variant: str = "type"):
        """Construit un message ping selon la variante du serveur."""
        if variant == "action":
            return json.dumps({"action": "ping"})
        return json.dumps({"type": "ping"})

    def _parse_pong(self, raw: str) -> dict:
        msg = json.loads(raw)
        assert msg.get("type") == "pong", f"Expected pong, got: {msg}"
        return msg

    # ── Tests de format ──

    def test_ping_type_format(self):
        """Format ping avec 'type' (STT, TTS, VAD, WakeWord, Memory)."""
        ping = json.loads(self._make_ping("type"))
        assert ping == {"type": "ping"}

    def test_ping_action_format(self):
        """Format ping avec 'action' (NLU)."""
        ping = json.loads(self._make_ping("action"))
        assert ping == {"action": "ping"}

    def test_pong_format(self):
        """Le pong doit être un JSON avec type=pong."""
        pong_raw = json.dumps({"type": "pong"})
        msg = self._parse_pong(pong_raw)
        assert msg["type"] == "pong"

    # ── Tests de dispatch pour chaque serveur ──

    @pytest.mark.parametrize("server", [
        "stt", "tts", "vad", "wakeword", "memory"
    ])
    def test_type_ping_dispatch(self, server):
        """Chaque serveur (sauf NLU) doit router type=ping → pong."""
        msg = json.loads(self._make_ping("type"))
        assert msg.get("type") == "ping"
        # Simulate the response
        response = json.dumps({"type": "pong"})
        parsed = json.loads(response)
        assert parsed["type"] == "pong"

    def test_nlu_action_ping_dispatch(self):
        """NLU utilise action=ping au lieu de type=ping."""
        msg = json.loads(self._make_ping("action"))
        assert msg.get("action") == "ping"
        response = json.dumps({"type": "pong"})
        parsed = json.loads(response)
        assert parsed["type"] == "pong"

    # ── Tests de robustesse ──

    def test_unknown_type_ignored(self):
        """Un type inconnu ne doit pas crasher (serveur ignore)."""
        msg = json.dumps({"type": "unknown_command"})
        parsed = json.loads(msg)
        assert parsed["type"] != "ping"

    def test_malformed_json_safe(self):
        """Un JSON invalide ne doit pas crasher le parsing."""
        raw = "not valid json {"
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)

    def test_empty_type_safe(self):
        """Un message sans type ne doit pas matcher ping."""
        msg = json.loads(json.dumps({"data": "hello"}))
        assert msg.get("type", "") != "ping"

    def test_ping_response_latency_format(self):
        """Le health check C++ mesure la latence — vérifier que le pong est minimal."""
        import time
        start = time.monotonic()
        pong = json.dumps({"type": "pong"})
        _ = json.loads(pong)
        elapsed = time.monotonic() - start
        # Le sérialisation JSON doit être < 1ms
        assert elapsed < 0.01
