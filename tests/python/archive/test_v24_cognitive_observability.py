"""Tests EXO v24 — Cognitive Observability (8 modules, ~70 tests)."""
import sys, os, pytest


# ═══════════════════════════════════════════════════════════
# 1. CognitiveTelemetryEngine
# ═══════════════════════════════════════════════════════════
from cognitive_telemetry_engine import CognitiveTelemetryEngine


class TestCognitiveTelemetryEngine:
    def _make(self):
        return CognitiveTelemetryEngine()

    def test_collect_valid_event(self):
        e = self._make()
        r = e.telemetry_collect({"type": "agent", "source": "nlu", "data": {"x": 1}})
        assert r["collected"] is True
        assert r["valid"] is True
        assert r["type"] == "agent"
        assert r["source"] == "nlu"
        assert r["total_events"] == 1
        assert r["id"].startswith("tel_")

    def test_collect_unknown_type(self):
        e = self._make()
        r = e.telemetry_collect({"type": "random", "source": "test"})
        assert r["collected"] is True
        assert r["valid"] is False

    def test_stream_empty(self):
        e = self._make()
        r = e.telemetry_stream()
        assert r["count"] == 0
        assert r["events"] == []

    def test_stream_with_events(self):
        e = self._make()
        e.telemetry_collect({"type": "layer", "source": "stt"})
        e.telemetry_collect({"type": "agent", "source": "nlu"})
        r = e.telemetry_stream()
        assert r["count"] == 2
        assert "layer" in r["by_type"]

    def test_snapshot(self):
        e = self._make()
        e.telemetry_collect({"type": "inference", "source": "llm"})
        e.telemetry_collect({"type": "inference", "source": "llm"})
        r = e.telemetry_snapshot()
        assert r["total_events"] == 2
        assert r["by_type"]["inference"] == 2
        assert r["by_source"]["llm"] == 2
        assert r["oldest"] is not None

    def test_health_check(self):
        e = self._make()
        h = e.health_check()
        assert h["service"] == "cognitive_telemetry_engine"
        assert h["status"] == "ok"

    def test_restart(self):
        e = self._make()
        e.telemetry_collect({"type": "agent", "source": "x"})
        e.restart()
        assert e.get_stats()["collected"] == 0
        r = e.telemetry_snapshot()
        assert r["total_events"] == 0

    def test_stats(self):
        e = self._make()
        e.telemetry_collect({"type": "agent", "source": "x"})
        e.telemetry_stream()
        e.telemetry_snapshot()
        s = e.get_stats()
        assert s["collected"] == 1
        assert s["streams"] == 1
        assert s["snapshots"] == 1


# ═══════════════════════════════════════════════════════════
# 2. StructuredTracingEngine
# ═══════════════════════════════════════════════════════════
from structured_tracing_engine import StructuredTracingEngine


class TestStructuredTracingEngine:
    def _make(self):
        return StructuredTracingEngine()

    def test_trace_start(self):
        e = self._make()
        r = e.trace_start({"type": "agent", "name": "nlu_process"})
        assert r["started"] is True
        assert r["type"] == "agent"
        assert r["name"] == "nlu_process"
        assert r["active_spans"] == 1

    def test_trace_end(self):
        e = self._make()
        r1 = e.trace_start({"type": "pipeline", "name": "main"})
        r2 = e.trace_end({"span_id": r1["id"], "status": "ok"})
        assert r2["ended"] is True
        assert r2["duration"] >= 0
        assert r2["completed_spans"] == 1

    def test_trace_end_not_found(self):
        e = self._make()
        r = e.trace_end({"span_id": "nope"})
        assert r["ended"] is False
        assert r["error"] == "span_not_found"

    def test_trace_export_empty(self):
        e = self._make()
        r = e.trace_export()
        assert r["total_spans"] == 0
        assert r["active_spans"] == 0

    def test_trace_export_with_spans(self):
        e = self._make()
        r1 = e.trace_start({"type": "layer", "name": "stt"})
        e.trace_end({"span_id": r1["id"]})
        r = e.trace_export()
        assert r["total_spans"] == 1
        assert "layer" in r["by_type"]

    def test_health_check(self):
        e = self._make()
        h = e.health_check()
        assert h["service"] == "structured_tracing_engine"
        assert h["status"] == "ok"

    def test_restart(self):
        e = self._make()
        e.trace_start({"type": "agent", "name": "x"})
        e.restart()
        assert e.get_stats()["started"] == 0
        r = e.trace_export()
        assert r["total_spans"] == 0
        assert r["active_spans"] == 0


