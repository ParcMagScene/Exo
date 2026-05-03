"""
EXO v24 — ObservabilityAggregator
Fusionne toutes les données d'observabilité :
télémétrie, traces, métriques, anomalies, performance.

API:
  aggregate_all()              → dict
  aggregate_by_layer()         → dict
  aggregate_by_agent()         → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("observability_aggregator")


class ObservabilityAggregator:
    """Agrégateur d'observabilité EXO v24."""

    def __init__(self, governance=None, telemetry=None, tracing=None,
                 metrics=None, anomaly=None, performance=None):
        self._governance = governance
        self._telemetry = telemetry
        self._tracing = tracing
        self._metrics = metrics
        self._anomaly = anomaly
        self._performance = performance

        self._aggregations: list[dict] = []
        self._stats = {
            "aggregated_all": 0,
            "aggregated_by_layer": 0,
            "aggregated_by_agent": 0,
        }

    # ── aggregate_all ───────────────────────────────────────
    def aggregate_all(self) -> dict:
        """Fusionner toutes les sources d'observabilité."""
        self._stats["aggregated_all"] += 1

        telemetry_data = {}
        if self._telemetry and hasattr(self._telemetry, "telemetry_snapshot"):
            telemetry_data = self._telemetry.telemetry_snapshot()

        tracing_data = {}
        if self._tracing and hasattr(self._tracing, "trace_export"):
            tracing_data = self._tracing.trace_export()

        metrics_data = {}
        if self._metrics and hasattr(self._metrics, "metrics_compute"):
            metrics_data = self._metrics.metrics_compute()

        anomaly_data = {}
        if self._anomaly and hasattr(self._anomaly, "explain_anomaly"):
            anomaly_data = self._anomaly.explain_anomaly()

        perf_data = {}
        if self._performance and hasattr(self._performance, "analyze_performance"):
            perf_data = self._performance.analyze_performance()

        record = {
            "id": f"agg_{uuid.uuid4().hex[:8]}",
            "aggregated": True,
            "sources": {
                "telemetry": {
                    "total_events": telemetry_data.get("total_events", 0),
                },
                "tracing": {
                    "total_spans": tracing_data.get("total_spans", 0),
                    "active_spans": tracing_data.get("active_spans", 0),
                },
                "metrics": {
                    "metrics_count": metrics_data.get("metrics_count", 0),
                },
                "anomalies": {
                    "count": anomaly_data.get("count", 0),
                },
                "performance": {
                    "overall_status": perf_data.get("overall_status", "unknown"),
                },
            },
            "timestamp": time.time(),
        }
        self._aggregations.append(record)
        self._trim()

        return record

    # ── aggregate_by_layer ──────────────────────────────────
    def aggregate_by_layer(self) -> dict:
        """Agréger les données par couche."""
        self._stats["aggregated_by_layer"] += 1

        layers: dict[str, dict] = {}

        # Utiliser la télémétrie
        if self._telemetry and hasattr(self._telemetry, "telemetry_snapshot"):
            snap = self._telemetry.telemetry_snapshot()
            by_type = snap.get("by_type", {})
            for t, count in by_type.items():
                if t == "layer":
                    layers.setdefault("all_layers", {"events": 0, "anomalies": 0})
                    layers["all_layers"]["events"] += count

        # Utiliser les métriques par couche
        if self._metrics and hasattr(self._metrics, "metrics_compute"):
            comp = self._metrics.metrics_compute()
            for name, data in comp.get("metrics", {}).items():
                if "layer" in name:
                    layers.setdefault(name, {"events": 0, "anomalies": 0})
                    layers[name]["avg"] = data.get("avg", 0)
                    layers[name]["samples"] = data.get("samples", 0)

        return {
            "id": f"abl_{uuid.uuid4().hex[:8]}",
            "aggregated": True,
            "layers_count": len(layers),
            "layers": layers,
            "timestamp": time.time(),
        }

    # ── aggregate_by_agent ──────────────────────────────────
    def aggregate_by_agent(self) -> dict:
        """Agréger les données par agent."""
        self._stats["aggregated_by_agent"] += 1

        agents: dict[str, dict] = {}

        if self._telemetry and hasattr(self._telemetry, "telemetry_snapshot"):
            snap = self._telemetry.telemetry_snapshot()
            by_source = snap.get("by_source", {})
            for src, count in by_source.items():
                agents.setdefault(src, {"events": 0, "anomalies": 0})
                agents[src]["events"] += count

        if self._metrics and hasattr(self._metrics, "metrics_compute"):
            comp = self._metrics.metrics_compute()
            for name, data in comp.get("metrics", {}).items():
                if "agent" in name:
                    agents.setdefault(name, {"events": 0, "anomalies": 0})
                    agents[name]["avg"] = data.get("avg", 0)
                    agents[name]["samples"] = data.get("samples", 0)

        return {
            "id": f"aba_{uuid.uuid4().hex[:8]}",
            "aggregated": True,
            "agents_count": len(agents),
            "agents": agents,
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "observability_aggregator",
            "status": "ok",
            "total_aggregations": len(self._aggregations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._aggregations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ObservabilityAggregator restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._aggregations) > 5000:
            self._aggregations = self._aggregations[-2500:]
