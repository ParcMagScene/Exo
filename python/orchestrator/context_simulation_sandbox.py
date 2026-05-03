"""
EXO v23 — ContextSimulationSandbox
Environnement isolé pour simuler des plans, contextes et états
dans une sandbox logique sécurisée.

API:
  sandbox_init(context: dict) → dict
  sandbox_run(plan: dict)     → dict
  sandbox_snapshot()           → dict
  health_check() / restart() / get_stats()
"""

import copy
import logging
import time
import uuid

log = logging.getLogger("context_simulation_sandbox")


class ContextSimulationSandbox:
    """Sandbox de simulation contextuelle EXO v23."""

    MAX_DEPTH = 50
    MAX_STEPS = 200

    def __init__(self, governance=None):
        self._governance = governance

        self._context: dict = {}
        self._state: dict = {}
        self._history: list[dict] = []
        self._snapshots: list[dict] = []
        self._active = False
        self._stats = {
            "inits": 0,
            "runs": 0,
            "snapshots": 0,
        }

    # ── sandbox_init ────────────────────────────────────────
    def sandbox_init(self, context: dict) -> dict:
        """Initialiser la sandbox avec un contexte."""
        self._stats["inits"] += 1

        self._context = copy.deepcopy(context)
        self._state = {
            "variables": copy.deepcopy(context.get("variables", {})),
            "agents": list(context.get("agents", [])),
            "constraints": list(context.get("constraints", [])),
            "time": context.get("time", 0),
        }
        self._history.clear()
        self._active = True

        result = {
            "id": f"sbox_{uuid.uuid4().hex[:8]}",
            "initialized": True,
            "context_keys": list(self._context.keys()),
            "variables_count": len(self._state["variables"]),
            "agents_count": len(self._state["agents"]),
            "constraints_count": len(self._state["constraints"]),
            "timestamp": time.time(),
        }
        self._history.append({"event": "init", "timestamp": result["timestamp"]})
        self._trim()
        return result

    # ── sandbox_run ─────────────────────────────────────────
    def sandbox_run(self, plan: dict) -> dict:
        """Exécuter un plan dans la sandbox."""
        self._stats["runs"] += 1

        if not self._active:
            return {
                "executed": False,
                "error": "sandbox_not_initialized",
                "timestamp": time.time(),
            }

        steps = plan.get("steps", [])
        if len(steps) > self.MAX_STEPS:
            return {
                "executed": False,
                "error": "too_many_steps",
                "max_steps": self.MAX_STEPS,
                "timestamp": time.time(),
            }

        results = []
        state_before = copy.deepcopy(self._state)

        for i, step in enumerate(steps):
            action = step.get("action", "noop")
            target = step.get("target", "")
            value = step.get("value")

            effect = self._apply_step(action, target, value)
            results.append({
                "step": i + 1,
                "action": action,
                "target": target,
                "effect": effect,
                "state_time": self._state["time"],
            })
            self._state["time"] += 1

        state_after = copy.deepcopy(self._state)
        changes = self._diff_states(state_before, state_after)

        result = {
            "id": f"run_{uuid.uuid4().hex[:8]}",
            "executed": True,
            "steps_executed": len(results),
            "results": results,
            "changes": changes,
            "changes_count": len(changes),
            "final_time": self._state["time"],
            "timestamp": time.time(),
        }
        self._history.append({"event": "run", "steps": len(results),
                              "timestamp": result["timestamp"]})
        self._trim()
        return result

    # ── sandbox_snapshot ────────────────────────────────────
    def sandbox_snapshot(self) -> dict:
        """Capturer l'état actuel de la sandbox."""
        self._stats["snapshots"] += 1

        snapshot = {
            "id": f"snap_{uuid.uuid4().hex[:8]}",
            "active": self._active,
            "state": copy.deepcopy(self._state),
            "history_length": len(self._history),
            "timestamp": time.time(),
        }
        self._snapshots.append(snapshot)
        if len(self._snapshots) > 1000:
            self._snapshots = self._snapshots[-500:]
        return snapshot

    # ── internals ───────────────────────────────────────────
    def _apply_step(self, action: str, target: str, value) -> str:
        if action == "set":
            self._state["variables"][target] = value
            return f"variable '{target}' = {value}"
        elif action == "increment":
            cur = self._state["variables"].get(target, 0)
            self._state["variables"][target] = cur + (value if value else 1)
            return f"variable '{target}' incrémentée"
        elif action == "add_agent":
            if target and target not in self._state["agents"]:
                self._state["agents"].append(target)
            return f"agent '{target}' ajouté"
        elif action == "remove_agent":
            if target in self._state["agents"]:
                self._state["agents"].remove(target)
            return f"agent '{target}' retiré"
        elif action == "add_constraint":
            self._state["constraints"].append({"name": target, "value": value})
            return f"contrainte '{target}' ajoutée"
        else:
            return f"action '{action}' exécutée (noop)"

    def _diff_states(self, before: dict, after: dict) -> list:
        changes = []
        for key in set(list(before.get("variables", {}).keys()) +
                       list(after.get("variables", {}).keys())):
            v_b = before.get("variables", {}).get(key)
            v_a = after.get("variables", {}).get(key)
            if v_b != v_a:
                changes.append({"variable": key, "before": v_b, "after": v_a})
        if before.get("agents") != after.get("agents"):
            changes.append({"agents_before": before.get("agents"),
                            "agents_after": after.get("agents")})
        return changes

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "context_simulation_sandbox",
            "status": "ok",
            "active": self._active,
            "history_length": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._context.clear()
        self._state.clear()
        self._history.clear()
        self._snapshots.clear()
        self._active = False
        for k in self._stats:
            self._stats[k] = 0
        log.info("ContextSimulationSandbox restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-2500:]