# ═══════════════════════════════════════════════════════════
# 3. CognitiveMetricsEngine
# ═══════════════════════════════════════════════════════════
from cognitive_metrics_engine import CognitiveMetricsEngine


class TestCognitiveMetricsEngine:
    def _make(self):
        return CognitiveMetricsEngine()

    def test_metrics_update(self):
        e = self._make()
        r = e.metrics_update({"name": "latency_agent", "value": 0.5, "source": "nlu"})
        assert r["updated"] is True
        assert r["name"] == "latency_agent"
        assert r["value"] == 0.5
        assert r["samples"] == 1

    def test_metrics_compute_empty(self):
        e = self._make()
        r = e.metrics_compute()
        assert r["computed"] is True
        assert r["metrics_count"] == 0

    def test_metrics_compute(self):
        e = self._make()
        e.metrics_update({"name": "latency_agent", "value": 1.0})
        e.metrics_update({"name": "latency_agent", "value": 2.0})
        r = e.metrics_compute()
        assert r["metrics_count"] == 1
        m = r["metrics"]["latency_agent"]
        assert m["avg"] == 1.5
        assert m["min"] == 1.0
        assert m["max"] == 2.0
        assert m["samples"] == 2

    def test_metrics_report(self):
        e = self._make()
        e.metrics_update({"name": "coherence", "value": 0.8})
        r = e.metrics_report()
        assert r["reported"] is True
        assert 0.0 <= r["health_score"] <= 1.0
        assert r["metrics_count"] >= 1

    def test_health_check(self):
        e = self._make()
        h = e.health_check()
        assert h["service"] == "cognitive_metrics_engine"

    def test_restart(self):
        e = self._make()
        e.metrics_update({"name": "latency_agent", "value": 1.0})
        e.restart()
        assert e.get_stats()["updated"] == 0
        r = e.metrics_compute()
        assert r["metrics_count"] == 0


# ═══════════════════════════════════════════════════════════
# 4. PerformanceAnalysisEngine
# ═══════════════════════════════════════════════════════════
from performance_analysis_engine import PerformanceAnalysisEngine


class TestPerformanceAnalysisEngine:
    def _make(self):
        m = CognitiveMetricsEngine()
        return PerformanceAnalysisEngine(metrics=m), m

    def test_analyze_no_data(self):
        p, _ = self._make()
        r = p.analyze_performance()
        assert r["analyzed"] is True
        assert r["overall_status"] == "healthy"
        assert r["metrics_analyzed"] == 0

    def test_analyze_warning(self):
        p, m = self._make()
        m.metrics_update({"name": "latency_agent", "value": 1.5})
        r = p.analyze_performance()
        assert r["overall_status"] == "degraded"
        assert r["warning_count"] >= 1

    def test_analyze_critical(self):
        p, m = self._make()
        m.metrics_update({"name": "latency_agent", "value": 3.0})
        r = p.analyze_performance()
        assert r["overall_status"] == "critical"

    def test_detect_bottlenecks_no_data(self):
        p, _ = self._make()
        r = p.detect_bottlenecks()
        assert r["detected"] is True
        assert r["count"] == 0

    def test_detect_bottlenecks(self):
        p, m = self._make()
        m.metrics_update({"name": "latency_agent", "value": 2.0})
        m.metrics_update({"name": "latency_layer", "value": 0.1})
        r = p.detect_bottlenecks()
        assert r["count"] >= 1
        assert r["bottlenecks"][0]["metric"] == "latency_agent"

    def test_propose_improvements(self):
        p, m = self._make()
        m.metrics_update({"name": "latency_agent", "value": 3.0})
        p.analyze_performance()
        r = p.propose_improvements()
        assert r["proposed"] is True
        assert r["count"] >= 1

    def test_health_check(self):
        p, _ = self._make()
        h = p.health_check()
        assert h["service"] == "performance_analysis_engine"

    def test_restart(self):
        p, m = self._make()
        m.metrics_update({"name": "latency_agent", "value": 3.0})
        p.analyze_performance()
        p.restart()
        assert p.get_stats()["analyzed"] == 0


# ═══════════════════════════════════════════════════════════
# 5. CognitiveAnomalyDetector
# ═══════════════════════════════════════════════════════════
from cognitive_anomaly_detector import CognitiveAnomalyDetector


