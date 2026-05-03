"""
EXO v10 — AgentStateMachine
Machine à états cognitifs de l'agent EXO.

Définit les états possibles de l'agent et les transitions valides.
Garantit que l'agent ne peut pas passer directement d'un état
à un état incohérent.

API:
  set_state(state)    → bool
  get_state()         → AgentState
  can_transition(to)  → bool
  get_history()       → list[dict]
"""

import logging
import time
from enum import Enum

log = logging.getLogger("agent_state_machine")


class AgentState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    OPTIMIZING = "optimizing"


# Valid state transitions: from_state → {allowed target states}
VALID_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.IDLE: {
        AgentState.LISTENING,
        AgentState.THINKING,
    },
    AgentState.LISTENING: {
        AgentState.THINKING,
        AgentState.IDLE,
    },
    AgentState.THINKING: {
        AgentState.PLANNING,
        AgentState.EXECUTING,  # simple tasks skip planning
        AgentState.IDLE,
    },
    AgentState.PLANNING: {
        AgentState.EXECUTING,
        AgentState.OPTIMIZING,
        AgentState.IDLE,
    },
    AgentState.EXECUTING: {
        AgentState.VERIFYING,
        AgentState.RECOVERING,
        AgentState.IDLE,
    },
    AgentState.VERIFYING: {
        AgentState.OPTIMIZING,
        AgentState.RECOVERING,
        AgentState.IDLE,
    },
    AgentState.RECOVERING: {
        AgentState.EXECUTING,  # retry after recovery
        AgentState.PLANNING,   # replan after recovery
        AgentState.IDLE,
    },
    AgentState.OPTIMIZING: {
        AgentState.IDLE,
        AgentState.EXECUTING,  # re-execute optimized plan
    },
}

MAX_HISTORY = 200


class AgentStateMachine:
    """Finite state machine for the EXO cognitive agent."""

    def __init__(self) -> None:
        self._state = AgentState.IDLE
        self._history: list[dict] = []
        self._state_entered_at: float = time.time()

    @property
    def state(self) -> AgentState:
        return self._state

    def get_state(self) -> dict:
        """Get current state with metadata."""
        return {
            "state": self._state.value,
            "since": self._state_entered_at,
            "duration_s": round(time.time() - self._state_entered_at, 3),
        }

    def can_transition(self, target: AgentState | str) -> bool:
        """Check if a transition to the target state is valid."""
        if isinstance(target, str):
            try:
                target = AgentState(target)
            except ValueError:
                return False
        allowed = VALID_TRANSITIONS.get(self._state, set())
        return target in allowed

    def set_state(self, target: AgentState | str) -> bool:
        """Transition to a new state if valid.

        Returns True on success, False if the transition is invalid.
        """
        if isinstance(target, str):
            try:
                target = AgentState(target)
            except ValueError:
                log.warning("Invalid state: %s", target)
                return False

        if target == self._state:
            return True  # no-op

        if not self.can_transition(target):
            log.warning("Invalid transition: %s → %s", self._state.value, target.value)
            return False

        now = time.time()
        duration = round(now - self._state_entered_at, 3)

        self._history.append({
            "from": self._state.value,
            "to": target.value,
            "timestamp": now,
            "duration_s": duration,
        })
        if len(self._history) > MAX_HISTORY:
            self._history = self._history[-MAX_HISTORY:]

        log.info("State: %s → %s (was %ss)", self._state.value, target.value, duration)
        self._state = target
        self._state_entered_at = now
        return True

    def force_state(self, target: AgentState | str) -> None:
        """Force a state transition (bypasses validation). Use for error recovery only."""
        if isinstance(target, str):
            target = AgentState(target)

        now = time.time()
        self._history.append({
            "from": self._state.value,
            "to": target.value,
            "timestamp": now,
            "forced": True,
        })
        log.warning("Forced state: %s → %s", self._state.value, target.value)
        self._state = target
        self._state_entered_at = now

    def get_history(self, limit: int = 20) -> list[dict]:
        return self._history[-limit:]

    def get_stats(self) -> dict:
        """Get state machine statistics."""
        state_durations: dict[str, float] = {}
        state_counts: dict[str, int] = {}

        for entry in self._history:
            from_state = entry["from"]
            duration = entry.get("duration_s", 0.0)
            state_durations[from_state] = state_durations.get(from_state, 0.0) + duration
            state_counts[from_state] = state_counts.get(from_state, 0) + 1

        return {
            "total_transitions": len(self._history),
            "current_state": self._state.value,
            "state_durations_s": state_durations,
            "state_counts": state_counts,
        }
