"""
EXO v21 — AbductiveReasoner
Raisonnement abductif : hypothèses plausibles, explications minimales,
complétion logique, scénarios explicatifs.

API:
  abduct(query: dict)                → dict
  explain_best_hypothesis()          → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("abductive_reasoner")


class AbductiveReasoner:
    """Raisonneur abductif EXO v21."""

    def __init__(self, governance=None, rule_engine=None,
                 causal_engine=None):
        self._governance = governance
        self._rule_engine = rule_engine
        self._causal = causal_engine

        self._hypotheses: list[dict] = []
        self._stats = {
            "abductions": 0,
            "best_explanations": 0,
        }

    # ── abduct ──────────────────────────────────────────────
    def abduct(self, query: dict) -> dict:
        """Trouver les explications les plus plausibles d'une observation."""
        self._stats["abductions"] += 1

        observation = query.get("observation", "")
        known_facts = query.get("known_facts", [])
        candidate_causes = query.get("candidate_causes", [])
        context = query.get("context", "general")

        hypotheses = []

        if not candidate_causes:
            # Generate hypotheses from observation
            hyp = {
                "id": f"hyp_{uuid.uuid4().hex[:8]}",
                "cause": f"inferred_cause_of_{observation}",
                "observation": observation,
                "plausibility": 0.5,
                "type": "default",
                "minimal": True,
            }
            hypotheses.append(hyp)
        else:
            for i, cause in enumerate(candidate_causes):
                cause_name = cause if isinstance(cause, str) else cause.get("name", "")
                # Score based on known facts overlap
                support = 0
                if isinstance(cause, dict):
                    evidence = cause.get("evidence", [])
                    support = sum(1 for e in evidence if e in known_facts)

                plausibility = min(1.0, (support + 1) / (len(known_facts) + 1))

                hyp = {
                    "id": f"hyp_{uuid.uuid4().hex[:8]}",
                    "cause": cause_name,
                    "observation": observation,
                    "plausibility": round(plausibility, 3),
                    "support": support,
                    "type": "candidate",
                    "minimal": i == 0,
                }
                hypotheses.append(hyp)

        # Sort by plausibility
        hypotheses.sort(key=lambda h: h["plausibility"], reverse=True)

        # Mark best
        if hypotheses:
            hypotheses[0]["best"] = True

        entry = {
            "id": f"abd_{uuid.uuid4().hex[:8]}",
            "abducted": True,
            "observation": observation,
            "context": context,
            "hypotheses": hypotheses,
            "hypotheses_count": len(hypotheses),
            "best_hypothesis": hypotheses[0] if hypotheses else None,
            "timestamp": time.time(),
        }
        self._hypotheses.append(entry)
        self._trim()

        return entry

    # ── explain_best_hypothesis ─────────────────────────────
    def explain_best_hypothesis(self) -> dict:
        """Expliquer la meilleure hypothèse la plus récente."""
        self._stats["best_explanations"] += 1

        if not self._hypotheses:
            return {
                "explained": False,
                "error": "no_hypotheses",
                "timestamp": time.time(),
            }

        last = self._hypotheses[-1]
        best = last.get("best_hypothesis")

        if not best:
            return {
                "explained": False,
                "error": "no_best_hypothesis",
                "timestamp": time.time(),
            }

        reasons = [
            f"Observation : '{last['observation']}'.",
            f"Meilleure hypothèse : '{best['cause']}'.",
            f"Plausibilité : {best['plausibility']}.",
            f"Type : {best['type']}.",
        ]
        if best.get("minimal"):
            reasons.append("Cette hypothèse est minimale (explication la plus simple).")

        return {
            "id": f"exp_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "observation": last["observation"],
            "best_cause": best["cause"],
            "plausibility": best["plausibility"],
            "reasons": reasons,
            "timestamp": time.time(),
        }

    def list_hypotheses(self, limit: int = 50) -> list[dict]:
        return self._hypotheses[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "abductive_reasoner",
            "status": "ok",
            "total_abductions": len(self._hypotheses),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._hypotheses.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("AbductiveReasoner restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._hypotheses) > 5000:
            self._hypotheses = self._hypotheses[-2500:]
