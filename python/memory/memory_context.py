"""
EXO Mémoire v2 — ContextEngine

Moteur de contexte dynamique :
- Fusionne STM + MTM + LTM pour construire un contexte optimal
- Scoring : similarité × importance × récence × poids tier
- Budget tokens configurable (4096 par défaut)
- Injection de contexte dans le prompt LLM

Résilience : timeout 2s, dégradation gracieuse si vectoriel indisponible.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .memory_hierarchy import MemoryEntry, MemoryHierarchy
    from .vector_index import VectorIndex

log = logging.getLogger("memory.context")


class ContextEngine:
    """Construit un contexte dynamique à partir de la hiérarchie mémoire."""

    DEFAULT_TOKEN_BUDGET = 4096
    CHARS_PER_TOKEN = 4  # approximation

    # Poids des tiers dans le scoring
    TIER_WEIGHTS = {"stm": 1.2, "mtm": 1.0, "ltm": 0.9}

    # Fenêtre de récence (secondes)
    RECENCY_HALFLIFE = 3600  # 1 heure

    def __init__(self, hierarchy: MemoryHierarchy,
                 vector_index: VectorIndex | None = None,
                 token_budget: int | None = None):
        self._hierarchy = hierarchy
        self._vector = vector_index
        self._token_budget = token_budget or self.DEFAULT_TOKEN_BUDGET
        self._metrics = {
            "context_builds": 0,
            "total_entries_scored": 0,
            "avg_context_entries": 0.0,
        }

    # ── Construction du contexte ─────────────────────

    def build_context(self, query: str, max_entries: int = 20,
                      tiers: list[str] | None = None) -> list[dict]:
        """Construit un contexte dynamique pour une requête.

        Returns: list[{id, text, score, tier, importance}] trié par score.
        """
        t0 = time.monotonic()
        search_tiers = tiers or ["stm", "mtm", "ltm"]

        # Phase 1 : récupérer les candidats
        candidates = self._gather_candidates(query, search_tiers, max_entries * 3)

        # Phase 2 : scorer
        scored = self._score_candidates(candidates, query)

        # Phase 3 : sélectionner dans le budget
        selected = self._select_within_budget(scored, max_entries)

        self._metrics["context_builds"] += 1
        self._metrics["total_entries_scored"] += len(candidates)
        if self._metrics["context_builds"] > 0:
            prev = self._metrics["avg_context_entries"]
            n = self._metrics["context_builds"]
            self._metrics["avg_context_entries"] = (
                prev * (n - 1) + len(selected)) / n

        elapsed = round((time.monotonic() - t0) * 1000)
        log.debug("Context built: %d entries from %d candidates (%dms)",
                  len(selected), len(candidates), elapsed)
        return selected

    def _gather_candidates(self, query: str, tiers: list[str],
                           max_per_source: int) -> list[dict]:
        """Rassemble les candidats depuis le vectoriel et la hiérarchie."""
        candidates = {}

        # Source 1 : recherche vectorielle
        if self._vector and self._vector.available:
            results = self._vector.search(query, top_k=max_per_source, tiers=tiers)
            for r in results:
                candidates[r["id"]] = {
                    "id": r["id"],
                    "text": r["text"],
                    "similarity": r["raw_similarity"],
                    "tier": r["tier"],
                }

        # Source 2 : entrées récentes de chaque tier
        for tier in tiers:
            entries = self._hierarchy.get_tier(tier)
            # Dernières N entrées par récence
            recent = sorted(entries, key=lambda e: e.last_accessed, reverse=True)
            for entry in recent[:max_per_source // len(tiers)]:
                if entry.id not in candidates:
                    candidates[entry.id] = {
                        "id": entry.id,
                        "text": entry.text,
                        "similarity": 0.3,  # Score par défaut si non vectoriel
                        "tier": entry.tier,
                    }

        # Enrichir avec les données de la hiérarchie
        for cid, cdata in candidates.items():
            entry = self._hierarchy.get(cid)
            if entry:
                cdata["importance"] = entry.importance
                cdata["access_count"] = entry.access_count
                cdata["timestamp"] = entry.timestamp
                cdata["category"] = entry.category
                cdata["tags"] = entry.tags
            else:
                cdata.setdefault("importance", 0.5)
                cdata.setdefault("access_count", 0)
                cdata.setdefault("timestamp", time.time())
                cdata.setdefault("category", "")
                cdata.setdefault("tags", [])

        return list(candidates.values())

    def _score_candidates(self, candidates: list[dict],
                          query: str) -> list[dict]:
        """Score chaque candidat : similarité × importance × récence × tier."""
        now = time.time()

        for c in candidates:
            similarity = c.get("similarity", 0.3)
            importance = c.get("importance", 0.5)
            age = now - c.get("timestamp", now)
            recency = 1.0 / (1.0 + age / self.RECENCY_HALFLIFE)
            tier_w = self.TIER_WEIGHTS.get(c["tier"], 1.0)

            c["score"] = similarity * importance * recency * tier_w

        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates

    def _select_within_budget(self, scored: list[dict],
                              max_entries: int) -> list[dict]:
        """Sélectionne les entrées dans le budget tokens."""
        max_chars = self._token_budget * self.CHARS_PER_TOKEN
        selected = []
        total_chars = 0

        for c in scored:
            text_len = len(c.get("text", ""))
            if total_chars + text_len > max_chars and selected:
                break
            if len(selected) >= max_entries:
                break
            selected.append({
                "id": c["id"],
                "text": c["text"],
                "score": round(c["score"], 4),
                "tier": c["tier"],
                "importance": c.get("importance", 0.5),
                "category": c.get("category", ""),
            })
            total_chars += text_len

        return selected

    # ── Injection dans le prompt LLM ─────────────────

    def inject_context(self, prompt: str, query: str,
                       max_entries: int = 10) -> str:
        """Injecte le contexte mémoire dans un prompt LLM.

        Ajoute une section [MEMORY CONTEXT] avant le prompt.
        """
        context_entries = self.build_context(query, max_entries=max_entries)
        if not context_entries:
            return prompt

        lines = ["[MEMORY CONTEXT]"]
        for entry in context_entries:
            tier_tag = entry["tier"].upper()
            lines.append(f"[{tier_tag}] {entry['text']}")
        lines.append("[/MEMORY CONTEXT]")
        lines.append("")

        return "\n".join(lines) + prompt

    # ── Recherche simple ─────────────────────────────

    def get_relevant_memory(self, query: str,
                            top_k: int = 5) -> list[dict]:
        """Raccourci pour récupérer les souvenirs les plus pertinents."""
        return self.build_context(query, max_entries=top_k)

    # ── Stats ────────────────────────────────────────

    def metrics(self) -> dict:
        return dict(self._metrics)
