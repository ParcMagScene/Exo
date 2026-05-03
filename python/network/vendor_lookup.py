"""
EXO NetworkMap v2 — VendorLookup

Identification du fabricant d'un appareil via son adresse MAC.
Base OUI IEEE chargée au démarrage, indexée en mémoire.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger("networkmap.vendor")


class VendorLookup:
    """Lookup vendeur via base OUI IEEE (MAC prefix → fabricant)."""

    def __init__(self, oui_path: str | Path | None = None):
        self._db: dict[str, str] = {}
        if oui_path:
            self.load(oui_path)

    def load(self, path: str | Path) -> int:
        """Charge la base OUI depuis un fichier IEEE.

        Format attendu : XX-XX-XX   (hex)   Vendor Name
        Returns: nombre d'entrées chargées.
        """
        path = Path(path)
        if not path.exists():
            log.info("OUI file not found: %s — vendor lookup disabled", path)
            return 0

        count = 0
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    m = re.match(
                        r"^([0-9A-F]{2}-[0-9A-F]{2}-[0-9A-F]{2})\s+\(hex\)\s+(.+)$",
                        line.strip(),
                    )
                    if m:
                        prefix = m.group(1).replace("-", ":").upper()
                        self._db[prefix] = m.group(2).strip()
                        count += 1
            log.info("Loaded %d OUI entries from %s", count, path)
        except Exception as e:
            log.warning("OUI load error: %s", e)
        return count

    def lookup(self, mac: str) -> str:
        """Retourne le nom du fabricant pour un MAC donné.

        Args:
            mac: adresse MAC (format XX:XX:XX:XX:XX:XX ou XX-XX-XX-XX-XX-XX)

        Returns:
            Nom du fabricant, ou chaîne vide si inconnu.
        """
        prefix = mac.replace("-", ":").upper()[:8]
        return self._db.get(prefix, "")

    @property
    def count(self) -> int:
        """Nombre d'entrées OUI chargées."""
        return len(self._db)

    def stats(self) -> dict:
        return {
            "entries": len(self._db),
            "loaded": len(self._db) > 0,
        }
