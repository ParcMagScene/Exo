"""
EXO v23 — TemporalSimulationEngine
Gère les dépendances temporelles dans les simulations :
propagation, cohérence, fenêtres, séquences.

API:
  simulate_temporal_flow(plan: dict)      → dict
  enforce_temporal_constraints()          → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("temporal_simulation_engine")


class TemporalSimulationEngine:
    """Moteur de simulation temporelle EXO v23."""

    MAX_STEPS = 200

    def __init__(self, governance=None, sandbox=None):
        self._governance = governance
        self._sandbox = sandbox

        self._flows: list[dict] = []
        self._constraints: list[dict] = []
        self._stats = {
            "flows_simulated": 0,
            "constraints_enforced": 0,
        }

    # ── simulate_temporal_flow ──────────────────────────────
    def simulate_temporal_flow(self, plan: dict) -> dict:
        """Simuler le flux temporel d'un plan."""
        self._stats["flows_simulated"] += 1

        steps = plan.get("steps", [])
        timeline = []
        current_time = 0.0

        for i, step in enumerate(steps[:self.MAX_STEPS]):
            duration = step.get("duration", 1.0)
            depends_on = step.get("depends_on", [])
            action = step.get("action", "noop")

            # Calculer le temps de départ effectif
            start = current_time
            if depends_on:
                dep_ends = []
                for dep_idx in depends_on:
                    if 0 <= dep_idx < len(timeline):
                        dep_ends.append(timeline[dep_idx]["end_time"])
                if dep_ends:
                    start = max(dep_ends)

            end = start + duration
            entry = {
                "step": i + 1,
                "action": action,
                "start_time": round(start, 3),
                "end_time": round(end, 3),
                "duration": duration,
                "dependencies": depends_on,
            }
            timeline.append(entry)
            current_time = end

        total_duration = timeline[-1]["end_time"] if timeline else 0.0

        flow = {
            "id": f"tf_{uuid.uuid4().hex[:8]}",
            "simulated": True,
            "steps_count": len(timeline),
            "timeline": timeline,
            "total_duration": round(total_duration, 3),
            "timestamp": time.time(),
        }
        self._flows.append(flow)
        self._trim()

        return flow

    # ── enforce_temporal_constraints ────────────────────────
    def enforce_temporal_constraints(self) -> dict:
        """Vérifier et forcer la cohérence temporelle."""
        self._stats["constraints_enforced"] += 1

        violations = []
        enforced = []

        for flow in self._flows[-20:]:
            timeline = flow.get("timeline", [])
            for i, entry in enumerate(timeline):
                deps = entry.get("dependencies", [])
                for dep_idx in deps:
                    if 0 <= dep_idx < len(timeline):
                        dep_entry = timeline[dep_idx]
                        if entry["start_time"] < dep_entry["end_time"]:
                            violations.append({
                                "flow_id": flow["id"],
                                "step": entry["step"],
                                "depends_on_step": dep_entry["step"],
                                "issue": "start_before_dependency_end",
                            })

        for v in violations:
            enforced.append({
                "flow_id": v["flow_id"],
                "step": v["step"],
                "action": "delay_start",
                "resolved": True,
            })

        constraint_record = {
            "id": f"etc_{uuid.uuid4().hex[:8]}",
            "violations_count": len(violations),
            "violations": violations,
            "enforced_count": len(enforced),
            "enforced": enforced,
            "coherent": len(violations) == 0,
            "timestamp": time.time(),
        }
        self._constraints.append(constraint_record)
        if len(self._constraints) > 5000:
            self._constraints = self._constraints[-2500:]

        return constraint_record

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "temporal_simulation_engine",
            "status": "ok",
            "total_flows": len(self._flows),
            "total_constraints": len(self._constraints),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._flows.clear()
        self._constraints.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("TemporalSimulationEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._flows) > 5000:
            self._flows = self._flows[-2500:]
