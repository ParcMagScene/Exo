"""
EXO v20 — ModularExplainabilityEngine
Explique les décisions de modules, swaps, partitions, orchestrations.

API:
  explain_module(module: dict)              → dict
  explain_swap(old: dict, new: dict)        → dict
  explain_partitioning()                    → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("modular_explainability_engine")


class ModularExplainabilityEngine:
    """Moteur d'explicabilité modulaire EXO v20."""

    def __init__(self, governance=None, mcu=None, orchestrator=None,
                 partitioning=None, hot_swap=None, lifecycle=None):
        self._governance = governance
        self._mcu = mcu
        self._orchestrator = orchestrator
        self._partitioning = partitioning
        self._hot_swap = hot_swap
        self._lifecycle = lifecycle

        self._explanations: list[dict] = []
        self._stats = {
            "module_explanations": 0,
            "swap_explanations": 0,
            "partition_explanations": 0,
        }

    # ── explain_module ──────────────────────────────────────
    def explain_module(self, module: dict) -> dict:
        """Expliquer l'état et les décisions d'un module."""
        self._stats["module_explanations"] += 1

        name = module.get("name", "unknown")
        module_id = module.get("module_id", "")
        state = module.get("state", "unknown")
        version = module.get("version", "")

        reasons = []
        if state == "active":
            reasons.append(f"Module '{name}' est actif et opérationnel.")
        elif state == "inactive":
            reasons.append(f"Module '{name}' est inactif — peut être réactivé.")
        elif state == "shutdown":
            reasons.append(f"Module '{name}' a été arrêté volontairement.")
        else:
            reasons.append(f"Module '{name}' est dans l'état '{state}'.")

        if version:
            reasons.append(f"Version courante : {version}.")

        explanation = {
            "id": f"exp_{uuid.uuid4().hex[:8]}",
            "type": "module",
            "module_name": name,
            "module_id": module_id,
            "state": state,
            "reasons": reasons,
            "timestamp": time.time(),
        }
        self._explanations.append(explanation)
        self._trim()

        return explanation

    # ── explain_swap ────────────────────────────────────────
    def explain_swap(self, old: dict, new: dict) -> dict:
        """Expliquer un swap de module."""
        self._stats["swap_explanations"] += 1

        old_name = old.get("name", "unknown")
        new_name = new.get("name", "unknown")
        old_version = old.get("version", "")
        new_version = new.get("version", "")
        reason = old.get("swap_reason", "upgrade")

        reasons = [
            f"Module '{old_name}' (v{old_version}) remplacé par "
            f"'{new_name}' (v{new_version}).",
        ]

        if reason == "upgrade":
            reasons.append(
                "Raison : mise à jour vers une version plus récente.")
        elif reason == "failure":
            reasons.append(
                "Raison : module défaillant remplacé par un module sain.")
        elif reason == "optimization":
            reasons.append(
                "Raison : remplacement par un module plus performant.")
        else:
            reasons.append(f"Raison : {reason}.")

        explanation = {
            "id": f"exp_{uuid.uuid4().hex[:8]}",
            "type": "swap",
            "old_name": old_name,
            "new_name": new_name,
            "old_version": old_version,
            "new_version": new_version,
            "swap_reason": reason,
            "reasons": reasons,
            "timestamp": time.time(),
        }
        self._explanations.append(explanation)

        return explanation

    # ── explain_partitioning ────────────────────────────────
    def explain_partitioning(self) -> dict:
        """Expliquer l'état du partitionnement cognitif."""
        self._stats["partition_explanations"] += 1

        partitions_info = []
        if self._partitioning:
            for p in self._partitioning.list_partitions():
                partitions_info.append({
                    "id": p["id"],
                    "name": p["name"],
                    "type": p["type"],
                    "modules_count": p["modules_count"],
                })

        reasons = []
        if partitions_info:
            reasons.append(
                f"{len(partitions_info)} partitions actives dans le système.")
            for p in partitions_info:
                reasons.append(
                    f"Partition '{p['name']}' ({p['type']}) : "
                    f"{p['modules_count']} modules.")
        else:
            reasons.append("Aucune partition active — système non partitionné.")

        explanation = {
            "id": f"exp_{uuid.uuid4().hex[:8]}",
            "type": "partitioning",
            "partitions": partitions_info,
            "total_partitions": len(partitions_info),
            "reasons": reasons,
            "timestamp": time.time(),
        }
        self._explanations.append(explanation)

        return explanation

    def list_explanations(self, limit: int = 50) -> list[dict]:
        return self._explanations[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "modular_explainability",
            "status": "ok",
            "total_explanations": len(self._explanations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._explanations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ModularExplainabilityEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._explanations) > 5000:
            self._explanations = self._explanations[-2500:]