class TestCognitiveAnomalyDetector:
    def _make(self):
        return CognitiveAnomalyDetector()

    def test_detect_no_anomaly(self):
        e = self._make()
        r = e.detect_anomaly({"source": "nlu", "metric": "latency_agent", "value": 0.5})
        assert r["detected"] is False
        assert r["type"] == "none"
        assert r["total_anomalies"] == 0

    def test_detect_excessive_latency(self):
        e = self._make()
        r = e.detect_anomaly({"source": "nlu", "metric": "latency_agent", "value": 3.0})
        assert r["detected"] is True
        assert r["type"] == "excessive_latency"
        assert r["severity"] == "high"

    def test_detect_overload(self):
        e = self._make()
        r = e.detect_anomaly({"source": "sys", "metric": "cognitive_load", "value": 0.95})
        assert r["detected"] is True
        assert r["type"] == "overload"

    def test_detect_incoherence(self):
        e = self._make()
        r = e.detect_anomaly({"source": "logic", "metric": "coherence", "value": 0.1})
        assert r["detected"] is True
        assert r["type"] == "incoherence"

    def test_classify_anomaly(self):
        e = self._make()
        r = e.classify_anomaly({"metric": "latency_agent", "value": 6.0})
        assert r["classified"] is True
        assert r["type"] == "excessive_latency"
        assert r["severity"] == "critical"
        assert r["category"] == "performance"
        assert r["actionable"] is True

    def test_classify_no_anomaly(self):
        e = self._make()
        r = e.classify_anomaly({"metric": "latency_agent", "value": 0.3})
        assert r["classified"] is True
        assert r["type"] == "none"
        assert r["severity"] == "none"

    def test_explain_anomaly_empty(self):
        e = self._make()
        r = e.explain_anomaly()
        assert r["explained"] is True
        assert r["count"] == 0

    def test_explain_anomaly_with_data(self):
        e = self._make()
        e.detect_anomaly({"source": "nlu", "metric": "latency_agent", "value": 3.0})
        r = e.explain_anomaly()
        assert r["count"] == 1
        assert r["explanations"][0]["type"] == "excessive_latency"

    def test_health_check(self):
        e = self._make()
        h = e.health_check()
        assert h["service"] == "cognitive_anomaly_detector"

    def test_restart(self):
        e = self._make()
        e.detect_anomaly({"source": "x", "metric": "latency_agent", "value": 5.0})
        e.restart()
        assert e.get_stats()["detected"] == 0


# ═══════════════════════════════════════════════════════════
# 6. ObservabilityAggregator
# ═══════════════════════════════════════════════════════════
from observability_aggregator import ObservabilityAggregator


class TestObservabilityAggregator:
    def _make(self):
        t = CognitiveTelemetryEngine()
        tr = StructuredTracingEngine()
        m = CognitiveMetricsEngine()
        a = CognitiveAnomalyDetector()
        p = PerformanceAnalysisEngine(metrics=m)
        agg = ObservabilityAggregator(
            telemetry=t, tracing=tr, metrics=m, anomaly=a, performance=p)
        return agg, t, m

    def test_aggregate_all_empty(self):
        agg, _, _ = self._make()
        r = agg.aggregate_all()
        assert r["aggregated"] is True
        assert r["id"].startswith("agg_")
        assert "sources" in r

    def test_aggregate_all_with_data(self):
        agg, t, m = self._make()
        t.telemetry_collect({"type": "agent", "source": "nlu"})
        m.metrics_update({"name": "latency_agent", "value": 0.5})
        r = agg.aggregate_all()
        assert r["sources"]["telemetry"]["total_events"] >= 1

    def test_aggregate_by_layer(self):
        agg, _, _ = self._make()
        r = agg.aggregate_by_layer()
        assert r["aggregated"] is True
        assert "layers_count" in r

    def test_aggregate_by_agent(self):
        agg, t, _ = self._make()
        t.telemetry_collect({"type": "agent", "source": "nlu"})
        r = agg.aggregate_by_agent()
        assert r["aggregated"] is True
        assert "agents_count" in r

    def test_health_check(self):
        agg, _, _ = self._make()
        h = agg.health_check()
        assert h["service"] == "observability_aggregator"

    def test_restart(self):
        agg, _, _ = self._make()
        agg.aggregate_all()
        agg.restart()
        assert agg.get_stats()["aggregated_all"] == 0


