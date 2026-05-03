"""
Tests unitaires — v9 Observability (LogManager, MetricsManager, TraceManager)

Valide les composants d'observabilité côté Python :
 - LogManager (structured JSON logging, correlation IDs)
 - MetricsManager (counter, gauge, histogram, timer)
 - TraceManager (traces, spans, export)
"""

import json
import logging
import time

import pytest

import sys
from pathlib import Path


# ═══════════════════════════════════════════════════════
#  LogManager
# ═══════════════════════════════════════════════════════

from shared.log_manager import LogManager, JSONFormatter


class TestJSONFormatter:
    def test_format_produces_valid_json(self):
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="exo.test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="hello world", args=(), exc_info=None,
        )
        line = fmt.format(record)
        data = json.loads(line)
        assert data["level"] == "INFO"
        assert data["msg"] == "hello world"
        assert "ts" in data

    def test_format_includes_exception(self):
        fmt = JSONFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="exo.test", level=logging.ERROR, pathname="test.py",
            lineno=1, msg="error", args=(), exc_info=exc_info,
        )
        data = json.loads(fmt.format(record))
        assert data["exception"]["type"] == "ValueError"
        assert "boom" in data["exception"]["msg"]


class TestLogManager:
    def setup_method(self):
        LogManager._instances.clear()

    def test_singleton_per_service(self):
        a = LogManager.get("svc_a")
        b = LogManager.get("svc_b")
        a2 = LogManager.get("svc_a")
        assert a is a2
        assert a is not b

    def test_get_creates_instance(self):
        mgr = LogManager.get("test_svc")
        assert mgr.service_name == "test_svc"

    def test_request_id_correlation(self):
        rid = LogManager.new_request_id()
        assert len(rid) == 12
        assert LogManager.get_request_id() == rid

    def test_set_request_id(self):
        LogManager.set_request_id("custom123")
        assert LogManager.get_request_id() == "custom123"

    def test_log_levels(self):
        mgr = LogManager("test_levels", log_to_file=False)
        # Should not raise
        mgr.debug("debug msg")
        mgr.info("info msg")
        mgr.warn("warn msg")
        mgr.error("error msg")
        mgr.critical("critical msg")


# ═══════════════════════════════════════════════════════
#  MetricsManager
# ═══════════════════════════════════════════════════════

from shared.metrics_manager import MetricsManager, Counter, Gauge, Histogram, Timer


class TestCounter:
    def test_increment(self):
        c = Counter("test")
        assert c.value == 0.0
        c.inc()
        assert c.value == 1.0
        c.inc(5)
        assert c.value == 6.0

    def test_snapshot(self):
        c = Counter("requests")
        c.inc(10)
        snap = c.snapshot()
        assert snap["type"] == "counter"
        assert snap["name"] == "requests"
        assert snap["value"] == 10.0


class TestGauge:
    def test_set_inc_dec(self):
        g = Gauge("temp")
        g.set(20.0)
        assert g.value == 20.0
        g.inc(5)
        assert g.value == 25.0
        g.dec(3)
        assert g.value == 22.0

    def test_snapshot(self):
        g = Gauge("connections")
        g.set(42)
        snap = g.snapshot()
        assert snap["type"] == "gauge"
        assert snap["value"] == 42


class TestHistogram:
    def test_observe_and_count(self):
        h = Histogram("latency")
        for v in [0.1, 0.2, 0.3, 0.4, 0.5]:
            h.observe(v)
        assert h.count == 5

    def test_snapshot_stats(self):
        h = Histogram("latency")
        for i in range(100):
            h.observe(float(i))
        snap = h.snapshot()
        assert snap["count"] == 100
        assert snap["min"] == 0.0
        assert snap["max"] == 99.0
        assert snap["avg"] == pytest.approx(49.5)
        assert "p50" in snap
        assert "p95" in snap
        assert "p99" in snap

    def test_empty_snapshot(self):
        h = Histogram("empty")
        snap = h.snapshot()
        assert snap["count"] == 0

    def test_max_samples_eviction(self):
        h = Histogram("bounded", max_samples=10)
        for i in range(50):
            h.observe(float(i))
        assert h.count == 10


class TestTimer:
    def test_timer_records_duration(self):
        h = Histogram("timer_test")
        t = Timer(h)
        with t.time():
            pass  # near-instant
        assert h.count == 1
        snap = h.snapshot()
        assert snap["min"] >= 0.0


