"""
EXO Mémoire v2 — MemoryHierarchy

Hiérarchie de mémoire à 3 niveaux :
- STM (Short-Term Memory) : 5–30 min, RAM, derniers messages/intentions
- MTM (Mid-Term Memory) : 24h–7 jours, fichier + index, résumés de sessions
- LTM (Long-Term Memory) : permanente, base locale + index, préférences stables

Chaque tier gère ses propres entrées avec purge, TTL, et limites de capacité.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("memory.hierarchy")

# ── Capacités par tier ───────────────────────────────
STM_MAX = 200
MTM_MAX = 2000
LTM_MAX = 10000

# ── TTL par défaut (secondes) ────────────────────────
STM_DEFAULT_TTL = 1800    # 30 minutes
MTM_DEFAULT_TTL = 604800  # 7 jours
LTM_DEFAULT_TTL = 0       # permanent


@dataclass
class MemoryEntry:
    """Entrée mémoire unifiée."""
    id: str
    text: str
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    category: str = ""
    source: str = "user"
    timestamp: float = field(default_factory=time.time)
    ttl_seconds: float = 0.0
    access_count: int = 0
    last_accessed: float = 0.0
    reinforcements: int = 0
    tier: str = "stm"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.last_accessed == 0.0:
            self.last_accessed = self.timestamp
        self.importance = max(0.0, min(1.0, self.importance))

    def is_expired(self) -> bool:
        if self.ttl_seconds <= 0:
            return False
        return (time.time() - self.timestamp) > self.ttl_seconds

    def age_seconds(self) -> float:
        return time.time() - self.timestamp

    def age_days(self) -> float:
        return self.age_seconds() / 86400

    def touch(self) -> None:
        self.access_count += 1
        self.last_accessed = time.time()

    def reinforce(self, boost: float = 0.1) -> None:
        self.importance = min(1.0, self.importance + boost)
        self.reinforcements += 1
        self.touch()

    def weaken(self, decay: float = 0.1) -> None:
        self.importance = max(0.0, self.importance - decay)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "importance": self.importance,
            "tags": list(self.tags),
            "category": self.category,
            "source": self.source,
            "timestamp": self.timestamp,
            "ttl_seconds": self.ttl_seconds,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "reinforcements": self.reinforcements,
            "tier": self.tier,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict) -> MemoryEntry:
        # Compat v8: ttl_days → ttl_seconds
        ttl = d.get("ttl_seconds", 0.0)
        if ttl == 0.0 and d.get("ttl_days", 0.0) > 0:
            ttl = d["ttl_days"] * 86400
        entry = cls(
            id=d["id"],
            text=d["text"],
            importance=d.get("importance", 0.5),
            tags=d.get("tags", []),
            category=d.get("category", ""),
            source=d.get("source", "user"),
            timestamp=d.get("timestamp", time.time()),
            ttl_seconds=ttl,
            tier=d.get("tier", "stm"),
            metadata=d.get("metadata", {}),
        )
        entry.access_count = d.get("access_count", 0)
        entry.last_accessed = d.get("last_accessed", entry.timestamp)
        entry.reinforcements = d.get("reinforcements", 0)
        return entry


class MemoryHierarchy:
    """Gestionnaire de la hiérarchie mémoire STM/MTM/LTM.

    Gère le stockage, la purge, les limites de capacité, et l'accès
    unifié aux trois tiers.
    """

    TIERS = ("stm", "mtm", "ltm")
    TIER_MAX = {"stm": STM_MAX, "mtm": MTM_MAX, "ltm": LTM_MAX}
    TIER_DEFAULT_TTL = {
        "stm": STM_DEFAULT_TTL,
        "mtm": MTM_DEFAULT_TTL,
        "ltm": LTM_DEFAULT_TTL,
    }

    def __init__(self):
        self._tiers: dict[str, list[MemoryEntry]] = {
            "stm": [], "mtm": [], "ltm": [],
        }
        self._metrics = {
            "stm_adds": 0, "mtm_adds": 0, "ltm_adds": 0,
            "stm_purged": 0, "mtm_purged": 0, "ltm_purged": 0,
            "promotions": 0,
        }

    # ── STM ──────────────────────────────────────────

    def stm_get(self, key: str) -> MemoryEntry | None:
        """Cherche dans STM par ID."""
        for e in self._tiers["stm"]:
            if e.id == key:
                e.touch()
                return e
        return None

    def stm_set(self, entry: MemoryEntry) -> None:
        """Ajoute/remplace dans STM."""
        entry.tier = "stm"
        if not entry.ttl_seconds:
            entry.ttl_seconds = self.TIER_DEFAULT_TTL["stm"]
        # Remplacer si même ID
        self._tiers["stm"] = [e for e in self._tiers["stm"] if e.id != entry.id]
        self._tiers["stm"].append(entry)
        self._metrics["stm_adds"] += 1
        self._enforce_capacity("stm")

    # ── MTM ──────────────────────────────────────────

    def mtm_get(self, key: str) -> MemoryEntry | None:
        """Cherche dans MTM par ID."""
        for e in self._tiers["mtm"]:
            if e.id == key:
                e.touch()
                return e
        return None

    def mtm_add(self, entry: MemoryEntry) -> None:
        """Ajoute dans MTM."""
        entry.tier = "mtm"
        if not entry.ttl_seconds:
            entry.ttl_seconds = self.TIER_DEFAULT_TTL["mtm"]
        self._tiers["mtm"] = [e for e in self._tiers["mtm"] if e.id != entry.id]
        self._tiers["mtm"].append(entry)
        self._metrics["mtm_adds"] += 1
        self._enforce_capacity("mtm")

    # ── LTM ──────────────────────────────────────────

    def ltm_get(self, key: str) -> MemoryEntry | None:
        """Cherche dans LTM par ID."""
        for e in self._tiers["ltm"]:
            if e.id == key:
                e.touch()
                return e
        return None

    def ltm_add(self, entry: MemoryEntry) -> None:
        """Ajoute dans LTM."""
        entry.tier = "ltm"
        entry.ttl_seconds = 0  # permanent
        self._tiers["ltm"] = [e for e in self._tiers["ltm"] if e.id != entry.id]
        self._tiers["ltm"].append(entry)
        self._metrics["ltm_adds"] += 1
        self._enforce_capacity("ltm")

    # ── Accès générique ──────────────────────────────

    def get(self, entry_id: str) -> MemoryEntry | None:
        """Cherche dans tous les tiers."""
        for tier in self.TIERS:
            for e in self._tiers[tier]:
                if e.id == entry_id:
                    e.touch()
                    return e
        return None

    def add(self, entry: MemoryEntry) -> None:
        """Ajoute dans le tier approprié."""
        tier = entry.tier if entry.tier in self.TIERS else "stm"
        if tier == "stm":
            self.stm_set(entry)
        elif tier == "mtm":
            self.mtm_add(entry)
        else:
            self.ltm_add(entry)

    def remove(self, entry_id: str) -> bool:
        """Supprime une entrée par ID."""
        for tier in self.TIERS:
            for i, e in enumerate(self._tiers[tier]):
                if e.id == entry_id:
                    self._tiers[tier].pop(i)
                    return True
        return False

    def get_tier(self, tier: str) -> list[MemoryEntry]:
        """Retourne toutes les entrées d'un tier."""
        return list(self._tiers.get(tier, []))

    def get_all(self) -> list[MemoryEntry]:
        """Retourne toutes les entrées de tous les tiers."""
        result = []
        for tier in self.TIERS:
            result.extend(self._tiers[tier])
        return result

    # ── Promotion ────────────────────────────────────

    def promote(self, entry_id: str, target_tier: str) -> MemoryEntry | None:
        """Promeut une entrée vers un tier supérieur."""
        if target_tier not in self.TIERS:
            return None
        entry = self.get(entry_id)
        if not entry:
            return None
        old_tier = entry.tier
        if old_tier == target_tier:
            return entry
        # Retirer de l'ancien tier
        self._tiers[old_tier] = [e for e in self._tiers[old_tier] if e.id != entry_id]
        # Ajouter au nouveau
        entry.tier = target_tier
        if target_tier == "ltm":
            entry.ttl_seconds = 0
        elif target_tier == "mtm":
            entry.ttl_seconds = self.TIER_DEFAULT_TTL["mtm"]
        self._tiers[target_tier].append(entry)
        self._metrics["promotions"] += 1
        self._enforce_capacity(target_tier)
        log.info("Promoted %s: %s → %s", entry_id[:8], old_tier, target_tier)
        return entry

    # ── Purge & Capacité ─────────────────────────────

    def purge(self) -> dict[str, int]:
        """Purge les entrées expirées de tous les tiers."""
        purged = {}
        for tier in self.TIERS:
            before = len(self._tiers[tier])
            self._tiers[tier] = [e for e in self._tiers[tier] if not e.is_expired()]
            n = before - len(self._tiers[tier])
            purged[tier] = n
            self._metrics[f"{tier}_purged"] += n
        log.info("Purged: STM=%d MTM=%d LTM=%d", purged["stm"], purged["mtm"], purged["ltm"])
        return purged

    def _enforce_capacity(self, tier: str) -> None:
        """Éviction des entrées les moins importantes si capacité dépassée."""
        max_cap = self.TIER_MAX.get(tier, STM_MAX)
        while len(self._tiers[tier]) > max_cap:
            self._evict_one(tier)

    def _evict_one(self, tier: str) -> None:
        """Retire l'entrée la moins pertinente du tier."""
        mems = self._tiers[tier]
        if not mems:
            return
        now = time.time()
        worst_idx = 0
        worst_score = float("inf")
        for i, m in enumerate(mems):
            recency = 1.0 / (1.0 + m.age_days() / 30.0)
            score = m.importance * recency
            if score < worst_score:
                worst_score = score
                worst_idx = i
        mems.pop(worst_idx)

    # ── Stats ────────────────────────────────────────

    def tier_stats(self) -> dict:
        result = {}
        for tier in self.TIERS:
            mems = self._tiers[tier]
            result[tier] = {
                "count": len(mems),
                "avg_importance": (
                    sum(m.importance for m in mems) / len(mems) if mems else 0.0
                ),
                "max_capacity": self.TIER_MAX[tier],
            }
        result["total"] = sum(len(self._tiers[t]) for t in self.TIERS)
        return result

    def metrics(self) -> dict:
        return dict(self._metrics)

    # ── Serialization ────────────────────────────────

    def export_data(self) -> dict:
        """Exporte toutes les données pour persistance."""
        return {
            tier: [e.to_dict() for e in self._tiers[tier]]
            for tier in self.TIERS
        }

    def import_data(self, data: dict) -> int:
        """Importe des données depuis un export."""
        total = 0
        for tier in self.TIERS:
            entries = data.get(tier, [])
            self._tiers[tier] = [MemoryEntry.from_dict(d) for d in entries]
            total += len(self._tiers[tier])
        return total
