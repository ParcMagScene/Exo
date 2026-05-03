"""
EXO v16 — CognitiveAuditLog (Journal d'audit cognitif)
Trace immutable de toutes les initiatives, validations, rejets et émergences.
Fondation pour la traçabilité et la supervision de l'autonomie.

API:
  log_initiative(initiative)      → dict
  log_validation(validation)      → dict
  log_rejection(rejection)        → dict
  log_emergence(emergence)        → dict
  log_governance(event)           → dict
  log_regulation(event)           → dict
  get_audit_trail(limit, filters) → list[dict]
  get_summary(window_sec)         → dict
  health_check()                  → dict
  restart()                       → None
  get_stats()                     → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("cognitive_audit_log")

# Types d'entrées valides
VALID_ENTRY_TYPES = frozenset({
    "initiative_proposed", "initiative_validated", "initiative_rejected",
    "initiative_executed", "initiative_rolled_back",
    "emergence_detected", "emergence_evaluated", "emergence_applied",
    "governance_decision", "governance_override",
    "regulation_adjustment", "regulation_alert",
    "collaboration_started", "collaboration_completed",
})

MAX_LOG_SIZE = 10_000


class CognitiveAuditLog:
    """Journal d'audit cognitif immutable EXO v16."""

    def __init__(self, meta_memory=None):
        self._memory = meta_memory
        self._entries: list[dict] = []
        self._stats = {
            "initiatives_logged": 0,
            "validations_logged": 0,
            "rejections_logged": 0,
            "emergences_logged": 0,
            "governance_logged": 0,
            "regulations_logged": 0,
            "total_entries": 0,
        }

    # ── log_initiative ──────────────────────────────────────
    def log_initiative(self, initiative: dict) -> dict:
        """Enregistrer une proposition d'initiative autonome."""
        self._stats["initiatives_logged"] += 1
        entry = self._create_entry(
            "initiative_proposed",
            agent=initiative.get("agent", "unknown"),
            action=initiative.get("action", "unknown"),
            confidence=initiative.get("confidence", 0.0),
            domain=initiative.get("domain", "general"),
            reasoning=initiative.get("reasoning", ""),
            budget_cost=initiative.get("budget_cost", 0),
            data=initiative,
        )
        log.info("Initiative logged: %s by %s (confidence=%.2f)",
                 entry["action"], entry["agent"], entry["confidence"])
        return entry

    # ── log_validation ──────────────────────────────────────
    def log_validation(self, validation: dict) -> dict:
        """Enregistrer la validation d'une initiative."""
        self._stats["validations_logged"] += 1
        entry = self._create_entry(
            "initiative_validated",
            initiative_id=validation.get("initiative_id", ""),
            validator=validation.get("validator", "governor"),
            approval_level=validation.get("approval_level", "auto"),
            conditions=validation.get("conditions", []),
            data=validation,
        )
        log.info("Validation logged: %s by %s (level=%s)",
                 entry["initiative_id"], entry["validator"],
                 entry["approval_level"])
        return entry

    # ── log_rejection ───────────────────────────────────────
    def log_rejection(self, rejection: dict) -> dict:
        """Enregistrer le rejet d'une initiative."""
        self._stats["rejections_logged"] += 1
        entry = self._create_entry(
            "initiative_rejected",
            initiative_id=rejection.get("initiative_id", ""),
            rejector=rejection.get("rejector", "governor"),
            reason=rejection.get("reason", ""),
            severity=rejection.get("severity", "low"),
            data=rejection,
        )
        log.info("Rejection logged: %s — %s", entry["initiative_id"],
                 entry["reason"])
        return entry

    # ── log_emergence ───────────────────────────────────────
    def log_emergence(self, emergence: dict) -> dict:
        """Enregistrer une émergence cognitive détectée."""
        self._stats["emergences_logged"] += 1
        entry = self._create_entry(
            "emergence_detected",
            pattern=emergence.get("pattern", "unknown"),
            agents_involved=emergence.get("agents_involved", []),
            novelty_score=emergence.get("novelty_score", 0.0),
            viability=emergence.get("viability", 0.0),
            domain=emergence.get("domain", "general"),
            data=emergence,
        )
        log.info("Emergence logged: %s (novelty=%.2f, viability=%.2f)",
                 entry["pattern"], entry["novelty_score"], entry["viability"])
        return entry

    # ── log_governance ──────────────────────────────────────
    def log_governance(self, event: dict) -> dict:
        """Enregistrer une décision de gouvernance."""
        self._stats["governance_logged"] += 1
        entry = self._create_entry(
            event.get("type", "governance_decision"),
            governor=event.get("governor", "cognitive_governor"),
            decision=event.get("decision", ""),
            scope=event.get("scope", "system"),
            impact=event.get("impact", "low"),
            data=event,
        )
        return entry

    # ── log_regulation ──────────────────────────────────────
    def log_regulation(self, event: dict) -> dict:
        """Enregistrer un ajustement de régulation."""
        self._stats["regulations_logged"] += 1
        entry = self._create_entry(
            event.get("type", "regulation_adjustment"),
            parameter=event.get("parameter", ""),
            old_value=event.get("old_value"),
            new_value=event.get("new_value"),
            reason=event.get("reason", ""),
            data=event,
        )
        return entry

    # ── get_audit_trail ─────────────────────────────────────
    def get_audit_trail(self, limit: int = 50,
                        filters: dict | None = None) -> list[dict]:
        """Récupérer les entrées du journal avec filtres optionnels."""
        entries = self._entries
        if filters:
            entry_type = filters.get("type")
            agent = filters.get("agent")
            domain = filters.get("domain")
            since = filters.get("since", 0)

            if entry_type:
                entries = [e for e in entries if e["entry_type"] == entry_type]
            if agent:
                entries = [e for e in entries if e.get("agent") == agent]
            if domain:
                entries = [e for e in entries if e.get("domain") == domain]
            if since:
                entries = [e for e in entries if e["timestamp"] >= since]

        return entries[-limit:]

    # ── get_summary ─────────────────────────────────────────
    def get_summary(self, window_sec: float = 3600) -> dict:
        """Résumé des activités sur une fenêtre de temps."""
        cutoff = time.time() - window_sec
        recent = [e for e in self._entries if e["timestamp"] >= cutoff]

        type_counts: dict[str, int] = {}
        for e in recent:
            t = e["entry_type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "window_sec": window_sec,
            "total_entries": len(recent),
            "by_type": type_counts,
            "oldest": recent[0]["timestamp"] if recent else None,
            "newest": recent[-1]["timestamp"] if recent else None,
        }

    # ── health_check ────────────────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "cognitive_audit_log",
            "status": "ok",
            "entries_count": len(self._entries),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._entries.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("CognitiveAuditLog restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _create_entry(self, entry_type: str, **kwargs) -> dict:
        """Créer une entrée d'audit immutable."""
        data = kwargs.pop("data", {})
        entry = {
            "id": f"audit_{uuid.uuid4().hex[:12]}",
            "entry_type": entry_type,
            "timestamp": time.time(),
            **kwargs,
        }
        if data:
            entry["raw"] = data

        self._entries.append(entry)
        self._stats["total_entries"] += 1
        self._trim()
        return entry

    def _trim(self) -> None:
        if len(self._entries) > MAX_LOG_SIZE:
            self._entries = self._entries[-MAX_LOG_SIZE:]
