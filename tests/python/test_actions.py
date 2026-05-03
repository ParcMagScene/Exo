"""Tests for ha_actions.py — ActionDispatcher + TOOL_DEFINITIONS tests."""

from __future__ import annotations

import pytest
import pytest_asyncio

from integrations.ha_entities import EntityManager
from integrations.ha_devices import DeviceManager
from integrations.ha_areas import AreaManager
from integrations.ha_actions import ActionDispatcher, TOOL_DEFINITIONS
from .conftest import MockBridge


@pytest_asyncio.fixture
async def dispatcher(bridge: MockBridge) -> ActionDispatcher:
    em = EntityManager(bridge)
    dm = DeviceManager(bridge)
    am = AreaManager(bridge)
    await em.load_entities()
    await dm.load_devices()
    await am.load_areas()
    return ActionDispatcher(bridge, em, dm, am)


# ---------------------------------------------------------------------------
# TOOL_DEFINITIONS validation
# ---------------------------------------------------------------------------

class TestToolDefinitions:
    def test_all_tools_have_required_keys(self):
        for tool in TOOL_DEFINITIONS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"

    def test_tool_count(self):
        assert len(TOOL_DEFINITIONS) == 13

    def test_unique_names(self):
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert len(names) == len(set(names))

    def test_all_tools_dispatched(self):
        """Each tool in TOOL_DEFINITIONS must have a handler in ActionDispatcher."""
        # We check by name — the dispatcher maps them
        tool_names = {t["name"] for t in TOOL_DEFINITIONS}
        expected = {
            "ha_turn_on", "ha_turn_off", "ha_toggle",
            "ha_set_brightness", "ha_set_color", "ha_set_temperature",
            "ha_play_media", "ha_pause_media", "ha_stop_media",
            "ha_get_state", "ha_list_devices", "ha_list_entities", "ha_list_areas",
        }
        assert tool_names == expected


# ---------------------------------------------------------------------------
# ActionDispatcher.execute
# ---------------------------------------------------------------------------

class TestActionDispatcherTurnOn:
    @pytest.mark.asyncio
    async def test_turn_on(self, dispatcher: ActionDispatcher, bridge: MockBridge):
        result = await dispatcher.execute("ha_turn_on", {"entity_id": "light.salon"})
        assert result["ok"] is True
        bridge.call_service.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_turn_off(self, dispatcher: ActionDispatcher, bridge: MockBridge):
        result = await dispatcher.execute("ha_turn_off", {"entity_id": "switch.garage"})
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_toggle(self, dispatcher: ActionDispatcher, bridge: MockBridge):
        result = await dispatcher.execute("ha_toggle", {"entity_id": "light.salon"})
        assert result["ok"] is True


class TestActionDispatcherBrightness:
    @pytest.mark.asyncio
    async def test_set_brightness(self, dispatcher: ActionDispatcher, bridge: MockBridge):
        result = await dispatcher.execute("ha_set_brightness", {"entity_id": "light.salon", "brightness": 128})
        assert result["ok"] is True
        # Verify call_service was called with brightness
        call_args = bridge.call_service.call_args
        assert call_args[0][0] == "light"
        assert call_args[0][1] == "turn_on"
        assert call_args[0][2]["brightness"] == 128

    @pytest.mark.asyncio
    async def test_set_brightness_clamped(self, dispatcher: ActionDispatcher, bridge: MockBridge):
        result = await dispatcher.execute("ha_set_brightness", {"entity_id": "light.salon", "brightness": 999})
        assert result["ok"] is True
        call_args = bridge.call_service.call_args
        assert call_args[0][2]["brightness"] == 255


