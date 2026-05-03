"""
EXO v24 — ObservabilityExplainabilityEngine
Explique métriques, anomalies, performance, cohérence, stabilité.

API:
  explain_metric(metric)     → dict
  explain_anomaly(anomaly)   → dict
  explain_performance()      → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("observability_explainability_engine")


class ObservabilityExplainabilityEngine:
    """Explicabilité d'observabilité EXO v24."""

    METRIC_DESCRIPTIONS = {
        "latency_agent": "Mesure le temps de réponse des agents cognitifs.",
        "latency_layer": "Mesure le temps de traitement par couche.",
        "latency_task": "Mesure le temps d'exécution des tâches.",
        "cognitive_load": "Charge cognitive totale du système.",
        "coherence": "Cohérence des décisions prises.",
        "stability": "Stabilité temporelle des réponses.",
        "efficiency": "Efficacité globale du traitement.",
    }

    ANOMALY_EXPLANATIONS = {
        "excessive_latency": "Le temps de traitement dépasse le seuil attendu. "
                             "Causes possibles : surcharge, dépendances lentes.",
        "incoherence": "Les décisions manquent de cohérence. "
                       "Causes possibles : conflits entre modules, données contradictoires.",
        "overload": "La charge cognitive dépasse le seuil de sécurité. "
                    "Causes possibles : trop de requêtes simultanées.",
        "useless_loop": "Des boucles de traitement inutiles ont été détectées. "
                        "Causes possibles : conditions d'arrêt manquantes.",
        "internal_conflict": "Conflit interne entre modules. "
                              "Causes possibles : objectifs contradictoires.",
    }

    def __init__(self, governance=None, metrics=None,
                 anomaly=None, performance=None):
        self._governance = governance
        self._metrics = metrics
        self._anomaly = anomaly
        self._performance = performance

        self._explanations: list[dict] = []
        self._stats = {
            "metrics_explained": 0,
            "anomalies_explained": 0,
            "performance_explained": 0,
        }

    # ── explain_metric ──────────────────────────────────────
    def explain_metric(self, metric: str) -> dict:
        """Expliquer une métrique cognitive."""
        self._stats["metrics_explained"] += 1

        description = self.METRIC_DESCRIPTIONS.get(
            metric, f"Métrique '{metric}' non documentée."
        )

        # Chercher les données actuelles
        current_value = None
        status = "unknown"
        if self._metrics and hasattr(self._metrics, "metrics_compute"):
            comp = self._metrics.metrics_compute()
            m_data = comp.get("metrics", {}).get(metric, {})
            if m_data:
                current_value = m_data.get("avg", None)
                samples = m_data.get("samples", 0)
                if samples == 0:
                    status = "no_data"
                elif metric in ("coherence", "stability", "efficiency"):
                    status = "ok" if (current_value or 0) > 0.5 else "warning"
                else:
                    status = "ok" if (current_value or 0) < 1.5 else "warning"

        record = {
            "id": f"exm_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "metric": metric,
            "description": description,
            "current_value": current_value,
            "status": status,
            "timestamp": time.time(),
        }
        self._explanations.append(record)
        self._trim()

        return record

    # ── explain_anomaly ─────────────────────────────────────
    def explain_anomaly(self, anomaly: str) -> dict:
        """Expliquer une anomalie cognitive."""
        self._stats["anomalies_explained"] += 1

        explanation = self.ANOMALY_EXPLANATIONS.get(
            anomaly, f"Anomalie '{anomaly}' non documentée."
        )

        # Degrés de gravité
        severity_map = {
            "excessive_latency": "medium",
            "incoherence": "high",
            "overload": "high",
            "useless_loop": "low",
            "internal_conflict": "critical",
        }
        severity = severity_map.get(anomaly, "unknown")

        # Recommandation
        recommendation_map = {
            "excessive_latency": "Vérifier les dépendances et réduire la charge.",
            "incoherence": "Auditer les conflits entre modules.",
            "overload": "Réduire le nombre de requêtes simultanées.",
            "useless_loop": "Vérifier les conditions d'arrêt des boucles.",
            "internal_conflict": "Résoudre les objectifs contradictoires entre modules.",
        }
        recommendation = recommendation_map.get(anomaly, "Analyse manuelle requise.")

        record = {
            "id": f"exa_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "anomaly": anomaly,
            "explanation": explanation,
            "severity": severity,
            "recommendation": recommendation,
            "timestamp": time.time(),
        }
        self._explanations.append(record)
        self._trim()

        return record

    # ── explain_performance ─────────────────────────────────
    def explain_performance(self) -> dict:
        """Expliquer l'état de performance global."""
        self._stats["performance_explained"] += 1

        perf_data = {}
        if self._performance and hasattr(self._performance, "analyze_performance"):
            perf_data = self._performance.analyze_performance()

        overall_status = perf_data.get("overall_status", "unknown")
        analyses = perf_data.get("analyses", {})

        explanations = []
        for name, an in analyses.items():
            status = an.get("status", "unknown")
            if status in ("warning", "critical"):
                explanations.append({
                    "metric": name,
                    "status": status,
                    "avg": an.get("avg"),
                    "description": self.METRIC_DESCRIPTIONS.get(
                        name, f"Métrique '{name}' non documentée."
                    ),
                })

        record = {
            "id": f"exp_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "overall_status": overall_status,
            "issues_count": len(explanations),
            "issues": explanations,
            "timestamp": time.time(),
        }
        self._explanations.append(record)
        self._trim()

        return record

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "observability_explainability_engine",
            "status": "ok",
            "total_explanations": len(self._explanations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._explanations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ObservabilityExplainabilityEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._explanations) > 5000:
            self._explanations = self._explanations[-2500:]
