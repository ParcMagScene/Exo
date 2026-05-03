"""
EXO v22 — ScenarioPlanner
Génère, compare et sélectionne des scénarios alternatifs de planification :
déterministe, probabiliste, contextuel, multi-agent, optimisé.

API:
  generate_scenarios(intent: dict) → dict
  compare_scenarios(scenarios: list) → dict
  select_best_scenario()            → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("scenario_planner")


class ScenarioPlanner:
    """Planificateur de scénarios EXO v22."""

    SCENARIO_TYPES = {
        "deterministic", "probabilistic", "contextual",
        "multi_agent", "optimized",
    }

    def __init__(self, governance=None):
        self._governance = governance

        self._scenarios: list[dict] = []
        self._comparisons: list[dict] = []
        self._stats = {
            "generated": 0,
            "comparisons": 0,
            "selections": 0,
        }

    # ── generate_scenarios ──────────────────────────────────
    def generate_scenarios(self, intent: dict) -> dict:
        """Générer plusieurs scénarios pour un intent donné."""
        self._stats["generated"] += 1

        goal = intent.get("goal", "unknown")
        constraints = intent.get("constraints", [])
        requested_types = intent.get("scenario_types", list(self.SCENARIO_TYPES))

        generated = []
        for i, stype in enumerate(requested_types):
            if stype not in self.SCENARIO_TYPES:
                continue

            steps = self._build_steps(goal, stype, constraints)
            score = self._score_scenario(steps, stype)

            scenario = {
                "id": f"sc_{uuid.uuid4().hex[:6]}",
                "type": stype,
                "goal": goal,
                "steps": steps,
                "score": score,
            }
            generated.append(scenario)

        self._scenarios.extend(generated)
        self._trim()

        return {
            "id": f"gs_{uuid.uuid4().hex[:8]}",
            "generated": True,
            "count": len(generated),
            "scenarios": generated,
            "timestamp": time.time(),
        }

    # ── compare_scenarios ───────────────────────────────────
    def compare_scenarios(self, scenarios: list) -> dict:
        """Comparer une liste de scénarios selon plusieurs axes."""
        self._stats["comparisons"] += 1

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

        result = {
            "id": f"cmp_{uuid.uuid4().hex[:8]}",
            "compared": True,
            "count": len(comparisons),
            "ranking": comparisons,
            "best": comparisons[0] if comparisons else None,
            "timestamp": time.time(),
        }
        self._comparisons.append(result)
        return result

    # ── select_best_scenario ────────────────────────────────
    def select_best_scenario(self) -> dict:
        """Sélectionner le meilleur scénario des dernières comparaisons."""
        self._stats["selections"] += 1

        if not self._comparisons:
            return {
                "selected": False,
                "error": "no_comparisons",
                "timestamp": time.time(),
            }

        last = self._comparisons[-1]
        best = last.get("best")

        return {
            "id": f"sel_{uuid.uuid4().hex[:8]}",
            "selected": True,
            "best_scenario": best,
            "timestamp": time.time(),
        }

    # ── internal helpers ────────────────────────────────────
    def _build_steps(self, goal: str, stype: str, constraints: list) -> list:
        """Construire des étapes de scénario de manière déterministe."""
        base_steps = [
            {"action": "analyse_objectif", "target": goal},
            {"action": "évaluation_faisabilité", "target": goal},
        ]

        if stype == "deterministic":
            base_steps.append({"action": "exécution_directe", "target": goal})
        elif stype == "probabilistic":
            base_steps.append({"action": "estimations_probabilistes", "target": goal})
            base_steps.append({"action": "sélection_meilleure_branche", "target": goal})
        elif stype == "contextual":
            base_steps.append({"action": "analyse_contexte", "target": goal})
            base_steps.append({"action": "adaptation_plan", "target": goal})
        elif stype == "multi_agent":
            base_steps.append({"action": "répartition_agents", "target": goal})
            base_steps.append({"action": "coordination", "target": goal})
        elif stype == "optimized":
            base_steps.append({"action": "optimisation_coûts", "target": goal})
            base_steps.append({"action": "exécution_optimisée", "target": goal})

        if constraints:
            base_steps.append({"action": "vérification_contraintes", "target": goal})

        return base_steps

    def _score_scenario(self, steps: list, stype: str) -> float:
        """Score déterministe d'un scénario."""
        base = 1.0
        base -= len(steps) * 0.05
        type_bonus = {
            "deterministic": 0.3,
            "optimized": 0.25,
            "contextual": 0.2,
            "probabilistic": 0.15,
            "multi_agent": 0.1,
        }
        base += type_bonus.get(stype, 0.0)
        return round(max(0.0, min(1.0, base)), 3)

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "scenario_planner",
            "status": "ok",
            "total_scenarios": len(self._scenarios),
            "total_comparisons": len(self._comparisons),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._scenarios.clear()
        self._comparisons.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ScenarioPlanner restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._scenarios) > 5000:
            self._scenarios = self._scenarios[-2500:]
