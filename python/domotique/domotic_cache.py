"""
EXO Domotique v2 — DomoticCache

Cache d'état des appareils domotiques avec TTL configurable,
invalidation automatique, et fallback en cas de service indisponible.
"""

from __future__ import annotations

import time
import threading
from typing import Any


class CacheEntry:
    __slots__ = ("state", "timestamp", "ttl")

    def __init__(self, state: dict, ttl: float):
        self.state = state
        self.timestamp = time.monotonic()
        self.ttl = ttl

    @property
    def expired(self) -> bool:
        return (time.monotonic() - self.timestamp) > self.ttl


class DomoticCache:
    """Cache d'état domotique par device_id.

    Thread-safe. TTL configurable par appareil.
    """

    DEFAULT_TTL = 30.0  # secondes

    def __init__(self, default_ttl: float = DEFAULT_TTL):
        self._default_ttl = default_ttl
        self._store: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get_state(self, device_id: str) -> dict | None:
        """Retourne l'état caché si valide, None sinon."""
        with self._lock:
            entry = self._store.get(device_id)
            if entry is None or entry.expired:
                self._misses += 1
                return None
            self._hits += 1
            return dict(entry.state)

    def set_state(self, device_id: str, state: dict,
                  ttl: float | None = None) -> None:
        """Met en cache l'état d'un appareil."""
        with self._lock:
            self._store[device_id] = CacheEntry(
                state=dict(state),
                ttl=ttl if ttl is not None else self._default_ttl,
            )

    def invalidate(self, device_id: str) -> bool:
        """Invalide le cache pour un appareil. Retourne True si existait."""
        with self._lock:
            return self._store.pop(device_id, None) is not None

    def invalidate_all(self) -> int:
        """Invalide tout le cache. Retourne le nombre d'entrées supprimées."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def has(self, device_id: str) -> bool:
        """Vérifie si un appareil est en cache (et non expiré)."""
        with self._lock:
            entry = self._store.get(device_id)
            return entry is not None and not entry.expired

    def all_states(self) -> dict[str, dict]:
        """Retourne tous les états non expirés."""
        with self._lock:
            return {
                did: dict(entry.state)
                for did, entry in self._store.items()
                if not entry.expired
            }

    def stats(self) -> dict[str, Any]:
        """Statistiques du cache."""
        with self._lock:
            valid = sum(1 for e in self._store.values() if not e.expired)
            total = self._hits + self._misses
            return {
                "entries": len(self._store),
                "valid": valid,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 3) if total else 0.0,
            }

    def cleanup(self) -> int:
        """Supprime les entrées expirées. Retourne le nombre supprimé."""
        with self._lock:
            expired = [did for did, e in self._store.items() if e.expired]
            for did in expired:
                del self._store[did]
            return len(expired)
