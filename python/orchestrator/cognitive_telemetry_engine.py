"""
EXO v24 — CognitiveTelemetryEngine
Collecte des données de télémétrie sur le fonctionnement interne d'EXO :
agents, couches, inférences, simulations, planification.

API:
  telemetry_collect(event: dict)  → dict
  telemetry_stream()              → dict
  telemetry_snapshot()            → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("cognitive_telemetry_engine")


class CognitiveTelemetryEngine:
    """Moteur de télémétrie cognitive EXO v24."""

    EVENT_TYPES = {
        "agent", "layer", "inference", "simulation",
        "planning", "pipeline", "decision", "governance",
    }

    MAX_EVENTS = 10000

    def __init__(self, governance=None):
        self._governance = governance

        self._events: list[dict] = []
        self._stats = {
            "collected": 0,
            "streams": 0,
            "snapshots": 0,
        }

    # ── telemetry_collect ───────────────────────────────────
    def telemetry_collect(self, event: dict) -> dict:
        """Collecter un événement de télémétrie."""
        self._stats["collected"] += 1

        etype = event.get("type", "unknown")
        source = event.get("source", "unknown")
        data = event.get("data", {})

        record = {
            "id": f"tel_{uuid.uuid4().hex[:8]}",
            "type": etype,
            "source": source,
            "data": data,
            "valid": etype in self.EVENT_TYPES,
            "timestamp": time.time(),
        }
        self._events.append(record)
        self._trim()

        return {
            "id": record["id"],
            "collected": True,
            "type": etype,
            "source": source,
            "valid": record["valid"],
            "total_events": len(self._events),
            "timestamp": record["timestamp"],
        }

    # ── telemetry_stream ────────────────────────────────────
    def telemetry_stream(self) -> dict:
        """Retourner les événements récents (flux de télémétrie)."""
        self._stats["streams"] += 1

        recent = self._events[-50:] if self._events else []

        by_type: dict[str, int] = {}
        for ev in recent:
            t = ev.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "id": f"tstr_{uuid.uuid4().hex[:8]}",
            "count": len(recent),
            "events": recent,
            "by_type": by_type,
            "timestamp": time.time(),
        }

    # ── telemetry_snapshot ──────────────────────────────────
    def telemetry_snapshot(self) -> dict:
        """Capturer un instantané complet de la télémétrie."""
        self._stats["snapshots"] += 1

        by_type: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for ev in self._events:
            t = ev.get("type", "unknown")
            s = ev.get("source", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
            by_source[s] = by_source.get(s, 0) + 1

        return {
            "id": f"tsnap_{uuid.uuid4().hex[:8]}",
            "total_events": len(self._events),
            "by_type": by_type,
            "by_source": by_source,
            "oldest": self._events[0]["timestamp"] if self._events else None,
            "newest": self._events[-1]["timestamp"] if self._events else None,
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "cognitive_telemetry_engine",
            "status": "ok",
            "total_events": len(self._events),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._events.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("CognitiveTelemetryEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._events) > self.MAX_EVENTS:
            self._events = self._events[-5000:]
