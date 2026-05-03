"""
EXO v20 — ModularCognitiveUnit (MCU)
Unité cognitive modulaire de base : indépendante, interchangeable,
versionnée, isolée, supervisée et compatible.

API:
  mcu_init()               → dict
  mcu_execute(input: dict)  → dict
  mcu_report()             → dict
  mcu_shutdown()           → dict
  health_check()           → dict
  restart()                → None
  get_stats()              → dict
"""

import logging
import time
import uuid

log = logging.getLogger("modular_cognitive_unit")

_DEFAULT_VERSION = "1.0.0"


class ModularCognitiveUnit:
    """Unité cognitive modulaire EXO v20."""

    def __init__(self, governance=None, meta_memory=None):
        self._governance = governance
        self._memory = meta_memory

        self._units: dict[str, dict] = {}
        self._stats = {
            "units_created": 0,
            "executions": 0,
            "shutdowns": 0,
        }

    # ── mcu_init ────────────────────────────────────────────
    def mcu_init(self, *, name: str = "default",
                 version: str = _DEFAULT_VERSION,
                 capabilities: list[str] | None = None,
                 config: dict | None = None) -> dict:
        """Initialiser une nouvelle unité cognitive modulaire."""
        self._stats["units_created"] += 1

        uid = f"mcu_{uuid.uuid4().hex[:8]}"
        unit = {
            "id": uid,
            "name": name,
            "version": version,
            "capabilities": capabilities or [],
            "config": config or {},
            "state": "initialized",
            "created_at": time.time(),
            "executions": 0,
            "errors": 0,
        }
        self._units[uid] = unit
        self._trim()

        return {
            "id": uid,
            "initialized": True,
            "name": name,
            "version": version,
            "state": "initialized",
            "timestamp": time.time(),
        }

    # ── mcu_execute ─────────────────────────────────────────
    def mcu_execute(self, input_data: dict) -> dict:
        """Exécuter une tâche sur une unité cognitive."""
        self._stats["executions"] += 1

        unit_id = input_data.get("unit_id", "")
        task = input_data.get("task", "")
        payload = input_data.get("payload", {})

        unit = self._units.get(unit_id)
        if not unit:
            return {
                "executed": False,
                "error": "unit_not_found",
                "unit_id": unit_id,
                "timestamp": time.time(),
            }

        if unit["state"] != "initialized" and unit["state"] != "active":
            return {
                "executed": False,
                "error": "unit_not_active",
                "unit_id": unit_id,
                "state": unit["state"],
                "timestamp": time.time(),
            }

        unit["state"] = "active"
        unit["executions"] += 1

        return {
            "id": f"exec_{uuid.uuid4().hex[:8]}",
            "executed": True,
            "unit_id": unit_id,
            "unit_name": unit["name"],
            "task": task,
            "result": {
                "status": "completed",
                "output": f"Task '{task}' executed by MCU '{unit['name']}'",
            },
            "timestamp": time.time(),
        }

    # ── mcu_report ──────────────────────────────────────────
    def mcu_report(self) -> dict:
        """Générer un rapport sur toutes les unités cognitives."""
        units_report = []
        for uid, unit in self._units.items():
            units_report.append({
                "id": uid,
                "name": unit["name"],
                "version": unit["version"],
                "state": unit["state"],
                "executions": unit["executions"],
                "errors": unit["errors"],
                "capabilities": unit["capabilities"],
            })

        return {
            "id": f"rpt_{uuid.uuid4().hex[:8]}",
            "reported": True,
            "units": units_report,
            "total_units": len(units_report),
            "active": sum(1 for u in units_report if u["state"] == "active"),
            "timestamp": time.time(),
        }

    # ── mcu_shutdown ────────────────────────────────────────
    def mcu_shutdown(self, unit_id: str = "") -> dict:
        """Arrêter une unité cognitive."""
        self._stats["shutdowns"] += 1

        if unit_id and unit_id in self._units:
            self._units[unit_id]["state"] = "shutdown"
            return {
                "shutdown": True,
                "unit_id": unit_id,
                "timestamp": time.time(),
            }

        if not unit_id:
            # Shutdown all
            count = 0
            for u in self._units.values():
                if u["state"] != "shutdown":
                    u["state"] = "shutdown"
                    count += 1
            return {
                "shutdown": True,
                "units_shutdown": count,
                "timestamp": time.time(),
            }

        return {
            "shutdown": False,
            "error": "unit_not_found",
            "unit_id": unit_id,
            "timestamp": time.time(),
        }

    # ── get_unit / list_units ───────────────────────────────
    def get_unit(self, unit_id: str) -> dict | None:
        return self._units.get(unit_id)

    def list_units(self) -> list[dict]:
        return [
            {"id": uid, "name": u["name"], "version": u["version"],
             "state": u["state"], "executions": u["executions"]}
            for uid, u in self._units.items()
        ]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "modular_cognitive_unit",
            "status": "ok",
            "total_units": len(self._units),
            "active": sum(1 for u in self._units.values()
                          if u["state"] == "active"),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._units.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ModularCognitiveUnit restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._units) > 5000:
            # Remove oldest shutdown units first
            shutdown = [uid for uid, u in self._units.items()
                        if u["state"] == "shutdown"]
            for uid in shutdown[:len(self._units) - 5000]:
                del self._units[uid]
