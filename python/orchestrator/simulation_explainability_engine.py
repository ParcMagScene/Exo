"""
EXO v23 — SimulationExplainabilityEngine
Explique les scénarios, prédictions, résultats, cohérence et arbitration
de manière transparente et traçable.

API:
  explain_simulation(sim: dict)       → dict
  explain_outcome(outcome: dict)      → dict
  explain_temporal_flow()             → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("simulation_explainability_engine")


class SimulationExplainabilityEngine:
    """Moteur d'explicabilité de simulation EXO v23."""

    def __init__(self, governance=None, sandbox=None):
        self._governance = governance
        self._sandbox = sandbox

        self._explanations: list[dict] = []
        self._stats = {
            "simulations_explained": 0,
            "outcomes_explained": 0,
            "temporal_explained": 0,
        }

    # ── explain_simulation ──────────────────────────────────
    def explain_simulation(self, sim: dict) -> dict:
        """Expliquer une simulation de manière humainement lisible."""
        self._stats["simulations_explained"] += 1

        sim_id = sim.get("id", "unknown")
        results = sim.get("results", [])
        steps = sim.get("steps", [])

        explanation_parts = []

        # Expliquer la structure
        explanation_parts.append({
            "aspect": "structure",
            "description": f"Simulation {sim_id} : {len(steps)} étapes, {len(results)} résultats",
        })

        # Expliquer chaque résultat
        for r in results[:10]:
            explanation_parts.append({
                "aspect": "résultat",
                "scenario_id": r.get("scenario_id", "?"),
                "description": (
                    f"Scénario {r.get('scenario_id', '?')}: "
                    f"score={r.get('score', 0)}, "
                    f"effets={r.get('effects_count', 0)}, "
                    f"succès={'oui' if r.get('success') else 'non'}"
                ),
            })

        record = {
            "id": f"es_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "simulation_id": sim_id,
            "parts_count": len(explanation_parts),
            "parts": explanation_parts,
            "timestamp": time.time(),
        }
        self._explanations.append(record)
        self._trim()

        return record

    # ── explain_outcome ─────────────────────────────────────
    def explain_outcome(self, outcome: dict) -> dict:
        """Expliquer un résultat d'analyse."""
        self._stats["outcomes_explained"] += 1

        analysis = outcome.get("analysis", [])
        aggregated = outcome.get("aggregated", {})

        parts = []
        parts.append({
            "aspect": "agrégation",
            "description": (
                f"Score moyen: {aggregated.get('avg_score', 0)}, "
                f"Taux de succès: {aggregated.get('success_rate', 0)}, "
                f"Total: {aggregated.get('total', 0)}"
            ),
        })

        for a in analysis[:10]:
            parts.append({
                "aspect": "détail",
                "scenario_id": a.get("scenario_id", "?"),
                "description": (
                    f"Score={a.get('score', 0)}, "
                    f"Risque={a.get('risk_level', '?')}, "
                    f"Succès={'oui' if a.get('success') else 'non'}"
                ),
            })

        record = {
            "id": f"eo_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "parts_count": len(parts),
            "parts": parts,
            "timestamp": time.time(),
        }
        self._explanations.append(record)
        self._trim()

        return record

    # ── explain_temporal_flow ───────────────────────────────
    def explain_temporal_flow(self) -> dict:
        """Expliquer le flux temporel des simulations récentes."""
        self._stats["temporal_explained"] += 1

        recent = [e for e in self._explanations[-20:]
                  if "simulation_id" in e]

        parts = []
        for e in recent[:5]:
            parts.append({
                "simulation_id": e.get("simulation_id", "?"),
                "description": f"Simulation {e.get('simulation_id', '?')} expliquée avec {e.get('parts_count', 0)} parties",
            })

        if not parts:
            parts.append({
                "simulation_id": "none",
                "description": "Aucune simulation récente à expliquer",
            })

        return {
            "id": f"etf_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "count": len(parts),
            "parts": parts,
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "simulation_explainability_engine",
            "status": "ok",
            "total_explanations": len(self._explanations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._explanations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("SimulationExplainabilityEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._explanations) > 5000:
            self._explanations = self._explanations[-2500:]
