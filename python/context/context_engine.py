#!/usr/bin/env python3
"""

# Patch global EXO : forcer le working directory à D:/EXO/ pour tous les services
import os
os.chdir("D:/EXO/")
EXO v10 — ContextEngine v3 Server (WebSocket)
Port 8777 — Conscience contextuelle dynamique enrichie

v10 enrichments (ContextEngine v3):
  - All v8 features (location, preferences, topic, energy, plan tracking)
  - build_agent_context(intent) — full agent context for cognitive processing
  - inject_context(prompt) — inject context into LLM prompt
  - Agent state awareness (current cognitive state)
  - Task history integration

Protocol WebSocket :
  → JSON {"action":"get_context"}
  ← JSON {"ok":true,"data":{"temporal":{...},"activity":{...},...}}

  → JSON {"action":"build_agent_context","params":{"intent":"..."}}
  ← JSON {"ok":true,"data":{"temporal":{...},"tasks":{...},"preferences":{...},...}}

  → JSON {"action":"inject_context","params":{"prompt":"..."}}
  ← JSON {"ok":true,"data":{"enriched_prompt":"..."}}

  → JSON {"action":"score_relevance","params":{"memory_text":"..."}}
  ← JSON {"ok":true,"data":{"score":0.72}}
"""

import asyncio
try:
    import ujson as json  # v6.0 perf : 3-5x plus rapide que stdlib (audit perf)
except ImportError:
    import json
import logging
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")

from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9


# --- Logging EXO centralisé (identique C++) ---
def _get_exo_logfile():
    # Correction : tous les logs doivent aller dans D:/EXO/logs/
    log_dir = os.environ.get("EXO_LOGS_DIR", "D:/EXO/logs")
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    ts = os.environ.get("EXO_SESSION_TIMESTAMP")
    if not ts:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(log_dir, f"exo_{ts}.log")

logfile = _get_exo_logfile()
_file_handler = logging.FileHandler(logfile, encoding="utf-8", delay=False)
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [Context] %(message)s"))
_file_handler.flush = _file_handler.stream.flush  # flush explicite

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Context] %(message)s")
log = logging.getLogger("context_engine")
log.addHandler(_file_handler)
log.propagate = True

# Log d'amorçage immédiat pour diagnostic
log.info("=== EXO CONTEXT_ENGINE STARTUP ===")
_file_handler.flush()

PORT = 8777
MAX_EVENTS = 200
MAX_INTERACTIONS = 50

# v8: Preference detection patterns
PREFERENCE_PATTERNS = {
    "musique": ["musique", "chanson", "album", "artiste", "playlist", "spotify"],
    "sport": ["sport", "foot", "tennis", "course", "gym", "musculation"],
    "cuisine": ["cuisine", "recette", "plat", "restaurant", "manger"],
    "tech": ["code", "programmation", "python", "javascript", "api", "serveur"],
    "lecture": ["livre", "roman", "lecture", "auteur", "lire"],
    "cinéma": ["film", "série", "netflix", "cinéma", "acteur"],
    "voyage": ["voyage", "vacances", "avion", "hôtel", "destination"],
    "santé": ["santé", "médecin", "sport", "sommeil", "régime"],
}

# ─────────────────────────────────────────────────────
#  Activity patterns based on time of day (local)
# ─────────────────────────────────────────────────────

ACTIVITY_PATTERNS = {
    (6, 9):   "morning_routine",
    (9, 12):  "work_morning",
    (12, 14): "lunch_break",
    (14, 18): "work_afternoon",
    (18, 20): "evening_leisure",
    (20, 23): "night_relaxation",
    (23, 6):  "sleeping",
}

SEASON_MAP = {
    (3, 5): "printemps",
    (6, 8): "été",
    (9, 11): "automne",
    (12, 2): "hiver",
}


def get_season(month: int) -> str:
    if month in (3, 4, 5):
        return "printemps"
    if month in (6, 7, 8):
        return "été"
    if month in (9, 10, 11):
        return "automne"
    return "hiver"


def get_probable_activity(hour: int) -> str:
    for (start, end), activity in ACTIVITY_PATTERNS.items():
        if start <= end:
            if start <= hour < end:
                return activity
        else:  # wraps midnight
            if hour >= start or hour < end:
                return activity
    return "unknown"


# ─────────────────────────────────────────────────────
#  ContextEngine — maintains live context state
# ─────────────────────────────────────────────────────

