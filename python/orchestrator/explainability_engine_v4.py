"""
EXO v14 — ExplainabilityEngineV4 (Explication multi-agents)
Explique les décisions distribuées : rôle de chaque agent,
arbitrages, conflits résolus, décisions finales, cohérence globale.

API:
  explain_agent_decision(agent_name)     → dict
  explain_global_decision(decision)      → dict
  explain_conflict_resolution(resolution)→ dict
  explain_orchestration(orch_result)     → dict
  health_check()                         → dict
  restart()                              → None
  get_stats()                            → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("explainability_v4")


class ExplainabilityEngineV4:
    """Moteur d'explicabilité multi-agents EXO v14."""

    def __init__(self, meta_memory=None, registry=None,
                 explainability_v3=None):
        self._memory = meta_memory
        self._registry = registry
        self._explainability_v3 = explainability_v3
        self._history: list[dict] = []
        self._stats = {
            "agent_explanations": 0,
            "global_explanations": 0,
            "conflict_explanations": 0,
            "orchestration_explanations": 0,
        }

    # ── explain_agent_decision ──────────────────────────────
    def explain_agent_decision(self, agent_name: str) -> dict:
        """Explain what a specific agent decided and why."""
        self._stats["agent_explanations"] += 1

        agent = None
        if self._registry:
            agent = self._registry.get_agent(agent_name)

        if not agent:
            result = {
                "agent": agent_name,
                "explanation": f"Agent '{agent_name}' non trouvé.",
                "found": False,
            }
            self._record(result)
            return result

        last_result = agent.report_result() if hasattr(
            agent, "report_result") else {}
        last_error = agent.report_error() if hasattr(
            agent, "report_error") else {}
        stats = agent.get_stats() if hasattr(agent, "get_stats") else {}

        lines = [
            f"Agent: {agent_name}",
            f"  Domaine: {getattr(agent, 'domain', '?')}",
            f"  Version: {getattr(agent, 'version', '?')}",
            f"  Capacités: {', '.join(getattr(agent, 'capabilities', []))}",
        ]

        if last_result.get("status") == "success":
            lines.append(f"  Dernier résultat: succès")
            inner = last_result.get("result", {})
            if isinstance(inner, dict):
                for k, v in inner.items():
                    lines.append(f"    {k}: {v}")
        elif last_result.get("status") == "no_result":
            lines.append("  Aucun résultat récent")

        if last_error.get("error"):
            lines.append(f"  Dernière erreur: {last_error['error']}")

        if stats:
            lines.append(f"  Tâches traitées: {stats.get('tasks_handled', 0)}")
            lines.append(f"  Succès: {stats.get('tasks_succeeded', 0)}")
            lines.append(f"  Échecs: {stats.get('tasks_failed', 0)}")

        result = {
            "agent": agent_name,
            "explanation": "\n".join(lines),
            "found": True,
            "stats": stats,
            "last_result": last_result,
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── explain_global_decision ─────────────────────────────
    def explain_global_decision(self, decision: dict) -> dict:
        """Explain a finalized global decision."""
        self._stats["global_explanations"] += 1

        status = decision.get("status", "unknown")
        agents = decision.get("agent_names", [])
        successful = decision.get("successful", 0)
        failed = decision.get("failed", 0)
        merged = decision.get("merged_result", {})

        lines = [
            f"Décision globale: {status}",
            f"  Agents impliqués: {', '.join(agents) if agents else 'aucun'}",
            f"  Succès: {successful}, Échecs: {failed}",
        ]

        if merged:
            lines.append("  Résultat fusionné:")
            for k, v in merged.items():
                lines.append(f"    {k}: {v}")

        if status == "failed":
            lines.append("  Raison: Tous les agents ont échoué.")
        elif status == "decided":
            lines.append("  La décision a été prise avec succès.")

        result = {
            "explanation": "\n".join(lines),
            "decision_status": status,
            "agents_involved": len(agents),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── explain_conflict_resolution ─────────────────────────
    def explain_conflict_resolution(self, resolution: dict) -> dict:
        """Explain how a conflict was resolved."""
        self._stats["conflict_explanations"] += 1

        conflicts_found = resolution.get("conflicts_found", 0)
        method = resolution.get("resolution_method", "unknown")
        conflicts = resolution.get("conflicts", [])
        selected = resolution.get("selected_outputs", [])
        dropped = resolution.get("dropped_outputs", [])

        lines = [
            f"Résolution de conflits:",
            f"  Méthode: {method}",
            f"  Conflits détectés: {conflicts_found}",
        ]

        for i, c in enumerate(conflicts[:5]):
            c_type = c.get("type", "?")
            detail = ""
            if c_type == "contradiction":
                detail = (f"{c.get('agent_a')} ({c.get('action_a')}) vs "
                          f"{c.get('agent_b')} ({c.get('action_b')}) "
                          f"sur {c.get('target', '?')}")
            elif c_type == "domain_overlap":
                detail = (f"Cible '{c.get('target')}' — agents: "
                          f"{', '.join(c.get('agents', []))}")
            elif c_type == "temporal_conflict":
                detail = (f"{c.get('agent_a')} vs {c.get('agent_b')} "
                          f"sur {c.get('target', '?')}")
            lines.append(f"  Conflit {i + 1}: {c_type} — {detail}")

        lines.append(f"  Résultats retenus: {len(selected)}")
        lines.append(f"  Résultats écartés: {len(dropped)}")

        result = {
            "explanation": "\n".join(lines),
            "conflicts_found": conflicts_found,
            "method": method,
            "selected_count": len(selected),
            "dropped_count": len(dropped),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── explain_orchestration ───────────────────────────────
    def explain_orchestration(self, orch_result: dict) -> dict:
        """Explain a full orchestration cycle."""
        self._stats["orchestration_explanations"] += 1

        intent = orch_result.get("intent", {})
        dispatched = orch_result.get("dispatched", [])
        collected = orch_result.get("collected", [])
        resolution = orch_result.get("resolution", {})
        decision = orch_result.get("decision", {})

        lines = [
            f"Orchestration:",
            f"  Intention: {intent.get('action', '?')} "
            f"(domaine: {intent.get('domain', '?')})",
            f"  Tâches distribuées: {len(dispatched)}",
            f"  Résultats collectés: {len(collected)}",
        ]

        if resolution:
            lines.append(f"  Conflits: {resolution.get('conflicts_found', 0)}")
            lines.append(
                f"  Méthode de résolution: "
                f"{resolution.get('resolution_method', 'aucune')}")

        if decision:
            lines.append(
                f"  Décision: {decision.get('status', '?')} "
                f"({decision.get('agents_involved', 0)} agents)")

        result = {
            "explanation": "\n".join(lines),
            "intent": intent,
            "dispatched_count": len(dispatched),
            "collected_count": len(collected),
            "decision_status": decision.get("status", ""),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 500:
            self._history = self._history[-300:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "explainability_v4",
            "status": "ok",
            "explanations_total": sum(self._stats.values()),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ExplainabilityEngineV4 restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
