"""
EXO Domotique v2 — Modèle de données unifié
Structures : Device, Room, Link, DeviceSource, DeviceType, Capability,
             LinkType, Protocol, Connectivity, DeviceEvent
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class DeviceSource(str, Enum):
    HUE = "hue"
    TAPO = "tapo"
    IKEA = "ikea"
    TPLINK = "tplink"
    EZVIZ = "ezviz"
    SAMSUNG = "samsung"
    VOLTALIS = "voltalis"
    ECHO = "echo"
    NETWORK = "network"
    OTHER = "other"


class DeviceType(str, Enum):
    LIGHT = "light"
    PLUG = "plug"
    CAMERA = "camera"
    TV = "tv"
    SOUNDBAR = "soundbar"
    SPEAKER = "speaker"
    HEATER = "heater"
    SENSOR = "sensor"
    ROUTER = "router"
    PC = "pc"
    PHONE = "phone"
    NAS = "nas"
    UNKNOWN = "unknown"


class Capability(str, Enum):
    ON_OFF = "on_off"
    BRIGHTNESS = "brightness"
    COLOR = "color"
    TEMP = "temp"
    VOLUME = "volume"
    SOURCE = "source"
    MUTE = "mute"
    SNAPSHOT = "snapshot"
    STREAM = "stream"
    MODE = "mode"
    ENERGY = "energy"
    TTS = "tts"


class LinkType(str, Enum):
    ETH = "eth"
    WIFI = "wifi"
    IOT = "iot"
    UNKNOWN = "unknown"


# ── v2 additions ─────────────────────────────────────────────

class Protocol(str, Enum):
    HUE = "hue"
    TAPO = "tapo"
    EZVIZ = "ezviz"
    SAMSUNG = "samsung"
    ECHO = "echo"
    MDNS = "mdns"
    SSDP = "ssdp"
    UNKNOWN = "unknown"


class Connectivity(str, Enum):
    ETH = "eth"
    WIFI = "wifi"
    IOT = "iot"
    UNKNOWN = "unknown"


@dataclass
class DeviceEvent:
    """Single event on a device (state change, motion, etc.)."""
    timestamp: float
    event_type: str          # "state_change", "motion", "offline", "online"
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "data": dict(self.data),
        }


@dataclass
class Device:
    id_exo: str
    id_origin: str
    source: DeviceSource
    type: DeviceType
    name: str
    room_id: str = ""
    capabilities: set[Capability] = field(default_factory=set)
    state: dict = field(default_factory=dict)
    ip: str = ""
    mac: str = ""
    vendor: str = ""
    last_seen: float = field(default_factory=time.time)
    online: bool = True
    # v2 extensions
    protocol: Protocol = Protocol.UNKNOWN
    connectivity: Connectivity = Connectivity.UNKNOWN
    signal_strength: int | None = None
    last_event: DeviceEvent | None = None
    energy: dict = field(default_factory=dict)    # {"consumption_wh": ..., "power_w": ...}
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "id_exo": self.id_exo,
            "id_origin": self.id_origin,
            "source": self.source.value,
            "type": self.type.value,
            "name": self.name,
            "room_id": self.room_id,
            "capabilities": sorted(c.value for c in self.capabilities),
            "state": dict(self.state),
            "ip": self.ip,
            "mac": self.mac,
            "vendor": self.vendor,
            "last_seen": self.last_seen,
            "online": self.online,
            "protocol": self.protocol.value,
            "connectivity": self.connectivity.value,
            "signal_strength": self.signal_strength,
            "last_event": self.last_event.to_dict() if self.last_event else None,
            "energy": dict(self.energy),
            "tags": list(self.tags),
        }
        return d


@dataclass
class Room:
    id: str
    name: str
    device_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "device_ids": list(self.device_ids),
        }


@dataclass
class Link:
    from_id: str
    to_id: str
    type: LinkType = LinkType.UNKNOWN

    def to_dict(self) -> dict:
        return {
            "from_id": self.from_id,
            "to_id": self.to_id,
            "type": self.type.value,
        }
