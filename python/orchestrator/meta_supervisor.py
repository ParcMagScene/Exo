"""
EXO v11 — MetaSupervisor (Surveillance de l'apprentissage)
Surveille l'apprentissage pour éviter les dérives, applique les limites,
valide les entrées, vérifie la cohérence, et permet le rollback.

API:
  validate_learning(entry)  → bool
  rollback_learning(entry_id) → bool
  enforce_rules()           → dict
  get_drift_report()        → dict
  get_stats()               → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("meta_supervisor")

# Default supervision rules
DEFAULT_RULES = {
    "max_entries_per_category": 500,
    "max_entries_total": 5000,
    "min_confidence": 0.3,
    "max_learning_rate_per_min": 30,
    "forbidden_categories": [],
    "require_source": True,
}


class MetaSupervisor:
    """Superviseur de l'apprentissage EXO v11."""

    def __init__(self, meta_memory, learning_engine=None, governance=None):
        """
        Args:
            meta_memory: MetaMemory instance.
            learning_engine: LearningEngine (optional) to monitor.
            governance: AutoGovernance (optional) for rule source.
        """
        self._memory = meta_memory
        self._learning = learning_engine
        self._governance = governance
        self._rules = dict(DEFAULT_RULES)
        self._recent_learns: list[float] = []
        self._rollback_history: list[dict] = []
        self._alerts: list[dict] = []
        self._stats = {
            "validations": 0,
            "rejections": 0,
            "rollbacks": 0,
            "enforcements": 0,
            "alerts_raised": 0,
        }

    def set_rules(self, rules: dict) -> None:
        """Update supervision rules."""
        self._rules.update(rules)
        log.info("MetaSupervisor rules updated: %s", list(rules.keys()))

    def validate_learning(self, entry: dict) -> bool:
        """Validate a learning entry before it is stored.

        Checks: confidence threshold, rate limit, category limits, source.
        Returns True if valid, False if rejected.
        """
        self._stats["validations"] += 1

        # Check confidence
        confidence = entry.get("confidence", 0.0)
        if confidence < self._rules["min_confidence"]:
            self._reject("low_confidence",
                          f"confidence {confidence} < {self._rules['min_confidence']}",
                          entry)
            return False

        # Check forbidden categories
        category = entry.get("category", "")
        if category in self._rules.get("forbidden_categories", []):
            self._reject("forbidden_category",
                          f"category '{category}' is forbidden", entry)
            return False

        # Check source requirement
        if self._rules["require_source"] and not entry.get("source"):
            self._reject("missing_source", "entry has no source", entry)
            return False

        # Check rate limit
        now = time.time()
        self._recent_learns = [t for t in self._recent_learns if now - t < 60]
        if len(self._recent_learns) >= self._rules["max_learning_rate_per_min"]:
            self._reject("rate_limit",
                          f"rate {len(self._recent_learns)}/min exceeded", entry)
            return False
        self._recent_learns.append(now)

        # Check total entries
        stats = self._memory.get_stats()
        if stats.get("total", 0) >= self._rules["max_entries_total"]:
            self._reject("total_limit",
                          f"total entries {stats['total']} >= {self._rules['max_entries_total']}",
                          entry)
            return False

        # Check category limit
        cat_count = stats.get("by_category", {}).get(category, 0)
        if cat_count >= self._rules["max_entries_per_category"]:
            self._reject("category_limit",
                          f"category '{category}' has {cat_count} entries", entry)
            return False

        return True

    def _reject(self, reason: str, detail: str, entry: dict) -> None:
        """Record a rejection and raise an alert."""
        self._stats["rejections"] += 1
        alert = {
            "type": "learning_rejected",
            "reason": reason,
            "detail": detail,
            "key": entry.get("key", ""),
            "timestamp": time.time(),
        }
        self._alerts.append(alert)
        if len(self._alerts) > 200:
            self._alerts = self._alerts[-200:]
        self._stats["alerts_raised"] += 1
        log.warning("Learning rejected (%s): %s", reason, detail)

    def rollback_learning(self, entry_id: str) -> bool:
        """Remove a learned entry (rollback)."""
        entry = None
        entries = self._memory.list_entries(limit=5000)
        for e in entries:
            if e.get("id") == entry_id:
                entry = e
                break

        if not entry:
            log.warning("Rollback failed: entry %s not found", entry_id)
            return False

        success = self._memory.meta_delete(entry_id)
        if success:
            self._rollback_history.append({
                "entry_id": entry_id,
                "entry": entry,
                "timestamp": time.time(),
            })
            if len(self._rollback_history) > 100:
                self._rollback_history = self._rollback_history[-100:]
            self._stats["rollbacks"] += 1
            log.info("Rolled back entry %s (%s: %s)",
                     entry_id, entry.get("category"), entry.get("key"))
        return success

    def enforce_rules(self) -> dict:
        """Enforce supervision rules on existing MetaMemory content.

        Prunes entries that exceed limits, removes low-confidence entries.
        Returns a report of actions taken.
        """
        self._stats["enforcements"] += 1
        actions = []

        stats = self._memory.get_stats()

        # Remove low-confidence entries
        all_entries = self._memory.list_entries(limit=10000)
        for entry in all_entries:
            conf = entry.get("confidence", 1.0)
            if conf < self._rules["min_confidence"]:
                eid = entry.get("id", "")
                if self._memory.meta_delete(eid):
                    actions.append({
                        "action": "delete_low_confidence",
                        "entry_id": eid,
                        "confidence": conf,
                    })

        # Prune categories over limit
        for cat, count in stats.get("by_category", {}).items():
            limit = self._rules["max_entries_per_category"]
            if count > limit:
                cat_entries = self._memory.list_entries(cat, limit=count)
                # Remove oldest entries beyond limit
                to_remove = cat_entries[limit:]
                for entry in to_remove:
                    eid = entry.get("id", "")
                    if self._memory.meta_delete(eid):
                        actions.append({
                            "action": "prune_category",
                            "category": cat,
                            "entry_id": eid,
                        })

        log.info("Enforce rules: %d actions taken", len(actions))
        return {
            "actions": actions,
            "count": len(actions),
        }

    def get_drift_report(self) -> dict:
        """Generate a drift detection report.

        Checks for: imbalanced categories, suspiciously rapid learning,
        concentration of sources.
        """
        stats = self._memory.get_stats()
        by_cat = stats.get("by_category", {})
        total = stats.get("total", 0)
        warnings = []

        # Category imbalance
        if by_cat and total > 20:
            max_cat = max(by_cat.values()) if by_cat else 0
            if max_cat > total * 0.7:
                dominant = [c for c, n in by_cat.items() if n == max_cat]
                warnings.append({
                    "type": "category_imbalance",
                    "detail": f"category '{dominant[0]}' has {max_cat}/{total} entries",
                })

        # Recent rate
        now = time.time()
        recent = [t for t in self._recent_learns if now - t < 300]
        if len(recent) > 50:
            warnings.append({
                "type": "rapid_learning",
                "detail": f"{len(recent)} learns in last 5 min",
            })

        # Source concentration
        all_entries = self._memory.list_entries(limit=200)
        sources: dict[str, int] = {}
        for e in all_entries:
            src = e.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1
        if sources and len(sources) == 1 and total > 10:
            warnings.append({
                "type": "source_concentration",
                "detail": f"all entries from single source: {list(sources.keys())[0]}",
            })

        return {
            "total_entries": total,
            "by_category": by_cat,
            "warnings": warnings,
            "warning_count": len(warnings),
            "recent_alerts": self._alerts[-10:],
        }

    def get_stats(self) -> dict:
        return dict(self._stats)

    def get_alerts(self, limit: int = 50) -> list[dict]:
        return self._alerts[-limit:]

    def get_rollback_history(self, limit: int = 20) -> list[dict]:
        return self._rollback_history[-limit:]
