#!/usr/bin/env python3
"""

# Patch global EXO : forcer le working directory à D:/EXO/ pour tous les services
import os
os.chdir("D:/EXO/")
EXO v10 — TaskExecutor Server (WebSocket)
Port 8779 — Exécution séquentielle/parallèle des plans avec pause/resume

Reçoit un plan du TaskPlanner et orchestre l'exécution des étapes
via les microservices existants. Gère erreurs, retries, pause/resume et replanning.

Protocol WebSocket :
  → {"action":"execute_plan","params":{"plan_id":"...","plan":{...}}}
  ← {"ok":true,"data":{"plan_id":"...","status":"running"}}
  ← {"type":"step_started","plan_id":"...","step_index":0}
  ← {"type":"step_completed","plan_id":"...","step_index":0,"result":{...}}
  ← {"type":"plan_completed","plan_id":"...","status":"completed","results":[...]}

  → {"action":"pause","params":{"plan_id":"..."}}
  ← {"ok":true}

  → {"action":"resume","params":{"plan_id":"..."}}
  ← {"ok":true}

  → {"action":"abort","params":{"plan_id":"..."}}
  ← {"ok":true}

  → {"action":"status","params":{"plan_id":"..."}}
  ← {"ok":true,"data":{"plan_id":"...","status":"...","progress":{...}}}
"""

import asyncio
try:
    import ujson as json  # v6.0 perf : 3-5x plus rapide que stdlib (audit perf)
except ImportError:
    import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")

from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9


# --- Logging EXO centralisé (identique C++) ---
import os
from pathlib import Path
def _get_exo_logfile():
    # Correction : tous les logs doivent aller dans D:/EXO/logs/
    log_dir = os.environ.get("EXO_LOGS_DIR", "D:/EXO/logs")
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    ts = os.environ.get("EXO_SESSION_TIMESTAMP")
    if not ts:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(log_dir, f"exo_{ts}.log")

logfile = _get_exo_logfile()

_file_handler = logging.FileHandler(logfile, encoding="utf-8", delay=False)
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [Executor] %(message)s"))
_file_handler.flush = _file_handler.stream.flush

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Executor] %(message)s")
log = logging.getLogger("task_executor")
log.addHandler(_file_handler)
log.propagate = True
log.info("=== EXO TASK_EXECUTOR_SERVER STARTUP ===")
_file_handler.flush()

PORT = 8779
STEP_TIMEOUT = 30.0
MAX_RETRIES = 3


async def _safe_notify(ws: Any, payload: dict) -> bool:
    """Send a notification on a WebSocket without crashing the executor.

    Returns True if the message was sent, False if the WS was already closed
    or another error occurred (logged but swallowed).
    """
    try:
        await ws.send(json.dumps(payload))
        return True
    except Exception as exc:  # ConnectionClosed*, RuntimeError, etc.
        log.warning("notify_ws.send dropped (%s): %.80s",
                    type(exc).__name__, payload.get("type", ""))
        return False

# ── Tool → Service mapping ─────────────────────────
TOOL_SERVICE_MAP = {
    "search_web": ("websearch", 8773),
    "get_news": ("news", 8774),
    "get_summary": ("knowledge", 8775),
    "calculate": ("tools", 8776),
    "convert": ("tools", 8776),
    "remember_info": ("memory", 8771),
    "recall_info": ("memory", 8771),
    "get_context": ("context", 8777),
    "create_plan": ("planner", 8778),
}


class ExecutionState:
    """Tracks execution state of a single plan."""

    def __init__(self, plan_id: str, plan: dict) -> None:
        self.plan_id = plan_id
        self.plan = plan
        self.status = "running"
        self.results: dict[int, Any] = {}
        self.errors: dict[int, str] = {}
        self.started_at = time.time()
        self.aborted = False
        self.paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # not paused initially

    def to_dict(self) -> dict:
        steps = self.plan.get("steps", [])
        completed = sum(1 for r in self.results.values() if r is not None)
        failed = len(self.errors)
        total = len(steps)
        return {
            "plan_id": self.plan_id,
            "status": self.status,
            "progress": {
                "total": total,
                "completed": completed,
                "failed": failed,
                "pct": round(completed / total * 100) if total else 0,
            },
            "elapsed_s": round(time.time() - self.started_at, 2),
        }


