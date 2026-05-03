"""
EXO v15 — ExplainabilityEngineV5 (Explicabilité complète)
Explication logique, causale, temporelle, multi-agents et prospective.

API:
  explain_decision(decision)     → dict
  explain_inference(inference)   → dict
  explain_future(future)         → dict
  explain_conflict(conflict)     → dict
  explain_full(session)          → dict
  get_explanations(limit)        → list[dict]
  health_check()                 → dict
  restart()                      → None
  get_stats()                    → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("explainability_v5")


class ExplainabilityEngineV5:
    """Explicabilité complète EXO v15."""

    def __init__(self, meta_memory=None, knowledge_graph=None,
                 inference_engine=None):
        self._memory = meta_memory
        self._kg = knowledge_graph
        self._inference = inference_engine
        self._explanations: list[dict] = []
        self._stats = {
            "decisions_explained": 0,
            "inferences_explained": 0,
            "futures_explained": 0,
            "conflicts_explained": 0,
            "full_explanations": 0,
        }

    # ── explain_decision ────────────────────────────────────
    def explain_decision(self, decision: dict) -> dict:
        """Expliquer une décision de manière logique et causale."""
        self._stats["decisions_explained"] += 1
        exp_id = f"expd_{uuid.uuid4().hex[:8]}"

        action = decision.get("action", "unknown")
        reasoning = decision.get("reasoning", "")
        confidence = decision.get("confidence", 0.5)

        lines = [f"Décision : {action}"]
        if reasoning:
            lines.append(f"Raisonnement : {reasoning}")
        lines.append(f"Confiance : {confidence:.0%}")

        # KG context
        if self._kg and action:
            neighbors = self._kg.kg_neighbors(action)
            if neighbors:
                lines.append("Contexte KG :")
                for n in neighbors[:5]:
                    lines.append(
                        f"  {n['direction']} {n['relation']} → {n['node']}")

        # Alternatives
        alternatives = decision.get("alternatives", [])
        if alternatives:
            lines.append("Alternatives considérées :")
            for alt in alternatives[:3]:
                lines.append(f"  - {alt}")

        explanation = {
            "id": exp_id,
            "type": "decision",
            "action": action,
            "text": "\n".join(lines),
            "confidence": confidence,
            "timestamp": time.time(),
        }
        self._explanations.append(explanation)
        return explanation

    # ── explain_inference ───────────────────────────────────
    def explain_inference(self, inference: dict) -> dict:
        """Expliquer un résultat d'inférence."""
        self._stats["inferences_explained"] += 1
        exp_id = f"expi_{uuid.uuid4().hex[:8]}"

        inf_type = inference.get("type", "unknown")
        conclusions = inference.get("conclusions",
                                    inference.get("links",
                                                  inference.get("patterns", [])))

        lines = [f"Inférence ({inf_type}) :"]

        if inf_type == "logical":
            for c in conclusions[:5]:
                lines.append(f"  Conclusion : {c}")
        elif inf_type == "causal":
            for link in conclusions[:5]:
                lines.append(
                    f"  {link.get('cause', '?')} → {link.get('effect', '?')} "
                    f"(p={link.get('probability', '?')})")
        elif inf_type == "temporal":
            for p in conclusions[:5]:
                lines.append(
                    f"  Pattern : {p.get('pattern', '?')} "
                    f"— {p.get('event', p.get('antecedent', '?'))}")
        else:
            for item in conclusions[:5]:
                lines.append(f"  {item}")

        explanation = {
            "id": exp_id,
            "type": "inference",
            "inference_type": inf_type,
            "text": "\n".join(lines),
            "conclusions_count": len(conclusions),
            "timestamp": time.time(),
        }
        self._explanations.append(explanation)
        return explanation

    # ── explain_future ──────────────────────────────────────
    def explain_future(self, future: dict) -> dict:
        """Expliquer un scénario futur."""
        self._stats["futures_explained"] += 1
        exp_id = f"expf_{uuid.uuid4().hex[:8]}"

        label = future.get("label", "unknown")
        risk = future.get("risk", 0)
        viable = future.get("viable", True)

        lines = [f"Scénario : {label}"]
        lines.append(f"Risque : {risk:.1%}")
        lines.append(f"Viable : {'Oui' if viable else 'Non'}")

        if "steps" in future:
            lines.append("Étapes simulées :")
            for s in future["steps"][:5]:
                lines.append(
                    f"  {s.get('step', '?')}. {s.get('action', '?')} "
                    f"(risque cumulé: {s.get('cumulative_risk', '?')})")

        explanation = {
            "id": exp_id,
            "type": "future",
            "label": label,
            "text": "\n".join(lines),
            "risk": risk,
            "viable": viable,
            "timestamp": time.time(),
        }
        self._explanations.append(explanation)
        return explanation

    # ── explain_conflict ────────────────────────────────────
    def explain_conflict(self, conflict: dict) -> dict:
        """Expliquer un conflit et sa résolution."""
        self._stats["conflicts_explained"] += 1
        exp_id = f"expc_{uuid.uuid4().hex[:8]}"

        ctype = conflict.get("type", "unknown")
        resolution = conflict.get("resolution", "")

        lines = [f"Conflit : {ctype}"]
        if "detail" in conflict:
            lines.append(f"Détail : {conflict['detail']}")
        if resolution:
            lines.append(f"Résolution : {resolution}")
        if "severity" in conflict:
            lines.append(f"Sévérité : {conflict['severity']}")

        explanation = {
            "id": exp_id,
            "type": "conflict",
            "conflict_type": ctype,
            "text": "\n".join(lines),
            "resolution": resolution,
            "timestamp": time.time(),
        }
        self._explanations.append(explanation)
        return explanation

    # ── explain_full ────────────────────────────────────────
    def explain_full(self, session: dict) -> dict:
        """Explication complète d'une session de raisonnement."""
        self._stats["full_explanations"] += 1
        exp_id = f"expfull_{uuid.uuid4().hex[:8]}"

        sections = []

        if "decisions" in session:
            for d in session["decisions"][:5]:
                sections.append(self.explain_decision(d))
        if "inferences" in session:
            for inf in session["inferences"][:5]:
                sections.append(self.explain_inference(inf))
        if "futures" in session:
            for f in session["futures"][:3]:
                sections.append(self.explain_future(f))
        if "conflicts" in session:
            for c in session["conflicts"][:3]:
                sections.append(self.explain_conflict(c))

        full_text = "\n\n---\n\n".join(
            s.get("text", "") for s in sections)

        explanation = {
            "id": exp_id,
            "type": "full",
            "sections": len(sections),
            "text": full_text or "Aucun élément à expliquer.",
            "timestamp": time.time(),
        }
        self._explanations.append(explanation)
        return explanation

    # ── get_explanations ────────────────────────────────────
    def get_explanations(self, limit: int = 20) -> list[dict]:
        return self._explanations[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "explainability_v5",
            "status": "ok",
            "explanations_count": len(self._explanations),
        }

    def restart(self) -> None:
        self._explanations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ExplainabilityEngineV5 restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
