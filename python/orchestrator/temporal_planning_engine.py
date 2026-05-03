"""
EXO v22 — TemporalPlanningEngine
Gère les contraintes temporelles complexes dans les plans :
dépendances, fenêtres d'exécution, séquences obligatoires/interdites.

API:
  analyze_temporal_constraints(plan: dict) → dict
  enforce_temporal_order(plan: dict)       → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("temporal_planning_engine")


class TemporalPlanningEngine:
    """Moteur de planification temporelle EXO v22."""

    def __init__(self, governance=None):
        self._governance = governance

        self._analyses: list[dict] = []
        self._stats = {
            "analyses": 0,
            "enforcements": 0,
        }

    # ── analyze_temporal_constraints ────────────────────────
    def analyze_temporal_constraints(self, plan: dict) -> dict:
        """Analyser les contraintes temporelles d'un plan."""
        self._stats["analyses"] += 1

        steps = plan.get("steps", [])
        temporal_constraints = plan.get("temporal_constraints", [])

        issues = []
        valid_sequences = []

        for tc in temporal_constraints:
            tc_type = tc.get("type", "dependency")
            before = tc.get("before")
            after = tc.get("after")
            window = tc.get("window")

            if tc_type == "dependency":
                if before is not None and after is not None:
                    step_ids = [s.get("id", i) for i, s in enumerate(steps)]
                    if before in step_ids and after in step_ids:
                        b_idx = step_ids.index(before)
                        a_idx = step_ids.index(after)
                        if b_idx >= a_idx:
                            issues.append({
                                "type": "dependency_violation",
                                "before": before,
                                "after": after,
                                "detail": f"L'étape {before} doit précéder {after}",
                            })
                        else:
                            valid_sequences.append({"before": before, "after": after})

            elif tc_type == "window":
                if window is not None:
                    start = window.get("start", 0)
                    end = window.get("end", float("inf"))
                    if start > end:
                        issues.append({
                            "type": "invalid_window",
                            "window": window,
                            "detail": "Début de fenêtre après la fin",
                        })

            elif tc_type == "forbidden_sequence":
                seq = tc.get("sequence", [])
                step_ids = [s.get("id", i) for i, s in enumerate(steps)]
                found = True
                for sid in seq:
                    if sid not in step_ids:
                        found = False
                        break
                if found and len(seq) >= 2:
                    indices = [step_ids.index(sid) for sid in seq]
                    if indices == sorted(indices):
                        issues.append({
                            "type": "forbidden_sequence_detected",
                            "sequence": seq,
                            "detail": "Séquence interdite détectée dans le plan",
                        })

        result = {
            "id": f"tpa_{uuid.uuid4().hex[:8]}",
            "analyzed": True,
            "steps_count": len(steps),
            "constraints_count": len(temporal_constraints),
            "issues_count": len(issues),
            "issues": issues,
            "valid_sequences": valid_sequences,
            "temporally_valid": len(issues) == 0,
            "timestamp": time.time(),
        }
        self._analyses.append(result)
        self._trim()

        return result

    # ── enforce_temporal_order ──────────────────────────────
    def enforce_temporal_order(self, plan: dict) -> dict:
        """Réordonner les étapes pour satisfaire les contraintes temporelles."""
        self._stats["enforcements"] += 1

        steps = list(plan.get("steps", []))
        temporal_constraints = plan.get("temporal_constraints", [])

        dependencies: dict[str, list[str]] = {}

        for tc in temporal_constraints:
            if tc.get("type") == "dependency":
                before = tc.get("before")
                after = tc.get("after")
                if before is not None and after is not None:
                    dependencies.setdefault(after, []).append(before)

        step_map = {s.get("id", i): s for i, s in enumerate(steps)}
        ordered_ids: list = []
        visited: set = set()

        def topo_visit(sid):
            if sid in visited:
                return
            visited.add(sid)
            for dep in dependencies.get(sid, []):
                if dep in step_map:
                    topo_visit(dep)
            ordered_ids.append(sid)

        for sid in step_map:
            topo_visit(sid)

        ordered_steps = []
        for sid in ordered_ids:
            if sid in step_map:
                ordered_steps.append(step_map[sid])

        remaining = [s for s in steps if s not in ordered_steps]
        ordered_steps.extend(remaining)

        return {
            "id": f"tpe_{uuid.uuid4().hex[:8]}",
            "enforced": True,
            "original_count": len(steps),
            "ordered_count": len(ordered_steps),
            "steps": ordered_steps,
            "reordered": ordered_steps != steps,
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "temporal_planning_engine",
            "status": "ok",
            "total_analyses": len(self._analyses),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._analyses.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("TemporalPlanningEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._analyses) > 5000:
            self._analyses = self._analyses[-2500:]