class TaskExecutor:
    """Executes task plans by dispatching steps to tool services."""

    def __init__(self) -> None:
        self._executions: dict[str, ExecutionState] = {}
        self._service_connections: dict[str, Any] = {}

    async def execute_plan(self, plan_id: str, plan: dict,
                           notify_ws: Any) -> dict:
        """Execute a full plan, sending progress via notify_ws."""
        state = ExecutionState(plan_id, plan)
        self._executions[plan_id] = state

        steps = plan.get("steps", [])
        strategy = plan.get("strategy", "sequential")

        try:
            if strategy == "parallel":
                await self._execute_parallel(state, steps, notify_ws)
            else:
                await self._execute_sequential(state, steps, notify_ws)

            # Determine final status
            if state.aborted:
                state.status = "aborted"
            elif state.paused:
                state.status = "paused"
            elif state.errors:
                state.status = "partial" if state.results else "failed"
            else:
                state.status = "completed"

        except Exception as e:
            log.error("Plan execution error: %s", e, exc_info=True)
            state.status = "failed"
            state.errors[-1] = "Erreur interne d'exécution"

        # Send final notification
        await _safe_notify(notify_ws, {
            "type": "plan_completed",
            "plan_id": plan_id,
            "status": state.status,
            "results": {str(k): v for k, v in state.results.items()},
            "errors": {str(k): v for k, v in state.errors.items()},
        })

        return state.to_dict()

    async def _execute_sequential(self, state: ExecutionState,
                                   steps: list[dict], notify_ws: Any) -> None:
        """Execute steps one by one, respecting dependencies."""
        for step in steps:
            if state.aborted:
                break
            # Wait if paused
            await state._pause_event.wait()
            if state.aborted:
                break
            if step.get("is_composite"):
                continue
            if step.get("status") in ("completed", "skipped"):
                continue

            idx = step.get("index", 0)
            # Check dependencies
            deps = step.get("depends_on", [])
            deps_ok = all(d in state.results for d in deps)
            if not deps_ok:
                state.errors[idx] = "Dependencies not met"
                continue

            await self._execute_step(state, step, notify_ws)

    async def _execute_parallel(self, state: ExecutionState,
                                 steps: list[dict], notify_ws: Any) -> None:
        """Execute independent steps in parallel batches."""
        remaining = [s for s in steps
                     if not s.get("is_composite")
                     and s.get("status") not in ("completed", "skipped")]

        while remaining and not state.aborted:
            # Wait if paused
            await state._pause_event.wait()
            if state.aborted:
                break
            # Find steps with all dependencies satisfied
            batch = []
            for step in remaining:
                deps = step.get("depends_on", [])
                if all(d in state.results for d in deps):
                    batch.append(step)

            if not batch:
                # No executable steps — deadlock or all done
                break

            # Execute batch in parallel
            tasks = [
                self._execute_step(state, step, notify_ws)
                for step in batch
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

            # Remove executed steps
            executed_indices = {s.get("index") for s in batch}
            remaining = [s for s in remaining
                         if s.get("index") not in executed_indices]

    async def _execute_step(self, state: ExecutionState,
                             step: dict, notify_ws: Any) -> None:
        """Execute a single step by dispatching to appropriate service."""
        idx = step.get("index", 0)
        tool = step.get("tool", "")
        params = step.get("params", {})
        description = step.get("description", "")

        # Notify step started
        await _safe_notify(notify_ws, {
            "type": "step_started",
            "plan_id": state.plan_id,
            "step_index": idx,
            "tool": tool,
            "description": description,
        })

        try:
            result = await self._dispatch_to_service(tool, params)
            state.results[idx] = result

            await _safe_notify(notify_ws, {
                "type": "step_completed",
                "plan_id": state.plan_id,
                "step_index": idx,
                "status": "completed",
                "result": result,
            })
            log.info("Step %d completed (plan %s): %s", idx, state.plan_id, tool)

        except Exception as e:
            log.error("Step %d failed (plan %s): %s — %s",
                      idx, state.plan_id, tool, e, exc_info=True)
            error_msg = "Erreur interne d'exécution"
            state.errors[idx] = error_msg

            await _safe_notify(notify_ws, {
                "type": "step_failed",
                "plan_id": state.plan_id,
                "step_index": idx,
                "status": "failed",
                "error": error_msg,
            })

    async def _dispatch_to_service(self, tool: str, params: dict) -> dict:
        """Dispatch a tool call to the appropriate microservice via WebSocket."""
        service_info = TOOL_SERVICE_MAP.get(tool)
        if not service_info:
            return {"warning": f"Unknown tool: {tool}", "tool": tool, "params": params}

        service_name, port = service_info

        # Map tool name to service action
        action = self._tool_to_action(tool)

        try:
            async with websockets.connect(
                f"ws://localhost:{port}",
                ping_interval=None, ping_timeout=None,
            ) as ws:
                # Consume ready message
                ready = await asyncio.wait_for(ws.recv(), timeout=5.0)

                # Send action
                await ws.send(json.dumps({"action": action, "params": params}))

                # Wait for response
                raw = await asyncio.wait_for(ws.recv(), timeout=STEP_TIMEOUT)
                response = json.loads(raw)

                if response.get("ok"):
                    return response.get("data", {})
                else:
                    raise RuntimeError(response.get("error", "Service error"))

        except asyncio.TimeoutError:
            raise RuntimeError(f"Timeout calling {service_name}:{port}")
        except ConnectionRefusedError:
            raise RuntimeError(f"Service {service_name}:{port} not available")

    def _tool_to_action(self, tool: str) -> str:
        """Map EXO tool name to service action name."""
        mapping = {
            "search_web": "search_web",
            "get_news": "get_news",
            "get_summary": "get_summary",
            "calculate": "calculate",
            "convert": "convert",
            "remember_info": "add",
            "recall_info": "search",
            "get_context": "get_context",
            "create_plan": "create_plan",
        }
        return mapping.get(tool, tool)

    def abort(self, plan_id: str) -> bool:
        state = self._executions.get(plan_id)
        if not state:
            return False
        state.aborted = True
        state._pause_event.set()  # unblock if paused
        return True

    def pause(self, plan_id: str) -> bool:
        state = self._executions.get(plan_id)
        if not state or state.status != "running":
            return False
        state.paused = True
        state.status = "paused"
        state._pause_event.clear()
        log.info("Plan %s paused", plan_id)
        return True

    def resume(self, plan_id: str) -> bool:
        state = self._executions.get(plan_id)
        if not state or not state.paused:
            return False
        state.paused = False
        state.status = "running"
        state._pause_event.set()
        log.info("Plan %s resumed", plan_id)
        return True

    def get_status(self, plan_id: str) -> dict | None:
        state = self._executions.get(plan_id)
        return state.to_dict() if state else None


# ─────────────────────────────────────────────────────
#  WebSocket Handler
# ─────────────────────────────────────────────────────

async def handle_client(ws, executor: TaskExecutor) -> None:
    log.info("Executor client connected")
    await ws.send(json.dumps({
        "type": "ready",
        "service": "task_executor",
        "model": "n/a",
        "device": "n/a",
        "backend": "n/a"
    }))

    try:
        async for raw in ws:
            if not isinstance(raw, str):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action", msg.get("type", ""))
            params = msg.get("params", {})

            if action == "ping":
                await ws.send(json.dumps({"type": "pong"}))
                continue

            try:
                if action == "execute_plan":
                    plan_id = params.get("plan_id", "")
                    plan = params.get("plan", {})
                    # Start execution in background, results streamed via ws
                    asyncio.create_task(
                        executor.execute_plan(plan_id, plan, ws)
                    )
                    await ws.send(json.dumps({
                        "ok": True,
                        "data": {"plan_id": plan_id, "status": "running"},
                    }))

                elif action == "abort":
                    plan_id = params.get("plan_id", "")
                    ok = executor.abort(plan_id)
                    await ws.send(json.dumps({"ok": ok}))

                elif action == "pause":
                    plan_id = params.get("plan_id", "")
                    ok = executor.pause(plan_id)
                    await ws.send(json.dumps({"ok": ok}))

                elif action == "resume":
                    plan_id = params.get("plan_id", "")
                    ok = executor.resume(plan_id)
                    await ws.send(json.dumps({"ok": ok}))

                elif action == "status":
                    plan_id = params.get("plan_id", "")
                    status = executor.get_status(plan_id)
                    if status:
                        await ws.send(json.dumps({"ok": True, "data": status}))
                    else:
                        await ws.send(json.dumps({"ok": False, "error": "Execution not found"}))

                else:
                    await ws.send(json.dumps({
                        "ok": False,
                        "error": f"Unknown action: {action}",
                    }))

            except Exception as e:
                log.error("Executor operation error: %s", e, exc_info=True)
                await ws.send(json.dumps({"ok": False, "error": "Erreur interne du service executor"}))

    except Exception as e:
        log.error("Executor session error: %s", e)
    finally:
        log.info("Executor client disconnected")


# ─────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────

async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="EXO v10 Task Executor Server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    ensure_single_instance(args.port, "task_executor")
    _v9 = init_v9("task_executor", args.port)

    executor = TaskExecutor()
    log.info("TaskExecutor initialized")

    async def handler(ws):
        await handle_client(ws, executor)

    server = await websockets.serve(
        handler, args.host, args.port,
        ping_interval=None, ping_timeout=None,
    )
    log.info("Task Executor running on ws://%s:%d", args.host, args.port)

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        await server.wait_closed()
        log.info("Task Executor stopped")


if __name__ == "__main__":
    asyncio.run(main())
