"""
EXO v8.2 — Intégration v9 Pipeline

Bridge entre le pipeline ultra-low latency et le système v9 :
- Logs structurés par étage (via LogManager)
- Métriques pipeline (via MetricsManager)
- Traces distribuées avec spans STT/LLM/TTS (via TraceManager)
- Health check pipeline pour le superviseur
- SecurityManager contrôle d'accès

Utilise les managers de python/shared/.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

log = logging.getLogger("pipeline.v9")


class PipelineV9Integration:
    """Intégration du pipeline avec le système v9.

    Fournit une couche d'abstraction entre les modules pipeline v8.2
    et les managers v9 (logs, métriques, traces, erreurs, sécurité).
    """

    def __init__(self, service_name: str = "pipeline"):
        self._service_name = service_name
        self._log_mgr = None
        self._metrics_mgr = None
        self._trace_mgr = None
        self._error_mgr = None
        self._security_mgr = None

        # Initialiser les managers v9
        try:
            from shared.log_manager import LogManager
            self._log_mgr = LogManager(service_name)
        except ImportError:
            log.debug("LogManager non disponible")

        try:
            from shared.metrics_manager import MetricsManager
            self._metrics_mgr = MetricsManager(service_name)
        except ImportError:
            log.debug("MetricsManager non disponible")

        try:
            from shared.trace_manager import TraceManager
            self._trace_mgr = TraceManager(service_name)
        except ImportError:
            log.debug("TraceManager non disponible")

        try:
            from shared.error_manager import ErrorManager
            self._error_mgr = ErrorManager.instance()
        except ImportError:
            log.debug("ErrorManager non disponible")

        try:
            from shared.security_manager import SecurityManager
            self._security_mgr = SecurityManager.instance()
        except ImportError:
            log.debug("SecurityManager non disponible")

    # ── Métriques ────────────────────────────────────────────

    def record_latency(self, stage: str, latency_ms: float) -> None:
        """Enregistre la latence d'un étage."""
        if self._metrics_mgr:
            try:
                hist = self._metrics_mgr.histogram(f"{stage}_latency_ms")
                hist.observe(latency_ms)
            except Exception:
                pass

    def increment_counter(self, name: str, value: int = 1) -> None:
        """Incrémente un compteur."""
        if self._metrics_mgr:
            try:
                counter = self._metrics_mgr.counter(name)
                counter.inc(value)
            except Exception:
                pass

    def set_gauge(self, name: str, value: float) -> None:
        """Met à jour une jauge."""
        if self._metrics_mgr:
            try:
                gauge = self._metrics_mgr.gauge(name)
                gauge.set(value)
            except Exception:
                pass

    def get_metrics(self) -> dict[str, Any]:
        """Exporte toutes les métriques."""
        if self._metrics_mgr:
            try:
                return self._metrics_mgr.export()
            except Exception:
                pass
        return {}

    # ── Traces ───────────────────────────────────────────────

    def begin_span(self, name: str, interaction_id: str = "") -> Any:
        """Démarre un span de trace."""
        if self._trace_mgr:
            try:
                return self._trace_mgr.begin_span(
                    name=name,
                    attributes={"interaction_id": interaction_id},
                )
            except Exception:
                pass
        return None

    def end_span(self, span: Any, **attributes: Any) -> None:
        """Termine un span de trace."""
        if self._trace_mgr and span:
            try:
                self._trace_mgr.end_span(span, attributes=attributes)
            except Exception:
                pass

    def get_traces(self) -> list[dict[str, Any]]:
        """Exporte les traces récentes."""
        if self._trace_mgr:
            try:
                return self._trace_mgr.export()
            except Exception:
                pass
        return []

    # ── Logs structurés ──────────────────────────────────────

    def log_event(self, level: str, event: str, **data: Any) -> None:
        """Log un événement structuré."""
        if self._log_mgr:
            try:
                self._log_mgr.log(level, event, **data)
            except Exception:
                pass
        # Fallback vers logging standard
        getattr(log, level.lower(), log.info)(f"{event}: {data}" if data else event)

    # ── Erreurs ──────────────────────────────────────────────

    def record_error(self, error: Exception, context: str = "") -> None:
        """Enregistre une erreur."""
        if self._error_mgr:
            try:
                from shared.error_manager import ExoError, ErrorCategory
                if isinstance(error, ExoError):
                    self._error_mgr.handle(error)
                else:
                    exo_err = ExoError(
                        str(error),
                        category=ErrorCategory.INTERNAL,
                        context={"source": context},
                    )
                    self._error_mgr.handle(exo_err)
            except Exception:
                pass
        log.error(f"[{context}] {type(error).__name__}: {error}")

    def get_errors(self) -> list[dict[str, Any]]:
        """Retourne les erreurs récentes."""
        if self._error_mgr:
            try:
                return self._error_mgr.recent_errors()
            except Exception:
                pass
        return []

    # ── Sécurité ─────────────────────────────────────────────

    def check_access(self, resource: str, action: str = "read") -> bool:
        """Vérifie l'accès à une ressource."""
        if self._security_mgr:
            try:
                return self._security_mgr.check_access(resource, action)
            except Exception:
                pass
        return True  # permissif par défaut si pas de SecurityManager

    # ── Health Check ─────────────────────────────────────────

    def health_check(self, components: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Health check pour le superviseur.

        Args:
            components: Dict nom → état de chaque composant pipeline.

        Returns:
            Dict avec status global et détails.
        """
        result: dict[str, Any] = {
            "service": self._service_name,
            "status": "healthy",
            "timestamp": time.time(),
        }

        if components:
            result["components"] = components
            # Si un composant est FAILED, le pipeline est unhealthy
            states = [c.get("state", "HEALTHY") for c in components.values()]
            if "FAILED" in states:
                result["status"] = "unhealthy"
            elif "DEGRADED" in states:
                result["status"] = "degraded"

        # Ajouter métriques résumées
        result["metrics"] = self.get_metrics()

        return result
