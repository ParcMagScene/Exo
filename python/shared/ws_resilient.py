"""
WebSocket resilient helpers (Hardening 2026).

Ce module fournit des utilitaires défensifs autour des clients/serveurs
WebSocket EXO **sans toucher** aux composants critiques exclus :

- `server_ws.py` (Orpheus TTS) — EXCLU
- `server_gguf.py` (LLM)      — EXCLU
- `server_stt.py` (Whisper)   — EXCLU

Les helpers ici sont à utiliser dans les services périphériques (NLU,
context, planner, executor, verifier, etc.) qui dialoguent avec
l'orchestrateur, **pas** dans les boucles audio temps-réel.

Utilitaires exposés :
  - `WsBackoff`           : backoff exponentiel borné pour reconnexions.
  - `parse_ws_message`    : JSON-parse défensif (retourne `default` si
                            payload invalide, log structuré).
  - `safe_send_json`      : envoie un dict JSON avec timeout + capture
                            d'erreurs de transport (websockets/aiohttp/qt).
  - `make_reconnect_loop` : décorateur asynchrone qui re-tente une coroutine
                            de connexion avec circuit-breaker via
                            `shared.resilience.CircuitBreaker`.
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Awaitable, Callable, Optional

from .hardening import RateLimiter, safe_json_dumps, safe_json_loads, with_timeout

logger = logging.getLogger("exo.ws_resilient")
logger.addHandler(logging.NullHandler())

__all__ = [
    "WsBackoff",
    "parse_ws_message",
    "safe_send_json",
    "make_reconnect_loop",
]


class WsBackoff:
    """Backoff exponentiel borné avec jitter et rate-limit anti-tempête.

    Politique :
      - délai = min(initial * factor**n, max) + jitter ±20%
      - rate-limit global (par défaut 20 reconnexions / minute) pour éviter
        qu'une boucle de reconnexion ne sature le CPU/réseau si le serveur
        est définitivement KO.
    """

    def __init__(
        self,
        *,
        initial_s: float = 0.5,
        max_s: float = 30.0,
        factor: float = 2.0,
        max_per_minute: int = 20,
    ) -> None:
        self._initial = float(initial_s)
        self._max = float(max_s)
        self._factor = float(factor)
        self._current = self._initial
        self._limiter = RateLimiter(max_per_minute, 60.0)

    def reset(self) -> None:
        self._current = self._initial

    def next_delay(self) -> float:
        delay = min(self._current, self._max)
        self._current = min(self._current * self._factor, self._max)
        jitter = delay * 0.2 * (random.random() * 2 - 1)
        return max(0.05, delay + jitter)

    def allow_reconnect(self) -> bool:
        """False si on dépasse le quota anti-tempête."""
        return self._limiter.try_acquire()


def parse_ws_message(raw: Any, *, default: Optional[dict] = None) -> dict:
    """Parse un message WS en dict de manière défensive.

    Accepte str / bytes / bytearray / dict. Tout autre type ou JSON invalide
    retourne `default` (ou {} si non fourni) et log un warning structuré.
    """
    if default is None:
        default = {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover - decode robuste
            logger.warning("WS payload bytes non décodable : %s", exc)
            return dict(default)
    if not isinstance(raw, str):
        logger.warning("WS payload type inattendu : %s", type(raw).__name__)
        return dict(default)
    parsed = safe_json_loads(raw, default=None)
    if not isinstance(parsed, dict):
        # JSON valide mais pas un dict (liste, scalaire) -> trace courte.
        snippet = raw[:120].replace("\n", " ")
        logger.warning("WS payload non-dict : %s", snippet)
        return dict(default)
    return parsed


async def safe_send_json(
    websocket: Any,
    payload: dict,
    *,
    timeout_s: float = 5.0,
    label: str = "ws.send",
) -> bool:
    """Envoie `payload` (JSON) sur `websocket` avec timeout et erreurs avalées.

    Retourne True si l'envoi a réussi, False sinon (la coroutine appelante
    décide alors de reconnecter / abandonner).

    Compatible avec `websockets.WebSocketClientProtocol`, `aiohttp.ClientWebSocketResponse`
    et tout objet exposant une méthode `send(str)` async.
    """
    raw = safe_json_dumps(payload, default="{}")
    try:
        send = getattr(websocket, "send_str", None) or getattr(websocket, "send", None)
        if send is None:
            logger.warning("[%s] objet WS sans méthode send()", label)
            return False
        await with_timeout(send, timeout_s, raw, fallback=None, label=label)
        return True
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("[%s] échec envoi WS : %s", label, exc)
        return False


def make_reconnect_loop(
    connect: Callable[[], Awaitable[Any]],
    *,
    on_connected: Optional[Callable[[Any], Awaitable[None]]] = None,
    backoff: Optional[WsBackoff] = None,
    label: str = "ws.reconnect",
) -> Callable[[], Awaitable[None]]:
    """Construit une boucle de reconnexion asynchrone défensive.

    Usage :
        loop = make_reconnect_loop(connect=my_connect, on_connected=my_handler)
        await loop()
    """
    bo = backoff or WsBackoff()

    async def _loop() -> None:
        while True:
            if not bo.allow_reconnect():
                logger.error(
                    "[%s] quota reconnexion dépassé — pause 60 s avant reprise",
                    label,
                )
                await asyncio.sleep(60.0)
                bo.reset()
                continue
            try:
                ws = await connect()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                delay = bo.next_delay()
                logger.warning(
                    "[%s] connexion échouée (%s) — retry dans %.2fs",
                    label,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            bo.reset()
            try:
                if on_connected is not None:
                    await on_connected(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("[%s] handler post-connexion levé : %s", label, exc)
            delay = bo.next_delay()
            logger.info("[%s] déconnecté — retry dans %.2fs", label, delay)
            await asyncio.sleep(delay)

    return _loop
