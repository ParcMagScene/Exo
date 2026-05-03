"""
home_bridge.py — WebSocket + REST bridge to Home Assistant.

Manages persistent WebSocket connection with auto-reconnect,
event subscriptions, and REST API calls for EXO.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Callable, Optional

import aiohttp

logger = logging.getLogger("exo.ha.bridge")

# ---------------------------------------------------------------------------
# Internal event bus
# ---------------------------------------------------------------------------

class EventBus:
    """Lightweight async event bus for HA events inside EXO."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable]] = {}

    def on(self, event_type: str, callback: Callable) -> None:
        self._listeners.setdefault(event_type, []).append(callback)

    def off(self, event_type: str, callback: Callable) -> None:
        cbs = self._listeners.get(event_type, [])
        if callback in cbs:
            cbs.remove(callback)

    async def emit(self, event_type: str, data: Any = None) -> None:
        for cb in self._listeners.get(event_type, []):
            try:
                result = cb(data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception("EventBus callback error for %s", event_type)


# ---------------------------------------------------------------------------
# Home Assistant Bridge
# ---------------------------------------------------------------------------

class HomeBridge:
    """Manages WebSocket + REST communication with Home Assistant."""

    PING_INTERVAL = 30  # seconds

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
    ) -> None:
        self._base_url = (url or os.environ.get("HA_URL", "http://localhost:8123")).rstrip("/")
        self._token = token or os.environ.get("HA_TOKEN", "")
        self._ws_url = self._base_url.replace("http", "ws", 1) + "/api/websocket"

        self.bus = EventBus()

        # WebSocket state
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._msg_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._connected = False
        self._running = False

        # Caches populated on connect
        self.entities: dict[str, dict] = {}
        self.devices: dict[str, dict] = {}
        self.areas: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Connect and run the event loop. Reconnects automatically."""
        self._running = True
        self._session = aiohttp.ClientSession()
        while self._running:
            try:
                await self._connect()
                await self._listen()
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                logger.warning("HA connection lost: %s — retrying in 5s", exc)
            finally:
                self._connected = False
                await self.bus.emit("disconnected")
            if self._running:
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Gracefully shut down."""
        self._running = False
        for fut in self._pending.values():
            fut.cancel()
        self._pending.clear()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------------
    # WebSocket internals
    # ------------------------------------------------------------------

    async def _connect(self) -> None:
        assert self._session is not None
        self._ws = await self._session.ws_connect(self._ws_url, heartbeat=self.PING_INTERVAL)
        # HA sends auth_required on connect
        msg = await self._ws.receive_json()
        if msg.get("type") != "auth_required":
            raise RuntimeError(f"Unexpected HA greeting: {msg}")

        # Authenticate
        await self._ws.send_json({"type": "auth", "access_token": self._token})
        msg = await self._ws.receive_json()
        if msg.get("type") != "auth_ok":
            raise RuntimeError(f"HA auth failed: {msg.get('message', 'unknown')}")

        self._msg_id = 0
        self._connected = True
        logger.info("Connected to Home Assistant (%s)", self._base_url)
        await self.bus.emit("connected")

        # Initial data fetch + subscriptions
        await self._bootstrap()

    async def _bootstrap(self) -> None:
        """Fetch initial data and subscribe to events after connect."""
        states, devices, areas, entity_reg = await asyncio.gather(
            self.ws_command("get_states"),
            self.ws_command("config/device_registry/list"),
            self.ws_command("config/area_registry/list"),
            self.ws_command("config/entity_registry/list"),
        )

        # Populate entities cache
        if isinstance(states, list):
            for s in states:
                eid = s.get("entity_id", "")
                self.entities[eid] = s

        # Populate devices cache
        if isinstance(devices, list):
            for d in devices:
                did = d.get("id", "")
                self.devices[did] = d

        # Populate areas cache
        if isinstance(areas, list):
            for a in areas:
                aid = a.get("area_id", "")
                self.areas[aid] = a

        logger.info(
            "HA bootstrap: %d entities, %d devices, %d areas",
            len(self.entities), len(self.devices), len(self.areas),
        )

        # Subscribe to live events
        for event_type in (
            "state_changed",
            "device_registry_updated",
            "area_registry_updated",
            "entity_registry_updated",
        ):
            await self._subscribe_event(event_type)

    async def _subscribe_event(self, event_type: str) -> None:
        await self.ws_command("subscribe_events", event_type=event_type)

    async def _listen(self) -> None:
        """Read messages until the connection closes."""
        assert self._ws is not None
        async for raw in self._ws:
            if raw.type == aiohttp.WSMsgType.TEXT:
                msg = json.loads(raw.data)
                await self._handle_message(msg)
            elif raw.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break

    async def _handle_message(self, msg: dict) -> None:
        msg_type = msg.get("type")

        # Command response
        if msg_type == "result":
            mid = msg.get("id")
            fut = self._pending.pop(mid, None)
            if fut and not fut.done():
                if msg.get("success"):
                    fut.set_result(msg.get("result"))
                else:
                    fut.set_exception(RuntimeError(msg.get("error", {}).get("message", "unknown")))
            return

        # Event
        if msg_type == "event":
            event = msg.get("event", {})
            etype = event.get("event_type", "")
            data = event.get("data", {})
            await self._dispatch_event(etype, data)

    async def _dispatch_event(self, event_type: str, data: dict) -> None:
        if event_type == "state_changed":
            new_state = data.get("new_state")
            if new_state:
                eid = new_state.get("entity_id", "")
                self.entities[eid] = new_state
                await self.bus.emit("on_state_changed", new_state)

        elif event_type == "device_registry_updated":
            action = data.get("action")
            if action == "create":
                await self.bus.emit("on_new_device", data)
            elif action == "remove":
                self.devices.pop(data.get("device_id", ""), None)
                await self.bus.emit("on_device_removed", data)
            else:
                await self.bus.emit("on_device_updated", data)
            # Refresh device list
            result = await self.ws_command("config/device_registry/list")
            if isinstance(result, list):
                self.devices = {d.get("id", ""): d for d in result}

        elif event_type == "area_registry_updated":
            result = await self.ws_command("config/area_registry/list")
            if isinstance(result, list):
                self.areas = {a.get("area_id", ""): a for a in result}
            await self.bus.emit("on_area_updated", data)

        elif event_type == "entity_registry_updated":
            result = await self.ws_command("config/entity_registry/list")
            if isinstance(result, list):
                for e in result:
                    eid = e.get("entity_id", "")
                    if eid in self.entities:
                        self.entities[eid].update(e)

    # ------------------------------------------------------------------
    # WebSocket command helper
    # ------------------------------------------------------------------

    async def ws_command(self, cmd_type: str, **kwargs: Any) -> Any:
        """Send a WS command and await the result (timeout 15s)."""
        if not self._ws or self._ws.closed:
            raise ConnectionError("Not connected to Home Assistant")
        self._msg_id += 1
        mid = self._msg_id
        payload = {"id": mid, "type": cmd_type, **kwargs}
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[mid] = fut
        await self._ws.send_json(payload)
        try:
            return await asyncio.wait_for(fut, timeout=15)
        except asyncio.TimeoutError:
            self._pending.pop(mid, None)
            raise

    # ------------------------------------------------------------------
    # REST helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def rest_get(self, path: str) -> Any:
        assert self._session is not None
        url = f"{self._base_url}{path}"
        async with self._session.get(url, headers=self._headers(), timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def rest_post(self, path: str, data: Optional[dict] = None) -> Any:
        assert self._session is not None
        url = f"{self._base_url}{path}"
        async with self._session.post(url, headers=self._headers(), json=data or {}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            return await resp.json()

    # ------------------------------------------------------------------
    # Convenience REST endpoints
    # ------------------------------------------------------------------

    async def get_states(self) -> list[dict]:
        return await self.rest_get("/api/states")

    async def get_services(self) -> list[dict]:
        return await self.rest_get("/api/services")

    async def call_service(self, domain: str, service: str, data: Optional[dict] = None) -> dict:
        return await self.rest_post(f"/api/services/{domain}/{service}", data)

    async def get_camera_proxy(self, entity_id: str) -> bytes:
        """Return raw JPEG bytes from a camera entity."""
        assert self._session is not None
        url = f"{self._base_url}/api/camera_proxy/{entity_id}"
        async with self._session.get(url, headers=self._headers(), timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            return await resp.read()
