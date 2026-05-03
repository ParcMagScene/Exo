"""
EXO v8.2 — LLM Warmup + KeepAlive

Pré-activation LLM pour réduire le temps de premier token :
- Warmup : ping léger au démarrage pour initialiser la session
- KeepAlive : ping périodique pour maintenir la connexion chaude
- Pré-chargement du squelette de prompt système

Intégration v9 : logs, métriques, traces.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Optional

log = logging.getLogger("pipeline.warmup")

# ── Configuration ────────────────────────────────────────────
DEFAULT_KEEPALIVE_INTERVAL = 240  # 4 minutes
DEFAULT_WARMUP_PROMPT = "Réponds OK."
DEFAULT_WARMUP_MAX_TOKENS = 1
WARMUP_TIMEOUT = 10.0


class LLMWarmup:
    """Pré-activation et maintien de session LLM.

    Réduit la latence du premier token en gardant la connexion
    et le contexte chauds. Compatible avec tout backend LLM
    exposant une API async (Anthropic, local, etc.).
    """

    def __init__(
        self,
        *,
        keepalive_interval: float = DEFAULT_KEEPALIVE_INTERVAL,
        warmup_prompt: str = DEFAULT_WARMUP_PROMPT,
        warmup_max_tokens: int = DEFAULT_WARMUP_MAX_TOKENS,
        system_prompt: str = "",
    ):
        self._keepalive_interval = keepalive_interval
        self._warmup_prompt = warmup_prompt
        self._warmup_max_tokens = warmup_max_tokens
        self._system_prompt = system_prompt

        # État
        self._warmed_up = False
        self._keepalive_task: Optional[asyncio.Task] = None
        self._last_warmup: float = 0.0
        self._warmup_count: int = 0
        self._keepalive_count: int = 0
        self._last_warmup_latency: float = 0.0
        self._send_fn: Optional[Any] = None
        self._running = False

    @property
    def warmed_up(self) -> bool:
        return self._warmed_up

    @property
    def last_warmup_latency(self) -> float:
        return self._last_warmup_latency

    def set_send_function(self, fn) -> None:
        """Injecte la fonction d'envoi LLM.

        fn doit être async et accepter (prompt, max_tokens, system) → str.
        """
        self._send_fn = fn

    async def warmup(self) -> dict[str, Any]:
        """Exécute un warmup : envoie un prompt léger + pré-charge le système.

        Returns:
            Dict avec status, latency_ms, warmed_up.
        """
        if self._send_fn is None:
            log.warning("warmup: pas de fonction d'envoi LLM configurée")
            return {"status": "skip", "reason": "no_send_fn", "warmed_up": False}

        t0 = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                self._send_fn(
                    self._warmup_prompt,
                    self._warmup_max_tokens,
                    self._system_prompt,
                ),
                timeout=WARMUP_TIMEOUT,
            )
            latency = (time.perf_counter() - t0) * 1000
            self._warmed_up = True
            self._last_warmup = time.monotonic()
            self._last_warmup_latency = latency
            self._warmup_count += 1
            log.info(f"LLM warmup OK en {latency:.0f}ms (#{self._warmup_count})")
            return {
                "status": "ok",
                "latency_ms": round(latency, 1),
                "warmed_up": True,
                "count": self._warmup_count,
            }
        except asyncio.TimeoutError:
            latency = (time.perf_counter() - t0) * 1000
            log.warning(f"LLM warmup timeout après {latency:.0f}ms")
            return {
                "status": "timeout",
                "latency_ms": round(latency, 1),
                "warmed_up": self._warmed_up,
            }
        except Exception as exc:
            latency = (time.perf_counter() - t0) * 1000
            log.error(f"LLM warmup erreur: {exc}")
            return {
                "status": "error",
                "error": str(exc),
                "latency_ms": round(latency, 1),
                "warmed_up": self._warmed_up,
            }

    async def keep_alive_loop(self) -> None:
        """Boucle de keep-alive : ping périodique pour garder la connexion chaude."""
        self._running = True
        log.info(f"KeepAlive démarré (intervalle={self._keepalive_interval}s)")
        try:
            while self._running:
                await asyncio.sleep(self._keepalive_interval)
                if not self._running:
                    break
                t0 = time.perf_counter()
                try:
                    if self._send_fn:
                        await asyncio.wait_for(
                            self._send_fn(
                                self._warmup_prompt,
                                self._warmup_max_tokens,
                                self._system_prompt,
                            ),
                            timeout=WARMUP_TIMEOUT,
                        )
                        latency = (time.perf_counter() - t0) * 1000
                        self._keepalive_count += 1
                        self._last_warmup = time.monotonic()
                        self._last_warmup_latency = latency
                        self._warmed_up = True
                        log.debug(f"KeepAlive ping OK en {latency:.0f}ms")
                except asyncio.TimeoutError:
                    log.warning("KeepAlive timeout")
                except Exception as exc:
                    log.warning(f"KeepAlive erreur: {exc}")
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            log.info("KeepAlive arrêté")

    def start_keepalive(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Démarre la boucle keep-alive en tâche de fond."""
        if self._keepalive_task and not self._keepalive_task.done():
            return
        _loop = loop or asyncio.get_event_loop()
        self._keepalive_task = _loop.create_task(self.keep_alive_loop())

    def stop_keepalive(self) -> None:
        """Arrête la boucle keep-alive."""
        self._running = False
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            self._keepalive_task = None

    def metrics(self) -> dict[str, Any]:
        """Retourne les métriques de warmup/keepalive."""
        return {
            "warmed_up": self._warmed_up,
            "warmup_count": self._warmup_count,
            "keepalive_count": self._keepalive_count,
            "last_warmup_latency_ms": round(self._last_warmup_latency, 1),
            "keepalive_interval_s": self._keepalive_interval,
            "running": self._running,
            "time_since_last_warmup_s": round(
                time.monotonic() - self._last_warmup, 1
            ) if self._last_warmup > 0 else None,
        }