class TestMetricsManager:
    def setup_method(self):
        MetricsManager.reset()

    def test_builtin_metrics(self):
        m = MetricsManager("test_svc")
        assert m.counter("requests_total").value == 0
        assert m.counter("errors_total").value == 0
        assert m.gauge("uptime_s").value == 0.0

    def test_factory_idempotent(self):
        m = MetricsManager("test_svc")
        c1 = m.counter("my_counter")
        c2 = m.counter("my_counter")
        assert c1 is c2

    def test_snapshot(self):
        m = MetricsManager("test_svc")
        m.counter("requests_total").inc(5)
        snap = m.snapshot()
        assert snap["service"] == "test_svc"
        assert "counters" in snap
        assert "gauges" in snap
        assert "histograms" in snap
        assert snap["counters"]["requests_total"]["value"] == 5.0

    def test_timer_factory(self):
        m = MetricsManager("test_svc")
        timer = m.timer("request_time")
        with timer.time():
            pass
        assert m.histogram("request_time").count == 1


# ═══════════════════════════════════════════════════════
#  TraceManager
# ═══════════════════════════════════════════════════════

from shared.trace_manager import TraceManager, Trace, Span


class TestSpan:
    def test_span_creation(self):
        s = Span("trace1", "test_span", "test_svc")
        assert s.trace_id == "trace1"
        assert s.name == "test_span"
        assert s.service == "test_svc"
        assert len(s.span_id) == 12

    def test_span_finish(self):
        s = Span("trace1", "test_span", "test_svc")
        s.finish()
        assert s.end_ns > 0
        assert s.status == "ok"

    def test_span_error(self):
        s = Span("trace1", "test_span", "test_svc")
        s.finish(status="error", error="timeout")
        assert s.status == "error"
        assert s.error == "timeout"

    def test_span_duration(self):
        s = Span("trace1", "test_span", "test_svc")
        assert s.duration_ms >= 0.0
        s.finish()
        assert s.duration_ms >= 0.0

    def test_to_dict(self):
        s = Span("trace1", "test_span", "test_svc")
        s.metadata["key"] = "value"
        s.finish()
        d = s.to_dict()
        assert d["trace_id"] == "trace1"
        assert d["name"] == "test_span"
        assert d["metadata"] == {"key": "value"}


class TestTrace:
    def test_trace_creation(self):
        t = Trace()
        assert len(t.trace_id) == 16
        assert t.spans == []

    def test_start_span(self):
        t = Trace("fixed_id")
        s = t.start_span("op1", "svc1")
        assert s.trace_id == "fixed_id"
        assert len(t.spans) == 1

    def test_context_manager_span(self):
        t = Trace()
        with t.span("op1", "svc1") as s:
            s.metadata["x"] = 1
        assert t.spans[0].status == "ok"
        assert t.spans[0].end_ns > 0

    def test_context_manager_span_error(self):
        t = Trace()
        with pytest.raises(RuntimeError):
            with t.span("op1", "svc1"):
                raise RuntimeError("fail")
        assert t.spans[0].status == "error"
        assert "fail" in t.spans[0].error

    def test_duration(self):
        t = Trace()
        with t.span("op1", "svc1"):
            pass
        assert t.duration_ms >= 0.0


class TestTraceManager:
    def setup_method(self):
        TraceManager.reset()

    def test_new_trace_and_finish(self):
        tm = TraceManager("test_svc")
        t = tm.new_trace()
        s = t.start_span("op1", "test_svc")
        s.finish()
        doc = tm.finish_trace(t.trace_id)
        assert doc is not None
        assert doc["trace_id"] == t.trace_id
        assert doc["span_count"] == 1

    def test_recent_traces(self):
        tm = TraceManager("test_svc")
        for _ in range(5):
            t = tm.new_trace()
            t.start_span("op", "test_svc").finish()
            tm.finish_trace(t.trace_id)
        assert len(tm.recent(10)) == 5

    def test_trace_context_manager(self):
        tm = TraceManager("test_svc")
        with tm.trace("request") as t:
            t.start_span("sub_op", "test_svc").finish()
        assert len(tm.recent()) >= 1

    def test_export_json(self, tmp_path):
        tm = TraceManager("test_svc")
        t = tm.new_trace()
        t.start_span("op1", "test_svc").finish()
        tm.finish_trace(t.trace_id)
        path = tm.export_json(tmp_path / "traces.json")
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data) == 1

    def test_max_history(self):
        tm = TraceManager("test_svc", max_history=5)
        for _ in range(10):
            t = tm.new_trace()
            t.start_span("op", "test_svc").finish()
            tm.finish_trace(t.trace_id)
        assert len(tm.recent(100)) == 5
