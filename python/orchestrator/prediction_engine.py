"""
EXO v13 — PredictionEngine (Prévision)
Prédit les états futurs, besoins utilisateur, routines et risques
à partir de l'historique, des patterns temporels et des préférences.

API:
  predict_user_need()        → dict
  predict_domotic_state()    → dict
  predict_network_state()    → dict
  predict_routine()          → dict
  health_check()             → dict
  restart()                  → None
  get_stats()                → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("prediction_engine")


class PredictionEngine:
    """Moteur de prévision EXO v13."""

    def __init__(self, meta_memory, governance=None):
        self._memory = meta_memory
        self._governance = governance
        self._history: list[dict] = []
        self._stats = {
            "user_need_predictions": 0,
            "domotic_predictions": 0,
            "network_predictions": 0,
            "routine_predictions": 0,
        }

    # ── predict_user_need ───────────────────────────────────
    def predict_user_need(self) -> dict:
        """Predict probable user needs based on patterns and history."""
        predictions: list[dict] = []

        # 1. Check time-based patterns
        current_hour = time.localtime().tm_hour
        time_patterns = self._get_time_patterns(current_hour)
        predictions.extend(time_patterns)

        # 2. Check recent activity patterns
        recent = self._get_recent_patterns("user_need")
        predictions.extend(recent)

        # 3. Check learned preferences
        prefs = self._get_preferences()
        predictions.extend(prefs)

        # Sort by confidence
        predictions.sort(key=lambda p: p.get("confidence", 0), reverse=True)

        self._stats["user_need_predictions"] += 1

        result = {
            "type": "user_need_prediction",
            "predictions": predictions[:10],
            "prediction_count": len(predictions),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── predict_domotic_state ───────────────────────────────
    def predict_domotic_state(self) -> dict:
        """Predict future domotic device states."""
        predictions: list[dict] = []

        # Time-based domotic patterns
        current_hour = time.localtime().tm_hour
        patterns = self._get_domotic_patterns(current_hour)
        predictions.extend(patterns)

        # Historical device patterns
        device_patterns = self._get_device_patterns()
        predictions.extend(device_patterns)

        predictions.sort(key=lambda p: p.get("confidence", 0), reverse=True)

        self._stats["domotic_predictions"] += 1

        result = {
            "type": "domotic_prediction",
            "predictions": predictions[:10],
            "prediction_count": len(predictions),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── predict_network_state ───────────────────────────────
    def predict_network_state(self) -> dict:
        """Predict future network state based on patterns."""
        predictions: list[dict] = []

        # Check network patterns from memory
        net_patterns = self._memory.meta_get("network")
        for entry in net_patterns[:5]:
            predictions.append({
                "source": "memory",
                "key": entry.get("key", ""),
                "predicted_state": entry.get("value"),
                "confidence": entry.get("confidence", 0.5),
            })

        # Time-based network patterns
        current_hour = time.localtime().tm_hour
        if 0 <= current_hour < 6:
            predictions.append({
                "source": "time_pattern",
                "key": "bandwidth",
                "predicted_state": "low_usage",
                "confidence": 0.7,
            })
        elif 18 <= current_hour < 23:
            predictions.append({
                "source": "time_pattern",
                "key": "bandwidth",
                "predicted_state": "high_usage",
                "confidence": 0.6,
            })

        predictions.sort(key=lambda p: p.get("confidence", 0), reverse=True)

        self._stats["network_predictions"] += 1

        result = {
            "type": "network_prediction",
            "predictions": predictions[:10],
            "prediction_count": len(predictions),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── predict_routine ─────────────────────────────────────
    def predict_routine(self) -> dict:
        """Predict next likely routine based on time and patterns."""
        predictions: list[dict] = []

        # Check routine patterns from memory
        routines = self._memory.meta_get("routine")
        for entry in routines[:5]:
            predictions.append({
                "source": "memory",
                "routine": entry.get("key", ""),
                "details": entry.get("value"),
                "confidence": entry.get("confidence", 0.5),
            })

        # Time-based routine defaults
        current_hour = time.localtime().tm_hour
        if 6 <= current_hour < 9:
            predictions.append({
                "source": "time_pattern",
                "routine": "morning_routine",
                "details": {"actions": ["lights_on", "coffee", "news"]},
                "confidence": 0.6,
            })
        elif 22 <= current_hour or current_hour < 1:
            predictions.append({
                "source": "time_pattern",
                "routine": "night_routine",
                "details": {"actions": ["lights_off", "lock_doors", "alarm_on"]},
                "confidence": 0.6,
            })

        predictions.sort(key=lambda p: p.get("confidence", 0), reverse=True)

        self._stats["routine_predictions"] += 1

        result = {
            "type": "routine_prediction",
            "predictions": predictions[:10],
            "prediction_count": len(predictions),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── health_check / restart / stats ──────────────────────
    def health_check(self) -> dict:
        return {
            "service": "prediction_engine",
            "status": "ok",
            "history_size": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("PredictionEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── private ─────────────────────────────────────────────
    def _get_time_patterns(self, hour: int) -> list[dict]:
        """Derive user-need predictions from time of day."""
        preds = []
        if 6 <= hour < 9:
            preds.append({
                "source": "time_pattern",
                "need": "morning_briefing",
                "description": "Résumé matinal (météo, agenda, nouvelles)",
                "confidence": 0.7,
            })
        elif 12 <= hour < 14:
            preds.append({
                "source": "time_pattern",
                "need": "lunch_break",
                "description": "Pause déjeuner — musique, recettes",
                "confidence": 0.5,
            })
        elif 18 <= hour < 20:
            preds.append({
                "source": "time_pattern",
                "need": "evening_routine",
                "description": "Retour maison — éclairage, chauffage",
                "confidence": 0.65,
            })
        return preds

    def _get_recent_patterns(self, category: str) -> list[dict]:
        entries = self._memory.meta_get(category)
        preds = []
        for e in entries[:5]:
            preds.append({
                "source": "recent_pattern",
                "need": e.get("key", ""),
                "description": str(e.get("value", "")),
                "confidence": e.get("confidence", 0.4),
            })
        return preds

    def _get_preferences(self) -> list[dict]:
        entries = self._memory.meta_get("preference")
        preds = []
        for e in entries[:5]:
            preds.append({
                "source": "preference",
                "need": e.get("key", ""),
                "description": str(e.get("value", "")),
                "confidence": e.get("confidence", 0.5),
            })
        return preds

    def _get_domotic_patterns(self, hour: int) -> list[dict]:
        preds = []
        if 6 <= hour < 8:
            preds.append({
                "source": "time_pattern",
                "device": "lights_bedroom",
                "predicted_state": "on",
                "confidence": 0.7,
            })
        elif 23 <= hour or hour < 5:
            preds.append({
                "source": "time_pattern",
                "device": "lights_all",
                "predicted_state": "off",
                "confidence": 0.8,
            })
        return preds

    def _get_device_patterns(self) -> list[dict]:
        entries = self._memory.meta_get("device")
        preds = []
        for e in entries[:5]:
            preds.append({
                "source": "memory",
                "device": e.get("key", ""),
                "predicted_state": e.get("value"),
                "confidence": e.get("confidence", 0.5),
            })
        return preds

    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 500:
            self._history = self._history[-300:]
