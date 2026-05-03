"""
EXO v25 — CognitiveAuditEngine
Audit cognitif : trace actions, décisions, validations, refus, anomalies.

API:
  audit_log(event)          → dict
  audit_export()            → dict
  audit_query(criteria)     → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("cognitive_audit_engine")


class CognitiveAuditEngine:
    """Moteur d'audit cognitif EXO v25."""

    EVENT_CATEGORIES = {
        "action", "decision", "validation", "rejection",
        "anomaly", "permission", "compliance", "governance",
    }

    def __init__(self, governance=None):
        self._governance = governance

        self._logs: list[dict] = []
        self._stats = {
            "logged": 0,
            "exported": 0,
            "queried": 0,
        }

    # ── audit_log ───────────────────────────────────────────
    def audit_log(self, event: dict) -> dict:
        """Enregistrer un événement d'audit."""
        self._stats["logged"] += 1

        category = event.get("category", "unknown")
        source = event.get("source", "unknown")
        action = event.get("action", "unknown")
        result = event.get("result", "unknown")
        details = event.get("details", {})

        record = {
            "id": f"aud_{uuid.uuid4().hex[:8]}",
            "category": category,
            "source": source,
            "action": action,
            "result": result,
            "details": details,
            "valid_category": category in self.EVENT_CATEGORIES,
            "timestamp": time.time(),
        }
        self._logs.append(record)
        self._trim()

        return {
            "id": record["id"],
            "logged": True,
            "category": category,
            "source": source,
            "total_logs": len(self._logs),
            "timestamp": record["timestamp"],
        }

    # ── audit_export ────────────────────────────────────────
    def audit_export(self) -> dict:
        """Exporter l'intégralité du journal d'audit."""
        self._stats["exported"] += 1

        by_category: dict[str, int] = {}
        for entry in self._logs:
            cat = entry.get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "id": f"aexp_{uuid.uuid4().hex[:8]}",
            "exported": True,
            "total_logs": len(self._logs),
            "by_category": by_category,
            "logs": self._logs[-100:],
            "timestamp": time.time(),
        }

    # ── audit_query ─────────────────────────────────────────
    def audit_query(self, criteria: dict) -> dict:
        """Rechercher dans le journal d'audit."""
        self._stats["queried"] += 1

        category = criteria.get("category")
        source = criteria.get("source")
        action = criteria.get("action")
        limit = criteria.get("limit", 50)

        matches = []
        for entry in reversed(self._logs):
            if category and entry.get("category") != category:
                continue
            if source and entry.get("source") != source:
                continue
            if action and entry.get("action") != action:
                continue
            matches.append(entry)
            if len(matches) >= limit:
                break

        return {
            "id": f"aq_{uuid.uuid4().hex[:8]}",
            "queried": True,
            "criteria": criteria,
            "count": len(matches),
            "matches": matches,
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "cognitive_audit_engine",
            "status": "ok",
            "total_logs": len(self._logs),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._logs.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("CognitiveAuditEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._logs) > 5000:
            self._logs = self._logs[-2500:]
