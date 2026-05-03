"""
EXO v12 — MetaVerifier (Vérification méta-cognitive)
Vérifie la validité logique des plans et raisonnements,
détecte les contradictions, vérifie les hypothèses,
contrôle l'alignement avec l'intention et la gouvernance.

API:
  meta_verify(plan)                       → dict
  meta_verify_reasoning(reasoning_trace)  → dict
  get_stats()                             → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("meta_verifier")


class MetaVerifier:
    """Vérificateur méta-cognitif EXO v12."""

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
            "plans_verified": 0,
            "reasonings_verified": 0,
            "contradictions_found": 0,
            "violations_found": 0,
        }

    # ── Plan verification ────────────────────────────────────
    def meta_verify(self, plan: dict) -> dict:
        """Verify a plan for logical validity and governance alignment.

        Returns verification report with status, issues, and recommendations.
        """
        steps = plan.get("steps", [])
        goal = plan.get("goal", "")
        issues = []
        warnings = []

        # 1. Logical validity: steps form a coherent sequence
        issues.extend(self._check_step_coherence(steps))

        # 2. Contradiction detection
        contradictions = self._detect_plan_contradictions(steps)
        issues.extend(contradictions)
        self._stats["contradictions_found"] += len(contradictions)

        # 3. Hypothesis validity
        issues.extend(self._check_hypothesis_validity(steps))

        # 4. Goal alignment
        if goal:
            alignment = self._check_goal_alignment(steps, goal)
            if alignment:
                warnings.extend(alignment)

        # 5. Governance compliance
        if self._governance:
            gov_issues = self._check_governance(steps)
            issues.extend(gov_issues)
            self._stats["violations_found"] += len(gov_issues)

        valid = len(issues) == 0
        self._stats["plans_verified"] += 1

        result = {
            "type": "plan_verification",
            "valid": valid,
            "issues": issues,
            "warnings": warnings,
            "step_count": len(steps),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Reasoning verification ───────────────────────────────
    def meta_verify_reasoning(self, reasoning_trace: dict) -> dict:
        """Verify a reasoning trace for logical validity.

        Returns verification report.
        """
        steps = reasoning_trace.get("steps", [])
        conclusion = reasoning_trace.get("conclusion", "")
        confidence = reasoning_trace.get("confidence", 0.5)
        issues = []
        warnings = []

        # 1. Check logical flow
        for i, step in enumerate(steps):
            text = step.get("text", "") if isinstance(step, dict) else str(step)
            if not text.strip():
                issues.append({
                    "type": "empty_reasoning_step",
                    "step_index": i,
                    "detail": f"Step {i} is empty",
                })

        # 2. Contradiction detection in reasoning
        contradictions = self._detect_reasoning_contradictions(steps)
        issues.extend(contradictions)
        self._stats["contradictions_found"] += len(contradictions)

        # 3. Conclusion validity
        if conclusion and not steps:
            issues.append({
                "type": "unsupported_conclusion",
                "detail": "Conclusion without supporting reasoning steps",
            })

        # 4. Confidence calibration check
        if confidence > 0.95 and len(steps) < 2:
            warnings.append({
                "type": "overconfident",
                "detail": f"Confidence {confidence:.0%} with only {len(steps)} step(s)",
            })
        elif confidence < 0.1 and len(steps) >= 3:
            warnings.append({
                "type": "underconfident",
                "detail": f"Low confidence {confidence:.0%} despite {len(steps)} steps",
            })

        # 5. Governance compliance for reasoning actions
        if self._governance:
            for step in steps:
                if isinstance(step, dict):
                    action = step.get("action", "")
                    if action and not self._governance.check_permission(
                        action, step
                    ):
                        issues.append({
                            "type": "governance_violation",
                            "detail": f"Action '{action}' blocked by governance",
                        })
                        self._stats["violations_found"] += 1

        valid = len(issues) == 0
        self._stats["reasonings_verified"] += 1

        result = {
            "type": "reasoning_verification",
            "valid": valid,
            "issues": issues,
            "warnings": warnings,
            "step_count": len(steps),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Stats ────────────────────────────────────────────────
    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ─────────────────────────────────────────────
    def _check_step_coherence(self, steps: list) -> list[dict]:
        """Check that steps form a coherent sequence."""
        issues = []
        seen_ids = set()
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            step_id = step.get("id", i)
            deps = step.get("depends_on", [])
            for dep in deps:
                if dep not in seen_ids:
                    issues.append({
                        "type": "forward_dependency",
                        "step_index": i,
                        "detail": f"Step {i} depends on {dep} which comes later or doesn't exist",
                    })
            seen_ids.add(step_id)
        return issues

    def _detect_plan_contradictions(self, steps: list) -> list[dict]:
        """Detect contradictory actions in a plan."""
        contradictions = []
        actions = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            action = step.get("tool", "") or step.get("action", "")
            target = step.get("target", "") or step.get("description", "")
            actions.append((i, action, target.lower()))

        # Check for create then delete of same target
        for i, (idx_a, act_a, tgt_a) in enumerate(actions):
            for idx_b, act_b, tgt_b in actions[i + 1:]:
                if not tgt_a or not tgt_b:
                    continue
                # Create/delete contradiction
                create_words = {"create", "add", "enable", "start"}
                delete_words = {"delete", "remove", "disable", "stop"}
                a_creates = any(w in act_a.lower() for w in create_words)
                b_deletes = any(w in act_b.lower() for w in delete_words)
                if a_creates and b_deletes and tgt_a == tgt_b:
                    contradictions.append({
                        "type": "contradiction",
                        "step_indices": [idx_a, idx_b],
                        "detail": f"Step {idx_a} creates and step {idx_b} deletes same target",
                    })
        return contradictions

    def _detect_reasoning_contradictions(self, steps: list) -> list[dict]:
        """Detect contradictions between reasoning steps."""
        contradictions = []
        assertions = []
        for i, step in enumerate(steps):
            text = step.get("text", "") if isinstance(step, dict) else str(step)
            text_lower = text.lower().strip()
            if not text_lower:
                continue
            # Simple negation pattern detection
            assertions.append((i, text_lower))

        for i, (idx_a, text_a) in enumerate(assertions):
            for idx_b, text_b in assertions[i + 1:]:
                # Check for direct negation
                negation_pairs = [
                    ("vrai", "faux"), ("true", "false"),
                    ("oui", "non"), ("yes", "no"),
                    ("possible", "impossible"),
                ]
                for pos, neg in negation_pairs:
                    if pos in text_a and neg in text_b:
                        # Check context overlap
                        words_a = set(text_a.split()) - {pos}
                        words_b = set(text_b.split()) - {neg}
                        if len(words_a & words_b) >= 2:
                            contradictions.append({
                                "type": "reasoning_contradiction",
                                "step_indices": [idx_a, idx_b],
                                "detail": f"Steps {idx_a} and {idx_b} appear contradictory",
                            })
        return contradictions

    def _check_hypothesis_validity(self, steps: list) -> list[dict]:
        """Check that hypotheses are properly supported."""
        issues = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            if step.get("type") == "hypothesis" and not step.get("evidence"):
                issues.append({
                    "type": "unsupported_hypothesis",
                    "step_index": i,
                    "detail": f"Step {i} is a hypothesis without evidence",
                })
        return issues

    def _check_goal_alignment(self, steps: list, goal: str) -> list[dict]:
        """Check if steps are aligned with the goal."""
        warnings = []
        goal_words = set(goal.lower().split()) - {
            "le", "la", "les", "de", "du", "des", "un", "une",
            "the", "a", "an", "to", "of", "in", "for",
        }
        if not goal_words:
            return warnings

        unaligned = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            desc = step.get("description", "")
            desc_words = set(desc.lower().split())
            if not desc_words & goal_words:
                unaligned.append(i)

        if unaligned and len(unaligned) > len(steps) * 0.5:
            warnings.append({
                "type": "weak_goal_alignment",
                "detail": f"Steps {unaligned} may not align with goal '{goal}'",
            })
        return warnings

    def _check_governance(self, steps: list) -> list[dict]:
        """Check governance compliance for plan steps."""
        issues = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            action = step.get("tool", "") or step.get("action", "")
            if action and not self._governance.check_permission(action, step):
                issues.append({
                    "type": "governance_violation",
                    "step_index": i,
                    "detail": f"Step {i} action '{action}' blocked by governance",
                })
        return issues

    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 300:
            self._history = self._history[-300:]
