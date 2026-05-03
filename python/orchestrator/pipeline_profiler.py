"""
EXO v8.2 — Profilage Complet du Pipeline

Profiler pour mesurer précisément chaque étage du pipeline :
- Timestamps par étage (STT, LLM, TTS, Tools)
- Latence bout-en-bout, temps du premier chunk TTS
- CPU/mémoire par phase
- Export structuré (JSON, logs)
- Rolling averages, percentiles (p50, p95, p99)

Intégration v9 : traces, métriques manager.
"""

from __future__ import annotations

import logging
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

log = logging.getLogger("pipeline.profiler")


@dataclass
class StageProfile:
    """Profil d'un étage individuel."""
    name: str
    t_start: float = 0.0
    t_end: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        if self.t_start and self.t_end:
            return (self.t_end - self.t_start) * 1000
        return 0.0

    def snapshot(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "duration_ms": round(self.duration_ms, 1),
            **self.metadata,
        }


@dataclass
class InteractionProfile:
    """Profil complet d'une interaction vocale."""
    interaction_id: str
    t_start: float = 0.0
    t_end: float = 0.0
    stages: dict[str, StageProfile] = field(default_factory=dict)

    def begin_stage(self, name: str) -> StageProfile:
        """Démarre le profilage d'un étage."""
        stage = StageProfile(name=name, t_start=time.perf_counter())
        self.stages[name] = stage
        return stage

    def end_stage(self, name: str, **metadata: Any) -> Optional[StageProfile]:
        """Termine le profilage d'un étage."""
        stage = self.stages.get(name)
        if stage:
            stage.t_end = time.perf_counter()
            stage.metadata.update(metadata)
            log.debug(
                f"[{self.interaction_id}] {name}: {stage.duration_ms:.0f}ms"
            )
        return stage

    @property
    def total_ms(self) -> float:
        if self.t_start and self.t_end:
            return (self.t_end - self.t_start) * 1000
        return 0.0

    @property
    def first_audio_ms(self) -> float:
        """Temps entre début interaction et premier chunk audio TTS."""
        tts = self.stages.get("tts")
        if tts and tts.metadata.get("first_chunk_at"):
            return (tts.metadata["first_chunk_at"] - self.t_start) * 1000
        return 0.0

    def snapshot(self) -> dict[str, Any]:
        return {
            "interaction_id": self.interaction_id,
            "total_ms": round(self.total_ms, 1),
            "first_audio_ms": round(self.first_audio_ms, 1),
            "stages": {k: v.snapshot() for k, v in self.stages.items()},
        }


class PipelineProfiler:
    """Profiler du pipeline complet avec historique et percentiles.

    Usage::

        profiler = PipelineProfiler()
        profile = profiler.begin("int-001")
        profile.begin_stage("stt")
        # ... STT ...
        profile.end_stage("stt", model="medium", backend="whispercpp")
        profile.begin_stage("llm")
        # ... LLM ...
        profile.end_stage("llm", tokens=150)
        profiler.end(profile)
    """

    def __init__(self, max_history: int = 200):
        self._max_history = max_history
        self._history: deque[dict[str, Any]] = deque(maxlen=max_history)
        self._current: Optional[InteractionProfile] = None
        self._total = 0

        # Latences par étage pour percentiles
        self._stage_latencies: dict[str, deque[float]] = {}

    def begin(self, interaction_id: str = "") -> InteractionProfile:
        """Démarre le profilage d'une interaction."""
        self._total += 1
        if not interaction_id:
            interaction_id = f"prof-{self._total:06d}"
        profile = InteractionProfile(
            interaction_id=interaction_id,
            t_start=time.perf_counter(),
        )
        self._current = profile
        return profile

    def end(self, profile: InteractionProfile) -> dict[str, Any]:
        """Termine et archive le profil d'une interaction."""
        profile.t_end = time.perf_counter()
        snapshot = profile.snapshot()
        self._history.append(snapshot)

        # Accumuler latences par étage
        for name, stage in profile.stages.items():
            if stage.duration_ms > 0:
                if name not in self._stage_latencies:
                    self._stage_latencies[name] = deque(maxlen=self._max_history)
                self._stage_latencies[name].append(stage.duration_ms)

        # Log résumé
        stages_str = " | ".join(
            f"{s.name}={s.duration_ms:.0f}ms" for s in profile.stages.values()
        )
        log.info(
            f"[{profile.interaction_id}] total={profile.total_ms:.0f}ms "
            f"first_audio={profile.first_audio_ms:.0f}ms | {stages_str}"
        )

        if self._current is profile:
            self._current = None
        return snapshot

    def percentiles(self, stage_name: str) -> dict[str, float]:
        """Calcule les percentiles pour un étage donné."""
        values = list(self._stage_latencies.get(stage_name, []))
        if not values:
            return {"count": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0, "min": 0, "max": 0}

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "count": n,
            "avg": round(statistics.mean(sorted_vals), 1),
            "p50": round(sorted_vals[int(n * 0.50)], 1) if n > 0 else 0,
            "p95": round(sorted_vals[min(int(n * 0.95), n - 1)], 1) if n > 0 else 0,
            "p99": round(sorted_vals[min(int(n * 0.99), n - 1)], 1) if n > 0 else 0,
            "min": round(sorted_vals[0], 1),
            "max": round(sorted_vals[-1], 1),
        }

    def all_percentiles(self) -> dict[str, dict[str, float]]:
        """Percentiles pour tous les étages."""
        return {name: self.percentiles(name) for name in self._stage_latencies}

    def summary(self) -> dict[str, Any]:
        """Résumé complet du profiler."""
        recent = list(self._history)[-20:]
        total_lats = [h["total_ms"] for h in recent if h["total_ms"] > 0]
        first_audio_lats = [h["first_audio_ms"] for h in recent if h["first_audio_ms"] > 0]

        def _avg(vals: list[float]) -> float:
            return round(statistics.mean(vals), 1) if vals else 0.0

        return {
            "total_interactions": self._total,
            "history_size": len(self._history),
            "avg_total_ms": _avg(total_lats),
            "avg_first_audio_ms": _avg(first_audio_lats),
            "stages": self.all_percentiles(),
        }

    def recent(self, n: int = 10) -> list[dict[str, Any]]:
        """Retourne les n derniers profils."""
        return list(self._history)[-n:]

    def metrics(self) -> dict[str, Any]:
        """Métriques pour le système de monitoring v9."""
        return self.summary()
