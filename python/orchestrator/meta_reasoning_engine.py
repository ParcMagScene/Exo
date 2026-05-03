"""
EXO v12 — MetaReasoningEngine (Méta-raisonnement)
Analyse la structure logique des raisonnements, évalue la force des arguments,
la pertinence des étapes, la cohérence globale, et propose des améliorations.

API:
  meta_reason(reasoning_trace)                 → dict
  evaluate_reasoning_quality(reasoning_trace)  → dict
  propose_reasoning_improvements(reasoning_trace) → dict
  health_check()                               → dict
  restart()                                    → None
  get_stats()                                  → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("meta_reasoning")


class MetaReasoningEngine:
    """Moteur de méta-raisonnement EXO v12."""

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
            "meta_reasonings": 0,
            "quality_evaluations": 0,
            "improvements_proposed": 0,
            "biases_detected": 0,
        }

    # ── Full meta-reasoning ──────────────────────────────────
    def meta_reason(self, reasoning_trace: dict) -> dict:
        """Perform meta-reasoning on a reasoning trace.

        Analyzes logical structure, evaluates quality, detects biases,
        and proposes improvements. Returns comprehensive analysis.
        """
        quality = self.evaluate_reasoning_quality(reasoning_trace)
        improvements = self.propose_reasoning_improvements(reasoning_trace)
        biases = self._detect_biases(reasoning_trace)

        self._stats["meta_reasonings"] += 1

        result = {
            "type": "meta_reasoning",
            "quality": quality,
            "improvements": improvements,
            "biases": biases,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Quality evaluation ───────────────────────────────────
    def evaluate_reasoning_quality(self, reasoning_trace: dict) -> dict:
        """Evaluate the quality of a reasoning trace.

        Returns scores for logical_structure, argument_strength,
        step_relevance, global_coherence.
        """
        steps = reasoning_trace.get("steps", [])
        conclusion = reasoning_trace.get("conclusion", "")
        confidence = reasoning_trace.get("confidence", 0.5)

        # Logical structure score
        logical_structure = self._eval_logical_structure(steps, conclusion)

        # Argument strength
        argument_strength = self._eval_argument_strength(steps, confidence)

        # Step relevance
        step_relevance = self._eval_step_relevance(steps, conclusion)

        # Global coherence
        global_coherence = self._eval_global_coherence(steps, conclusion, confidence)

        overall = (
            logical_structure * 0.3
            + argument_strength * 0.25
            + step_relevance * 0.25
            + global_coherence * 0.2
        )

        self._stats["quality_evaluations"] += 1

        return {
            "logical_structure": round(logical_structure, 2),
            "argument_strength": round(argument_strength, 2),
            "step_relevance": round(step_relevance, 2),
            "global_coherence": round(global_coherence, 2),
            "overall": round(overall, 2),
        }

    # ── Improvement proposals ────────────────────────────────
    def propose_reasoning_improvements(self, reasoning_trace: dict) -> dict:
        """Propose improvements to a reasoning trace.

        Returns list of concrete improvement suggestions.
        """
        steps = reasoning_trace.get("steps", [])
        conclusion = reasoning_trace.get("conclusion", "")
        confidence = reasoning_trace.get("confidence", 0.5)

        improvements = []

        # Suggest adding missing steps
        if len(steps) < 2:
            improvements.append({
                "type": "add_steps",
                "detail": "Add intermediate reasoning steps for thoroughness",
                "priority": "high",
            })

        # Suggest evidence reinforcement
        evidence_count = sum(
            1 for s in steps
            if isinstance(s, dict) and s.get("evidence")
        )
        if evidence_count < len(steps) * 0.5 and steps:
            improvements.append({
                "type": "add_evidence",
                "detail": "Support reasoning steps with explicit evidence",
                "priority": "medium",
            })

        # Suggest conclusion reinforcement
        if conclusion and confidence < 0.5:
            improvements.append({
                "type": "strengthen_conclusion",
                "detail": "Low confidence — consider stronger supporting arguments",
                "priority": "high",
            })

        # Suggest removing weak steps
        for i, step in enumerate(steps):
            text = step.get("text", "") if isinstance(step, dict) else str(step)
            if len(text) < 10:
                improvements.append({
                    "type": "elaborate_step",
                    "step_index": i,
                    "detail": f"Step {i} is too brief — elaborate",
                    "priority": "low",
                })

        # Suggest alternative perspectives
        if not any(
            isinstance(s, dict) and s.get("perspective") == "counter"
            for s in steps
        ):
            improvements.append({
                "type": "add_counter_argument",
                "detail": "Consider counter-arguments for balanced reasoning",
                "priority": "medium",
            })

        # Look for learned reasoning patterns
        patterns = self._memory.meta_get("reasoning_pattern")
        if patterns:
            improvements.append({
                "type": "apply_learned_pattern",
                "detail": f"Found {len(patterns)} learned reasoning pattern(s) to apply",
                "priority": "low",
            })

        self._stats["improvements_proposed"] += len(improvements)

        return {
            "improvements": improvements,
            "count": len(improvements),
        }

    # ── Bias detection ───────────────────────────────────────
    def _detect_biases(self, reasoning_trace: dict) -> list[dict]:
        """Detect cognitive biases in reasoning."""
        steps = reasoning_trace.get("steps", [])
        confidence = reasoning_trace.get("confidence", 0.5)
        biases = []

        # Confirmation bias: all steps support the same conclusion
        if len(steps) >= 3:
            sentiments = []
            for step in steps:
                text = step.get("text", "") if isinstance(step, dict) else str(step)
                # Simple heuristic: check for negation words
                has_negation = any(
                    w in text.lower()
                    for w in ["mais", "cependant", "toutefois", "néanmoins",
                              "however", "but", "although", "despite"]
                )
                sentiments.append("counter" if has_negation else "support")
            if all(s == "support" for s in sentiments):
                biases.append({
                    "type": "confirmation_bias",
                    "detail": "All steps support conclusion without counter-arguments",
                })

        # Overconfidence bias
        if confidence > 0.95 and len(steps) < 3:
            biases.append({
                "type": "overconfidence_bias",
                "detail": f"Confidence {confidence:.0%} with only {len(steps)} steps",
            })

        # Anchoring bias: first step dominates
        if len(steps) >= 2:
            first_text = steps[0].get("text", "") if isinstance(steps[0], dict) else str(steps[0])
            conclusion = reasoning_trace.get("conclusion", "")
            if first_text and conclusion:
                first_words = set(first_text.lower().split()[:5])
                conc_words = set(conclusion.lower().split())
                overlap = first_words & conc_words - {"le", "la", "les", "de", "du", "des",
                                                        "the", "a", "an", "is", "are"}
                if len(overlap) >= 3:
                    biases.append({
                        "type": "anchoring_bias",
                        "detail": "Conclusion heavily influenced by first step",
                    })

        self._stats["biases_detected"] += len(biases)
        return biases

    # ── Health / restart (v9 integration) ────────────────────
    def health_check(self) -> dict:
        return {
            "service": "meta_reasoning",
            "status": "ok",
            "stats": dict(self._stats),
            "history_size": len(self._history),
        }

    def restart(self) -> None:
        self._history.clear()
        self._stats = {k: 0 for k in self._stats}
        log.info("MetaReasoningEngine restarted")

    # ── Stats ────────────────────────────────────────────────
    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ─────────────────────────────────────────────
    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 300:
            self._history = self._history[-300:]

    def _eval_logical_structure(self, steps: list, conclusion: str) -> float:
        score = 0.3
        if steps:
            score += 0.2
        if len(steps) >= 3:
            score += 0.2
        if conclusion:
            score += 0.2
        # Check step ordering (each step should build on previous)
        if len(steps) >= 2:
            has_deps = any(
                isinstance(s, dict) and s.get("depends_on")
                for s in steps
            )
            if has_deps:
                score += 0.1
        return min(1.0, score)

    def _eval_argument_strength(self, steps: list, confidence: float) -> float:
        score = 0.3
        evidence_count = sum(
            1 for s in steps
            if isinstance(s, dict) and s.get("evidence")
        )
        if steps:
            ratio = evidence_count / len(steps)
            score += 0.4 * ratio
        if 0.4 <= confidence <= 0.9:
            score += 0.2
        elif confidence > 0.9:
            score += 0.1
        return min(1.0, score)

    def _eval_step_relevance(self, steps: list, conclusion: str) -> float:
        if not steps:
            return 0.2
        score = 0.4
        if conclusion:
            conc_words = set(conclusion.lower().split())
            relevant_count = 0
            for step in steps:
                text = step.get("text", "") if isinstance(step, dict) else str(step)
                step_words = set(text.lower().split())
                if step_words & conc_words:
                    relevant_count += 1
            if steps:
                score += 0.5 * (relevant_count / len(steps))
        else:
            score += 0.2
        return min(1.0, score)

    def _eval_global_coherence(self, steps: list, conclusion: str,
                                confidence: float) -> float:
        score = 0.3
        if steps and conclusion:
            score += 0.3
        if 0.3 <= confidence <= 0.9:
            score += 0.2
        if len(steps) >= 2:
            score += 0.1
        return min(1.0, score)
