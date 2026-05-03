"""Tests for ha_sync.py — SyncManager unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from integrations.ha_entities import EntityManager
from integrations.ha_devices import DeviceManager
from integrations.ha_areas import AreaManager
from integrations.ha_sync import SyncManager
from .conftest import MockBridge


@pytest_asyncio.fixture
async def sync_setup(bridge: MockBridge):
    em = EntityManager(bridge)
    dm = DeviceManager(bridge)
    am = AreaManager(bridge)
    await em.load_entities()
    await dm.load_devices()
    await am.load_areas()
    broadcast = AsyncMock()
    sm = SyncManager(bridge, em, dm, am)
    sm.set_gui_broadcast(broadcast)
    return sm, broadcast, bridge


# ---------------------------------------------------------------------------
# Plans → HA sync
# ---------------------------------------------------------------------------

class TestPlanSync:
    @pytest.mark.asyncio
    async def test_on_plan_move_known_room(self, sync_setup):
        sm, broadcast, bridge = sync_setup
        result = await sm.on_plan_move("dev_001", 100.0, 200.0, "Garage")
        assert result["ok"] is True
        # Should broadcast plan update
        broadcast.assert_awaited()
        payload = broadcast.call_args[0][0]
        assert payload["type"] == "plan_update"
        assert payload["plan_update"]["device_id"] == "dev_001"

    @pytest.mark.asyncio
    async def test_on_plan_move_unknown_room(self, sync_setup):
        sm, broadcast, bridge = sync_setup
        result = await sm.on_plan_move("dev_001", 10.0, 20.0, "Grenier")
        assert result["ok"] is True
        broadcast.assert_awaited()


# ---------------------------------------------------------------------------
# Network → HA matching
# ---------------------------------------------------------------------------

class TestNetworkSync:
    @pytest.mark.asyncio
    async def test_match_by_mac(self, sync_setup):
        sm, _, _ = sync_setup
        result = await sm.match_network_host(mac="aa:bb:cc:dd:ee:01")
        assert result["matched"] is True
        assert result["device"]["device_id"] == "dev_001"

    @pytest.mark.asyncio
    async def test_match_by_ip(self, sync_setup):
        sm, _, _ = sync_setup
        result = await sm.match_network_host(ip="192.168.1.101")
        assert result["matched"] is True

    @pytest.mark.asyncio
    async def test_no_match(self, sync_setup):
        sm, _, _ = sync_setup
        result = await sm.match_network_host(mac="ff:ff:ff:ff:ff:ff")
        assert result["matched"] is False
        assert "suggestion" in result

    @pytest.mark.asyncio
    async def test_sync_network_devices_batch(self, sync_setup):
        sm, broadcast, _ = sync_setup
        hosts = [
            {"mac": "aa:bb:cc:dd:ee:01", "ip": "192.168.1.100", "hostname": "hue-bulb"},
            {"mac": "ff:ff:ff:ff:ff:ff", "ip": "192.168.1.200", "hostname": "unknown-host"},
        ]
        result = await sm.sync_network_devices(hosts)
        assert result["matched"] == 1
        assert result["unmatched"] == 1
        # Should broadcast topology
        broadcast.assert_awaited()


# ---------------------------------------------------------------------------
# Full snapshot
# ---------------------------------------------------------------------------

class TestSnapshot:
    @pytest.mark.asyncio
    async def test_build_full_snapshot(self, sync_setup):
        sm, _, _ = sync_setup
        snap = sm.build_full_snapshot()
        assert snap["type"] == "snapshot"
        assert "entities" in snap
        assert "devices" in snap
        assert "areas" in snap
        assert "network_topology" in snap

    @pytest.mark.asyncio
    async def test_snapshot_topology_has_router(self, sync_setup):
        sm, _, _ = sync_setup
        snap = sm.build_full_snapshot()
        topo = snap["network_topology"]
        node_ids = [n["id"] for n in topo["nodes"]]
        assert "router" in node_ids


# ---------------------------------------------------------------------------
# GUI push on state change
# ---------------------------------------------------------------------------

class TestGUIPush:
    @pytest.mark.asyncio
    async def test_state_change_pushes_to_gui(self, sync_setup):
        sm, broadcast, bridge = sync_setup
        await bridge.bus.emit("on_state_changed", {
            "entity_id": "light.salon",
            "state": "off",
            "attributes": {"friendly_name": "Lumière Salon"},
            "last_changed": "2025-01-01T13:00:00Z",
        })
        broadcast.assert_awaited()
        payload = broadcast.call_args[0][0]
        assert payload["type"] == "device_update"
        assert payload["device_update"]["entity_id"] == "light.salon"
