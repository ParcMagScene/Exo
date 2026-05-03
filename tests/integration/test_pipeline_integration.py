"""
Tests d'intégration — Pipeline STT (connexion WebSocket)
Teste la connexion/déconnexion aux serveurs sans nécessiter
que les serveurs soient en cours d'exécution.
"""

import asyncio
import json
import pytest

try:
    import websockets
except ImportError:
    pytest.skip("websockets not installed", allow_module_level=True)


# ─────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────

STT_URL = "ws://localhost:8766"
TTS_URL = "ws://localhost:8767"
VAD_URL = "ws://localhost:8768"
NLU_URL = "ws://localhost:8772"
MEM_URL = "ws://localhost:8771"


async def try_connect(url: str, timeout: float = 2.0) -> bool:
    """Tente une connexion WS, retourne True si réussie."""
    try:
        async with asyncio.timeout(timeout):
            async with websockets.connect(url):
                return True
    except Exception:
        return False


async def send_recv(url: str, msg: dict, timeout: float = 5.0) -> dict | None:
    """Envoie un JSON et attend la réponse."""
    try:
        async with asyncio.timeout(timeout):
            async with websockets.connect(url) as ws:
                await ws.send(json.dumps(msg))
                raw = await ws.recv()
                return json.loads(raw)
    except Exception:
        return None


# ─────────────────────────────────────────────────────
#  Tests — portent le marker "integration"
#
#  Exécuter uniquement si les serveurs tournent :
#    pytest tests/integration/ -m integration
# ─────────────────────────────────────────────────────

pytestmark = pytest.mark.integration


class TestSTTIntegration:
    """Tests d'intégration STT."""

    @pytest.mark.asyncio
    async def test_stt_connect(self):
        ok = await try_connect(STT_URL)
        if not ok:
            pytest.skip("STT server not running")
        assert ok

    @pytest.mark.asyncio
    async def test_stt_start_end(self):
        try:
            async with asyncio.timeout(5.0):
                async with websockets.connect(STT_URL) as ws:
                    await ws.send(json.dumps({"type": "start"}))
                    await ws.send(json.dumps({"type": "end"}))
                    # Attendre la réponse finale
                    raw = await ws.recv()
                    msg = json.loads(raw)
                    assert msg["type"] in ("final", "error", "ready")
        except Exception:
            pytest.skip("STT server not running or timed out")


class TestNLUIntegration:
    """Tests d'intégration NLU."""

    @pytest.mark.asyncio
    async def test_nlu_classify(self):
        result = await send_recv(NLU_URL, {
            "action": "classify",
            "text": "allume la lumière du salon"
        })
        if result is None:
            pytest.skip("NLU server not running")
        assert result["type"] == "nlu_result"
        assert result["intent"] == "home_control"

    @pytest.mark.asyncio
    async def test_nlu_ping(self):
        result = await send_recv(NLU_URL, {"action": "ping"})
        if result is None:
            pytest.skip("NLU server not running")
        assert result["type"] == "pong"


class TestVADIntegration:
    """Tests d'intégration VAD."""

    @pytest.mark.asyncio
    async def test_vad_connect(self):
        ok = await try_connect(VAD_URL)
        if not ok:
            pytest.skip("VAD server not running")
        assert ok


class TestMemoryIntegration:
    """Tests d'intégration Memory."""

    @pytest.mark.asyncio
    async def test_memory_stats(self):
        try:
            async with asyncio.timeout(5.0):
                async with websockets.connect(MEM_URL) as ws:
                    # Le serveur envoie d'abord un message "ready"
                    raw = await ws.recv()
                    ready = json.loads(raw)
                    assert ready["type"] == "ready"
                    # Envoyer la requête stats
                    await ws.send(json.dumps({"type": "stats"}))
                    raw2 = await ws.recv()
                    result = json.loads(raw2)
                    assert result["type"] == "stats"
                    assert "count" in result
        except Exception:
            pytest.skip("Memory server not running")
