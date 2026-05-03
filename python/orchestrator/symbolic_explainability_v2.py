"""
EXO v21 — SymbolicExplainabilityEngineV2
Explication des inférences symboliques avancées :
déduction, induction, abduction, chaîne causale.

API:
  explain_deduction()       → dict
  explain_induction()       → dict
  explain_abduction()       → dict
  explain_causal_chain()    → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("symbolic_explainability_v2")


class SymbolicExplainabilityEngineV2:
    """Moteur d'explicabilité symbolique avancée EXO v21."""

    def __init__(self, deductive=None, inductive=None, abductive=None,
                 causal_engine=None, governance=None):
        self._deductive = deductive
        self._inductive = inductive
        self._abductive = abductive
        self._causal_engine = causal_engine
        self._governance = governance

        self._explanations: list[dict] = []
        self._stats = {
            "deduction_explanations": 0,
            "induction_explanations": 0,
            "abduction_explanations": 0,
            "causal_explanations": 0,
        }

    # ── explain_deduction ───────────────────────────────────
    def explain_deduction(self) -> dict:
        """Expliquer les inférences déductives."""
        self._stats["deduction_explanations"] += 1

        steps = []
        d_stats = {}
        if self._deductive:
            try:
                d_stats = self._deductive.get_stats()
            except Exception:
                pass

        ded_count = d_stats.get("deductions", 0)
        ver_count = d_stats.get("verifications", 0)

        steps.append(f"Déductions effectuées : {ded_count}.")
        steps.append(f"Vérifications effectuées : {ver_count}.")
        if ded_count > 0:
            steps.append("Méthodes : modus ponens, modus tollens, syllogisme.")
        steps.append("Les déductions suivent des règles logiques strictes.")

        result = {
            "id": f"explD_{uuid.uuid4().hex[:8]}",
            "type": "deduction",
            "explained": True,
            "steps": steps,
            "source_stats": d_stats,
            "timestamp": time.time(),
        }
        self._explanations.append(result)
        self._trim()
        return result

    # ── explain_induction ───────────────────────────────────
    def explain_induction(self) -> dict:
        """Expliquer les inférences inductives."""
        self._stats["induction_explanations"] += 1

        steps = []
        i_stats = {}
        if self._inductive:
            try:
                i_stats = self._inductive.get_stats()
            except Exception:
                pass

        ind_count = i_stats.get("inductions", 0)
        gen_count = i_stats.get("generalizations", 0)

        steps.append(f"Inductions effectuées : {ind_count}.")
        steps.append(f"Généralisations effectuées : {gen_count}.")
        if ind_count > 0:
            steps.append("Motifs extraits par fréquence et support minimum.")
        steps.append("Confiance calculée sur la base des occurrences observées.")

        result = {
            "id": f"explI_{uuid.uuid4().hex[:8]}",
            "type": "induction",
            "explained": True,
            "steps": steps,
            "source_stats": i_stats,
            "timestamp": time.time(),
        }
        self._explanations.append(result)
        self._trim()
        return result

    # ── explain_abduction ───────────────────────────────────
    def explain_abduction(self) -> dict:
        """Expliquer les inférences abductives."""
        self._stats["abduction_explanations"] += 1

        steps = []
        a_stats = {}
        if self._abductive:
            try:
                a_stats = self._abductive.get_stats()
            except Exception:
                pass

        abd_count = a_stats.get("abductions", 0)
        hyp_count = a_stats.get("best_hypotheses", 0)

        steps.append(f"Abductions effectuées : {abd_count}.")
        steps.append(f"Meilleures hypothèses sélectionnées : {hyp_count}.")
        if abd_count > 0:
            steps.append("Candidats évalués par chevauchement avec les faits connus.")
        steps.append("L'hypothèse la plus plausible est sélectionnée par score.")

        result = {
            "id": f"explA_{uuid.uuid4().hex[:8]}",
            "type": "abduction",
            "explained": True,
            "steps": steps,
            "source_stats": a_stats,
            "timestamp": time.time(),
        }
        self._explanations.append(result)
        self._trim()
        return result

    # ── explain_causal_chain ────────────────────────────────
    def explain_causal_chain(self) -> dict:
        """Expliquer les chaînes causales."""
        self._stats["causal_explanations"] += 1

        steps = []
        c_stats = {}
        if self._causal_engine:
            try:
                c_stats = self._causal_engine.get_stats()
            except Exception:
                pass

        chains = c_stats.get("chains_inferred", 0)
        impacts = c_stats.get("impacts_analyzed", 0)

        steps.append(f"Chaînes causales inférées : {chains}.")
        steps.append(f"Analyses d'impact effectuées : {impacts}.")
        if chains > 0:
            steps.append("Chaînes construites par parcours BFS du graphe causal.")
        steps.append("Propagation des effets avec atténuation par poids.")

        result = {
            "id": f"explC_{uuid.uuid4().hex[:8]}",
            "type": "causal_chain",
            "explained": True,
            "steps": steps,
            "source_stats": c_stats,
            "timestamp": time.time(),
        }
        self._explanations.append(result)
        self._trim()
        return result

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "symbolic_explainability_v2",
            "status": "ok",
            "total_explanations": len(self._explanations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._explanations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("SymbolicExplainabilityEngineV2 restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._explanations) > 5000:
            self._explanations = self._explanations[-2500:]
