"""
EXO NetworkMap v2 — SSDPScanner

Découverte SSDP/UPnP : M-SEARCH multicast pour détecter TV, caméras, IoT.
Extraction : deviceType, manufacturer, modelName, server.
"""

from __future__ import annotations

import logging
import socket
import time

log = logging.getLogger("networkmap.ssdp")


class SSDPScanner:
    """Scanner SSDP/UPnP par M-SEARCH multicast."""

    TIMEOUT = 3.0  # secondes
    MAX_RETRIES = 1
    MULTICAST_ADDR = "239.255.255.250"
    MULTICAST_PORT = 1900

    def scan(self, timeout: float | None = None) -> list[dict]:
        """SSDP M-SEARCH discovery (synchrone).

        Returns list of dicts: {ip, server, location, st}.
        """
        t0 = time.monotonic()
        effective_timeout = timeout or self.TIMEOUT
        results: list[dict] = []

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                results = self._do_search(effective_timeout)
                if results:
                    break
            except Exception as e:
                log.warning("SSDP scan attempt %d failed: %s", attempt + 1, e)
                if attempt >= self.MAX_RETRIES:
                    break

        elapsed_ms = round((time.monotonic() - t0) * 1000)
        log.info("SSDP scan: %d devices (%dms)", len(results), elapsed_ms)
        return results

    def _do_search(self, timeout: float) -> list[dict]:
        """Execute une requête M-SEARCH."""
        msg = (
            "M-SEARCH * HTTP/1.1\r\n"
            f"HOST: {self.MULTICAST_ADDR}:{self.MULTICAST_PORT}\r\n"
            'MAN: "ssdp:discover"\r\n'
            "MX: 2\r\n"
            "ST: ssdp:all\r\n"
            "\r\n"
        )
        results: list[dict] = []
        seen_ips: set[str] = set()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.settimeout(timeout)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.sendto(msg.encode(), (self.MULTICAST_ADDR, self.MULTICAST_PORT))

            while True:
                try:
                    data, addr = sock.recvfrom(4096)
                    ip = addr[0]
                    if ip in seen_ips:
                        continue
                    seen_ips.add(ip)

                    text = data.decode("utf-8", errors="ignore")
                    headers = self._parse_headers(text)

                    results.append({
                        "ip": ip,
                        "server": headers.get("server", ""),
                        "location": headers.get("location", ""),
                        "st": headers.get("st", ""),
                        "manufacturer": self._extract_manufacturer(headers),
                    })
                except socket.timeout:
                    break
        finally:
            sock.close()

        return results

    @staticmethod
    def _parse_headers(text: str) -> dict[str, str]:
        """Parse HTTP-like headers from SSDP response."""
        headers: dict[str, str] = {}
        for line in text.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                headers[key.strip().lower()] = value.strip()
        return headers

    @staticmethod
    def _extract_manufacturer(headers: dict[str, str]) -> str:
        """Essaie d'extraire le fabricant depuis les headers SSDP."""
        server = headers.get("server", "").lower()
        known = [
            ("samsung", "Samsung"), ("lg", "LG"), ("sony", "Sony"),
            ("philips", "Philips"), ("roku", "Roku"),
            ("amazon", "Amazon"), ("google", "Google"),
            ("microsoft", "Microsoft"), ("apple", "Apple"),
        ]
        for keyword, name in known:
            if keyword in server:
                return name
        return ""
