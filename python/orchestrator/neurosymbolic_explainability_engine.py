"""
EXO v17 — NeuroSymbolicExplainabilityEngine (Explication neuro-symbolique)
Explique les décisions hybrides en décomposant les parties
symbolique et neuronale de chaque raisonnement.

API:
  explain_hybrid_decision(decision)    → dict
  explain_symbolic_part(decision)      → dict
  explain_neural_part(decision)        → dict
  explain_full_v17(session)            → dict
  get_explanation_history(limit)       → list[dict]
  health_check()                       → dict
  restart()                            → None
  get_stats()                          → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("neurosymbolic_explainability")


class NeuroSymbolicExplainabilityEngine:
    """Moteur d'explicabilité neuro-symbolique EXO v17."""

    def __init__(self, meta_memory=None, explainability_v6=None,
                 reasoning_bridge=None, hybrid_inference=None,
                 symbolic_validator=None, coherence_engine=None):
        self._memory = meta_memory
        self._v6 = explainability_v6
        self._bridge = reasoning_bridge
        self._hybrid = hybrid_inference
        self._validator = symbolic_validator
        self._coherence = coherence_engine
        self._history: list[dict] = []
        self._stats = {
            "hybrid_explanations": 0,
            "symbolic_explanations": 0,
            "neural_explanations": 0,
            "full_explanations": 0,
        }

    # ── explain_hybrid_decision ─────────────────────────────
    def explain_hybrid_decision(self, decision: dict) -> dict:
        """Expliquer une décision neuro-symbolique complète."""
        self._stats["hybrid_explanations"] += 1

        parts = []
        parts.append("=== Explication décision hybride ===")

        # Partie symbolique
        symbolic = self.explain_symbolic_part(decision)
        parts.append(f"\n[SYMBOLIQUE]\n{symbolic.get('text', 'N/A')}")

        # Partie neuronale
        neural = self.explain_neural_part(decision)
        parts.append(f"\n[NEURONAL]\n{neural.get('text', 'N/A')}")

        # Fusion
        merged_conf = decision.get("merged_confidence",
                                    decision.get("confidence", 0))
        preferred = decision.get("preferred_source", "unknown")
        conflicts = decision.get("conflict_count",
                                  len(decision.get("conflicts", [])))

        parts.append(f"\n[FUSION]")
        parts.append(f"  Confiance fusionnée: {merged_conf:.2f}")
        parts.append(f"  Source préférée: {preferred}")
        if conflicts:
            parts.append(f"  Conflits détectés: {conflicts}")
            parts.append(f"  Résolution: pondération par confiance")

        # Cohérence
        if self._coherence:
            try:
                coh = self._coherence.check_neuro_symbolic_consistency()
                parts.append(f"\n[COHÉRENCE]")
                parts.append(f"  Score global: {coh.get('overall_score', 0):.2f}")
                parts.append(f"  Cohérent: {coh.get('coherent', False)}")
            except Exception:
                pass

        # Validation
        if self._validator:
            try:
                val = self._validator.explain_validation()
                if val.get("found"):
                    parts.append(f"\n[VALIDATION]\n{val.get('text', '')}")
            except Exception:
                pass

        result = {
            "id": f"hexp_{uuid.uuid4().hex[:8]}",
            "text": "\n".join(parts),
            "symbolic": symbolic,
            "neural": neural,
            "merged_confidence": merged_conf,
            "preferred_source": preferred,
            "conflicts": conflicts,
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        log.info("Hybrid explanation generated: conf=%.2f, pref=%s",
                 merged_conf, preferred)
        return result

    # ── explain_symbolic_part ───────────────────────────────
    def explain_symbolic_part(self, decision: dict) -> dict:
        """Expliquer la partie symbolique d'une décision."""
        self._stats["symbolic_explanations"] += 1

        parts = []
        sym = decision.get("symbolic_result", decision.get("symbolic", {}))
        sym_conf = sym.get("confidence", decision.get(
            "symbolic_confidence", 0))

        parts.append(f"Confiance symbolique: {sym_conf:.2f}")

        conclusions = sym.get("conclusions", [])
        if conclusions:
            parts.append(f"Conclusions ({len(conclusions)}):")
            for i, c in enumerate(conclusions[:5]):
                stmt = c.get("statement", str(c)) if isinstance(
                    c, dict) else str(c)
                parts.append(f"  {i+1}. {stmt}")

        kg_facts = sym.get("kg_facts", [])
        if kg_facts:
            parts.append(f"Faits KG utilisés: {len(kg_facts)}")

        # Bridge context
        if self._bridge:
            try:
                translations = self._bridge.get_translations(3)
                if translations:
                    parts.append(f"Traductions bridge récentes: {len(translations)}")
            except Exception:
                pass

        result = {
            "text": "\n".join(parts),
            "confidence": sym_conf,
            "conclusions_count": len(conclusions),
            "kg_facts_count": len(kg_facts),
        }

        self._history.append(result)
        self._trim()
        return result

    # ── explain_neural_part ─────────────────────────────────
    def explain_neural_part(self, decision: dict) -> dict:
        """Expliquer la partie neuronale d'une décision."""
        self._stats["neural_explanations"] += 1

        parts = []
        neu = decision.get("neural_result", decision.get("neural", {}))
        neu_conf = neu.get("confidence", decision.get(
            "neural_confidence", 0))

        parts.append(f"Confiance neuronale: {neu_conf:.2f}")

        interpretation = neu.get("interpretation", {})
        if interpretation:
            stmt = interpretation.get("statement", str(interpretation))
            parts.append(f"Interprétation: {stmt}")
            if interpretation.get("grounded"):
                parts.append("  → Ancré dans les connaissances")

        neural_ctx = neu.get("neural_context", {})
        if neural_ctx.get("prompt"):
            parts.append("Prompt structuré disponible")

        # Hybrid inference stats
        if self._hybrid:
            try:
                s = self._hybrid.get_stats()
                parts.append(f"Inférences hybrides total: "
                             f"{s.get('hybrid_inferences', 0)}")
            except Exception:
                pass

        result = {
            "text": "\n".join(parts),
            "confidence": neu_conf,
            "grounded": interpretation.get("grounded", False),
        }

        self._history.append(result)
        self._trim()
        return result

    # ── explain_full_v17 ────────────────────────────────────
    def explain_full_v17(self, session: dict) -> dict:
        """Explication complète d'une session neuro-symbolique v17."""
        self._stats["full_explanations"] += 1

        parts = []
        parts.append("══════ EXO v17 — Rapport neuro-symbolique ══════")

        # Module bridge
        if self._bridge:
            try:
                bs = self._bridge.get_stats()
                parts.append(f"\n[ReasoningBridge]")
                parts.append(f"  LLM→Symbolique: {bs.get('llm_to_symbolic', 0)}")
                parts.append(f"  Symbolique→LLM: {bs.get('symbolic_to_llm', 0)}")
                parts.append(f"  Fusions: {bs.get('merges', 0)}")
                parts.append(f"  Conflits: {bs.get('merge_conflicts', 0)}")
            except Exception:
                pass

        # Module hybrid inference
        if self._hybrid:
            try:
                hs = self._hybrid.get_stats()
                parts.append(f"\n[HybridInference]")
                parts.append(f"  Inférences hybrides: "
                             f"{hs.get('hybrid_inferences', 0)}")
                parts.append(f"  Symbolique préféré: "
                             f"{hs.get('symbolic_preferred', 0)}")
                parts.append(f"  Neuronal préféré: "
                             f"{hs.get('neural_preferred', 0)}")
            except Exception:
                pass

        # Module validator
        if self._validator:
            try:
                vs = self._validator.get_stats()
                parts.append(f"\n[SymbolicValidator]")
                parts.append(f"  Validations: {vs.get('validations_run', 0)}")
                parts.append(f"  Passées: {vs.get('validations_passed', 0)}")
                parts.append(f"  Échouées: {vs.get('validations_failed', 0)}")
                parts.append(f"  Corrections: {vs.get('corrections_applied', 0)}")
            except Exception:
                pass

        # Module coherence
        if self._coherence:
            try:
                cs = self._coherence.get_stats()
                parts.append(f"\n[Cohérence]")
                parts.append(f"  Vérifications: {cs.get('checks_run', 0)}")
                parts.append(f"  Cohérent: {cs.get('coherent', 0)}")
                parts.append(f"  Incohérent: {cs.get('incoherent', 0)}")
            except Exception:
                pass

        # Explicabilité héritée v16
        if self._v6:
            try:
                v6s = self._v6.get_stats()
                parts.append(f"\n[ExplainabilityV6 hérité]")
                for k, v in v6s.items():
                    parts.append(f"  {k}: {v}")
            except Exception:
                pass

        parts.append(f"\n══════ Fin rapport v17 ══════")

        result = {
            "id": f"fexp_{uuid.uuid4().hex[:8]}",
            "text": "\n".join(parts),
            "session": session,
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        log.info("Full v17 explanation generated")
        return result

    # ── get_explanation_history ──────────────────────────────
    def get_explanation_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "neurosymbolic_explainability",
            "status": "ok",
            "history_entries": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("NeuroSymbolicExplainabilityEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
