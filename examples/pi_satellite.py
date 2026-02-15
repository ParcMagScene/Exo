"""example_pi_satellite.py - Exemple de client Wyoming sur Raspberry Pi.

À exécuter sur Pi Zero 2W ou Pi 5 pour envoyer l'audio vers le serveur central.

Utilise:
- Faster-Whisper (STT local)
- Wyoming protocol (WebSocket + audio brut)
- PyAudio pour capture microphone
"""

import asyncio
import json
import logging
import os
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import websockets  # type: ignore
    import pyaudio  # type: ignore
    import numpy as np
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    logger.error("Installer: pip install websockets pyaudio numpy faster-whisper")


class WyomingPiClient:
    """Client Wyoming pour Raspberry Pi."""

    def __init__(
        self,
        server_url: str = "ws://192.168.1.100:10700",
        room: str = "pi_zero",
        sample_rate: int = 16000,
        chunk_size: int = 512
    ):
        self.server_url = server_url
        self.room = room
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.websocket = None
        self.audio_stream = None

    async def connect(self):
        """Connexion au serveur Wyoming."""
        try:
            self.websocket = await websockets.connect(self.server_url)
            logger.info(f"✅ Connecté au serveur {self.server_url}")
        except Exception as e:
            logger.error(f"❌ Erreur connexion: {e}")
            return False
        return True

    async def start_audio_stream(self):
        """Démarre la capture microphone."""
        if not HAS_DEPS:
            logger.error("Dépendances manquantes")
            return

        try:
            p = pyaudio.PyAudio()
            self.audio_stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            logger.info("✅ Stream audio démarré")
        except Exception as e:
            logger.error(f"❌ Erreur PyAudio: {e}")

    async def send_audio_chunk(self):
        """Envoie un bloc audio."""
        if not self.audio_stream:
            return

        try:
            # Lire depuis le microphone
            data = self.audio_stream.read(self.chunk_size, exception_on_overflow=False)

            # Créer message Wyoming
            msg = {
                "event": "audio",
                "room": self.room,
                "format": "pcm16",
                "rate": self.sample_rate,
                "channels": 1,
                "timestamp": 0
            }

            # Envoyer JSON + audio brut
            if not self.websocket:
                logger.error("WebSocket non connectée")
                return
            
            message = json.dumps(msg).encode('utf-8') + b'\x00' + data
            await self.websocket.send(message)
            logger.debug(f"📤 Chunk envoyé ({len(data)} bytes)")

        except Exception as e:
            logger.error(f"Erreur envoi: {e}")

    async def run(self):
        """Boucle principale - capture et envoi continu."""
        if not await self.connect():
            return

        await self.start_audio_stream()

        try:
            # Boucle d'envoi audio
            while True:
                await self.send_audio_chunk()
                # Envoyer ~50 chunks/sec
                await asyncio.sleep(0.02)
        except KeyboardInterrupt:
            logger.info("⚠️ Arrêt...")
        finally:
            if self.websocket:
                await self.websocket.close()
            if self.audio_stream:
                self.audio_stream.stop_stream()
                self.audio_stream.close()


async def main():
    """Lance le client Wyoming."""
    # Configuration
    server_url = os.getenv("ASSISTANT_SERVER", "ws://192.168.1.100:10700")
    room_name = os.getenv("PI_ROOM", "pi_zero")

    logger.info(f"🎙️ Client Wyoming - Pièce: {room_name}")

    client = WyomingPiClient(
        server_url=server_url,
        room=room_name
    )

    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
