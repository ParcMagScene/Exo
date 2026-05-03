"""
EXO v8.2 — Cache Contextuel Intelligent

Cache intelligent avec TTL par domaine :
- Météo (ttl=600s), Actualités (ttl=300s), Domotique (ttl=30s)
- Network (ttl=60s), Outils (ttl=120s), LLM contexte (ttl=60s)
- LRU eviction, invalidation sélective, statistiques hit/miss

Intégration v9 : métriques, logs structurés.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

log = logging.getLogger("pipeline.cache")


class CacheDomain(Enum):
    """Domaines avec TTL par défaut."""
    WEATHER = "weather"
    NEWS = "news"
    DOMOTIQUE = "domotique"
    NETWORK = "network"
    TOOLS = "tools"
    LLM_CONTEXT = "llm_context"
    STT_RESULT = "stt_result"
    TTS_AUDIO = "tts_audio"
    GENERAL = "general"


# TTL par défaut (secondes) par domaine
DOMAIN_TTL: dict[CacheDomain, float] = {
    CacheDomain.WEATHER: 600.0,      # 10 minutes
    CacheDomain.NEWS: 300.0,         # 5 minutes
    CacheDomain.DOMOTIQUE: 30.0,     # 30 secondes (état temps réel)
    CacheDomain.NETWORK: 60.0,       # 1 minute
    CacheDomain.TOOLS: 120.0,        # 2 minutes
    CacheDomain.LLM_CONTEXT: 60.0,   # 1 minute
    CacheDomain.STT_RESULT: 10.0,    # 10 secondes
    CacheDomain.TTS_AUDIO: 300.0,    # 5 minutes (cache audio synthétisé)
    CacheDomain.GENERAL: 60.0,       # 1 minute
}


@dataclass
class CacheEntry:
    """Entrée de cache avec métadonnées."""
    key: str
    value: Any
    domain: CacheDomain
    created_at: float
    ttl: float
    access_count: int = 0
    last_access: float = 0.0

    @property
    def expired(self) -> bool:
        return (time.monotonic() - self.created_at) > self.ttl

    @property
    def age_s(self) -> float:
        return time.monotonic() - self.created_at


class ContextCache:
    """Cache contextuel intelligent avec TTL par domaine et LRU eviction.

    Thread-safe via threading.Lock pour accès depuis les coroutines
    et les callbacks.
    """

    def __init__(self, max_entries: int = 256):
        self._max = max_entries
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()

        # Stats
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

    @staticmethod
    def _make_key(domain: CacheDomain, key: str) -> str:
        """Crée une clé composite domain:hash."""
        h = hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()[:12]
        return f"{domain.value}:{h}"

    def get(self, key: str, domain: CacheDomain = CacheDomain.GENERAL) -> Optional[Any]:
        """Récupère une valeur du cache.

        Returns:
            Valeur si trouvée et non expirée, None sinon.
        """
        cache_key = self._make_key(domain, key)
        with self._lock:
            entry = self._store.get(cache_key)
            if entry is None:
                self._misses += 1
                return None
            if entry.expired:
                del self._store[cache_key]
                self._expirations += 1
                self._misses += 1
                return None
            # LRU: déplacer en fin
            self._store.move_to_end(cache_key)
            entry.access_count += 1
            entry.last_access = time.monotonic()
            self._hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        domain: CacheDomain = CacheDomain.GENERAL,
        ttl: Optional[float] = None,
    ) -> None:
        """Stocke une valeur dans le cache.

        Args:
            key: Clé de cache.
            value: Valeur à stocker.
            domain: Domaine (détermine le TTL par défaut).
            ttl: TTL override (sinon utilise le TTL du domaine).
        """
        cache_key = self._make_key(domain, key)
        effective_ttl = ttl if ttl is not None else DOMAIN_TTL.get(domain, 60.0)

        entry = CacheEntry(
            key=cache_key,
            value=value,
            domain=domain,
            created_at=time.monotonic(),
            ttl=effective_ttl,
            last_access=time.monotonic(),
        )

        with self._lock:
            if cache_key in self._store:
                del self._store[cache_key]
            self._store[cache_key] = entry
            # Eviction LRU si nécessaire
            while len(self._store) > self._max:
                self._store.popitem(last=False)
                self._evictions += 1

    def has(self, key: str, domain: CacheDomain = CacheDomain.GENERAL) -> bool:
        """Vérifie si une clé existe et n'est pas expirée (sans compter comme hit)."""
        cache_key = self._make_key(domain, key)
        with self._lock:
            entry = self._store.get(cache_key)
            if entry is None:
                return False
            if entry.expired:
                del self._store[cache_key]
                self._expirations += 1
                return False
            return True

    def invalidate(self, key: str, domain: CacheDomain = CacheDomain.GENERAL) -> bool:
        """Invalide une entrée spécifique."""
        cache_key = self._make_key(domain, key)
        with self._lock:
            if cache_key in self._store:
                del self._store[cache_key]
                return True
            return False

    def invalidate_domain(self, domain: CacheDomain) -> int:
        """Invalide toutes les entrées d'un domaine."""
        prefix = f"{domain.value}:"
        with self._lock:
            to_remove = [k for k in self._store if k.startswith(prefix)]
            for k in to_remove:
                del self._store[k]
            return len(to_remove)

    def clear(self) -> None:
        """Vide le cache complet."""
        with self._lock:
            self._store.clear()

    def cleanup_expired(self) -> int:
        """Supprime les entrées expirées. Retourne le nombre supprimé."""
        with self._lock:
            to_remove = [k for k, v in self._store.items() if v.expired]
            for k in to_remove:
                del self._store[k]
                self._expirations += 1
            return len(to_remove)

    @property
    def size(self) -> int:
        return len(self._store)

    def metrics(self) -> dict[str, Any]:
        """Statistiques du cache."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0

        # Comptage par domaine
        domain_counts: dict[str, int] = {}
        with self._lock:
            for entry in self._store.values():
                d = entry.domain.value
                domain_counts[d] = domain_counts.get(d, 0) + 1

        return {
            "size": len(self._store),
            "max_entries": self._max,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(hit_rate, 1),
            "evictions": self._evictions,
            "expirations": self._expirations,
            "by_domain": domain_counts,
        }
