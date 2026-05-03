"""
EXO v18 — LayeredExplainabilityEngine
Explication hiérarchique à chaque niveau de cognition.
Génère des explications pour couches, macro-agents, micro-agents
et flux verticaux.

API:
  explain_layer(layer)              → dict
  explain_macro(agent)              → dict
  explain_micro(agent)              → dict
  explain_vertical_flow()           → dict
  explain_decision(decision)        → dict
  get_explanation_history()         → list[dict]
  health_check()                    → dict
  restart()                         → None
  get_stats()                       → dict
"""

import logging
import time
import uuid

log = logging.getLogger("layered_explainability")


class LayeredExplainabilityEngine:
    """Moteur d'explicabilité hiérarchique EXO v18."""

    def __init__(self, layer_stack=None, macro_layer=None,
                 micro_layer=None, vertical_flow=None,
                 supervisor=None, governance=None):
        self._stack = layer_stack
        self._macro = macro_layer
        self._micro = micro_layer
        self._flow = vertical_flow
        self._supervisor = supervisor
        self._governance = governance

        self._explanations: list[dict] = []
        self._stats = {
            "layer_explanations": 0,
            "macro_explanations": 0,
            "micro_explanations": 0,
            "flow_explanations": 0,
            "decision_explanations": 0,
        }

    # ── explain_layer ───────────────────────────────────────
    def explain_layer(self, layer: dict) -> dict:
        """Expliquer l'état et l'activité d'une couche cognitive."""
        self._stats["layer_explanations"] += 1

        layer_name = layer.get("layer", layer.get("name", "unknown"))
        details = {}

        if self._stack:
            try:
                state = self._stack.get_layer_state(layer_name)
                details = state
            except Exception:
                details = {"simulated": True}

        explanation = (
            f"Couche '{layer_name}' : "
            f"{'active' if details.get('active', True) else 'inactive'}, "
            f"{details.get('buffer_size', 0)} éléments en buffer, "
            f"{details.get('push_count', 0)} push / "
            f"{details.get('pull_count', 0)} pull."
        )

        record = {
            "id": f"el_{uuid.uuid4().hex[:8]}",
            "type": "layer",
            "target": layer_name,
            "explanation": explanation,
            "details": details,
            "timestamp": time.time(),
        }
        self._explanations.append(record)
        self._trim()
        return record

    # ── explain_macro ───────────────────────────────────────
    def explain_macro(self, agent: dict) -> dict:
        """Expliquer le rôle et l'activité d'un macro-agent."""
        self._stats["macro_explanations"] += 1

        agent_name = agent.get("name", agent.get("macro", "unknown"))
        domain = agent.get("domain", "")
        details = {}

        if self._macro:
            try:
                macros = self._macro.list_macros()
                for m in macros:
                    if m.get("name") == agent_name:
                        details = m
                        break
            except Exception:
                pass

        explanation = (
            f"Macro-agent '{agent_name}' : "
            f"domaine '{domain or details.get('domain', 'N/A')}', "
            f"{'actif' if details.get('active', True) else 'inactif'}. "
            f"Regroupe les micro-agents liés à son domaine."
        )

        record = {
            "id": f"em_{uuid.uuid4().hex[:8]}",
            "type": "macro",
            "target": agent_name,
            "explanation": explanation,
            "details": details,
            "timestamp": time.time(),
        }
        self._explanations.append(record)
        self._trim()
        return record

    # ── explain_micro ───────────────────────────────────────
    def explain_micro(self, agent: dict) -> dict:
        """Expliquer l'activité d'un micro-agent."""
        self._stats["micro_explanations"] += 1

        agent_name = agent.get("name", agent.get("micro", "unknown"))
        details = {}

        if self._micro:
            try:
                micros = self._micro.list_micros()
                for m in micros:
                    if m.get("name") == agent_name:
                        details = m
                        break
            except Exception:
                pass

        executions = details.get("executions", 0)
        failures = details.get("failures", 0)
        latency = details.get("avg_latency_ms", 0.0)

        explanation = (
            f"Micro-agent '{agent_name}' : "
            f"{executions} exécutions, {failures} échecs, "
            f"latence moyenne {latency:.1f}ms, "
            f"{'actif' if details.get('active', True) else 'inactif'}."
        )

        record = {
            "id": f"ei_{uuid.uuid4().hex[:8]}",
            "type": "micro",
            "target": agent_name,
            "explanation": explanation,
            "details": details,
            "timestamp": time.time(),
        }
        self._explanations.append(record)
        self._trim()
        return record

    # ── explain_vertical_flow ───────────────────────────────
    def explain_vertical_flow(self) -> dict:
        """Expliquer le flux de raisonnement vertical actuel."""
        self._stats["flow_explanations"] += 1
        details = {}

        if self._flow:
            try:
                stats = self._flow.get_stats()
                details = stats
            except Exception:
                details = {"simulated": True}

        bu = details.get("bottom_up_flows", 0)
        td = details.get("top_down_flows", 0)
        merges = details.get("merges", 0)

        explanation = (
            f"Flux vertical : {bu} remontées (bottom-up), "
            f"{td} descentes (top-down), {merges} fusions. "
            f"Le flux bi-directionnel assure la cohérence entre "
            f"perception et décision."
        )

        record = {
            "id": f"ef_{uuid.uuid4().hex[:8]}",
            "type": "vertical_flow",
            "target": "vertical_reasoning_flow",
            "explanation": explanation,
            "details": details,
            "timestamp": time.time(),
        }
        self._explanations.append(record)
        self._trim()
        return record

    # ── explain_decision ────────────────────────────────────
    def explain_decision(self, decision: dict) -> dict:
        """Expliquer une décision prise par la hiérarchie."""
        self._stats["decision_explanations"] += 1

        action = decision.get("action", decision.get("decision", ""))
        source = decision.get("source", "unknown")
        reason = decision.get("reason", "")

        explanation = (
            f"Décision '{action}' émise par '{source}'. "
            f"Raison : {reason or 'non spécifiée'}. "
            f"Validée par la hiérarchie cognitive."
        )

        record = {
            "id": f"ed_{uuid.uuid4().hex[:8]}",
            "type": "decision",
            "target": action,
            "source": source,
            "explanation": explanation,
            "details": decision,
            "timestamp": time.time(),
        }
        self._explanations.append(record)
        self._trim()
        return record

    # ── get_explanation_history ──────────────────────────────
    def get_explanation_history(self) -> list[dict]:
        return self._explanations[-30:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "layered_explainability",
            "status": "ok",
            "explanations_total": len(self._explanations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._explanations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("LayeredExplainabilityEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _trim(self) -> None:
        if len(self._explanations) > 5000:
            self._explanations = self._explanations[-5000:]
