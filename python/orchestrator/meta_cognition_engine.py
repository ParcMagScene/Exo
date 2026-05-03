"""
EXO v15 — MetaCognitionEngine (Méta-cognition avancée)
Auto-réflexion, méta-raisonnement, auto-cohérence, auto-critique,
auto-correction.

API:
  reflect(trace)                   → dict
  meta_reason(trace)               → dict
  enforce_self_consistency(state)   → dict
  self_critique(decision)          → dict
  self_correct(issue)              → dict
  get_reflections(limit)           → list[dict]
  health_check()                   → dict
  restart()                        → None
  get_stats()                      → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("meta_cognition_engine")


class MetaCognitionEngine:
    """Méta-cognition avancée EXO v15."""

    def __init__(self, meta_memory=None, governance=None):
        self._memory = meta_memory
        self._governance = governance
        self._reflections: list[dict] = []
        self._stats = {
            "reflections": 0,
            "meta_reasonings": 0,
            "consistency_checks": 0,
            "critiques": 0,
            "corrections": 0,
        }

    # ── reflect ─────────────────────────────────────────────
    def reflect(self, trace: dict) -> dict:
        """Auto-réflexion sur un processus de raisonnement."""
        self._stats["reflections"] += 1
        ref_id = f"ref_{uuid.uuid4().hex[:8]}"

        steps = trace.get("steps", [])
        observations = []

        # Analyse de complexité
        complexity = len(steps)
        if complexity > 5:
            observations.append({
                "type": "complexity",
                "detail": f"Raisonnement complexe ({complexity} étapes)",
                "suggestion": "Décomposer en sous-problèmes",
            })

        # Analyse de confiance
        confidences = [s.get("confidence", 0.5) for s in steps]
        avg_conf = sum(confidences) / max(len(confidences), 1)
        if avg_conf < 0.6:
            observations.append({
                "type": "low_confidence",
                "detail": f"Confiance moyenne faible : {avg_conf:.2f}",
                "suggestion": "Chercher des preuves supplémentaires",
            })

        # Analyse de biais
        domains = [s.get("domain", "") for s in steps if s.get("domain")]
        if len(set(domains)) == 1 and len(steps) > 2:
            observations.append({
                "type": "domain_bias",
                "detail": f"Biais domaine : tout dans '{domains[0]}'",
                "suggestion": "Considérer d'autres domaines",
            })

        reflection = {
            "id": ref_id,
            "type": "reflection",
            "trace_length": complexity,
            "avg_confidence": round(avg_conf, 3),
            "observations": observations,
            "quality": "good" if not observations else "needs_review",
            "timestamp": time.time(),
        }
        self._reflections.append(reflection)
        return reflection

    # ── meta_reason ─────────────────────────────────────────
    def meta_reason(self, trace: dict) -> dict:
        """Méta-raisonnement : raisonner sur le raisonnement."""
        self._stats["meta_reasonings"] += 1
        mr_id = f"mr_{uuid.uuid4().hex[:8]}"

        steps = trace.get("steps", [])
        reasoning_types = [s.get("type", "unknown") for s in steps]

        analysis = {
            "id": mr_id,
            "type": "meta_reasoning",
            "reasoning_types_used": list(set(reasoning_types)),
            "depth": len(steps),
            "has_logical": "logical" in reasoning_types,
            "has_causal": "causal" in reasoning_types,
            "has_temporal": "temporal" in reasoning_types,
            "completeness": min(len(set(reasoning_types)) / 3.0, 1.0),
            "recommendation": "",
            "timestamp": time.time(),
        }

        missing = []
        for rt in ["logical", "causal", "temporal"]:
            if rt not in reasoning_types:
                missing.append(rt)
        if missing:
            analysis["recommendation"] = (
                f"Enrichir avec : {', '.join(missing)}")
        else:
            analysis["recommendation"] = "Raisonnement complet"

        self._reflections.append(analysis)
        return analysis

    # ── enforce_self_consistency ─────────────────────────────
    def enforce_self_consistency(self, state: dict) -> dict:
        """Vérifier et renforcer l'auto-cohérence."""
        self._stats["consistency_checks"] += 1
        sc_id = f"sc_{uuid.uuid4().hex[:8]}"

        conflicts = []
        beliefs = state.get("beliefs", {})
        decisions = state.get("decisions", [])

        # Check beliefs for contradictions
        belief_keys = list(beliefs.keys())
        for i, k1 in enumerate(belief_keys):
            for k2 in belief_keys[i + 1:]:
                v1 = beliefs[k1]
                v2 = beliefs[k2]
                if (k1.startswith("not_") and k1[4:] == k2) or \
                   (k2.startswith("not_") and k2[4:] == k1):
                    conflicts.append({
                        "type": "contradiction",
                        "belief_a": k1,
                        "belief_b": k2,
                        "detail": "Croyances contradictoires",
                    })

        # Check decisions consistency
        seen_targets = {}
        for d in decisions:
            target = d.get("target", "")
            action = d.get("action", "")
            if target in seen_targets and seen_targets[target] != action:
                conflicts.append({
                    "type": "decision_conflict",
                    "target": target,
                    "action_a": seen_targets[target],
                    "action_b": action,
                })
            seen_targets[target] = action

        result = {
            "id": sc_id,
            "type": "self_consistency",
            "consistent": len(conflicts) == 0,
            "conflicts": conflicts,
            "beliefs_checked": len(beliefs),
            "decisions_checked": len(decisions),
            "timestamp": time.time(),
        }
        self._reflections.append(result)
        return result

    # ── self_critique ───────────────────────────────────────
    def self_critique(self, decision: dict) -> dict:
        """Auto-critique d'une décision."""
        self._stats["critiques"] += 1
        cr_id = f"crit_{uuid.uuid4().hex[:8]}"

        issues = []
        confidence = decision.get("confidence", 0.5)
        reasoning = decision.get("reasoning", "")

        if confidence < 0.5:
            issues.append("Confiance trop basse pour agir")
        if not reasoning:
            issues.append("Aucun raisonnement fourni")
        if not decision.get("alternatives"):
            issues.append("Aucune alternative considérée")

        critique = {
            "id": cr_id,
            "type": "self_critique",
            "decision": decision.get("action", "unknown"),
            "confidence": confidence,
            "issues": issues,
            "score": max(0, 1.0 - len(issues) * 0.33),
            "approved": len(issues) == 0,
            "timestamp": time.time(),
        }
        self._reflections.append(critique)
        return critique

    # ── self_correct ────────────────────────────────────────
    def self_correct(self, issue: dict) -> dict:
        """Auto-correction suite à un problème détecté."""
        self._stats["corrections"] += 1
        co_id = f"corr_{uuid.uuid4().hex[:8]}"

        issue_type = issue.get("type", "unknown")
        correction_map = {
            "contradiction": "remove_weaker_belief",
            "decision_conflict": "prefer_higher_confidence",
            "low_confidence": "seek_more_evidence",
            "domain_bias": "broaden_search",
            "complexity": "decompose",
        }
        action = correction_map.get(issue_type, "log_and_monitor")

        correction = {
            "id": co_id,
            "type": "self_correction",
            "issue_type": issue_type,
            "corrective_action": action,
            "status": "applied",
            "timestamp": time.time(),
        }
        self._reflections.append(correction)
        return correction

    # ── get_reflections ─────────────────────────────────────
    def get_reflections(self, limit: int = 20) -> list[dict]:
        return self._reflections[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "meta_cognition_engine",
            "status": "ok",
            "reflections_count": len(self._reflections),
        }

    def restart(self) -> None:
        self._reflections.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("MetaCognitionEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
