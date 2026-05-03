"""
EXO v11 — FeedbackEngine (Apprentissage utilisateur)
Apprend explicitement de l'utilisateur via feedback positif, négatif,
corrections, préférences, rejets et validations.

API:
  feedback_positive(event) → str
  feedback_negative(event) → str
  feedback_correction(event) → str
  feedback_preference(key, value) → str
  feedback_reject(event) → str
  feedback_validate(event) → str
  get_feedback_history(limit) → list[dict]
  get_stats() → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("feedback_engine")

FEEDBACK_TYPES = ("positive", "negative", "correction", "preference", "reject", "validate")


class FeedbackEngine:
    """Moteur de feedback utilisateur EXO v11."""

    def __init__(self, learning_engine):
        """
        Args:
            learning_engine: LearningEngine instance to propagate learnings.
        """
        self._learning = learning_engine
        self._history: list[dict] = []
        self._stats = {t: 0 for t in FEEDBACK_TYPES}

    def _record(self, fb_type: str, event: dict) -> str | None:
        """Record feedback and learn from it."""
        record = {
            "feedback_type": fb_type,
            "context": event.get("context", ""),
            "detail": event.get("detail", ""),
            "task_id": event.get("task_id", ""),
            "timestamp": time.time(),
        }
        self._history.append(record)
        if len(self._history) > 500:
            self._history = self._history[-500:]

        self._stats[fb_type] = self._stats.get(fb_type, 0) + 1
        log.info("Feedback %s: %s", fb_type, event.get("detail", "")[:80])

        # Propagate to LearningEngine
        entry_id = self._learning.learn({
            "type": "preference" if fb_type == "preference" else "strategy",
            "key": f"feedback:{fb_type}:{event.get('context', 'general')[:40]}",
            "value": {
                "feedback_type": fb_type,
                "detail": event.get("detail", ""),
                "task_id": event.get("task_id", ""),
            },
            "source": "user_feedback",
            "confidence": 1.0 if fb_type in ("correction", "preference") else 0.9,
            "tags": ["feedback", fb_type],
        })
        return entry_id

    def feedback_positive(self, event: dict) -> str | None:
        """Record positive feedback (user liked the result)."""
        return self._record("positive", event)

    def feedback_negative(self, event: dict) -> str | None:
        """Record negative feedback (user disliked the result)."""
        return self._record("negative", event)

    def feedback_correction(self, event: dict) -> str | None:
        """Record a correction (user provides the right answer).

        event should contain: context, detail (correction text), task_id
        """
        return self._record("correction", event)

    def feedback_preference(self, key: str, value: Any) -> str | None:
        """Record an explicit user preference."""
        return self._record("preference", {
            "context": key,
            "detail": str(value),
        })

    def feedback_reject(self, event: dict) -> str | None:
        """Record a rejection (user explicitly rejects a suggestion)."""
        return self._record("reject", event)

    def feedback_validate(self, event: dict) -> str | None:
        """Record a validation (user confirms a suggestion is correct)."""
        return self._record("validate", event)

    def get_feedback_history(self, limit: int = 50) -> list[dict]:
        """Get recent feedback entries."""
        return self._history[-limit:]

    def get_stats(self) -> dict:
        """Return feedback statistics."""
        total = sum(self._stats.values())
        positive_rate = (
            self._stats.get("positive", 0) / total if total > 0 else 0.0
        )
        return {
            "total": total,
            "by_type": dict(self._stats),
            "positive_rate": round(positive_rate, 3),
            "history_size": len(self._history),
        }
