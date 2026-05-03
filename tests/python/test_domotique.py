#!/usr/bin/env python3
"""Tests unitaires — HomeGraphManager + Domotique v2."""

import asyncio
import sys
from pathlib import Path

import pytest

from domotique.models import Device, Room, Link, DeviceSource, DeviceType, Capability, LinkType


# ═══════════════════════════════════════════════════════
#  Tests Models
# ═══════════════════════════════════════════════════════

class TestDevice:
    def test_to_dict_basic(self):
        d = Device(
            id_exo="light_1",
            id_origin="hue:123",
            source=DeviceSource.HUE,
            type=DeviceType.LIGHT,
            name="Lampe salon",
            capabilities=[Capability.ON_OFF, Capability.BRIGHTNESS],
        )
        out = d.to_dict()
        assert out["id_exo"] == "light_1"
        assert out["source"] == "hue"
        assert out["type"] == "light"
        assert "on_off" in out["capabilities"]
        assert "brightness" in out["capabilities"]

    def test_to_dict_with_state(self):
        d = Device(
            id_exo="tv_1",
            id_origin="samsung:456",
            source=DeviceSource.SAMSUNG,
            type=DeviceType.TV,
            name="TV Salon",
            state={"on": True, "volume": 30},
        )
        out = d.to_dict()
        assert out["state"]["on"] is True
        assert out["state"]["volume"] == 30

    def test_default_values(self):
        d = Device(
            id_exo="x",
            id_origin="y",
            source=DeviceSource.OTHER,
            type=DeviceType.UNKNOWN,
            name="Test",
        )
        assert d.room_id == ""
        assert d.capabilities == set()
        assert d.state == {}
        assert d.online is True


class TestRoom:
    def test_to_dict(self):
        r = Room(id="salon", name="Salon", device_ids=["light_1", "tv_1"])
        out = r.to_dict()
        assert out["id"] == "salon"
        assert out["name"] == "Salon"
        assert len(out["device_ids"]) == 2


class TestLink:
    def test_to_dict(self):
        lk = Link(from_id="device_a", to_id="router", type=LinkType.WIFI)
        out = lk.to_dict()
        assert out["from_id"] == "device_a"
        assert out["to_id"] == "router"
        assert out["type"] == "wifi"


# ═══════════════════════════════════════════════════════
#  Tests HomeGraphManager
# ═══════════════════════════════════════════════════════

from domotique.homegraph_server import HomeGraphManager


class TestHomeGraphManager:
    def setup_method(self):
        self.hg = HomeGraphManager()

    def test_merge_devices(self):
        devices = [
            {
                "id_origin": "hue:1",
                "source": "hue",
                "type": "light",
                "name": "Lampe bureau",
                "capabilities": ["on_off", "brightness"],
                "state": {"on": True},
            },
            {
                "id_origin": "tapo:2",
                "source": "tapo",
                "type": "plug",
                "name": "Prise salon",
                "capabilities": ["on_off"],
                "state": {"on": False},
            },
        ]
        self.hg.merge_devices("hue", devices[:1])
        self.hg.merge_devices("tapo", devices[1:])
        assert len(self.hg.list_devices()) == 2

    def test_merge_rooms(self):
        rooms = [
            {"id": "salon", "name": "Salon"},
            {"id": "bureau", "name": "Bureau"},
        ]
        self.hg.merge_rooms(rooms)
        assert len(self.hg.list_rooms()) == 2

    def test_assign_device_to_room(self):
        self.hg.merge_devices("hue", [
            {"id_origin": "hue:1", "source": "hue", "type": "light",
             "name": "L1", "capabilities": [], "state": {}},
        ])
        self.hg.add_room("salon", "Salon")
        devs = self.hg.list_devices()
        assert len(devs) == 1
        dev_id = devs[0]["id_exo"]
        self.hg.assign_device_to_room(dev_id, "salon")
        rooms = self.hg.list_rooms()
        assert dev_id in rooms[0]["device_ids"]

    def test_find_device_by_name(self):
        self.hg.merge_devices("samsung", [
            {"id_origin": "samsung:tv1", "source": "samsung", "type": "tv",
             "name": "TV Salon", "capabilities": ["on_off"], "state": {}},
        ])
        result = self.hg.find_device_by_name("tv salon")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0]["name"] == "TV Salon"

    def test_find_device_by_name_not_found(self):
        result = self.hg.find_device_by_name("inexistant")
        assert result == []

    def test_find_devices_by_type(self):
        self.hg.merge_devices("hue", [
            {"id_origin": "hue:1", "source": "hue", "type": "light",
             "name": "L1", "capabilities": [], "state": {}},
            {"id_origin": "hue:2", "source": "hue", "type": "light",
             "name": "L2", "capabilities": [], "state": {}},
        ])
        self.hg.merge_devices("samsung", [
            {"id_origin": "samsung:tv1", "source": "samsung", "type": "tv",
             "name": "TV", "capabilities": [], "state": {}},
        ])
        lights = self.hg.find_devices_by_type("light")
        assert len(lights) == 2

    def test_update_device_state(self):
        self.hg.merge_devices("hue", [
            {"id_origin": "hue:1", "source": "hue", "type": "light",
             "name": "L1", "capabilities": [], "state": {"on": False}},
        ])
        devs = self.hg.list_devices()
        dev_id = devs[0]["id_exo"]
        ok = self.hg.update_device_state(dev_id, {"on": True, "brightness": 80})
        assert ok is True
        dev = self.hg.get_device(dev_id)
        assert dev["state"]["on"] is True
        assert dev["state"]["brightness"] == 80

    def test_update_device_state_not_found(self):
        ok = self.hg.update_device_state("nonexistent", {"on": True})
        assert ok is False

    def test_list_devices_by_room(self):
        self.hg.merge_devices("hue", [
            {"id_origin": "hue:1", "source": "hue", "type": "light",
             "name": "L1", "capabilities": [], "state": {}},
            {"id_origin": "hue:2", "source": "hue", "type": "light",
             "name": "L2", "capabilities": [], "state": {}},
        ])
        self.hg.add_room("salon", "Salon")
        devs = self.hg.list_devices()
        self.hg.assign_device_to_room(devs[0]["id_exo"], "salon")
        salon_devs = self.hg.list_devices_by_room("salon")
        assert len(salon_devs) == 1

    def test_merge_links(self):
        links = [
            {"from_id": "dev1", "to_id": "router", "type": "wifi"},
            {"from_id": "dev2", "to_id": "router", "type": "eth"},
        ]
        self.hg.merge_links(links)
        net = self.hg.get_network_links()
        assert len(net) == 2


