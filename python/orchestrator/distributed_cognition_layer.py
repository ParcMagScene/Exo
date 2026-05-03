"""
EXO v15 — DistributedCognitionLayer (Cognition distribuée unifiée)
Couche qui unifie les agents distribués de v14 dans un cadre cognitif
cohérent avec coordination, consensus et partage de connaissances.

API:
  dispatch(task)                → dict
  coordinate(agents, goal)      → dict
  consensus(agents, question)   → dict
  share_knowledge(source, target, knowledge) → dict
  get_agent_status(agent)       → dict
  get_all_agents()              → list[dict]
  health_check()                → dict
  restart()                     → None
  get_stats()                   → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("distributed_cognition")


class DistributedCognitionLayer:
    """Cognition distribuée unifiée EXO v15."""

    AGENT_DOMAINS = [
        "domotique", "reseau", "preferences", "routines", "scenarios",
        "contexte", "securite", "diagnostic", "apprentissage",
        "optimisation", "planification", "communication", "supervision",
    ]

    def __init__(self, meta_memory=None, governance=None,
                 agent_manager=None):
        self._memory = meta_memory
        self._governance = governance
        self._agent_mgr = agent_manager
        self._agents: dict[str, dict] = {}
        self._dispatch_log: list[dict] = []
        self._stats = {
            "dispatches": 0,
            "coordinations": 0,
            "consensus_rounds": 0,
            "knowledge_shares": 0,
        }
        self._init_agents()

    def _init_agents(self) -> None:
        for domain in self.AGENT_DOMAINS:
            self._agents[domain] = {
                "name": domain,
                "status": "active",
                "load": 0.0,
                "tasks_completed": 0,
                "last_active": time.time(),
            }

    # ── dispatch ────────────────────────────────────────────
    def dispatch(self, task: dict) -> dict:
        """Dispatcher une tâche vers l'agent le plus adapté."""
        self._stats["dispatches"] += 1
        disp_id = f"disp_{uuid.uuid4().hex[:8]}"

        domain = task.get("domain", "general")
        action = task.get("action", "process")

        # Find best agent
        target_agent = None
        if domain in self._agents:
            target_agent = domain
        else:
            # Least loaded agent
            active = [
                (name, a) for name, a in self._agents.items()
                if a["status"] == "active"
            ]
            if active:
                target_agent = min(active, key=lambda x: x[1]["load"])[0]

        if not target_agent:
            return {"id": disp_id, "status": "no_agent_available",
                    "timestamp": time.time()}

        # Simulate dispatch
        agent = self._agents[target_agent]
        agent["load"] = min(agent["load"] + 0.1, 1.0)
        agent["tasks_completed"] += 1
        agent["last_active"] = time.time()

        result = {
            "id": disp_id,
            "agent": target_agent,
            "action": action,
            "status": "dispatched",
            "result": f"completed_{action}",
            "timestamp": time.time(),
        }
        self._dispatch_log.append(result)
        return result

    # ── coordinate ──────────────────────────────────────────
    def coordinate(self, agents: list[str], goal: str) -> dict:
        """Coordonner plusieurs agents vers un objectif commun."""
        self._stats["coordinations"] += 1
        coord_id = f"coord_{uuid.uuid4().hex[:8]}"

        participants = []
        for name in agents:
            if name in self._agents:
                self._agents[name]["last_active"] = time.time()
                participants.append({
                    "agent": name,
                    "status": "participating",
                    "contribution": f"contrib_{name}",
                })

        coordination = {
            "id": coord_id,
            "goal": goal,
            "participants": participants,
            "status": "coordinated" if participants else "no_participants",
            "agents_count": len(participants),
            "timestamp": time.time(),
        }
        return coordination

    # ── consensus ───────────────────────────────────────────
    def consensus(self, agents: list[str], question: str) -> dict:
        """Atteindre un consensus entre agents."""
        self._stats["consensus_rounds"] += 1
        cons_id = f"cons_{uuid.uuid4().hex[:8]}"

        votes: dict[str, str] = {}
        for name in agents:
            if name in self._agents:
                votes[name] = f"agree_{question[:10]}"

        # Simple majority
        if votes:
            vote_counts: dict[str, int] = {}
            for v in votes.values():
                vote_counts[v] = vote_counts.get(v, 0) + 1
            winner = max(vote_counts, key=lambda k: vote_counts[k])
            agreement = vote_counts[winner] / len(votes)
        else:
            winner = "no_vote"
            agreement = 0.0

        result = {
            "id": cons_id,
            "question": question,
            "votes": votes,
            "consensus": winner,
            "agreement_ratio": round(agreement, 3),
            "reached": agreement > 0.5,
            "timestamp": time.time(),
        }
        return result

    # ── share_knowledge ─────────────────────────────────────
    def share_knowledge(self, source: str, target: str,
                        knowledge: dict) -> dict:
        """Partager des connaissances entre agents."""
        self._stats["knowledge_shares"] += 1
        share_id = f"share_{uuid.uuid4().hex[:8]}"

        if source not in self._agents or target not in self._agents:
            return {"id": share_id, "status": "agent_not_found",
                    "timestamp": time.time()}

        self._agents[source]["last_active"] = time.time()
        self._agents[target]["last_active"] = time.time()

        return {
            "id": share_id,
            "source": source,
            "target": target,
            "knowledge_type": knowledge.get("type", "fact"),
            "status": "shared",
            "timestamp": time.time(),
        }

    # ── get_agent_status ────────────────────────────────────
    def get_agent_status(self, agent: str) -> dict:
        return self._agents.get(agent, {"name": agent, "status": "unknown"})

    # ── get_all_agents ──────────────────────────────────────
    def get_all_agents(self) -> list[dict]:
        return list(self._agents.values())

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        active = sum(1 for a in self._agents.values()
                     if a["status"] == "active")
        return {
            "service": "distributed_cognition",
            "status": "ok",
            "agents_total": len(self._agents),
            "agents_active": active,
        }

    def restart(self) -> None:
        self._dispatch_log.clear()
        self._init_agents()
        for k in self._stats:
            self._stats[k] = 0
        log.info("DistributedCognitionLayer restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
