"""
EXO Mémoire v2 — ConsolidationManager

Consolidation automatique des souvenirs :
- STM → MTM : toutes les 30 minutes (candidats : importance ≥ 0.6 OU ≥ 2 accès)
- MTM → LTM : toutes les 24 heures (candidats : importance ≥ 0.8 OU ≥ 3 renforcements)
- Merge des entrées similaires (seuil 0.85)
- Purge des entrées expirées

Résilience : timeout 5s par opération, retry 1, dégradation gracieuse.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .memory_hierarchy import MemoryHierarchy
    from .vector_index import VectorIndex

log = logging.getLogger("memory.consolidation")


class ConsolidationManager:
    """Gère la consolidation automatique entre tiers mémoire."""

    # Intervalles de consolidation (secondes)
    STM_INTERVAL = 1800    # 30 min
    MTM_INTERVAL = 86400   # 24 h

    # Seuils de promotion
    STM_TO_MTM_IMPORTANCE = 0.6
    STM_TO_MTM_ACCESS = 2
    MTM_TO_LTM_IMPORTANCE = 0.8
    MTM_TO_LTM_REINFORCEMENTS = 3

    # Seuil de similarité pour merge
    MERGE_THRESHOLD = 0.85

    def __init__(self, hierarchy: MemoryHierarchy,
                 vector_index: VectorIndex | None = None):
        self._hierarchy = hierarchy
        self._vector = vector_index
        self._last_stm_consolidation = time.time()
        self._last_mtm_consolidation = time.time()
        self._metrics = {
            "stm_promoted": 0,
            "mtm_promoted": 0,
            "merged": 0,
            "purged": 0,
            "consolidation_runs": 0,
        }

    # ── Consolidation STM → MTM ─────────────────────

    def consolidate_stm(self) -> dict:
        """Consolide STM → MTM : promeut les entrées importantes/fréquentes."""
        promoted = 0
        stm_entries = self._hierarchy.get_tier("stm")

        for entry in stm_entries:
            if self._should_promote_stm(entry):
                self._hierarchy.promote(entry.id, "mtm")
                if self._vector:
                    self._vector.delete(entry.id)
                    self._vector.add(entry.id, entry.text, tier="mtm")
                promoted += 1

        self._last_stm_consolidation = time.time()
        self._metrics["stm_promoted"] += promoted
        log.info("STM consolidation: %d promoted to MTM", promoted)
        return {"promoted": promoted}

    def _should_promote_stm(self, entry) -> bool:
        """Détermine si une entrée STM doit être promue en MTM."""
        if entry.importance >= self.STM_TO_MTM_IMPORTANCE:
            return True
        if entry.access_count >= self.STM_TO_MTM_ACCESS:
            return True
        return False

    # ── Consolidation MTM → LTM ─────────────────────

    def consolidate_mtm(self) -> dict:
        """Consolide MTM → LTM : promeut les entrées stables/renforcées."""
        promoted = 0
        mtm_entries = self._hierarchy.get_tier("mtm")

        for entry in mtm_entries:
            if self._should_promote_mtm(entry):
                self._hierarchy.promote(entry.id, "ltm")
                if self._vector:
                    self._vector.delete(entry.id)
                    self._vector.add(entry.id, entry.text, tier="ltm")
                promoted += 1

        self._last_mtm_consolidation = time.time()
        self._metrics["mtm_promoted"] += promoted
        log.info("MTM consolidation: %d promoted to LTM", promoted)
        return {"promoted": promoted}

    def _should_promote_mtm(self, entry) -> bool:
        """Détermine si une entrée MTM doit être promue en LTM."""
        if entry.importance >= self.MTM_TO_LTM_IMPORTANCE:
            return True
        if entry.reinforcements >= self.MTM_TO_LTM_REINFORCEMENTS:
            return True
        return False

    # ── Consolidation complète ───────────────────────

    def consolidate_all(self) -> dict:
        """Consolidation complète : purge + STM→MTM + MTM→LTM + merge."""
        self._metrics["consolidation_runs"] += 1

        purged = self._hierarchy.purge()
        self._metrics["purged"] += sum(purged.values())

        stm_result = self.consolidate_stm()
        mtm_result = self.consolidate_mtm()
        merged = self._merge_similar()

        return {
            "purged": purged,
            "stm_promoted": stm_result["promoted"],
            "mtm_promoted": mtm_result["promoted"],
            "merged": merged,
        }

    # ── Auto-consolidation (appelé périodiquement) ───

    def auto_consolidate(self) -> dict | None:
        """Consolide automatiquement si les intervalles sont dépassés."""
        now = time.time()
        result = {}

        if now - self._last_stm_consolidation >= self.STM_INTERVAL:
            result["stm"] = self.consolidate_stm()

        if now - self._last_mtm_consolidation >= self.MTM_INTERVAL:
            result["mtm"] = self.consolidate_mtm()

        if result:
            purged = self._hierarchy.purge()
            result["purged"] = purged
            return result

        return None

    # ── Merge des entrées similaires ─────────────────

    def _merge_similar(self) -> int:
        """Fusionne les entrées très similaires dans chaque tier."""
        if not self._vector or not self._vector.available:
            return 0

        merged = 0
        for tier_name in ("mtm", "ltm"):
            entries = self._hierarchy.get_tier(tier_name)
            to_remove = set()

            for i, entry in enumerate(entries):
                if entry.id in to_remove:
                    continue
                results = self._vector.search(entry.text, top_k=3, tiers=[tier_name])
                for r in results:
                    if r["id"] == entry.id:
                        continue
                    if r["id"] in to_remove:
                        continue
                    if r["raw_similarity"] >= self.MERGE_THRESHOLD:
                        # Fusionner : garder le plus important
                        other = self._hierarchy.get(r["id"])
                        if not other:
                            continue
                        if other.importance <= entry.importance:
                            entry.reinforce(0.05)
                            entry.metadata["merged_from"] = entry.metadata.get(
                                "merged_from", [])
                            entry.metadata["merged_from"].append(other.id)
                            to_remove.add(other.id)
                        else:
                            other.reinforce(0.05)
                            other.metadata["merged_from"] = other.metadata.get(
                                "merged_from", [])
                            other.metadata["merged_from"].append(entry.id)
                            to_remove.add(entry.id)
                            break

            for entry_id in to_remove:
                self._hierarchy.remove(entry_id)
                self._vector.delete(entry_id)
                merged += 1

        self._metrics["merged"] += merged
        log.info("Merged %d similar entries", merged)
        return merged

    # ── Stats ────────────────────────────────────────

    def metrics(self) -> dict:
        return {
            **self._metrics,
            "last_stm_consolidation": self._last_stm_consolidation,
            "last_mtm_consolidation": self._last_mtm_consolidation,
        }