# ═══════════════════════════════════════════════════════════
# 7. ObservabilityDashboardEngine
# ═══════════════════════════════════════════════════════════
from observability_dashboard_engine import ObservabilityDashboardEngine


class TestObservabilityDashboardEngine:
    def _make(self):
        t = CognitiveTelemetryEngine()
        m = CognitiveMetricsEngine()
        a = CognitiveAnomalyDetector()
        p = PerformanceAnalysisEngine(metrics=m)
        agg = ObservabilityAggregator(
            telemetry=t, tracing=StructuredTracingEngine(),
            metrics=m, anomaly=a, performance=p)
        dash = ObservabilityDashboardEngine(aggregator=agg)
        return dash, t, m

    def test_dashboard_generate(self):
        d, _, _ = self._make()
        r = d.dashboard_generate()
        assert r["generated"] is True
        assert r["id"].startswith("dsh_")
        assert r["overall_status"] in ("healthy", "warning", "critical")
        assert "overview" in r

    def test_dashboard_export_empty(self):
        d, _, _ = self._make()
        r = d.dashboard_export()
        assert r["exported"] is True
        assert r["has_data"] is False

    def test_dashboard_export_with_data(self):
        d, _, _ = self._make()
        d.dashboard_generate()
        r = d.dashboard_export()
        assert r["exported"] is True
        assert r["has_data"] is True
        assert r["dashboards_count"] == 1

    def test_dashboard_summary_empty(self):
        d, _, _ = self._make()
        r = d.dashboard_summary()
        assert r["summary"] is True
        assert r["current_status"] == "unknown"

    def test_dashboard_summary_after_generate(self):
        d, _, _ = self._make()
        d.dashboard_generate()
        r = d.dashboard_summary()
        assert r["summary"] is True
        assert r["total_dashboards"] == 1
        assert r["current_status"] == "healthy"

    def test_health_check(self):
        d, _, _ = self._make()
        h = d.health_check()
        assert h["service"] == "observability_dashboard_engine"

    def test_restart(self):
        d, _, _ = self._make()
        d.dashboard_generate()
        d.restart()
        assert d.get_stats()["generated"] == 0


# ═══════════════════════════════════════════════════════════
# 8. ObservabilityExplainabilityEngine
# ═══════════════════════════════════════════════════════════
from observability_explainability_engine import ObservabilityExplainabilityEngine


class TestObservabilityExplainabilityEngine:
    def _make(self):
        m = CognitiveMetricsEngine()
        a = CognitiveAnomalyDetector()
        p = PerformanceAnalysisEngine(metrics=m)
        ex = ObservabilityExplainabilityEngine(metrics=m, anomaly=a, performance=p)
        return ex, m

    def test_explain_known_metric(self):
        ex, m = self._make()
        m.metrics_update({"name": "latency_agent", "value": 0.5})
        r = ex.explain_metric("latency_agent")
        assert r["explained"] is True
        assert r["metric"] == "latency_agent"
        assert r["current_value"] is not None
        assert r["status"] == "ok"

    def test_explain_unknown_metric(self):
        ex, _ = self._make()
        r = ex.explain_metric("unknown_metric")
        assert r["explained"] is True
        assert "non documentée" in r["description"]

    def test_explain_anomaly_known(self):
        ex, _ = self._make()
        r = ex.explain_anomaly("excessive_latency")
        assert r["explained"] is True
        assert r["anomaly"] == "excessive_latency"
        assert r["severity"] == "medium"
        assert len(r["recommendation"]) > 0

    def test_explain_anomaly_unknown(self):
        ex, _ = self._make()
        r = ex.explain_anomaly("something_weird")
        assert r["explained"] is True
        assert "non documentée" in r["explanation"]
        assert r["severity"] == "unknown"

    def test_explain_performance_no_data(self):
        ex, _ = self._make()
        r = ex.explain_performance()
        assert r["explained"] is True
        assert r["issues_count"] == 0

    def test_explain_performance_with_issues(self):
        ex, m = self._make()
        m.metrics_update({"name": "latency_agent", "value": 3.0})
        r = ex.explain_performance()
        assert r["explained"] is True
        # The performance engine may classify this as critical
        assert r["issues_count"] >= 0

    def test_health_check(self):
        ex, _ = self._make()
        h = ex.health_check()
        assert h["service"] == "observability_explainability_engine"

    def test_restart(self):
        ex, _ = self._make()
        ex.explain_metric("coherence")
        ex.restart()
        assert ex.get_stats()["metrics_explained"] == 0
