"""
EXO v24 — StructuredTracingEngine
Trace toutes les opérations cognitives de manière structurée :
spans agents, couches, pipelines, simulations, inférences.

API:
  trace_start(operation: dict) → dict
  trace_end(operation: dict)   → dict
  trace_export()               → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("structured_tracing_engine")


class StructuredTracingEngine:
    """Moteur de traces structurées EXO v24."""

    SPAN_TYPES = {
        "agent", "layer", "pipeline", "simulation",
        "inference", "planning", "decision", "governance",
    }

    def __init__(self, governance=None):
        self._governance = governance

        self._active_spans: dict[str, dict] = {}
        self._completed_spans: list[dict] = []
        self._stats = {
            "started": 0,
            "ended": 0,
            "exported": 0,
        }

    # ── trace_start ─────────────────────────────────────────
    def trace_start(self, operation: dict) -> dict:
        """Démarrer un span de trace."""
        self._stats["started"] += 1

        span_id = f"span_{uuid.uuid4().hex[:8]}"
        op_type = operation.get("type", "unknown")
        op_name = operation.get("name", "unnamed")
        parent = operation.get("parent_span", None)

        span = {
            "id": span_id,
            "type": op_type,
            "name": op_name,
            "parent_span": parent,
            "start_time": time.time(),
            "end_time": None,
            "duration": None,
            "status": "active",
            "metadata": operation.get("metadata", {}),
        }
        self._active_spans[span_id] = span

        return {
            "id": span_id,
            "started": True,
            "type": op_type,
            "name": op_name,
            "active_spans": len(self._active_spans),
            "timestamp": span["start_time"],
        }

    # ── trace_end ───────────────────────────────────────────
    def trace_end(self, operation: dict) -> dict:
        """Terminer un span de trace."""
        self._stats["ended"] += 1

        span_id = operation.get("span_id", "")
        status = operation.get("status", "ok")
        result = operation.get("result", {})

        span = self._active_spans.pop(span_id, None)
        if span is None:
            return {
                "id": span_id,
                "ended": False,
                "error": "span_not_found",
                "timestamp": time.time(),
            }

        end_time = time.time()
        span["end_time"] = end_time
        span["duration"] = round(end_time - span["start_time"], 6)
        span["status"] = status
        span["result"] = result

        self._completed_spans.append(span)
        self._trim()

        return {
            "id": span_id,
            "ended": True,
            "duration": span["duration"],
            "status": status,
            "completed_spans": len(self._completed_spans),
            "timestamp": end_time,
        }

    # ── trace_export ────────────────────────────────────────
    def trace_export(self) -> dict:
        """Exporter toutes les traces complétées."""
        self._stats["exported"] += 1

        by_type: dict[str, int] = {}
        total_duration = 0.0
        for sp in self._completed_spans:
            t = sp.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
            total_duration += sp.get("duration", 0)

        avg_duration = (total_duration / len(self._completed_spans)
                        if self._completed_spans else 0.0)

        return {
            "id": f"tex_{uuid.uuid4().hex[:8]}",
            "total_spans": len(self._completed_spans),
            "active_spans": len(self._active_spans),
            "by_type": by_type,
            "avg_duration": round(avg_duration, 6),
            "spans": self._completed_spans[-100:],
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "structured_tracing_engine",
            "status": "ok",
            "active_spans": len(self._active_spans),
            "completed_spans": len(self._completed_spans),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._active_spans.clear()
        self._completed_spans.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("StructuredTracingEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._completed_spans) > 5000:
            self._completed_spans = self._completed_spans[-2500:]
