"""
EXO v11 — MetaMemory (Mémoire d'apprentissage)
Stocke les connaissances apprises : préférences, stratégies, patterns,
optimisations, diagnostics, réglages, historiques d'apprentissage.

Persistance JSON dans $EXO_FAISS_DIR/meta_memory.json.

API:
  meta_add(entry)      → str   (id)
  meta_get(query)      → list[dict]
  meta_update(entry_id, updates) → bool
  meta_delete(entry_id) → bool
  list_entries(category, limit) → list[dict]
  get_stats()          → dict
"""

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("meta_memory")

# Categories
CATEGORIES = (
    "preference", "strategy", "pattern", "optimization",
    "diagnostic", "tuning", "feedback", "routine",
)


class MetaMemory:
    """Persistent meta-learning memory store."""

    def __init__(self, persist_dir: str | None = None):
        base = persist_dir or os.environ.get("EXO_FAISS_DIR", r"D:\EXO\faiss\semantic_memory")
        self._path = Path(base) / "meta_memory.json"
        self._entries: dict[str, dict] = {}
        self._load()

    # ── persistence ──────────────────────────────────────────
    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._entries = data.get("entries", {})
                log.info("MetaMemory loaded %d entries from %s",
                         len(self._entries), self._path)
            except Exception as exc:
                log.warning("MetaMemory load failed: %s", exc)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps({"entries": self._entries}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            log.warning("MetaMemory save failed: %s", exc)

    # ── API ──────────────────────────────────────────────────
    def meta_add(self, entry: dict) -> str:
        """Add a new learning entry. Returns entry_id."""
        entry_id = f"meta_{uuid.uuid4().hex[:8]}"
        record = {
            "id": entry_id,
            "category": entry.get("category", "pattern"),
            "key": entry.get("key", ""),
            "value": entry.get("value"),
            "source": entry.get("source", "system"),
            "confidence": entry.get("confidence", 1.0),
            "created_at": time.time(),
            "updated_at": time.time(),
            "access_count": 0,
            "tags": entry.get("tags", []),
        }
        self._entries[entry_id] = record
        self._save()
        log.info("MetaMemory added %s (%s: %s)",
                 entry_id, record["category"], record["key"])
        return entry_id

    def meta_get(self, query: str) -> list[dict]:
        """Search entries by keyword in key, value, tags."""
        q = query.lower()
        results = []
        for e in self._entries.values():
            if (q in str(e.get("key", "")).lower()
                    or q in str(e.get("value", "")).lower()
                    or any(q in t.lower() for t in e.get("tags", []))):
                e["access_count"] = e.get("access_count", 0) + 1
                results.append(dict(e))
        results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        if results:
            self._save()
        return results

    def meta_update(self, entry_id: str, updates: dict) -> bool:
        """Update an existing entry."""
        if entry_id not in self._entries:
            return False
        entry = self._entries[entry_id]
        for k, v in updates.items():
            if k not in ("id", "created_at"):
                entry[k] = v
        entry["updated_at"] = time.time()
        self._save()
        return True

    def meta_delete(self, entry_id: str) -> bool:
        """Delete an entry."""
        if entry_id not in self._entries:
            return False
        del self._entries[entry_id]
        self._save()
        return True

    def list_entries(self, category: str | None = None,
                     limit: int = 50) -> list[dict]:
        """List entries, optionally filtered by category."""
        entries = list(self._entries.values())
        if category:
            entries = [e for e in entries if e.get("category") == category]
        entries.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        return entries[:limit]

    def get_stats(self) -> dict:
        """Return summary statistics."""
        by_cat: dict[str, int] = {}
        for e in self._entries.values():
            cat = e.get("category", "unknown")
            by_cat[cat] = by_cat.get(cat, 0) + 1
        return {
            "total": len(self._entries),
            "by_category": by_cat,
            "categories": list(by_cat.keys()),
        }

    def get_preferences(self) -> list[dict]:
        """Shortcut: get all preference entries."""
        return self.list_entries("preference", limit=200)

    def get_strategies(self) -> list[dict]:
        """Shortcut: get all strategy entries."""
        return self.list_entries("strategy", limit=200)

    def clear_category(self, category: str) -> int:
        """Remove all entries in a category. Returns count removed."""
        to_del = [eid for eid, e in self._entries.items()
                  if e.get("category") == category]
        for eid in to_del:
            del self._entries[eid]
        if to_del:
            self._save()
        return len(to_del)
