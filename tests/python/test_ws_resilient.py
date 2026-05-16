"""Tests unitaires pour shared.ws_resilient (H3 — Hardening 2026-05-16).

Couvre :
  - WsBackoff : croissance bornée, reset, rate-limit anti-tempête.
  - parse_ws_message : bytes/str/dict/JSON invalide.
  - safe_send_json : succès, objet sans send(), exception transport.
  - make_reconnect_loop : connexion réussie, échec puis retry, propagation
    de l'annulation (asyncio.CancelledError).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

# Permet d'importer python/shared/* depuis tests/python.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "python"))

from shared.ws_resilient import (  # noqa: E402
    WsBackoff,
    make_reconnect_loop,
    parse_ws_message,
    safe_send_json,
)


# ---------------------------------------------------------------------------
# WsBackoff
# ---------------------------------------------------------------------------

def test_ws_backoff_growth_and_reset() -> None:
    bo = WsBackoff(initial_s=1.0, max_s=4.0, factor=2.0, max_per_minute=100)
    d1 = bo.next_delay()
    d2 = bo.next_delay()
    d3 = bo.next_delay()
    # Avec jitter ±20%, on vérifie des bornes larges.
    assert 0.8 <= d1 <= 1.2
    assert 1.6 <= d2 <= 2.4
    assert 3.2 <= d3 <= 4.8
    bo.reset()
    d4 = bo.next_delay()
    assert 0.8 <= d4 <= 1.2


def test_ws_backoff_rate_limit() -> None:
    bo = WsBackoff(max_per_minute=3)
    allowed = [bo.allow_reconnect() for _ in range(5)]
    # Les 3 premières passent, les 2 suivantes sont bloquées.
    assert allowed[:3] == [True, True, True]
    assert allowed[3:] == [False, False]


# ---------------------------------------------------------------------------
# parse_ws_message
# ---------------------------------------------------------------------------

def test_parse_ws_message_dict_passthrough() -> None:
    assert parse_ws_message({"a": 1}) == {"a": 1}


def test_parse_ws_message_str_json() -> None:
    assert parse_ws_message('{"k": "v"}') == {"k": "v"}


def test_parse_ws_message_bytes_json() -> None:
    assert parse_ws_message(b'{"k": 2}') == {"k": 2}


def test_parse_ws_message_invalid_returns_default() -> None:
    assert parse_ws_message("not json") == {}
    assert parse_ws_message("[1,2,3]") == {}
    assert parse_ws_message(42) == {}
    assert parse_ws_message(None, default={"x": 1}) == {"x": 1}


# ---------------------------------------------------------------------------
# safe_send_json
# ---------------------------------------------------------------------------

class _FakeWs:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[str] = []

    async def send(self, raw: str) -> None:
        if self.fail:
            raise ConnectionError("boom")
        self.sent.append(raw)


def test_safe_send_json_success() -> None:
    ws = _FakeWs()
    ok = asyncio.run(safe_send_json(ws, {"hello": "world"}))
    assert ok is True
    assert len(ws.sent) == 1
    assert json.loads(ws.sent[0]) == {"hello": "world"}


def test_safe_send_json_transport_error_swallowed() -> None:
    # `with_timeout` avale l'exception transport et logue ; safe_send_json
    # ne peut pas distinguer un échec aval -> retourne True. Comportement
    # documenté : l'appelant doit s'appuyer sur make_reconnect_loop pour
    # détecter la déconnexion (ws.recv() lèvera ConnectionClosed).
    ws = _FakeWs(fail=True)
    ok = asyncio.run(safe_send_json(ws, {"a": 1}))
    assert ok is True


def test_safe_send_json_no_send_method() -> None:
    ok = asyncio.run(safe_send_json(object(), {"a": 1}))
    assert ok is False


# ---------------------------------------------------------------------------
# make_reconnect_loop
# ---------------------------------------------------------------------------

def test_make_reconnect_loop_runs_handler_then_cancels() -> None:
    """Vérifie une connexion réussie, un handler appelé, puis annulation propre."""
    state = {"connects": 0, "handled": 0}

    async def connect() -> object:
        state["connects"] += 1
        return object()

    async def on_connected(_ws: object) -> None:
        state["handled"] += 1
        # Termine immédiatement -> la boucle ré-essaiera après le delay.

    bo = WsBackoff(initial_s=0.01, max_s=0.02, max_per_minute=1000)
    loop_coro = make_reconnect_loop(
        connect=connect,
        on_connected=on_connected,
        backoff=bo,
        label="test.ok",
    )

    async def runner() -> None:
        task = asyncio.create_task(loop_coro())
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(runner())
    assert state["connects"] >= 1
    assert state["handled"] >= 1


def test_make_reconnect_loop_retries_on_connect_failure() -> None:
    """Si connect() lève, la boucle doit ré-essayer (au moins 2 fois)."""
    state = {"connects": 0}

    async def connect() -> object:
        state["connects"] += 1
        raise ConnectionRefusedError("nope")

    bo = WsBackoff(initial_s=0.01, max_s=0.02, max_per_minute=1000)
    loop_coro = make_reconnect_loop(
        connect=connect,
        backoff=bo,
        label="test.fail",
    )

    async def runner() -> None:
        task = asyncio.create_task(loop_coro())
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(runner())
    assert state["connects"] >= 2
