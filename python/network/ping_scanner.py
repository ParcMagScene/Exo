"""
EXO NetworkMap v2 — PingScanner

Ping sweep : mesure de latence par appareil, détection appareils silencieux.
Utilise ping ICMP natif (subprocess) pour compatibilité Windows/Linux.
"""

from __future__ import annotations

import asyncio
import logging
import platform
import re
import time

log = logging.getLogger("networkmap.ping")


class PingScanner:
    """Ping sweep : mesure latence par IP."""

    TIMEOUT = 1.0  # secondes par ping

    async def scan(self, ips: list[str]) -> dict[str, dict]:
        """Ping toutes les IPs en parallèle.

        Returns: dict keyed by IP with {reachable, latency_ms}.
        """
        t0 = time.monotonic()
        results: dict[str, dict] = {}

        # Limiter la concurrence pour éviter la saturation
        sem = asyncio.Semaphore(20)
        tasks = [self._ping_with_sem(sem, ip) for ip in ips]
        done = await asyncio.gather(*tasks, return_exceptions=True)

        for ip, result in zip(ips, done):
            if isinstance(result, Exception):
                results[ip] = {"reachable": False, "latency_ms": None}
            else:
                results[ip] = result

        reachable = sum(1 for r in results.values() if r["reachable"])
        elapsed_ms = round((time.monotonic() - t0) * 1000)
        log.info("Ping sweep: %d/%d reachable (%dms)", reachable, len(ips), elapsed_ms)
        return results

    async def _ping_with_sem(self, sem: asyncio.Semaphore, ip: str) -> dict:
        async with sem:
            return await self.ping(ip)

    async def ping(self, ip: str) -> dict:
        """Ping une IP. Returns {reachable, latency_ms}."""
        is_windows = platform.system().lower() == "windows"
        cmd = ["ping", "-n" if is_windows else "-c", "1",
               "-w" if is_windows else "-W",
               str(int(self.TIMEOUT * 1000)) if is_windows else str(int(self.TIMEOUT)),
               ip]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=self.TIMEOUT + 2
            )
            output = stdout.decode("utf-8", errors="ignore")

            if proc.returncode == 0:
                latency = self._extract_latency(output)
                return {"reachable": True, "latency_ms": latency}
            return {"reachable": False, "latency_ms": None}

        except asyncio.TimeoutError:
            return {"reachable": False, "latency_ms": None}
        except Exception:
            return {"reachable": False, "latency_ms": None}

    @staticmethod
    def _extract_latency(output: str) -> float | None:
        """Extraire la latence depuis la sortie ping."""
        # Windows: "temps=1ms" ou "time=1ms"
        # Linux: "time=1.23 ms"
        m = re.search(r"(?:temps?|time)[<=](\d+(?:\.\d+)?)\s*ms", output, re.IGNORECASE)
        if m:
            return float(m.group(1))
        return None
