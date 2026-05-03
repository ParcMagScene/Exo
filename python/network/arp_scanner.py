"""
EXO NetworkMap v2 — ARPScanner

Scan ARP local : extraction IP + MAC, détection gateway,
enrichissement vendor via OUI.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time

log = logging.getLogger("networkmap.arp")


class ARPScanner:
    """Scanner ARP : parse la table ARP système."""

    TIMEOUT = 2.0  # secondes

    def __init__(self, vendor_lookup=None):
        self._vendor_lookup = vendor_lookup  # callable(mac) -> str
        self._last_scan: float = 0
        self._gateway_ip: str = ""
        self._gateway_mac: str = ""

    @property
    def gateway_ip(self) -> str:
        return self._gateway_ip

    @property
    def gateway_mac(self) -> str:
        return self._gateway_mac

    async def scan(self) -> list[dict]:
        """Parse ARP table (Windows: arp -a). Returns list of devices."""
        t0 = time.monotonic()
        results: list[dict] = []
        self._gateway_ip = ""
        self._gateway_mac = ""

        try:
            proc = await asyncio.create_subprocess_exec(
                "arp", "-a",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=self.TIMEOUT + 8
            )
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

                vendor = ""
                if self._vendor_lookup:
                    vendor = self._vendor_lookup(mac)

                is_gateway = ip.endswith(".1") or ip.endswith(".254")
                if is_gateway and not self._gateway_mac:
                    self._gateway_ip = ip
                    self._gateway_mac = mac

                results.append({
                    "ip": ip,
                    "mac": mac,
                    "vendor": vendor,
                    "type": "router" if is_gateway else "unknown",
                    "online": True,
                    "source": "arp",
                    "last_seen": time.time(),
                })

        except asyncio.TimeoutError:
            log.warning("ARP scan timed out after %.1fs", self.TIMEOUT + 8)
        except Exception as e:
            log.warning("ARP scan failed: %s", e)

        elapsed_ms = round((time.monotonic() - t0) * 1000)
        self._last_scan = time.time()
        log.info("ARP scan: %d devices (%dms)", len(results), elapsed_ms)

        return results

    def metrics(self) -> dict:
        return {
            "gateway_ip": self._gateway_ip,
            "gateway_mac": self._gateway_mac,
            "last_scan": self._last_scan,
        }
