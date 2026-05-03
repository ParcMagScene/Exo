"""Tests for ha_areas.py — AreaManager unit tests."""

from __future__ import annotations

import pytest

from integrations.ha_areas import AreaManager
from .conftest import MockBridge, FAKE_AREAS


class TestAreaManagerBootstrap:
    @pytest.mark.asyncio
    async def test_load_areas(self, bridge: MockBridge):
        am = AreaManager(bridge)
        await am.load_areas()
        assert len(am.list_areas()) == len(FAKE_AREAS)

    @pytest.mark.asyncio
    async def test_on_connected_triggers_load(self, bridge: MockBridge):
        am = AreaManager(bridge)
        await bridge.bus.emit("connected")
        assert len(am.list_areas()) == len(FAKE_AREAS)


class TestAreaManagerQueries:
    @pytest.mark.asyncio
    async def test_get_area(self, bridge: MockBridge):
        am = AreaManager(bridge)
        await am.load_areas()
        a = am.get_area("area_salon")
        assert a is not None
        assert a["name"] == "Salon"

    @pytest.mark.asyncio
    async def test_get_area_missing(self, bridge: MockBridge):
        am = AreaManager(bridge)
        await am.load_areas()
        assert am.get_area("area_nonexist") is None

    @pytest.mark.asyncio
    async def test_get_devices_in_area(self, bridge: MockBridge):
        am = AreaManager(bridge)
        await am.load_areas()
        devs = am.get_devices_in_area("area_salon")
        assert "dev_001" in devs

    @pytest.mark.asyncio
    async def test_get_entities_in_area(self, bridge: MockBridge):
        am = AreaManager(bridge)
        await am.load_areas()
        ents = am.get_entities_in_area("area_salon")
        assert "light.salon" in ents

    @pytest.mark.asyncio
    async def test_search(self, bridge: MockBridge):
        am = AreaManager(bridge)
        await am.load_areas()
        results = am.search("garage")
        assert len(results) == 1
        assert results[0]["name"] == "Garage"

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, bridge: MockBridge):
        am = AreaManager(bridge)
        await am.load_areas()
        results = am.search("SALON")
        assert len(results) == 1


class TestAreaManagerAssignment:
    @pytest.mark.asyncio
    async def test_assign_device_to_area(self, bridge: MockBridge):
        am = AreaManager(bridge)
        await am.load_areas()
        await am.assign_device_to_area("dev_001", "area_chambre")
        bridge.ws_command.assert_awaited_with(
            "config/device_registry/update",
            device_id="dev_001",
            area_id="area_chambre",
        )

    @pytest.mark.asyncio
    async def test_assign_entity_to_area(self, bridge: MockBridge):
        am = AreaManager(bridge)
        await am.load_areas()
        await am.assign_entity_to_area("light.salon", "area_chambre")
        bridge.ws_command.assert_awaited_with(
            "config/entity_registry/update",
            entity_id="light.salon",
            area_id="area_chambre",
        )


class TestAreaManagerPlanSync:
    @pytest.mark.asyncio
    async def test_update_plan_position_known_room(self, bridge: MockBridge):
        am = AreaManager(bridge)
        await am.load_areas()
        # Track bus emits
        emitted = []
        bridge.bus.on("plan_device_moved", lambda d: emitted.append(d))

        await am.update_plan_position("dev_001", 150.0, 200.0, "Garage")
        # Should have called ws_command to reassign area
        bridge.ws_command.assert_awaited()
        # Should have emitted plan_device_moved
        assert len(emitted) == 1
        assert emitted[0]["room"] == "Garage"

    @pytest.mark.asyncio
    async def test_update_plan_position_unknown_room(self, bridge: MockBridge):
        am = AreaManager(bridge)
        await am.load_areas()

        emitted = []
        bridge.bus.on("plan_device_moved", lambda d: emitted.append(d))

        await am.update_plan_position("dev_001", 10.0, 20.0, "Grenier")
        # Should still emit event even if room not found in HA
        assert len(emitted) == 1
        assert emitted[0]["room"] == "Grenier"


class TestAreaManagerSummary:
    @pytest.mark.asyncio
    async def test_summary(self, bridge: MockBridge):
        am = AreaManager(bridge)
        await am.load_areas()
        s = am.summary("area_salon")
        assert s is not None
        assert s["area_id"] == "area_salon"
        assert s["name"] == "Salon"

    @pytest.mark.asyncio
    async def test_all_summaries(self, bridge: MockBridge):
        am = AreaManager(bridge)
        await am.load_areas()
        summaries = am.all_summaries()
        assert len(summaries) == len(FAKE_AREAS)
