"""Shared test fixtures for HA integration tests."""

from __future__ import annotations

import asyncio
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Fake HA data
# ---------------------------------------------------------------------------

FAKE_ENTITIES = {
    "light.salon": {
        "entity_id": "light.salon",
        "state": "on",
        "area_id": "area_salon",
        "attributes": {"friendly_name": "Lumière Salon", "brightness": 200},
        "last_changed": "2025-01-01T12:00:00Z",
    },
    "switch.garage": {
        "entity_id": "switch.garage",
        "state": "off",
        "area_id": "area_garage",
        "attributes": {"friendly_name": "Prise Garage"},
        "last_changed": "2025-01-01T12:00:00Z",
    },
    "sensor.temperature": {
        "entity_id": "sensor.temperature",
        "state": "21.5",
        "area_id": "area_salon",
        "attributes": {"friendly_name": "Température Salon", "unit_of_measurement": "°C"},
        "last_changed": "2025-01-01T12:00:00Z",
    },
    "climate.thermostat": {
        "entity_id": "climate.thermostat",
        "state": "heat",
        "area_id": "area_salon",
        "attributes": {"friendly_name": "Thermostat", "temperature": 20},
        "last_changed": "2025-01-01T12:00:00Z",
    },
    "media_player.tv": {
        "entity_id": "media_player.tv",
        "state": "playing",
        "area_id": "area_salon",
        "attributes": {"friendly_name": "TV Salon"},
        "last_changed": "2025-01-01T12:00:00Z",
    },
}

FAKE_DEVICES = {
    "dev_001": {
        "id": "dev_001",
        "name": "Ampoule Hue Salon",
        "manufacturer": "Philips",
        "model": "LWB010",
        "area_id": "area_salon",
        "connections": [["mac", "aa:bb:cc:dd:ee:01"]],
        "identifiers": [["hue", "ABC123"]],
        "configuration_url": "http://192.168.1.100",
        "via_device_id": "dev_bridge",
    },
    "dev_002": {
        "id": "dev_002",
        "name": "Prise Garage",
        "manufacturer": "Sonoff",
        "model": "S20",
        "area_id": "area_garage",
        "connections": [["mac", "aa:bb:cc:dd:ee:02"]],
        "identifiers": [["sonoff", "DEF456"]],
        "configuration_url": "http://192.168.1.101",
        "via_device_id": None,
    },
    "dev_bridge": {
        "id": "dev_bridge",
        "name": "Hue Bridge",
        "manufacturer": "Philips",
        "model": "BSB002",
        "area_id": None,
        "connections": [["mac", "aa:bb:cc:dd:ee:ff"]],
        "identifiers": [["hue", "BRIDGE"]],
        "configuration_url": "http://192.168.1.50",
        "via_device_id": None,
    },
}

FAKE_AREAS = {
    "area_salon": {"area_id": "area_salon", "name": "Salon"},
    "area_garage": {"area_id": "area_garage", "name": "Garage"},
    "area_chambre": {"area_id": "area_chambre", "name": "Chambre"},
}


# ---------------------------------------------------------------------------
# Mock bridge
# ---------------------------------------------------------------------------

class MockBridge:
    """Lightweight mock of HomeBridge for unit tests."""

    def __init__(self) -> None:
        from integrations.home_bridge import EventBus

        self.bus = EventBus()
        self.entities: dict[str, dict] = dict(FAKE_ENTITIES)
        self.devices: dict[str, dict] = dict(FAKE_DEVICES)
        self.areas: dict[str, dict] = dict(FAKE_AREAS)
        self._connected = True

        # Mock async methods
        self.ws_command = AsyncMock(return_value={})
        self.rest_get = AsyncMock(return_value={})
        self.rest_post = AsyncMock(return_value={})
        self.call_service = AsyncMock(return_value={})

    @property
    def connected(self) -> bool:
        return self._connected


@pytest.fixture
def bridge() -> MockBridge:
    return MockBridge()