# ═══════════════════════════════════════════════════════
#  Tests SamsungService
# ═══════════════════════════════════════════════════════

from domotique.samsung_service import SamsungService


class TestSamsungService:
    def setup_method(self):
        self.svc = SamsungService()

    def test_not_configured(self):
        assert self.svc.configured is False

    @pytest.mark.asyncio
    async def test_list_devices_empty(self):
        devices = await self.svc.list_devices()
        assert isinstance(devices, list)


# ═══════════════════════════════════════════════════════
#  Tests VoltalisService
# ═══════════════════════════════════════════════════════

from domotique.voltalis_service import VoltalisService


class TestVoltalisService:
    def setup_method(self):
        self.svc = VoltalisService()

    def test_not_configured(self):
        assert self.svc.configured is False

    @pytest.mark.asyncio
    async def test_list_devices_empty(self):
        devices = await self.svc.list_devices()
        assert isinstance(devices, list)


# ═══════════════════════════════════════════════════════
#  Tests EchoService
# ═══════════════════════════════════════════════════════

from domotique.echo_service import EchoService


class TestEchoService:
    def setup_method(self):
        self.svc = EchoService()

    def test_list_devices_empty(self):
        devices = self.svc.list_devices()
        assert isinstance(devices, list)

    @pytest.mark.asyncio
    async def test_get_state_not_found(self):
        state = await self.svc.get_state("nonexistent")
        assert state is None

    @pytest.mark.asyncio
    async def test_apply_command_unknown(self):
        result = await self.svc.apply_command("echo:x", "unknown_cmd")
        assert result["ok"] is False


# ═══════════════════════════════════════════════════════
#  Tests NetworkMapService
# ═══════════════════════════════════════════════════════

from network.network_map_service import NetworkMapService


class TestNetworkMapService:
    def setup_method(self):
        self.svc = NetworkMapService()

    def test_list_nodes_empty(self):
        nodes = self.svc.list_nodes()
        assert isinstance(nodes, list)
        assert len(nodes) == 0

    def test_list_links_empty(self):
        links = self.svc.list_links()
        assert isinstance(links, list)

    def test_get_node_not_found(self):
        node = self.svc.get_node_details("FF:FF:FF:FF:FF:FF")
        assert node is None

    def test_vendor_lookup_no_oui(self):
        vendor = self.svc.get_vendor("AA:BB:CC:DD:EE:FF")
        assert vendor == ""

    def test_capabilities(self):
        caps = self.svc.capabilities()
        assert "scan_full" in caps
        assert "scan_fast" in caps
        assert "get_topology" in caps

    def test_metadata(self):
        meta = self.svc.metadata()
        assert meta["name"] == "network_map"
        assert meta["version"] == "v2"

    def test_health_check(self):
        hc = self.svc.health_check()
        assert hc["status"] == "ok"
        assert hc["devices_count"] == 0

    def test_get_topology_empty(self):
        topo = self.svc.get_topology()
        assert "nodes" in topo
        assert "links" in topo

    def test_get_latency_unknown(self):
        lat = self.svc.get_latency("1.2.3.4")
        assert lat is None

    def test_classify_device(self):
        dtype = self.svc.classify_device({"vendor": "Samsung", "type": "unknown"})
        assert dtype == "tv"

    def test_get_metrics(self):
        m = self.svc.get_metrics()
        assert "scans_total" in m
        assert "devices_found" in m

    def test_restart(self):
        result = self.svc.restart()
        assert result["status"] == "restarted"

    def test_export_json(self):
        data = self.svc.export_json()
        import json
        parsed = json.loads(data)
        assert "devices" in parsed
        assert "topology" in parsed


# ═══════════════════════════════════════════════════════
#  Tests NetworkMap v2 — VendorLookup
# ═══════════════════════════════════════════════════════

import tempfile
from network.vendor_lookup import VendorLookup


