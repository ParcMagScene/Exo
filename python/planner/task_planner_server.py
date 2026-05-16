#!/usr/bin/env python3
"""

# Patch global EXO : forcer le working directory à D:/EXO/ pour tous les services
import os
os.chdir("D:/EXO/")
EXO v10 — TaskPlanner Server (WebSocket) — HTN Decomposition
Port 8778 — Planification hiérarchique avec expected outcomes

Décompose un objectif complexe en plan multi-étapes via HTN
(Hierarchical Task Network) avec DAG de dépendances et optimisation.

Protocol WebSocket :
  → {"action":"create_plan","params":{"goal":"...","context":{},"strategy":"sequential|parallel|adaptive"}}
  ← {"ok":true,"data":{"plan_id":"...","steps":[...],"status":"pending","dag":{...}}}

  → {"action":"decompose","params":{"plan_id":"...","step_index":0,"sub_steps":[...]}}
  ← {"ok":true,"data":{"plan_id":"...","decomposed":true}}

  → {"action":"execute_step","params":{"plan_id":"...","step_index":0}}
  ← {"ok":true,"data":{"step_index":0,"result":{...},"status":"completed"}}

  → {"action":"get_plan","params":{"plan_id":"..."}}
  ← {"ok":true,"data":{"plan_id":"...","steps":[...],"status":"..."}}

  → {"action":"list_plans"}
  ← {"ok":true,"data":{"plans":[...]}}

  → {"action":"next_executable","params":{"plan_id":"..."}}
  ← {"ok":true,"data":{"steps":[...],"parallel":true}}

  → {"action":"replan","params":{"plan_id":"...","failed_step":2,"strategy":"skip|retry|alternative"}}
  ← {"ok":true,"data":{"plan_id":"...","replanned":true}}

  → {"action":"cancel_plan","params":{"plan_id":"..."}}
  ← {"ok":true}
"""

import asyncio
try:
    import ujson as json  # v6.0 perf : 3-5x plus rapide que stdlib (audit perf)
except ImportError:
    import json
import logging
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
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
_file_handler.setFormatter(logging.Formatter("%(asctime)s [Planner] %(message)s"))
_file_handler.flush = _file_handler.stream.flush

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Planner] %(message)s")
log = logging.getLogger("task_planner")
log.addHandler(_file_handler)
log.propagate = True
log.info("=== EXO TASK_PLANNER_SERVER STARTUP ===")
_file_handler.flush()

PORT = 8778
MAX_PLANS = 50
MAX_STEPS = 20
STEP_TIMEOUT = 30.0  # seconds
MAX_RETRIES = 3


