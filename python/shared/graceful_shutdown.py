"""
graceful_shutdown.py
====================
Helper unifié pour fermeture propre des serveurs WebSocket EXO.

Sur POSIX  : capture SIGTERM, SIGINT.
Sur Windows: capture SIGINT, SIGBREAK (Ctrl+Break) — SIGTERM n'est PAS
             interceptable car Stop-Process -Force = TerminateProcess.
             Pour un graceful shutdown sur Windows, utilisez
             `taskkill /PID xxx` (sans /F) ou GenerateConsoleCtrlEvent.

Exemple d'usage :

    from python.shared.graceful_shutdown import install_shutdown, ShutdownToken

    async def main() -> None:
        token = install_shutdown(name="orpheus")
        server = await websockets.serve(handler, host, port)
        try:
            await token.wait()
        finally:
            server.close()
            await server.wait_closed()
"""
from __future__ import annotations

import asyncio
import logging
import signal
from typing import Optional

log = logging.getLogger(__name__)


class ShutdownToken:
    """Wrapper autour d'un asyncio.Event signalé par les handlers de signaux."""

    def __init__(self, name: str) -> None:
        self._event = asyncio.Event()
        self._name = name

    def trigger(self, source: str) -> None:
        if not self._event.is_set():
            log.info("[%s] arrêt gracieux demandé (source=%s)", self._name, source)
            self._event.set()

    async def wait(self) -> None:
        await self._event.wait()

    @property
    def is_set(self) -> bool:
        return self._event.is_set()


def install_shutdown(name: str = "service",
                     loop: Optional[asyncio.AbstractEventLoop] = None) -> ShutdownToken:
    """Installe les handlers de signaux et retourne un ShutdownToken.

    Doit être appelé depuis une coroutine (boucle asyncio active).
    Idempotent et safe sur Windows comme POSIX.
    """
    token = ShutdownToken(name)
    if loop is None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

    def _request(source: str) -> None:
        try:
            loop.call_soon_threadsafe(token.trigger, source)
        except RuntimeError:
            # Loop déjà fermée
            pass

    # POSIX : add_signal_handler est natif pour asyncio.
    # Windows : add_signal_handler n'est pas supporté → fallback signal.signal.
    handlers = [("SIGINT", signal.SIGINT), ("SIGTERM", getattr(signal, "SIGTERM", None))]
    if hasattr(signal, "SIGBREAK"):
        handlers.append(("SIGBREAK", signal.SIGBREAK))

    for label, sig in handlers:
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, _request, label)
        except (NotImplementedError, RuntimeError, ValueError):
            try:
                signal.signal(sig, lambda s, f, _l=label: _request(_l))
            except (ValueError, OSError):
                # SIGTERM inutilisable sur Windows worker thread, on ignore.
                pass
    return token
