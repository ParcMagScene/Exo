#!/usr/bin/env python3
"""
EXO v8 — CalendarService (WebSocket)
Port 8782 — Gestion d'événements calendrier pour l'agent autonome

Calendrier local basé fichier JSON. Pas de dépendance externe.

Protocol WebSocket :
  → {"action":"calendar_add","params":{"title":"...","date":"2025-07-20","time":"14:00","duration_min":60}}
  ← {"ok":true,"data":{"event_id":"...","created":true}}

  → {"action":"calendar_list","params":{"from":"2025-07-20","to":"2025-07-27"}}
  ← {"ok":true,"data":{"events":[...],"count":3}}

  → {"action":"calendar_delete","params":{"event_id":"..."}}
  ← {"ok":true}

  → {"action":"calendar_today"}
  ← {"ok":true,"data":{"events":[...],"date":"2025-07-20"}}
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")

from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Calendar] %(message)s")
log = logging.getLogger("calendar_service")

PORT = 8782
DATA_DIR = Path(os.environ.get("EXO_FILES_DIR", r"D:\EXO\files"))
CALENDAR_FILE = DATA_DIR / "calendar.json"
MAX_EVENTS = 5000


class CalendarService:
    """Local JSON-backed calendar service."""

    def __init__(self, calendar_file: Path) -> None:
        self._file = calendar_file
        self._events: list[dict] = []
        self._load()

    def _load(self) -> None:
        if self._file.is_file():
            try:
                data = json.loads(self._file.read_text(encoding="utf-8"))
                self._events = data.get("events", [])
                log.info("Loaded %d calendar events", len(self._events))
            except Exception as e:
                log.error("Failed to load calendar: %s", e)
                self._events = []
        else:
            self._file.parent.mkdir(parents=True, exist_ok=True)

    def _save(self) -> None:
        self._file.write_text(
            json.dumps({"events": self._events}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_event(self, title: str, date: str, time: str = "",
                  duration_min: int = 60, description: str = "",
                  recurrence: str = "") -> dict:
        if len(self._events) >= MAX_EVENTS:
            raise ValueError("Calendar full")

        event_id = str(uuid.uuid4())[:8]
        event = {
            "event_id": event_id,
            "title": title,
            "date": date,  # YYYY-MM-DD
            "time": time,  # HH:MM (optional)
            "duration_min": duration_min,
            "description": description,
            "recurrence": recurrence,  # daily, weekly, monthly, yearly, ""
            "created_at": datetime.now().isoformat(),
        }
        self._events.append(event)
        self._save()
        log.info("Event added: %s on %s", title, date)
        return {"event_id": event_id, "created": True, "event": event}

    def list_events(self, from_date: str = "", to_date: str = "") -> dict:
        events = self._events

        if from_date:
            events = [e for e in events if e.get("date", "") >= from_date]
        if to_date:
            events = [e for e in events if e.get("date", "") <= to_date]

        # Sort by date and time
        events = sorted(events, key=lambda e: (e.get("date", ""), e.get("time", "")))

        return {"events": events, "count": len(events)}

    def today(self) -> dict:
        today_str = datetime.now().strftime("%Y-%m-%d")
        result = self.list_events(from_date=today_str, to_date=today_str)
        result["date"] = today_str
        return result

    def delete_event(self, event_id: str) -> bool:
        initial = len(self._events)
        self._events = [e for e in self._events if e.get("event_id") != event_id]
        if len(self._events) < initial:
            self._save()
            return True
        return False

    def upcoming(self, days: int = 7) -> dict:
        today = datetime.now()
        end = today + timedelta(days=days)
        return self.list_events(
            from_date=today.strftime("%Y-%m-%d"),
            to_date=end.strftime("%Y-%m-%d"),
        )


# ─────────────────────────────────────────────────────
#  WebSocket Handler
# ─────────────────────────────────────────────────────

async def handle_client(ws, service: CalendarService) -> None:
    log.info("Calendar client connected")
    await ws.send(json.dumps({
        "type": "ready", "service": "calendar_service", "version": "v8",
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
                if action == "calendar_add":
                    data = service.add_event(
                        title=params.get("title", ""),
                        date=params.get("date", ""),
                        time=params.get("time", ""),
                        duration_min=params.get("duration_min", 60),
                        description=params.get("description", ""),
                        recurrence=params.get("recurrence", ""),
                    )
                    await ws.send(json.dumps({"ok": True, "data": data}))

                elif action == "calendar_list":
                    data = service.list_events(
                        from_date=params.get("from", ""),
                        to_date=params.get("to", ""),
                    )
                    await ws.send(json.dumps({"ok": True, "data": data}))

                elif action == "calendar_today":
                    data = service.today()
                    await ws.send(json.dumps({"ok": True, "data": data}))

                elif action == "calendar_upcoming":
                    data = service.upcoming(days=params.get("days", 7))
                    await ws.send(json.dumps({"ok": True, "data": data}))

                elif action == "calendar_delete":
                    ok = service.delete_event(params.get("event_id", ""))
                    await ws.send(json.dumps({"ok": ok}))

                else:
                    await ws.send(json.dumps({
                        "ok": False,
                        "error": f"Unknown action: {action}",
                    }))

            except Exception as e:
                log.error("Calendar error: %s", e, exc_info=True)
                await ws.send(json.dumps({"ok": False, "error": "Erreur interne du service calendrier"}))

    except Exception as e:
        log.error("Calendar session error: %s", e)
    finally:
        log.info("Calendar client disconnected")


async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="EXO v8 Calendar Service")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    ensure_single_instance(args.port, "calendar_service")
    _v9 = init_v9("calendar_service", args.port)

    service = CalendarService(CALENDAR_FILE)
    log.info("CalendarService initialized")

    async def handler(ws):
        await handle_client(ws, service)

    server = await websockets.serve(
        handler, args.host, args.port,
        ping_interval=None, ping_timeout=None,
    )
    log.info("Calendar Service running on ws://%s:%d", args.host, args.port)

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