class TestVendorLookup:
    def test_empty_lookup(self):
        vl = VendorLookup()
        assert vl.lookup("AA:BB:CC:DD:EE:FF") == ""
        assert vl.count == 0

    def test_load_and_lookup(self):
        content = (
            "AA-BB-CC   (hex)   TestVendor Inc.\n"
            "11-22-33   (hex)   Another Corp\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            f.flush()
            vl = VendorLookup(f.name)
        assert vl.count == 2
        assert vl.lookup("AA:BB:CC:DD:EE:FF") == "TestVendor Inc."
        assert vl.lookup("11:22:33:44:55:66") == "Another Corp"
        assert vl.lookup("FF:FF:FF:FF:FF:FF") == ""

    def test_lookup_case_insensitive_mac(self):
        content = "AA-BB-CC   (hex)   TestVendor\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            f.flush()
            vl = VendorLookup(f.name)
        assert vl.lookup("aa:bb:cc:dd:ee:ff") == "TestVendor"
        assert vl.lookup("AA-BB-CC-DD-EE-FF") == "TestVendor"

    def test_load_missing_file(self):
        vl = VendorLookup("/nonexistent/path/oui.txt")
        assert vl.count == 0

    def test_stats(self):
        vl = VendorLookup()
        s = vl.stats()
        assert s["entries"] == 0
        assert s["loaded"] is False


# ═══════════════════════════════════════════════════════
#  Tests NetworkMap v2 — DeviceClassifier
# ═══════════════════════════════════════════════════════

from network.device_classifier import DeviceClassifier


class TestDeviceClassifier:
    def setup_method(self):
        self.cls = DeviceClassifier()

    def test_already_classified(self):
        assert self.cls.classify({"type": "tv"}) == "tv"

    def test_unknown_stays_unknown(self):
        assert self.cls.classify({"type": "unknown"}) == "unknown"
        assert self.cls.classify({}) == "unknown"

    def test_classify_by_service_mdns(self):
        dev = {"type": "unknown", "services": ["_hue._tcp"]}
        assert self.cls.classify(dev) == "light"

    def test_classify_by_ssdp_manufacturer(self):
        dev = {"type": "unknown", "ssdp_manufacturer": "Samsung TV"}
        assert self.cls.classify(dev) == "tv"

    def test_classify_by_hostname(self):
        dev = {"type": "unknown", "hostname": "echo-dot-salon"}
        assert self.cls.classify(dev) == "speaker"

    def test_classify_by_vendor(self):
        dev = {"type": "unknown", "vendor": "Philips Lighting"}
        assert self.cls.classify(dev) == "light"

    def test_classify_pc_by_vendor(self):
        dev = {"type": "unknown", "vendor": "Intel Corporate"}
        assert self.cls.classify(dev) == "pc"

    def test_classify_camera(self):
        dev = {"type": "unknown", "hostname": "EZVIZ-C6N"}
        assert self.cls.classify(dev) == "camera"

    def test_classify_printer(self):
        dev = {"type": "unknown", "services": ["_ipp._tcp"]}
        assert self.cls.classify(dev) == "printer"

    def test_classify_nas(self):
        dev = {"type": "unknown", "hostname": "synology-ds220"}
        assert self.cls.classify(dev) == "nas"

    def test_classify_batch(self):
        devices = [
            {"type": "unknown", "vendor": "Samsung"},
            {"type": "unknown", "hostname": "echo-dot"},
            {"type": "light"},
        ]
        result = self.cls.classify_batch(devices)
        assert result[0]["type"] == "tv"
        assert result[1]["type"] == "speaker"
        assert result[2]["type"] == "light"

    def test_classify_by_name_fallback(self):
        dev = {"type": "unknown", "name": "TV-Salon"}
        assert self.cls.classify(dev) == "tv"

    def test_classify_plug(self):
        dev = {"type": "unknown", "services": ["_tapo._tcp"]}
        assert self.cls.classify(dev) == "plug"

    def test_classify_iot_vendor(self):
        dev = {"type": "unknown", "vendor": "Espressif Inc."}
        assert self.cls.classify(dev) == "iot"


# ═══════════════════════════════════════════════════════
#  Tests NetworkMap v2 — TopologyBuilder
# ═══════════════════════════════════════════════════════

from network.topology_builder import TopologyBuilder


class TestTopologyBuilder:
    def setup_method(self):
        self.tb = TopologyBuilder()

    def _sample_devices(self):
        return [
            {"ip": "192.168.1.1", "mac": "AA:BB:CC:00:00:01", "vendor": "", "type": "router", "online": True},
            {"ip": "192.168.1.10", "mac": "AA:BB:CC:00:00:10", "vendor": "Intel", "type": "pc", "online": True},
            {"ip": "192.168.1.20", "mac": "AA:BB:CC:00:00:20", "vendor": "Philips", "type": "light", "online": True},
        ]

    def test_build_basic(self):
        topo = self.tb.build(self._sample_devices(), gateway_ip="192.168.1.1", gateway_mac="AA:BB:CC:00:00:01")
        assert topo["stats"]["total_nodes"] == 3
        assert topo["stats"]["total_links"] == 2  # pc→gw + light→gw
        assert topo["gateway"]["ip"] == "192.168.1.1"

    def test_nodes_have_required_fields(self):
        topo = self.tb.build(self._sample_devices(), gateway_ip="192.168.1.1")
        for node in topo["nodes"]:
            assert "id" in node
            assert "ip" in node
            assert "mac" in node
            assert "type" in node
            assert "is_gateway" in node
            assert "is_exo" in node
            assert "priority" in node

    def test_gateway_detection_auto(self):
        devices = self._sample_devices()
        topo = self.tb.build(devices)
        assert topo["gateway"]["ip"] == "192.168.1.1"

    def test_gateway_priority(self):
        topo = self.tb.build(self._sample_devices(), gateway_ip="192.168.1.1")
        gw_node = [n for n in topo["nodes"] if n["is_gateway"]][0]
        assert gw_node["priority"] == 0

    def test_link_types(self):
        topo = self.tb.build(self._sample_devices(), gateway_ip="192.168.1.1", gateway_mac="AA:BB:CC:00:00:01")
        link_types = {l["from_id"]: l["type"] for l in topo["links"]}
        # PC → eth, light → iot
        assert link_types.get("AA:BB:CC:00:00:10") == "eth"
        assert link_types.get("AA:BB:CC:00:00:20") == "iot"

    def test_latencies_in_links(self):
        latencies = {
            "192.168.1.10": {"reachable": True, "latency_ms": 2.5},
            "192.168.1.20": {"reachable": True, "latency_ms": 15.0},
        }
        topo = self.tb.build(self._sample_devices(), gateway_ip="192.168.1.1",
                             gateway_mac="AA:BB:CC:00:00:01", latencies=latencies)
        for link in topo["links"]:
            assert "latency_ms" in link

    def test_empty_devices(self):
        topo = self.tb.build([])
        assert topo["stats"]["total_nodes"] == 0
        assert topo["stats"]["total_links"] == 0

    def test_get_topology_after_build(self):
        self.tb.build(self._sample_devices(), gateway_ip="192.168.1.1")
        topo = self.tb.get_topology()
        assert len(topo["nodes"]) == 3

    def test_get_links(self):
        self.tb.build(self._sample_devices(), gateway_ip="192.168.1.1", gateway_mac="AA:BB:CC:00:00:01")
        links = self.tb.get_links()
        assert len(links) == 2


# ═══════════════════════════════════════════════════════
#  Tests NetworkMap v2 — ARPScanner
# ═══════════════════════════════════════════════════════

from unittest.mock import AsyncMock, MagicMock, patch
from network.arp_scanner import ARPScanner


class TestARPScanner:
    def setup_method(self):
        self.scanner = ARPScanner()

    @pytest.mark.asyncio
    async def test_scan_parses_output(self):
        fake_output = (
            "Interface: 192.168.1.100 --- 0xd\n"
            "  Internet Address      Physical Address      Type\n"
            "  192.168.1.1            aa-bb-cc-00-00-01     dynamic\n"
            "  192.168.1.10           11-22-33-44-55-66     dynamic\n"
            "  192.168.1.255          ff-ff-ff-ff-ff-ff     static\n"
        )
        proc_mock = AsyncMock()
        proc_mock.communicate.return_value = (fake_output.encode(), b"")
        proc_mock.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=proc_mock):
            results = await self.scanner.scan()

        assert len(results) == 2  # ff:ff:ff:ff:ff:ff filtered
        ips = [r["ip"] for r in results]
        assert "192.168.1.1" in ips
        assert "192.168.1.10" in ips

    @pytest.mark.asyncio
    async def test_gateway_detection(self):
        fake_output = "  192.168.1.1   aa-bb-cc-00-00-01     dynamic\n"
        proc_mock = AsyncMock()
        proc_mock.communicate.return_value = (fake_output.encode(), b"")

        with patch("asyncio.create_subprocess_exec", return_value=proc_mock):
            await self.scanner.scan()

        assert self.scanner.gateway_ip == "192.168.1.1"
        assert self.scanner.gateway_mac == "AA:BB:CC:00:00:01"

    @pytest.mark.asyncio
    async def test_vendor_lookup_called(self):
        fake_output = "  192.168.1.10   11-22-33-44-55-66     dynamic\n"
        proc_mock = AsyncMock()
        proc_mock.communicate.return_value = (fake_output.encode(), b"")

        vendor_fn = MagicMock(return_value="TestVendor")
        scanner = ARPScanner(vendor_lookup=vendor_fn)

        with patch("asyncio.create_subprocess_exec", return_value=proc_mock):
            results = await scanner.scan()

        vendor_fn.assert_called_once_with("11:22:33:44:55:66")
        assert results[0]["vendor"] == "TestVendor"

    @pytest.mark.asyncio
    async def test_scan_timeout(self):
        with patch("asyncio.create_subprocess_exec", side_effect=asyncio.TimeoutError):
            results = await self.scanner.scan()
        assert results == []

    def test_metrics_initial(self):
        m = self.scanner.metrics()
        assert m["gateway_ip"] == ""
        assert m["last_scan"] == 0

    @pytest.mark.asyncio
    async def test_mac_format_normalized(self):
        fake_output = "  192.168.1.5   AB-cd-EF-12-34-56     dynamic\n"
        proc_mock = AsyncMock()
        proc_mock.communicate.return_value = (fake_output.encode(), b"")

        with patch("asyncio.create_subprocess_exec", return_value=proc_mock):
            results = await self.scanner.scan()

        assert results[0]["mac"] == "AB:CD:EF:12:34:56"


