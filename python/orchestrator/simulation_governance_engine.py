"""
EXO v23 — SimulationGovernanceEngine
Supervise et contrôle toutes les simulations :
validation, blocage, audit, limites de profondeur/complexité.

API:
  validate_simulation(sim: dict) → dict
  block_simulation(sim: dict)    → dict
  audit_simulation(sim: dict)    → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("simulation_governance_engine")


class SimulationGovernanceEngine:
    """Moteur de gouvernance de simulation EXO v23."""

    MAX_DEPTH = 50
    MAX_STEPS = 200
    MAX_SCORE_DRIFT = 0.8

    def __init__(self, governance=None, sandbox=None):
        self._governance = governance
        self._sandbox = sandbox

        self._validations: list[dict] = []
        self._blocks: list[dict] = []
        self._audits: list[dict] = []
        self._stats = {
            "validated": 0,
            "blocked": 0,
            "audited": 0,
        }

    # ── validate_simulation ─────────────────────────────────
    def validate_simulation(self, sim: dict) -> dict:
        """Valider qu'une simulation respecte les règles de gouvernance."""
        self._stats["validated"] += 1

        steps = sim.get("steps", [])
        depth = sim.get("depth", 0)
        violations = []

        if len(steps) > self.MAX_STEPS:
            violations.append({
                "type": "max_steps_exceeded",
                "limit": self.MAX_STEPS,
                "actual": len(steps),
            })

        if depth > self.MAX_DEPTH:
            violations.append({
                "type": "max_depth_exceeded",
                "limit": self.MAX_DEPTH,
                "actual": depth,
            })

        # Vérifier les scores anormaux
        scores = [s.get("score", 0.5) for s in steps if "score" in s]
        if scores:
            spread = max(scores) - min(scores)
            if spread > self.MAX_SCORE_DRIFT:
                violations.append({
                    "type": "score_drift",
                    "limit": self.MAX_SCORE_DRIFT,
                    "actual": round(spread, 3),
                })

        valid = len(violations) == 0

        record = {
            "id": f"vs_{uuid.uuid4().hex[:8]}",
            "valid": valid,
            "violations_count": len(violations),
            "violations": violations,
            "timestamp": time.time(),
        }
        self._validations.append(record)
        self._trim()

        return record

    # ── block_simulation ────────────────────────────────────
    def block_simulation(self, sim: dict) -> dict:
        """Bloquer une simulation jugée non conforme."""
        self._stats["blocked"] += 1

        reason = sim.get("block_reason", "governance_violation")
        sim_id = sim.get("id", f"sim_{uuid.uuid4().hex[:6]}")

        block = {
            "id": f"bs_{uuid.uuid4().hex[:8]}",
            "blocked": True,
            "simulation_id": sim_id,
            "reason": reason,
            "timestamp": time.time(),
        }
        self._blocks.append(block)
        if len(self._blocks) > 5000:
            self._blocks = self._blocks[-2500:]

        return block

    # ── audit_simulation ────────────────────────────────────
    def audit_simulation(self, sim: dict) -> dict:
        """Auditer une simulation pour traçabilité."""
        self._stats["audited"] += 1

        sim_id = sim.get("id", "unknown")
        steps = sim.get("steps", [])
        results = sim.get("results", [])

        audit_entries = []
        audit_entries.append({
            "aspect": "structure",
            "steps_count": len(steps),
            "results_count": len(results),
            "compliant": len(steps) <= self.MAX_STEPS,
        })
        audit_entries.append({
            "aspect": "governance",
            "depth": sim.get("depth", 0),
            "max_depth_compliant": sim.get("depth", 0) <= self.MAX_DEPTH,
        })

        compliant = all(e.get("compliant", e.get("max_depth_compliant", True))
                        for e in audit_entries)

        audit = {
            "id": f"as_{uuid.uuid4().hex[:8]}",
            "audited": True,
            "simulation_id": sim_id,
            "entries": audit_entries,
            "compliant": compliant,
            "timestamp": time.time(),
        }
        self._audits.append(audit)
        if len(self._audits) > 5000:
            self._audits = self._audits[-2500:]

        return audit

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "simulation_governance_engine",
            "status": "ok",
            "total_validations": len(self._validations),
            "total_blocks": len(self._blocks),
            "total_audits": len(self._audits),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._validations.clear()
        self._blocks.clear()
        self._audits.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("SimulationGovernanceEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._validations) > 5000:
            self._validations = self._validations[-2500:]
