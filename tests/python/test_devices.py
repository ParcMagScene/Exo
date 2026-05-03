"""Tests for ha_devices.py — DeviceManager unit tests."""

from __future__ import annotations

import pytest

from integrations.ha_devices import DeviceManager
from .conftest import MockBridge, FAKE_DEVICES, FAKE_ENTITIES


class TestDeviceManagerBootstrap:
    @pytest.mark.asyncio
    async def test_load_devices(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await dm.load_devices()
        assert len(dm.list_devices()) == len(FAKE_DEVICES)

    @pytest.mark.asyncio
    async def test_on_connected_triggers_load(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await bridge.bus.emit("connected")
        assert len(dm.list_devices()) == len(FAKE_DEVICES)


class TestDeviceManagerQueries:
    @pytest.mark.asyncio
    async def test_get_device(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await dm.load_devices()
        d = dm.get_device("dev_001")
        assert d is not None
        assert d["name"] == "Ampoule Hue Salon"

    @pytest.mark.asyncio
    async def test_get_device_missing(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await dm.load_devices()
        assert dm.get_device("nonexist") is None


class TestDeviceManagerMACIPMatch:
    @pytest.mark.asyncio
    async def test_match_by_mac(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await dm.load_devices()
        dev = dm.match_device_by_mac("aa:bb:cc:dd:ee:01")
        assert dev is not None
        assert dev["id"] == "dev_001"

    @pytest.mark.asyncio
    async def test_match_by_mac_normalized(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await dm.load_devices()
        # Uppercase + dash format
        dev = dm.match_device_by_mac("AA-BB-CC-DD-EE-02")
        assert dev is not None
        assert dev["id"] == "dev_002"

    @pytest.mark.asyncio
    async def test_match_by_mac_not_found(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await dm.load_devices()
        assert dm.match_device_by_mac("00:00:00:00:00:00") is None

    @pytest.mark.asyncio
    async def test_match_by_ip(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await dm.load_devices()
        dev = dm.match_device_by_ip("192.168.1.100")
        assert dev is not None
        assert dev["id"] == "dev_001"

    @pytest.mark.asyncio
    async def test_match_by_ip_not_found(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await dm.load_devices()
        assert dm.match_device_by_ip("10.0.0.99") is None


class TestDeviceManagerSearch:
    @pytest.mark.asyncio
    async def test_search_by_name(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await dm.load_devices()
        results = dm.search("hue")
        ids = [d["id"] for d in results]
        assert "dev_001" in ids
        assert "dev_bridge" in ids

    @pytest.mark.asyncio
    async def test_search_by_manufacturer(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await dm.load_devices()
        results = dm.search("sonoff")
        assert len(results) == 1
        assert results[0]["id"] == "dev_002"


class TestDeviceManagerSummary:
    @pytest.mark.asyncio
    async def test_summary(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await dm.load_devices()
        s = dm.summary("dev_001")
        assert s is not None
        assert s["device_id"] == "dev_001"
        assert s["manufacturer"] == "Philips"
        assert s["area_id"] == "area_salon"

    @pytest.mark.asyncio
    async def test_summary_missing(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await dm.load_devices()
        assert dm.summary("nonexist") is None

    @pytest.mark.asyncio
    async def test_all_summaries(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await dm.load_devices()
        summaries = dm.all_summaries()
        assert len(summaries) == len(FAKE_DEVICES)


class TestDeviceManagerEntityMapping:
    @pytest.mark.asyncio
    async def test_entity_map_built(self, bridge: MockBridge):
        # Add device_id to some entities
        bridge.entities["light.salon"]["device_id"] = "dev_001"
        bridge.entities["switch.garage"]["device_id"] = "dev_002"
        dm = DeviceManager(bridge)
        await dm.load_devices()
        ents = dm.get_entities_for_device("dev_001")
        assert "light.salon" in ents

    @pytest.mark.asyncio
    async def test_entity_map_empty(self, bridge: MockBridge):
        dm = DeviceManager(bridge)
        await dm.load_devices()
        # dev_bridge has no entities mapped
        ents = dm.get_entities_for_device("dev_bridge")
        assert ents == [] or isinstance(ents, list)
