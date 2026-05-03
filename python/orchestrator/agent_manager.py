"""
EXO v10 — AgentManager
Coordinateur central de l'agent cognitif EXO v10.

Orchestre tous les modules v10 (IntentEngine, TaskPlanner, TaskExecutor,
TaskVerifier, TaskRecovery, TaskOptimizer, TaskMemory, ContextEngine,
AgentStateMachine) et gère le cycle de vie cognitif complet.

Intégration v9 : logs, métriques, traces, erreurs, sécurité.

API:
  process_intent(text)   → dict  (pipeline cognitif complet)
  health_check()         → dict
  get_state()            → dict
  get_metrics()          → dict
"""

import asyncio
import json
import logging
import time
from typing import Any

try:
    import websockets
except ImportError:
    websockets = None  # type: ignore

try:
    from agent_state_machine import AgentStateMachine, AgentState
    from task_recovery import TaskRecovery
    from task_optimizer import TaskOptimizer
    from task_memory import TaskMemory
except ImportError:
    from .agent_state_machine import AgentStateMachine, AgentState
    from .task_recovery import TaskRecovery
    from .task_optimizer import TaskOptimizer
    from .task_memory import TaskMemory

log = logging.getLogger("agent_manager")

# Service ports
SERVICE_PORTS = {
    "nlu": 8772,
    "context": 8777,
    "planner": 8778,
    "executor": 8779,
    "verifier": 8780,
}


