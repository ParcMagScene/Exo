"""
EXO Domotique v2 — DiscoveryManager

Moteur de découverte avancée : ARP + mDNS + SSDP + vendor lookup.
Fusionne les résultats, détecte les doublons, enrichit le HomeGraph.
"""

from __future__ import annotations

import asyncio
import logging
import re
import socket
import time
from typing import Any

log = logging.getLogger("discovery")


# ── OUI vendor database ───────────────────────────────────────

def load_oui(path: str) -> dict[str, str]:
    """Load IEEE OUI vendor prefix database."""
    oui: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = re.match(
                    r"^([0-9A-F]{2}-[0-9A-F]{2}-[0-9A-F]{2})\s+\(hex\)\s+(.+)$",
                    line.strip(),
                )
                if m:
                    prefix = m.group(1).replace("-", ":").upper()
                    oui[prefix] = m.group(2).strip()
    except FileNotFoundError:
        pass
    except Exception as e:
        log.warning("OUI load error: %s", e)
    return oui


class DiscoveredDevice:
    """Appareil découvert avec données fusionnées multi-sources."""
    __slots__ = (
        "ip", "mac", "vendor", "hostname", "services",
        "source", "device_type", "last_seen",
    )

    def __init__(self, ip: str = "", mac: str = ""):
        self.ip = ip
        self.mac = mac.upper()
        self.vendor = ""
        self.hostname = ""
        self.services: list[str] = []      # e.g. ["_hue._tcp", "_googlecast._tcp"]
        self.source: set[str] = set()      # {"arp", "mdns", "ssdp"}
        self.device_type = "unknown"
        self.last_seen = time.time()

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "mac": self.mac,
            "vendor": self.vendor,
            "hostname": self.hostname,
            "services": list(self.services),
            "sources": sorted(self.source),
            "type": self.device_type,
            "last_seen": self.last_seen,
        }


