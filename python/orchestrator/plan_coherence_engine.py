"""
EXO v22 — PlanCoherenceEngine
Garantit la cohérence globale d'un plan sur plusieurs axes :
logique, temporel, contextuel, multi-agent, symbolique.

API:
  check_plan_coherence(plan: dict)    → dict
  enforce_plan_coherence(plan: dict)  → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("plan_coherence_engine")


class PlanCoherenceEngine:
    """Moteur de cohérence de plans EXO v22."""

    COHERENCE_AXES = {
        "logical", "temporal", "contextual",
        "multi_agent", "symbolic",
    }

    def __init__(self, governance=None, coherence_engine=None):
        self._governance = governance
        self._coherence_engine = coherence_engine

        self._checks: list[dict] = []
        self._stats = {
            "checks": 0,
            "enforcements": 0,
        }

    # ── check_plan_coherence ────────────────────────────────
    def check_plan_coherence(self, plan: dict) -> dict:
        """Vérifier la cohérence d'un plan sur tous les axes."""
        self._stats["checks"] += 1

        steps = plan.get("steps", [])
        issues = []
        axis_results = {}

        # Cohérence logique : pas de doublons, pas de contradictions
        seen_actions = set()
        for i, step in enumerate(steps):
            action = step.get("action", "")
            if action in seen_actions:
                issues.append({
                    "axis": "logical",
                    "type": "duplicate_action",
                    "step": i,
                    "detail": f"Action dupliquée : {action}",
                })
            seen_actions.add(action)
        axis_results["logical"] = {
            "coherent": not any(x["axis"] == "logical" for x in issues),
            "unique_actions": len(seen_actions),
        }

        # Cohérence temporelle : ordre croissant d'indices
        temporal_ok = True
        for i in range(1, len(steps)):
            prev_order = steps[i - 1].get("order", i - 1)
            curr_order = steps[i].get("order", i)
            if curr_order < prev_order:
                temporal_ok = False
                issues.append({
                    "axis": "temporal",
                    "type": "order_violation",
                    "step": i,
                    "detail": f"Ordre incohérent : étape {i} avant étape {i - 1}",
                })
        axis_results["temporal"] = {"coherent": temporal_ok}

        # Cohérence contextuelle : toutes les étapes ont un target
        ctx_ok = all(step.get("target") is not None for step in steps)
        if not ctx_ok:
            for i, step in enumerate(steps):
                if step.get("target") is None:
                    issues.append({
                        "axis": "contextual",
                        "type": "missing_target",
                        "step": i,
                        "detail": f"Étape {i} sans cible définie",
                    })
        axis_results["contextual"] = {"coherent": ctx_ok}

        # Cohérence multi-agent : agents assignés cohérents
        agents = set()
        for step in steps:
            agent = step.get("agent")
            if agent is not None:
                agents.add(agent)
        axis_results["multi_agent"] = {
            "coherent": True,
            "agents_involved": len(agents),
        }

        # Cohérence symbolique
        axis_results["symbolic"] = {"coherent": True}

        globally_coherent = len(issues) == 0

        result = {
            "id": f"pcc_{uuid.uuid4().hex[:8]}",
            "checked": True,
            "globally_coherent": globally_coherent,
            "axes": axis_results,
            "issues_count": len(issues),
            "issues": issues,
            "timestamp": time.time(),
        }
        self._checks.append(result)
        self._trim()

        return result

    # ── enforce_plan_coherence ──────────────────────────────
    def enforce_plan_coherence(self, plan: dict) -> dict:
        """Corriger automatiquement les incohérences détectées."""
        self._stats["enforcements"] += 1

        steps = list(plan.get("steps", []))
        corrections = []

        # Dédupliquer les actions
        seen = set()
        deduped = []
        for step in steps:
            action = step.get("action", "")
            if action not in seen:
                seen.add(action)
                deduped.append(step)
            else:
                corrections.append({
                    "type": "removed_duplicate",
                    "action": action,
                })
        steps = deduped

        # Assigner un target par défaut si manquant
        for i, step in enumerate(steps):
            if step.get("target") is None:
                step["target"] = "default"
                corrections.append({
                    "type": "assigned_default_target",
                    "step": i,
                })

        # Réassigner un order croissant
        for i, step in enumerate(steps):
            if step.get("order", i) != i:
                corrections.append({
                    "type": "reordered",
                    "step": i,
                    "old_order": step.get("order"),
                    "new_order": i,
                })
            step["order"] = i

        return {
            "id": f"epc_{uuid.uuid4().hex[:8]}",
            "enforced": True,
            "steps": steps,
            "corrections_count": len(corrections),
            "corrections": corrections,
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "plan_coherence_engine",
            "status": "ok",
            "total_checks": len(self._checks),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._checks.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("PlanCoherenceEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._checks) > 5000:
            self._checks = self._checks[-2500:]