class ExecutionStrategy(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ADAPTIVE = "adaptive"  # auto-detect from DAG


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


@dataclass
class PlanStep:
    """A single step in a task plan (HTN node)."""
    index: int
    description: str
    tool: str  # which EXO tool to call
    params: dict = field(default_factory=dict)
    status: str = StepStatus.PENDING
    result: dict | None = None
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None
    depends_on: list[int] = field(default_factory=list)
    # v8 HTN fields
    priority: int = 0  # higher = more important
    retries: int = 0
    max_retries: int = MAX_RETRIES
    sub_steps: list[int] = field(default_factory=list)  # child step indices (HTN)
    parent_step: int | None = None  # parent step index (HTN)
    is_composite: bool = False  # True if this is a composite HTN task
    # v10 fields
    expected_outcome: str = ""  # what success looks like
    conditions: list[str] = field(default_factory=list)  # preconditions

    def to_dict(self) -> dict:
        d = {
            "index": self.index,
            "description": self.description,
            "tool": self.tool,
            "params": self.params,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "depends_on": self.depends_on,
            "priority": self.priority,
            "retries": self.retries,
            "is_composite": self.is_composite,
            "duration_s": (
                round(self.completed_at - self.started_at, 2)
                if self.started_at and self.completed_at
                else None
            ),
        }
        if self.sub_steps:
            d["sub_steps"] = self.sub_steps
        if self.parent_step is not None:
            d["parent_step"] = self.parent_step
        if self.expected_outcome:
            d["expected_outcome"] = self.expected_outcome
        if self.conditions:
            d["conditions"] = self.conditions
        return d


@dataclass
class TaskPlan:
    """A multi-step plan for achieving a goal (HTN-based)."""
    plan_id: str
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    status: str = PlanStatus.PENDING
    created_at: float = field(default_factory=time.time)
    context: dict = field(default_factory=dict)
    strategy: str = ExecutionStrategy.SEQUENTIAL
    replanned: bool = False

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
            "created_at": self.created_at,
            "context": self.context,
            "strategy": self.strategy,
            "replanned": self.replanned,
            "progress": self._progress(),
            "dag": self._build_dag(),
        }

    def _progress(self) -> dict:
        total = len(self.steps)
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in self.steps if s.status == StepStatus.FAILED)
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pct": round(completed / total * 100) if total else 0,
        }

    def update_status(self) -> None:
        """Recalculate plan status from step statuses."""
        if not self.steps:
            self.status = PlanStatus.PENDING
            return

        # Only consider leaf steps (non-composite) for status
        leaf_steps = [s for s in self.steps if not s.is_composite]
        if not leaf_steps:
            leaf_steps = self.steps

        statuses = {s.status for s in leaf_steps}

        if statuses == {StepStatus.COMPLETED}:
            self.status = PlanStatus.COMPLETED
        elif StepStatus.RUNNING in statuses:
            self.status = PlanStatus.RUNNING
        elif StepStatus.FAILED in statuses and StepStatus.COMPLETED in statuses:
            self.status = PlanStatus.PARTIAL
        elif statuses == {StepStatus.FAILED} or (
            StepStatus.FAILED in statuses and StepStatus.PENDING not in statuses
        ):
            self.status = PlanStatus.FAILED
        elif statuses == {StepStatus.PENDING}:
            self.status = PlanStatus.PENDING
        else:
            self.status = PlanStatus.RUNNING

    def _build_dag(self) -> dict:
        """Build DAG representation for visualization."""
        nodes = []
        edges = []
        for s in self.steps:
            nodes.append({"index": s.index, "status": s.status,
                          "tool": s.tool, "composite": s.is_composite})
            for dep in s.depends_on:
                edges.append({"from": dep, "to": s.index})
            if s.parent_step is not None:
                edges.append({"from": s.parent_step, "to": s.index, "type": "parent"})
        return {"nodes": nodes, "edges": edges}


# ─────────────────────────────────────────────────────
#  TaskPlanner — manages plans and step execution
# ─────────────────────────────────────────────────────

