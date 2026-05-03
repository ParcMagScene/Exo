"""Tests for ha_entities.py — EntityManager unit tests."""

from __future__ import annotations

import pytest

from integrations.ha_entities import EntityManager
from .conftest import MockBridge, FAKE_ENTITIES


class TestEntityManagerBootstrap:
    @pytest.mark.asyncio
    async def test_load_entities(self, bridge: MockBridge):
        em = EntityManager(bridge)
        await em.load_entities()
        assert len(em.list_entities()) == len(FAKE_ENTITIES)

    @pytest.mark.asyncio
    async def test_on_connected_triggers_load(self, bridge: MockBridge):
        em = EntityManager(bridge)
        await bridge.bus.emit("connected")
        # After connected event, entities should be loaded
        assert len(em.list_entities()) == len(FAKE_ENTITIES)


class TestEntityManagerQueries:
    @pytest.mark.asyncio
    async def test_get_entity(self, bridge: MockBridge):
        em = EntityManager(bridge)
        await em.load_entities()
        e = em.get_entity("light.salon")
        assert e is not None
        assert e["state"] == "on"

    @pytest.mark.asyncio
    async def test_get_entity_missing(self, bridge: MockBridge):
        em = EntityManager(bridge)
        await em.load_entities()
        assert em.get_entity("light.nonexist") is None

    @pytest.mark.asyncio
    async def test_list_by_domain(self, bridge: MockBridge):
        em = EntityManager(bridge)
        await em.load_entities()
        lights = em.list_entities_by_domain("light")
        assert len(lights) == 1
        assert lights[0]["entity_id"] == "light.salon"

    @pytest.mark.asyncio
    async def test_list_by_area(self, bridge: MockBridge):
        em = EntityManager(bridge)
        await em.load_entities()
        salon_entities = em.list_entities_by_area("area_salon")
        ids = [e["entity_id"] for e in salon_entities]
        assert "light.salon" in ids
        assert "sensor.temperature" in ids
        assert "switch.garage" not in ids

    @pytest.mark.asyncio
    async def test_search(self, bridge: MockBridge):
        em = EntityManager(bridge)
        await em.load_entities()
        results = em.search("salon")
        ids = [e["entity_id"] for e in results]
        assert "light.salon" in ids

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, bridge: MockBridge):
        em = EntityManager(bridge)
        await em.load_entities()
        results = em.search("GARAGE")
        assert any(e["entity_id"] == "switch.garage" for e in results)


class TestEntityManagerLiveUpdate:
    @pytest.mark.asyncio
    async def test_state_changed_event(self, bridge: MockBridge):
        em = EntityManager(bridge)
        await em.load_entities()
        # Emit a state change
        await bridge.bus.emit("on_state_changed", {
            "entity_id": "light.salon",
            "state": "off",
            "attributes": {"friendly_name": "Lumière Salon", "brightness": 0},
        })
        e = em.get_entity("light.salon")
        assert e["state"] == "off"

    @pytest.mark.asyncio
    async def test_update_entity_state_manual(self, bridge: MockBridge):
        em = EntityManager(bridge)
        await em.load_entities()
        em.update_entity_state({
            "new_state": {"entity_id": "light.salon", "state": "off"},
        })
        assert em.get_entity("light.salon")["state"] == "off"


class TestEntityManagerSummary:
    @pytest.mark.asyncio
    async def test_summary(self, bridge: MockBridge):
        em = EntityManager(bridge)
        await em.load_entities()
        s = em.summary("light.salon")
        assert s is not None
        assert s["entity_id"] == "light.salon"
        assert s["domain"] == "light"
        assert s["name"] == "Lumière Salon"

    @pytest.mark.asyncio
    async def test_summary_missing(self, bridge: MockBridge):
        em = EntityManager(bridge)
        await em.load_entities()
        assert em.summary("nonexist.x") is None

    @pytest.mark.asyncio
    async def test_all_summaries(self, bridge: MockBridge):
        em = EntityManager(bridge)
        await em.load_entities()
        summaries = em.all_summaries()
        assert len(summaries) == len(FAKE_ENTITIES)

    @pytest.mark.asyncio
    async def test_all_summaries_filtered(self, bridge: MockBridge):
        em = EntityManager(bridge)
        await em.load_entities()
        summaries = em.all_summaries(domain="switch")
        assert len(summaries) == 1
        assert summaries[0]["entity_id"] == "switch.garage"