class ContextEngine:
    """Stateful context engine tracking user activity and environment (v10/v3)."""

    def __init__(self) -> None:
        self._events: list[dict] = []
        self._interactions: list[dict] = []
        self._active_modules: dict[str, bool] = {}
        self._active_tasks: list[dict] = []
        self._user_preferences: dict[str, Any] = {}
        self._custom_vars: dict[str, Any] = {}
        # v8 additions
        self._location: dict[str, str] = {"city": "Paris", "country": "FR"}
        self._conversation_topic: str = ""
        self._topic_confidence: float = 0.0
        self._implicit_preferences: dict[str, float] = {}  # category → score
        self._current_plan: dict | None = None
        self._agent_state: str = "idle"
        self._task_history: list[dict] = []

    def get_context(self) -> dict:
        """Build complete context snapshot (v8: enriched)."""
        now = datetime.now()
        utc_now = datetime.now(timezone.utc)

        temporal = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day_name": now.strftime("%A"),
            "day_of_week": now.isoweekday(),
            "month": now.month,
            "year": now.year,
            "hour": now.hour,
            "season": get_season(now.month),
            "is_weekend": now.isoweekday() >= 6,
            "utc_offset": int((now - utc_now.replace(tzinfo=None)).total_seconds() / 3600),
        }

        activity = {
            "probable": get_probable_activity(now.hour),
            "last_interaction_ago_s": self._seconds_since_last_interaction(),
            "interaction_count_1h": self._count_recent_interactions(3600),
            "is_active": self._seconds_since_last_interaction() < 300,
        }

        # v8: Energy estimation from interaction frequency
        energy = self._estimate_energy()

        modules = dict(self._active_modules)
        tasks = list(self._active_tasks)
        recent = self._interactions[-5:] if self._interactions else []
        recent_events = self._events[-10:] if self._events else []
        preferences = dict(self._user_preferences)

        return {
            "temporal": temporal,
            "activity": activity,
            "modules": modules,
            "active_tasks": tasks,
            "recent_interactions": recent,
            "recent_events": recent_events,
            "preferences": preferences,
            "custom": dict(self._custom_vars),
            # v8 additions
            "location": dict(self._location),
            "conversation_topic": self._conversation_topic,
            "topic_confidence": self._topic_confidence,
            "implicit_preferences": dict(self._implicit_preferences),
            "energy_level": energy,
            "current_plan": self._current_plan,
        }

    def update_context(self, event: str, data: dict | None = None) -> None:
        """Record a context event."""
        entry = {
            "event": event,
            "timestamp": time.time(),
            "data": data or {},
        }
        self._events.append(entry)
        if len(self._events) > MAX_EVENTS:
            self._events = self._events[-MAX_EVENTS:]

    def add_interaction(self, user_msg: str, assistant_msg: str = "") -> None:
        """Track a conversation interaction (v8: + topic + preferences)."""
        self._interactions.append({
            "timestamp": time.time(),
            "user": user_msg[:200],
            "assistant": assistant_msg[:200],
        })
        if len(self._interactions) > MAX_INTERACTIONS:
            self._interactions = self._interactions[-MAX_INTERACTIONS:]
        # v8: Auto-detect topic and preferences
        if user_msg:
            self._update_topic(user_msg)
            self.detect_preferences(user_msg)

    def set_module_status(self, module: str, active: bool) -> None:
        self._active_modules[module] = active

    def set_active_tasks(self, tasks: list[dict]) -> None:
        self._active_tasks = tasks

    def set_preference(self, key: str, value: Any) -> None:
        self._user_preferences[key] = value

    def set_custom(self, key: str, value: Any) -> None:
        self._custom_vars[key] = value

    # ── v8: Location ─────────────────────────────────

    def set_location(self, city: str, country: str = "FR") -> None:
        self._location = {"city": city, "country": country}
        log.info("Location set: %s, %s", city, country)

    # ── v8: Topic Tracking ───────────────────────────

    def _update_topic(self, text: str) -> None:
        """Detect the conversation topic from user text."""
        text_lower = text.lower()
        topic_scores: dict[str, float] = {}
        for category, keywords in PREFERENCE_PATTERNS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                topic_scores[category] = score

        if topic_scores:
            best = max(topic_scores, key=topic_scores.get)
            self._conversation_topic = best
            self._topic_confidence = min(1.0, topic_scores[best] / 3.0)
        # Decay topic confidence slowly
        elif self._topic_confidence > 0:
            self._topic_confidence *= 0.8
            if self._topic_confidence < 0.1:
                self._conversation_topic = ""
                self._topic_confidence = 0.0

    # ── v8: Implicit Preference Detection ────────────

    def detect_preferences(self, text: str) -> list[dict]:
        """Detect implicit preferences from user text."""
        text_lower = text.lower()
        detected = []
        for category, keywords in PREFERENCE_PATTERNS.items():
            matches = [kw for kw in keywords if kw in text_lower]
            if matches:
                # Accumulate preference score
                current = self._implicit_preferences.get(category, 0.0)
                boost = min(0.3, len(matches) * 0.1)
                self._implicit_preferences[category] = min(1.0, current + boost)
                detected.append({
                    "category": category,
                    "keywords": matches,
                    "score": self._implicit_preferences[category],
                })
        return detected

    # ── v8: Energy Estimation ────────────────────────

    def _estimate_energy(self) -> str:
        """Estimate user energy level from interaction patterns."""
        count_1h = self._count_recent_interactions(3600)
        last_ago = self._seconds_since_last_interaction()

        if last_ago > 1800:  # 30min idle
            return "resting"
        elif count_1h >= 10:
            return "high"
        elif count_1h >= 5:
            return "moderate"
        elif count_1h >= 1:
            return "low"
        return "idle"

    # ── v8: Plan Tracking ────────────────────────────

    def set_current_plan(self, plan: dict | None) -> None:
        self._current_plan = plan

    def score_relevance(self, memory_text: str) -> float:
        """Score how relevant a memory is to the current context."""
        now = datetime.now()
        score = 0.5  # base

        text_lower = memory_text.lower()

        # Temporal relevance
        if now.strftime("%A").lower() in text_lower:
            score += 0.1
        season = get_season(now.month)
        if season in text_lower:
            score += 0.05

        # Activity relevance
        activity = get_probable_activity(now.hour)
        activity_keywords = {
            "morning_routine": ["matin", "réveil", "café", "morning"],
            "work_morning": ["travail", "bureau", "réunion", "projet"],
            "lunch_break": ["déjeuner", "midi", "repas", "lunch"],
            "work_afternoon": ["travail", "après-midi", "projet"],
            "evening_leisure": ["soir", "repos", "musique", "cuisine"],
            "night_relaxation": ["nuit", "film", "lecture", "dormir"],
        }
        for kw in activity_keywords.get(activity, []):
            if kw in text_lower:
                score += 0.08
                break

        # Recent interaction relevance
        if self._interactions:
            last = self._interactions[-1]
            last_words = set(last.get("user", "").lower().split())
            mem_words = set(text_lower.split())
            overlap = len(last_words & mem_words)
            if overlap > 2:
                score += min(0.15, overlap * 0.03)

        return min(1.0, score)

    # ── v10: Agent Context Builder ─────────────────

    def build_agent_context(self, intent: str = "") -> dict:
        """Build a rich agent context combining all available information.

        Used by the AgentManager before sending to LLM or planning.
        Combines temporal, tasks, preferences, environment, history, and intent.
        """
        base = self.get_context()

        # Active tasks summary
        tasks_summary = {
            "active": base.get("active_tasks", []),
            "current_plan": base.get("current_plan"),
            "recent_history": self._task_history[-5:] if self._task_history else [],
        }

        # Intent analysis
        intent_ctx = {}
        if intent:
            intent_lower = intent.lower()
            # Detect relevant preferences for this intent
            relevant_prefs = {}
            for cat, score in self._implicit_preferences.items():
                for kw in PREFERENCE_PATTERNS.get(cat, []):
                    if kw in intent_lower:
                        relevant_prefs[cat] = score
                        break
            intent_ctx = {
                "raw": intent,
                "relevant_preferences": relevant_prefs,
                "topic_match": self._conversation_topic if self._conversation_topic and self._conversation_topic in intent_lower else "",
            }

        return {
            "temporal": base["temporal"],
            "activity": base["activity"],
            "location": base["location"],
            "tasks": tasks_summary,
            "preferences": base["preferences"],
            "implicit_preferences": base["implicit_preferences"],
            "energy_level": base["energy_level"],
            "conversation_topic": base["conversation_topic"],
            "agent_state": self._agent_state,
            "intent": intent_ctx,
            "modules": base["modules"],
        }

    def inject_context(self, prompt: str) -> str:
        """Inject contextual information into an LLM prompt.

        Prepends a concise context block to the prompt so the LLM
        is aware of temporal, environmental, and user state.
        """
        ctx = self.get_context()
        temporal = ctx["temporal"]
        parts = [
            f"[Contexte: {temporal['day_name']} {temporal['date']} {temporal['time']}",
            f"Saison: {temporal['season']}",
        ]
        if ctx.get("location", {}).get("city"):
            parts.append(f"Lieu: {ctx['location']['city']}")
        if ctx.get("conversation_topic"):
            parts.append(f"Sujet: {ctx['conversation_topic']}")
        if ctx.get("energy_level"):
            parts.append(f"\u00c9nergie: {ctx['energy_level']}")
        if ctx.get("current_plan"):
            plan_goal = ctx["current_plan"].get("goal", "")
            parts.append(f"Plan actif: {plan_goal}")

        context_line = " | ".join(parts) + "]"
        return f"{context_line}\n\n{prompt}"

    def set_agent_state(self, state: str) -> None:
        self._agent_state = state

    def add_task_history(self, task: dict) -> None:
        self._task_history.append(task)
        if len(self._task_history) > 100:
            self._task_history = self._task_history[-100:]

    def _seconds_since_last_interaction(self) -> float:
        if not self._interactions:
            return 9999.0
        return time.time() - self._interactions[-1]["timestamp"]

    def _count_recent_interactions(self, window_s: float) -> int:
        cutoff = time.time() - window_s
        return sum(1 for i in self._interactions if i["timestamp"] > cutoff)


