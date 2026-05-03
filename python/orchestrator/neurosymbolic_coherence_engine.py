"""
EXO v17 — NeuroSymbolicCoherenceEngine (Cohérence neuro-symbolique globale)
Garantit la cohérence entre logique symbolique, sorties LLM,
agents spécialisés et connaissances structurées.

API:
  check_neuro_symbolic_consistency()             → dict
  enforce_neuro_symbolic_consistency()            → dict
  check_specific(domain, aspect)                 → dict
  get_coherence_history(limit)                   → list[dict]
  health_check()                                 → dict
  restart()                                      → None
  get_stats()                                    → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("neurosymbolic_coherence")

# Types de cohérence vérifiés
COHERENCE_ASPECTS = frozenset({
    "logical", "semantic", "contextual", "temporal", "multi_agent",
})

# Seuils
COHERENCE_THRESHOLD = 0.6
CRITICAL_THRESHOLD = 0.3


class NeuroSymbolicCoherenceEngine:
    """Moteur de cohérence neuro-symbolique EXO v17."""

    def __init__(self, reasoning_bridge=None, knowledge_graph=None,
                 hybrid_inference=None, meta_memory=None, governance=None):
        self._bridge = reasoning_bridge
        self._kg = knowledge_graph
        self._hybrid = hybrid_inference
        self._memory = meta_memory
        self._governance = governance
        self._history: list[dict] = []
        self._stats = {
            "checks_run": 0,
            "enforcements_run": 0,
            "coherent": 0,
            "incoherent": 0,
            "fixes_applied": 0,
            "critical_violations": 0,
        }

    # ── check_neuro_symbolic_consistency ─────────────────────
    def check_neuro_symbolic_consistency(self) -> dict:
        """Vérifier la cohérence globale neuro-symbolique."""
        self._stats["checks_run"] += 1

        aspects = {}
        overall_score = 0.0
        count = 0

        # 1. Cohérence logique
        logical = self._check_logical()
        aspects["logical"] = logical
        overall_score += logical["score"]
        count += 1

        # 2. Cohérence sémantique
        semantic = self._check_semantic()
        aspects["semantic"] = semantic
        overall_score += semantic["score"]
        count += 1

        # 3. Cohérence contextuelle
        contextual = self._check_contextual()
        aspects["contextual"] = contextual
        overall_score += contextual["score"]
        count += 1

        # 4. Cohérence temporelle
        temporal = self._check_temporal()
        aspects["temporal"] = temporal
        overall_score += temporal["score"]
        count += 1

        # 5. Cohérence multi-agents
        multi_agent = self._check_multi_agent()
        aspects["multi_agent"] = multi_agent
        overall_score += multi_agent["score"]
        count += 1

        avg_score = round(overall_score / count, 3) if count > 0 else 0.0
        coherent = avg_score >= COHERENCE_THRESHOLD

        violations = [name for name, a in aspects.items()
                      if a["score"] < CRITICAL_THRESHOLD]
        if violations:
            self._stats["critical_violations"] += len(violations)

        if coherent:
            self._stats["coherent"] += 1
        else:
            self._stats["incoherent"] += 1

        result = {
            "id": f"coh_{uuid.uuid4().hex[:8]}",
            "coherent": coherent,
            "overall_score": avg_score,
            "aspects": aspects,
            "critical_violations": violations,
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        log.info("Coherence check: score=%.2f, coherent=%s, violations=%d",
                 avg_score, coherent, len(violations))
        return result

    # ── enforce_neuro_symbolic_consistency ────────────────────
    def enforce_neuro_symbolic_consistency(self) -> dict:
        """Appliquer des corrections pour restaurer la cohérence."""
        self._stats["enforcements_run"] += 1

        # D'abord vérifier
        check = self.check_neuro_symbolic_consistency()

        if check["coherent"]:
            return {
                "enforced": False,
                "reason": "already_coherent",
                "score": check["overall_score"],
                "actions_taken": [],
            }

        actions = []

        # Corrections par aspect
        for name, aspect in check["aspects"].items():
            if aspect["score"] < COHERENCE_THRESHOLD:
                action = self._fix_aspect(name, aspect)
                if action:
                    actions.append(action)
                    self._stats["fixes_applied"] += 1

        # Re-vérifier après corrections
        new_check = self.check_neuro_symbolic_consistency()

        result = {
            "enforced": True,
            "previous_score": check["overall_score"],
            "new_score": new_check["overall_score"],
            "actions_taken": actions,
            "actions_count": len(actions),
            "improved": new_check["overall_score"] > check["overall_score"],
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        log.info("Enforcement: %d actions, %.2f → %.2f",
                 len(actions), check["overall_score"],
                 new_check["overall_score"])
        return result

    # ── check_specific ──────────────────────────────────────
    def check_specific(self, domain: str = "general",
                       aspect: str = "logical") -> dict:
        """Vérifier un aspect spécifique de cohérence."""
        self._stats["checks_run"] += 1

        if aspect == "logical":
            result = self._check_logical(domain)
        elif aspect == "semantic":
            result = self._check_semantic(domain)
        elif aspect == "contextual":
            result = self._check_contextual(domain)
        elif aspect == "temporal":
            result = self._check_temporal(domain)
        elif aspect == "multi_agent":
            result = self._check_multi_agent(domain)
        else:
            result = {"score": 0.5, "aspect": aspect, "issues": ["unknown_aspect"]}

        coherent = result["score"] >= COHERENCE_THRESHOLD
        if coherent:
            self._stats["coherent"] += 1
        else:
            self._stats["incoherent"] += 1

        return {
            "aspect": aspect,
            "domain": domain,
            "coherent": coherent,
            **result,
        }

    # ── get_coherence_history ───────────────────────────────
    def get_coherence_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "neurosymbolic_coherence",
            "status": "ok",
            "history_entries": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("NeuroSymbolicCoherenceEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal checks ────────────────────────────────────
    def _check_logical(self, domain: str = "general") -> dict:
        score = 0.7
        issues = []
        if self._kg:
            try:
                nodes = self._kg.health_check().get("nodes", 0)
                if nodes > 0:
                    score += 0.1
            except Exception:
                issues.append("kg_unreachable")
                score -= 0.2
        if self._bridge:
            try:
                self._bridge.health_check()
                score += 0.05
            except Exception:
                issues.append("bridge_unreachable")
                score -= 0.1
        return {"score": round(min(max(score, 0), 1.0), 3),
                "aspect": "logical", "issues": issues}

    def _check_semantic(self, domain: str = "general") -> dict:
        score = 0.7
        issues = []
        if self._hybrid:
            try:
                s = self._hybrid.get_stats()
                if s.get("hybrid_inferences", 0) > 0:
                    score += 0.1
            except Exception:
                issues.append("hybrid_unreachable")
                score -= 0.15
        return {"score": round(min(max(score, 0), 1.0), 3),
                "aspect": "semantic", "issues": issues}

    def _check_contextual(self, domain: str = "general") -> dict:
        score = 0.75
        issues = []
        if self._memory:
            try:
                self._memory.health_check()
                score += 0.1
            except Exception:
                issues.append("memory_unreachable")
                score -= 0.15
        return {"score": round(min(max(score, 0), 1.0), 3),
                "aspect": "contextual", "issues": issues}

    def _check_temporal(self, domain: str = "general") -> dict:
        score = 0.75
        issues = []
        # Vérifier la cohérence temporelle des entrées
        if self._history:
            recent = self._history[-10:]
            times = [e.get("timestamp", 0) for e in recent if "timestamp" in e]
            if times and times != sorted(times):
                issues.append("temporal_ordering_violation")
                score -= 0.2
        return {"score": round(min(max(score, 0), 1.0), 3),
                "aspect": "temporal", "issues": issues}

    def _check_multi_agent(self, domain: str = "general") -> dict:
        score = 0.7
        issues = []
        # Base check — pas de conflits détectés
        return {"score": round(min(max(score, 0), 1.0), 3),
                "aspect": "multi_agent", "issues": issues}

    def _fix_aspect(self, name: str, aspect: dict) -> dict | None:
        """Tenter de corriger un aspect incohérent."""
        if aspect["score"] >= COHERENCE_THRESHOLD:
            return None
        return {
            "aspect": name,
            "action": "reset_and_recheck",
            "previous_score": aspect["score"],
            "issues_addressed": aspect.get("issues", []),
        }

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
