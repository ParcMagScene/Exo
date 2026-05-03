"""EXO v9 — Metrics: counters, gauges, histograms, timers."""

import math
import threading
import time
from contextlib import contextmanager
from typing import Any, Optional


class Counter:
    """Monotonically-increasing counter."""

    __slots__ = ("name", "_value", "_lock")

    def __init__(self, name: str, initial: float = 0.0):
        self.name = name
        self._value = initial
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    @property
    def value(self) -> float:
        return self._value

    def snapshot(self) -> dict[str, Any]:
        return {"type": "counter", "name": self.name, "value": self._value}


class Gauge:
    """Value that can go up or down."""

    __slots__ = ("name", "_value", "_lock")

    def __init__(self, name: str, initial: float = 0.0):
        self.name = name
        self._value = initial
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value -= amount

    @property
    def value(self) -> float:
        return self._value

    def snapshot(self) -> dict[str, Any]:
        return {"type": "gauge", "name": self.name, "value": self._value}


class Histogram:
    """Latency distribution: count, sum, min, max, avg, p50, p95, p99."""

    __slots__ = ("name", "_values", "_lock", "_max_samples")

    def __init__(self, name: str, max_samples: int = 1000):
        self.name = name
        self._values: list[float] = []
        self._lock = threading.Lock()
        self._max_samples = max_samples

    def observe(self, value: float) -> None:
        with self._lock:
            self._values.append(value)
            if len(self._values) > self._max_samples:
                self._values = self._values[-self._max_samples:]

    @property
    def count(self) -> int:
        return len(self._values)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            vals = list(self._values)
        if not vals:
            return {"type": "histogram", "name": self.name, "count": 0}
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        return {
            "type": "histogram",
            "name": self.name,
            "count": n,
            "sum": sum(vals_sorted),
            "min": vals_sorted[0],
            "max": vals_sorted[-1],
            "avg": sum(vals_sorted) / n,
            "p50": vals_sorted[n // 2],
            "p95": vals_sorted[int(n * 0.95)] if n >= 20 else vals_sorted[-1],
            "p99": vals_sorted[int(n * 0.99)] if n >= 100 else vals_sorted[-1],
        }


class Timer:
    """Convenience wrapper: measures elapsed time → feeds a Histogram."""

    __slots__ = ("_histogram",)

    def __init__(self, histogram: Histogram):
        self._histogram = histogram

    @contextmanager
    def time(self):
        t0 = time.perf_counter()
        yield
        self._histogram.observe(time.perf_counter() - t0)


class MetricsManager:
    """Central registry for all EXO metrics."""

    _instance: Optional["MetricsManager"] = None

    def __init__(self, service_name: str):
        self.service_name = service_name
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._start_time = time.monotonic()
        self._lock = threading.Lock()

        # built-in gauges
        self.gauge("uptime_s")
        self.counter("requests_total")
        self.counter("errors_total")
        self.histogram("request_latency_s")

    @classmethod
    def instance(cls, service_name: str = "exo") -> "MetricsManager":
        if cls._instance is None:
            cls._instance = cls(service_name)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    # ── factory ──────────────────────────────────────────────────
    def counter(self, name: str) -> Counter:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name)
            return self._counters[name]

    def gauge(self, name: str) -> Gauge:
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name)
            return self._gauges[name]

    def histogram(self, name: str) -> Histogram:
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(name)
            return self._histograms[name]

    def timer(self, name: str) -> Timer:
        return Timer(self.histogram(name))

    # ── queries ──────────────────────────────────────────────────
    def snapshot(self) -> dict[str, Any]:
        self.gauge("uptime_s").set(time.monotonic() - self._start_time)
        result: dict[str, Any] = {
            "service": self.service_name,
            "ts": time.time(),
            "counters": {n: c.snapshot() for n, c in self._counters.items()},
            "gauges": {n: g.snapshot() for n, g in self._gauges.items()},
            "histograms": {n: h.snapshot() for n, h in self._histograms.items()},
        }
        return result