# ─────────────────────────────────────────────────────
#  WebSocket Handler
# ─────────────────────────────────────────────────────

async def handle_client(ws, engine: ContextEngine) -> None:
    log.info("Context client connected")
    await ws.send(json.dumps({
        "type": "ready",
        "service": "context_engine",
        "model": "n/a",
        "device": "n/a",
        "backend": "n/a"
    }))

    try:
        async for raw in ws:
            if not isinstance(raw, str):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action", msg.get("type", ""))
            params = msg.get("params", {})

            if action == "ping":
                await ws.send(json.dumps({"type": "pong"}))
                continue

            try:
                if action == "get_context":
                    ctx = engine.get_context()
                    await ws.send(json.dumps({"ok": True, "data": ctx}))

                elif action == "update_context":
                    engine.update_context(
                        params.get("event", "unknown"),
                        params.get("data", {}),
                    )
                    await ws.send(json.dumps({"ok": True}))

                elif action == "add_interaction":
                    engine.add_interaction(
                        params.get("user", ""),
                        params.get("assistant", ""),
                    )
                    await ws.send(json.dumps({"ok": True}))

                elif action == "set_module_status":
                    engine.set_module_status(
                        params.get("module", ""),
                        params.get("active", True),
                    )
                    await ws.send(json.dumps({"ok": True}))

                elif action == "set_tasks":
                    engine.set_active_tasks(params.get("tasks", []))
                    await ws.send(json.dumps({"ok": True}))

                elif action == "set_preference":
                    engine.set_preference(
                        params.get("key", ""),
                        params.get("value"),
                    )
                    await ws.send(json.dumps({"ok": True}))

                elif action == "score_relevance":
                    score = engine.score_relevance(params.get("memory_text", ""))
                    await ws.send(json.dumps({
                        "ok": True,
                        "data": {"score": score},
                    }))

                # ── v8: New actions ──────────────────

                elif action == "detect_preferences":
                    detected = engine.detect_preferences(params.get("text", ""))
                    await ws.send(json.dumps({
                        "ok": True,
                        "data": {"detected": detected},
                    }))

                elif action == "set_location":
                    engine.set_location(
                        params.get("city", "Paris"),
                        params.get("country", "FR"),
                    )
                    await ws.send(json.dumps({"ok": True}))

                elif action == "get_topic":
                    await ws.send(json.dumps({
                        "ok": True,
                        "data": {
                            "topic": engine._conversation_topic,
                            "confidence": engine._topic_confidence,
                        },
                    }))

                elif action == "set_current_plan":
                    engine.set_current_plan(params.get("plan"))
                    await ws.send(json.dumps({"ok": True}))

                # ── v10: Agent context actions ─────────

                elif action == "build_agent_context":
                    ctx = engine.build_agent_context(params.get("intent", ""))
                    await ws.send(json.dumps({"ok": True, "data": ctx}))

                elif action == "inject_context":
                    enriched = engine.inject_context(params.get("prompt", ""))
                    await ws.send(json.dumps({
                        "ok": True,
                        "data": {"enriched_prompt": enriched},
                    }))

                elif action == "set_agent_state":
                    engine.set_agent_state(params.get("state", "idle"))
                    await ws.send(json.dumps({"ok": True}))

                elif action == "add_task_history":
                    engine.add_task_history(params.get("task", {}))
                    await ws.send(json.dumps({"ok": True}))

                else:
                    await ws.send(json.dumps({
                        "ok": False,
                        "error": f"Unknown action: {action}",
                    }))

            except Exception as e:
                log.error("Context operation error: %s", e, exc_info=True)
                await ws.send(json.dumps({
                    "ok": False,
                    "error": "Erreur interne du service context",
                }))

    except Exception as e:
        log.error("Context session error: %s", e)
    finally:
        log.info("Context client disconnected")


# ─────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────

async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="EXO v10 Context Engine v3 Server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    ensure_single_instance(args.port, "context_engine")
    _v9 = init_v9("context_engine", args.port)

    engine = ContextEngine()
    log.info("ContextEngine initialized")

    async def handler(ws):
        await handle_client(ws, engine)

    server = await websockets.serve(
        handler, args.host, args.port,
        ping_interval=None, ping_timeout=None,
    )
    log.info("Context Engine running on ws://%s:%d", args.host, args.port)

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        await server.wait_closed()
        log.info("Context Engine stopped")


if __name__ == "__main__":
    asyncio.run(main())
