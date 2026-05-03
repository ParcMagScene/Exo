"""
EXO v19 — MetaOptimizer (optimiseur cognitif global)
Analyse et optimise l'ensemble du système cognitif EXO v9→v18.

API:
  analyze_system()            → dict
  detect_inefficiencies()     → dict
  propose_optimizations()     → dict
  get_optimization_history()  → list[dict]
  health_check()              → dict
  restart()                   → None
  get_stats()                 → dict
"""

import logging
import time
import uuid

log = logging.getLogger("meta_optimizer")


class MetaOptimizer:
    """Optimiseur cognitif global EXO v19."""

    def __init__(self, layer_stack=None, macro_layer=None,
                 micro_layer=None, priority_engine=None,
                 governance=None, meta_memory=None):
        self._stack = layer_stack
        self._macro = macro_layer
        self._micro = micro_layer
        self._priority = priority_engine
        self._governance = governance
        self._memory = meta_memory

        self._analyses: list[dict] = []
        self._optimizations: list[dict] = []
        self._stats = {
            "analyses": 0,
            "inefficiencies_detected": 0,
            "optimizations_proposed": 0,
        }

    # ── analyze_system ──────────────────────────────────────
    def analyze_system(self) -> dict:
        """Analyser les performances globales du système cognitif."""
        self._stats["analyses"] += 1

        findings = []

        # Analyser couches
        if self._stack:
            try:
                layers = self._stack.list_layers()
                for L in layers:
                    push = L.get("push_count", 0)
                    pull = L.get("pull_count", 0)
                    ratio = pull / max(push, 1)
                    findings.append({
                        "component": "layer",
                        "name": L.get("name", "?"),
                        "push_count": push,
                        "pull_count": pull,
                        "utilization_ratio": round(ratio, 3),
                        "status": "underutilized" if ratio < 0.1
                                  and push > 10 else "ok",
                    })
            except Exception:
                pass

        # Analyser macro-agents
        if self._macro:
            try:
                macros = self._macro.list_macros()
                for m in macros:
                    findings.append({
                        "component": "macro",
                        "name": m.get("name", "?"),
                        "tasks_handled": m.get("tasks_handled", 0),
                        "active": m.get("active", True),
                        "status": "idle" if m.get("tasks_handled", 0) == 0
                                  else "ok",
                    })
            except Exception:
                pass

        # Analyser micro-agents
        if self._micro:
            try:
                micros = self._micro.list_micros()
                for m in micros:
                    findings.append({
                        "component": "micro",
                        "name": m.get("name", "?"),
                        "executions": m.get("executions", 0),
                        "failures": m.get("failures", 0),
                        "avg_latency_ms": m.get("avg_latency_ms", 0.0),
                        "status": "slow" if m.get("avg_latency_ms", 0) > 100
                                  else "ok",
                    })
            except Exception:
                pass

        record = {
            "id": f"sa_{uuid.uuid4().hex[:8]}",
            "analyzed": True,
            "findings": findings,
            "total_components": len(findings),
            "issues": sum(1 for f in findings if f["status"] != "ok"),
            "timestamp": time.time(),
        }
        self._analyses.append(record)
        self._trim()
        return record

    # ── detect_inefficiencies ───────────────────────────────
    def detect_inefficiencies(self) -> dict:
        """Détecter les inefficacités, redondances et goulots."""
        self._stats["inefficiencies_detected"] += 1

        inefficiencies = []

        # Goulots : micro-agents lents
        if self._micro:
            try:
                micros = self._micro.list_micros()
                for m in micros:
                    if m.get("avg_latency_ms", 0) > 50:
                        inefficiencies.append({
                            "type": "bottleneck",
                            "component": "micro",
                            "name": m["name"],
                            "metric": "latency",
                            "value": m["avg_latency_ms"],
                            "threshold": 50,
                        })
                    if m.get("failures", 0) > 0 and m.get("executions", 0) > 0:
                        rate = m["failures"] / m["executions"]
                        if rate > 0.1:
                            inefficiencies.append({
                                "type": "high_failure_rate",
                                "component": "micro",
                                "name": m["name"],
                                "metric": "failure_rate",
                                "value": round(rate, 3),
                                "threshold": 0.1,
                            })
            except Exception:
                pass

        # Redondances : couches avec beaucoup de push mais pas de pull
        if self._stack:
            try:
                layers = self._stack.list_layers()
                for L in layers:
                    push = L.get("push_count", 0)
                    pull = L.get("pull_count", 0)
                    if push > 20 and pull == 0:
                        inefficiencies.append({
                            "type": "redundant_computation",
                            "component": "layer",
                            "name": L["name"],
                            "metric": "push_no_pull",
                            "push_count": push,
                            "pull_count": pull,
                        })
            except Exception:
                pass

        return {
            "id": f"di_{uuid.uuid4().hex[:8]}",
            "detected": True,
            "inefficiencies": inefficiencies,
            "total": len(inefficiencies),
            "bottlenecks": sum(1 for i in inefficiencies
                               if i["type"] == "bottleneck"),
            "redundancies": sum(1 for i in inefficiencies
                                if i["type"] == "redundant_computation"),
            "timestamp": time.time(),
        }

    # ── propose_optimizations ───────────────────────────────
    def propose_optimizations(self) -> dict:
        """Proposer des améliorations globales."""
        self._stats["optimizations_proposed"] += 1

        ineff = self.detect_inefficiencies()
        proposals = []

        for item in ineff.get("inefficiencies", []):
            if item["type"] == "bottleneck":
                proposals.append({
                    "target": item["name"],
                    "action": "optimize_latency",
                    "description": (
                        f"Réduire la latence de '{item['name']}' "
                        f"(actuellement {item['value']}ms > {item['threshold']}ms)"
                    ),
                    "priority": "high",
                    "estimated_gain_pct": 20,
                })
            elif item["type"] == "redundant_computation":
                proposals.append({
                    "target": item["name"],
                    "action": "remove_unused_push",
                    "description": (
                        f"Couche '{item['name']}' reçoit des données "
                        f"({item['push_count']} push) sans consommation"
                    ),
                    "priority": "medium",
                    "estimated_gain_pct": 10,
                })
            elif item["type"] == "high_failure_rate":
                proposals.append({
                    "target": item["name"],
                    "action": "improve_reliability",
                    "description": (
                        f"Micro-agent '{item['name']}' a un taux d'échec de "
                        f"{item['value']*100:.1f}%"
                    ),
                    "priority": "high",
                    "estimated_gain_pct": 15,
                })

        record = {
            "id": f"po_{uuid.uuid4().hex[:8]}",
            "proposed": True,
            "proposals": proposals,
            "total_proposals": len(proposals),
            "estimated_total_gain_pct": sum(
                p.get("estimated_gain_pct", 0) for p in proposals),
            "timestamp": time.time(),
        }
        self._optimizations.append(record)
        self._trim()
        return record

    # ── get_optimization_history ────────────────────────────
    def get_optimization_history(self) -> list[dict]:
        return self._optimizations[-30:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "meta_optimizer",
            "status": "ok",
            "analyses": len(self._analyses),
            "optimizations": len(self._optimizations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._analyses.clear()
        self._optimizations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("MetaOptimizer restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._analyses) > 5000:
            self._analyses = self._analyses[-5000:]
        if len(self._optimizations) > 5000:
            self._optimizations = self._optimizations[-5000:]
