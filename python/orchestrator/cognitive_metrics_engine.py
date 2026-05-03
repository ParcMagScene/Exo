"""
EXO v24 — CognitiveMetricsEngine
Mesure les performances cognitives d'EXO : latence, charge,
cohérence, stabilité, efficacité.

API:
  metrics_update(metric: dict)  → dict
  metrics_compute()             → dict
  metrics_report()              → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("cognitive_metrics_engine")


class CognitiveMetricsEngine:
    """Moteur de métriques cognitives EXO v24."""

    METRIC_TYPES = {
        "latency_agent", "latency_layer", "latency_task",
        "cognitive_load", "coherence", "stability", "efficiency",
    }

    def __init__(self, governance=None):
        self._governance = governance

        self._metrics: dict[str, list[float]] = {}
        self._history: list[dict] = []
        self._stats = {
            "updated": 0,
            "computed": 0,
            "reported": 0,
        }

    # ── metrics_update ──────────────────────────────────────
    def metrics_update(self, metric: dict) -> dict:
        """Mettre à jour une métrique."""
        self._stats["updated"] += 1

        name = metric.get("name", "unknown")
        value = metric.get("value", 0.0)
        source = metric.get("source", "unknown")

        if name not in self._metrics:
            self._metrics[name] = []
        self._metrics[name].append(value)

        # Limiter l'historique par métrique
        if len(self._metrics[name]) > 1000:
            self._metrics[name] = self._metrics[name][-500:]

        record = {
            "id": f"mu_{uuid.uuid4().hex[:8]}",
            "name": name,
            "value": value,
            "source": source,
            "valid": name in self.METRIC_TYPES,
            "timestamp": time.time(),
        }
        self._history.append(record)
        self._trim()

        return {
            "id": record["id"],
            "updated": True,
            "name": name,
            "value": value,
            "samples": len(self._metrics[name]),
            "timestamp": record["timestamp"],
        }

    # ── metrics_compute ─────────────────────────────────────
    def metrics_compute(self) -> dict:
        """Calculer les métriques agrégées."""
        self._stats["computed"] += 1

        computed = {}
        for name, values in self._metrics.items():
            if not values:
                continue
            n = len(values)
            avg = sum(values) / n
            mn = min(values)
            mx = max(values)
            computed[name] = {
                "avg": round(avg, 4),
                "min": round(mn, 4),
                "max": round(mx, 4),
                "samples": n,
                "last": round(values[-1], 4),
            }

        return {
            "id": f"mc_{uuid.uuid4().hex[:8]}",
            "computed": True,
            "metrics_count": len(computed),
            "metrics": computed,
            "timestamp": time.time(),
        }

    # ── metrics_report ──────────────────────────────────────
    def metrics_report(self) -> dict:
        """Générer un rapport de métriques."""
        self._stats["reported"] += 1

        computed = self.metrics_compute()
        metrics = computed.get("metrics", {})

        # Score de santé global
        health_score = 1.0
        for name, data in metrics.items():
            if "latency" in name and data["avg"] > 1.0:
                health_score -= 0.1
            if name == "coherence" and data["avg"] < 0.5:
                health_score -= 0.2
            if name == "stability" and data["avg"] < 0.5:
                health_score -= 0.15

        health_score = round(max(0.0, min(1.0, health_score)), 3)

        return {
            "id": f"mr_{uuid.uuid4().hex[:8]}",
            "reported": True,
            "health_score": health_score,
            "metrics_count": len(metrics),
            "metrics": metrics,
            "total_samples": sum(m["samples"] for m in metrics.values()),
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "cognitive_metrics_engine",
            "status": "ok",
            "metrics_tracked": len(self._metrics),
            "total_history": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._metrics.clear()
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("CognitiveMetricsEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-2500:]
