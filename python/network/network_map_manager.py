"""
EXO NetworkMap v2 — NetworkMapManager

Orchestre les scans (ARP + mDNS + SSDP + Ping), fusionne les résultats,
reconstruit la topologie, classifie les appareils, mesure la latence.
Expose une API unifiée avec résilience complète (timeouts, retry, fallback).
Intègre EXO v9 (logs, métriques, traces).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from .arp_scanner import ARPScanner
from .mdns_scanner import MDNSScanner
from .ssdp_scanner import SSDPScanner
from .ping_scanner import PingScanner
from .vendor_lookup import VendorLookup
from .device_classifier import DeviceClassifier
from .topology_builder import TopologyBuilder

log = logging.getLogger("networkmap.manager")


class NetworkMapManager:
    """Orchestre tous les composants NetworkMap v2.

    Fournit : scan_full, scan_fast, topologie, latence, classification,
    vendor lookup, export JSON, health_check, restart.
    """

    def __init__(self, oui_path: str | Path | None = None, v9=None):
        # Composants
        self._vendor = VendorLookup(oui_path)
        self._arp = ARPScanner(vendor_lookup=self._vendor.lookup)
        self._mdns = MDNSScanner()
        self._ssdp = SSDPScanner()
        self._ping = PingScanner()
        self._classifier = DeviceClassifier()
        self._topology = TopologyBuilder()

        # État
        self._devices: dict[str, dict] = {}   # keyed by IP
        self._latencies: dict[str, dict] = {}  # keyed by IP
        self._last_scan: float = 0
        self._scan_count: int = 0
        self._last_topology: dict = {}

        # Métriques
        self._metrics: dict[str, Any] = {
            "scans_total": 0,
            "scan_errors": 0,
            "arp_time_ms": 0,
            "mdns_time_ms": 0,
            "ssdp_time_ms": 0,
            "ping_time_ms": 0,
            "total_time_ms": 0,
            "devices_found": 0,
            "devices_new": 0,
        }

        # v9 integration
        self._v9 = v9

    # ── SCAN FULL ────────────────────────────────────

    async def scan_full(self) -> dict:
        """Scan complet : ARP + mDNS + SSDP + Ping + topologie.

        Résilience : si mDNS échoue → ARP+vendor, si SSDP échoue → ARP+mDNS,
        si ping échoue → latence=null.
        """
        t0 = time.monotonic()
        old_count = len(self._devices)
        self._devices.clear()
        self._latencies.clear()

        if self._v9:
            self._v9.metrics.counter("scans_total").inc()

        # 1. ARP scan
        t_arp = time.monotonic()
        arp_results = await self._arp.scan()
        arp_ms = round((time.monotonic() - t_arp) * 1000)
        self._metrics["arp_time_ms"] = arp_ms

        for dev in arp_results:
            self._devices[dev["ip"]] = dev

        # 2. mDNS enrichment (fallback: continue with ARP+vendor)
        t_mdns = time.monotonic()
        try:
            ips = [d["ip"] for d in arp_results]
            mdns_results = await self._mdns.scan(ips)
            for ip, info in mdns_results.items():
                if ip in self._devices:
                    self._devices[ip]["hostname"] = info.get("hostname", "")
                    self._devices[ip]["services"] = info.get("services", [])
                    if info.get("type", "unknown") != "unknown":
                        self._devices[ip]["type"] = info["type"]
                    self._devices[ip].setdefault("sources", [])
                    if "mdns" not in self._devices[ip]["sources"]:
                        self._devices[ip]["sources"].append("mdns")
        except Exception as e:
            log.warning("mDNS fallback — using ARP+vendor: %s", e)
            self._metrics["scan_errors"] = self._metrics.get("scan_errors", 0) + 1
        mdns_ms = round((time.monotonic() - t_mdns) * 1000)
        self._metrics["mdns_time_ms"] = mdns_ms

        # 3. SSDP enrichment (fallback: continue with ARP+mDNS)
        t_ssdp = time.monotonic()
        try:
            loop = asyncio.get_running_loop()
            ssdp_results = await loop.run_in_executor(None, self._ssdp.scan)
            for item in ssdp_results:
                ip = item.get("ip", "")
                if ip in self._devices:
                    dev = self._devices[ip]
                    if item.get("server") and not dev.get("hostname"):
                        dev["hostname"] = item["server"]
                    if item.get("manufacturer"):
                        dev["ssdp_manufacturer"] = item["manufacturer"]
                    dev.setdefault("sources", [])
                    if "ssdp" not in dev["sources"]:
                        dev["sources"].append("ssdp")
                else:
                    self._devices[ip] = {
                        "ip": ip,
                        "mac": "",
                        "vendor": "",
                        "hostname": item.get("server", ""),
                        "type": "unknown",
                        "online": True,
                        "source": "ssdp",
                        "sources": ["ssdp"],
                        "ssdp_manufacturer": item.get("manufacturer", ""),
                        "last_seen": time.time(),
                    }
        except Exception as e:
            log.warning("SSDP fallback — using ARP+mDNS: %s", e)
            self._metrics["scan_errors"] = self._metrics.get("scan_errors", 0) + 1
        ssdp_ms = round((time.monotonic() - t_ssdp) * 1000)
        self._metrics["ssdp_time_ms"] = ssdp_ms

        # 4. Ping sweep (fallback: latence=null)
        t_ping = time.monotonic()
        try:
            all_ips = list(self._devices.keys())
            self._latencies = await self._ping.scan(all_ips)
            for ip, lat in self._latencies.items():
                if ip in self._devices:
                    self._devices[ip]["latency_ms"] = lat.get("latency_ms")
                    if not self._devices[ip].get("online") and lat.get("reachable"):
                        self._devices[ip]["online"] = True
        except Exception as e:
            log.warning("Ping fallback — latency unavailable: %s", e)
            self._metrics["scan_errors"] = self._metrics.get("scan_errors", 0) + 1
        ping_ms = round((time.monotonic() - t_ping) * 1000)
        self._metrics["ping_time_ms"] = ping_ms

        # 5. Classification
        devices_list = list(self._devices.values())
        self._classifier.classify_batch(devices_list)

        # 6. Topologie
        self._last_topology = self._topology.build(
            devices_list,
            gateway_ip=self._arp.gateway_ip,
            gateway_mac=self._arp.gateway_mac,
            latencies=self._latencies,
        )

        # Métriques finales
        total_ms = round((time.monotonic() - t0) * 1000)
        new_count = len(self._devices) - old_count
        self._metrics["total_time_ms"] = total_ms
        self._metrics["devices_found"] = len(self._devices)
        self._metrics["devices_new"] = max(0, new_count)
        self._metrics["scans_total"] = self._metrics.get("scans_total", 0) + 1
        self._last_scan = time.time()
        self._scan_count += 1

        if self._v9:
            self._v9.metrics.histogram("scan_duration_ms").observe(total_ms)

        log.info("Full scan: %d devices, %d links (%.1fs) [ARP:%dms mDNS:%dms SSDP:%dms Ping:%dms]",
                 len(self._devices), len(self._last_topology.get("links", [])),
                 total_ms / 1000, arp_ms, mdns_ms, ssdp_ms, ping_ms)

        return {
            "devices": devices_list,
            "topology": self._last_topology,
            "metrics": dict(self._metrics),
            "scan_time_ms": total_ms,
        }

    # ── SCAN FAST (ARP only + classify) ──────────────

    async def scan_fast(self) -> dict:
        """Scan rapide : ARP + vendor + classification uniquement."""
        t0 = time.monotonic()
        self._devices.clear()

        arp_results = await self._arp.scan()
        for dev in arp_results:
            self._devices[dev["ip"]] = dev

        self._classifier.classify_batch(list(self._devices.values()))

        elapsed_ms = round((time.monotonic() - t0) * 1000)
        self._last_scan = time.time()

        log.info("Fast scan: %d devices (%dms)", len(self._devices), elapsed_ms)
        return {
            "devices": list(self._devices.values()),
            "scan_time_ms": elapsed_ms,
        }

    # ── GETTERS ──────────────────────────────────────

    def get_devices(self) -> list[dict]:
        """Retourne tous les appareils découverts."""
        return list(self._devices.values())

    def get_device(self, ip: str) -> dict | None:
        """Retourne un appareil par IP."""
        return self._devices.get(ip)

    def get_topology(self) -> dict:
        """Retourne la topologie courante."""
        return self._last_topology or {"nodes": [], "links": []}

    def get_links(self) -> list[dict]:
        """Retourne les liens réseau."""
        return self._last_topology.get("links", [])

    def get_vendor(self, mac: str) -> str:
        """Lookup vendor par MAC."""
        return self._vendor.lookup(mac)

    def get_latency(self, ip: str) -> float | None:
        """Retourne la latence pour une IP."""
        lat = self._latencies.get(ip, {})
        return lat.get("latency_ms")

    def classify_device(self, device: dict) -> str:
        """Classifie un appareil."""
        return self._classifier.classify(device)

    # ── EXPORT ───────────────────────────────────────

    def export_json(self) -> str:
        """Exporte l'état complet en JSON."""
        return json.dumps({
            "devices": list(self._devices.values()),
            "topology": self._last_topology,
            "latencies": self._latencies,
            "metrics": self._metrics,
            "last_scan": self._last_scan,
        }, default=str, indent=2)

    # ── RESILIENCE ───────────────────────────────────

    def health_check(self) -> dict:
        """Retourne l'état de santé du NetworkMapManager."""
        return {
            "status": "ok",
            "devices_count": len(self._devices),
            "scan_count": self._scan_count,
            "last_scan": self._last_scan,
            "oui_entries": self._vendor.count,
            "errors": self._metrics.get("scan_errors", 0),
        }

    def restart(self) -> dict:
        """Réinitialise le manager."""
        self._devices.clear()
        self._latencies.clear()
        self._last_topology = {}
        self._metrics = {k: 0 for k in self._metrics}
        self._scan_count = 0
        log.info("NetworkMapManager restarted")
        return {"status": "restarted"}

    # ── METADATA ─────────────────────────────────────

    def capabilities(self) -> list[str]:
        return [
            "scan_full", "scan_fast", "get_devices", "get_device",
            "get_topology", "get_links", "get_vendor", "get_latency",
            "classify_device", "export_json",
            "health_check", "restart",
            "capabilities", "metadata",
        ]

    def metadata(self) -> dict:
        return {
            "name": "network_map",
            "version": "v2",
            "backend": "arp+mdns+ssdp+ping",
            "devices_count": len(self._devices),
            "links_count": len(self._last_topology.get("links", [])),
            "oui_entries": self._vendor.count,
            "scan_count": self._scan_count,
            "last_scan": self._last_scan,
        }

    def get_metrics(self) -> dict:
        """Retourne les métriques de performance."""
        return dict(self._metrics)
