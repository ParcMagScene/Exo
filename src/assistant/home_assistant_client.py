import os
import aiohttp
from typing import Any, Dict, Optional


class HomeAssistantClient:
    """Minimal async client to call Home Assistant services via REST.

    Uses `HA_URL` and `HA_TOKEN` environment variables.
    """

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self.base_url = base_url or os.environ.get("HA_URL")
        self.token = token or os.environ.get("HA_TOKEN")
        if not self.base_url or not self.token:
            raise RuntimeError("HA_URL and HA_TOKEN must be set in environment")
        self._headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def call_service(self, domain: str, service: str, service_data: Dict[str, Any]):
        url = f"{self.base_url.rstrip('/')}/api/services/{domain}/{service}"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=service_data, headers=self._headers) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise RuntimeError(f"HA service call failed: {resp.status} {text}")
                return await resp.json()

    async def set_light(self, entity_id: str, on: bool = True, brightness: Optional[int] = None, color_name: Optional[str] = None):
        data: Dict[str, Any] = {"entity_id": entity_id}
        if on:
            service = "turn_on"
            if brightness is not None:
                data["brightness"] = brightness
            if color_name:
                data["color_name"] = color_name
        else:
            service = "turn_off"

        return await self.call_service("light", service, data)