# ═══════════════════════════════════════════════════════
#  Tests NetworkMap v2 — MDNSScanner
# ═══════════════════════════════════════════════════════

from network.mdns_scanner import MDNSScanner


class TestMDNSScanner:
    def setup_method(self):
        self.scanner = MDNSScanner()

    @pytest.mark.asyncio
    async def test_scan_resolves_ips(self):
        async def fake_gethostbyaddr(ip):
            return (f"host-{ip.split('.')[-1]}", [], [ip])

        with patch("socket.gethostbyaddr", side_effect=lambda ip: (f"host-{ip.split('.')[-1]}", [], [ip])):
            results = await self.scanner.scan(["192.168.1.10", "192.168.1.20"])

        assert len(results) == 2
        assert results["192.168.1.10"]["hostname"] == "host-10"

    @pytest.mark.asyncio
    async def test_scan_handles_failures(self):
        import socket
        with patch("socket.gethostbyaddr", side_effect=socket.herror("not found")):
            results = await self.scanner.scan(["192.168.1.10"])
        assert len(results) == 0

    def test_infer_type_tv(self):
        assert MDNSScanner._infer_type("Samsung-TV-Salon") == "tv"

    def test_infer_type_speaker(self):
        assert MDNSScanner._infer_type("echo-dot-kitchen") == "speaker"

    def test_infer_type_phone(self):
        assert MDNSScanner._infer_type("iPhone-de-Alex") == "phone"

    def test_infer_type_camera(self):
        assert MDNSScanner._infer_type("EZVIZ-C6N-001") == "camera"

    def test_infer_type_unknown(self):
        assert MDNSScanner._infer_type("random-device") == "unknown"

    def test_infer_services_hue(self):
        svcs = MDNSScanner._infer_services("Philips-HUE-Bridge")
        assert "_hue._tcp" in svcs

    def test_infer_services_chromecast(self):
        svcs = MDNSScanner._infer_services("Chromecast-Salon")
        assert "_googlecast._tcp" in svcs

    def test_infer_services_none(self):
        svcs = MDNSScanner._infer_services("generic-host")
        assert svcs == []