class TaskPlanner:
    """Manages multi-step task plans with HTN decomposition."""

    def __init__(self) -> None:
        self._plans: dict[str, TaskPlan] = {}

    def create_plan(
        self, goal: str, steps: list[dict], context: dict | None = None,
        strategy: str = ExecutionStrategy.SEQUENTIAL,
    ) -> TaskPlan:
        """Create a new plan from a goal and step descriptions.

        Each step dict should have:
          - description: str
          - tool: str (EXO tool name)
          - params: dict (tool parameters)
          - depends_on: list[int] (optional, step indices this depends on)
          - priority: int (optional, higher = more important)
          - sub_steps: list[dict] (optional, HTN child tasks)
        """
        plan_id = str(uuid.uuid4())[:8]

        plan_steps = []
        for i, s in enumerate(steps[:MAX_STEPS]):
            step = PlanStep(
                index=i,
                description=s.get("description", f"Step {i}"),
                tool=s.get("tool", ""),
                params=s.get("params", {}),
                depends_on=s.get("depends_on", []),
                priority=s.get("priority", 0),
            )
            plan_steps.append(step)

        # v10: enrich steps with expected_outcome and conditions
        for i, s in enumerate(steps[:MAX_STEPS]):
            if i < len(plan_steps):
                plan_steps[i].expected_outcome = s.get("expected_outcome", "")
                plan_steps[i].conditions = s.get("conditions", [])

        # Auto-detect strategy from DAG if adaptive
        if strategy == ExecutionStrategy.ADAPTIVE:
            strategy = self._detect_strategy(plan_steps)

        plan = TaskPlan(
            plan_id=plan_id,
            goal=goal,
            steps=plan_steps,
            context=context or {},
            strategy=strategy,
        )

        self._plans[plan_id] = plan
        self._evict_old()

        log.info("Plan created: %s (%d steps, %s) — %s",
                 plan_id, len(plan_steps), strategy, goal[:60])
        return plan

    def decompose(self, plan_id: str, step_index: int,
                  sub_steps: list[dict]) -> bool:
        """HTN decomposition: split a composite step into sub-steps."""
        plan = self._plans.get(plan_id)
        if not plan or step_index >= len(plan.steps):
            return False

        parent = plan.steps[step_index]
        parent.is_composite = True

        base_index = len(plan.steps)
        child_indices = []
        for i, s in enumerate(sub_steps[:MAX_STEPS]):
            idx = base_index + i
            child = PlanStep(
                index=idx,
                description=s.get("description", f"Sub-step {i}"),
                tool=s.get("tool", ""),
                params=s.get("params", {}),
                depends_on=s.get("depends_on", []),
                priority=s.get("priority", parent.priority),
                parent_step=step_index,
            )
            # Remap depends_on relative to base_index
            child.depends_on = [
                d + base_index if d < len(sub_steps) else d
                for d in child.depends_on
            ]
            plan.steps.append(child)
            child_indices.append(idx)

        parent.sub_steps = child_indices
        log.info("Decomposed step %d into %d sub-steps (plan %s)",
                 step_index, len(child_indices), plan_id)
        return True

    def get_plan(self, plan_id: str) -> TaskPlan | None:
        return self._plans.get(plan_id)

    def list_plans(self) -> list[dict]:
        return [
            {"plan_id": p.plan_id, "goal": p.goal, "status": p.status,
             "steps": len(p.steps), "progress": p._progress()}
            for p in sorted(self._plans.values(), key=lambda x: x.created_at, reverse=True)
        ]

    def mark_step_running(self, plan_id: str, step_index: int) -> PlanStep | None:
        plan = self._plans.get(plan_id)
        if not plan or step_index >= len(plan.steps):
            return None

        step = plan.steps[step_index]

        # Check dependencies
        for dep_idx in step.depends_on:
            if dep_idx < len(plan.steps):
                dep = plan.steps[dep_idx]
                if dep.status != StepStatus.COMPLETED:
                    log.warning("Step %d depends on step %d which is %s",
                                step_index, dep_idx, dep.status)
                    return None

        step.status = StepStatus.RUNNING
        step.started_at = time.time()
        plan.update_status()
        return step

    def complete_step(self, plan_id: str, step_index: int,
                      result: dict | None = None, error: str | None = None) -> None:
        plan = self._plans.get(plan_id)
        if not plan or step_index >= len(plan.steps):
            return

        step = plan.steps[step_index]
        step.completed_at = time.time()

        if error:
            step.status = StepStatus.FAILED
            step.error = error
        else:
            step.status = StepStatus.COMPLETED
            step.result = result

        plan.update_status()
        log.info("Step %d %s (plan %s)", step_index, step.status, plan_id)

    def cancel_plan(self, plan_id: str) -> bool:
        plan = self._plans.get(plan_id)
        if not plan:
            return False

        plan.status = PlanStatus.CANCELLED
        for step in plan.steps:
            if step.status == StepStatus.PENDING:
                step.status = StepStatus.SKIPPED
        return True

    def get_next_step(self, plan_id: str) -> PlanStep | None:
        """Get the next executable step (all dependencies satisfied)."""
        plan = self._plans.get(plan_id)
        if not plan:
            return None

        for step in plan.steps:
            if step.status != StepStatus.PENDING:
                continue
            if step.is_composite:
                continue  # Skip composite nodes

            deps_ok = all(
                plan.steps[d].status == StepStatus.COMPLETED
                for d in step.depends_on
                if d < len(plan.steps)
            )
            if deps_ok:
                return step

        return None

    def get_next_executable(self, plan_id: str) -> list[PlanStep]:
        """Get ALL steps that can be executed in parallel (DAG-aware)."""
        plan = self._plans.get(plan_id)
        if not plan:
            return []

        executable = []
        for step in plan.steps:
            if step.status != StepStatus.PENDING:
                continue
            if step.is_composite:
                continue

            deps_ok = all(
                plan.steps[d].status == StepStatus.COMPLETED
                for d in step.depends_on
                if d < len(plan.steps)
            )
            if deps_ok:
                executable.append(step)

        # Sort by priority (descending)
        executable.sort(key=lambda s: s.priority, reverse=True)
        return executable

    def replan(self, plan_id: str, failed_step: int,
               strategy: str = "skip") -> bool:
        """Replan after a step failure.

        Strategies:
          - skip: skip the failed step and dependent steps
          - retry: reset step for retry (up to max_retries)
          - alternative: mark failed, allow dependents to proceed with partial data
        """
        plan = self._plans.get(plan_id)
        if not plan or failed_step >= len(plan.steps):
            return False

        step = plan.steps[failed_step]

        if strategy == "retry":
            if step.retries < step.max_retries:
                step.retries += 1
                step.status = StepStatus.PENDING
                step.error = None
                step.started_at = None
                step.completed_at = None
                log.info("Retry step %d (attempt %d/%d, plan %s)",
                         failed_step, step.retries, step.max_retries, plan_id)
            else:
                log.warning("Max retries for step %d (plan %s)", failed_step, plan_id)
                return False

        elif strategy == "skip":
            step.status = StepStatus.SKIPPED
            # Skip all steps that depend on this one
            self._cascade_skip(plan, failed_step)
            log.info("Skipped step %d and dependents (plan %s)", failed_step, plan_id)

        elif strategy == "alternative":
            # Mark as failed but allow dependents to run with partial data
            step.status = StepStatus.FAILED
            log.info("Step %d failed, dependents proceed with partial data (plan %s)",
                     failed_step, plan_id)

        plan.replanned = True
        plan.update_status()
        return True

    def _cascade_skip(self, plan: TaskPlan, step_index: int) -> None:
        """Recursively skip all steps that depend on a given step."""
        for step in plan.steps:
            if step_index in step.depends_on and step.status == StepStatus.PENDING:
                step.status = StepStatus.SKIPPED
                self._cascade_skip(plan, step.index)

    def _detect_strategy(self, steps: list[PlanStep]) -> str:
        """Auto-detect execution strategy from dependency graph."""
        has_deps = any(s.depends_on for s in steps)
        if not has_deps:
            return ExecutionStrategy.PARALLEL
        # Check if it's a simple chain (each step depends only on previous)
        is_chain = all(
            s.depends_on == [s.index - 1] or not s.depends_on
            for s in steps
        )
        if is_chain:
            return ExecutionStrategy.SEQUENTIAL
        return ExecutionStrategy.PARALLEL

    def refine(self, plan_id: str, optimizations: dict | None = None) -> bool:
        """v10: Affine un plan existant (reorder, remove redundant, add expected_outcomes)."""
        plan = self._plans.get(plan_id)
        if not plan or plan.status != PlanStatus.PENDING:
            return False

        if optimizations:
            # Update expected_outcomes
            outcomes = optimizations.get("expected_outcomes", {})
            for idx_str, outcome in outcomes.items():
                idx = int(idx_str)
                if idx < len(plan.steps):
                    plan.steps[idx].expected_outcome = outcome
            # Update priorities
            priorities = optimizations.get("priorities", {})
            for idx_str, prio in priorities.items():
                idx = int(idx_str)
                if idx < len(plan.steps):
                    plan.steps[idx].priority = prio

        log.info("Plan %s refined", plan_id)
        return True

    def _evict_old(self) -> None:
        if len(self._plans) <= MAX_PLANS:
            return
        # Remove oldest completed/cancelled plans
        candidates = sorted(
            [(pid, p) for pid, p in self._plans.items()
             if p.status in (PlanStatus.COMPLETED, PlanStatus.CANCELLED, PlanStatus.FAILED)],
            key=lambda x: x[1].created_at,
        )
        while len(self._plans) > MAX_PLANS and candidates:
            pid, _ = candidates.pop(0)
            del self._plans[pid]


