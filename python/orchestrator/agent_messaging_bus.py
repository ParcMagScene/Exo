"""
EXO v14 — AgentMessagingBus (Communication inter-agents)
Permet aux agents spécialisés de communiquer via messages typés,
protocoles stricts, logs complets et supervision permanente.

API:
  send(sender, recipient, message)    → dict
  broadcast(sender, message)          → list[dict]
  receive(agent_name)                 → list[dict]
  register_channel(agent_name)        → bool
  unregister_channel(agent_name)      → bool
  get_message_log(limit)              → list[dict]
  health_check()                      → dict
  restart()                           → None
  get_stats()                         → dict
"""

import logging
import time
import uuid
from collections import defaultdict
from typing import Any

log = logging.getLogger("agent_messaging_bus")

# Types de messages autorisés
VALID_MESSAGE_TYPES = frozenset({
    "task_request", "task_result", "task_error",
    "info", "query", "response",
    "alert", "status_update",
    "conflict_report", "assistance_request",
})


class AgentMessagingBus:
    """Bus de communication inter-agents EXO v14."""

    def __init__(self, meta_memory=None):
        self._memory = meta_memory
        self._channels: dict[str, bool] = {}  # agent_name → active
        self._mailboxes: dict[str, list[dict]] = defaultdict(list)
        self._message_log: list[dict] = []
        self._stats = {
            "messages_sent": 0,
            "messages_broadcast": 0,
            "messages_received": 0,
            "messages_dropped": 0,
            "channels_active": 0,
        }

    # ── register / unregister ───────────────────────────────
    def register_channel(self, agent_name: str) -> bool:
        """Register a communication channel for an agent."""
        if not agent_name:
            return False
        if agent_name in self._channels:
            log.debug("Channel '%s' already registered", agent_name)
            return True
        self._channels[agent_name] = True
        self._stats["channels_active"] = sum(
            1 for v in self._channels.values() if v)
        log.info("Channel registered: %s", agent_name)
        return True

    def unregister_channel(self, agent_name: str) -> bool:
        """Unregister a communication channel."""
        if agent_name not in self._channels:
            return False
        del self._channels[agent_name]
        self._mailboxes.pop(agent_name, None)
        self._stats["channels_active"] = sum(
            1 for v in self._channels.values() if v)
        log.info("Channel unregistered: %s", agent_name)
        return True

    # ── send ────────────────────────────────────────────────
    def send(self, sender: str, recipient: str, message: dict) -> dict:
        """Send a typed message from one agent to another."""
        msg_type = message.get("type", "info")
        if msg_type not in VALID_MESSAGE_TYPES:
            log.warning("Invalid message type '%s' from %s", msg_type, sender)
            self._stats["messages_dropped"] += 1
            return {"delivered": False, "reason": "invalid_message_type"}

        if recipient not in self._channels:
            log.warning("Recipient '%s' not registered", recipient)
            self._stats["messages_dropped"] += 1
            return {"delivered": False, "reason": "recipient_not_found"}

        if not self._channels.get(recipient, False):
            self._stats["messages_dropped"] += 1
            return {"delivered": False, "reason": "recipient_inactive"}

        envelope = {
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "sender": sender,
            "recipient": recipient,
            "type": msg_type,
            "payload": message.get("payload", {}),
            "timestamp": time.time(),
        }

        self._mailboxes[recipient].append(envelope)
        self._message_log.append(envelope)
        self._trim_log()
        self._stats["messages_sent"] += 1

        log.debug("Message %s: %s → %s (%s)",
                  envelope["id"], sender, recipient, msg_type)
        return {"delivered": True, "message_id": envelope["id"]}

    # ── broadcast ───────────────────────────────────────────
    def broadcast(self, sender: str, message: dict) -> list[dict]:
        """Broadcast a message to all registered agents (except sender)."""
        results = []
        for agent_name in list(self._channels):
            if agent_name == sender:
                continue
            r = self.send(sender, agent_name, message)
            results.append({"agent": agent_name, **r})
        self._stats["messages_broadcast"] += 1
        return results

    # ── receive ─────────────────────────────────────────────
    def receive(self, agent_name: str) -> list[dict]:
        """Retrieve and clear all pending messages for an agent."""
        messages = list(self._mailboxes.get(agent_name, []))
        self._mailboxes[agent_name] = []
        self._stats["messages_received"] += len(messages)
        return messages

    # ── peek (non-destructive) ──────────────────────────────
    def peek(self, agent_name: str) -> list[dict]:
        """Peek at pending messages without consuming them."""
        return list(self._mailboxes.get(agent_name, []))

    # ── get_message_log ─────────────────────────────────────
    def get_message_log(self, limit: int = 50) -> list[dict]:
        """Return recent message log entries."""
        return self._message_log[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "agent_messaging_bus",
            "status": "ok",
            "channels": len(self._channels),
            "pending_messages": sum(
                len(v) for v in self._mailboxes.values()),
        }

    def restart(self) -> None:
        self._mailboxes.clear()
        self._message_log.clear()
        for k in self._stats:
            self._stats[k] = 0
        self._stats["channels_active"] = sum(
            1 for v in self._channels.values() if v)
        log.info("AgentMessagingBus restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim_log(self) -> None:
        if len(self._message_log) > 2000:
            self._message_log = self._message_log[-1000:]
