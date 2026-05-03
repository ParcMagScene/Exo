"""
EXO v24 — PerformanceAnalysisEngine
Analyse les performances globales et locales d'EXO :
agents, couches, pipelines, simulations, inférences.

API:
  analyze_performance()       → dict
  detect_bottlenecks()        → dict
  propose_improvements()      → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("performance_analysis_engine")


class PerformanceAnalysisEngine:
    """Moteur d'analyse de performance EXO v24."""

    BOTTLENECK_THRESHOLD = 0.8  # latence relative > 80% = goulot

    def __init__(self, governance=None, telemetry=None, metrics=None):
        self._governance = governance
        self._telemetry = telemetry
        self._metrics = metrics

        self._analyses: list[dict] = []
        self._bottlenecks: list[dict] = []
        self._stats = {
            "analyzed": 0,
            "bottlenecks_detected": 0,
            "improvements_proposed": 0,
        }

    # ── analyze_performance ─────────────────────────────────
    def analyze_performance(self) -> dict:
        """Analyser les performances globales."""
        self._stats["analyzed"] += 1

        metrics_data = {}
        if self._metrics and hasattr(self._metrics, "metrics_compute"):
            computed = self._metrics.metrics_compute()
            metrics_data = computed.get("metrics", {})

        analysis = []
        for name, data in metrics_data.items():
            entry = {
                "metric": name,
                "avg": data.get("avg", 0),
                "max": data.get("max", 0),
                "samples": data.get("samples", 0),
                "status": self._classify_metric(name, data),
            }
            analysis.append(entry)

        overall = "healthy"
        warning_count = sum(1 for a in analysis if a["status"] == "warning")
        critical_count = sum(1 for a in analysis if a["status"] == "critical")
        if critical_count > 0:
            overall = "critical"
        elif warning_count > 0:
            overall = "degraded"

        record = {
            "id": f"pa_{uuid.uuid4().hex[:8]}",
            "analyzed": True,
            "overall_status": overall,
            "metrics_analyzed": len(analysis),
            "analysis": analysis,
            "warning_count": warning_count,
            "critical_count": critical_count,
            "timestamp": time.time(),
        }
        self._analyses.append(record)
        self._trim()

        return record

    # ── detect_bottlenecks ──────────────────────────────────
    def detect_bottlenecks(self) -> dict:
        """Détecter les goulots d'étranglement."""
        self._stats["bottlenecks_detected"] += 1

        metrics_data = {}
        if self._metrics and hasattr(self._metrics, "metrics_compute"):
            computed = self._metrics.metrics_compute()
            metrics_data = computed.get("metrics", {})

        bottlenecks = []
        max_latency = 0.0
        for name, data in metrics_data.items():
            if "latency" in name:
                lat = data.get("max", 0)
                if lat > max_latency:
                    max_latency = lat

        if max_latency > 0:
            for name, data in metrics_data.items():
                if "latency" in name:
                    ratio = data.get("max", 0) / max_latency
                    if ratio >= self.BOTTLENECK_THRESHOLD:
                        bottlenecks.append({
                            "metric": name,
                            "value": data.get("max", 0),
                            "ratio": round(ratio, 3),
                            "severity": "high" if ratio > 0.9 else "medium",
                        })

        self._bottlenecks.extend(bottlenecks)
        if len(self._bottlenecks) > 5000:
            self._bottlenecks = self._bottlenecks[-2500:]

        return {
            "id": f"bn_{uuid.uuid4().hex[:8]}",
            "detected": True,
            "count": len(bottlenecks),
            "bottlenecks": bottlenecks,
            "timestamp": time.time(),
        }

    # ── propose_improvements ────────────────────────────────
    def propose_improvements(self) -> dict:
        """Proposer des améliorations basées sur l'analyse."""
        self._stats["improvements_proposed"] += 1

        improvements = []

        if self._analyses:
            latest = self._analyses[-1]
            for entry in latest.get("analysis", []):
                if entry["status"] in ("warning", "critical"):
                    improvements.append({
                        "metric": entry["metric"],
                        "current_status": entry["status"],
                        "suggestion": self._suggest(entry["metric"], entry["status"]),
                        "priority": "high" if entry["status"] == "critical" else "medium",
                    })

        if self._bottlenecks:
            recent = self._bottlenecks[-5:]
            for bn in recent:
                improvements.append({
                    "metric": bn["metric"],
                    "current_status": "bottleneck",
                    "suggestion": f"Optimiser {bn['metric']} (ratio={bn['ratio']})",
                    "priority": "high",
                })

        return {
            "id": f"imp_{uuid.uuid4().hex[:8]}",
            "proposed": True,
            "count": len(improvements),
            "improvements": improvements,
            "timestamp": time.time(),
        }

    # ── internal helpers ────────────────────────────────────
    def _classify_metric(self, name: str, data: dict) -> str:
        avg = data.get("avg", 0)
        if "latency" in name:
            if avg > 2.0:
                return "critical"
            elif avg > 1.0:
                return "warning"
            return "ok"
        if name in ("coherence", "stability", "efficiency"):
            if avg < 0.3:
                return "critical"
            elif avg < 0.6:
                return "warning"
            return "ok"
        if name == "cognitive_load":
            if avg > 0.9:
                return "critical"
            elif avg > 0.7:
                return "warning"
            return "ok"
        return "ok"

    def _suggest(self, metric: str, status: str) -> str:
        suggestions = {
            "latency_agent": "Réduire la complexité des agents ou paralléliser",
            "latency_layer": "Optimiser les couches de traitement",
            "latency_task": "Découper les tâches en sous-tâches plus petites",
            "cognitive_load": "Réduire la charge cognitive via filtrage",
            "coherence": "Renforcer les vérifications de cohérence",
            "stability": "Stabiliser les décisions via lissage",
            "efficiency": "Améliorer le ratio actions/résultats",
        }
        return suggestions.get(metric, f"Investiguer {metric} ({status})")

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "performance_analysis_engine",
            "status": "ok",
            "total_analyses": len(self._analyses),
            "total_bottlenecks": len(self._bottlenecks),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._analyses.clear()
        self._bottlenecks.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("PerformanceAnalysisEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._analyses) > 5000:
            self._analyses = self._analyses[-2500:]