class TestActionDispatcherColor:
    @pytest.mark.asyncio
    async def test_set_color(self, dispatcher: ActionDispatcher, bridge: MockBridge):
        result = await dispatcher.execute("ha_set_color", {"entity_id": "light.salon", "r": 255, "g": 0, "b": 128})
        assert result["ok"] is True
        call_args = bridge.call_service.call_args
        assert call_args[0][2]["rgb_color"] == [255, 0, 128]

    @pytest.mark.asyncio
    async def test_set_color_clamped(self, dispatcher: ActionDispatcher, bridge: MockBridge):
        result = await dispatcher.execute("ha_set_color", {"entity_id": "light.salon", "r": 300, "g": -10, "b": 128})
        assert result["ok"] is True
        call_args = bridge.call_service.call_args
        assert call_args[0][2]["rgb_color"] == [255, 0, 128]


class TestActionDispatcherClimate:
    @pytest.mark.asyncio
    async def test_set_temperature(self, dispatcher: ActionDispatcher, bridge: MockBridge):
        result = await dispatcher.execute("ha_set_temperature", {"entity_id": "climate.thermostat", "temperature": 22.5})
        assert result["ok"] is True
        call_args = bridge.call_service.call_args
        assert call_args[0][2]["temperature"] == 22.5


class TestActionDispatcherMedia:
    @pytest.mark.asyncio
    async def test_play_media(self, dispatcher: ActionDispatcher, bridge: MockBridge):
        result = await dispatcher.execute("ha_play_media", {
            "entity_id": "media_player.tv",
            "media_url": "http://example.com/song.mp3",
        })
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_pause_media(self, dispatcher: ActionDispatcher, bridge: MockBridge):
        result = await dispatcher.execute("ha_pause_media", {"entity_id": "media_player.tv"})
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_stop_media(self, dispatcher: ActionDispatcher, bridge: MockBridge):
        result = await dispatcher.execute("ha_stop_media", {"entity_id": "media_player.tv"})
        assert result["ok"] is True


class TestActionDispatcherQueries:
    @pytest.mark.asyncio
    async def test_get_state(self, dispatcher: ActionDispatcher):
        result = await dispatcher.execute("ha_get_state", {"entity_id": "light.salon"})
        assert result["entity_id"] == "light.salon"
        assert result["state"] == "on"

    @pytest.mark.asyncio
    async def test_get_state_missing_falls_back_to_rest(self, dispatcher: ActionDispatcher, bridge: MockBridge):
        bridge.rest_get.return_value = {"entity_id": "light.unknown", "state": "off"}
        result = await dispatcher.execute("ha_get_state", {"entity_id": "light.unknown"})
        bridge.rest_get.assert_awaited()

    @pytest.mark.asyncio
    async def test_list_devices(self, dispatcher: ActionDispatcher):
        result = await dispatcher.execute("ha_list_devices", {})
        assert "devices" in result
        assert len(result["devices"]) > 0

    @pytest.mark.asyncio
    async def test_list_entities(self, dispatcher: ActionDispatcher):
        result = await dispatcher.execute("ha_list_entities", {})
        assert "entities" in result

    @pytest.mark.asyncio
    async def test_list_entities_filtered(self, dispatcher: ActionDispatcher):
        result = await dispatcher.execute("ha_list_entities", {"domain": "light"})
        assert "entities" in result
        assert all(e["domain"] == "light" for e in result["entities"])

    @pytest.mark.asyncio
    async def test_list_areas(self, dispatcher: ActionDispatcher):
        result = await dispatcher.execute("ha_list_areas", {})
        assert "areas" in result
        assert len(result["areas"]) > 0


class TestActionDispatcherErrors:
    @pytest.mark.asyncio
    async def test_unknown_action(self, dispatcher: ActionDispatcher):
        result = await dispatcher.execute("ha_nonexist", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_service_call_failure(self, dispatcher: ActionDispatcher, bridge: MockBridge):
        bridge.call_service.side_effect = RuntimeError("HA unreachable")
        result = await dispatcher.execute("ha_turn_on", {"entity_id": "light.salon"})
        assert "error" in result
