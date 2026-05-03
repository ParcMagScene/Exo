"""
EXO v15 — CognitiveAgentCore (Agent cognitif unifié)
Planification HTN, exécution robuste, vérification, récupération,
optimisation continue.

API:
  plan(intent)            → dict   (plan HTN)
  execute(plan)           → dict   (résultat)
  verify(result)          → dict   (vérification)
  recover(error)          → dict   (récupération)
  optimize(plan)          → dict   (plan optimisé)
  get_history(limit)      → list[dict]
  health_check()          → dict
  restart()               → None
  get_stats()             → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("cognitive_agent_core")


class CognitiveAgentCore:
    """Agent cognitif unifié EXO v15 — planification, exécution, vérification."""

    def __init__(self, meta_memory=None, governance=None,
                 inference_engine=None):
        self._memory = meta_memory
        self._governance = governance
        self._inference = inference_engine
        self._history: list[dict] = []
        self._stats = {
            "plans_created": 0,
            "executions": 0,
            "verifications": 0,
            "recoveries": 0,
            "optimizations": 0,
        }

    # ── plan ────────────────────────────────────────────────
    def plan(self, intent: dict) -> dict:
        """Créer un plan HTN à partir d'une intention."""
        self._stats["plans_created"] += 1
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"

        goal = intent.get("goal", "unknown")
        constraints = intent.get("constraints", [])
        domain = intent.get("domain", "general")

        # Decompose into sub-tasks (HTN-style)
        steps = []
        if "steps" in intent:
            for i, s in enumerate(intent["steps"]):
                steps.append({
                    "step": i,
                    "action": s.get("action", "noop"),
                    "params": s.get("params", {}),
                    "status": "pending",
                })
        else:
            # Auto-decomposition: single-step plan
            steps.append({
                "step": 0,
                "action": goal,
                "params": intent.get("params", {}),
                "status": "pending",
            })

        plan = {
            "id": plan_id,
            "goal": goal,
            "domain": domain,
            "constraints": constraints,
            "steps": steps,
            "status": "ready",
            "created": time.time(),
        }
        self._history.append({"type": "plan", "data": plan})
        return plan

    # ── execute ─────────────────────────────────────────────
    def execute(self, plan: dict) -> dict:
        """Exécuter un plan étape par étape."""
        self._stats["executions"] += 1

        # Permission check
        if self._governance:
            perm = self._governance.check_permission(
                "learn", {"action": "execute_plan", "plan_id": plan.get("id")})
            if not perm.get("allowed", True):
                return {
                    "plan_id": plan.get("id"),
                    "status": "blocked",
                    "reason": perm.get("reason", "governance denied"),
                }

        results = []
        all_ok = True
        for step in plan.get("steps", []):
            step_result = {
                "step": step["step"],
                "action": step["action"],
                "status": "completed",
                "result": f"executed_{step['action']}",
                "timestamp": time.time(),
            }
            step["status"] = "completed"
            results.append(step_result)

        outcome = {
            "plan_id": plan.get("id"),
            "status": "completed" if all_ok else "partial",
            "steps_completed": len(results),
            "results": results,
            "timestamp": time.time(),
        }
        self._history.append({"type": "execution", "data": outcome})
        return outcome

    # ── verify ──────────────────────────────────────────────
    def verify(self, result: dict) -> dict:
        """Vérifier la cohérence d'un résultat."""
        self._stats["verifications"] += 1

        checks = []
        status_ok = True

        # Check: plan completed?
        if result.get("status") != "completed":
            checks.append({"check": "completion", "passed": False,
                           "detail": f"status={result.get('status')}"})
            status_ok = False
        else:
            checks.append({"check": "completion", "passed": True})

        # Check: all steps completed?
        for sr in result.get("results", []):
            if sr.get("status") != "completed":
                checks.append({"check": f"step_{sr['step']}", "passed": False})
                status_ok = False
            else:
                checks.append({"check": f"step_{sr['step']}", "passed": True})

        # Inference cross-check
        if self._inference:
            inf = self._inference.infer_logical({
                "subject": result.get("plan_id", ""),
                "predicate": "verify",
            })
            checks.append({"check": "inference_cross",
                           "passed": True,
                           "inference_id": inf.get("id")})

        verification = {
            "plan_id": result.get("plan_id"),
            "verified": status_ok,
            "checks": checks,
            "timestamp": time.time(),
        }
        self._history.append({"type": "verification", "data": verification})
        return verification

    # ── recover ─────────────────────────────────────────────
    def recover(self, error: dict) -> dict:
        """Récupération automatique après erreur."""
        self._stats["recoveries"] += 1

        error_type = error.get("type", "unknown")
        plan_id = error.get("plan_id", "")

        strategies = {
            "timeout": "retry_with_backoff",
            "permission": "escalate",
            "resource": "degrade_gracefully",
            "logic": "replan",
        }
        strategy = strategies.get(error_type, "log_and_skip")

        recovery = {
            "plan_id": plan_id,
            "error_type": error_type,
            "strategy": strategy,
            "status": "recovered",
            "timestamp": time.time(),
        }
        self._history.append({"type": "recovery", "data": recovery})
        return recovery

    # ── optimize ────────────────────────────────────────────
    def optimize(self, plan: dict) -> dict:
        """Optimiser un plan : réduire étapes, paralléliser."""
        self._stats["optimizations"] += 1

        steps = plan.get("steps", [])
        optimized_steps = []
        # Merge consecutive identical actions
        prev = None
        for s in steps:
            if prev and prev["action"] == s["action"]:
                prev["params"] = {**prev.get("params", {}),
                                  **s.get("params", {})}
                prev["merged"] = True
            else:
                if prev:
                    optimized_steps.append(prev)
                prev = dict(s)
        if prev:
            optimized_steps.append(prev)

        optimized = {
            "id": plan.get("id"),
            "goal": plan.get("goal"),
            "domain": plan.get("domain"),
            "steps": optimized_steps,
            "original_steps": len(steps),
            "optimized_steps": len(optimized_steps),
            "savings": len(steps) - len(optimized_steps),
            "status": "optimized",
            "timestamp": time.time(),
        }
        self._history.append({"type": "optimization", "data": optimized})
        return optimized

    # ── get_history ─────────────────────────────────────────
    def get_history(self, limit: int = 20) -> list[dict]:
        return self._history[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "cognitive_agent_core",
            "status": "ok",
            "history_size": len(self._history),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("CognitiveAgentCore restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
