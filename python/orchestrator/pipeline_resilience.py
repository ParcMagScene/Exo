"""
EXO v8.2 — Résilience Pipeline

Résilience par module avec :
- Timeouts configurables par étage (STT 3s, LLM 10s, TTS 3s, Tools 5s, Domotique 3s)
- Retry avec backoff exponentiel par étage
- Fallbacks dégradés par module (STT offline, TTS voix secondaire, LLM cache)
- CircuitBreaker intégré (utilise shared/resilience.py)

Intégration v9 : logs structurés, métriques résilience.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Coroutine, Optional

log = logging.getLogger("pipeline.resilience")


class ModuleState(Enum):
    """État de santé d'un module."""
    HEALTHY = auto()
    DEGRADED = auto()
    FAILED = auto()


@dataclass
class ModuleConfig:
    """Configuration de résilience par module."""
    name: str
    timeout_s: float
    retries: int
    backoff_base: float = 0.5
    fallback: Optional[Callable[..., Coroutine]] = None
    fallback_label: str = ""

    def backoff_delay(self, attempt: int) -> float:
        """Calcule le délai de backoff pour un attempt donné."""
        return self.backoff_base * (2 ** attempt)


# Configuration par défaut par module
DEFAULT_MODULES: dict[str, dict[str, Any]] = {
    "stt": {"timeout_s": 3.0, "retries": 1, "backoff_base": 0.3,
            "fallback_label": "stt_offline"},
    "llm": {"timeout_s": 10.0, "retries": 2, "backoff_base": 0.5,
            "fallback_label": "llm_cache"},
    "tts": {"timeout_s": 3.0, "retries": 1, "backoff_base": 0.3,
            "fallback_label": "tts_secondary"},
    "tools": {"timeout_s": 5.0, "retries": 1, "backoff_base": 0.5,
              "fallback_label": "tools_cache"},
    "domotique": {"timeout_s": 3.0, "retries": 2, "backoff_base": 0.3,
                  "fallback_label": "domotique_cache"},
    "network": {"timeout_s": 5.0, "retries": 1, "backoff_base": 0.5,
                "fallback_label": "network_cache"},
}


@dataclass
class ModuleHealth:
    """Suivi de santé d'un module."""
    name: str
    state: ModuleState = ModuleState.HEALTHY
    total_calls: int = 0
    success_count: int = 0
    timeout_count: int = 0
    retry_count: int = 0
    fallback_count: int = 0
    error_count: int = 0
    last_error: str = ""
    last_latency_ms: float = 0.0
    consecutive_failures: int = 0

    def record_success(self, latency_ms: float) -> None:
        self.total_calls += 1
        self.success_count += 1
        self.last_latency_ms = latency_ms
        self.consecutive_failures = 0
        self.state = ModuleState.HEALTHY

    def record_timeout(self) -> None:
        self.total_calls += 1
        self.timeout_count += 1
        self.consecutive_failures += 1
        self._update_state()

    def record_retry(self) -> None:
        self.retry_count += 1

    def record_fallback(self) -> None:
        self.fallback_count += 1

    def record_error(self, error: str) -> None:
        self.total_calls += 1
        self.error_count += 1
        self.last_error = error
        self.consecutive_failures += 1
        self._update_state()

    def _update_state(self) -> None:
        if self.consecutive_failures >= 5:
            self.state = ModuleState.FAILED
        elif self.consecutive_failures >= 2:
            self.state = ModuleState.DEGRADED

    def snapshot(self) -> dict[str, Any]:
        total = self.total_calls or 1
        return {
            "name": self.name,
            "state": self.state.name,
            "total_calls": self.total_calls,
            "success_rate_pct": round(self.success_count / total * 100, 1),
            "timeout_count": self.timeout_count,
            "retry_count": self.retry_count,
            "fallback_count": self.fallback_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "last_latency_ms": round(self.last_latency_ms, 1),
            "consecutive_failures": self.consecutive_failures,
        }


