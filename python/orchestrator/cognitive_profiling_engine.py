"""
EXO v19 — CognitiveProfilingEngine
Mesure les performances cognitives : latence par agent/couche/tâche,
charge, points chauds, goulots d'étranglement.

API:
  profile_system()              → dict
  profile_agent(agent: dict)    → dict
  profile_layer(layer: dict)    → dict
  health_check()                → dict
  restart()                     → None
  get_stats()                   → dict
"""

import logging
import time
import uuid

log = logging.getLogger("cognitive_profiling_engine")


class CognitiveProfilingEngine:
    """Moteur de profilage cognitif EXO v19."""

    def __init__(self, layer_stack=None, macro_layer=None,
                 micro_layer=None, meta_optimizer=None):
        self._stack = layer_stack
        self._macro = macro_layer
        self._micro = micro_layer
        self._meta = meta_optimizer

        self._profiles: list[dict] = []
        self._stats = {
            "system_profiles": 0,
            "agent_profiles": 0,
            "layer_profiles": 0,
        }

    # ── profile_system ──────────────────────────────────────
    def profile_system(self) -> dict:
        """Profiler le système cognitif global."""
        self._stats["system_profiles"] += 1

        layers_info = []
        agents_info = []
        hotspots = []

        # Profiler les couches
        if self._stack:
            try:
                layers = self._stack.list_layers()
                for L in layers:
                    push = L.get("push_count", 0)
                    pull = L.get("pull_count", 0)
                    info = {
                        "name": L.get("name", "?"),
                        "push_count": push,
                        "pull_count": pull,
                        "throughput": push + pull,
                    }
                    layers_info.append(info)
                    if push + pull > 100:
                        hotspots.append({
                            "component": "layer",
                            "name": L.get("name", "?"),
                            "throughput": push + pull,
                        })
            except Exception:
                log.debug("layer profiling failed", exc_info=True)

        # Profiler les micro-agents
        if self._micro:
            try:
                micros = self._micro.list_micros()
                for m in micros:
                    info = {
                        "name": m.get("name", "?"),
                        "executions": m.get("executions", 0),
                        "failures": m.get("failures", 0),
                        "avg_latency_ms": m.get("avg_latency_ms", 0.0),
                    }
                    agents_info.append(info)
                    if m.get("avg_latency_ms", 0) > 80:
                        hotspots.append({
                            "component": "micro_agent",
                            "name": m.get("name", "?"),
                            "avg_latency_ms": m["avg_latency_ms"],
                        })
            except Exception:
                log.debug("micro-agent profiling failed", exc_info=True)

        # Profiler les macro-agents
        if self._macro:
            try:
                macros = self._macro.list_macros()
                for m in macros:
                    agents_info.append({
                        "name": m.get("name", "?"),
                        "type": "macro",
                        "tasks_handled": m.get("tasks_handled", 0),
                    })
            except Exception:
                log.debug("macro-agent profiling failed", exc_info=True)

        record = {
            "id": f"ps_{uuid.uuid4().hex[:8]}",
            "profiled": True,
            "layers": layers_info,
            "agents": agents_info,
            "hotspots": hotspots,
            "total_layers": len(layers_info),
            "total_agents": len(agents_info),
            "total_hotspots": len(hotspots),
            "timestamp": time.time(),
        }
        self._profiles.append(record)
        self._trim()
        return record

    # ── profile_agent ───────────────────────────────────────
    def profile_agent(self, agent: dict) -> dict:
        """Profiler un agent spécifique."""
        self._stats["agent_profiles"] += 1

        name = agent.get("name", "unknown")
        agent_type = agent.get("type", "micro")

        metrics = {
            "name": name,
            "type": agent_type,
            "executions": agent.get("executions", 0),
            "failures": agent.get("failures", 0),
            "avg_latency_ms": agent.get("avg_latency_ms", 0.0),
            "max_latency_ms": agent.get("max_latency_ms", 0.0),
            "memory_usage_mb": agent.get("memory_usage_mb", 0.0),
        }

        # Calculer l'efficacité
        execs = metrics["executions"]
        fails = metrics["failures"]
        efficiency = (execs - fails) / max(execs, 1)

        bottleneck = metrics["avg_latency_ms"] > 100 or efficiency < 0.8

        return {
            "id": f"pa_{uuid.uuid4().hex[:8]}",
            "profiled": True,
            "agent": name,
            "metrics": metrics,
            "efficiency": round(efficiency, 4),
            "is_bottleneck": bottleneck,
            "recommendations": (
                ["Optimiser la latence", "Réduire le taux d'échec"]
                if bottleneck else ["Agent performant"]
            ),
            "timestamp": time.time(),
        }

    # ── profile_layer ───────────────────────────────────────
    def profile_layer(self, layer: dict) -> dict:
        """Profiler une couche cognitive spécifique."""
        self._stats["layer_profiles"] += 1

        name = layer.get("name", "unknown")
        push = layer.get("push_count", 0)
        pull = layer.get("pull_count", 0)

        utilization = pull / max(push, 1)
        is_underutilized = push > 10 and utilization < 0.1

        return {
            "id": f"pl_{uuid.uuid4().hex[:8]}",
            "profiled": True,
            "layer": name,
            "push_count": push,
            "pull_count": pull,
            "utilization": round(utilization, 4),
            "is_underutilized": is_underutilized,
            "recommendations": (
                ["Couche sous-utilisée, envisager la fusion"]
                if is_underutilized else ["Utilisation normale"]
            ),
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "cognitive_profiling",
            "status": "ok",
            "profiles": len(self._profiles),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._profiles.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("CognitiveProfilingEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._profiles) > 5000:
            self._profiles = self._profiles[-5000:]
