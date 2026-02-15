"""home_bridge.py - Pont vers Home Assistant (WebSocket + API REST).

Contrôle de:
- Philips Hue / IKEA Hub
- Samsung TV/Soundbar
- Caméras EZWIZ
- Dispositifs Petkit
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import aiohttp  # type: ignore
    import websockets  # type: ignore
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    logger.warning("⚠️ aiohttp/websockets non disponibles")


class HomeBridge:
    """Gestionnaire d'intégrations Home Assistant."""

    def __init__(self):
        """Initialise le bridge."""
        self.ha_url = os.getenv("HA_URL", "http://homeassistant.local:8123")
        self.ha_token = os.getenv("HA_TOKEN")
        
        if not self.ha_token:
            raise ValueError("HA_TOKEN requis dans les variables d'environnement")
        
        self._ws_connection = None
        self._message_id = 0
        self._pending_responses: Dict[int, asyncio.Future] = {}
        self._event_callbacks: Dict[str, list] = {}
        
        logger.info("✅ HomeBridge initialisé")

    async def connect(self):
        """Établit la connexion WebSocket à Home Assistant."""
        if not HAS_DEPS:
            logger.error("Dépendances manquantes")
            return
        
        try:
            ws_url = self.ha_url.replace("http", "ws").rstrip("/") + "/api/websocket"
            
            async with aiohttp.ClientSession() as session:
                self._ws_connection = await websockets.connect(ws_url)
            
            # Authentification
            auth_msg = await self._ws_connection.recv()
            auth_response = json.loads(auth_msg)
            
            if auth_response.get("type") == "auth_required":
                await self._ws_connection.send(json.dumps({
                    "type": "auth",
                    "access_token": self.ha_token
                }))
                
                auth_result = json.loads(await self._ws_connection.recv())
                
                if auth_result.get("type") == "auth_ok":
                    logger.info("✅ Connecté à Home Assistant")
                    # Lancer la boucle d'écoute
                    asyncio.create_task(self._ws_listener())
                else:
                    logger.error(f"Authentification échouée: {auth_result}")
                    self._ws_connection = None
        
        except Exception as e:
            logger.error(f"Erreur connexion HA: {e}")
            self._ws_connection = None

    async def _ws_listener(self):
        """Écoute les messages WebSocket de HA."""
        if not self._ws_connection:
            return
        
        try:
            while True:
                message = await self._ws_connection.recv()
                data = json.loads(message)
                
                # Traiter les réponses
                if "id" in data and data["id"] in self._pending_responses:
                    future = self._pending_responses.pop(data["id"])
                    future.set_result(data)
                
                # Traiter les événements
                if data.get("type") == "event":
                    event_type = data.get("event", {}).get("event_type")
                    if event_type in self._event_callbacks:
                        for callback in self._event_callbacks[event_type]:
                            asyncio.create_task(callback(data))
        
        except Exception as e:
            logger.error(f"Erreur WebSocket: {e}")
            self._ws_connection = None

    async def call_service(
        self,
        domain: str,
        service: str,
        service_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Appelle un service Home Assistant."""
        if not service_data:
            service_data = {}
        
        self._message_id += 1
        msg_id = self._message_id
        
        message = {
            "id": msg_id,
            "type": "call_service",
            "domain": domain,
            "service": service,
            "service_data": service_data
        }
        
        try:
            if self._ws_connection:
                # Via WebSocket
                future = asyncio.Future()
                self._pending_responses[msg_id] = future
                
                await self._ws_connection.send(json.dumps(message))
                response = await asyncio.wait_for(future, timeout=5.0)
                
                logger.info(f"✅ Service {domain}.{service} appelé")
                return response
            else:
                # Fallback REST API
                return await self._call_service_rest(domain, service, service_data)
        
        except asyncio.TimeoutError:
            logger.error(f"Timeout service {domain}.{service}")
            return {}
        except Exception as e:
            logger.error(f"Erreur appel service: {e}")
            return {}

    async def _call_service_rest(
        self,
        domain: str,
        service: str,
        service_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Appelle un service via REST API."""
        url = f"{self.ha_url.rstrip('/')}/api/services/{domain}/{service}"
        
        headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=service_data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5.0)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.error(f"Service REST error {resp.status}")
                        return {}
        except Exception as e:
            logger.error(f"Erreur REST: {e}")
            return {}

    async def call_function(self, func_name: str, args: Dict[str, Any]):
        """Dispatcher des fonction calls du Brain."""
        parts = func_name.split(".")
        
        if func_name.startswith("home.light"):
            await self._control_light(args)
        
        elif func_name.startswith("home.media"):
            await self._control_media(args)
        
        elif func_name.startswith("home.camera"):
            await self._control_camera(args)
        
        else:
            logger.warning(f"Fonction inconnue: {func_name}")

    async def _control_light(self, args: Dict[str, Any]):
        """Contrôle l'éclairage (HUE/IKEA)."""
        room = args.get("room", "salon")
        action = args.get("action", "on")
        brightness = args.get("brightness")
        color = args.get("color")
        
        # Mapper pièce -> entity_id
        entity_map = {
            "salon": "light.salon_hue",
            "chambre": "light.chambre_hue",
            "cuisine": "light.cuisine_ikea",
            "salle_bain": "light.salle_bain_hue",
        }
        
        entity_id = entity_map.get(room, f"light.{room.lower().replace(' ', '_')}")
        
        service_data = {"entity_id": entity_id}
        
        if action == "on":
            if brightness is not None:
                service_data["brightness"] = str(int(brightness * 255 / 100))
            if color:
                service_data["color_name"] = color
            
            await self.call_service("light", "turn_on", service_data)
            logger.info(f"💡 Lumière {room} allumée")
        
        elif action == "off":
            await self.call_service("light", "turn_off", service_data)
            logger.info(f"💡 Lumière {room} éteinte")
        
        elif action == "dim":
            service_data["brightness"] = str(int(brightness * 255 / 100) if brightness else 128)
            await self.call_service("light", "turn_on", service_data)
            logger.info(f"💡 Lumière {room} dimée")

    async def _control_media(self, args: Dict[str, Any]):
        """Contrôle TV/Soundbar Samsung."""
        device = args.get("device", "tv")
        action = args.get("action", "on")
        value = args.get("value")
        
        entity_id = f"media_player.samsung_{device}"
        
        if action == "on":
            await self.call_service("media_player", "turn_on", {"entity_id": entity_id})
            logger.info(f"📺 {device.upper()} allumé")
        
        elif action == "off":
            await self.call_service("media_player", "turn_off", {"entity_id": entity_id})
            logger.info(f"📺 {device.upper()} éteint")
        
        elif action == "volume" and value is not None:
            await self.call_service(
                "media_player",
                "volume_set",
                {
                    "entity_id": entity_id,
                    "volume_level": value / 100
                }
            )
            logger.info(f"🔊 Volume {device}: {value}%")

    async def _control_camera(self, args: Dict[str, Any]):
        """Contrôle caméras EZWIZ."""
        camera_id = args.get("camera_id", "camera_entree")
        action = args.get("action", "view")
        
        entity_id = f"camera.ezwiz_{camera_id}"
        
        if action == "record":
            await self.call_service(
                "record",
                "start",
                {"entity_id": entity_id}
            )
            logger.info(f"📹 Enregistrement {camera_id} démarré")
        
        elif action == "stop":
            await self.call_service(
                "record",
                "stop",
                {"entity_id": entity_id}
            )
            logger.info(f"📹 Enregistrement {camera_id} arrêté")

    async def get_petkit_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Récupère le statut Petkit."""
        device_id = args.get("device_id", "kitten_box")
        metric = args.get("metric", "all")
        
        entity_ids = {
            "litter_level": f"sensor.{device_id}_litter_level",
            "last_use": f"sensor.{device_id}_last_use",
            "health": f"sensor.{device_id}_health_alert"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.ha_token}"}
                
                status = {}
                
                if metric == "all":
                    metrics_to_fetch = entity_ids.keys()
                else:
                    metrics_to_fetch = [metric]
                
                for met in metrics_to_fetch:
                    entity_id = entity_ids.get(met)
                    if not entity_id:
                        continue
                    
                    url = f"{self.ha_url.rstrip('/')}/api/states/{entity_id}"
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            status[met] = data.get("state")
                
                logger.info(f"🐱 Petkit status: {status}")
                return status
        
        except Exception as e:
            logger.error(f"Erreur Petkit: {e}")
            return {}

    async def subscribe_event(self, event_type: str, callback: Callable):
        """S'abonne à un événement HA."""
        if event_type not in self._event_callbacks:
            self._event_callbacks[event_type] = []
        
        self._event_callbacks[event_type].append(callback)
        logger.info(f"📢 Abonnement à {event_type}")

    async def get_entities_by_domain(self, domain: str) -> Dict[str, Any]:
        """Récupère toutes les entités d'un domaine."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.ha_token}"}
                url = f"{self.ha_url.rstrip('/')}/api/states"
                
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        all_states = await resp.json()
                        return {
                            entity["entity_id"]: entity
                            for entity in all_states
                            if entity["entity_id"].startswith(domain)
                        }
        except Exception as e:
            logger.error(f"Erreur récupération entités: {e}")
        
        return {}

    async def disconnect(self):
        """Ferme la connexion."""
        if self._ws_connection:
            await self._ws_connection.close()
        logger.info("🔌 HomeBridge déconnecté")
