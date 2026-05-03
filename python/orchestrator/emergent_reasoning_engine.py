"""
EXO v16 — EmergentReasoningEngine (Moteur de raisonnement émergent)
Génère, évalue et explique des solutions émergentes issues de
la collaboration inter-agents et du raisonnement multi-perspectives.

API:
  generate_emergent_solution(context)    → dict
  evaluate_emergent_solution(solution)   → dict
  explain_emergent_solution(solution)    → dict
  detect_emergence(observations)         → dict
  get_emergent_solutions(limit)          → list[dict]
  health_check()                         → dict
  restart()                              → None
  get_stats()                            → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("emergent_reasoning")

# Types d'émergence
EMERGENCE_TYPES = frozenset({
    "pattern_synthesis", "cross_domain", "novel_combination",
    "constraint_relaxation", "analogy_transfer", "collective_insight",
})

# Seuils d'évaluation
MIN_VIABILITY = 0.3
MIN_NOVELTY = 0.2
MAX_RISK = 0.8


class EmergentReasoningEngine:
    """Moteur de raisonnement émergent EXO v16."""

    def __init__(self, collaboration_bus=None, governor=None,
                 audit_log=None, meta_memory=None,
                 knowledge_graph=None, inference_engine=None):
        self._collab = collaboration_bus
        self._governor = governor
        self._audit = audit_log
        self._memory = meta_memory
        self._kg = knowledge_graph
        self._inference = inference_engine
        self._solutions: list[dict] = []
        self._emergences: list[dict] = []
        self._stats = {
            "solutions_generated": 0,
            "solutions_evaluated": 0,
            "solutions_viable": 0,
            "solutions_rejected": 0,
            "emergences_detected": 0,
            "cross_domain_links": 0,
        }

    # ── generate_emergent_solution ──────────────────────────
    def generate_emergent_solution(self, context: dict) -> dict:
        """Générer une solution émergente à partir du contexte."""
        self._stats["solutions_generated"] += 1
        sol_id = f"emsol_{uuid.uuid4().hex[:10]}"

        problem = context.get("problem", "")
        domain = context.get("domain", "general")
        constraints = context.get("constraints", [])
        observations = context.get("observations", [])
        perspectives = context.get("perspectives", [])

        # Collect observations from collaboration bus
        if self._collab and not observations:
            observations = self._collab.get_shared_observations(
                domain=domain, limit=20)

        # Generate perspectives from KG
        kg_context = []
        if self._kg and problem:
            neighbors = self._kg.kg_neighbors(problem)
            kg_context = [
                {"source": "knowledge_graph",
                 "relation": n.get("relation", ""),
                 "node": n.get("node", "")}
                for n in (neighbors if isinstance(neighbors, list)
                          else neighbors.get("neighbors", []))[:10]
            ]

        # Inference-based reasoning
        inferred = []
        if self._inference:
            try:
                causal = self._inference.infer_causal(
                    {"observations": [o.get("content", str(o))
                                      for o in observations[:5]]})
                inferred.append({"type": "causal", "result": causal})
            except Exception:
                pass

        # Synthesize solution paths
        paths = self._synthesize_paths(problem, observations, kg_context,
                                        inferred, constraints)

        # Score novelty
        novelty = self._compute_novelty(paths, domain)

        solution = {
            "id": sol_id,
            "problem": problem,
            "domain": domain,
            "paths": paths,
            "novelty_score": novelty,
            "observations_used": len(observations),
            "kg_context_used": len(kg_context),
            "inferences_used": len(inferred),
            "constraints": constraints,
            "viability": None,  # Set after evaluation
            "status": "generated",
            "timestamp": time.time(),
        }

        self._solutions.append(solution)
        self._trim_solutions()

        log.info("Emergent solution %s generated (novelty=%.2f, %d paths)",
                 sol_id, novelty, len(paths))

        return solution

    # ── evaluate_emergent_solution ──────────────────────────
    def evaluate_emergent_solution(self, solution: dict) -> dict:
        """Évaluer la viabilité d'une solution émergente."""
        self._stats["solutions_evaluated"] += 1
        eval_id = f"eval_{uuid.uuid4().hex[:8]}"

        sol_id = solution.get("id", "unknown")
        paths = solution.get("paths", [])
        novelty = solution.get("novelty_score", 0.0)
        domain = solution.get("domain", "general")

        # Evaluate each path
        path_scores = []
        for p in paths:
            feasibility = p.get("feasibility", 0.5)
            impact = p.get("impact", 0.5)
            risk = p.get("risk", 0.3)
            score = (feasibility * 0.4 + impact * 0.3 +
                     (1 - risk) * 0.3)
            path_scores.append({
                "path": p.get("description", ""),
                "feasibility": feasibility,
                "impact": impact,
                "risk": risk,
                "score": round(score, 3),
            })

        # Overall viability
        viability = (sum(ps["score"] for ps in path_scores) /
                     len(path_scores)) if path_scores else 0.0

        # Governor check
        gov_approved = True
        if self._governor:
            em_data = {
                "pattern": solution.get("problem", ""),
                "novelty_score": novelty,
                "viability": viability,
                "risk": max((p.get("risk", 0) for p in paths), default=0),
                "agents_involved": [],
                "domain": domain,
            }
            gov_result = self._governor.supervise_emergence(em_data)
            gov_approved = gov_result.get("decision") == "approved"

        viable = viability >= MIN_VIABILITY and gov_approved
        if viable:
            self._stats["solutions_viable"] += 1
        else:
            self._stats["solutions_rejected"] += 1

        # Update solution in list
        for s in self._solutions:
            if s.get("id") == sol_id:
                s["viability"] = viability
                s["status"] = "viable" if viable else "rejected"
                break

        if self._audit and viable:
            self._audit.log_emergence({
                "pattern": sol_id,
                "novelty_score": novelty,
                "viability": viability,
                "domain": domain,
            })

        result = {
            "id": eval_id,
            "solution_id": sol_id,
            "viability": round(viability, 3),
            "novelty_score": novelty,
            "viable": viable,
            "governor_approved": gov_approved,
            "path_scores": path_scores,
            "best_path": max(path_scores, key=lambda x: x["score"])
            if path_scores else None,
            "timestamp": time.time(),
        }

        return result

    # ── explain_emergent_solution ───────────────────────────
    def explain_emergent_solution(self, solution: dict) -> dict:
        """Expliquer comment une solution émergente a été générée."""
        sol_id = solution.get("id", "unknown")
        problem = solution.get("problem", "")
        paths = solution.get("paths", [])
        novelty = solution.get("novelty_score", 0.0)
        viability = solution.get("viability")

        lines = [f"Solution émergente : {sol_id}"]
        lines.append(f"Problème : {problem}")
        lines.append(f"Nouveauté : {novelty:.0%}")
        if viability is not None:
            lines.append(f"Viabilité : {viability:.0%}")

        lines.append(f"\n{len(paths)} chemin(s) identifié(s) :")
        for i, p in enumerate(paths, 1):
            desc = p.get("description", "?")
            source = p.get("source", "unknown")
            lines.append(f"  {i}. {desc} (source: {source})")

        lines.append(f"\nDonnées utilisées :")
        lines.append(f"  Observations : {solution.get('observations_used', 0)}")
        lines.append(f"  Contexte KG : {solution.get('kg_context_used', 0)}")
        lines.append(f"  Inférences : {solution.get('inferences_used', 0)}")

        return {
            "solution_id": sol_id,
            "type": "emergence_explanation",
            "text": "\n".join(lines),
            "novelty": novelty,
            "viability": viability,
            "paths_count": len(paths),
            "timestamp": time.time(),
        }

    # ── detect_emergence ────────────────────────────────────
    def detect_emergence(self, observations: list[dict]) -> dict:
        """Détecter des patterns émergents dans les observations."""
        self._stats["emergences_detected"] += 1
        det_id = f"emdet_{uuid.uuid4().hex[:8]}"

        if not observations:
            return {"id": det_id, "emergences": [], "count": 0}

        # Group by domain
        by_domain: dict[str, list[dict]] = {}
        for obs in observations:
            d = obs.get("domain", "general")
            by_domain.setdefault(d, []).append(obs)

        emergences = []

        # Cross-domain connections
        domains = list(by_domain.keys())
        for i, d1 in enumerate(domains):
            for d2 in domains[i + 1:]:
                # Check for shared tags/concepts
                tags1 = set()
                for o in by_domain[d1]:
                    tags1.update(o.get("tags", []))
                tags2 = set()
                for o in by_domain[d2]:
                    tags2.update(o.get("tags", []))

                shared = tags1 & tags2
                if shared:
                    self._stats["cross_domain_links"] += 1
                    emergences.append({
                        "type": "cross_domain",
                        "domains": [d1, d2],
                        "shared_concepts": list(shared),
                        "novelty_score": min(1.0, len(shared) * 0.2),
                    })

        # Pattern frequency
        contents = [o.get("content", "") for o in observations if o.get("content")]
        if len(contents) >= 3:
            emergences.append({
                "type": "pattern_synthesis",
                "observation_count": len(contents),
                "domains": domains,
                "novelty_score": 0.4,
            })

        self._emergences.extend(emergences)

        return {
            "id": det_id,
            "emergences": emergences,
            "count": len(emergences),
            "domains_analyzed": len(domains),
            "observations_analyzed": len(observations),
        }

    # ── get_emergent_solutions ──────────────────────────────
    def get_emergent_solutions(self, limit: int = 20) -> list[dict]:
        return self._solutions[-limit:]

    # ── health_check ────────────────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "emergent_reasoning",
            "status": "ok",
            "solutions_count": len(self._solutions),
            "emergences_count": len(self._emergences),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._solutions.clear()
        self._emergences.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("EmergentReasoningEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _synthesize_paths(self, problem: str, observations: list,
                          kg_context: list, inferred: list,
                          constraints: list) -> list[dict]:
        """Synthétiser les chemins de solution."""
        paths = []

        # Path from observations
        if observations:
            obs_insights = [o.get("content", "") for o in observations
                           if o.get("confidence", 0) > 0.5]
            if obs_insights:
                paths.append({
                    "description": f"Solution basée sur {len(obs_insights)} "
                                   f"observations convergentes",
                    "source": "observations",
                    "feasibility": 0.6,
                    "impact": 0.5,
                    "risk": 0.2,
                    "insights": obs_insights[:5],
                })

        # Path from KG
        if kg_context:
            paths.append({
                "description": "Solution basée sur le graphe de connaissances",
                "source": "knowledge_graph",
                "feasibility": 0.7,
                "impact": 0.6,
                "risk": 0.15,
                "relations": [kc.get("relation", "") for kc in kg_context[:5]],
            })

        # Path from inference
        if inferred:
            paths.append({
                "description": "Solution basée sur inférence causale",
                "source": "inference",
                "feasibility": 0.5,
                "impact": 0.7,
                "risk": 0.3,
            })

        # Default path
        if not paths:
            paths.append({
                "description": f"Approche directe pour : {problem[:60]}",
                "source": "default",
                "feasibility": 0.4,
                "impact": 0.4,
                "risk": 0.2,
            })

        return paths

    def _compute_novelty(self, paths: list[dict], domain: str) -> float:
        """Calculer le score de nouveauté."""
        if not paths:
            return 0.0

        sources = {p.get("source", "default") for p in paths}
        # More diverse sources = more novel
        novelty = min(1.0, len(sources) * 0.25)

        # Cross-source bonus
        if "knowledge_graph" in sources and "inference" in sources:
            novelty = min(1.0, novelty + 0.2)

        return round(novelty, 3)

    def _trim_solutions(self) -> None:
        if len(self._solutions) > 1000:
            self._solutions = self._solutions[-1000:]
