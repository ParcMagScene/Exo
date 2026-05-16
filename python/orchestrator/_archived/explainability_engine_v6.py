"""
EXO v16 — ExplainabilityEngineV6 (Explicabilité v16)
Explique initiatives autonomes, émergences cognitives et
décisions du gouverneur. Étend ExplainabilityEngineV5.

API:
  explain_initiative(initiative)     → dict
  explain_emergence(emergence)       → dict
  explain_governor_decision(decision) → dict
  explain_regulation(regulation)     → dict
  explain_collaboration(collab)      → dict
  explain_full_v16(session)          → dict
  get_explanations(limit)            → list[dict]
  health_check()                     → dict
  restart()                          → None
  get_stats()                        → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("explainability_v6")


class ExplainabilityEngineV6:
    """Explicabilité complète EXO v16 — Autonomie et émergence."""

    def __init__(self, meta_memory=None, explainability_v5=None,
                 audit_log=None):
        self._memory = meta_memory
        self._v5 = explainability_v5
        self._audit = audit_log
        self._explanations: list[dict] = []
        self._stats = {
            "initiatives_explained": 0,
            "emergences_explained": 0,
            "governor_decisions_explained": 0,
            "regulations_explained": 0,
            "collaborations_explained": 0,
            "full_explanations": 0,
        }

    # ── explain_initiative ──────────────────────────────────
    def explain_initiative(self, initiative: dict) -> dict:
        """Expliquer une initiative autonome et son parcours."""
        self._stats["initiatives_explained"] += 1
        exp_id = f"expinit_{uuid.uuid4().hex[:8]}"

        agent = initiative.get("agent", "unknown")
        action = initiative.get("action", "unknown")
        status = initiative.get("status", "unknown")
        domain = initiative.get("domain", "general")
        confidence = initiative.get("confidence", 0.0)
        reasoning = initiative.get("reasoning", "")
        autonomy = initiative.get("autonomy_level", 2)

        lines = [f"Initiative : {action}"]
        lines.append(f"Agent : {agent} (autonomie: {autonomy})")
        lines.append(f"Domaine : {domain}")
        lines.append(f"Statut : {status}")
        lines.append(f"Confiance : {confidence:.0%}")

        if reasoning:
            lines.append(f"Raisonnement : {reasoning}")

        # Explain status transitions
        if status == "rejected":
            reason = initiative.get("rejection_reason", "non spécifié")
            lines.append(f"Raison du rejet : {reason}")
            violations = initiative.get("violations", [])
            if violations:
                lines.append("Violations :")
                for v in violations[:5]:
                    lines.append(f"  - [{v.get('rule', '?')}] "
                                 f"{v.get('detail', '')}")

        elif status == "approved":
            lines.append("L'initiative a été approuvée par le gouverneur.")
            val_level = initiative.get("validation_level", "auto")
            lines.append(f"Niveau de validation : {val_level}")

        elif status == "rolled_back":
            lines.append("L'initiative a été annulée (rollback).")

        explanation = {
            "id": exp_id,
            "type": "initiative",
            "text": "\n".join(lines),
            "initiative_id": initiative.get("id", "?"),
            "agent": agent,
            "status": status,
            "timestamp": time.time(),
        }
        self._explanations.append(explanation)
        return explanation

    # ── explain_emergence ───────────────────────────────────
    def explain_emergence(self, emergence: dict) -> dict:
        """Expliquer une émergence cognitive."""
        self._stats["emergences_explained"] += 1
        exp_id = f"expem_{uuid.uuid4().hex[:8]}"

        sol_id = emergence.get("id", emergence.get("solution_id", "?"))
        problem = emergence.get("problem", "")
        novelty = emergence.get("novelty_score", 0.0)
        viability = emergence.get("viability", 0.0)
        paths = emergence.get("paths", [])
        domain = emergence.get("domain", "general")

        lines = [f"Émergence cognitive : {sol_id}"]
        if problem:
            lines.append(f"Problème adressé : {problem}")
        lines.append(f"Domaine : {domain}")
        lines.append(f"Score de nouveauté : {novelty:.0%}")
        if viability:
            lines.append(f"Viabilité : {viability:.0%}")

        if paths:
            lines.append(f"\n{len(paths)} chemin(s) de solution :")
            for i, p in enumerate(paths, 1):
                desc = p.get("description", "?")
                source = p.get("source", "?")
                lines.append(f"  {i}. {desc}")
                lines.append(f"     Source : {source}, "
                             f"Faisabilité : {p.get('feasibility', '?')}, "
                             f"Impact : {p.get('impact', '?')}")

        lines.append(f"\nDonnées contributives :")
        lines.append(f"  Observations : {emergence.get('observations_used', 0)}")
        lines.append(f"  Graphe de connaissances : "
                     f"{emergence.get('kg_context_used', 0)}")
        lines.append(f"  Inférences : {emergence.get('inferences_used', 0)}")

        explanation = {
            "id": exp_id,
            "type": "emergence",
            "text": "\n".join(lines),
            "solution_id": sol_id,
            "novelty": novelty,
            "viability": viability,
            "timestamp": time.time(),
        }
        self._explanations.append(explanation)
        return explanation

    # ── explain_governor_decision ───────────────────────────
    def explain_governor_decision(self, decision: dict) -> dict:
        """Expliquer une décision du gouverneur cognitif."""
        self._stats["governor_decisions_explained"] += 1
        exp_id = f"expgov_{uuid.uuid4().hex[:8]}"

        dec_type = decision.get("type", "unknown")
        verdict = decision.get("decision", "unknown")
        violations = decision.get("violations", [])

        lines = [f"Décision du gouverneur : {verdict}"]
        lines.append(f"Type : {dec_type}")

        if "initiative" in decision:
            init = decision["initiative"]
            lines.append(f"Agent : {init.get('agent', '?')}")
            lines.append(f"Action : {init.get('action', '?')}")
            lines.append(f"Domaine : {init.get('domain', '?')}")

        if "pattern" in decision:
            lines.append(f"Pattern émergent : {decision['pattern']}")

        if violations:
            lines.append(f"\n{len(violations)} violation(s) détectée(s) :")
            for v in violations:
                lines.append(f"  [{v.get('severity', '?')}] "
                             f"{v.get('rule', '?')} — {v.get('detail', '')}")

        if verdict == "approved":
            lines.append("\nDécision : APPROUVÉ — pas de violation critique.")
        elif verdict == "blocked":
            lines.append("\nDécision : BLOQUÉ — violations de sécurité.")
        elif verdict == "needs_approval":
            lines.append("\nDécision : VALIDATION REQUISE — confiance "
                         "insuffisante.")

        explanation = {
            "id": exp_id,
            "type": "governor_decision",
            "text": "\n".join(lines),
            "verdict": verdict,
            "violations_count": len(violations),
            "timestamp": time.time(),
        }
        self._explanations.append(explanation)
        return explanation

    # ── explain_regulation ──────────────────────────────────
    def explain_regulation(self, regulation: dict) -> dict:
        """Expliquer un ajustement de régulation."""
        self._stats["regulations_explained"] += 1
        exp_id = f"expreg_{uuid.uuid4().hex[:8]}"

        agent = regulation.get("agent", "system")
        direction = regulation.get("direction", "none")
        reg_type = regulation.get("type", "unknown")
        metrics = regulation.get("metrics", {})

        lines = [f"Ajustement de régulation : {reg_type}"]
        lines.append(f"Agent : {agent}")
        lines.append(f"Direction : {direction}")

        if "previous_level" in regulation:
            lines.append(
                f"Autonomie : {regulation['previous_level']} → "
                f"{regulation['new_level']}")
        if "previous_budget" in regulation:
            pb = regulation["previous_budget"]
            nb = regulation["new_budget"]
            lines.append(
                f"Budget initiatives : {pb.get('max_initiatives_per_hour')} → "
                f"{nb.get('max_initiatives_per_hour')}")

        if metrics:
            lines.append("\nMétriques :")
            for k, v in metrics.items():
                lines.append(f"  {k}: {v}")

        explanation = {
            "id": exp_id,
            "type": "regulation",
            "text": "\n".join(lines),
            "agent": agent,
            "direction": direction,
            "timestamp": time.time(),
        }
        self._explanations.append(explanation)
        return explanation

    # ── explain_collaboration ───────────────────────────────
    def explain_collaboration(self, collab: dict) -> dict:
        """Expliquer une collaboration inter-agents."""
        self._stats["collaborations_explained"] += 1
        exp_id = f"expcollab_{uuid.uuid4().hex[:8]}"

        collab_id = collab.get("id", "?")
        initiator = collab.get("initiator", "?")
        participants = collab.get("participants", [])
        status = collab.get("status", "?")
        collab_type = collab.get("type", "?")
        contributions = collab.get("contributions_count",
                                   len(collab.get("contributions", [])))

        lines = [f"Collaboration : {collab_id}"]
        lines.append(f"Type : {collab_type}")
        lines.append(f"Initiateur : {initiator}")
        lines.append(f"Participants : {', '.join(participants)}")
        lines.append(f"Statut : {status}")
        lines.append(f"Contributions : {contributions}")

        if "duration_sec" in collab:
            lines.append(f"Durée : {collab['duration_sec']:.1f}s")

        if collab.get("result"):
            summary = collab["result"].get("summary", "")
            if summary:
                lines.append(f"Résultat : {summary}")

        explanation = {
            "id": exp_id,
            "type": "collaboration",
            "text": "\n".join(lines),
            "collaboration_id": collab_id,
            "status": status,
            "timestamp": time.time(),
        }
        self._explanations.append(explanation)
        return explanation

    # ── explain_full_v16 ────────────────────────────────────
    def explain_full_v16(self, session: dict) -> dict:
        """Explication complète v16 d'une session."""
        self._stats["full_explanations"] += 1
        exp_id = f"expfull_{uuid.uuid4().hex[:8]}"

        sections = []

        # v15 base explanation
        if self._v5:
            v5_exp = self._v5.explain_full(session)
            sections.append({
                "section": "base_v15",
                "text": v5_exp.get("text", ""),
            })

        # Initiatives
        initiatives = session.get("initiatives", [])
        if initiatives:
            lines = [f"\n=== INITIATIVES ({len(initiatives)}) ==="]
            for init in initiatives[:10]:
                lines.append(
                    f"  [{init.get('status', '?')}] "
                    f"{init.get('agent', '?')} → {init.get('action', '?')}")
            sections.append({"section": "initiatives",
                             "text": "\n".join(lines)})

        # Emergences
        emergences = session.get("emergences", [])
        if emergences:
            lines = [f"\n=== ÉMERGENCES ({len(emergences)}) ==="]
            for em in emergences[:10]:
                lines.append(
                    f"  [{em.get('status', '?')}] "
                    f"novelty={em.get('novelty_score', 0):.2f} "
                    f"viability={em.get('viability', 0):.2f}")
            sections.append({"section": "emergences",
                             "text": "\n".join(lines)})

        # Governance
        governance = session.get("governance", [])
        if governance:
            lines = [f"\n=== GOUVERNANCE ({len(governance)}) ==="]
            for g in governance[:10]:
                lines.append(
                    f"  [{g.get('decision', '?')}] "
                    f"{g.get('type', '?')}")
            sections.append({"section": "governance",
                             "text": "\n".join(lines)})

        # Audit trail
        if self._audit:
            trail = self._audit.get_audit_trail(limit=5)
            if trail:
                lines = [f"\n=== AUDIT TRAIL (dernières {len(trail)}) ==="]
                for e in trail:
                    lines.append(
                        f"  [{e.get('entry_type', '?')}] "
                        f"{e.get('agent', e.get('governor', '?'))}")
                sections.append({"section": "audit",
                                 "text": "\n".join(lines)})

        full_text = "\n".join(s["text"] for s in sections)

        explanation = {
            "id": exp_id,
            "type": "full_v16",
            "text": full_text,
            "sections": [s["section"] for s in sections],
            "initiatives_count": len(initiatives),
            "emergences_count": len(emergences),
            "governance_count": len(governance),
            "timestamp": time.time(),
        }
        self._explanations.append(explanation)
        return explanation

    # ── get_explanations ────────────────────────────────────
    def get_explanations(self, limit: int = 20) -> list[dict]:
        return self._explanations[-limit:]

    # ── health_check ────────────────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "explainability_v6",
            "status": "ok",
            "explanations_count": len(self._explanations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._explanations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ExplainabilityEngineV6 restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
