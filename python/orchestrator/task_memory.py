"""
EXO v10 — TaskMemory
Mémoire persistante des tâches exécutées par l'agent.

Stocke l'historique des tâches (état, résultats, erreurs, durée,
dépendances) et permet la recherche et l'analyse.

API:
  add_task(task)                     → str (task_id)
  update_task(task_id, updates)      → bool
  get_task(task_id)                  → dict | None
  list_tasks(limit, status_filter)   → list[dict]
  search_tasks(query)                → list[dict]
  get_stats()                        → dict
"""

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("task_memory")

# Persistence file
_FAISS_DIR = os.environ.get("EXO_FAISS_DIR") or r"D:\EXO\faiss\semantic_memory"
_TASK_MEMORY_FILE = os.path.join(_FAISS_DIR, "task_memory.json")


class TaskMemory:
    """Persistent memory of all tasks executed by the agent."""

    def __init__(self, persist_path: str = "") -> None:
        self._tasks: dict[str, dict] = {}
        self._persist_path = persist_path or _TASK_MEMORY_FILE
        self._load()

    def add_task(self, task: dict) -> str:
        """Add a new task to memory. Returns task_id."""
        task_id = task.get("task_id") or f"task_{uuid.uuid4().hex[:8]}"

        entry = {
            "task_id": task_id,
            "goal": task.get("goal", ""),
            "intent": task.get("intent", ""),
            "status": task.get("status", "pending"),
            "plan_id": task.get("plan_id", ""),
            "steps_total": task.get("steps_total", 0),
            "steps_completed": task.get("steps_completed", 0),
            "steps_failed": task.get("steps_failed", 0),
            "results": task.get("results", {}),
            "errors": task.get("errors", []),
            "created_at": time.time(),
            "updated_at": time.time(),
            "completed_at": None,
            "elapsed_s": 0.0,
            "dependencies": task.get("dependencies", []),
            "tags": task.get("tags", []),
        }

        self._tasks[task_id] = entry
        self._save()
        log.info("Task added: %s — %s", task_id, entry["goal"])
        return task_id

    def update_task(self, task_id: str, updates: dict) -> bool:
        """Update a task's fields."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        for key, value in updates.items():
            if key == "task_id":
                continue  # immutable
            task[key] = value

        task["updated_at"] = time.time()

        # Auto-set completed_at and elapsed_s
        if updates.get("status") in ("completed", "failed", "aborted"):
            task["completed_at"] = time.time()
            task["elapsed_s"] = round(task["completed_at"] - task["created_at"], 3)

        self._save()
        return True

    def get_task(self, task_id: str) -> dict | None:
        return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 20, status_filter: str = "") -> list[dict]:
        """List tasks, optionally filtered by status."""
        tasks = list(self._tasks.values())

        if status_filter:
            tasks = [t for t in tasks if t["status"] == status_filter]

        # Sort by creation time, most recent first
        tasks.sort(key=lambda t: t.get("created_at", 0), reverse=True)
        return tasks[:limit]

    def search_tasks(self, query: str) -> list[dict]:
        """Search tasks by keyword in goal/intent/tags."""
        query_lower = query.lower()
        results = []
        for task in self._tasks.values():
            searchable = " ".join([
                task.get("goal", ""),
                task.get("intent", ""),
                " ".join(task.get("tags", [])),
            ]).lower()
            if query_lower in searchable:
                results.append(task)
        return results

    def get_stats(self) -> dict:
        """Get task memory statistics."""
        tasks = list(self._tasks.values())
        total = len(tasks)
        by_status: dict[str, int] = {}
        latencies: list[float] = []

        for t in tasks:
            status = t.get("status", "unknown")
            by_status[status] = by_status.get(status, 0) + 1
            if t.get("elapsed_s", 0) > 0:
                latencies.append(t["elapsed_s"])

        return {
            "total_tasks": total,
            "by_status": by_status,
            "avg_elapsed_s": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
            "total_elapsed_s": round(sum(latencies), 3),
        }

    def clear_old(self, max_age_s: float = 86400 * 7) -> int:
        """Remove tasks older than max_age_s. Returns count removed."""
        cutoff = time.time() - max_age_s
        to_remove = [
            tid for tid, t in self._tasks.items()
            if t.get("completed_at") and t["completed_at"] < cutoff
        ]
        for tid in to_remove:
            del self._tasks[tid]
        if to_remove:
            self._save()
        return len(to_remove)

    # ── Persistence ──────────────────────────────────

    def _save(self) -> None:
        if not self._persist_path:
            return
        try:
            path = Path(self._persist_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._tasks, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        except Exception as e:
            log.error("Failed to save task memory: %s", e)

    def _load(self) -> None:
        if not self._persist_path:
            return
        path = Path(self._persist_path)
        if path.exists():
            try:
                self._tasks = json.loads(path.read_text(encoding="utf-8"))
                log.info("Loaded %d tasks from %s", len(self._tasks), path)
            except Exception as e:
                log.error("Failed to load task memory: %s", e)
                self._tasks = {}
