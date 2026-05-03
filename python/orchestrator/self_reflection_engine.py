"""
EXO v12 — SelfReflectionEngine (Auto-réflexion)
Évalue la qualité des raisonnements, plans et décisions d'EXO.
Détecte les étapes inutiles, les raccourcis dangereux,
les hypothèses faibles et les incohérences internes.

API:
  reflect_on_reasoning(reasoning_trace) → dict
  reflect_on_plan(plan)                 → dict
  reflect_on_decision(decision)         → dict
  health_check()                        → dict
  restart()                             → None
  get_stats()                           → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("self_reflection")


class SelfReflectionEngine:
    """Moteur d'auto-réflexion EXO v12."""

    def __init__(self, meta_memory, governance=None):
        """
        Args:
            meta_memory: MetaMemory instance.
            governance: AutoGovernance (optional).
        """
        self._memory = meta_memory
        self._governance = governance
        self._history: list[dict] = []
        self._stats = {
            "reasoning_reflections": 0,
            "plan_reflections": 0,
            "decision_reflections": 0,
            "issues_detected": 0,
        }

    # ── Reasoning reflection ────────────────────────────────
    def reflect_on_reasoning(self, reasoning_trace: dict) -> dict:
        """Reflect on a reasoning trace.

        reasoning_trace: dict with 'steps' (list of reasoning steps),
            'conclusion', 'confidence'.
        Returns analysis with issues, strengths, suggestions.
        """
        steps = reasoning_trace.get("steps", [])
        conclusion = reasoning_trace.get("conclusion", "")
        confidence = reasoning_trace.get("confidence", 0.5)

        issues = []
        strengths = []
        suggestions = []

        # 1. Check clarity of steps
        for i, step in enumerate(steps):
            text = step.get("text", "") if isinstance(step, dict) else str(step)
            if len(text) < 5:
                issues.append({
                    "type": "unclear_step",
                    "step_index": i,
                    "detail": f"Step {i} too vague: '{text}'",
                })

        # 2. Detect unnecessary steps (duplicates)
        seen_texts = set()
        for i, step in enumerate(steps):
            text = step.get("text", "") if isinstance(step, dict) else str(step)
            normalized = text.strip().lower()
            if normalized in seen_texts:
                issues.append({
                    "type": "redundant_step",
                    "step_index": i,
                    "detail": f"Step {i} is a duplicate",
                })
            seen_texts.add(normalized)

        # 3. Check for weak hypotheses
        for i, step in enumerate(steps):
            text = step.get("text", "") if isinstance(step, dict) else str(step)
            weak_markers = ["peut-être", "probablement", "je suppose",
                            "maybe", "probably", "I guess", "perhaps"]
            for marker in weak_markers:
                if marker.lower() in text.lower():
                    issues.append({
                        "type": "weak_hypothesis",
                        "step_index": i,
                        "detail": f"Step {i} contains weak marker: '{marker}'",
                    })
                    break

        # 4. Check confidence
        if confidence < 0.3:
            issues.append({
                "type": "low_confidence",
                "detail": f"Overall confidence too low: {confidence:.0%}",
            })
        elif confidence > 0.9 and len(steps) < 2:
            issues.append({
                "type": "overconfidence",
                "detail": "High confidence with minimal reasoning steps",
            })

        # 5. Detect empty conclusion
        if not conclusion:
            issues.append({
                "type": "missing_conclusion",
                "detail": "No conclusion provided",
            })

        # Strengths
        if len(steps) >= 3 and not any(
            i["type"] == "redundant_step" for i in issues
        ):
            strengths.append("Multi-step reasoning with no redundancy")
        if 0.5 <= confidence <= 0.9:
            strengths.append("Well-calibrated confidence")

        # Suggestions
        if any(i["type"] == "weak_hypothesis" for i in issues):
            suggestions.append("Replace weak hypotheses with evidence-based claims")
        if any(i["type"] == "redundant_step" for i in issues):
            suggestions.append("Remove duplicate reasoning steps")
        if not strengths:
            suggestions.append("Add more reasoning steps for thorough analysis")

        quality = self._compute_quality(steps, issues, confidence)

        self._stats["reasoning_reflections"] += 1
        self._stats["issues_detected"] += len(issues)

        result = {
            "type": "reasoning_reflection",
            "quality": quality,
            "issues": issues,
            "strengths": strengths,
            "suggestions": suggestions,
            "step_count": len(steps),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Plan reflection ──────────────────────────────────────
    def reflect_on_plan(self, plan: dict) -> dict:
        """Reflect on a plan.

        plan: dict with 'steps', 'goal', optional 'constraints'.
        Returns analysis with issues, strengths, suggestions.
        """
        steps = plan.get("steps", [])
        goal = plan.get("goal", "")
        constraints = plan.get("constraints", [])

        issues = []
        strengths = []
        suggestions = []

        # 1. Check goal clarity
        if not goal:
            issues.append({
                "type": "missing_goal",
                "detail": "Plan has no explicit goal",
            })
        elif len(goal) < 5:
            issues.append({
                "type": "vague_goal",
                "detail": f"Plan goal too vague: '{goal}'",
            })

        # 2. Check step coverage
        if len(steps) == 0:
            issues.append({
                "type": "empty_plan",
                "detail": "Plan has no steps",
            })
        elif len(steps) == 1:
            suggestions.append("Consider breaking down into smaller steps")

        # 3. Check for dangerous shortcuts
        for i, step in enumerate(steps):
            tool = step.get("tool", "") if isinstance(step, dict) else ""
            desc = step.get("description", "") if isinstance(step, dict) else str(step)
            dangerous = ["delete", "rm ", "drop", "truncate", "format"]
            for d in dangerous:
                if d in desc.lower() or d in tool.lower():
                    issues.append({
                        "type": "dangerous_shortcut",
                        "step_index": i,
                        "detail": f"Step {i} contains dangerous operation: '{d}'",
                    })
                    break

        # 4. Check dependency coherence
        step_ids = set()
        for i, step in enumerate(steps):
            if isinstance(step, dict):
                step_ids.add(step.get("id", i))
        for i, step in enumerate(steps):
            if isinstance(step, dict):
                deps = step.get("depends_on", [])
                for dep in deps:
                    if dep not in step_ids:
                        issues.append({
                            "type": "broken_dependency",
                            "step_index": i,
                            "detail": f"Step {i} depends on unknown step: {dep}",
                        })

        # Strengths
        if goal and len(steps) >= 2 and not issues:
            strengths.append("Well-structured plan with clear goal")
        if constraints:
            strengths.append(f"Explicit constraints defined ({len(constraints)})")

        quality = self._compute_plan_quality(steps, issues, goal)

        self._stats["plan_reflections"] += 1
        self._stats["issues_detected"] += len(issues)

        result = {
            "type": "plan_reflection",
            "quality": quality,
            "issues": issues,
            "strengths": strengths,
            "suggestions": suggestions,
            "step_count": len(steps),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Decision reflection ──────────────────────────────────
    def reflect_on_decision(self, decision: dict) -> dict:
        """Reflect on a decision.

        decision: dict with 'action', 'reason', 'alternatives', 'confidence'.
        Returns analysis.
        """
        action = decision.get("action", "")
        reason = decision.get("reason", "")
        alternatives = decision.get("alternatives", [])
        confidence = decision.get("confidence", 0.5)

        issues = []
        strengths = []
        suggestions = []

        # 1. Check reason
        if not reason:
            issues.append({
                "type": "missing_reason",
                "detail": "Decision has no stated reason",
            })

        # 2. Check alternatives considered
        if not alternatives:
            issues.append({
                "type": "no_alternatives",
                "detail": "No alternative actions were considered",
            })
            suggestions.append("Always consider at least one alternative")
        elif len(alternatives) >= 2:
            strengths.append(f"{len(alternatives)} alternatives considered")

        # 3. Check confidence calibration
        if confidence < 0.3:
            issues.append({
                "type": "low_confidence",
                "detail": f"Decision confidence too low: {confidence:.0%}",
            })
            suggestions.append("Gather more evidence before deciding")
        elif confidence > 0.95 and not alternatives:
            issues.append({
                "type": "overconfidence",
                "detail": "Very high confidence without considering alternatives",
            })

        # 4. Governance check
        if self._governance:
            permitted = self._governance.check_permission(action, decision)
            if not permitted:
                issues.append({
                    "type": "governance_block",
                    "detail": f"Action '{action}' blocked by governance",
                })

        # Lookup past similar decisions
        past = self._memory.meta_get(action)
        relevant = [e for e in past if e.get("category") == "decision"]
        if relevant:
            strengths.append(f"Historical data available ({len(relevant)} entries)")

        quality = max(0.0, min(1.0,
            1.0
            - 0.2 * len(issues)
            + 0.1 * len(strengths)
        ))

        self._stats["decision_reflections"] += 1
        self._stats["issues_detected"] += len(issues)

        result = {
            "type": "decision_reflection",
            "quality": quality,
            "issues": issues,
            "strengths": strengths,
            "suggestions": suggestions,
            "action": action,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Health / restart (v9 integration) ────────────────────
    def health_check(self) -> dict:
        return {
            "service": "self_reflection",
            "status": "ok",
            "stats": dict(self._stats),
            "history_size": len(self._history),
        }

    def restart(self) -> None:
        self._history.clear()
        self._stats = {k: 0 for k in self._stats}
        log.info("SelfReflectionEngine restarted")

    # ── Stats ────────────────────────────────────────────────
    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ─────────────────────────────────────────────
    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 300:
            self._history = self._history[-300:]

    def _compute_quality(self, steps: list, issues: list, confidence: float) -> float:
        base = 0.5
        if len(steps) >= 3:
            base += 0.2
        elif len(steps) >= 1:
            base += 0.1
        base -= 0.15 * len(issues)
        if 0.4 <= confidence <= 0.9:
            base += 0.1
        return max(0.0, min(1.0, base))

    def _compute_plan_quality(self, steps: list, issues: list, goal: str) -> float:
        base = 0.5
        if goal:
            base += 0.15
        if len(steps) >= 2:
            base += 0.15
        base -= 0.15 * len(issues)
        return max(0.0, min(1.0, base))