# ─────────────────────────────────────────────────────
#  WebSocket Handler
# ─────────────────────────────────────────────────────

async def handle_client(ws, planner: TaskPlanner) -> None:
    log.info("Planner client connected")
    await ws.send(json.dumps({
        "type": "ready",
        "service": "task_planner",
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
                if action == "create_plan":
                    goal = params.get("goal", "")
                    steps = params.get("steps", [])
                    context = params.get("context", {})
                    strategy = params.get("strategy", ExecutionStrategy.SEQUENTIAL)
                    plan = planner.create_plan(goal, steps, context, strategy)
                    await ws.send(json.dumps({"ok": True, "data": plan.to_dict()}))

                elif action == "decompose":
                    plan_id = params.get("plan_id", "")
                    step_index = params.get("step_index", 0)
                    sub_steps = params.get("sub_steps", [])
                    ok = planner.decompose(plan_id, step_index, sub_steps)
                    if ok:
                        plan = planner.get_plan(plan_id)
                        await ws.send(json.dumps({
                            "ok": True,
                            "data": {"plan_id": plan_id, "decomposed": True,
                                     "plan": plan.to_dict() if plan else {}},
                        }))
                    else:
                        await ws.send(json.dumps({
                            "ok": False, "error": "Impossible de décomposer l'étape",
                        }))

                elif action == "get_plan":
                    plan = planner.get_plan(params.get("plan_id", ""))
                    if plan:
                        await ws.send(json.dumps({"ok": True, "data": plan.to_dict()}))
                    else:
                        await ws.send(json.dumps({"ok": False, "error": "Plan introuvable"}))

                elif action == "list_plans":
                    plans = planner.list_plans()
                    await ws.send(json.dumps({"ok": True, "data": {"plans": plans}}))

                elif action == "execute_step":
                    plan_id = params.get("plan_id", "")
                    step_index = params.get("step_index", 0)
                    step = planner.mark_step_running(plan_id, step_index)
                    if step:
                        await ws.send(json.dumps({
                            "ok": True,
                            "data": {
                                "plan_id": plan_id,
                                "step": step.to_dict(),
                                "message": f"Step {step_index} running: {step.description}",
                            },
                        }))
                    else:
                        await ws.send(json.dumps({
                            "ok": False,
                            "error": "Impossible d'exécuter l'étape (introuvable ou dépendances non satisfaites)",
                        }))

                elif action == "complete_step":
                    plan_id = params.get("plan_id", "")
                    step_index = params.get("step_index", 0)
                    result = params.get("result")
                    error = params.get("error")
                    planner.complete_step(plan_id, step_index, result, error)

                    plan = planner.get_plan(plan_id)
                    await ws.send(json.dumps({
                        "ok": True,
                        "data": plan.to_dict() if plan else {},
                    }))

                elif action == "next_step":
                    plan_id = params.get("plan_id", "")
                    step = planner.get_next_step(plan_id)
                    if step:
                        await ws.send(json.dumps({
                            "ok": True,
                            "data": {"step": step.to_dict(), "plan_id": plan_id},
                        }))
                    else:
                        await ws.send(json.dumps({
                            "ok": True,
                            "data": {"step": None, "plan_id": plan_id,
                                     "message": "Aucune étape exécutable restante"},
                        }))

                elif action == "next_executable":
                    plan_id = params.get("plan_id", "")
                    steps = planner.get_next_executable(plan_id)
                    await ws.send(json.dumps({
                        "ok": True,
                        "data": {
                            "steps": [s.to_dict() for s in steps],
                            "plan_id": plan_id,
                            "parallel": len(steps) > 1,
                            "count": len(steps),
                        },
                    }))

                elif action == "replan":
                    plan_id = params.get("plan_id", "")
                    failed_step = params.get("failed_step", 0)
                    strategy = params.get("strategy", "skip")
                    ok = planner.replan(plan_id, failed_step, strategy)
                    if ok:
                        plan = planner.get_plan(plan_id)
                        await ws.send(json.dumps({
                            "ok": True,
                            "data": {"plan_id": plan_id, "replanned": True,
                                     "plan": plan.to_dict() if plan else {}},
                        }))
                    else:
                        await ws.send(json.dumps({
                            "ok": False, "error": "Impossible de replanifier",
                        }))

                elif action == "cancel_plan":
                    ok = planner.cancel_plan(params.get("plan_id", ""))
                    await ws.send(json.dumps({"ok": ok}))

                elif action == "refine":
                    plan_id = params.get("plan_id", "")
                    optimizations = params.get("optimizations", {})
                    refined = planner.refine(plan_id, optimizations)
                    if refined:
                        await ws.send(json.dumps({"ok": True, "data": refined.to_dict()}))
                    else:
                        await ws.send(json.dumps({"ok": False, "error": "Plan introuvable"}))

                else:
                    await ws.send(json.dumps({
                        "ok": False,
                        "error": f"Unknown action: {action}",
                    }))

            except Exception as e:
                log.error("Planner operation error: %s", e, exc_info=True)
                await ws.send(json.dumps({"ok": False, "error": "Erreur interne du service planner"}))

    except Exception as e:
        log.error("Planner session error: %s", e)
    finally:
        log.info("Planner client disconnected")


# ─────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────

async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="EXO v10 Task Planner Server (HTN)")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    ensure_single_instance(args.port, "task_planner")
    _v9 = init_v9("task_planner", args.port)

    planner = TaskPlanner()
    log.info("TaskPlanner initialized")

    async def handler(ws):
        await handle_client(ws, planner)

    server = await websockets.serve(
        handler, args.host, args.port,
        ping_interval=None, ping_timeout=None,
    )
    log.info("Task Planner running on ws://%s:%d", args.host, args.port)

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        await server.wait_closed()
        log.info("Task Planner stopped")


if __name__ == "__main__":
    asyncio.run(main())
