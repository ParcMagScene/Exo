"""
EXO v11 — LearningEngine (Apprentissage contrôlé)
Apprend des interactions, corrections, préférences et patterns.

Sources : feedback utilisateur, succès/échecs, latences, patterns d'usage,
routines, scénarios domotiques, contexte environnemental.

Types : préférences, routines, stratégies, optimisations,
patterns temporels, patterns domotiques, patterns réseau.

API:
  learn(event)                → str  (entry_id)
  learn_preference(key, value) → str
  learn_pattern(pattern)       → str
  learn_strategy(strategy)     → str
  get_learned(category, limit) → list[dict]
  get_stats()                  → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("learning_engine")

# Learning types
LEARNING_TYPES = (
    "preference", "routine", "strategy", "optimization",
    "pattern_temporal", "pattern_domotique", "pattern_reseau",
)


class LearningEngine:
    """Moteur d'apprentissage contrôlé EXO v11."""

    def __init__(self, meta_memory, governance=None):
        """
        Args:
            meta_memory: MetaMemory instance for persistent storage.
            governance: AutoGovernance instance (optional, for permission checks).
        """
        self._memory = meta_memory
        self._governance = governance
        self._session_events: list[dict] = []
        self._stats = {
            "total_learned": 0,
            "rejected": 0,
            "by_type": {},
        }

    def learn(self, event: dict) -> str | None:
        """Learn from a generic event.

        event keys: type, key, value, source, confidence, tags
        Returns entry_id or None if rejected by governance.
        """
        learning_type = event.get("type", "pattern_temporal")

        # Governance check
        if self._governance and not self._governance.check_permission(
                "learn", {"type": learning_type, "key": event.get("key", "")}):
            self._stats["rejected"] += 1
            log.info("Learning rejected by governance: %s", event.get("key", ""))
            return None

        entry = {
            "category": learning_type if learning_type in LEARNING_TYPES else "pattern_temporal",
            "key": event.get("key", ""),
            "value": event.get("value"),
            "source": event.get("source", "observation"),
            "confidence": event.get("confidence", 0.8),
            "tags": event.get("tags", []),
        }
        entry_id = self._memory.meta_add(entry)

        self._session_events.append({
            "entry_id": entry_id,
            "type": learning_type,
            "key": entry["key"],
            "timestamp": time.time(),
        })

        self._stats["total_learned"] += 1
        t = entry["category"]
        self._stats["by_type"][t] = self._stats["by_type"].get(t, 0) + 1

        log.info("Learned: %s = %s (type=%s)", entry["key"], entry["value"], t)
        return entry_id

    def learn_preference(self, key: str, value: Any) -> str | None:
        """Learn a user preference."""
        return self.learn({
            "type": "preference",
            "key": key,
            "value": value,
            "source": "user",
            "confidence": 1.0,
            "tags": ["preference", "user"],
        })

    def learn_pattern(self, pattern: dict) -> str | None:
        """Learn a usage pattern.

        pattern keys: name, description, frequency, context, type
        """
        ptype = pattern.get("type", "pattern_temporal")
        return self.learn({
            "type": ptype,
            "key": pattern.get("name", "unnamed_pattern"),
            "value": {
                "description": pattern.get("description", ""),
                "frequency": pattern.get("frequency", "unknown"),
                "context": pattern.get("context", {}),
            },
            "source": "observation",
            "confidence": pattern.get("confidence", 0.7),
            "tags": ["pattern", ptype],
        })

    def learn_strategy(self, strategy: dict) -> str | None:
        """Learn a strategy (e.g. which tool works best for a task type).

        strategy keys: name, description, success_rate, context
        """
        return self.learn({
            "type": "strategy",
            "key": strategy.get("name", "unnamed_strategy"),
            "value": {
                "description": strategy.get("description", ""),
                "success_rate": strategy.get("success_rate", 0.0),
                "context": strategy.get("context", {}),
            },
            "source": "analysis",
            "confidence": strategy.get("success_rate", 0.7),
            "tags": ["strategy"],
        })

    def learn_from_task_result(self, task: dict) -> str | None:
        """Learn from a completed task (success or failure)."""
        status = task.get("status", "unknown")
        goal = task.get("goal", "")
        elapsed = task.get("elapsed_s", 0)

        if status == "completed":
            return self.learn({
                "type": "optimization",
                "key": f"task_success:{goal[:50]}",
                "value": {"elapsed_s": elapsed, "status": status},
                "source": "task_result",
                "confidence": 0.9,
                "tags": ["task", "success"],
            })
        elif status == "failed":
            error = task.get("error", "")
            return self.learn({
                "type": "strategy",
                "key": f"task_failure:{goal[:50]}",
                "value": {"error": error, "status": status},
                "source": "task_result",
                "confidence": 0.8,
                "tags": ["task", "failure"],
            })
        return None

    def get_learned(self, category: str | None = None,
                    limit: int = 50) -> list[dict]:
        """Get learned entries from MetaMemory."""
        return self._memory.list_entries(category, limit)

    def get_stats(self) -> dict:
        """Return learning statistics."""
        return {
            **self._stats,
            "session_events": len(self._session_events),
            "memory_stats": self._memory.get_stats(),
        }

    def get_session_events(self, limit: int = 50) -> list[dict]:
        """Get recent learning events from this session."""
        return self._session_events[-limit:]
