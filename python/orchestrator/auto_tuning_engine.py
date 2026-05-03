"""
EXO v11 — AutoTuningEngine (Auto-réglage)
Ajuste automatiquement les paramètres internes : TTL caches, intervalles
polling, timeouts, stratégies retry, seuils STT/TTS/LLM, priorités CPU.

API:
  tune(parameter, value) → bool
  auto_tune_all()        → dict
  get_tunings()          → dict
  get_stats()            → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("auto_tuning")

# Default parameter ranges (min, default, max)
TUNABLE_PARAMETERS = {
    "cache_ttl_s": (30, 300, 3600),
    "polling_interval_s": (5, 30, 300),
    "timeout_stt_s": (3, 10, 30),
    "timeout_tts_s": (3, 12, 30),
    "timeout_llm_s": (5, 15, 60),
    "retry_max": (0, 3, 5),
    "retry_backoff_s": (0.5, 1.0, 5.0),
    "stt_beam_size": (1, 3, 5),
    "stt_confidence_threshold": (0.3, 0.5, 0.9),
    "tts_rate": (0.8, 1.0, 1.3),
    "llm_max_tokens": (256, 1024, 4096),
    "llm_temperature": (0.0, 0.7, 1.0),
    "cpu_priority": (0, 1, 2),
    "plan_timeout_s": (10, 60, 300),
}


class AutoTuningEngine:
    """Moteur d'auto-réglage EXO v11."""

    def __init__(self, meta_memory, governance=None):
        """
        Args:
            meta_memory: MetaMemory instance.
            governance: AutoGovernance (optional) for permission checks.
        """
        self._memory = meta_memory
        self._governance = governance
        self._current: dict[str, float] = {
            k: v[1] for k, v in TUNABLE_PARAMETERS.items()
        }
        self._history: list[dict] = []
        self._stats = {
            "tunings_applied": 0,
            "tunings_rejected": 0,
            "auto_tune_runs": 0,
        }
        # Load persisted tunings
        self._load_from_memory()

    def _load_from_memory(self) -> None:
        """Load previously saved tunings from MetaMemory."""
        tunings = self._memory.list_entries("tuning", limit=100)
        for entry in tunings:
            key = entry.get("key", "")
            if key.startswith("tuning:"):
                param = key[7:]
                if param in self._current:
                    val = entry.get("value")
                    if isinstance(val, (int, float)):
                        self._current[param] = val

    def tune(self, parameter: str, value: float) -> bool:
        """Set a parameter to a specific value.

        Returns True if applied, False if rejected (out of range or governance).
        """
        if parameter not in TUNABLE_PARAMETERS:
            log.warning("Unknown parameter: %s", parameter)
            return False

        pmin, _, pmax = TUNABLE_PARAMETERS[parameter]
        if not (pmin <= value <= pmax):
            log.warning("Value %s out of range [%s, %s] for %s",
                        value, pmin, pmax, parameter)
            return False

        # Governance check
        if self._governance and not self._governance.check_permission(
                "tune", {"parameter": parameter, "value": value}):
            self._stats["tunings_rejected"] += 1
            log.info("Tuning rejected by governance: %s=%s", parameter, value)
            return False

        old_value = self._current.get(parameter)
        self._current[parameter] = value

        record = {
            "parameter": parameter,
            "old_value": old_value,
            "new_value": value,
            "timestamp": time.time(),
        }
        self._history.append(record)
        if len(self._history) > 200:
            self._history = self._history[-200:]

        # Persist to MetaMemory
        self._memory.meta_add({
            "category": "tuning",
            "key": f"tuning:{parameter}",
            "value": value,
            "source": "auto_tuning",
            "confidence": 0.9,
            "tags": ["tuning", parameter],
        })

        self._stats["tunings_applied"] += 1
        log.info("Tuned %s: %s → %s", parameter, old_value, value)
        return True

    def auto_tune_all(self) -> dict:
        """Automatically adjust parameters based on MetaMemory data."""
        adjustments = []
        self._stats["auto_tune_runs"] += 1

        # Analyze task performance → adjust timeouts
        opt_data = self._memory.meta_get("task_success")
        if opt_data:
            latencies = [
                e.get("value", {}).get("elapsed_s", 0)
                for e in opt_data
                if isinstance(e.get("value"), dict)
            ]
            if latencies:
                avg_lat = sum(latencies) / len(latencies)
                max_lat = max(latencies)

                # If tasks are fast, reduce timeouts
                if avg_lat < 2.0 and self._current["timeout_llm_s"] > 10:
                    new_val = max(8, self._current["timeout_llm_s"] - 2)
                    if self.tune("timeout_llm_s", new_val):
                        adjustments.append({"param": "timeout_llm_s", "new": new_val})

                # If tasks are slow, increase timeouts
                if max_lat > self._current["timeout_llm_s"] * 0.8:
                    new_val = min(60, self._current["timeout_llm_s"] + 5)
                    if self.tune("timeout_llm_s", new_val):
                        adjustments.append({"param": "timeout_llm_s", "new": new_val})

        # Analyze failures → increase retries
        failure_data = self._memory.meta_get("task_failure")
        if len(failure_data) >= 3 and self._current["retry_max"] < 5:
            new_val = min(5, self._current["retry_max"] + 1)
            if self.tune("retry_max", new_val):
                adjustments.append({"param": "retry_max", "new": new_val})

        # Analyze feedback → adjust temperature
        feedback_data = self._memory.meta_get("feedback:negative")
        positive_data = self._memory.meta_get("feedback:positive")
        if len(feedback_data) > len(positive_data) * 2 and len(feedback_data) >= 3:
            # Reduce creativity if too many negative feedbacks
            new_temp = max(0.3, self._current["llm_temperature"] - 0.1)
            if self.tune("llm_temperature", new_temp):
                adjustments.append({"param": "llm_temperature", "new": new_temp})

        log.info("Auto-tune: %d adjustments applied", len(adjustments))
        return {
            "adjustments": adjustments,
            "count": len(adjustments),
            "current_params": dict(self._current),
        }

    def get_tunings(self) -> dict:
        """Get current parameter values."""
        return dict(self._current)

    def get_value(self, parameter: str) -> float | None:
        """Get a single parameter value."""
        return self._current.get(parameter)

    def get_stats(self) -> dict:
        return dict(self._stats)

    def get_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]
