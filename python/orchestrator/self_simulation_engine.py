"""
EXO v13 — SelfSimulationEngine (Auto-simulation)
Simule mentalement l'exécution d'un plan avant exécution réelle.
Détecte les risques, évalue les conséquences, propose des alternatives.

API:
  simulate_plan(plan)           → dict
  simulate_step(step)           → dict
  simulate_scenario(scenario)   → dict
  simulate_outcome(plan)        → dict
  health_check()                → dict
  restart()                     → None
  get_stats()                   → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("self_simulation")

# Actions considérées dangereuses lors de simulation
_DANGEROUS_TOOLS = frozenset({
    "rm", "delete", "drop", "format", "shutdown", "reboot",
    "factory_reset", "erase", "wipe",
})

# Paires d'actions contradictoires
_OPPOSING_ACTIONS = [
    ("enable", "disable"), ("start", "stop"), ("open", "close"),
    ("lock", "unlock"), ("on", "off"), ("create", "delete"),
]


class SelfSimulationEngine:
    """Moteur d'auto-simulation EXO v13."""

    def __init__(self, meta_memory, governance=None):
        self._memory = meta_memory
        self._governance = governance
        self._history: list[dict] = []
        self._stats = {
            "plans_simulated": 0,
            "steps_simulated": 0,
            "scenarios_simulated": 0,
            "outcomes_simulated": 0,
            "risks_detected": 0,
        }

    # ── simulate_plan ───────────────────────────────────────
    def simulate_plan(self, plan: dict) -> dict:
        """Simulate full plan execution mentally.

        Returns simulation result with step outcomes, risks, side effects.
        """
        steps = plan.get("steps", [])
        goal = plan.get("goal", "")

        step_results: list[dict] = []
        risks: list[dict] = []
        side_effects: list[dict] = []
        simulated_state: dict[str, Any] = {}

        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            sr = self._simulate_single_step(step, i, simulated_state)
            step_results.append(sr)
            risks.extend(sr.get("risks", []))
            side_effects.extend(sr.get("side_effects", []))
            # Update simulated state
            for effect in sr.get("state_changes", []):
                simulated_state[effect["key"]] = effect["value"]

        # Detect contradictions between steps
        contradictions = self._detect_contradictions(steps)
        risks.extend(contradictions)

        success_probability = self._estimate_success(step_results, risks)
        self._stats["plans_simulated"] += 1
        self._stats["risks_detected"] += len(risks)

        result = {
            "type": "plan_simulation",
            "goal": goal,
            "step_count": len(steps),
            "step_results": step_results,
            "risks": risks,
            "side_effects": side_effects,
            "success_probability": success_probability,
            "governance_ok": True,
            "simulated_state": simulated_state,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── simulate_step ───────────────────────────────────────
    def simulate_step(self, step: dict) -> dict:
        """Simulate a single step."""
        sr = self._simulate_single_step(step, 0, {})
        self._stats["steps_simulated"] += 1
        result = {
            "type": "step_simulation",
            **sr,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── simulate_scenario ───────────────────────────────────
    def simulate_scenario(self, scenario: dict) -> dict:
        """Simulate a scenario (sequence of plans or events).

        scenario: dict with 'name', 'steps' (or 'plans'), 'context'.
        """
        name = scenario.get("name", "unnamed")
        plans = scenario.get("plans", [])
        if not plans:
            # Treat the scenario itself as a single plan
            plans = [scenario]

        plan_results: list[dict] = []
        total_risks: list[dict] = []
        for plan in plans:
            sim = self.simulate_plan(plan)
            plan_results.append(sim)
            total_risks.extend(sim.get("risks", []))

        overall_success = 1.0
        for pr in plan_results:
            overall_success *= pr.get("success_probability", 0.5)

        self._stats["scenarios_simulated"] += 1

        result = {
            "type": "scenario_simulation",
            "name": name,
            "plan_count": len(plans),
            "plan_results": plan_results,
            "total_risks": total_risks,
            "overall_success_probability": round(overall_success, 3),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── simulate_outcome ────────────────────────────────────
    def simulate_outcome(self, plan: dict) -> dict:
        """Simulate and predict the outcome of a plan.

        Returns predicted final state, consequences, and alternatives.
        """
        sim = self.simulate_plan(plan)
        steps = plan.get("steps", [])

        # Compute expected final state
        final_state = dict(sim.get("simulated_state", {}))

        # Compute consequences
        consequences: list[dict] = []
        for se in sim.get("side_effects", []):
            consequences.append({
                "type": "side_effect",
                "description": se.get("description", ""),
                "severity": se.get("severity", "low"),
            })
        for risk in sim.get("risks", []):
            consequences.append({
                "type": "risk",
                "description": risk.get("detail", ""),
                "severity": "high" if risk.get("type") in (
                    "dangerous_tool", "governance_blocked") else "medium",
            })

        # Generate alternatives if risks detected
        alternatives: list[dict] = []
        if sim.get("risks"):
            alt = self._generate_alternative(plan, sim["risks"])
            if alt:
                alternatives.append(alt)

        # Check with MetaMemory for similar past outcomes
        memory_hints = self._check_memory(plan)

        self._stats["outcomes_simulated"] += 1

        result = {
            "type": "outcome_simulation",
            "predicted_state": final_state,
            "consequences": consequences,
            "alternatives": alternatives,
            "memory_hints": memory_hints,
            "success_probability": sim["success_probability"],
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── health_check / restart / stats ──────────────────────
    def health_check(self) -> dict:
        return {
            "service": "self_simulation",
            "status": "ok",
            "history_size": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("SelfSimulationEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── private ─────────────────────────────────────────────
    def _simulate_single_step(self, step: dict, index: int,
                              state: dict) -> dict:
        tool = step.get("tool", "")
        desc = step.get("description", "")
        target = step.get("target", "")

        risks: list[dict] = []
        side_effects: list[dict] = []
        state_changes: list[dict] = []

        # Dangerous tool check
        if tool.lower() in _DANGEROUS_TOOLS:
            risks.append({
                "type": "dangerous_tool",
                "step_index": index,
                "detail": f"Step {index} uses dangerous tool '{tool}'",
            })

        # Estimate state changes
        if tool and target:
            state_changes.append({
                "key": f"{tool}_{target}",
                "value": "executed",
            })

        # Check for side effects
        if tool in ("ha_scene", "ha_automation"):
            side_effects.append({
                "step_index": index,
                "description": f"Scene/automation '{desc}' may affect multiple devices",
                "severity": "medium",
            })

        # Estimate success
        success = 0.9
        if risks:
            success *= 0.5
        if not tool:
            success *= 0.7

        return {
            "step_index": index,
            "tool": tool,
            "description": desc,
            "simulated_success": round(success, 2),
            "risks": risks,
            "side_effects": side_effects,
            "state_changes": state_changes,
        }

    def _detect_contradictions(self, steps: list) -> list[dict]:
        risks = []
        actions: list[tuple[str, str]] = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            tool = step.get("tool", "").lower()
            target = step.get("target", "").lower()
            if tool and target:
                actions.append((tool, target))

        for i, (t1, tgt1) in enumerate(actions):
            for j, (t2, tgt2) in enumerate(actions):
                if j <= i or tgt1 != tgt2:
                    continue
                for pos, neg in _OPPOSING_ACTIONS:
                    if (pos in t1 and neg in t2) or (neg in t1 and pos in t2):
                        risks.append({
                            "type": "contradictory_steps",
                            "step_a": i,
                            "step_b": j,
                            "detail": f"Steps {i} and {j} contradict on '{tgt1}'",
                        })
        return risks

    def _estimate_success(self, step_results: list, risks: list) -> float:
        if not step_results:
            return 0.5
        avg = sum(s.get("simulated_success", 0.5) for s in step_results) / len(step_results)
        penalty = min(len(risks) * 0.1, 0.5)
        return round(max(0.0, avg - penalty), 3)

    def _generate_alternative(self, plan: dict, risks: list) -> dict | None:
        """Generate a safer alternative plan by removing risky steps."""
        steps = plan.get("steps", [])
        risky_indices = {r.get("step_index", -1) for r in risks}
        safe_steps = [s for i, s in enumerate(steps) if i not in risky_indices]
        if not safe_steps or len(safe_steps) == len(steps):
            return None
        return {
            "type": "safe_alternative",
            "goal": plan.get("goal", ""),
            "steps": safe_steps,
            "removed_risky_steps": len(steps) - len(safe_steps),
        }

    def _check_memory(self, plan: dict) -> list[dict]:
        """Check MetaMemory for similar past simulations/outcomes."""
        hints = []
        goal = plan.get("goal", "")
        if goal:
            entries = self._memory.meta_get(goal)
            for e in entries[:3]:
                hints.append({
                    "key": e.get("key", ""),
                    "value": e.get("value"),
                    "confidence": e.get("confidence", 0),
                })
        return hints

    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 500:
            self._history = self._history[-300:]
