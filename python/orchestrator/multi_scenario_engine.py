"""
EXO v13 — MultiScenarioEngine (Comparaison de futurs)
Génère, compare et sélectionne parmi plusieurs futurs possibles.

API:
  generate_future_variants(plan)  → dict
  compare_futures(futures)        → dict
  select_best_future(futures)     → dict
  get_stats()                     → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("multi_scenario")


class MultiScenarioEngine:
    """Moteur de comparaison de futurs EXO v13."""

    def __init__(self, meta_memory, simulation_engine=None,
                 governance=None):
        self._memory = meta_memory
        self._simulation = simulation_engine
        self._governance = governance
        self._history: list[dict] = []
        self._stats = {
            "variants_generated": 0,
            "comparisons": 0,
            "selections": 0,
        }

    # ── generate_future_variants ────────────────────────────
    def generate_future_variants(self, plan: dict) -> dict:
        """Generate multiple variants of a plan for comparison.

        Creates: original, optimized, conservative, minimal versions.
        """
        steps = plan.get("steps", [])
        goal = plan.get("goal", "")

        variants: list[dict] = []

        # Variant 0: Original plan
        v_original = {
            "variant_id": 0,
            "name": "original",
            "plan": dict(plan),
            "description": "Plan original sans modification",
        }
        variants.append(v_original)

        # Variant 1: Optimized — remove redundant steps
        opt_steps = self._optimize_steps(steps)
        variants.append({
            "variant_id": 1,
            "name": "optimized",
            "plan": {"goal": goal, "steps": opt_steps,
                     "constraints": plan.get("constraints", [])},
            "description": "Plan optimisé (étapes redondantes supprimées)",
        })

        # Variant 2: Conservative — add safety checks
        safe_steps = self._add_safety_steps(steps)
        variants.append({
            "variant_id": 2,
            "name": "conservative",
            "plan": {"goal": goal, "steps": safe_steps,
                     "constraints": plan.get("constraints", [])},
            "description": "Plan conservateur (vérifications ajoutées)",
        })

        # Variant 3: Minimal — only essential steps
        min_steps = self._minimal_steps(steps)
        variants.append({
            "variant_id": 3,
            "name": "minimal",
            "plan": {"goal": goal, "steps": min_steps,
                     "constraints": plan.get("constraints", [])},
            "description": "Plan minimal (étapes essentielles uniquement)",
        })

        # Simulate each variant if simulation engine is available
        if self._simulation:
            for v in variants:
                sim = self._simulation.simulate_plan(v["plan"])
                v["simulation"] = {
                    "success_probability": sim.get("success_probability", 0.5),
                    "risk_count": len(sim.get("risks", [])),
                    "side_effect_count": len(sim.get("side_effects", [])),
                }

        self._stats["variants_generated"] += 1

        result = {
            "type": "future_variants",
            "goal": goal,
            "variant_count": len(variants),
            "variants": variants,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── compare_futures ─────────────────────────────────────
    def compare_futures(self, futures: list[dict]) -> dict:
        """Compare multiple future variants on key dimensions.

        Each future should have: name, plan (with steps), and optionally
        simulation results.
        """
        if not futures:
            self._stats["comparisons"] += 1
            return {
                "type": "future_comparison",
                "comparison": [],
                "ranking": [],
                "best_index": -1,
                "timestamp": time.time(),
            }

        comparison: list[dict] = []
        for i, future in enumerate(futures):
            plan = future.get("plan", {})
            sim = future.get("simulation", {})
            steps = plan.get("steps", [])

            score = self._score_future(future)

            comparison.append({
                "index": i,
                "name": future.get("name", f"variant_{i}"),
                "step_count": len(steps),
                "success_probability": sim.get("success_probability", 0.5),
                "risk_count": sim.get("risk_count", 0),
                "side_effect_count": sim.get("side_effect_count", 0),
                "score": score,
            })

        # Sort by score descending
        ranking = sorted(comparison, key=lambda c: c["score"], reverse=True)
        best_index = ranking[0]["index"] if ranking else -1

        self._stats["comparisons"] += 1

        result = {
            "type": "future_comparison",
            "comparison": comparison,
            "ranking": [r["index"] for r in ranking],
            "best_index": best_index,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── select_best_future ──────────────────────────────────
    def select_best_future(self, futures: list[dict]) -> dict:
        """Select the best future variant.

        Returns the selected future with justification.
        """
        comp = self.compare_futures(futures)
        best_idx = comp["best_index"]

        if best_idx < 0 or best_idx >= len(futures):
            self._stats["selections"] += 1
            return {
                "type": "future_selection",
                "selected": None,
                "reason": "Aucun futur disponible",
                "timestamp": time.time(),
            }

        selected = futures[best_idx]
        ranking = comp.get("ranking", [])

        # Build justification
        reasons: list[str] = []
        sel_comp = next(
            (c for c in comp["comparison"] if c["index"] == best_idx), {})
        reasons.append(f"Score global: {sel_comp.get('score', 0):.2f}")
        if sel_comp.get("risk_count", 0) == 0:
            reasons.append("Aucun risque détecté")
        if sel_comp.get("success_probability", 0) > 0.7:
            reasons.append(f"Probabilité de succès: "
                           f"{sel_comp.get('success_probability', 0):.0%}")

        self._stats["selections"] += 1

        result = {
            "type": "future_selection",
            "selected_index": best_idx,
            "selected": selected,
            "reason": "; ".join(reasons),
            "ranking": ranking,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── stats ───────────────────────────────────────────────
    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── private ─────────────────────────────────────────────
    def _score_future(self, future: dict) -> float:
        """Score a future variant (0..1)."""
        plan = future.get("plan", {})
        sim = future.get("simulation", {})
        steps = plan.get("steps", [])

        # Base score
        score = 0.5

        # Success probability bonus
        success = sim.get("success_probability", 0.5)
        score += success * 0.3

        # Penalty for risks
        risk_count = sim.get("risk_count", 0)
        score -= min(risk_count * 0.05, 0.2)

        # Penalty for side effects
        se_count = sim.get("side_effect_count", 0)
        score -= min(se_count * 0.03, 0.1)

        # Bonus for fewer steps (efficiency)
        if 1 <= len(steps) <= 5:
            score += 0.1
        elif len(steps) > 10:
            score -= 0.05

        # Bonus for having a goal
        if plan.get("goal"):
            score += 0.05

        return round(max(0.0, min(1.0, score)), 3)

    def _optimize_steps(self, steps: list) -> list:
        """Remove duplicate / empty steps."""
        seen: set[str] = set()
        result = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            key = f"{step.get('tool', '')}_{step.get('description', '')}"
            if key in seen or not key.strip("_"):
                continue
            seen.add(key)
            result.append(step)
        return result

    def _add_safety_steps(self, steps: list) -> list:
        """Prepend/append safety verification steps."""
        safe = []
        if steps:
            safe.append({
                "tool": "verify_preconditions",
                "description": "Vérifier les pré-conditions avant exécution",
            })
        safe.extend(steps)
        if steps:
            safe.append({
                "tool": "verify_postconditions",
                "description": "Vérifier le résultat après exécution",
            })
        return safe

    def _minimal_steps(self, steps: list) -> list:
        """Keep only steps with a tool defined."""
        return [s for s in steps if isinstance(s, dict) and s.get("tool")]

    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 500:
            self._history = self._history[-300:]
