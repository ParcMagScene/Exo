"""
EXO v20 — DistributedOrchestrator
Orchestration distribuée de modules cognitifs.
Distribution de tâches, équilibrage cognitif, tolérance aux pannes.

API:
  orchestrate(task: dict)        → dict
  distribute(subtasks: dict)     → dict
  collect(results: dict)         → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("distributed_orchestrator")


class DistributedOrchestrator:
    """Orchestrateur distribué EXO v20."""

    def __init__(self, governance=None, mcu=None):
        self._governance = governance
        self._mcu = mcu

        self._tasks: dict[str, dict] = {}
        self._distributions: list[dict] = []
        self._stats = {
            "orchestrated": 0,
            "distributed": 0,
            "collected": 0,
        }

    # ── orchestrate ─────────────────────────────────────────
    def orchestrate(self, task: dict) -> dict:
        """Orchestrer une tâche à travers les modules distribués."""
        self._stats["orchestrated"] += 1

        task_id = f"orch_{uuid.uuid4().hex[:8]}"
        name = task.get("name", "unnamed")
        priority = task.get("priority", "normal")
        modules = task.get("modules", [])

        entry = {
            "id": task_id,
            "name": name,
            "priority": priority,
            "modules": modules,
            "state": "orchestrated",
            "created_at": time.time(),
            "subtasks": [],
            "results": [],
        }
        self._tasks[task_id] = entry
        self._trim()

        # Auto-distribute to listed modules
        subtask_ids = []
        for mod in modules:
            sub_id = f"sub_{uuid.uuid4().hex[:8]}"
            entry["subtasks"].append({
                "id": sub_id,
                "module": mod,
                "state": "pending",
            })
            subtask_ids.append(sub_id)

        return {
            "id": task_id,
            "orchestrated": True,
            "name": name,
            "priority": priority,
            "subtasks_count": len(subtask_ids),
            "subtask_ids": subtask_ids,
            "timestamp": time.time(),
        }

    # ── distribute ──────────────────────────────────────────
    def distribute(self, subtasks: dict) -> dict:
        """Distribuer des sous-tâches aux modules."""
        self._stats["distributed"] += 1

        task_id = subtasks.get("task_id", "")
        targets = subtasks.get("targets", [])
        strategy = subtasks.get("strategy", "round_robin")

        dist_id = f"dist_{uuid.uuid4().hex[:8]}"
        assignments = []
        for i, target in enumerate(targets):
            assignments.append({
                "target": target,
                "assigned": True,
                "order": i,
            })

        dist = {
            "id": dist_id,
            "task_id": task_id,
            "strategy": strategy,
            "assignments": assignments,
            "timestamp": time.time(),
        }
        self._distributions.append(dist)

        return {
            "id": dist_id,
            "distributed": True,
            "task_id": task_id,
            "strategy": strategy,
            "assignments_count": len(assignments),
            "timestamp": time.time(),
        }

    # ── collect ─────────────────────────────────────────────
    def collect(self, results: dict) -> dict:
        """Collecter et agréger les résultats distribués."""
        self._stats["collected"] += 1

        task_id = results.get("task_id", "")
        partial = results.get("results", [])

        task = self._tasks.get(task_id)
        if task:
            task["results"].extend(partial)
            task["state"] = "collected"

        aggregated = {
            "total_results": len(partial),
            "successful": sum(1 for r in partial
                              if r.get("status") == "success"),
            "failed": sum(1 for r in partial
                          if r.get("status") == "failed"),
        }

        return {
            "id": f"col_{uuid.uuid4().hex[:8]}",
            "collected": True,
            "task_id": task_id,
            "aggregated": aggregated,
            "timestamp": time.time(),
        }

    def get_task(self, task_id: str) -> dict | None:
        return self._tasks.get(task_id)

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "distributed_orchestrator",
            "status": "ok",
            "total_tasks": len(self._tasks),
            "total_distributions": len(self._distributions),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._tasks.clear()
        self._distributions.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("DistributedOrchestrator restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._tasks) > 5000:
            oldest = sorted(self._tasks, key=lambda k: self._tasks[k]["created_at"])
            for k in oldest[:len(self._tasks) - 5000]:
                del self._tasks[k]
        if len(self._distributions) > 5000:
            self._distributions = self._distributions[-2500:]
