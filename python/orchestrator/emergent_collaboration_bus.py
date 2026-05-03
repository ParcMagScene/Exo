"""
EXO v16 — EmergentCollaborationBus (Bus de collaboration émergente)
Communication inter-agents orientée collaboration et émergence.
Étend AgentMessagingBus avec protocoles de collaboration,
observations partagées et requêtes de support.

API:
  collaborate(initiator, participants, goal)  → dict
  share_observation(agent, observation)       → dict
  request_support(agent, request)             → dict
  get_collaboration_status(collab_id)         → dict
  complete_collaboration(collab_id, result)   → dict
  get_shared_observations(domain, limit)      → list[dict]
  health_check()                              → dict
  restart()                                   → None
  get_stats()                                 → dict
"""

import logging
import time
import uuid
from collections import defaultdict
from typing import Any

log = logging.getLogger("emergent_collaboration_bus")

# Types de collaboration
COLLAB_TYPES = frozenset({
    "problem_solving", "knowledge_sharing", "consensus",
    "optimization", "exploration", "diagnosis",
})

COLLAB_STATUS = {"active", "completed", "failed", "cancelled"}


class EmergentCollaborationBus:
    """Bus de collaboration émergente EXO v16."""

    def __init__(self, audit_log=None, messaging_bus=None, meta_memory=None):
        self._audit = audit_log
        self._msg_bus = messaging_bus
        self._memory = meta_memory
        self._collaborations: dict[str, dict] = {}
        self._observations: list[dict] = []
        self._support_requests: list[dict] = []
        self._agent_contributions: dict[str, list[dict]] = defaultdict(list)
        self._stats = {
            "collaborations_started": 0,
            "collaborations_completed": 0,
            "collaborations_failed": 0,
            "observations_shared": 0,
            "support_requests": 0,
            "support_fulfilled": 0,
            "agents_active": 0,
        }

    # ── collaborate ─────────────────────────────────────────
    def collaborate(self, initiator: str, participants: list[str],
                    goal: dict) -> dict:
        """Démarrer une collaboration entre agents."""
        self._stats["collaborations_started"] += 1
        collab_id = f"collab_{uuid.uuid4().hex[:10]}"

        collab_type = goal.get("type", "problem_solving")
        if collab_type not in COLLAB_TYPES:
            collab_type = "problem_solving"

        collaboration = {
            "id": collab_id,
            "initiator": initiator,
            "participants": participants,
            "all_agents": [initiator] + [p for p in participants
                                          if p != initiator],
            "goal": goal,
            "type": collab_type,
            "status": "active",
            "contributions": [],
            "started_at": time.time(),
            "result": None,
        }

        self._collaborations[collab_id] = collaboration

        # Track active agents
        all_agents = set(collaboration["all_agents"])
        self._stats["agents_active"] = len(all_agents)

        # Notify participants via messaging bus
        if self._msg_bus:
            for p in participants:
                self._msg_bus.send(initiator, p, {
                    "type": "task_request",
                    "payload": {
                        "collaboration_id": collab_id,
                        "goal": goal,
                        "role": "participant",
                    },
                })

        if self._audit:
            self._audit.log_governance({
                "type": "governance_decision",
                "governor": "collaboration_bus",
                "decision": "collaboration_started",
                "scope": collab_type,
                "impact": "medium",
            })

        log.info("Collaboration %s started: %s → %s (%s)",
                 collab_id, initiator, participants, collab_type)

        return {
            "id": collab_id,
            "status": "active",
            "initiator": initiator,
            "participants": participants,
            "type": collab_type,
            "goal": goal.get("description", str(goal)),
        }

    # ── share_observation ───────────────────────────────────
    def share_observation(self, agent: str,
                          observation: dict) -> dict:
        """Partager une observation entre agents."""
        self._stats["observations_shared"] += 1
        obs_id = f"obs_{uuid.uuid4().hex[:10]}"

        obs = {
            "id": obs_id,
            "agent": agent,
            "domain": observation.get("domain", "general"),
            "content": observation.get("content", ""),
            "confidence": observation.get("confidence", 0.5),
            "relevance": observation.get("relevance", 0.5),
            "tags": observation.get("tags", []),
            "timestamp": time.time(),
        }

        self._observations.append(obs)
        self._agent_contributions[agent].append(obs)
        self._trim_observations()

        # Broadcast to active collaborations
        collab_id = observation.get("collaboration_id")
        if collab_id and collab_id in self._collaborations:
            self._collaborations[collab_id]["contributions"].append(obs)

        # Share via messaging bus
        if self._msg_bus:
            self._msg_bus.broadcast(agent, {
                "type": "info",
                "payload": {"observation_id": obs_id, **obs},
            })

        return {"id": obs_id, "shared": True, "agent": agent,
                "domain": obs["domain"]}

    # ── request_support ─────────────────────────────────────
    def request_support(self, agent: str, request: dict) -> dict:
        """Un agent demande du support à d'autres agents."""
        self._stats["support_requests"] += 1
        req_id = f"supp_{uuid.uuid4().hex[:10]}"

        support = {
            "id": req_id,
            "requester": agent,
            "domain": request.get("domain", "general"),
            "description": request.get("description", ""),
            "urgency": request.get("urgency", "normal"),
            "required_skills": request.get("required_skills", []),
            "status": "pending",
            "responses": [],
            "timestamp": time.time(),
        }

        self._support_requests.append(support)

        # Broadcast support request
        if self._msg_bus:
            self._msg_bus.broadcast(agent, {
                "type": "assistance_request",
                "payload": {
                    "support_id": req_id,
                    "domain": support["domain"],
                    "description": support["description"],
                    "urgency": support["urgency"],
                },
            })

        log.info("Support request %s from %s: %s",
                 req_id, agent, support["description"][:80])

        return {"id": req_id, "status": "pending", "requester": agent}

    # ── get_collaboration_status ────────────────────────────
    def get_collaboration_status(self, collab_id: str) -> dict:
        collab = self._collaborations.get(collab_id)
        if not collab:
            return {"found": False, "collaboration_id": collab_id}

        return {
            "found": True,
            "id": collab_id,
            "status": collab["status"],
            "initiator": collab["initiator"],
            "participants": collab["participants"],
            "type": collab["type"],
            "contributions_count": len(collab["contributions"]),
            "duration_sec": time.time() - collab["started_at"],
        }

    # ── complete_collaboration ──────────────────────────────
    def complete_collaboration(self, collab_id: str,
                               result: dict) -> dict:
        """Marquer une collaboration comme terminée."""
        collab = self._collaborations.get(collab_id)
        if not collab:
            return {"completed": False, "reason": "not_found"}

        if collab["status"] != "active":
            return {"completed": False, "reason": "not_active",
                    "current_status": collab["status"]}

        collab["status"] = "completed"
        collab["result"] = result
        collab["completed_at"] = time.time()
        collab["duration_sec"] = collab["completed_at"] - collab["started_at"]

        self._stats["collaborations_completed"] += 1

        if self._audit:
            self._audit.log_governance({
                "type": "governance_decision",
                "governor": "collaboration_bus",
                "decision": "collaboration_completed",
                "scope": collab["type"],
                "impact": "low",
            })

        return {
            "completed": True,
            "id": collab_id,
            "duration_sec": collab["duration_sec"],
            "contributions_count": len(collab["contributions"]),
            "result_summary": result.get("summary", ""),
        }

    # ── get_shared_observations ─────────────────────────────
    def get_shared_observations(self, domain: str | None = None,
                                limit: int = 50) -> list[dict]:
        obs = self._observations
        if domain:
            obs = [o for o in obs if o["domain"] == domain]
        return obs[-limit:]

    # ── health_check ────────────────────────────────────────
    def health_check(self) -> dict:
        active_collabs = sum(
            1 for c in self._collaborations.values()
            if c["status"] == "active")
        return {
            "service": "emergent_collaboration_bus",
            "status": "ok",
            "active_collaborations": active_collabs,
            "total_collaborations": len(self._collaborations),
            "observations_count": len(self._observations),
            "pending_support": sum(
                1 for s in self._support_requests
                if s["status"] == "pending"),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._collaborations.clear()
        self._observations.clear()
        self._support_requests.clear()
        self._agent_contributions.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("EmergentCollaborationBus restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim_observations(self) -> None:
        if len(self._observations) > 5000:
            self._observations = self._observations[-5000:]