# ═══════════════════════════════════════════════════════
#  Tests NetworkMap v2 — SSDPScanner
# ═══════════════════════════════════════════════════════

from network.ssdp_scanner import SSDPScanner


class TestSSDPScanner:
    def setup_method(self):
        self.scanner = SSDPScanner()

    def test_parse_headers(self):
        text = (
            "HTTP/1.1 200 OK\r\n"
            "SERVER: Linux UPnP/1.0 Samsung\r\n"
            "LOCATION: http://192.168.1.50:8080/desc.xml\r\n"
            "ST: ssdp:all\r\n"
        )
        headers = SSDPScanner._parse_headers(text)
        assert "server" in headers
        assert "Samsung" in headers["server"]
        assert "location" in headers

    def test_extract_manufacturer_samsung(self):
        headers = {"server": "Linux/3.14 UPnP/1.0 Samsung TV"}
        assert SSDPScanner._extract_manufacturer(headers) == "Samsung"

    def test_extract_manufacturer_lg(self):
        headers = {"server": "Linux UPnP LG WebOS"}
        assert SSDPScanner._extract_manufacturer(headers) == "LG"

    def test_extract_manufacturer_unknown(self):
        headers = {"server": "Generic UPnP Device"}
        assert SSDPScanner._extract_manufacturer(headers) == ""

    def test_extract_manufacturer_google(self):
        headers = {"server": "Linux UPnP/1.0 Google Cast"}
        assert SSDPScanner._extract_manufacturer(headers) == "Google"

    def test_scan_with_timeout(self):
        with patch("socket.socket") as mock_sock:
            instance = MagicMock()
            mock_sock.return_value = instance
            instance.recvfrom.side_effect = IOError("timeout")
            results = self.scanner.scan(timeout=0.1)
        assert isinstance(results, list)


# ═══════════════════════════════════════════════════════
#  Tests NetworkMap v2 — PingScanner
# ═══════════════════════════════════════════════════════

from network.ping_scanner import PingScanner


class TestPingScanner:
    def setup_method(self):
        self.scanner = PingScanner()

    def test_extract_latency_windows(self):
        output = "Reply from 192.168.1.1: bytes=32 time=2ms TTL=64"
        assert PingScanner._extract_latency(output) == 2.0

    def test_extract_latency_linux(self):
        output = "64 bytes from 192.168.1.1: icmp_seq=1 ttl=64 time=1.23 ms"
        assert PingScanner._extract_latency(output) == 1.23

    def test_extract_latency_french(self):
        output = "Réponse de 192.168.1.1 : octets=32 temps=5ms TTL=64"
        assert PingScanner._extract_latency(output) == 5.0

    def test_extract_latency_none(self):
        output = "Request timed out."
        assert PingScanner._extract_latency(output) is None

    @pytest.mark.asyncio
    async def test_ping_reachable(self):
        proc_mock = AsyncMock()
        proc_mock.communicate.return_value = (b"time=3ms", b"")
        proc_mock.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=proc_mock):
            result = await self.scanner.ping("192.168.1.1")

        assert result["reachable"] is True
        assert result["latency_ms"] == 3.0

    @pytest.mark.asyncio
    async def test_ping_unreachable(self):
        proc_mock = AsyncMock()
        proc_mock.communicate.return_value = (b"Request timed out", b"")
        proc_mock.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=proc_mock):
            result = await self.scanner.ping("192.168.1.99")

        assert result["reachable"] is False

    @pytest.mark.asyncio
    async def test_scan_parallel(self):
        async def fake_ping(ip):
            return {"reachable": True, "latency_ms": 1.0}

        with patch.object(self.scanner, "ping", side_effect=fake_ping):
            results = await self.scanner.scan(["192.168.1.1", "192.168.1.2"])

        assert len(results) == 2
        assert all(r["reachable"] for r in results.values())

    @pytest.mark.asyncio
    async def test_ping_timeout(self):
        with patch("asyncio.create_subprocess_exec", side_effect=asyncio.TimeoutError):
            result = await self.scanner.ping("192.168.1.1")
        assert result["reachable"] is False
        assert result["latency_ms"] is None


