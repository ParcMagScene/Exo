"""
EXO v20 — PlugAndPlayAgentSystem
Ajout, retrait et remplacement dynamiques d'agents sans redémarrage.
Compatibilité ascendante et descendante garantie.

API:
  register_agent(agent: dict)                → dict
  unregister_agent(agent: dict)              → dict
  replace_agent(old: dict, new: dict)        → dict
  list_agents()                              → list[dict]
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("plug_and_play_agent_system")


class PlugAndPlayAgentSystem:
    """Système d'agents plug-and-play EXO v20."""

    def __init__(self, governance=None, agent_registry=None):
        self._governance = governance
        self._registry = agent_registry

        self._agents: dict[str, dict] = {}
        self._history: list[dict] = []
        self._stats = {
            "registered": 0,
            "unregistered": 0,
            "replaced": 0,
        }

    # ── register ────────────────────────────────────────────
    def register_agent(self, agent: dict) -> dict:
        """Enregistrer dynamiquement un nouvel agent."""
        self._stats["registered"] += 1

        name = agent.get("name", "unnamed")
        version = agent.get("version", "1.0.0")
        capabilities = agent.get("capabilities", [])
        uid = f"pnp_{uuid.uuid4().hex[:8]}"

        entry = {
            "id": uid,
            "name": name,
            "version": version,
            "capabilities": capabilities,
            "state": "active",
            "registered_at": time.time(),
        }
        self._agents[uid] = entry
        self._history.append({
            "action": "register",
            "agent_id": uid,
            "name": name,
            "timestamp": time.time(),
        })
        self._trim()

        return {
            "id": uid,
            "registered": True,
            "name": name,
            "version": version,
            "timestamp": time.time(),
        }

    # ── unregister ──────────────────────────────────────────
    def unregister_agent(self, agent: dict) -> dict:
        """Retirer un agent du système."""
        self._stats["unregistered"] += 1

        agent_id = agent.get("agent_id", "")
        if agent_id not in self._agents:
            return {
                "unregistered": False,
                "error": "agent_not_found",
                "agent_id": agent_id,
                "timestamp": time.time(),
            }

        removed = self._agents.pop(agent_id)
        self._history.append({
            "action": "unregister",
            "agent_id": agent_id,
            "name": removed["name"],
            "timestamp": time.time(),
        })

        return {
            "unregistered": True,
            "agent_id": agent_id,
            "name": removed["name"],
            "timestamp": time.time(),
        }

    # ── replace ─────────────────────────────────────────────
    def replace_agent(self, old: dict, new: dict) -> dict:
        """Remplacer un agent par un autre sans interruption."""
        self._stats["replaced"] += 1

        old_id = old.get("agent_id", "")
        if old_id not in self._agents:
            return {
                "replaced": False,
                "error": "old_agent_not_found",
                "old_id": old_id,
                "timestamp": time.time(),
            }

        old_entry = self._agents.pop(old_id)
        new_name = new.get("name", old_entry["name"])
        new_version = new.get("version", "1.0.0")
        new_caps = new.get("capabilities", old_entry["capabilities"])

        new_uid = f"pnp_{uuid.uuid4().hex[:8]}"
        new_entry = {
            "id": new_uid,
            "name": new_name,
            "version": new_version,
            "capabilities": new_caps,
            "state": "active",
            "registered_at": time.time(),
            "replaces": old_id,
        }
        self._agents[new_uid] = new_entry
        self._history.append({
            "action": "replace",
            "old_id": old_id,
            "new_id": new_uid,
            "old_name": old_entry["name"],
            "new_name": new_name,
            "timestamp": time.time(),
        })

        return {
            "replaced": True,
            "old_id": old_id,
            "new_id": new_uid,
            "old_name": old_entry["name"],
            "new_name": new_name,
            "new_version": new_version,
            "timestamp": time.time(),
        }

    # ── list ────────────────────────────────────────────────
    def list_agents(self) -> list[dict]:
        return [
            {"id": uid, "name": a["name"], "version": a["version"],
             "state": a["state"]}
            for uid, a in self._agents.items()
        ]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "plug_and_play_agent_system",
            "status": "ok",
            "total_agents": len(self._agents),
            "active": sum(1 for a in self._agents.values()
                          if a["state"] == "active"),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._agents.clear()
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("PlugAndPlayAgentSystem restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-2500:]
