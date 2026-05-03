"""
EXO v24 — ObservabilityDashboardEngine
Vue synthétique de l'état cognitif EXO :
agents, couches, pipelines, simulations, inférences.

API:
  dashboard_generate()   → dict
  dashboard_export()     → dict
  dashboard_summary()    → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("observability_dashboard_engine")


class ObservabilityDashboardEngine:
    """Tableau de bord d'observabilité EXO v24."""

    def __init__(self, governance=None, aggregator=None):
        self._governance = governance
        self._aggregator = aggregator

        self._dashboards: list[dict] = []
        self._stats = {
            "generated": 0,
            "exported": 0,
            "summaries": 0,
        }

    # ── dashboard_generate ──────────────────────────────────
    def dashboard_generate(self) -> dict:
        """Générer un tableau de bord complet."""
        self._stats["generated"] += 1

        agg_data = {}
        if self._aggregator and hasattr(self._aggregator, "aggregate_all"):
            agg_data = self._aggregator.aggregate_all()

        layer_data = {}
        if self._aggregator and hasattr(self._aggregator, "aggregate_by_layer"):
            layer_data = self._aggregator.aggregate_by_layer()

        agent_data = {}
        if self._aggregator and hasattr(self._aggregator, "aggregate_by_agent"):
            agent_data = self._aggregator.aggregate_by_agent()

        # Calculer le status global
        overall_status = "healthy"
        sources = agg_data.get("sources", {})
        anomaly_count = sources.get("anomalies", {}).get("count", 0)
        perf_status = sources.get("performance", {}).get("overall_status", "ok")

        if anomaly_count > 5 or perf_status == "critical":
            overall_status = "critical"
        elif anomaly_count > 2 or perf_status == "warning":
            overall_status = "warning"

        dashboard = {
            "id": f"dsh_{uuid.uuid4().hex[:8]}",
            "generated": True,
            "overall_status": overall_status,
            "overview": {
                "telemetry_events": sources.get("telemetry", {}).get("total_events", 0),
                "active_spans": sources.get("tracing", {}).get("active_spans", 0),
                "total_spans": sources.get("tracing", {}).get("total_spans", 0),
                "metrics_count": sources.get("metrics", {}).get("metrics_count", 0),
                "anomaly_count": anomaly_count,
                "perf_status": perf_status,
            },
            "layers": {
                "count": layer_data.get("layers_count", 0),
                "details": layer_data.get("layers", {}),
            },
            "agents": {
                "count": agent_data.get("agents_count", 0),
                "details": agent_data.get("agents", {}),
            },
            "timestamp": time.time(),
        }

        self._dashboards.append(dashboard)
        self._trim()

        return dashboard

    # ── dashboard_export ────────────────────────────────────
    def dashboard_export(self) -> dict:
        """Exporter le dernier tableau de bord."""
        self._stats["exported"] += 1

        if not self._dashboards:
            return {
                "id": f"dex_{uuid.uuid4().hex[:8]}",
                "exported": True,
                "has_data": False,
                "dashboards_count": 0,
                "timestamp": time.time(),
            }

        latest = self._dashboards[-1]
        return {
            "id": f"dex_{uuid.uuid4().hex[:8]}",
            "exported": True,
            "has_data": True,
            "dashboards_count": len(self._dashboards),
            "latest": latest,
            "timestamp": time.time(),
        }

    # ── dashboard_summary ───────────────────────────────────
    def dashboard_summary(self) -> dict:
        """Résumé court du tableau de bord."""
        self._stats["summaries"] += 1

        total = len(self._dashboards)
        healthy = sum(1 for d in self._dashboards if d.get("overall_status") == "healthy")
        warning = sum(1 for d in self._dashboards if d.get("overall_status") == "warning")
        critical = sum(1 for d in self._dashboards if d.get("overall_status") == "critical")

        current_status = "unknown"
        if self._dashboards:
            current_status = self._dashboards[-1].get("overall_status", "unknown")

        return {
            "id": f"dsm_{uuid.uuid4().hex[:8]}",
            "summary": True,
            "current_status": current_status,
            "total_dashboards": total,
            "by_status": {
                "healthy": healthy,
                "warning": warning,
                "critical": critical,
            },
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "observability_dashboard_engine",
            "status": "ok",
            "total_dashboards": len(self._dashboards),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._dashboards.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ObservabilityDashboardEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._dashboards) > 5000:
            self._dashboards = self._dashboards[-2500:]