# ═══════════════════════════════════════════════════════
#  Tests NetworkMap v2 — NetworkMapManager
# ═══════════════════════════════════════════════════════

from network.network_map_manager import NetworkMapManager


class TestNetworkMapManager:
    def setup_method(self):
        self.mgr = NetworkMapManager()

    def test_initial_state(self):
        assert self.mgr.get_devices() == []
        assert self.mgr.get_topology() == {"nodes": [], "links": []}
        assert self.mgr.get_links() == []

    def test_health_check(self):
        hc = self.mgr.health_check()
        assert hc["status"] == "ok"
        assert hc["devices_count"] == 0

    def test_capabilities(self):
        caps = self.mgr.capabilities()
        assert len(caps) == 14
        assert "scan_full" in caps
        assert "scan_fast" in caps

    def test_metadata(self):
        meta = self.mgr.metadata()
        assert meta["version"] == "v2"
        assert meta["backend"] == "arp+mdns+ssdp+ping"

    def test_restart(self):
        result = self.mgr.restart()
        assert result["status"] == "restarted"

    def test_get_device_not_found(self):
        assert self.mgr.get_device("1.2.3.4") is None

    def test_get_vendor_empty(self):
        assert self.mgr.get_vendor("AA:BB:CC:DD:EE:FF") == ""

    def test_get_latency_empty(self):
        assert self.mgr.get_latency("1.2.3.4") is None

    def test_classify_device(self):
        assert self.mgr.classify_device({"type": "unknown", "vendor": "Samsung"}) == "tv"

    def test_export_json(self):
        import json
        data = json.loads(self.mgr.export_json())
        assert "devices" in data
        assert "topology" in data
        assert "metrics" in data

    def test_get_metrics(self):
        m = self.mgr.get_metrics()
        assert m["scans_total"] == 0
        assert m["devices_found"] == 0

    @pytest.mark.asyncio
    async def test_scan_fast(self):
        fake_arp = [
            {"ip": "192.168.1.1", "mac": "AA:BB:CC:00:00:01", "vendor": "", "type": "router",
             "online": True, "source": "arp", "last_seen": 0},
            {"ip": "192.168.1.10", "mac": "11:22:33:44:55:66", "vendor": "Intel", "type": "unknown",
             "online": True, "source": "arp", "last_seen": 0},
        ]
        with patch.object(self.mgr._arp, "scan", return_value=fake_arp):
            result = await self.mgr.scan_fast()

        assert len(result["devices"]) == 2
        assert result["scan_time_ms"] >= 0
        # Intel → pc
        devs = {d["ip"]: d for d in result["devices"]}
        assert devs["192.168.1.10"]["type"] == "pc"

    @pytest.mark.asyncio
    async def test_scan_full_with_mocks(self):
        fake_arp = [
            {"ip": "192.168.1.1", "mac": "AA:BB:CC:00:00:01", "vendor": "", "type": "router",
             "online": True, "source": "arp", "sources": ["arp"], "last_seen": 0},
            {"ip": "192.168.1.10", "mac": "11:22:33:44:55:66", "vendor": "Samsung", "type": "unknown",
             "online": True, "source": "arp", "sources": ["arp"], "last_seen": 0},
        ]
        fake_mdns = {
            "192.168.1.10": {"hostname": "Samsung-TV", "services": [], "type": "tv"},
        }
        fake_ssdp = [
            {"ip": "192.168.1.10", "server": "Samsung TV", "manufacturer": "Samsung"},
        ]
        fake_ping = {
            "192.168.1.1": {"reachable": True, "latency_ms": 1.0},
            "192.168.1.10": {"reachable": True, "latency_ms": 5.0},
        }

        self.mgr._arp._gateway_ip = "192.168.1.1"
        self.mgr._arp._gateway_mac = "AA:BB:CC:00:00:01"

        with patch.object(self.mgr._arp, "scan", return_value=fake_arp), \
             patch.object(self.mgr._mdns, "scan", return_value=fake_mdns), \
             patch.object(self.mgr._ssdp, "scan", return_value=fake_ssdp), \
             patch.object(self.mgr._ping, "scan", return_value=fake_ping):
            result = await self.mgr.scan_full()

        assert len(result["devices"]) == 2
        assert "topology" in result
        assert result["topology"]["stats"]["total_nodes"] == 2
        assert result["scan_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_scan_full_resilience_mdns_failure(self):
        fake_arp = [
            {"ip": "192.168.1.10", "mac": "11:22:33:44:55:66", "vendor": "", "type": "unknown",
             "online": True, "source": "arp", "sources": ["arp"], "last_seen": 0},
        ]
        self.mgr._arp._gateway_ip = ""
        self.mgr._arp._gateway_mac = ""

        with patch.object(self.mgr._arp, "scan", return_value=fake_arp), \
             patch.object(self.mgr._mdns, "scan", side_effect=Exception("mDNS failed")), \
             patch.object(self.mgr._ssdp, "scan", return_value=[]), \
             patch.object(self.mgr._ping, "scan", return_value={}):
            result = await self.mgr.scan_full()

        assert len(result["devices"]) == 1
        assert result["metrics"]["scan_errors"] >= 1


# ═══════════════════════════════════════════════════════
#  Tests v2 — DomoticCache
# ═══════════════════════════════════════════════════════

from domotique.domotic_cache import DomoticCache


class TestDomoticCache:
    def setup_method(self):
        self.cache = DomoticCache(default_ttl=30.0)

    def test_set_and_get(self):
        self.cache.set_state("dev1", {"on": True, "brightness": 80})
        state = self.cache.get_state("dev1")
        assert state is not None
        assert state["on"] is True
        assert state["brightness"] == 80

    def test_get_miss(self):
        state = self.cache.get_state("nonexistent")
        assert state is None

    def test_invalidate(self):
        self.cache.set_state("dev1", {"on": True})
        self.cache.invalidate("dev1")
        state = self.cache.get_state("dev1")
        assert state is None

    def test_invalidate_all(self):
        self.cache.set_state("dev1", {"on": True})
        self.cache.set_state("dev2", {"on": False})
        self.cache.invalidate_all()
        assert self.cache.get_state("dev1") is None
        assert self.cache.get_state("dev2") is None

    def test_has(self):
        self.cache.set_state("dev1", {"on": True})
        assert self.cache.has("dev1") is True
        assert self.cache.has("nonexistent") is False

    def test_stats(self):
        self.cache.set_state("dev1", {"on": True})
        self.cache.get_state("dev1")  # hit
        self.cache.get_state("miss")  # miss
        stats = self.cache.stats()
        assert stats["entries"] >= 1
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1

    def test_expired_entry(self):
        self.cache.set_state("dev1", {"on": True}, ttl=0.0)
        import time
        time.sleep(0.01)
        state = self.cache.get_state("dev1")
        assert state is None

    def test_all_states(self):
        self.cache.set_state("dev1", {"on": True})
        self.cache.set_state("dev2", {"on": False})
        states = self.cache.all_states()
        assert "dev1" in states
        assert "dev2" in states


# ═══════════════════════════════════════════════════════
#  Tests v2 — EventManager
# ═══════════════════════════════════════════════════════

from domotique.event_manager import EventManager


class TestEventManager:
    def setup_method(self):
        self.em = EventManager()
        self.events_received = []

    async def _callback(self, device_id, old_state, new_state):
        self.events_received.append((device_id, old_state, new_state))

    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self):
        self.em.subscribe("dev1", self._callback)
        await self.em.on_event("dev1", {"on": True})
        assert len(self.events_received) == 1
        assert self.events_received[0][0] == "dev1"

    @pytest.mark.asyncio
    async def test_wildcard_subscribe(self):
        self.em.subscribe_all(self._callback)
        await self.em.on_event("dev1", {"on": True})
        await self.em.on_event("dev2", {"on": False})
        assert len(self.events_received) == 2

    @pytest.mark.asyncio
    async def test_no_event_on_same_state(self):
        self.em.subscribe("dev1", self._callback)
        await self.em.on_event("dev1", {"on": True})
        await self.em.on_event("dev1", {"on": True})
        # Second call same state → no new event
        assert len(self.events_received) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        self.em.subscribe("dev1", self._callback)
        self.em.unsubscribe("dev1", self._callback)
        await self.em.on_event("dev1", {"on": True})
        assert len(self.events_received) == 0

    def test_stats(self):
        stats = self.em.stats()
        assert "subscriptions" in stats
        assert "total_events" in stats

    @pytest.mark.asyncio
    async def test_recent_events(self):
        self.em.subscribe("dev1", self._callback)
        await self.em.on_event("dev1", {"on": True})
        events = self.em.recent_events(10)
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_device_state(self):
        await self.em.on_event("dev1", {"on": True, "brightness": 80})
        state = self.em.device_state("dev1")
        assert state is not None
        assert state["on"] is True


