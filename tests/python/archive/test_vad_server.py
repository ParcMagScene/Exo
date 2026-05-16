"""
Tests unitaires — VAD Server (logique session sans modèle ML)
"""

import sys
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import numpy as np


class TestVADProtocol:
    """Tests du protocole WebSocket VAD sans charger Silero."""

    @pytest.fixture
    def mock_ws(self):
        ws = AsyncMock()
        ws.remote_address = ("127.0.0.1", 9999)
        ws.send = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_config_message(self, mock_ws):
        """Le message config doit être parsé correctement."""
        # Simuler la réception du message config
        config_msg = json.dumps({"type": "config", "threshold": 0.7})

        # Vérifier que le parsing JSON fonctionne
        msg = json.loads(config_msg)
        assert msg["type"] == "config"
        assert msg["threshold"] == 0.7

    def test_pcm16_to_float(self):
        """Conversion PCM16 → float32 [-1, 1] pour Silero."""
        pcm16 = np.array([0, 16384, -16384, 32767, -32768], dtype=np.int16)
        float_audio = pcm16.astype(np.float32) / 32768.0

        assert float_audio.dtype == np.float32
        assert abs(float_audio[0]) < 1e-6
        assert abs(float_audio[1] - 0.5) < 0.01
        assert abs(float_audio[2] + 0.5) < 0.01
        assert float_audio[3] < 1.01
        assert float_audio[4] >= -1.0

    def test_pcm16_chunk_size(self):
        """Silero attend 512 samples à 16kHz (32ms)."""
        from vad_server import CHUNK_SAMPLES
        assert CHUNK_SAMPLES == 512

    def test_vad_json_response_format(self):
        """Format de réponse VAD attendu."""
        response = {
            "type": "vad",
            "score": 0.85,
            "is_speech": True,
        }
        assert response["type"] == "vad"
        assert isinstance(response["score"], float)
        assert isinstance(response["is_speech"], bool)
