"""
EXO NetworkMap v2 — TopologyBuilder

Reconstruction de la topologie réseau locale.
- Routeur = nœud central
- EXO = nœud prioritaire
- IoT = périphériques
- Liens = latence + type (WiFi/Ethernet)
"""

from __future__ import annotations

import logging
import socket
import time

log = logging.getLogger("networkmap.topology")


class TopologyBuilder:
    """Reconstruit la topologie réseau à partir des données de scan."""

    def __init__(self):
        self._nodes: list[dict] = []
        self._links: list[dict] = []
        self._gateway_ip: str = ""
        self._gateway_mac: str = ""
        self._exo_ip: str = ""

    def build(self, devices: list[dict], gateway_ip: str = "",
              gateway_mac: str = "", latencies: dict[str, dict] | None = None
              ) -> dict:
        """Construit la topologie complète.

        Args:
            devices: liste d'appareils avec ip, mac, vendor, type, etc.
            gateway_ip: IP du routeur (détectée si vide)
            gateway_mac: MAC du routeur
            latencies: dict[ip] -> {reachable, latency_ms}

        Returns:
            dict avec nodes, links, gateway, stats.
        """
        t0 = time.monotonic()
        self._nodes = []
        self._links = []
        latencies = latencies or {}

        # Identifier gateway
        self._gateway_ip = gateway_ip
        self._gateway_mac = gateway_mac
        if not self._gateway_ip:
            self._detect_gateway(devices)

        # Identifier EXO (self)
        self._detect_exo()

        # Construire les nœuds
        for dev in devices:
            ip = dev.get("ip", "")
            mac = dev.get("mac", "")
            lat_info = latencies.get(ip, {})
            latency_ms = lat_info.get("latency_ms")

            is_gw = (ip == self._gateway_ip or mac == self._gateway_mac)
            is_exo = (ip == self._exo_ip)

            node = {
                "id": mac or ip,
                "ip": ip,
                "mac": mac,
                "vendor": dev.get("vendor", ""),
                "name": dev.get("hostname", "") or dev.get("name", ""),
                "type": dev.get("type", "unknown"),
                "online": dev.get("online", True),
                "latency_ms": latency_ms,
                "last_seen": dev.get("last_seen", time.time()),
                "is_gateway": is_gw,
                "is_exo": is_exo,
                "priority": 0 if is_gw else (1 if is_exo else 2),
                "sources": dev.get("sources", [dev.get("source", "unknown")]),
            }
            self._nodes.append(node)

        # Construire les liens (étoile → gateway)
        gw_id = self._gateway_mac or self._gateway_ip
        if gw_id:
            for node in self._nodes:
                nid = node["id"]
                if nid == gw_id:
                    continue

                link_type = self._infer_link_type(node)
                latency_ms = node.get("latency_ms")

                self._links.append({
                    "from_id": nid,
                    "to_id": gw_id,
                    "type": link_type,
                    "latency_ms": latency_ms,
                })

        elapsed_ms = round((time.monotonic() - t0) * 1000)
        log.info("Topology built: %d nodes, %d links (%dms)",
                 len(self._nodes), len(self._links), elapsed_ms)

        return {
            "nodes": self._nodes,
            "links": self._links,
            "gateway": {
                "ip": self._gateway_ip,
                "mac": self._gateway_mac,
            },
            "exo_ip": self._exo_ip,
            "stats": {
                "total_nodes": len(self._nodes),
                "total_links": len(self._links),
                "build_time_ms": elapsed_ms,
            },
        }

    def _detect_gateway(self, devices: list[dict]) -> None:
        """Détecte le routeur dans la liste d'appareils."""
        for dev in devices:
            ip = dev.get("ip", "")
            if ip.endswith(".1") or ip.endswith(".254"):
                self._gateway_ip = ip
                self._gateway_mac = dev.get("mac", "")
                return
        # Fallback: premier appareil de type router
        for dev in devices:
            if dev.get("type") == "router":
                self._gateway_ip = dev.get("ip", "")
                self._gateway_mac = dev.get("mac", "")
                return

    def _detect_exo(self) -> None:
        """Détecte l'IP locale d'EXO."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self._exo_ip = s.getsockname()[0]
            s.close()
        except Exception:
            self._exo_ip = "127.0.0.1"

    @staticmethod
    def _infer_link_type(node: dict) -> str:
        """Infère le type de lien réseau."""
        vendor = node.get("vendor", "").lower()
        dtype = node.get("type", "")

        # Ethernet si vendor réseau ou type PC/NAS
        if any(kw in vendor for kw in ("realtek", "intel", "broadcom")):
            return "eth"
        if dtype in ("pc", "nas", "router"):
            return "eth"

        # IoT pour objets connectés
        if dtype in ("light", "plug", "iot", "sensor"):
            return "iot"

        # WiFi par défaut
        return "wifi"

    def get_topology(self) -> dict:
        """Retourne la topologie courante."""
        return {
            "nodes": list(self._nodes),
            "links": list(self._links),
        }

    def get_links(self) -> list[dict]:
        """Retourne les liens courants."""
        return list(self._links)