# ═══════════════════════════════════════════════════════
#  Tests v2 — ScenarioManager
# ═══════════════════════════════════════════════════════

from domotique.scenario_manager import ScenarioManager, StepType, ScenarioStep


class TestScenarioManager:
    def setup_method(self):
        self.sm = ScenarioManager()
        self.commands_executed = []

    async def _executor(self, device_id, command, params=None):
        self.commands_executed.append((device_id, command, params))
        return {"ok": True}

    def test_list_builtin_scenarios(self):
        scenarios = self.sm.list_scenarios()
        assert len(scenarios) >= 6
        names = [s["name"] for s in scenarios]
        assert "cinema" in names
        assert "nuit" in names
        assert "absence" in names
        assert "reveil" in names
        assert "securite" in names
        assert "eco" in names

    def test_get_scenario(self):
        s = self.sm.get_scenario("cinema")
        assert s is not None
        assert s["name"] == "cinema"
        assert s["builtin"] is True

    def test_get_scenario_not_found(self):
        s = self.sm.get_scenario("nonexistent")
        assert s is None

    def test_add_custom_scenario(self):
        steps = [{"type": "action", "target": "*light*", "command": "turn_on"}]
        self.sm.add_scenario("test_custom", steps, description="Test")
        s = self.sm.get_scenario("test_custom")
        assert s is not None
        assert s["builtin"] is False

    def test_remove_custom_scenario(self):
        steps = [{"type": "action", "target": "*light*", "command": "turn_on"}]
        self.sm.add_scenario("toremove", steps)
        ok = self.sm.remove_scenario("toremove")
        assert ok is True
        assert self.sm.get_scenario("toremove") is None

    def test_cannot_remove_builtin(self):
        ok = self.sm.remove_scenario("cinema")
        assert ok is False

    @pytest.mark.asyncio
    async def test_run_scenario(self):
        self.sm.set_executor(self._executor)
        devices = [
            {"id_exo": "light_1", "type": "light", "name": "Lampe salon"},
            {"id_exo": "tv_1", "type": "tv", "name": "TV Salon"},
        ]
        result = await self.sm.run_scenario("cinema", devices)
        assert result is not None
        assert len(self.commands_executed) > 0


