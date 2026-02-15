"""wyoming.py - Protocole Wyoming pour audio distribué multi-room.

Réception d'audio depuis:
- Raspberry Pi Zero 2 W (satellite 1)
- Raspberry Pi 5 (satellite 2 + media)

Format Wyoming: JSON + audio brut
"""

import asyncio
import json
import logging
from typing import Callable, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import websockets  # type: ignore
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    logger.warning("⚠️ websockets non disponible")


@dataclass
class WyomingAudioFrame:
    """Cadre audio Wyoming."""
    timestamp: float
    room: str
    audio_bytes: bytes
    session_id: str
    format: str = "pcm16"
    rate: int = 16000
    channels: int = 1


class WyomingServer:
    """Serveur Wyoming pour réception audio multi-room."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 10700,
        on_audio_frame: Optional[Callable] = None,
        on_text: Optional[Callable] = None
    ):
        """Initialise le serveur Wyoming."""
        self.host = host
        self.port = port
        self.on_audio_frame = on_audio_frame
        self.on_text = on_text
        
        self.running = False
        self.server = None
        self.clients = {}
        
        logger.info(f"✅ WyomingServer initialisé ({host}:{port})")

    async def start(self):
        """Démarre le serveur Wyoming."""
        if not HAS_WEBSOCKETS:
            logger.error("websockets non disponible")
            return
        
        self.running = True
        
        try:
            self.server = await websockets.serve(
                self._on_client_connect,
                self.host,
                self.port
            )
            
            logger.info(f"🎙️ Serveur Wyoming démarré ({self.host}:{self.port})")
            
            # Garder le serveur actif
            await asyncio.Future()  # Run forever
        
        except Exception as e:
            logger.error(f"Erreur démarrage Wyoming: {e}")
            self.running = False

    async def _on_client_connect(self, websocket, path):
        """Callback connexion client."""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.clients[client_id] = websocket
        
        logger.info(f"🤝 Client Wyoming connecté: {client_id}")
        
        try:
            async for message_raw in websocket:
                await self._process_message(message_raw, client_id)
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Erreur client Wyoming: {e}")
        
        finally:
            del self.clients[client_id]
            logger.info(f"👋 Client Wyoming déconnecté: {client_id}")

    async def _process_message(self, message_raw, client_id: str):
        """Traite un message Wyoming reçu."""
        try:
            # Les messages Wyoming sont JSON + audio
            if isinstance(message_raw, bytes):
                # Si bytes, extrait le JSON au début (séparé par null byte)
                null_idx = message_raw.find(b'\x00')
                if null_idx > 0:
                    json_part = message_raw[:null_idx].decode('utf-8')
                    audio_part = message_raw[null_idx+1:]
                else:
                    json_part = message_raw.decode('utf-8')
                    audio_part = b""
            else:
                json_part = str(message_raw)
                audio_part = b""
            
            data = json.loads(json_part)
            
            # Parser le header Wyoming
            event_type = data.get("event")
            
            if event_type == "recognize":
                # Texte issu du STT (satellite)
                text = data.get("text", "")
                room = data.get("room", "unknown")
                session_id = data.get("session_id", client_id)
                
                if text and self.on_text:
                    logger.info(f"📝 Texte reçu: '{text}' ({room})")
                    # Import local pour éviter les circular imports
                    from src.core.core import AudioRoom
                    room_enum = AudioRoom.PI_ZERO if "zero" in room else AudioRoom.PI_5
                    await self.on_text(text, room_enum, session_id)
            
            elif event_type == "audio-start":
                # Début d'un flux audio
                logger.info(f"🎙️ Flux audio démarré ({data})")
            
            elif event_type == "audio":
                # Cadre audio
                if audio_part and self.on_audio_frame:
                    # Import local pour éviter les circular imports
                    from src.core.core import AudioRoom
                    
                    room_str = data.get("room", "unknown")
                    room_enum = AudioRoom.PI_ZERO if "zero" in room_str else AudioRoom.PI_5
                    
                    frame = WyomingAudioFrame(
                        timestamp=data.get("timestamp", 0),
                        room=room_str,
                        audio_bytes=audio_part,
                        session_id=data.get("session_id", client_id),
                        format=data.get("format", "pcm16"),
                        rate=data.get("rate", 16000),
                        channels=data.get("channels", 1)
                    )
                    
                    # Convertir la room string en enum pour la frame
                    frame.room = room_enum.value
                    
                    await self.on_audio_frame(frame)
                    logger.debug(f"🎵 Cadre audio: {len(audio_part)} bytes")
            
            elif event_type == "audio-stop":
                logger.info(f"🛑 Flux audio arrêté")
        
        except json.JSONDecodeError as e:
            logger.error(f"Erreur parsing Wyoming JSON: {e}")
        except Exception as e:
            logger.error(f"Erreur traitement message Wyoming: {e}")

    async def send_response(self, session_id: str, text: str, audio_bytes: Optional[bytes] = None):
        """Envoie une réponse au client Wyoming."""
        response = {
            "event": "respond",
            "session_id": session_id,
            "text": text
        }
        
        message = json.dumps(response)
        
        if audio_bytes:
            message_bytes = message.encode('utf-8') + b'\x00' + audio_bytes
        else:
            message_bytes = message.encode('utf-8')
        
        # Envoyer à tous les clients (simplifié)
        for client_id, websocket in list(self.clients.items()):
            try:
                if isinstance(message_bytes, str):
                    await websocket.send(message_bytes)
                else:
                    await websocket.send(message_bytes)
            except Exception as e:
                logger.error(f"Erreur envoi réponse: {e}")

    async def stop(self):
        """Arrête le serveur."""
        self.running = False
        
        # Fermer tous les clients
        for client_id, ws in list(self.clients.items()):
            try:
                await ws.close()
            except:
                pass
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("🔌 Serveur Wyoming arrêté")
