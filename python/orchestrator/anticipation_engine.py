"""
EXO v13 — AnticipationEngine (Anticipation contrôlée)
Anticipe les besoins utilisateur sans jamais agir sans validation.
Propose des suggestions, pré-prépare des scénarios, pré-charge du contexte.

API:
  anticipate_need()            → dict
  propose_anticipation()       → dict
  prepare_future_context()     → dict
  get_stats()                  → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("anticipation_engine")


class AnticipationEngine:
    """Moteur d'anticipation contrôlée EXO v13."""

    def __init__(self, meta_memory, prediction_engine=None,
                 governance=None):
        self._memory = meta_memory
        self._prediction = prediction_engine
        self._governance = governance
        self._suggestions: list[dict] = []
        self._history: list[dict] = []
        self._stats = {
            "needs_anticipated": 0,
            "anticipations_proposed": 0,
            "contexts_prepared": 0,
            "suggestions_blocked": 0,
        }

    # ── anticipate_need ─────────────────────────────────────
    def anticipate_need(self) -> dict:
        """Anticipate user needs based on predictions and memory.

        Returns anticipated needs ranked by confidence. Never acts —
        only suggests.
        """
        anticipated: list[dict] = []

        # Use PredictionEngine if available
        if self._prediction:
            pred = self._prediction.predict_user_need()
            for p in pred.get("predictions", []):
                need = {
                    "source": "prediction",
                    "need": p.get("need", p.get("key", "")),
                    "description": p.get("description", ""),
                    "confidence": p.get("confidence", 0.5),
                    "actionable": True,
                }
                anticipated.append(need)

        # Check MetaMemory for anticipation patterns
        patterns = self._memory.meta_get("anticipation")
        for entry in patterns[:5]:
            anticipated.append({
                "source": "memory_pattern",
                "need": entry.get("key", ""),
                "description": str(entry.get("value", "")),
                "confidence": entry.get("confidence", 0.4),
                "actionable": True,
            })

        anticipated.sort(key=lambda a: a.get("confidence", 0), reverse=True)

        self._stats["needs_anticipated"] += 1

        result = {
            "type": "anticipated_needs",
            "needs": anticipated[:10],
            "count": len(anticipated),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── propose_anticipation ────────────────────────────────
    def propose_anticipation(self) -> dict:
        """Propose anticipatory actions for user review.

        Combines predictions, routines, and context to produce
        actionable suggestions. User must approve before execution.
        """
        proposals: list[dict] = []

        # Routine-based proposals
        if self._prediction:
            routine = self._prediction.predict_routine()
            for p in routine.get("predictions", []):
                details = p.get("details", {})
                actions = details.get("actions", []) if isinstance(details, dict) else []
                proposals.append({
                    "type": "routine",
                    "routine": p.get("routine", ""),
                    "actions": actions,
                    "confidence": p.get("confidence", 0.5),
                    "requires_approval": True,
                })

        # Domotic-based proposals
        if self._prediction:
            dom = self._prediction.predict_domotic_state()
            for p in dom.get("predictions", []):
                proposals.append({
                    "type": "domotic",
                    "device": p.get("device", ""),
                    "suggested_state": p.get("predicted_state"),
                    "confidence": p.get("confidence", 0.5),
                    "requires_approval": True,
                })

        # Memory-based proposals
        strategies = self._memory.meta_get("strategy")
        for entry in strategies[:3]:
            val = entry.get("value", {})
            if isinstance(val, dict) and val.get("feedback_type") == "positive":
                proposals.append({
                    "type": "learned_strategy",
                    "strategy": entry.get("key", ""),
                    "details": val,
                    "confidence": entry.get("confidence", 0.5),
                    "requires_approval": True,
                })

        self._suggestions = proposals
        self._stats["anticipations_proposed"] += 1

        result = {
            "type": "anticipation_proposals",
            "proposals": proposals[:10],
            "count": len(proposals),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── prepare_future_context ──────────────────────────────
    def prepare_future_context(self) -> dict:
        """Pre-load context that may be needed soon.

        Returns context elements to cache for faster response.
        """
        context_items: list[dict] = []

        # Predicted user needs → context
        if self._prediction:
            needs = self._prediction.predict_user_need()
            for p in needs.get("predictions", [])[:5]:
                context_items.append({
                    "type": "predicted_need",
                    "key": p.get("need", p.get("key", "")),
                    "details": p.get("description", ""),
                    "priority": "high" if p.get("confidence", 0) > 0.7 else "normal",
                })

        # Recent conversation topics
        recent = self._memory.meta_get("conversation")
        for entry in recent[:3]:
            context_items.append({
                "type": "recent_topic",
                "key": entry.get("key", ""),
                "details": str(entry.get("value", "")),
                "priority": "normal",
            })

        # Active routines
        routines = self._memory.meta_get("routine")
        for entry in routines[:3]:
            context_items.append({
                "type": "active_routine",
                "key": entry.get("key", ""),
                "details": entry.get("value"),
                "priority": "low",
            })

        self._stats["contexts_prepared"] += 1

        result = {
            "type": "future_context",
            "items": context_items,
            "item_count": len(context_items),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── stats ───────────────────────────────────────────────
    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── private ─────────────────────────────────────────────
    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 500:
            self._history = self._history[-300:]