# ═══════════════════════════════════════════════════════
#  Tests v2 — Models v2 extensions
# ═══════════════════════════════════════════════════════

from domotique.models import Protocol, Connectivity, DeviceEvent


class TestModelsV2:
    def test_protocol_enum(self):
        assert Protocol.HUE == "hue"
        assert Protocol.TAPO == "tapo"
        assert Protocol.SAMSUNG == "samsung"

    def test_connectivity_enum(self):
        assert Connectivity.WIFI == "wifi"
        assert Connectivity.ETH == "eth"

    def test_device_event(self):
        evt = DeviceEvent(
            timestamp=1234567890.0,
            event_type="state_change",
            data={"on": True},
        )
        assert evt.timestamp == 1234567890.0
        assert evt.event_type == "state_change"

    def test_device_v2_fields(self):
        d = Device(
            id_exo="light_1",
            id_origin="hue:123",
            source=DeviceSource.HUE,
            type=DeviceType.LIGHT,
            name="Lampe salon",
            protocol=Protocol.HUE,
            connectivity=Connectivity.WIFI,
            tags=["salon", "ambiance"],
        )
        out = d.to_dict()
        assert out["protocol"] == "hue"
        assert out["connectivity"] == "wifi"
        assert "salon" in out["tags"]

    def test_device_v2_defaults(self):
        d = Device(
            id_exo="x",
            id_origin="y",
            source=DeviceSource.OTHER,
            type=DeviceType.UNKNOWN,
            name="Test",
        )
        assert d.tags == []
        assert d.energy == {}


# ═══════════════════════════════════════════════════════
#  Tests v2 — HomeGraph v2 API
# ═══════════════════════════════════════════════════════

class TestHomeGraphV2:
    def setup_method(self):
        self.hg = HomeGraphManager()

    def test_capabilities(self):
        caps = self.hg.capabilities()
        assert isinstance(caps, list)
        assert "list_devices" in caps
        assert "list_scenarios" in caps
        assert "refresh_device" in caps
        assert "discovery" in caps

    def test_metadata(self):
        meta = self.hg.metadata()
        assert meta["name"] == "homegraph"
        assert meta["version"] == "v2"
        assert "devices_count" in meta
        assert "cache" in meta

    def test_get_capabilities_for_device(self):
        self.hg.merge_devices("hue", [
            {"id_origin": "hue:1", "source": "hue", "type": "light",
             "name": "L1", "capabilities": ["on_off", "brightness"], "state": {}},
        ])
        devs = self.hg.list_devices()
        caps = self.hg.get_capabilities(devs[0]["id_exo"])
        assert "on_off" in caps

    def test_get_vendor(self):
        self.hg.merge_devices("hue", [
            {"id_origin": "hue:1", "source": "hue", "type": "light",
             "name": "L1", "capabilities": [], "state": {}, "vendor": "Philips"},
        ])
        devs = self.hg.list_devices()
        vendor = self.hg.get_vendor(devs[0]["id_exo"])
        assert vendor == "Philips"

    def test_cache_stats(self):
        stats = self.hg.get_cache_stats()
        assert "entries" in stats
        assert "hits" in stats

    def test_event_stats(self):
        stats = self.hg.get_event_stats()
        assert isinstance(stats, dict)

    def test_list_scenarios(self):
        scenarios = self.hg.list_scenarios()
        assert len(scenarios) >= 6

    def test_list_devices_by_type(self):
        self.hg.merge_devices("hue", [
            {"id_origin": "hue:1", "source": "hue", "type": "light",
             "name": "L1", "capabilities": [], "state": {}},
        ])
        lights = self.hg.list_devices_by_type("light")
        assert len(lights) >= 1


# ═══════════════════════════════════════════════════════
#  Tests v2 — Service capabilities/metadata
# ═══════════════════════════════════════════════════════

class TestServiceV2Capabilities:
    def test_samsung_capabilities(self):
        svc = SamsungService()
        caps = svc.capabilities()
        assert "list_devices" in caps
        assert "capabilities" in caps
        assert "metadata" in caps

    def test_samsung_metadata(self):
        svc = SamsungService()
        meta = svc.metadata()
        assert meta["name"] == "samsung"
        assert meta["version"] == "v2"

    def test_voltalis_capabilities(self):
        svc = VoltalisService()
        caps = svc.capabilities()
        assert "list_devices" in caps
        assert "get_consumption" in caps

    def test_voltalis_metadata(self):
        svc = VoltalisService()
        meta = svc.metadata()
        assert meta["name"] == "voltalis"
        assert meta["version"] == "v2"

    def test_echo_capabilities(self):
        svc = EchoService()
        caps = svc.capabilities()
        assert "send_tts" in caps
        assert "set_volume" in caps

    def test_echo_metadata(self):
        svc = EchoService()
        meta = svc.metadata()
        assert meta["name"] == "echo"
        assert meta["version"] == "v2"

    def test_networkmap_capabilities(self):
        svc = NetworkMapService()
        caps = svc.capabilities()
        assert "scan_full" in caps

    def test_networkmap_metadata(self):
        svc = NetworkMapService()
        meta = svc.metadata()
        assert meta["name"] == "network_map"
        assert meta["version"] == "v2"