class PipelineResilience:
    """Gestionnaire de résilience pour le pipeline.

    Applique timeouts, retries et fallbacks par module.

    Usage::

        resilience = PipelineResilience()
        result = await resilience.call("stt", stt_transcribe, audio_data)
    """

    def __init__(self, config_overrides: Optional[dict[str, dict[str, Any]]] = None):
        self._modules: dict[str, ModuleConfig] = {}
        self._health: dict[str, ModuleHealth] = {}
        self._fallbacks: dict[str, Callable[..., Coroutine]] = {}

        # Charger config par défaut + overrides
        merged = copy.deepcopy(DEFAULT_MODULES)
        if config_overrides:
            for name, overrides in config_overrides.items():
                if name in merged:
                    merged[name].update(overrides)
                else:
                    merged[name] = overrides

        for name, cfg in merged.items():
            self._modules[name] = ModuleConfig(
                name=name,
                timeout_s=cfg.get("timeout_s", 5.0),
                retries=cfg.get("retries", 1),
                backoff_base=cfg.get("backoff_base", 0.5),
                fallback_label=cfg.get("fallback_label", ""),
            )
            self._health[name] = ModuleHealth(name=name)

    def register_fallback(self, module_name: str, fallback_fn: Callable[..., Coroutine]) -> None:
        """Enregistre une fonction de fallback pour un module."""
        self._fallbacks[module_name] = fallback_fn
        if module_name in self._modules:
            self._modules[module_name].fallback = fallback_fn

    async def call(
        self,
        module_name: str,
        fn: Callable[..., Coroutine],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Appelle une fonction avec résilience (timeout + retry + fallback).

        Args:
            module_name: Nom du module (stt, llm, tts, etc.).
            fn: Fonction async à appeler.
            *args, **kwargs: Arguments passés à fn.

        Returns:
            Résultat de fn, ou du fallback en cas d'échec.

        Raises:
            Exception: Si toutes les tentatives et le fallback échouent.
        """
        cfg = self._modules.get(module_name)
        if cfg is None:
            # Module non configuré, appel direct
            return await fn(*args, **kwargs)

        health = self._health[module_name]
        last_exc: Optional[Exception] = None

        for attempt in range(cfg.retries + 1):
            if attempt > 0:
                health.record_retry()
                delay = cfg.backoff_delay(attempt - 1)
                log.info(f"[{module_name}] Retry #{attempt} après {delay:.1f}s")
                await asyncio.sleep(delay)

            t0 = time.perf_counter()
            try:
                result = await asyncio.wait_for(
                    fn(*args, **kwargs),
                    timeout=cfg.timeout_s,
                )
                latency = (time.perf_counter() - t0) * 1000
                health.record_success(latency)
                return result
            except asyncio.TimeoutError:
                health.record_timeout()
                log.warning(
                    f"[{module_name}] Timeout après {cfg.timeout_s}s "
                    f"(attempt {attempt + 1}/{cfg.retries + 1})"
                )
                last_exc = asyncio.TimeoutError(
                    f"{module_name} timeout after {cfg.timeout_s}s"
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                health.record_error(str(exc))
                log.warning(
                    f"[{module_name}] Erreur: {exc} "
                    f"(attempt {attempt + 1}/{cfg.retries + 1})"
                )
                last_exc = exc

        # Toutes les tentatives échouées → fallback
        fallback_fn = self._fallbacks.get(module_name) or cfg.fallback
        if fallback_fn:
            health.record_fallback()
            log.info(
                f"[{module_name}] Fallback '{cfg.fallback_label}' activé"
            )
            try:
                return await fallback_fn(*args, **kwargs)
            except Exception as fb_exc:
                log.error(f"[{module_name}] Fallback échoué: {fb_exc}")

        # Tout échoué
        if last_exc:
            raise last_exc
        raise RuntimeError(f"{module_name}: all attempts failed")

    def health(self, module_name: str) -> Optional[dict[str, Any]]:
        """Retourne la santé d'un module."""
        h = self._health.get(module_name)
        return h.snapshot() if h else None

    def all_health(self) -> dict[str, dict[str, Any]]:
        """Retourne la santé de tous les modules."""
        return {name: h.snapshot() for name, h in self._health.items()}

    @property
    def overall_state(self) -> ModuleState:
        """État global : HEALTHY si tout OK, DEGRADED si au moins un dégradé, FAILED si un failed."""
        states = [h.state for h in self._health.values()]
        if ModuleState.FAILED in states:
            return ModuleState.FAILED
        if ModuleState.DEGRADED in states:
            return ModuleState.DEGRADED
        return ModuleState.HEALTHY

    def metrics(self) -> dict[str, Any]:
        """Métriques de résilience globales."""
        return {
            "overall_state": self.overall_state.name,
            "modules": self.all_health(),
        }
