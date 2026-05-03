"""
EXO v14 — AgentRegistry (Gestion des agents)
Enregistre, versionne, vérifie la compatibilité et gère le cycle de vie
de tous les agents spécialisés du système.

API:
  register_agent(agent)             → bool
  unregister_agent(name)            → bool
  get_agent(name)                   → SpecializedAgent | None
  list_agents()                     → list[dict]
  get_agent_info(name)              → dict
  health_check()                    → dict
  restart()                         → None
  get_stats()                       → dict
"""

import logging
import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from specialized_agents import SpecializedAgent

log = logging.getLogger("agent_registry")


class AgentRegistry:
    """Registre central des agents spécialisés EXO v14."""

    def __init__(self, messaging_bus=None):
        self._agents: dict[str, "SpecializedAgent"] = {}
        self._bus = messaging_bus
        self._history: list[dict] = []
        self._stats = {
            "agents_registered": 0,
            "agents_unregistered": 0,
            "agents_active": 0,
        }

    # ── register ────────────────────────────────────────────
    def register_agent(self, agent: "SpecializedAgent") -> bool:
        """Register a specialized agent."""
        name = getattr(agent, "name", "")
        if not name:
            log.warning("Cannot register agent without a name")
            return False

        if name in self._agents:
            log.warning("Agent '%s' already registered — replacing", name)

        self._agents[name] = agent
        self._stats["agents_registered"] += 1
        self._stats["agents_active"] = len(self._agents)

        # Register on messaging bus if available
        if self._bus:
            self._bus.register_channel(name)

        self._history.append({
            "event": "register",
            "agent": name,
            "domain": getattr(agent, "domain", ""),
            "version": getattr(agent, "version", "1.0"),
            "timestamp": time.time(),
        })

        log.info("Agent registered: %s (domain=%s, v%s)",
                 name, getattr(agent, "domain", "?"),
                 getattr(agent, "version", "1.0"))
        return True

    # ── unregister ──────────────────────────────────────────
    def unregister_agent(self, name: str) -> bool:
        """Unregister an agent by name."""
        if name not in self._agents:
            return False

        del self._agents[name]
        self._stats["agents_unregistered"] += 1
        self._stats["agents_active"] = len(self._agents)

        if self._bus:
            self._bus.unregister_channel(name)

        self._history.append({
            "event": "unregister",
            "agent": name,
            "timestamp": time.time(),
        })

        log.info("Agent unregistered: %s", name)
        return True

    # ── get / list ──────────────────────────────────────────
    def get_agent(self, name: str) -> "SpecializedAgent | None":
        """Get a registered agent by name."""
        return self._agents.get(name)

    def list_agents(self) -> list[dict]:
        """List all registered agents with their metadata."""
        result = []
        for name, agent in self._agents.items():
            result.append({
                "name": name,
                "domain": getattr(agent, "domain", ""),
                "version": getattr(agent, "version", "1.0"),
                "status": "active",
            })
        return result

    def get_agent_info(self, name: str) -> dict:
        """Get detailed info about a specific agent."""
        agent = self._agents.get(name)
        if not agent:
            return {"found": False, "name": name}
        return {
            "found": True,
            "name": name,
            "domain": getattr(agent, "domain", ""),
            "version": getattr(agent, "version", "1.0"),
            "capabilities": getattr(agent, "capabilities", []),
            "status": "active",
        }

    def get_agents_for_domain(self, domain: str) -> list["SpecializedAgent"]:
        """Get all agents matching a domain."""
        return [a for a in self._agents.values()
                if getattr(a, "domain", "") == domain]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        agent_health = {}
        for name, agent in self._agents.items():
            if hasattr(agent, "health_check"):
                agent_health[name] = agent.health_check()
            else:
                agent_health[name] = {"status": "unknown"}
        return {
            "service": "agent_registry",
            "status": "ok",
            "agents": len(self._agents),
            "agent_health": agent_health,
        }

    def restart(self) -> None:
        for k in self._stats:
            self._stats[k] = 0
        self._stats["agents_active"] = len(self._agents)
        self._history.clear()
        log.info("AgentRegistry restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
