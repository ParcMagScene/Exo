"""
EXO v10 — TaskRecovery
Module de récupération automatique en cas d'échec d'exécution.

Analyse les erreurs, tente des corrections automatiques,
effectue des rollbacks si nécessaire, et escalade à l'utilisateur
si la récupération automatique échoue.

API:
  recover(step, error)  → RecoveryResult
  rollback(step)        → bool
  escalate(error)       → EscalationResult
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("task_recovery")


class RecoveryStrategy(str, Enum):
    RETRY = "retry"
    ALTERNATIVE = "alternative"
    SKIP = "skip"
    ROLLBACK = "rollback"
    ESCALATE = "escalate"


class ErrorCategory(str, Enum):
    TIMEOUT = "timeout"
    SERVICE_DOWN = "service_down"
    INVALID_RESULT = "invalid_result"
    PERMISSION = "permission"
    RESOURCE = "resource"
    LOGIC = "logic"
    UNKNOWN = "unknown"


@dataclass
class RecoveryResult:
    success: bool
    strategy: RecoveryStrategy
    error_category: ErrorCategory
    message: str
    corrected_step: dict | None = None
    attempts: int = 0
    elapsed_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "strategy": self.strategy.value,
            "error_category": self.error_category.value,
            "message": self.message,
            "corrected_step": self.corrected_step,
            "attempts": self.attempts,
            "elapsed_s": self.elapsed_s,
        }


@dataclass
class EscalationResult:
    level: str  # "user", "admin", "critical"
    reason: str
    context: dict = field(default_factory=dict)
    suggested_action: str = ""

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "reason": self.reason,
            "context": self.context,
            "suggested_action": self.suggested_action,
        }


# Error patterns for classification
_TIMEOUT_PATTERNS = ["timeout", "timed out", "deadline exceeded", "too slow"]
_SERVICE_PATTERNS = ["connection refused", "not available", "unreachable", "503", "502"]
_PERMISSION_PATTERNS = ["permission", "forbidden", "403", "unauthorized", "401"]
_RESOURCE_PATTERNS = ["not found", "404", "no such", "does not exist", "missing"]

MAX_RECOVERY_ATTEMPTS = 3


class TaskRecovery:
    """Handles automatic error recovery for failed task steps."""

    def __init__(self) -> None:
        self._recovery_log: list[dict] = []
        self._rollback_stack: list[dict] = []

    def recover(self, step: dict, error: str) -> RecoveryResult:
        """Attempt automatic recovery from a step failure.

        Analyzes the error, determines the best recovery strategy,
        and attempts correction.
        """
        start = time.time()
        category = self._classify_error(error)
        strategy = self._determine_strategy(step, category, error)

        result: RecoveryResult

        if strategy == RecoveryStrategy.RETRY:
            result = self._attempt_retry(step, category, error)
        elif strategy == RecoveryStrategy.ALTERNATIVE:
            result = self._attempt_alternative(step, category, error)
        elif strategy == RecoveryStrategy.SKIP:
            result = RecoveryResult(
                success=True,
                strategy=RecoveryStrategy.SKIP,
                error_category=category,
                message=f"Step skipped due to {category.value} error",
            )
        elif strategy == RecoveryStrategy.ROLLBACK:
            ok = self.rollback(step)
            result = RecoveryResult(
                success=ok,
                strategy=RecoveryStrategy.ROLLBACK,
                error_category=category,
                message="Rollback " + ("successful" if ok else "failed"),
            )
        else:
            escalation = self.escalate(error)
            result = RecoveryResult(
                success=False,
                strategy=RecoveryStrategy.ESCALATE,
                error_category=category,
                message=f"Escalated to {escalation.level}: {escalation.reason}",
            )

        result.elapsed_s = round(time.time() - start, 4)

        # Log recovery attempt
        self._recovery_log.append({
            "timestamp": time.time(),
            "step": step.get("description", ""),
            "error": error,
            "category": category.value,
            "strategy": strategy.value,
            "success": result.success,
        })

        return result

    def rollback(self, step: dict) -> bool:
        """Rollback a step's effects if possible."""
        tool = step.get("tool", "")
        description = step.get("description", "")

        # Track rollback
        self._rollback_stack.append({
            "timestamp": time.time(),
            "step": description,
            "tool": tool,
        })

        # Reversible operations
        reversible = {"remember_info", "set_preference", "create_plan"}
        if tool in reversible:
            log.info("Rollback step: %s (tool: %s)", description, tool)
            return True

        # Non-reversible operations (search, news) — nothing to undo
        log.info("Step %s doesn't need rollback (tool: %s)", description, tool)
        return True

    def escalate(self, error: str) -> EscalationResult:
        """Escalate an unrecoverable error to the user."""
        category = self._classify_error(error)

        if category in (ErrorCategory.PERMISSION, ErrorCategory.RESOURCE):
            return EscalationResult(
                level="user",
                reason=f"Action impossible: {error}",
                suggested_action="Vérifiez les permissions ou la ressource demandée.",
            )
        elif category == ErrorCategory.SERVICE_DOWN:
            return EscalationResult(
                level="admin",
                reason=f"Service indisponible: {error}",
                suggested_action="Un service est en panne. Réessayez plus tard.",
            )
        else:
            return EscalationResult(
                level="user",
                reason=f"Erreur inattendue: {error}",
                suggested_action="L'opération a échoué. Veuillez reformuler.",
            )

    def get_recovery_log(self) -> list[dict]:
        return list(self._recovery_log)

    def get_stats(self) -> dict:
        total = len(self._recovery_log)
        successes = sum(1 for r in self._recovery_log if r["success"])
        return {
            "total_recoveries": total,
            "successful": successes,
            "failed": total - successes,
            "success_rate": round(successes / total, 3) if total else 0.0,
            "by_category": self._stats_by_field("category"),
            "by_strategy": self._stats_by_field("strategy"),
        }

    # ── Internal ─────────────────────────────────────

    def _classify_error(self, error: str) -> ErrorCategory:
        error_lower = error.lower()
        if any(p in error_lower for p in _TIMEOUT_PATTERNS):
            return ErrorCategory.TIMEOUT
        if any(p in error_lower for p in _SERVICE_PATTERNS):
            return ErrorCategory.SERVICE_DOWN
        if any(p in error_lower for p in _PERMISSION_PATTERNS):
            return ErrorCategory.PERMISSION
        if any(p in error_lower for p in _RESOURCE_PATTERNS):
            return ErrorCategory.RESOURCE
        if "invalid" in error_lower or "unexpected" in error_lower:
            return ErrorCategory.INVALID_RESULT
        return ErrorCategory.UNKNOWN

    def _determine_strategy(self, step: dict, category: ErrorCategory,
                            error: str) -> RecoveryStrategy:
        """Determine the best recovery strategy based on error type."""
        retries = step.get("retries", 0)

        # Timeout/transient → retry
        if category == ErrorCategory.TIMEOUT and retries < MAX_RECOVERY_ATTEMPTS:
            return RecoveryStrategy.RETRY

        # Service down → retry once, then alternative
        if category == ErrorCategory.SERVICE_DOWN:
            if retries < 1:
                return RecoveryStrategy.RETRY
            return RecoveryStrategy.ALTERNATIVE

        # Invalid result → alternative tool
        if category == ErrorCategory.INVALID_RESULT:
            return RecoveryStrategy.ALTERNATIVE

        # Permission/resource → escalate
        if category in (ErrorCategory.PERMISSION, ErrorCategory.RESOURCE):
            return RecoveryStrategy.ESCALATE

        # Logic error → skip if non-critical
        if step.get("priority", 5) > 3:
            return RecoveryStrategy.SKIP

        return RecoveryStrategy.ESCALATE

    def _attempt_retry(self, step: dict, category: ErrorCategory,
                       error: str) -> RecoveryResult:
        """Create a retry-corrected step."""
        corrected = dict(step)
        corrected["retries"] = step.get("retries", 0) + 1

        # Increase timeout for timeout errors
        if category == ErrorCategory.TIMEOUT:
            corrected["timeout"] = step.get("timeout", 30) * 1.5

        return RecoveryResult(
            success=True,
            strategy=RecoveryStrategy.RETRY,
            error_category=category,
            message=f"Retry attempt #{corrected['retries']}",
            corrected_step=corrected,
            attempts=corrected["retries"],
        )

    def _attempt_alternative(self, step: dict, category: ErrorCategory,
                             error: str) -> RecoveryResult:
        """Find an alternative approach for a failed step."""
        tool = step.get("tool", "")

        # Alternative tool mappings
        alternatives = {
            "search_web": "get_summary",
            "get_news": "search_web",
            "get_summary": "recall_info",
        }

        alt_tool = alternatives.get(tool)
        if alt_tool:
            corrected = dict(step)
            corrected["tool"] = alt_tool
            corrected["original_tool"] = tool
            return RecoveryResult(
                success=True,
                strategy=RecoveryStrategy.ALTERNATIVE,
                error_category=category,
                message=f"Using alternative tool: {alt_tool} instead of {tool}",
                corrected_step=corrected,
            )

        return RecoveryResult(
            success=False,
            strategy=RecoveryStrategy.ALTERNATIVE,
            error_category=category,
            message=f"No alternative available for tool: {tool}",
        )

    def _stats_by_field(self, field: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self._recovery_log:
            val = r.get(field, "unknown")
            counts[val] = counts.get(val, 0) + 1
        return counts
