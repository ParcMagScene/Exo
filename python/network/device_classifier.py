"""
EXO NetworkMap v2 — DeviceClassifier

Classification automatique des appareils réseau.
Basée sur : vendor, services mDNS, SSDP, hostname, type connu.
"""

from __future__ import annotations

import logging

log = logging.getLogger("networkmap.classifier")

# Types supportés
DEVICE_TYPES = [
    "router", "pc", "phone", "tv", "camera", "speaker",
    "light", "plug", "nas", "printer", "iot", "unknown",
]

# Règles vendor → type
_VENDOR_RULES: list[tuple[list[str], str]] = [
    (["philips", "signify"], "light"),
    (["tp-link", "tapo"], "plug"),
    (["amazon"], "speaker"),
    (["samsung"], "tv"),
    (["lg electronics", "lg innotek"], "tv"),
    (["sony"], "tv"),
    (["synology", "qnap", "western digital", "seagate"], "nas"),
    (["ezviz", "hikvision", "dahua", "reolink"], "camera"),
    (["apple"], "phone"),
    (["google"], "iot"),
    (["espressif", "tuya", "shelly"], "iot"),
    (["hp ", "epson", "canon", "brother"], "printer"),
    (["intel", "dell", "lenovo", "asus", "acer", "msi"], "pc"),
    (["realtek", "qualcomm", "broadcom"], "unknown"),
]

# Règles hostname → type
_HOSTNAME_RULES: list[tuple[list[str], str]] = [
    (["echo", "amazon", "alexa"], "speaker"),
    (["tv", "samsung", "lg", "bravia", "roku", "chromecast"], "tv"),
    (["phone", "iphone", "android", "galaxy", "pixel"], "phone"),
    (["pc", "desktop", "laptop", "workstation"], "pc"),
    (["nas", "synology", "qnap"], "nas"),
    (["cam", "ezviz", "hikvision", "dahua"], "camera"),
    (["hue", "philips", "signify", "bulb", "lamp"], "light"),
    (["tapo", "plug", "switch", "sonoff"], "plug"),
    (["printer", "epson", "canon", "hp-"], "printer"),
    (["esp", "tuya", "shelly", "zigbee"], "iot"),
]

# Services mDNS → type  
_SERVICE_RULES: dict[str, str] = {
    "_hue._tcp": "light",
    "_googlecast._tcp": "tv",
    "_homekit._tcp": "iot",
    "_alexa._tcp": "speaker",
    "_ewelink._tcp": "plug",
    "_tapo._tcp": "plug",
    "_airplay._tcp": "speaker",
    "_raop._tcp": "speaker",
    "_ipp._tcp": "printer",
    "_smb._tcp": "nas",
}


class DeviceClassifier:
    """Classifie les appareils réseau par type."""

    def classify(self, device: dict) -> str:
        """Classifie un appareil.

        Args:
            device: dict avec keys optionnelles: vendor, hostname/name,
                    services, type, ssdp_manufacturer.

        Returns:
            Type d'appareil (str).
        """
        # Si déjà classifié et pas "unknown", garder
        existing = device.get("type", "unknown")
        if existing != "unknown":
            return existing

        # 1. Services mDNS (plus fiable)
        services = device.get("services", [])
        for svc in services:
            if svc in _SERVICE_RULES:
                return _SERVICE_RULES[svc]

        # 2. SSDP manufacturer
        manufacturer = device.get("ssdp_manufacturer", "").lower()
        if manufacturer:
            for keywords, dtype in _VENDOR_RULES:
                if any(kw in manufacturer for kw in keywords):
                    return dtype

        # 3. Hostname / name
        hostname = (device.get("hostname", "") or device.get("name", "")).lower()
        if hostname:
            for keywords, dtype in _HOSTNAME_RULES:
                if any(kw in hostname for kw in keywords):
                    return dtype

        # 4. Vendor (OUI)
        vendor = device.get("vendor", "").lower()
        if vendor:
            for keywords, dtype in _VENDOR_RULES:
                if any(kw in vendor for kw in keywords):
                    return dtype

        return "unknown"

    def classify_batch(self, devices: list[dict]) -> list[dict]:
        """Classifie une liste d'appareils en place.

        Returns la même liste avec le champ 'type' mis à jour.
        """
        for dev in devices:
            dev["type"] = self.classify(dev)
        return devices
