"""
EXO Domotique v2 — EventManager

Moteur d'événements domotiques : push (WebSocket) + polling intelligent.
Détection de changement d'état, propagation au HomeGraph.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Awaitable

log = logging.getLogger("event_manager")

# Type alias for event callbacks
EventCallback = Callable[[str, dict, dict], Awaitable[None]]
# callback(device_id, old_state, new_state)


class EventManager:
    """Gestionnaire d'événements domotiques.

    Supporte :
    - subscriptions par device / wildcard
    - polling intelligent (intervalle adaptatif)
    - détection de changement d'état
    """

    def __init__(self):
        self._subscriptions: dict[str, list[EventCallback]] = {}
        self._device_states: dict[str, dict] = {}
        self._poll_intervals: dict[str, float] = {}  # device_id → seconds
        self._default_poll_interval = 15.0            # secondes
        self._min_poll_interval = 5.0
        self._max_poll_interval = 60.0
        self._running = False
        self._poll_task: asyncio.Task | None = None
        self._poll_fn: Callable[[str], Awaitable[dict | None]] | None = None
        self._event_count = 0
        self._last_events: list[dict] = []
        self._max_history = 200

    # ── Subscriptions ─────────────────────────────────

    def subscribe(self, device_id: str, callback: EventCallback) -> None:
        """Abonner un callback aux événements d'un device."""
        if device_id not in self._subscriptions:
            self._subscriptions[device_id] = []
        self._subscriptions[device_id].append(callback)

    def subscribe_all(self, callback: EventCallback) -> None:
        """Abonner un callback à TOUS les événements (wildcard *)."""
        self.subscribe("*", callback)

    def unsubscribe(self, device_id: str,
                    callback: EventCallback | None = None) -> bool:
        """Retirer un callback (ou tous) pour un device."""
        if device_id not in self._subscriptions:
            return False
        if callback is None:
            del self._subscriptions[device_id]
        else:
            try:
                self._subscriptions[device_id].remove(callback)
            except ValueError:
                return False
        return True

    # ── Event processing ──────────────────────────────

    async def on_event(self, device_id: str, new_state: dict) -> bool:
        """Notifier un changement d'état.

        Compare avec le dernier état connu, propage aux abonnés si changé.
        Retourne True si l'état a effectivement changé.
        """
        old_state = self._device_states.get(device_id, {})

        # Détection de changement
        if old_state == new_state:
            return False

        self._device_states[device_id] = dict(new_state)
        self._event_count += 1

        # Record event
        event_record = {
            "device_id": device_id,
            "timestamp": time.time(),
            "old_state": dict(old_state),
            "new_state": dict(new_state),
        }
        self._last_events.append(event_record)
        if len(self._last_events) > self._max_history:
            self._last_events = self._last_events[-self._max_history:]

        # Notify subscribers
        callbacks = list(self._subscriptions.get(device_id, []))
        callbacks += list(self._subscriptions.get("*", []))

        for cb in callbacks:
            try:
                await cb(device_id, old_state, new_state)
            except Exception as e:
                log.warning("Event callback error for %s: %s", device_id, e)

        # Adapt polling interval (more active → faster poll)
        self._adapt_poll_interval(device_id, changed=True)

        return True

    # ── Polling intelligent ───────────────────────────

    def set_poll_function(self, fn: Callable[[str], Awaitable[dict | None]]) -> None:
        """Définir la fonction de polling : async fn(device_id) -> state dict."""
        self._poll_fn = fn

    def set_poll_interval(self, device_id: str, interval: float) -> None:
        """Définir l'intervalle de polling pour un device."""
        self._poll_intervals[device_id] = max(
            self._min_poll_interval,
            min(self._max_poll_interval, interval),
        )

    async def start_polling(self, device_ids: list[str] | None = None) -> None:
        """Démarrer le polling intelligent."""
        if self._running:
            return
        self._running = True

        if device_ids:
            for did in device_ids:
                if did not in self._poll_intervals:
                    self._poll_intervals[did] = self._default_poll_interval

        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop_polling(self) -> None:
        """Arrêter le polling."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

    async def _poll_loop(self) -> None:
        """Boucle de polling : interroge chaque device selon son intervalle."""
        last_poll: dict[str, float] = {}

        while self._running:
            now = time.monotonic()
            for device_id, interval in list(self._poll_intervals.items()):
                last = last_poll.get(device_id, 0)
                if now - last < interval:
                    continue

                last_poll[device_id] = now
                if self._poll_fn:
                    try:
                        new_state = await asyncio.wait_for(
                            self._poll_fn(device_id), timeout=10,
                        )
                        if new_state is not None:
                            await self.on_event(device_id, new_state)
                    except asyncio.TimeoutError:
                        log.debug("Poll timeout for %s", device_id)
                    except Exception as e:
                        log.warning("Poll error for %s: %s", device_id, e)

            await asyncio.sleep(1.0)

    def _adapt_poll_interval(self, device_id: str, *, changed: bool) -> None:
        """Adapter l'intervalle de polling selon l'activité."""
        current = self._poll_intervals.get(device_id, self._default_poll_interval)
        if changed:
            # Device actif → polling plus rapide
            new = max(self._min_poll_interval, current * 0.8)
        else:
            # Device calme → polling plus lent
            new = min(self._max_poll_interval, current * 1.2)
        self._poll_intervals[device_id] = new

    # ── API ───────────────────────────────────────────

    def recent_events(self, n: int = 50) -> list[dict]:
        """Retourne les N derniers événements."""
        return self._last_events[-n:]

    def device_state(self, device_id: str) -> dict | None:
        """Dernier état connu d'un device."""
        return self._device_states.get(device_id)

    def stats(self) -> dict:
        return {
            "subscriptions": len(self._subscriptions),
            "tracked_devices": len(self._device_states),
            "total_events": self._event_count,
            "polling_active": self._running,
            "poll_devices": len(self._poll_intervals),
        }