class DiscoveryManager:
    """Moteur de découverte réseau unifié."""

    def __init__(self, oui_db: dict[str, str] | None = None):
        self._oui = oui_db or {}
        self._devices: dict[str, DiscoveredDevice] = {}   # keyed by IP
        self._metrics: dict[str, Any] = {}

    # ── vendor lookup ─────────────────────────────────

    def vendor_lookup(self, mac: str) -> str:
        prefix = mac.upper()[:8]
        return self._oui.get(prefix, "")

    # ── ARP scan ──────────────────────────────────────

    async def scan_arp(self) -> list[DiscoveredDevice]:
        """Parse ARP table (Windows: arp -a)."""
        t0 = time.monotonic()
        results: list[DiscoveredDevice] = []
        try:
            proc = await asyncio.create_subprocess_exec(
                "arp", "-a",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            output = stdout.decode("utf-8", errors="ignore")

            for line in output.splitlines():
                m = re.search(
                    r"(\d+\.\d+\.\d+\.\d+)\s+"
                    r"([0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-]"
                    r"[0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-]"
                    r"[0-9a-fA-F]{2}[:-][0-9a-fA-F]{2})",
                    line,
                )
                if not m:
                    continue
                ip = m.group(1)
                mac = m.group(2).replace("-", ":").upper()
                if mac == "FF:FF:FF:FF:FF:FF":
                    continue

                dev = DiscoveredDevice(ip=ip, mac=mac)
                dev.vendor = self.vendor_lookup(mac)
                dev.source.add("arp")

                # Detect gateway
                if ip.endswith(".1") or ip.endswith(".254"):
                    dev.device_type = "router"

                results.append(dev)
        except Exception as e:
            log.warning("ARP scan failed: %s", e)

        self._metrics["arp_time_ms"] = round((time.monotonic() - t0) * 1000)
        self._metrics["arp_count"] = len(results)
        return results

    # ── mDNS scan ─────────────────────────────────────

    async def scan_mdns(self, ips: list[str] | None = None) -> dict[str, dict]:
        """Reverse DNS + service inference for known IPs."""
        t0 = time.monotonic()
        results: dict[str, dict] = {}
        loop = asyncio.get_running_loop()

        targets = ips or [d.ip for d in self._devices.values()]
        for ip in targets:
            try:
                hostname, _, _ = await loop.run_in_executor(
                    None, socket.gethostbyaddr, ip,
                )
                if hostname:
                    services = self._infer_services(hostname)
                    dtype = self._infer_type_from_hostname(hostname)
                    results[ip] = {
                        "hostname": hostname,
                        "services": services,
                        "type": dtype,
                    }
            except (socket.herror, socket.gaierror, OSError):
                pass

        self._metrics["mdns_time_ms"] = round((time.monotonic() - t0) * 1000)
        self._metrics["mdns_resolved"] = len(results)
        return results

    # ── SSDP scan ─────────────────────────────────────

    async def scan_ssdp(self, timeout: float = 3.0) -> list[dict]:
        """SSDP/UPnP M-SEARCH discovery."""
        t0 = time.monotonic()
        results: list[dict] = []
        try:
            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(None, self._ssdp_search, timeout)
            results = data
        except Exception as e:
            log.warning("SSDP scan failed: %s", e)

        self._metrics["ssdp_time_ms"] = round((time.monotonic() - t0) * 1000)
        self._metrics["ssdp_count"] = len(results)
        return results

    def _ssdp_search(self, timeout: float) -> list[dict]:
        msg = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            'MAN: "ssdp:discover"\r\n'
            "MX: 2\r\n"
            "ST: ssdp:all\r\n"
            "\r\n"
        )
        results: list[dict] = []
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.settimeout(timeout)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.sendto(msg.encode(), ("239.255.255.250", 1900))
            seen_ips: set[str] = set()
            while True:
                try:
                    data, addr = sock.recvfrom(4096)
                    ip = addr[0]
                    if ip in seen_ips:
                        continue
                    seen_ips.add(ip)
                    text = data.decode("utf-8", errors="ignore")
                    server = ""
                    location = ""
                    for line in text.splitlines():
                        upper = line.upper()
                        if upper.startswith("SERVER:"):
                            server = line.split(":", 1)[1].strip()
                        elif upper.startswith("LOCATION:"):
                            location = line.split(":", 1)[1].strip()
                    results.append({
                        "ip": ip,
                        "server": server,
                        "location": location,
                    })
                except socket.timeout:
                    break
        finally:
            sock.close()
        return results

    # ── Fusion ────────────────────────────────────────

    async def full_scan(self) -> dict:
        """Scan complet : ARP + mDNS + SSDP, fusion, dédoublonnage."""
        t0 = time.monotonic()
        self._devices.clear()

        # 1. ARP scan
        arp_devices = await self.scan_arp()
        for dev in arp_devices:
            self._devices[dev.ip] = dev

        # 2. mDNS enrichment
        ips = [d.ip for d in arp_devices]
        mdns_results = await self.scan_mdns(ips)
        for ip, info in mdns_results.items():
            if ip in self._devices:
                dev = self._devices[ip]
                dev.hostname = info.get("hostname", "")
                dev.services = info.get("services", [])
                if info.get("type", "unknown") != "unknown":
                    dev.device_type = info["type"]
                dev.source.add("mdns")

        # 3. SSDP enrichment
        ssdp_results = await self.scan_ssdp()
        for item in ssdp_results:
            ip = item.get("ip", "")
            if ip in self._devices:
                dev = self._devices[ip]
                if item.get("server") and not dev.hostname:
                    dev.hostname = item["server"]
                dev.source.add("ssdp")
            else:
                dev = DiscoveredDevice(ip=ip)
                dev.hostname = item.get("server", "")
                dev.source.add("ssdp")
                self._devices[ip] = dev

        # 4. Infer remaining types from vendor
        for dev in self._devices.values():
            if dev.device_type == "unknown" and dev.vendor:
                dev.device_type = self._infer_type_from_vendor(dev.vendor)

        elapsed = time.monotonic() - t0
        self._metrics["total_time_ms"] = round(elapsed * 1000)
        self._metrics["total_devices"] = len(self._devices)

        new_count = len(self._devices)
        log.info("Discovery complete: %d devices (%.1fs)", new_count, elapsed)

        return {
            "devices": [d.to_dict() for d in self._devices.values()],
            "metrics": dict(self._metrics),
            "count": new_count,
        }

    def get_results(self) -> list[dict]:
        return [d.to_dict() for d in self._devices.values()]

    def get_metrics(self) -> dict:
        return dict(self._metrics)

    # ── helpers ───────────────────────────────────────

    @staticmethod
    def _infer_services(hostname: str) -> list[str]:
        hl = hostname.lower()
        services = []
        if "hue" in hl or "philips" in hl:
            services.append("_hue._tcp")
        if "googlecast" in hl or "chromecast" in hl or "google" in hl:
            services.append("_googlecast._tcp")
        if "echo" in hl or "amazon" in hl:
            services.append("_alexa._tcp")
        if "ewelink" in hl or "sonoff" in hl:
            services.append("_ewelink._tcp")
        if "homekit" in hl or "apple" in hl:
            services.append("_homekit._tcp")
        if "tapo" in hl or "tp-link" in hl:
            services.append("_tapo._tcp")
        return services

    @staticmethod
    def _infer_type_from_hostname(hostname: str) -> str:
        hl = hostname.lower()
        if "echo" in hl or "amazon" in hl:
            return "speaker"
        if "tv" in hl or "samsung" in hl or "lg" in hl:
            return "tv"
        if "phone" in hl or "iphone" in hl or "android" in hl:
            return "phone"
        if "pc" in hl or "desktop" in hl or "laptop" in hl:
            return "pc"
        if "nas" in hl or "synology" in hl:
            return "nas"
        if "cam" in hl or "ezviz" in hl:
            return "camera"
        if "hue" in hl or "philips" in hl:
            return "light"
        if "tapo" in hl or "plug" in hl:
            return "plug"
        return "unknown"

    @staticmethod
    def _infer_type_from_vendor(vendor: str) -> str:
        vl = vendor.lower()
        if "philips" in vl or "signify" in vl:
            return "light"
        if "tp-link" in vl or "tapo" in vl:
            return "plug"
        if "amazon" in vl:
            return "speaker"
        if "samsung" in vl:
            return "tv"
        if "synology" in vl or "qnap" in vl:
            return "nas"
        if "ezviz" in vl or "hikvision" in vl:
            return "camera"
        if "apple" in vl:
            return "phone"
        return "unknown"
