"""EXO v9 — Distributed tracing: each request = trace, each step = span."""

import json
import time
import uuid
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

TRACE_DIR = Path("D:/EXO/logs/traces")


class Span:
    """A single unit of work inside a trace."""

    __slots__ = (
        "trace_id", "span_id", "parent_id", "name", "service",
        "start_ns", "end_ns", "metadata", "status", "error",
    )

    def __init__(self, trace_id: str, name: str, service: str,
                 parent_id: Optional[str] = None):
        self.trace_id = trace_id
        self.span_id = uuid.uuid4().hex[:12]
        self.parent_id = parent_id
        self.name = name
        self.service = service
        self.start_ns = time.monotonic_ns()
        self.end_ns: int = 0
        self.metadata: dict[str, Any] = {}
        self.status: str = "ok"
        self.error: Optional[str] = None

    def finish(self, status: str = "ok", error: Optional[str] = None) -> None:
        self.end_ns = time.monotonic_ns()
        self.status = status
        if error:
            self.error = error

    @property
    def duration_ms(self) -> float:
        end = self.end_ns or time.monotonic_ns()
        return (end - self.start_ns) / 1_000_000

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "service": self.service,
            "duration_ms": round(self.duration_ms, 2),
            "status": self.status,
        }
        if self.parent_id:
            d["parent_id"] = self.parent_id
        if self.metadata:
            d["metadata"] = self.metadata
        if self.error:
            d["error"] = self.error
        return d


class Trace:
    """A collection of spans representing one end-to-end request."""

    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or uuid.uuid4().hex[:16]
        self.spans: list[Span] = []
        self._lock = threading.Lock()
        self._start = time.time()

    def start_span(self, name: str, service: str,
                   parent_id: Optional[str] = None) -> Span:
        span = Span(self.trace_id, name, service, parent_id)
        with self._lock:
            self.spans.append(span)
        return span

    @contextmanager
    def span(self, name: str, service: str,
             parent_id: Optional[str] = None):
        s = self.start_span(name, service, parent_id)
        try:
            yield s
        except Exception as exc:
            s.finish(status="error", error=str(exc))
            raise
        else:
            s.finish()

    @property
    def duration_ms(self) -> float:
        if not self.spans:
            return 0.0
        starts = [s.start_ns for s in self.spans]
        ends = [s.end_ns or time.monotonic_ns() for s in self.spans]
        return (max(ends) - min(starts)) / 1_000_000

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "ts": self._start,
            "duration_ms": round(self.duration_ms, 2),
            "span_count": len(self.spans),
            "spans": [s.to_dict() for s in self.spans],
        }


class TraceManager:
    """Central registry of active & completed traces."""

    _instance: Optional["TraceManager"] = None

    def __init__(self, service_name: str, max_history: int = 200):
        self.service_name = service_name
        self._active: dict[str, Trace] = {}
        self._completed: list[dict[str, Any]] = []
        self._max_history = max_history
        self._lock = threading.Lock()

    @classmethod
    def instance(cls, service_name: str = "exo") -> "TraceManager":
        if cls._instance is None:
            cls._instance = cls(service_name)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def new_trace(self, trace_id: Optional[str] = None) -> Trace:
        t = Trace(trace_id)
        with self._lock:
            self._active[t.trace_id] = t
        return t

    def finish_trace(self, trace_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            t = self._active.pop(trace_id, None)
        if t is None:
            return None
        doc = t.to_dict()
        with self._lock:
            self._completed.append(doc)
            if len(self._completed) > self._max_history:
                self._completed = self._completed[-self._max_history:]
        return doc

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        return self._active.get(trace_id)

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._completed[-n:])

    def export_json(self, path: Optional[Path] = None) -> Path:
        path = path or TRACE_DIR / f"traces_{self.service_name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            data = list(self._completed)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return path

    @contextmanager
    def trace(self, name: str = "request"):
        """Create a trace, auto-finish on exit."""
        t = self.new_trace()
        span = t.start_span(name, self.service_name)
        try:
            yield t
        except Exception as exc:
            span.finish(status="error", error=str(exc))
            raise
        else:
            span.finish()
        finally:
            self.finish_trace(t.trace_id)
