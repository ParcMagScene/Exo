"""
EXO v20 — ModuleLifecycleManager
Gestion complète du cycle de vie des modules :
install, init, activate, deactivate, update, remove.

API:
  install_module(module: dict)  → dict
  update_module(module: dict)   → dict
  remove_module(module: dict)   → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("module_lifecycle_manager")

_VALID_STATES = ("installed", "initialized", "active", "inactive",
                 "updating", "removed")


class ModuleLifecycleManager:
    """Gestionnaire de cycle de vie des modules EXO v20."""

    def __init__(self, governance=None, mcu=None, compatibility_checker=None):
        self._governance = governance
        self._mcu = mcu
        self._checker = compatibility_checker

        self._modules: dict[str, dict] = {}
        self._history: list[dict] = []
        self._stats = {
            "installed": 0,
            "updated": 0,
            "removed": 0,
        }

    # ── install_module ──────────────────────────────────────
    def install_module(self, module: dict) -> dict:
        """Installer et initialiser un module."""
        self._stats["installed"] += 1

        name = module.get("name", "unnamed")
        version = module.get("version", "1.0.0")
        mod_type = module.get("type", "generic")
        config = module.get("config", {})

        uid = f"mod_{uuid.uuid4().hex[:8]}"
        entry = {
            "id": uid,
            "name": name,
            "version": version,
            "type": mod_type,
            "config": config,
            "state": "installed",
            "installed_at": time.time(),
            "updated_at": None,
        }
        self._modules[uid] = entry
        self._history.append({
            "action": "install",
            "module_id": uid,
            "name": name,
            "version": version,
            "timestamp": time.time(),
        })
        self._trim()

        # Auto-activate
        entry["state"] = "active"

        return {
            "id": uid,
            "installed": True,
            "name": name,
            "version": version,
            "state": "active",
            "timestamp": time.time(),
        }

    # ── update_module ───────────────────────────────────────
    def update_module(self, module: dict) -> dict:
        """Mettre à jour un module existant."""
        self._stats["updated"] += 1

        module_id = module.get("module_id", "")
        new_version = module.get("version", "")
        new_config = module.get("config")

        entry = self._modules.get(module_id)
        if not entry:
            return {
                "updated": False,
                "error": "module_not_found",
                "module_id": module_id,
                "timestamp": time.time(),
            }

        old_version = entry["version"]
        entry["state"] = "updating"
        entry["version"] = new_version or entry["version"]
        if new_config is not None:
            entry["config"] = new_config
        entry["updated_at"] = time.time()
        entry["state"] = "active"

        self._history.append({
            "action": "update",
            "module_id": module_id,
            "old_version": old_version,
            "new_version": entry["version"],
            "timestamp": time.time(),
        })

        return {
            "updated": True,
            "module_id": module_id,
            "name": entry["name"],
            "old_version": old_version,
            "new_version": entry["version"],
            "state": "active",
            "timestamp": time.time(),
        }

    # ── remove_module ───────────────────────────────────────
    def remove_module(self, module: dict) -> dict:
        """Retirer un module du système."""
        self._stats["removed"] += 1

        module_id = module.get("module_id", "")

        entry = self._modules.get(module_id)
        if not entry:
            return {
                "removed": False,
                "error": "module_not_found",
                "module_id": module_id,
                "timestamp": time.time(),
            }

        name = entry["name"]
        del self._modules[module_id]

        self._history.append({
            "action": "remove",
            "module_id": module_id,
            "name": name,
            "timestamp": time.time(),
        })

        return {
            "removed": True,
            "module_id": module_id,
            "name": name,
            "timestamp": time.time(),
        }

    def get_module(self, module_id: str) -> dict | None:
        return self._modules.get(module_id)

    def list_modules(self) -> list[dict]:
        return [
            {"id": uid, "name": m["name"], "version": m["version"],
             "state": m["state"]}
            for uid, m in self._modules.items()
        ]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "module_lifecycle_manager",
            "status": "ok",
            "total_modules": len(self._modules),
            "active": sum(1 for m in self._modules.values()
                          if m["state"] == "active"),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._modules.clear()
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ModuleLifecycleManager restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-2500:]
