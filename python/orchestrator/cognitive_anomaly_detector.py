"""
EXO v24 — CognitiveAnomalyDetector
Détecte les comportements cognitifs anormaux :
latence excessive, incohérence, surcharge, boucle inutile, conflit interne.

API:
  detect_anomaly(event: dict)    → dict
  classify_anomaly(event: dict)  → dict
  explain_anomaly()              → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("cognitive_anomaly_detector")


class CognitiveAnomalyDetector:
    """Détecteur d'anomalies cognitives EXO v24."""

    ANOMALY_TYPES = {
        "excessive_latency", "incoherence", "overload",
        "useless_loop", "internal_conflict",
    }

    THRESHOLDS = {
        "excessive_latency": 2.0,
        "overload": 0.9,
        "incoherence": 0.3,
    }

    def __init__(self, governance=None, telemetry=None):
        self._governance = governance
        self._telemetry = telemetry

        self._anomalies: list[dict] = []
        self._stats = {
            "detected": 0,
            "classified": 0,
            "explained": 0,
        }

    # ── detect_anomaly ──────────────────────────────────────
    def detect_anomaly(self, event: dict) -> dict:
        """Détecter une anomalie dans un événement."""
        self._stats["detected"] += 1

        source = event.get("source", "unknown")
        metric = event.get("metric", "unknown")
        value = event.get("value", 0.0)
        context = event.get("context", {})

        anomaly_type = self._infer_type(metric, value)
        is_anomaly = anomaly_type is not None
        severity = self._severity(anomaly_type, value) if is_anomaly else "none"

        record = {
            "id": f"anom_{uuid.uuid4().hex[:8]}",
            "is_anomaly": is_anomaly,
            "type": anomaly_type or "none",
            "source": source,
            "metric": metric,
            "value": value,
            "severity": severity,
            "context": context,
            "timestamp": time.time(),
        }

        if is_anomaly:
            self._anomalies.append(record)
            self._trim()

        return {
            "id": record["id"],
            "detected": is_anomaly,
            "type": record["type"],
            "severity": severity,
            "source": source,
            "metric": metric,
            "value": value,
            "total_anomalies": len(self._anomalies),
            "timestamp": record["timestamp"],
        }

    # ── classify_anomaly ────────────────────────────────────
    def classify_anomaly(self, event: dict) -> dict:
        """Classifier une anomalie."""
        self._stats["classified"] += 1

        metric = event.get("metric", "unknown")
        value = event.get("value", 0.0)

        anomaly_type = self._infer_type(metric, value)
        severity = self._severity(anomaly_type, value) if anomaly_type else "none"
        category = self._categorize(anomaly_type)

        return {
            "id": f"acl_{uuid.uuid4().hex[:8]}",
            "classified": True,
            "type": anomaly_type or "none",
            "severity": severity,
            "category": category,
            "metric": metric,
            "value": value,
            "actionable": severity in ("high", "critical"),
            "timestamp": time.time(),
        }

    # ── explain_anomaly ─────────────────────────────────────
    def explain_anomaly(self) -> dict:
        """Expliquer les anomalies récentes."""
        self._stats["explained"] += 1

        recent = self._anomalies[-10:] if self._anomalies else []

        explanations = []
        for a in recent:
            explanations.append({
                "id": a["id"],
                "type": a["type"],
                "severity": a["severity"],
                "description": self._describe(a),
            })

        return {
            "id": f"aex_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "count": len(explanations),
            "explanations": explanations,
            "timestamp": time.time(),
        }

    # ── internal helpers ────────────────────────────────────
    def _infer_type(self, metric: str, value: float) -> str | None:
        if "latency" in metric and value > self.THRESHOLDS["excessive_latency"]:
            return "excessive_latency"
        if metric == "cognitive_load" and value > self.THRESHOLDS["overload"]:
            return "overload"
        if metric == "coherence" and value < self.THRESHOLDS["incoherence"]:
            return "incoherence"
        if metric == "loop_count" and value > 5:
            return "useless_loop"
        if metric == "conflict" and value > 0:
            return "internal_conflict"
        return None

    def _severity(self, anomaly_type: str | None, value: float) -> str:
        if anomaly_type is None:
            return "none"
        if anomaly_type == "excessive_latency":
            return "critical" if value > 5.0 else "high"
        if anomaly_type == "overload":
            return "critical" if value > 0.95 else "high"
        if anomaly_type == "incoherence":
            return "critical" if value < 0.1 else "high"
        if anomaly_type in ("useless_loop", "internal_conflict"):
            return "medium"
        return "low"

    def _categorize(self, anomaly_type: str | None) -> str:
        cats = {
            "excessive_latency": "performance",
            "overload": "performance",
            "incoherence": "logic",
            "useless_loop": "efficiency",
            "internal_conflict": "logic",
        }
        return cats.get(anomaly_type, "unknown") if anomaly_type else "none"

    def _describe(self, anomaly: dict) -> str:
        atype = anomaly.get("type", "unknown")
        source = anomaly.get("source", "?")
        value = anomaly.get("value", 0)
        descriptions = {
            "excessive_latency": f"Latence excessive ({value}s) détectée sur {source}",
            "overload": f"Surcharge cognitive ({value}) sur {source}",
            "incoherence": f"Incohérence détectée (score={value}) sur {source}",
            "useless_loop": f"Boucle inutile ({value} itérations) sur {source}",
            "internal_conflict": f"Conflit interne détecté sur {source}",
        }
        return descriptions.get(atype, f"Anomalie {atype} sur {source}")

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "cognitive_anomaly_detector",
            "status": "ok",
            "total_anomalies": len(self._anomalies),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._anomalies.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("CognitiveAnomalyDetector restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._anomalies) > 5000:
            self._anomalies = self._anomalies[-2500:]
