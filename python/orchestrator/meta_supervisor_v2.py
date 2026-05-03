"""
EXO v12 — MetaSupervisorV2 (Méta-supervision avancée)
Étend MetaSupervisor v11 avec supervision du raisonnement,
de la planification, et application de méta-règles.

API:
  supervise_reasoning(reasoning_trace)  → dict
  supervise_planning(plan)              → dict
  enforce_meta_rules()                  → dict
  get_stats()                           → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("meta_supervisor_v2")


# Default meta-rules for v12 supervision
DEFAULT_META_RULES = {
    "max_reasoning_steps": 20,
    "min_reasoning_steps": 1,
    "max_plan_steps": 50,
    "min_plan_quality": 0.3,
    "max_reflections_per_min": 30,
    "require_conclusion": True,
    "require_goal": True,
    "forbidden_actions": [],
}


class MetaSupervisorV2:
    """Méta-superviseur avancé EXO v12."""

    def __init__(self, meta_memory, meta_supervisor_v1=None,
                 self_reflection=None, meta_reasoning=None,
                 governance=None):
        """
        Args:
            meta_memory: MetaMemory instance.
            meta_supervisor_v1: MetaSupervisor v11 (optional).
            self_reflection: SelfReflectionEngine (optional).
            meta_reasoning: MetaReasoningEngine (optional).
            governance: AutoGovernance (optional).
        """
        self._memory = meta_memory
        self._v1 = meta_supervisor_v1
        self._reflection = self_reflection
        self._reasoning = meta_reasoning
        self._governance = governance
        self._meta_rules = dict(DEFAULT_META_RULES)
        self._history: list[dict] = []
        self._recent_supervisions: list[float] = []
        self._alerts: list[dict] = []
        self._stats = {
            "reasoning_supervisions": 0,
            "planning_supervisions": 0,
            "meta_enforcements": 0,
            "alerts_raised": 0,
            "blocks": 0,
        }

    def set_meta_rules(self, rules: dict) -> None:
        """Update meta-supervision rules."""
        self._meta_rules.update(rules)
        log.info("MetaSupervisorV2 rules updated: %s", list(rules.keys()))

    # ── Reasoning supervision ────────────────────────────────
    def supervise_reasoning(self, reasoning_trace: dict) -> dict:
        """Supervise a reasoning trace.

        Checks constraints, runs reflection and meta-reasoning if available,
        returns approval status.
        """
        steps = reasoning_trace.get("steps", [])
        conclusion = reasoning_trace.get("conclusion", "")
        confidence = reasoning_trace.get("confidence", 0.5)
        issues = []
        approved = True

        # Rate limit check
        if not self._check_rate_limit():
            issues.append({
                "type": "rate_limit",
                "detail": "Supervision rate limit exceeded",
            })
            approved = False

        # Step count limits
        if len(steps) > self._meta_rules["max_reasoning_steps"]:
            issues.append({
                "type": "too_many_steps",
                "detail": f"Reasoning has {len(steps)} steps (max {self._meta_rules['max_reasoning_steps']})",
            })
            approved = False

        if len(steps) < self._meta_rules["min_reasoning_steps"]:
            issues.append({
                "type": "too_few_steps",
                "detail": f"Reasoning has {len(steps)} steps (min {self._meta_rules['min_reasoning_steps']})",
            })

        # Conclusion requirement
        if self._meta_rules["require_conclusion"] and not conclusion:
            issues.append({
                "type": "missing_conclusion",
                "detail": "Reasoning has no conclusion",
            })

        # Forbidden actions
        forbidden = self._meta_rules.get("forbidden_actions", [])
        for i, step in enumerate(steps):
            if isinstance(step, dict):
                action = step.get("action", "")
                if action in forbidden:
                    issues.append({
                        "type": "forbidden_action",
                        "step_index": i,
                        "detail": f"Step {i} uses forbidden action '{action}'",
                    })
                    approved = False

        # Run reflection if available
        reflection = None
        if self._reflection:
            reflection = self._reflection.reflect_on_reasoning(reasoning_trace)
            if reflection.get("quality", 1.0) < 0.3:
                issues.append({
                    "type": "low_quality_reasoning",
                    "detail": f"Reflection quality too low: {reflection['quality']:.0%}",
                })

        # Run meta-reasoning if available
        meta_analysis = None
        if self._reasoning:
            meta_analysis = self._reasoning.evaluate_reasoning_quality(reasoning_trace)
            if meta_analysis.get("overall", 1.0) < 0.3:
                issues.append({
                    "type": "low_meta_quality",
                    "detail": f"Meta-reasoning quality too low: {meta_analysis['overall']:.0%}",
                })

        if issues:
            self._raise_alert("reasoning_supervision", issues)
            if any(i["type"] in ("rate_limit", "too_many_steps", "forbidden_action")
                   for i in issues):
                approved = False
                self._stats["blocks"] += 1

        self._stats["reasoning_supervisions"] += 1

        result = {
            "type": "reasoning_supervision",
            "approved": approved,
            "issues": issues,
            "reflection": reflection,
            "meta_analysis": meta_analysis,
            "step_count": len(steps),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Planning supervision ─────────────────────────────────
    def supervise_planning(self, plan: dict) -> dict:
        """Supervise a plan.

        Checks constraints, verifies goal presence, enforces limits.
        """
        steps = plan.get("steps", [])
        goal = plan.get("goal", "")
        issues = []
        approved = True

        # Step count limit
        if len(steps) > self._meta_rules["max_plan_steps"]:
            issues.append({
                "type": "too_many_steps",
                "detail": f"Plan has {len(steps)} steps (max {self._meta_rules['max_plan_steps']})",
            })
            approved = False

        # Goal requirement
        if self._meta_rules["require_goal"] and not goal:
            issues.append({
                "type": "missing_goal",
                "detail": "Plan has no goal",
            })

        # Forbidden actions in steps
        forbidden = self._meta_rules.get("forbidden_actions", [])
        for i, step in enumerate(steps):
            if isinstance(step, dict):
                action = step.get("tool", "") or step.get("action", "")
                if action in forbidden:
                    issues.append({
                        "type": "forbidden_action",
                        "step_index": i,
                        "detail": f"Step {i} uses forbidden action '{action}'",
                    })
                    approved = False

        # Governance check
        if self._governance:
            for i, step in enumerate(steps):
                if isinstance(step, dict):
                    action = step.get("tool", "") or step.get("action", "")
                    if action and not self._governance.check_permission(action, step):
                        issues.append({
                            "type": "governance_block",
                            "step_index": i,
                            "detail": f"Step {i} blocked by governance",
                        })
                        approved = False

        # Run reflection if available
        reflection = None
        if self._reflection:
            reflection = self._reflection.reflect_on_plan(plan)
            quality = reflection.get("quality", 1.0)
            if quality < self._meta_rules["min_plan_quality"]:
                issues.append({
                    "type": "low_quality_plan",
                    "detail": f"Plan quality {quality:.0%} below minimum {self._meta_rules['min_plan_quality']:.0%}",
                })

        if issues:
            self._raise_alert("planning_supervision", issues)
            if any(i["type"] in ("too_many_steps", "forbidden_action", "governance_block")
                   for i in issues):
                approved = False
                self._stats["blocks"] += 1

        self._stats["planning_supervisions"] += 1

        result = {
            "type": "planning_supervision",
            "approved": approved,
            "issues": issues,
            "reflection": reflection,
            "step_count": len(steps),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Enforce meta-rules ───────────────────────────────────
    def enforce_meta_rules(self) -> dict:
        """Enforce meta-rules across the system.

        Checks MetaMemory consistency and applies v11 enforcement.
        """
        actions = []

        # 1. V11 enforcement if available
        if self._v1:
            v1_result = self._v1.enforce_rules()
            v1_actions = v1_result.get("actions", [])
            actions.extend([
                {"source": "v11", **a} for a in v1_actions
            ])

        # 2. Check alert volume
        recent_alerts = [
            a for a in self._alerts
            if time.time() - a.get("timestamp", 0) < 300  # last 5 min
        ]
        if len(recent_alerts) > 20:
            actions.append({
                "action": "high_alert_volume",
                "detail": f"{len(recent_alerts)} alerts in last 5 minutes",
                "source": "v12",
            })

        # 3. Check memory size
        stats = self._memory.get_stats()
        if stats.get("total", 0) > 4000:
            actions.append({
                "action": "memory_size_warning",
                "detail": f"MetaMemory has {stats['total']} entries (approaching limit)",
                "source": "v12",
            })

        self._stats["meta_enforcements"] += 1

        result = {
            "type": "meta_enforcement",
            "actions": actions,
            "action_count": len(actions),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Stats ────────────────────────────────────────────────
    def get_stats(self) -> dict:
        return dict(self._stats)

    def get_alerts(self, limit: int = 50) -> list[dict]:
        return self._alerts[-limit:]

    # ── Internal ─────────────────────────────────────────────
    def _check_rate_limit(self) -> bool:
        now = time.time()
        self._recent_supervisions = [
            t for t in self._recent_supervisions if now - t < 60
        ]
        if len(self._recent_supervisions) >= self._meta_rules["max_reflections_per_min"]:
            return False
        self._recent_supervisions.append(now)
        return True

    def _raise_alert(self, context: str, issues: list[dict]) -> None:
        alert = {
            "context": context,
            "issues": issues,
            "timestamp": time.time(),
        }
        self._alerts.append(alert)
        if len(self._alerts) > 200:
            self._alerts = self._alerts[-200:]
        self._stats["alerts_raised"] += 1
        log.warning("MetaSupervisorV2 alert (%s): %d issues", context, len(issues))

    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 300:
            self._history = self._history[-300:]
