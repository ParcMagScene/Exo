"""
EXO NetworkMap v2 — MDNSScanner

Résolution DNS inverse + détection de services mDNS.
Enrichit les appareils découverts avec hostname, services, type.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time

log = logging.getLogger("networkmap.mdns")

# Services mDNS connus
KNOWN_SERVICES = {
    "_hue._tcp": "light",
    "_googlecast._tcp": "tv",
    "_homekit._tcp": "iot",
    "_alexa._tcp": "speaker",
    "_ewelink._tcp": "plug",
    "_tapo._tcp": "plug",
    "_airplay._tcp": "speaker",
    "_raop._tcp": "speaker",
    "_http._tcp": "unknown",
    "_ipp._tcp": "printer",
    "_smb._tcp": "nas",
}


class MDNSScanner:
    """Scanner mDNS : résolution inverse + inférence services."""

    TIMEOUT = 3.0  # secondes par résolution
    MAX_RETRIES = 1

    async def scan(self, ips: list[str]) -> dict[str, dict]:
        """Résolution DNS inverse pour chaque IP.

        Returns: dict keyed by IP with hostname, services, type.
        """
        t0 = time.monotonic()
        results: dict[str, dict] = {}

        tasks = [self._resolve(ip) for ip in ips]
        resolved = await asyncio.gather(*tasks, return_exceptions=True)

        for ip, result in zip(ips, resolved):
            if isinstance(result, Exception) or result is None:
                continue
            results[ip] = result

        elapsed_ms = round((time.monotonic() - t0) * 1000)
        log.info("mDNS scan: %d/%d resolved (%dms)",
                 len(results), len(ips), elapsed_ms)
        return results

    async def _resolve(self, ip: str) -> dict | None:
        """Résolution d'une IP avec retry."""
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                loop = asyncio.get_running_loop()
                hostname, _, _ = await asyncio.wait_for(
                    loop.run_in_executor(None, socket.gethostbyaddr, ip),
                    timeout=self.TIMEOUT,
                )
                if hostname:
                    services = self._infer_services(hostname)
                    dtype = self._infer_type(hostname)
                    return {
                        "hostname": hostname,
                        "services": services,
                        "type": dtype,
                    }
            except asyncio.TimeoutError:
                if attempt < self.MAX_RETRIES:
                    continue
            except (socket.herror, socket.gaierror, OSError):
                break
        return None

    @staticmethod
    def _infer_services(hostname: str) -> list[str]:
        """Infère les services mDNS probables à partir du hostname."""
        hl = hostname.lower()
        services: list[str] = []
        mapping = {
            "hue": "_hue._tcp", "philips": "_hue._tcp",
            "googlecast": "_googlecast._tcp", "chromecast": "_googlecast._tcp",
            "echo": "_alexa._tcp", "amazon": "_alexa._tcp",
            "ewelink": "_ewelink._tcp", "sonoff": "_ewelink._tcp",
            "homekit": "_homekit._tcp", "apple": "_homekit._tcp",
            "tapo": "_tapo._tcp", "tp-link": "_tapo._tcp",
            "airplay": "_airplay._tcp",
        }
        for keyword, service in mapping.items():
            if keyword in hl and service not in services:
                services.append(service)
        return services

    @staticmethod
    def _infer_type(hostname: str) -> str:
        """Infère le type d'appareil à partir du hostname."""
        hl = hostname.lower()
        rules = [
            (["echo", "amazon", "alexa"], "speaker"),
            (["tv", "samsung", "lg", "bravia"], "tv"),
            (["phone", "iphone", "android", "galaxy"], "phone"),
            (["pc", "desktop", "laptop", "workstation"], "pc"),
            (["nas", "synology", "qnap"], "nas"),
            (["cam", "ezviz", "hikvision", "dahua"], "camera"),
            (["hue", "philips", "signify"], "light"),
            (["tapo", "plug", "sonoff"], "plug"),
            (["printer", "epson", "canon", "hp-"], "printer"),
        ]
        for keywords, dtype in rules:
            if any(kw in hl for kw in keywords):
                return dtype
        return "unknown"
