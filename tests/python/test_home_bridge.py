"""Tests for home_bridge.py — EventBus and HomeBridge unit tests."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.home_bridge import EventBus, HomeBridge


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

class TestEventBus:
    @pytest.mark.asyncio
    async def test_emit_calls_listener(self):
        bus = EventBus()
        cb = AsyncMock()
        bus.on("test_event", cb)
        await bus.emit("test_event", {"key": "value"})
        cb.assert_awaited_once_with({"key": "value"})

    @pytest.mark.asyncio
    async def test_emit_no_listeners(self):
        bus = EventBus()
        # Should not raise
        await bus.emit("no_listeners", {})

    @pytest.mark.asyncio
    async def test_off_removes_listener(self):
        bus = EventBus()
        cb = AsyncMock()
        bus.on("evt", cb)
        bus.off("evt", cb)
        await bus.emit("evt", {})
        cb.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_multiple_listeners(self):
        bus = EventBus()
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        bus.on("multi", cb1)
        bus.on("multi", cb2)
        await bus.emit("multi", 42)
        cb1.assert_awaited_once_with(42)
        cb2.assert_awaited_once_with(42)

    @pytest.mark.asyncio
    async def test_sync_callback_supported(self):
        bus = EventBus()
        results = []
        bus.on("sync", lambda d: results.append(d))
        await bus.emit("sync", "hello")
        assert results == ["hello"]

    @pytest.mark.asyncio
    async def test_callback_error_does_not_propagate(self):
        bus = EventBus()
        bus.on("bad", lambda _: (_ for _ in ()).throw(ValueError("boom")))
        good_cb = AsyncMock()
        bus.on("bad", good_cb)
        # Bad callback should not prevent good_cb from running
        await bus.emit("bad", {})
        good_cb.assert_awaited_once()


# ---------------------------------------------------------------------------
# HomeBridge init
# ---------------------------------------------------------------------------

class TestHomeBridgeInit:
    def test_default_url(self):
        bridge = HomeBridge(token="test")
        assert bridge._base_url == "http://localhost:8123"
        assert bridge._ws_url == "ws://localhost:8123/api/websocket"

    def test_custom_url(self):
        bridge = HomeBridge(url="http://10.0.0.5:8123/", token="t")
        assert bridge._base_url == "http://10.0.0.5:8123"
        assert bridge._ws_url == "ws://10.0.0.5:8123/api/websocket"

    def test_not_connected_initially(self):
        bridge = HomeBridge(token="t")
        assert bridge.connected is False
        assert bridge.entities == {}
        assert bridge.devices == {}
        assert bridge.areas == {}


# ---------------------------------------------------------------------------
# HomeBridge.ws_command
# ---------------------------------------------------------------------------

class TestHomeBridgeWSCommand:
    @pytest.mark.asyncio
    async def test_ws_command_raises_when_disconnected(self):
        bridge = HomeBridge(token="t")
        with pytest.raises(ConnectionError, match="Not connected"):
            await bridge.ws_command("get_states")


# ---------------------------------------------------------------------------
# HomeBridge._handle_message
# ---------------------------------------------------------------------------

class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_result_resolves_future(self):
        bridge = HomeBridge(token="t")
        fut = asyncio.get_event_loop().create_future()
        bridge._pending[1] = fut
        await bridge._handle_message({"type": "result", "id": 1, "success": True, "result": [1, 2, 3]})
        assert fut.result() == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_result_error_sets_exception(self):
        bridge = HomeBridge(token="t")
        fut = asyncio.get_event_loop().create_future()
        bridge._pending[2] = fut
        await bridge._handle_message({
            "type": "result",
            "id": 2,
            "success": False,
            "error": {"message": "not found"},
        })
        with pytest.raises(RuntimeError, match="not found"):
            fut.result()

    @pytest.mark.asyncio
    async def test_state_changed_event(self):
        bridge = HomeBridge(token="t")
        cb = AsyncMock()
        bridge.bus.on("on_state_changed", cb)
        await bridge._handle_message({
            "type": "event",
            "event": {
                "event_type": "state_changed",
                "data": {
                    "new_state": {"entity_id": "light.test", "state": "on"},
                },
            },
        })
        cb.assert_awaited_once()
        # Entity should be cached
        assert "light.test" in bridge.entities


# ---------------------------------------------------------------------------
# HomeBridge._dispatch_event
# ---------------------------------------------------------------------------

class TestDispatchEvent:
    @pytest.mark.asyncio
    async def test_state_changed_updates_cache(self):
        bridge = HomeBridge(token="t")
        new_state = {"entity_id": "sensor.x", "state": "42"}
        await bridge._dispatch_event("state_changed", {"new_state": new_state})
        assert bridge.entities["sensor.x"]["state"] == "42"

    @pytest.mark.asyncio
    async def test_device_created_emits_event(self):
        bridge = HomeBridge(token="t")
        bridge._ws = MagicMock()
        bridge._ws.closed = False
        cb = AsyncMock()
        bridge.bus.on("on_new_device", cb)

        # Patch ws_command to avoid real WS call
        bridge.ws_command = AsyncMock(return_value=[])
        await bridge._dispatch_event("device_registry_updated", {"action": "create"})
        cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_device_removed_clears_cache(self):
        bridge = HomeBridge(token="t")
        bridge.devices["old_device"] = {"id": "old_device"}
        bridge.ws_command = AsyncMock(return_value=[])
        await bridge._dispatch_event("device_registry_updated", {"action": "remove", "device_id": "old_device"})
        assert "old_device" not in bridge.devices