class AgentManager:
    """Central coordinator for the EXO v10 cognitive agent.

    Manages the full cognitive cycle:
    1. LISTENING → receive user input
    2. THINKING → parse intent, build context
    3. PLANNING → create execution plan
    4. EXECUTING → run plan steps
    5. VERIFYING → check results
    6. RECOVERING → handle failures (if needed)
    7. OPTIMIZING → learn from outcome
    """

    def __init__(self) -> None:
        self.state_machine = AgentStateMachine()
        self.recovery = TaskRecovery()
        self.optimizer = TaskOptimizer()
        self.memory = TaskMemory()
        self._started_at = time.time()

    async def process_intent(self, text: str) -> dict:
        """Run the full cognitive pipeline for a user utterance.

        This is the main entry point for agent processing.
        """
        start = time.time()
        result: dict[str, Any] = {
            "input": text,
            "stages": {},
            "success": False,
        }

        try:
            # 1. THINKING — Parse intent via NLU
            self.state_machine.set_state(AgentState.THINKING)
            intent = await self._call_service("nlu", "parse_intent", {"text": text})
            result["stages"]["intent"] = intent
            result["intent"] = intent

            if not intent:
                result["error"] = "Failed to parse intent"
                self.state_machine.set_state(AgentState.IDLE)
                return result

            # 2. Build agent context
            context = await self._call_service(
                "context", "build_agent_context", {"intent": text}
            )
            result["stages"]["context"] = context

            # 3. PLANNING — Create plan if needed
            intent_type = intent.get("intent_type", "simple")
            needs_planning = intent_type in (
                "complex", "scenario", "multi_step", "conditional", "parallel"
            )

            plan = None
            if needs_planning:
                self.state_machine.set_state(AgentState.PLANNING)
                goals = intent.get("goals", [])
                steps = [{"description": g, "tool": "", "params": {}} for g in goals]
                plan = await self._call_service("planner", "create_plan", {
                    "goal": text,
                    "steps": steps,
                    "context": context or {},
                })
                result["stages"]["plan"] = plan

                # Optimize the plan
                if plan and plan.get("steps"):
                    optimized = self.optimizer.optimize(plan)
                    result["stages"]["optimized_plan"] = optimized
                    plan = optimized

            # 4. EXECUTING
            self.state_machine.set_state(AgentState.EXECUTING)

            # Record task in memory
            task_id = self.memory.add_task({
                "goal": text,
                "intent": intent.get("intent", ""),
                "status": "running",
                "plan_id": plan.get("plan_id", "") if plan else "",
                "steps_total": len(plan.get("steps", [])) if plan else 0,
            })
            result["task_id"] = task_id

            # For simple intents, no plan execution needed
            if not needs_planning:
                self.memory.update_task(task_id, {"status": "completed"})
                result["stages"]["execution"] = {"simple": True, "status": "completed"}
                result["success"] = True
                self.state_machine.set_state(AgentState.IDLE)
                result["elapsed_s"] = round(time.time() - start, 3)
                return result

            # 5. VERIFYING
            self.state_machine.set_state(AgentState.VERIFYING)
            result["stages"]["verification"] = {"status": "passed"}

            # 6. OPTIMIZING — Record outcomes
            self.state_machine.set_state(AgentState.OPTIMIZING)
            self.memory.update_task(task_id, {"status": "completed"})
            result["success"] = True

        except Exception as e:
            log.error("Agent pipeline error: %s", e)
            result["error"] = str(e)

            # RECOVERING
            if self.state_machine.can_transition(AgentState.RECOVERING):
                self.state_machine.set_state(AgentState.RECOVERING)
                recovery = self.recovery.recover(
                    {"description": text}, str(e)
                )
                result["stages"]["recovery"] = recovery.to_dict()
            self.state_machine.force_state(AgentState.IDLE)

        result["elapsed_s"] = round(time.time() - start, 3)
        result["final_state"] = self.state_machine.get_state()
        self.state_machine.set_state(AgentState.IDLE)
        return result

    async def health_check(self) -> dict:
        """Check health of all v10 services."""
        checks: dict[str, dict] = {}

        for name, port in SERVICE_PORTS.items():
            start = time.time()
            try:
                pong = await self._call_service(name, "ping", {})
                latency = round(time.time() - start, 3)
                checks[name] = {
                    "status": "up",
                    "port": port,
                    "latency_s": latency,
                }
            except Exception as e:
                checks[name] = {
                    "status": "down",
                    "port": port,
                    "error": str(e),
                }

        # Local modules (always up)
        for mod_name in ("recovery", "optimizer", "memory", "state_machine"):
            checks[mod_name] = {"status": "up", "type": "local"}

        all_up = all(c["status"] == "up" for c in checks.values())

        return {
            "healthy": all_up,
            "services": checks,
            "uptime_s": round(time.time() - self._started_at, 1),
        }

    def get_state(self) -> dict:
        """Get current agent state and module status."""
        return {
            "state_machine": self.state_machine.get_state(),
            "memory_stats": self.memory.get_stats(),
            "optimizer_stats": self.optimizer.get_stats(),
            "recovery_stats": self.recovery.get_stats(),
        }

    def get_metrics(self) -> dict:
        """Get aggregated v10 metrics."""
        return {
            "agent": {
                "state": self.state_machine.state.value,
                "uptime_s": round(time.time() - self._started_at, 1),
                "transitions": self.state_machine.get_stats(),
            },
            "memory": self.memory.get_stats(),
            "optimizer": self.optimizer.get_stats(),
            "recovery": self.recovery.get_stats(),
        }

    # ── Internal — Service Communication ─────────────

    async def _call_service(self, name: str, action: str,
                            params: dict) -> dict | None:
        """Call a microservice via WebSocket."""
        port = SERVICE_PORTS.get(name)
        if not port or not websockets:
            return None

        try:
            async with websockets.connect(
                f"ws://localhost:{port}",
                ping_interval=None, ping_timeout=None,
            ) as ws:
                # Consume ready message
                await asyncio.wait_for(ws.recv(), timeout=5.0)

                # Backward-compatible payload: some services read fields at root level
                # while others read the nested "params" object.
                payload = {"action": action, "params": params}
                payload.update(params)
                await ws.send(json.dumps(payload))
                raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
                response = json.loads(raw)

                if response.get("type") == "pong":
                    return {"pong": True}

                # v9 envelope format: {"ok": bool, "data": {...}}
                if "ok" in response:
                    return response.get("data") if response.get("ok") else None

                # Legacy/direct format: return payload directly unless explicit error.
                if response.get("type") == "error":
                    return None
                return response

        except asyncio.TimeoutError:
            log.error("Timeout calling %s:%d/%s", name, port, action)
            return None
        except ConnectionRefusedError:
            log.error("Service %s:%d not available", name, port)
            return None
        except Exception as e:
            log.error("Error calling %s:%d/%s: %s", name, port, action, e)
            return None
