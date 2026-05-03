"""
EXO v23 — MultiScenarioSimulationEngine
Génère et simule plusieurs scénarios alternatifs dans la sandbox,
puis compare les résultats.

API:
  generate_scenarios(plan: dict)         → dict
  simulate_scenarios(scenarios: list)    → dict
  compare_scenarios(scenarios: list)     → dict
  health_check() / restart() / get_stats()
"""

import copy
import logging
import time
import uuid

log = logging.getLogger("multi_scenario_simulation_engine")


class MultiScenarioSimulationEngine:
    """Moteur de simulation multi-scénarios EXO v23."""

    SCENARIO_TYPES = {
        "deterministic", "probabilistic", "contextual",
        "multi_agent", "optimized",
    }

    def __init__(self, governance=None, sandbox=None):
        self._governance = governance
        self._sandbox = sandbox

        self._scenarios: list[dict] = []
        self._simulations: list[dict] = []
        self._stats = {
            "generated": 0,
            "simulated": 0,
            "compared": 0,
        }

    # ── generate_scenarios ──────────────────────────────────
    def generate_scenarios(self, plan: dict) -> dict:
        """Générer des scénarios alternatifs à partir d'un plan."""
        self._stats["generated"] += 1

        goal = plan.get("goal", "unknown")
        steps = plan.get("steps", [])
        types = plan.get("scenario_types", list(self.SCENARIO_TYPES))

        generated = []
        for stype in types:
            if stype not in self.SCENARIO_TYPES:
                continue
            sc_steps = self._vary_steps(steps, stype)
            score = self._score_scenario(sc_steps, stype)
            scenario = {
                "id": f"sim_sc_{uuid.uuid4().hex[:6]}",
                "type": stype,
                "goal": goal,
                "steps": sc_steps,
                "score": score,
            }
            generated.append(scenario)

        self._scenarios.extend(generated)
        self._trim()

        return {
            "id": f"gsc_{uuid.uuid4().hex[:8]}",
            "generated": True,
            "count": len(generated),
            "scenarios": generated,
            "timestamp": time.time(),
        }

    # ── simulate_scenarios ──────────────────────────────────
    def simulate_scenarios(self, scenarios: list) -> dict:
        """Simuler chaque scénario et collecter les résultats."""
        self._stats["simulated"] += 1

        results = []
        for sc in scenarios:
            steps = sc.get("steps", [])
            sim_result = self._simulate_one(sc)
            results.append(sim_result)

        self._simulations.extend(results)
        if len(self._simulations) > 5000:
            self._simulations = self._simulations[-2500:]

        return {
            "id": f"ssc_{uuid.uuid4().hex[:8]}",
            "simulated": True,
            "count": len(results),
            "results": results,
            "timestamp": time.time(),
        }

    # ── compare_scenarios ───────────────────────────────────
    def compare_scenarios(self, scenarios: list) -> dict:
        """Comparer les scénarios simulés."""
        self._stats["compared"] += 1

        ranked = sorted(scenarios, key=lambda s: s.get("score", 0), reverse=True)

        comparisons = []
        for i, sc in enumerate(ranked):
            comparisons.append({
                "id": sc.get("id", f"sc_{i}"),
                "type": sc.get("type", "unknown"),
                "score": sc.get("score", 0),
                "rank": i + 1,
                "steps_count": len(sc.get("steps", [])),
            })

        best = comparisons[0] if comparisons else None

        return {
            "id": f"csc_{uuid.uuid4().hex[:8]}",
            "compared": True,
            "count": len(comparisons),
            "ranking": comparisons,
            "best": best,
            "timestamp": time.time(),
        }

    # ── internal helpers ────────────────────────────────────
    def _vary_steps(self, steps: list, stype: str) -> list:
        """Créer une variation de steps selon le type de scénario."""
        varied = copy.deepcopy(steps)
        if stype == "optimized":
            # Retirer les étapes redondantes
            seen = set()
            deduped = []
            for s in varied:
                a = s.get("action", "")
                if a not in seen:
                    seen.add(a)
                    deduped.append(s)
            varied = deduped
        elif stype == "multi_agent":
            for i, s in enumerate(varied):
                s["agent"] = f"agent_{i % 3}"
        elif stype == "probabilistic":
            varied.append({"action": "évaluation_probabiliste", "target": "all"})
        elif stype == "contextual":
            varied.insert(0, {"action": "analyse_contexte", "target": "env"})

        return varied

    def _score_scenario(self, steps: list, stype: str) -> float:
        base = 1.0
        base -= len(steps) * 0.04
        bonus = {"deterministic": 0.3, "optimized": 0.25, "contextual": 0.2,
                 "probabilistic": 0.15, "multi_agent": 0.1}
        base += bonus.get(stype, 0.0)
        return round(max(0.0, min(1.0, base)), 3)

    def _simulate_one(self, scenario: dict) -> dict:
        steps = scenario.get("steps", [])
        effects = []
        for i, step in enumerate(steps):
            effects.append({
                "step": i + 1,
                "action": step.get("action", "noop"),
                "simulated": True,
                "effect": f"effet simulé pour {step.get('action', 'noop')}",
            })
        return {
            "scenario_id": scenario.get("id", "unknown"),
            "type": scenario.get("type", "unknown"),
            "score": scenario.get("score", 0),
            "effects": effects,
            "effects_count": len(effects),
            "success": True,
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "multi_scenario_simulation_engine",
            "status": "ok",
            "total_scenarios": len(self._scenarios),
            "total_simulations": len(self._simulations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._scenarios.clear()
        self._simulations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("MultiScenarioSimulationEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._scenarios) > 5000:
            self._scenarios = self._scenarios[-2500:]
