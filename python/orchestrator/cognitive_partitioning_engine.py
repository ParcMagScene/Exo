"""
EXO v20 — CognitivePartitioningEngine
Partitionnement de la cognition pour la scalabilité.
Partition par domaine, tâche, agent, couche; partitionnement dynamique.

API:
  partition_cognition(criteria: dict)       → dict
  reassign_partition(module: dict)          → dict
  merge_partitions()                        → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("cognitive_partitioning_engine")


class CognitivePartitioningEngine:
    """Moteur de partitionnement cognitif EXO v20."""

    def __init__(self, governance=None, mcu=None, fabric=None):
        self._governance = governance
        self._mcu = mcu
        self._fabric = fabric

        self._partitions: dict[str, dict] = {}
        self._stats = {
            "partitions_created": 0,
            "reassignments": 0,
            "merges": 0,
        }

    # ── partition_cognition ─────────────────────────────────
    def partition_cognition(self, criteria: dict) -> dict:
        """Créer une partition cognitive selon les critères donnés."""
        self._stats["partitions_created"] += 1

        partition_type = criteria.get("type", "domain")
        name = criteria.get("name", "default")
        modules = criteria.get("modules", [])
        strategy = criteria.get("strategy", "balanced")

        pid = f"part_{uuid.uuid4().hex[:8]}"
        partition = {
            "id": pid,
            "name": name,
            "type": partition_type,
            "strategy": strategy,
            "modules": modules,
            "state": "active",
            "created_at": time.time(),
            "load": 0.0,
        }
        self._partitions[pid] = partition
        self._trim()

        return {
            "id": pid,
            "partitioned": True,
            "name": name,
            "type": partition_type,
            "strategy": strategy,
            "modules_count": len(modules),
            "timestamp": time.time(),
        }

    # ── reassign_partition ──────────────────────────────────
    def reassign_partition(self, module: dict) -> dict:
        """Réassigner un module à une partition différente."""
        self._stats["reassignments"] += 1

        module_id = module.get("module_id", "")
        source_partition = module.get("source_partition", "")
        target_partition = module.get("target_partition", "")

        src = self._partitions.get(source_partition)
        tgt = self._partitions.get(target_partition)

        if not src or not tgt:
            return {
                "reassigned": False,
                "error": "partition_not_found",
                "module_id": module_id,
                "timestamp": time.time(),
            }

        # Move module between partitions
        if module_id in src["modules"]:
            src["modules"].remove(module_id)
        tgt["modules"].append(module_id)

        return {
            "reassigned": True,
            "module_id": module_id,
            "source": source_partition,
            "target": target_partition,
            "timestamp": time.time(),
        }

    # ── merge_partitions ────────────────────────────────────
    def merge_partitions(self, partition_ids: list[str] | None = None) -> dict:
        """Fusionner des partitions ou toutes les partitions."""
        self._stats["merges"] += 1

        if partition_ids is None:
            partition_ids = list(self._partitions.keys())

        if len(partition_ids) < 2:
            return {
                "merged": False,
                "error": "need_at_least_2_partitions",
                "timestamp": time.time(),
            }

        # Merge into first partition
        target_id = partition_ids[0]
        target = self._partitions.get(target_id)
        if not target:
            return {
                "merged": False,
                "error": "target_partition_not_found",
                "timestamp": time.time(),
            }

        merged_modules = list(target["modules"])
        removed = []
        for pid in partition_ids[1:]:
            p = self._partitions.get(pid)
            if p:
                merged_modules.extend(p["modules"])
                removed.append(pid)
                del self._partitions[pid]

        target["modules"] = merged_modules

        return {
            "merged": True,
            "target_partition": target_id,
            "merged_partitions": removed,
            "total_modules": len(merged_modules),
            "timestamp": time.time(),
        }

    def list_partitions(self) -> list[dict]:
        return [
            {"id": pid, "name": p["name"], "type": p["type"],
             "modules_count": len(p["modules"]), "state": p["state"]}
            for pid, p in self._partitions.items()
        ]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "cognitive_partitioning",
            "status": "ok",
            "total_partitions": len(self._partitions),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._partitions.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("CognitivePartitioningEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._partitions) > 5000:
            oldest = sorted(self._partitions,
                            key=lambda k: self._partitions[k]["created_at"])
            for k in oldest[:len(self._partitions) - 5000]:
                del self._partitions[k]
