"""
EXO Mémoire v2 — FactualMemory

Mémoire factuelle : faits persistants et stables.
- Stockage clé-valeur de faits (préférences, infos utilisateur, etc.)
- Catégorisation (preference, identity, location, technical, general)
- Détection de contradictions
- Historique des modifications (audit trail)

Les faits sont promus en LTM avec importance élevée.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

log = logging.getLogger("memory.factual")


FACT_CATEGORIES = (
    "preference", "identity", "location", "technical", "general",
)


@dataclass
class Fact:
    """Un fait persistant."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    key: str = ""
    value: str = ""
    category: str = "general"
    confidence: float = 1.0
    source: str = "user"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    history: list[dict] = field(default_factory=list)

    def update(self, new_value: str, source: str = "user") -> None:
        """Met à jour la valeur en gardant l'historique."""
        self.history.append({
            "old_value": self.value,
            "new_value": new_value,
            "timestamp": time.time(),
            "source": source,
        })
        self.value = new_value
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "history": list(self.history),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Fact:
        f = cls(
            id=d.get("id", str(uuid.uuid4())[:12]),
            key=d["key"],
            value=d["value"],
            category=d.get("category", "general"),
            confidence=d.get("confidence", 1.0),
            source=d.get("source", "user"),
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
        )
        f.history = d.get("history", [])
        return f


class FactualMemory:
    """Gère les faits persistants de l'utilisateur."""

    MAX_FACTS = 500

    def __init__(self):
        self._facts: dict[str, Fact] = {}  # key → Fact
        self._by_category: dict[str, list[str]] = {
            c: [] for c in FACT_CATEGORIES
        }

    def add_fact(self, key: str, value: str,
                 category: str = "general",
                 source: str = "user",
                 confidence: float = 1.0) -> Fact:
        """Ajoute ou met à jour un fait."""
        if category not in FACT_CATEGORIES:
            category = "general"

        existing = self._facts.get(key)
        if existing:
            # Détection de contradiction
            if existing.value != value:
                log.info("Fact update: '%s' = '%s' → '%s'",
                         key, existing.value, value)
                existing.update(value, source)
                existing.confidence = confidence
            return existing

        fact = Fact(
            key=key,
            value=value,
            category=category,
            confidence=confidence,
            source=source,
        )
        self._facts[key] = fact
        self._by_category.setdefault(category, []).append(key)

        # Capacité
        if len(self._facts) > self.MAX_FACTS:
            self._evict_oldest()

        return fact

    def get_fact(self, key: str) -> Fact | None:
        """Récupère un fait par clé."""
        return self._facts.get(key)

    def get_value(self, key: str, default: str = "") -> str:
        """Raccourci pour récupérer la valeur d'un fait."""
        f = self._facts.get(key)
        return f.value if f else default

    def update_fact(self, key: str, value: str,
                    source: str = "user") -> bool:
        """Met à jour un fait existant."""
        fact = self._facts.get(key)
        if not fact:
            return False
        fact.update(value, source)
        return True

    def delete_fact(self, key: str) -> bool:
        """Supprime un fait."""
        fact = self._facts.pop(key, None)
        if fact:
            cat_list = self._by_category.get(fact.category, [])
            if key in cat_list:
                cat_list.remove(key)
            return True
        return False

    def get_by_category(self, category: str) -> list[Fact]:
        """Récupère tous les faits d'une catégorie."""
        keys = self._by_category.get(category, [])
        return [self._facts[k] for k in keys if k in self._facts]

    def search_facts(self, query: str) -> list[Fact]:
        """Recherche textuelle dans les faits."""
        query_lower = query.lower()
        results = []
        for fact in self._facts.values():
            if (query_lower in fact.key.lower()
                    or query_lower in fact.value.lower()):
                results.append(fact)
        return results

    def detect_contradictions(self, key: str, new_value: str) -> dict | None:
        """Détecte si une mise à jour contredit un fait existant."""
        existing = self._facts.get(key)
        if not existing:
            return None
        if existing.value == new_value:
            return None
        return {
            "key": key,
            "current_value": existing.value,
            "new_value": new_value,
            "confidence": existing.confidence,
            "last_updated": existing.updated_at,
        }

    def all_facts(self) -> list[dict]:
        """Retourne tous les faits comme dicts."""
        return [f.to_dict() for f in self._facts.values()]

    def _evict_oldest(self) -> None:
        """Retire le fait le plus ancien (hors haute confidence)."""
        if not self._facts:
            return
        oldest_key = None
        oldest_time = float("inf")
        for key, fact in self._facts.items():
            if fact.confidence >= 0.9:
                continue
            if fact.updated_at < oldest_time:
                oldest_time = fact.updated_at
                oldest_key = key
        if oldest_key:
            self.delete_fact(oldest_key)

    def export_data(self) -> list[dict]:
        return [f.to_dict() for f in self._facts.values()]

    def import_data(self, data: list[dict]) -> int:
        count = 0
        for d in data:
            fact = Fact.from_dict(d)
            self._facts[fact.key] = fact
            self._by_category.setdefault(fact.category, []).append(fact.key)
            count += 1
        return count

    def stats(self) -> dict:
        categories = {}
        for cat in FACT_CATEGORIES:
            categories[cat] = len(self._by_category.get(cat, []))
        return {
            "total": len(self._facts),
            "categories": categories,
            "max_capacity": self.MAX_FACTS,
        }
