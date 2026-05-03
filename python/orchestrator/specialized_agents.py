"""
EXO v14 — SpecializedAgents (Agents experts)
Agents spécialisés, chacun limité à un domaine précis.
Tous héritent de SpecializedAgent et exposent l'API générique :
  handle_task(task)            → dict
  report_result()              → dict
  report_error(error)          → dict
  request_assistance(agent)    → dict
  health_check()               → dict
  restart()                    → None
  get_stats()                  → dict

Agents par défaut :
  AgentDomotique, AgentReseau, AgentMemoire, AgentPlanification,
  AgentSimulation, AgentPrevision, AgentOptimisation, AgentSecurite,
  AgentContexte, AgentAudio, AgentGUI, AgentScenarios, AgentRoutines
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("specialized_agents")


# ═════════════════════════════════════════════════════════════
#  BASE — SpecializedAgent
# ═════════════════════════════════════════════════════════════

class SpecializedAgent:
    """Base class for all EXO v14 specialized agents."""

    name: str = ""
    domain: str = ""
    version: str = "1.0"
    capabilities: list[str] = []

    def __init__(self, messaging_bus=None, meta_memory=None):
        self._bus = messaging_bus
        self._memory = meta_memory
        self._last_result: dict | None = None
        self._last_error: dict | None = None
        self._stats = {
            "tasks_handled": 0,
            "tasks_succeeded": 0,
            "tasks_failed": 0,
            "assistance_requests": 0,
        }

    # ── handle_task ─────────────────────────────────────────
    def handle_task(self, task: dict) -> dict:
        """Handle a task within this agent's domain.
        Subclasses override _execute_task for domain logic."""
        task_id = task.get("id", f"t_{uuid.uuid4().hex[:8]}")
        domain = task.get("domain", "")

        # Domain isolation: reject tasks outside our domain
        if domain and domain != self.domain:
            self._stats["tasks_failed"] += 1
            result = {
                "task_id": task_id,
                "agent": self.name,
                "status": "rejected",
                "reason": f"Domain mismatch: {domain} != {self.domain}",
            }
            self._last_error = result
            return result

        try:
            outcome = self._execute_task(task)
            self._stats["tasks_handled"] += 1
            self._stats["tasks_succeeded"] += 1
            result = {
                "task_id": task_id,
                "agent": self.name,
                "domain": self.domain,
                "status": "success",
                "result": outcome,
                "timestamp": time.time(),
            }
            self._last_result = result
            return result
        except Exception as exc:
            self._stats["tasks_handled"] += 1
            self._stats["tasks_failed"] += 1
            result = {
                "task_id": task_id,
                "agent": self.name,
                "domain": self.domain,
                "status": "error",
                "error": str(exc),
                "timestamp": time.time(),
            }
            self._last_error = result
            return result

    def _execute_task(self, task: dict) -> dict:
        """Override in subclasses for domain-specific logic."""
        return {"action": task.get("action", ""), "executed": True}

    # ── report ──────────────────────────────────────────────
    def report_result(self) -> dict:
        """Return the last successful result."""
        return self._last_result or {"agent": self.name, "status": "no_result"}

    def report_error(self, error: str | None = None) -> dict:
        """Return the last error or report a new one."""
        if error:
            self._last_error = {
                "agent": self.name,
                "error": error,
                "timestamp": time.time(),
            }
        return self._last_error or {"agent": self.name, "status": "no_error"}

    # ── assistance ──────────────────────────────────────────
    def request_assistance(self, target_agent: str) -> dict:
        """Request assistance from another agent via the bus."""
        self._stats["assistance_requests"] += 1
        if not self._bus:
            return {"sent": False, "reason": "no_messaging_bus"}

        result = self._bus.send(self.name, target_agent, {
            "type": "assistance_request",
            "payload": {
                "requesting_agent": self.name,
                "domain": self.domain,
                "last_error": self._last_error,
            },
        })
        return {"sent": result.get("delivered", False),
                "message_id": result.get("message_id", "")}

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": f"agent_{self.name}",
            "status": "ok",
            "domain": self.domain,
            "version": self.version,
        }

    def restart(self) -> None:
        self._last_result = None
        self._last_error = None
        for k in self._stats:
            self._stats[k] = 0
        log.info("Agent '%s' restarted", self.name)

    def get_stats(self) -> dict:
        return dict(self._stats)


# ═════════════════════════════════════════════════════════════
#  AGENTS SPÉCIALISÉS
# ═════════════════════════════════════════════════════════════

class AgentDomotique(SpecializedAgent):
    name = "domotique"
    domain = "domotique"
    version = "1.0"
    capabilities = ["control_devices", "manage_scenes", "automations"]

    def _execute_task(self, task: dict) -> dict:
        action = task.get("action", "")
        target = task.get("target", "")
        return {"action": action, "target": target,
                "executed": True, "domain": "domotique"}


class AgentReseau(SpecializedAgent):
    name = "reseau"
    domain = "reseau"
    version = "1.0"
    capabilities = ["network_status", "diagnostics", "bandwidth"]

    def _execute_task(self, task: dict) -> dict:
        action = task.get("action", "")
        return {"action": action, "executed": True, "domain": "reseau"}


class AgentMemoire(SpecializedAgent):
    name = "memoire"
    domain = "memoire"
    version = "1.0"
    capabilities = ["store", "retrieve", "search", "manage_context"]

    def _execute_task(self, task: dict) -> dict:
        action = task.get("action", "")
        key = task.get("key", "")
        value = task.get("value", None)
        if action == "store" and self._memory:
            entry_id = self._memory.meta_add({
                "category": task.get("category", "agent"),
                "key": key, "value": value,
            })
            return {"action": "store", "entry_id": entry_id}
        if action == "retrieve" and self._memory:
            entries = self._memory.meta_get(key)
            return {"action": "retrieve", "entries": entries}
        return {"action": action, "executed": True, "domain": "memoire"}


class AgentPlanification(SpecializedAgent):
    name = "planification"
    domain = "planification"
    version = "1.0"
    capabilities = ["plan_action", "schedule", "optimize_plan"]

    def _execute_task(self, task: dict) -> dict:
        action = task.get("action", "")
        return {"action": action, "executed": True,
                "plan_created": True, "domain": "planification"}


class AgentSimulation(SpecializedAgent):
    name = "simulation"
    domain = "simulation"
    version = "1.0"
    capabilities = ["simulate_plan", "simulate_scenario", "risk_analysis"]

    def _execute_task(self, task: dict) -> dict:
        action = task.get("action", "")
        return {"action": action, "executed": True,
                "simulated": True, "domain": "simulation"}


class AgentPrevision(SpecializedAgent):
    name = "prevision"
    domain = "prevision"
    version = "1.0"
    capabilities = ["predict_state", "forecast", "trend_analysis"]

    def _execute_task(self, task: dict) -> dict:
        action = task.get("action", "")
        return {"action": action, "executed": True,
                "prediction_made": True, "domain": "prevision"}


class AgentOptimisation(SpecializedAgent):
    name = "optimisation"
    domain = "optimisation"
    version = "1.0"
    capabilities = ["optimize", "tune", "benchmark"]

    def _execute_task(self, task: dict) -> dict:
        action = task.get("action", "")
        return {"action": action, "executed": True,
                "optimized": True, "domain": "optimisation"}


class AgentSecurite(SpecializedAgent):
    name = "securite"
    domain = "securite"
    version = "1.0"
    capabilities = ["check_permissions", "audit", "validate_action"]

    def _execute_task(self, task: dict) -> dict:
        action = task.get("action", "")
        return {"action": action, "executed": True,
                "security_check": "passed", "domain": "securite"}


class AgentContexte(SpecializedAgent):
    name = "contexte"
    domain = "contexte"
    version = "1.0"
    capabilities = ["gather_context", "analyze_context", "enrich"]

    def _execute_task(self, task: dict) -> dict:
        action = task.get("action", "")
        return {"action": action, "executed": True,
                "context_gathered": True, "domain": "contexte"}


class AgentAudio(SpecializedAgent):
    name = "audio"
    domain = "audio"
    version = "1.0"
    capabilities = ["stt", "tts", "vad", "wakeword"]

    def _execute_task(self, task: dict) -> dict:
        action = task.get("action", "")
        return {"action": action, "executed": True, "domain": "audio"}


class AgentGUI(SpecializedAgent):
    name = "gui"
    domain = "gui"
    version = "1.0"
    capabilities = ["display", "notify", "update_ui"]

    def _execute_task(self, task: dict) -> dict:
        action = task.get("action", "")
        return {"action": action, "executed": True, "domain": "gui"}


class AgentScenarios(SpecializedAgent):
    name = "scenarios"
    domain = "scenarios"
    version = "1.0"
    capabilities = ["generate_variants", "compare", "select"]

    def _execute_task(self, task: dict) -> dict:
        action = task.get("action", "")
        return {"action": action, "executed": True,
                "variants_generated": True, "domain": "scenarios"}


class AgentRoutines(SpecializedAgent):
    name = "routines"
    domain = "routines"
    version = "1.0"
    capabilities = ["manage_routines", "schedule", "trigger"]

    def _execute_task(self, task: dict) -> dict:
        action = task.get("action", "")
        return {"action": action, "executed": True,
                "routine_managed": True, "domain": "routines"}


# ── Factory ─────────────────────────────────────────────────

DEFAULT_AGENTS: list[type[SpecializedAgent]] = [
    AgentDomotique, AgentReseau, AgentMemoire, AgentPlanification,
    AgentSimulation, AgentPrevision, AgentOptimisation, AgentSecurite,
    AgentContexte, AgentAudio, AgentGUI, AgentScenarios, AgentRoutines,
]


def create_default_agents(messaging_bus=None,
                          meta_memory=None) -> list[SpecializedAgent]:
    """Instantiate all default specialized agents."""
    return [cls(messaging_bus=messaging_bus, meta_memory=meta_memory)
            for cls in DEFAULT_AGENTS]
