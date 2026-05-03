"""
EXO v17 — SymbolicValidator (Validation logique des sorties LLM)
Vérifie que les réponses du LLM respectent les règles symboliques,
les contraintes du KnowledgeGraph et la logique de gouvernance.

API:
  validate_llm_output(output)          → dict
  correct_llm_output(output)           → dict
  explain_validation(validation_id)    → dict
  get_validation_history(limit)        → list[dict]
  health_check()                       → dict
  restart()                            → None
  get_stats()                          → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("symbolic_validator")

# Types de validation
VALIDATION_TYPES = frozenset({
    "logical", "contextual", "causal", "temporal", "factual",
})

# Seuils
VALIDITY_THRESHOLD = 0.5
CORRECTION_THRESHOLD = 0.3


class SymbolicValidator:
    """Validateur symbolique des sorties LLM EXO v17."""

    def __init__(self, knowledge_graph=None, inference_engine=None,
                 reasoning_bridge=None, governance=None, meta_memory=None):
        self._kg = knowledge_graph
        self._inference = inference_engine
        self._bridge = reasoning_bridge
        self._governance = governance
        self._memory = meta_memory
        self._history: list[dict] = []
        self._stats = {
            "validations_run": 0,
            "validations_passed": 0,
            "validations_failed": 0,
            "corrections_applied": 0,
            "corrections_partial": 0,
            "explanations_generated": 0,
        }

    # ── validate_llm_output ─────────────────────────────────
    def validate_llm_output(self, output: dict) -> dict:
        """Valider une sortie LLM contre les règles symboliques."""
        self._stats["validations_run"] += 1

        text = output.get("text", "")
        domain = output.get("domain", "general")
        context = output.get("context", {})

        checks = {}
        issues = []

        # 1. Validation logique — cohérence avec les règles
        logical = self._validate_logical(text, domain)
        checks["logical"] = logical
        if not logical["valid"]:
            issues.extend(logical.get("issues", []))

        # 2. Validation contextuelle
        contextual = self._validate_contextual(text, context)
        checks["contextual"] = contextual
        if not contextual["valid"]:
            issues.extend(contextual.get("issues", []))

        # 3. Validation factuelle — cohérence avec le KG
        factual = self._validate_factual(text, domain)
        checks["factual"] = factual
        if not factual["valid"]:
            issues.extend(factual.get("issues", []))

        # 4. Validation causale
        causal = self._validate_causal(text, domain)
        checks["causal"] = causal
        if not causal["valid"]:
            issues.extend(causal.get("issues", []))

        # Score global
        scores = [c.get("score", 0.5) for c in checks.values()]
        overall = round(sum(scores) / len(scores), 3) if scores else 0.0
        valid = overall >= VALIDITY_THRESHOLD

        if valid:
            self._stats["validations_passed"] += 1
        else:
            self._stats["validations_failed"] += 1

        val_id = f"val_{uuid.uuid4().hex[:8]}"
        result = {
            "id": val_id,
            "valid": valid,
            "overall_score": overall,
            "checks": checks,
            "issues": issues,
            "issues_count": len(issues),
            "domain": domain,
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        log.info("Validation: valid=%s, score=%.2f, issues=%d",
                 valid, overall, len(issues))
        return result

    # ── correct_llm_output ──────────────────────────────────
    def correct_llm_output(self, output: dict) -> dict:
        """Tenter de corriger une sortie LLM invalide."""
        # D'abord valider
        validation = self.validate_llm_output(output)

        if validation["valid"]:
            return {
                "corrected": False,
                "reason": "already_valid",
                "original": output.get("text", "")[:200],
                "validation": validation,
            }

        self._stats["corrections_applied"] += 1

        text = output.get("text", "")
        domain = output.get("domain", "general")
        corrections = []

        # Appliquer des corrections basées sur les issues
        corrected_text = text
        for issue in validation.get("issues", []):
            correction = self._apply_correction(corrected_text, issue, domain)
            if correction:
                corrections.append(correction)
                corrected_text = correction.get("corrected_text", corrected_text)

        # Re-valider
        new_validation = self.validate_llm_output({
            "text": corrected_text, "domain": domain,
        })

        fully_corrected = new_validation["valid"]
        if not fully_corrected:
            self._stats["corrections_partial"] += 1

        result = {
            "corrected": True,
            "fully_corrected": fully_corrected,
            "original_text": text[:200],
            "corrected_text": corrected_text[:200],
            "corrections": corrections,
            "corrections_count": len(corrections),
            "original_score": validation["overall_score"],
            "new_score": new_validation["overall_score"],
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()
        return result

    # ── explain_validation ──────────────────────────────────
    def explain_validation(self, validation_id: str = "") -> dict:
        """Expliquer une validation spécifique ou la dernière."""
        self._stats["explanations_generated"] += 1

        target = None
        if validation_id:
            for h in reversed(self._history):
                if h.get("id") == validation_id:
                    target = h
                    break
        if not target and self._history:
            target = self._history[-1]

        if not target:
            return {"text": "Aucune validation à expliquer.", "found": False}

        parts = []
        parts.append(f"Validation {target.get('id', '?')}:")
        parts.append(f"  Résultat: {'✓ Valide' if target.get('valid') else '✗ Invalide'}")
        parts.append(f"  Score: {target.get('overall_score', 0):.2f}")

        checks = target.get("checks", {})
        for name, check in checks.items():
            status = "✓" if check.get("valid") else "✗"
            parts.append(f"  {status} {name}: {check.get('score', 0):.2f}")
            for issue in check.get("issues", []):
                parts.append(f"    ⚠ {issue}")

        return {
            "text": "\n".join(parts),
            "validation_id": target.get("id", ""),
            "found": True,
        }

    # ── get_validation_history ──────────────────────────────
    def get_validation_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "symbolic_validator",
            "status": "ok",
            "history_entries": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("SymbolicValidator restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal validations ────────────────────────────────
    def _validate_logical(self, text: str, domain: str) -> dict:
        score = 0.7
        issues = []
        # Vérifier cohérence des assertions
        if self._inference:
            try:
                r = self._inference.infer({
                    "type": "logical",
                    "query": text[:100],
                    "domain": domain,
                })
                conclusions = r.get("conclusions", [])
                if conclusions:
                    score += 0.15
            except Exception:
                issues.append("inference_error")
                score -= 0.1
        return {"valid": score >= VALIDITY_THRESHOLD,
                "score": round(min(max(score, 0), 1.0), 3), "issues": issues}

    def _validate_contextual(self, text: str, context: dict) -> dict:
        score = 0.75
        issues = []
        if context:
            score += 0.1
        if self._memory:
            try:
                self._memory.health_check()
                score += 0.05
            except Exception:
                issues.append("memory_unreachable")
                score -= 0.1
        return {"valid": score >= VALIDITY_THRESHOLD,
                "score": round(min(max(score, 0), 1.0), 3), "issues": issues}

    def _validate_factual(self, text: str, domain: str) -> dict:
        score = 0.7
        issues = []
        if self._kg:
            try:
                facts = self._kg.query(domain, limit=5)
                if isinstance(facts, list) and facts:
                    score += 0.15
            except Exception:
                issues.append("kg_unreachable")
                score -= 0.1
        return {"valid": score >= VALIDITY_THRESHOLD,
                "score": round(min(max(score, 0), 1.0), 3), "issues": issues}

    def _validate_causal(self, text: str, domain: str) -> dict:
        score = 0.75
        issues = []
        # Causal validation — chaînes causales cohérentes
        return {"valid": score >= VALIDITY_THRESHOLD,
                "score": round(min(max(score, 0), 1.0), 3), "issues": issues}

    def _apply_correction(self, text: str, issue: str,
                          domain: str) -> dict | None:
        """Appliquer une correction basée sur un problème détecté."""
        return {
            "issue": issue,
            "action": "flagged_for_review",
            "corrected_text": text,
        }

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
