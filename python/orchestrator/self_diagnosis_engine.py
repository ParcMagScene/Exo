"""
EXO v11 — SelfDiagnosisEngine (Auto-diagnostic)
Détecte faiblesses, lenteurs, erreurs récurrentes, instabilités,
dépendances cassées, latences anormales, outils inefficaces.

API:
  diagnose()              → dict
  detect_anomalies()      → dict
  detect_regressions()    → dict
  detect_instabilities()  → dict
  health_check()          → dict
  get_stats()             → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("self_diagnosis")


class SelfDiagnosisEngine:
    """Moteur d'auto-diagnostic EXO v11."""

    def __init__(self, meta_memory, task_memory=None, task_optimizer=None):
        """
        Args:
            meta_memory: MetaMemory instance.
            task_memory: v10 TaskMemory (optional) for task history analysis.
            task_optimizer: v10 TaskOptimizer (optional) for tool stats.
        """
        self._meta = meta_memory
        self._task_memory = task_memory
        self._task_optimizer = task_optimizer
        self._diagnosis_history: list[dict] = []
        self._stats = {
            "diagnoses_run": 0,
            "anomalies_found": 0,
            "regressions_found": 0,
            "instabilities_found": 0,
        }

    def diagnose(self) -> dict:
        """Run full diagnostic across all subsystems."""
        anomalies = self.detect_anomalies()
        regressions = self.detect_regressions()
        instabilities = self.detect_instabilities()

        report = {
            "timestamp": time.time(),
            "anomalies": anomalies,
            "regressions": regressions,
            "instabilities": instabilities,
            "overall_health": self._compute_health(anomalies, regressions, instabilities),
        }
        self._diagnosis_history.append(report)
        if len(self._diagnosis_history) > 100:
            self._diagnosis_history = self._diagnosis_history[-100:]

        self._stats["diagnoses_run"] += 1

        # Persist diagnostic to MetaMemory
        self._meta.meta_add({
            "category": "diagnostic",
            "key": f"full_diagnosis:{int(time.time())}",
            "value": {
                "anomaly_count": len(anomalies.get("anomalies", [])),
                "regression_count": len(regressions.get("regressions", [])),
                "instability_count": len(instabilities.get("instabilities", [])),
                "health": report["overall_health"],
            },
            "source": "self_diagnosis",
            "confidence": 0.9,
            "tags": ["diagnostic"],
        })

        log.info("Diagnosis complete: health=%s, anomalies=%d, regressions=%d, instabilities=%d",
                 report["overall_health"],
                 len(anomalies.get("anomalies", [])),
                 len(regressions.get("regressions", [])),
                 len(instabilities.get("instabilities", [])))
        return report

    def detect_anomalies(self) -> dict:
        """Detect modules with abnormal latency or error rates."""
        anomalies = []

        # Check task optimizer for tool statistics
        if self._task_optimizer:
            stats = self._task_optimizer.get_stats()
            for tool, tool_stats in stats.get("tools", {}).items():
                sr = tool_stats.get("success_rate", 1.0)
                avg_lat = tool_stats.get("avg_latency_s", 0)

                if sr < 0.5:
                    anomalies.append({
                        "module": tool,
                        "type": "low_success_rate",
                        "description": f"Tool {tool} has {sr:.0%} success rate",
                        "severity": "high",
                    })
                elif sr < 0.8:
                    anomalies.append({
                        "module": tool,
                        "type": "moderate_success_rate",
                        "description": f"Tool {tool} has {sr:.0%} success rate",
                        "severity": "medium",
                    })

                if avg_lat > 5.0:
                    anomalies.append({
                        "module": tool,
                        "type": "high_latency",
                        "description": f"Tool {tool} avg latency {avg_lat:.1f}s",
                        "severity": "high" if avg_lat > 10 else "medium",
                    })

        # Check task memory for recurring failures
        if self._task_memory:
            tasks = self._task_memory.list_tasks(limit=50, status_filter="failed")
            if len(tasks) >= 5:
                anomalies.append({
                    "module": "task_execution",
                    "type": "recurring_failures",
                    "description": f"{len(tasks)} recent task failures",
                    "severity": "high",
                })

        self._stats["anomalies_found"] += len(anomalies)
        return {"anomalies": anomalies, "count": len(anomalies)}

    def detect_regressions(self) -> dict:
        """Detect performance regressions by comparing recent vs. older metrics."""
        regressions = []

        # Compare recent optimizations with older ones
        opt_entries = self._meta.list_entries("optimization", limit=50)
        if len(opt_entries) >= 10:
            recent = opt_entries[:5]
            older = opt_entries[5:10]

            recent_improvements = sum(
                len(e.get("value", {}).get("improvements", []))
                if isinstance(e.get("value"), dict) else 0
                for e in recent
            )
            older_improvements = sum(
                len(e.get("value", {}).get("improvements", []))
                if isinstance(e.get("value"), dict) else 0
                for e in older
            )

            if recent_improvements > older_improvements * 2 and older_improvements > 0:
                regressions.append({
                    "type": "optimization_spike",
                    "description": (
                        f"Recent optimization runs found {recent_improvements} improvements "
                        f"vs {older_improvements} previously — possible regression"
                    ),
                    "severity": "medium",
                })

        # Check diagnostic history for worsening health
        if len(self._diagnosis_history) >= 3:
            recent_health = [
                d.get("overall_health", "unknown")
                for d in self._diagnosis_history[-3:]
            ]
            if all(h in ("degraded", "critical") for h in recent_health):
                regressions.append({
                    "type": "persistent_degradation",
                    "description": "Last 3 diagnoses show degraded/critical health",
                    "severity": "high",
                })

        self._stats["regressions_found"] += len(regressions)
        return {"regressions": regressions, "count": len(regressions)}

    def detect_instabilities(self) -> dict:
        """Detect unstable modules or services."""
        instabilities = []

        # Check for flip-flopping tool success rates
        if self._task_optimizer:
            stats = self._task_optimizer.get_stats()
            for tool, tool_stats in stats.get("tools", {}).items():
                sr = tool_stats.get("success_rate", 1.0)
                count = tool_stats.get("total", 0)
                if count >= 5 and 0.3 < sr < 0.7:
                    instabilities.append({
                        "module": tool,
                        "type": "unstable_tool",
                        "description": (
                            f"Tool {tool} success rate {sr:.0%} over {count} runs — "
                            f"inconsistent behavior"
                        ),
                        "severity": "medium",
                    })

        # Check for error patterns in meta_memory
        error_entries = self._meta.meta_get("task_failure")
        if len(error_entries) >= 3:
            # Group by error type
            error_types: dict[str, int] = {}
            for e in error_entries:
                val = e.get("value", {})
                err = val.get("error", "unknown") if isinstance(val, dict) else "unknown"
                error_types[err[:50]] = error_types.get(err[:50], 0) + 1
            for err_type, count in error_types.items():
                if count >= 3:
                    instabilities.append({
                        "module": "error_pattern",
                        "type": "recurring_error",
                        "description": f"Error '{err_type}' occurred {count} times",
                        "severity": "high" if count >= 5 else "medium",
                    })

        self._stats["instabilities_found"] += len(instabilities)
        return {"instabilities": instabilities, "count": len(instabilities)}

    def _compute_health(self, anomalies: dict, regressions: dict,
                        instabilities: dict) -> str:
        """Compute overall health: healthy, degraded, critical."""
        total_issues = (
            anomalies.get("count", 0)
            + regressions.get("count", 0)
            + instabilities.get("count", 0)
        )
        high_severity = sum(
            1 for items_list in (
                anomalies.get("anomalies", []),
                regressions.get("regressions", []),
                instabilities.get("instabilities", []),
            )
            for item in items_list
            if item.get("severity") == "high"
        )
        if high_severity >= 2 or total_issues >= 5:
            return "critical"
        if total_issues >= 2:
            return "degraded"
        return "healthy"

    def health_check(self) -> dict:
        """Quick health check (v9 compatible)."""
        return {
            "status": "up",
            "diagnoses_run": self._stats["diagnoses_run"],
            "last_health": (
                self._diagnosis_history[-1].get("overall_health", "unknown")
                if self._diagnosis_history else "not_yet_run"
            ),
        }

    def get_stats(self) -> dict:
        return dict(self._stats)

    def get_history(self, limit: int = 20) -> list[dict]:
        return self._diagnosis_history[-limit:]
