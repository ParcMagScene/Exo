"""
EXO v14 — CognitiveOrchestrator (Noyau central)
Coordonne tous les agents spécialisés : réception d'intentions,
distribution de tâches, collecte de résultats, fusion de raisonnements,
résolution de conflits, validation des décisions.

API:
  orchestrate(intent)                → dict
  dispatch(task, agent_name)         → dict
  collect(agent_result)              → list[dict]
  resolve_conflicts(results)         → dict
  finalize_decision()                → dict
  health_check()                     → dict
  restart()                          → None
  get_stats()                        → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("cognitive_orchestrator")


class CognitiveOrchestrator:
    """Noyau cognitif central EXO v14."""

    def __init__(self, registry=None, messaging_bus=None,
                 conflict_resolver=None, meta_memory=None,
                 governance=None):
        self._registry = registry
        self._bus = messaging_bus
        self._resolver = conflict_resolver
        self._memory = meta_memory
        self._governance = governance
        self._collected: list[dict] = []
        self._decision_history: list[dict] = []
        self._stats = {
            "intents_processed": 0,
            "tasks_dispatched": 0,
            "results_collected": 0,
            "conflicts_resolved": 0,
            "decisions_finalized": 0,
        }

    # ── orchestrate ─────────────────────────────────────────
    def orchestrate(self, intent: dict) -> dict:
        """Full orchestration cycle: analyze → dispatch → collect → resolve → finalize."""
        intent_id = f"int_{uuid.uuid4().hex[:8]}"
        self._stats["intents_processed"] += 1
        self._collected = []

        # 1. Determine which agents are relevant
        target_domains = self._resolve_domains(intent)
        if not target_domains:
            target_domains = [intent.get("domain", "")]

        # 2. Build and dispatch tasks
        dispatched: list[dict] = []
        for domain in target_domains:
            task = {
                "id": f"t_{uuid.uuid4().hex[:8]}",
                "intent_id": intent_id,
                "domain": domain,
                "action": intent.get("action", ""),
                "params": intent.get("params", {}),
                "description": intent.get("description", ""),
            }

            agents = self._get_agents_for_domain(domain)
            for agent in agents:
                result = self.dispatch(task, agent.name)
                dispatched.append(result)

        # 3. Resolve conflicts if multiple results
        resolution = {}
        if len(self._collected) > 1 and self._resolver:
            resolution = self.resolve_conflicts(self._collected)

        # 4. Finalize decision
        decision = self.finalize_decision()

        return {
            "intent_id": intent_id,
            "intent": intent,
            "dispatched": dispatched,
            "collected": self._collected,
            "resolution": resolution,
            "decision": decision,
            "timestamp": time.time(),
        }

    # ── dispatch ────────────────────────────────────────────
    def dispatch(self, task: dict, agent_name: str) -> dict:
        """Dispatch a task to a specific agent."""
        self._stats["tasks_dispatched"] += 1

        if not self._registry:
            return {"agent": agent_name, "status": "no_registry"}

        agent = self._registry.get_agent(agent_name)
        if not agent:
            return {"agent": agent_name, "status": "agent_not_found"}

        result = agent.handle_task(task)
        self._collected.append(result)
        self._stats["results_collected"] += 1

        # Notify via bus
        if self._bus:
            self._bus.send("orchestrator", agent_name, {
                "type": "task_request",
                "payload": task,
            })

        log.debug("Dispatched task to %s → %s",
                  agent_name, result.get("status"))
        return result

    # ── collect ─────────────────────────────────────────────
    def collect(self, agent_result: dict) -> list[dict]:
        """Collect a result from an agent (can be called externally)."""
        self._collected.append(agent_result)
        self._stats["results_collected"] += 1
        return list(self._collected)

    # ── resolve_conflicts ───────────────────────────────────
    def resolve_conflicts(self, results: list[dict] | None = None) -> dict:
        """Use ConflictResolver to resolve conflicting agent results."""
        if results is None:
            results = self._collected

        if not self._resolver:
            return {"resolved": False, "reason": "no_conflict_resolver"}

        resolution = self._resolver.resolve(results)
        self._stats["conflicts_resolved"] += 1
        return resolution

    # ── finalize_decision ───────────────────────────────────
    def finalize_decision(self) -> dict:
        """Produce a final merged decision from collected results."""
        self._stats["decisions_finalized"] += 1

        if not self._collected:
            decision = {
                "status": "no_results",
                "agents_involved": 0,
                "timestamp": time.time(),
            }
            self._decision_history.append(decision)
            return decision

        # Merge outcomes from all successful results
        successful = [r for r in self._collected
                      if r.get("status") == "success"]
        failed = [r for r in self._collected
                  if r.get("status") != "success"]

        agents_involved = list({r.get("agent", "") for r in self._collected})

        merged_result = {}
        for r in successful:
            inner = r.get("result", {})
            if isinstance(inner, dict):
                merged_result.update(inner)

        decision = {
            "status": "decided" if successful else "failed",
            "agents_involved": len(agents_involved),
            "agent_names": agents_involved,
            "successful": len(successful),
            "failed": len(failed),
            "merged_result": merged_result,
            "timestamp": time.time(),
        }
        self._decision_history.append(decision)
        if len(self._decision_history) > 500:
            self._decision_history = self._decision_history[-300:]

        return decision

    # ── domain routing ──────────────────────────────────────
    def _resolve_domains(self, intent: dict) -> list[str]:
        """Determine which domains an intent should be routed to."""
        domains = []
        explicit = intent.get("domain", "")
        if explicit:
            domains.append(explicit)

        # Multi-domain intents
        if intent.get("domains"):
            domains.extend(intent["domains"])

        return list(dict.fromkeys(domains))  # deduplicate, preserve order

    def _get_agents_for_domain(self, domain: str) -> list:
        """Get agents from registry for a domain."""
        if not self._registry:
            return []
        return self._registry.get_agents_for_domain(domain)

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "cognitive_orchestrator",
            "status": "ok",
            "collected_pending": len(self._collected),
            "decisions_made": self._stats["decisions_finalized"],
        }

    def restart(self) -> None:
        self._collected.clear()
        self._decision_history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("CognitiveOrchestrator restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
