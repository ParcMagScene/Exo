"""
EXO v11 — AutoExplanation (Auto-explication)
Explique les décisions, optimisations et apprentissages d'EXO de façon
compréhensible pour l'utilisateur.

API:
  explain_decision(action, context)   → str
  explain_learning(entry_id)          → str
  explain_optimization(opt_record)    → str
  explain_tuning(parameter)           → str
  explain_diagnosis(report)           → str
  get_explanation_log(limit)          → list[dict]
"""

import logging
import time
from typing import Any

log = logging.getLogger("auto_explanation")


class AutoExplanation:
    """Moteur d'auto-explication EXO v11."""

    def __init__(self, meta_memory):
        """
        Args:
            meta_memory: MetaMemory instance for context lookup.
        """
        self._memory = meta_memory
        self._log: list[dict] = []
        self._stats = {
            "explanations_generated": 0,
        }

    def _record(self, kind: str, subject: str, explanation: str) -> str:
        """Record an explanation and return it."""
        self._log.append({
            "kind": kind,
            "subject": subject,
            "explanation": explanation,
            "timestamp": time.time(),
        })
        if len(self._log) > 300:
            self._log = self._log[-300:]
        self._stats["explanations_generated"] += 1
        return explanation

    # ── Decision explanation ─────────────────────────────────
    def explain_decision(self, action: str, context: dict | None = None) -> str:
        """Explain why EXO chose a particular action.

        Looks up relevant strategies and preferences in MetaMemory.
        """
        parts = [f"Action choisie : {action}."]

        # Look for learned strategies related to the action
        strategies = self._memory.meta_get(action)
        relevant_strats = [
            s for s in strategies if s.get("category") == "strategy"
        ]
        if relevant_strats:
            best = relevant_strats[0]
            val = best.get("value", {})
            rate = val.get("success_rate", "?") if isinstance(val, dict) else "?"
            parts.append(
                f"Basé sur la stratégie '{best.get('key', '')}' "
                f"(taux de succès : {rate})."
            )

        # Look for user preferences
        prefs = self._memory.meta_get(action)
        relevant_prefs = [
            p for p in prefs if p.get("category") == "preference"
        ]
        if relevant_prefs:
            pref = relevant_prefs[0]
            parts.append(
                f"Préférence utilisateur : {pref.get('key')} = {pref.get('value')}."
            )

        if context:
            if context.get("reason"):
                parts.append(f"Raison : {context['reason']}.")

        explanation = " ".join(parts)
        return self._record("decision", action, explanation)

    # ── Learning explanation ─────────────────────────────────
    def explain_learning(self, entry_id: str) -> str:
        """Explain a specific learning entry."""
        entries = self._memory.list_entries(limit=5000)
        entry = None
        for e in entries:
            if e.get("id") == entry_id:
                entry = e
                break

        if not entry:
            explanation = f"Entrée d'apprentissage {entry_id} non trouvée."
            return self._record("learning", entry_id, explanation)

        cat = entry.get("category", "inconnu")
        key = entry.get("key", "")
        value = entry.get("value", "")
        source = entry.get("source", "inconnu")
        conf = entry.get("confidence", 0)

        explanation = (
            f"Apprentissage '{key}' (catégorie : {cat}). "
            f"Valeur apprise : {value}. "
            f"Source : {source}, confiance : {conf:.0%}."
        )
        return self._record("learning", entry_id, explanation)

    # ── Optimization explanation ─────────────────────────────
    def explain_optimization(self, opt_record: dict) -> str:
        """Explain an optimization decision."""
        opt_type = opt_record.get("type", "général")
        improvements = opt_record.get("improvements", [])

        if not improvements:
            explanation = (
                f"Optimisation de type '{opt_type}' exécutée, "
                f"aucune amélioration nécessaire."
            )
        else:
            details = []
            for imp in improvements[:5]:
                param = imp.get("parameter", imp.get("key", "?"))
                old = imp.get("old_value", "?")
                new = imp.get("new_value", "?")
                details.append(f"{param} : {old} → {new}")
            explanation = (
                f"Optimisation '{opt_type}' : "
                + ", ".join(details) + "."
            )

        return self._record("optimization", opt_type, explanation)

    # ── Tuning explanation ───────────────────────────────────
    def explain_tuning(self, parameter: str) -> str:
        """Explain the current value and history of a tuning parameter."""
        tunings = self._memory.meta_get(f"tuning:{parameter}")
        if not tunings:
            explanation = (
                f"Paramètre '{parameter}' : aucun historique de réglage trouvé."
            )
        else:
            latest = tunings[0]
            val = latest.get("value", "?")
            explanation = (
                f"Paramètre '{parameter}' réglé à {val}. "
                f"{len(tunings)} ajustement(s) enregistré(s)."
            )
        return self._record("tuning", parameter, explanation)

    # ── Diagnosis explanation ────────────────────────────────
    def explain_diagnosis(self, report: dict) -> str:
        """Explain a diagnosis report in natural language."""
        health = report.get("health", "inconnu")
        issues = report.get("issues", [])
        anomalies = report.get("anomalies", [])
        regressions = report.get("regressions", [])

        parts = [f"État de santé : {health}."]

        if issues:
            parts.append(f"{len(issues)} problème(s) détecté(s).")
            for issue in issues[:3]:
                parts.append(f"  - {issue.get('type', '?')} : {issue.get('detail', '')}")

        if anomalies:
            parts.append(f"{len(anomalies)} anomalie(s).")
        if regressions:
            parts.append(f"{len(regressions)} régression(s).")

        if not issues and not anomalies and not regressions:
            parts.append("Aucun problème détecté.")

        explanation = " ".join(parts)
        return self._record("diagnosis", health, explanation)

    # ── Accessors ────────────────────────────────────────────
    def get_explanation_log(self, limit: int = 50) -> list[dict]:
        """Get recent explanations."""
        return self._log[-limit:]

    def get_stats(self) -> dict:
        return dict(self._stats)
