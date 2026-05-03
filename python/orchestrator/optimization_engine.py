"""
EXO v11 — OptimizationEngine (Optimisation continue)
Optimise les pipelines, plans HTN, scénarios domotiques, caches, timeouts,
strategies de retry, priorités CPU/GPU basé sur les performances réelles.

API:
  optimize_pipeline()  → dict
  optimize_plans()     → dict
  optimize_domotics()  → dict
  optimize_network()   → dict
  optimize_caches()    → dict
  optimize_all()       → dict
  get_stats()          → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("optimization_engine")


class OptimizationEngine:
    """Moteur d'optimisation continue EXO v11."""

    def __init__(self, meta_memory, diagnosis_engine=None):
        """
        Args:
            meta_memory: MetaMemory instance.
            diagnosis_engine: SelfDiagnosisEngine (optional) for anomaly data.
        """
        self._memory = meta_memory
        self._diagnosis = diagnosis_engine
        self._history: list[dict] = []
        self._stats = {
            "optimizations_run": 0,
            "improvements_found": 0,
            "by_domain": {},
        }

    def _record(self, domain: str, improvements: list[dict]) -> dict:
        """Record an optimization run."""
        record = {
            "domain": domain,
            "timestamp": time.time(),
            "improvements": improvements,
            "count": len(improvements),
        }
        self._history.append(record)
        if len(self._history) > 200:
            self._history = self._history[-200:]

        self._stats["optimizations_run"] += 1
        self._stats["improvements_found"] += len(improvements)
        self._stats["by_domain"][domain] = (
            self._stats["by_domain"].get(domain, 0) + 1
        )

        # Persist optimizations to MetaMemory
        for imp in improvements:
            self._memory.meta_add({
                "category": "optimization",
                "key": f"opt:{domain}:{imp.get('parameter', 'unknown')}",
                "value": imp,
                "source": "optimization_engine",
                "confidence": imp.get("confidence", 0.7),
                "tags": ["optimization", domain],
            })

        log.info("Optimization %s: %d improvements", domain, len(improvements))
        return record

    def optimize_pipeline(self) -> dict:
        """Optimize STT/LLM/TTS pipeline parameters."""
        improvements = []

        # Analyze latency patterns from meta_memory
        latency_data = self._memory.meta_get("task_success")
        if latency_data:
            avg_latency = sum(
                e.get("value", {}).get("elapsed_s", 0) for e in latency_data
            ) / max(len(latency_data), 1)

            if avg_latency > 3.0:
                improvements.append({
                    "parameter": "llm_max_tokens",
                    "suggestion": "reduce",
                    "reason": f"avg latency {avg_latency:.1f}s > 3s threshold",
                    "confidence": 0.8,
                })
            if avg_latency > 5.0:
                improvements.append({
                    "parameter": "stt_beam_size",
                    "suggestion": "reduce to 1",
                    "reason": f"high avg latency {avg_latency:.1f}s",
                    "confidence": 0.7,
                })

        # Check diagnosis if available
        if self._diagnosis:
            anomalies = self._diagnosis.detect_anomalies()
            for a in anomalies.get("anomalies", []):
                if a.get("module") in ("stt", "tts", "llm"):
                    improvements.append({
                        "parameter": f"{a['module']}_config",
                        "suggestion": "review",
                        "reason": a.get("description", "anomaly detected"),
                        "confidence": 0.6,
                    })

        return self._record("pipeline", improvements)

    def optimize_plans(self) -> dict:
        """Optimize HTN plan strategies based on execution history."""
        improvements = []

        # Find failing strategies
        failures = self._memory.meta_get("task_failure")
        if len(failures) >= 3:
            improvements.append({
                "parameter": "plan_timeout",
                "suggestion": "increase",
                "reason": f"{len(failures)} recent task failures detected",
                "confidence": 0.7,
            })

        # Check for tool-specific patterns
        strategies = self._memory.list_entries("strategy", limit=50)
        tool_failures: dict[str, int] = {}
        for s in strategies:
            val = s.get("value", {})
            if isinstance(val, dict) and val.get("feedback_type") == "negative":
                ctx = s.get("key", "")
                tool_failures[ctx] = tool_failures.get(ctx, 0) + 1

        for tool, count in tool_failures.items():
            if count >= 2:
                improvements.append({
                    "parameter": f"tool_strategy:{tool}",
                    "suggestion": "use_alternative",
                    "reason": f"{count} negative feedbacks for {tool}",
                    "confidence": 0.75,
                })

        return self._record("plans", improvements)

    def optimize_domotics(self) -> dict:
        """Optimize home automation timings and polling."""
        improvements = []

        patterns = self._memory.meta_get("pattern_domotique")
        if patterns:
            improvements.append({
                "parameter": "domotics_polling_interval",
                "suggestion": "adaptive",
                "reason": f"{len(patterns)} domotique patterns available",
                "confidence": 0.6,
            })

        return self._record("domotics", improvements)

    def optimize_network(self) -> dict:
        """Optimize network scanning and polling."""
        improvements = []

        patterns = self._memory.meta_get("pattern_reseau")
        if patterns:
            improvements.append({
                "parameter": "network_scan_interval",
                "suggestion": "adaptive",
                "reason": f"{len(patterns)} network patterns available",
                "confidence": 0.6,
            })

        return self._record("network", improvements)

    def optimize_caches(self) -> dict:
        """Optimize cache TTLs based on usage patterns."""
        improvements = []

        pref_data = self._memory.list_entries("preference", limit=100)
        if len(pref_data) > 20:
            improvements.append({
                "parameter": "preference_cache_ttl",
                "suggestion": "increase",
                "reason": f"{len(pref_data)} preferences → higher cache hit likely",
                "confidence": 0.7,
            })

        return self._record("caches", improvements)

    def optimize_all(self) -> dict:
        """Run all optimizations."""
        return {
            "pipeline": self.optimize_pipeline(),
            "plans": self.optimize_plans(),
            "domotics": self.optimize_domotics(),
            "network": self.optimize_network(),
            "caches": self.optimize_caches(),
        }

    def get_stats(self) -> dict:
        return dict(self._stats)

    def get_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]
