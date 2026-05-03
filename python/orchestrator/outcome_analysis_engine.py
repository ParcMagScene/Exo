"""
EXO v23 — OutcomeAnalysisEngine
Analyse les résultats de simulations : risques, opportunités,
dépendances, conséquences, multi-critères.

API:
  analyze_outcomes(results: dict) → dict
  classify_risks(results: dict)   → dict
  compute_best_outcome()          → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("outcome_analysis_engine")


class OutcomeAnalysisEngine:
    """Moteur d'analyse des résultats de simulation EXO v23."""

    RISK_LEVELS = ("low", "medium", "high", "critical")

    def __init__(self, governance=None, sandbox=None):
        self._governance = governance
        self._sandbox = sandbox

        self._analyses: list[dict] = []
        self._stats = {
            "analyzed": 0,
            "risks_classified": 0,
            "best_computed": 0,
        }

    # ── analyze_outcomes ────────────────────────────────────
    def analyze_outcomes(self, results: dict) -> dict:
        """Analyser les résultats d'une simulation."""
        self._stats["analyzed"] += 1

        items = results.get("results", [])
        analysis = []
        for item in items:
            entry = self._analyze_one(item)
            analysis.append(entry)

        aggregated = self._aggregate(analysis)

        record = {
            "id": f"ao_{uuid.uuid4().hex[:8]}",
            "analyzed": True,
            "count": len(analysis),
            "analysis": analysis,
            "aggregated": aggregated,
            "timestamp": time.time(),
        }
        self._analyses.append(record)
        self._trim()

        return record

    # ── classify_risks ──────────────────────────────────────
    def classify_risks(self, results: dict) -> dict:
        """Classifier les risques dans les résultats."""
        self._stats["risks_classified"] += 1

        items = results.get("results", [])
        classifications = []
        risk_counts = {r: 0 for r in self.RISK_LEVELS}

        for item in items:
            risk = self._assess_risk(item)
            level = risk["level"]
            if level in risk_counts:
                risk_counts[level] += 1
            classifications.append(risk)

        return {
            "id": f"cr_{uuid.uuid4().hex[:8]}",
            "classified": True,
            "count": len(classifications),
            "classifications": classifications,
            "risk_counts": risk_counts,
            "timestamp": time.time(),
        }

    # ── compute_best_outcome ────────────────────────────────
    def compute_best_outcome(self) -> dict:
        """Déterminer le meilleur résultat parmi les analyses."""
        self._stats["best_computed"] += 1

        if not self._analyses:
            return {
                "id": f"bo_{uuid.uuid4().hex[:8]}",
                "found": False,
                "reason": "no_analyses",
                "timestamp": time.time(),
            }

        best = None
        best_score = -1.0
        for a in self._analyses:
            agg = a.get("aggregated", {})
            score = agg.get("avg_score", 0.0)
            if score > best_score:
                best_score = score
                best = a

        return {
            "id": f"bo_{uuid.uuid4().hex[:8]}",
            "found": True,
            "best_analysis_id": best["id"] if best else None,
            "best_score": best_score,
            "timestamp": time.time(),
        }

    # ── internal helpers ────────────────────────────────────
    def _analyze_one(self, item: dict) -> dict:
        score = item.get("score", 0.5)
        effects = item.get("effects", [])
        success = item.get("success", False)
        return {
            "scenario_id": item.get("scenario_id", "unknown"),
            "score": score,
            "effects_count": len(effects),
            "success": success,
            "risk_level": self._level_from_score(score),
        }

    def _level_from_score(self, score: float) -> str:
        if score >= 0.8:
            return "low"
        elif score >= 0.5:
            return "medium"
        elif score >= 0.2:
            return "high"
        return "critical"

    def _assess_risk(self, item: dict) -> dict:
        score = item.get("score", 0.5)
        return {
            "scenario_id": item.get("scenario_id", "unknown"),
            "level": self._level_from_score(score),
            "score": score,
            "mitigable": score >= 0.3,
        }

    def _aggregate(self, analysis: list) -> dict:
        if not analysis:
            return {"avg_score": 0.0, "total": 0, "success_rate": 0.0}
        total = len(analysis)
        avg = sum(a.get("score", 0) for a in analysis) / total
        success_count = sum(1 for a in analysis if a.get("success"))
        return {
            "avg_score": round(avg, 3),
            "total": total,
            "success_rate": round(success_count / total, 3),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "outcome_analysis_engine",
            "status": "ok",
            "total_analyses": len(self._analyses),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._analyses.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("OutcomeAnalysisEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._analyses) > 5000:
            self._analyses = self._analyses[-2500:]
