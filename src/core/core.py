"""core.py - Orchestrateur principal avec machine d'états et gestion audio multi-room.

Architecture distribuée:
- Gère la priorité des flux audio (Pi Zero, Pi 5)
- Identifie la pièce source de la commande
- Coordonne Brain Engine, Hardware Accel, Home Bridge, GUI
- Supervision ultra-faible latence (<500ms)
"""

import asyncio
import logging
import os
from enum import Enum
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AssistantState(Enum):
    """Machine d'états de l'assistant."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"
    ERROR = "error"


class AudioRoom(Enum):
    """Identification des pièces (satellites)."""
    PI_ZERO = "pi_zero"  # Satellite 1
    PI_5 = "pi_5"        # Satellite 2 (Media + GUI)
    UNKNOWN = "unknown"


@dataclass
class AudioFrame:
    """Un cadre audio entrant."""
    timestamp: float
    room: AudioRoom
    audio_bytes: bytes
    session_id: str
    priority: int = 0  # 0=normal, 1=haute priorité


@dataclass
class CommandContext:
    """Contexte d'une commande."""
    user_input: str
    room: AudioRoom
    timestamp: datetime
    session_id: str
    confidence: float = 1.0


class AssistantCore:
    """Orchestrateur principal de l'assistant distribué."""

    def __init__(self):
        """Initialise le noyau principal."""
        self.state = AssistantState.IDLE
        self.current_room = AudioRoom.UNKNOWN
        
        # Files de priorité pour l'audio multi-room
        self.audio_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.response_queue: Dict[str, asyncio.Queue] = {}
        
        # Modules internes (seront initialisés en async)
        self.brain_engine = None
        self.hardware_accel = None
        self.home_bridge = None
        self.face_gui = None
        self.wyoming_server = None
        self.local_audio_input = None  # Capture audio locale
        
        # Configuration
        self.target_latency_ms = 500
        self.max_concurrent_sessions = 2
        self.active_sessions: Dict[str, CommandContext] = {}
        
        # Statistiques
        self.stats = {
            "total_commands": 0,
            "avg_latency": 0.0,
            "errors": 0
        }

    async def initialize(self):
        """Initialise tous les modules asynchrones."""
        logger.info("🚀 Initialisation de l'Assistant Core...")
        
        try:
            # Import tardif pour les dépendances conditionnelles
            from ..brain.brain_engine import BrainEngine
            from ..hardware.hardware_accel import HardwareAccelerator
            from ..integrations.home_bridge import HomeBridge
            from ..gui.visage_gui import FaceGUI
            from ..protocols.wyoming import WyomingServer
            from .local_audio_input import LocalAudioInput, LocalAudioInputMode
            
            # Initialiser les modules
            self.brain_engine = BrainEngine()
            await self.brain_engine.initialize()
            
            self.hardware_accel = HardwareAccelerator()
            await self.hardware_accel.initialize()
            
            self.home_bridge = HomeBridge()
            await self.home_bridge.connect()
            
            self.face_gui = FaceGUI()
            await self.face_gui.initialize()
            
            # Initialiser capture audio locale (par défaut DISABLED)
            local_audio_mode = os.getenv("LOCAL_AUDIO_MODE", "disabled").lower()
            if local_audio_mode == "mic_duration":
                mode = LocalAudioInputMode.MIC_DURATION
            elif local_audio_mode == "mic_silence":
                mode = LocalAudioInputMode.MIC_SILENCE
            elif local_audio_mode == "demo":
                mode = LocalAudioInputMode.DEMO
            else:
                mode = LocalAudioInputMode.DISABLED
            
            self.local_audio_input = LocalAudioInput(
                mode=mode,
                on_audio_available=self._on_local_audio_available
            )
            
            self.wyoming_server = WyomingServer(
                on_audio_frame=self._on_audio_frame,
                on_text=self._on_text_input
            )
            
            logger.info("✅ Tous les modules initialisés avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation: {e}")
            self.state = AssistantState.ERROR
            raise

    async def start(self):
        """Démarre la boucle principale."""
        logger.info("▶️ Démarrage de la boucle principale...")
        
        # Lancer les services asynchrones
        tasks: List[Any] = [
            asyncio.create_task(self._audio_processing_loop()),
            asyncio.create_task(self._state_machine_loop()),
        ]
        
        if self.wyoming_server:
            tasks.append(asyncio.create_task(self.wyoming_server.start()))
        
        if self.face_gui and hasattr(self.face_gui, 'render_loop'):
            tasks.append(asyncio.create_task(self.face_gui.render_loop()))
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Erreur dans la boucle principale: {e}")
            await self.shutdown()

    async def _audio_processing_loop(self):
        """Boucle de traitement audio multi-room avec priorités."""
        logger.info("🎙️ Démarrage du traitement audio...")
        
        while True:
            try:
                # Récupérer le cadre audio avec la plus haute priorité
                priority, frame = await asyncio.wait_for(
                    self.audio_queue.get(),
                    timeout=60.0
                )
                
                start_time = datetime.now()
                
                # Identifier la pièce source
                self.current_room = frame.room
                logger.info(f"🎤 Audio reçu de: {frame.room.value}")
                
                # Transférer au STT (Hardware Accel)
                if self.face_gui:
                    await self.face_gui.set_state(AssistantState.LISTENING)
                
                if not self.hardware_accel:
                    logger.error("Hardware accelerator not available")
                    continue
                
                transcript = await self.hardware_accel.transcribe_audio(
                    frame.audio_bytes,
                    room=frame.room
                )
                
                if not transcript:
                    logger.warning("⚠️ Transcription échouée ou vide")
                    continue
                
                # Créer un contexte de commande
                ctx = CommandContext(
                    user_input=transcript,
                    room=frame.room,
                    timestamp=start_time,
                    session_id=frame.session_id,
                    confidence=0.95
                )
                
                # Mettre en file pour le traitement par le Brain
                self.active_sessions[frame.session_id] = ctx
                
                # Mesure de latence partielle
                latency_ms = (datetime.now() - start_time).total_seconds() * 1000
                logger.info(f"⏱️ Latence STT: {latency_ms:.1f}ms")
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Erreur dans le traitement audio: {e}")

    async def _state_machine_loop(self):
        """Machine d'états principale."""
        while True:
            try:
                if self.state == AssistantState.IDLE:
                    await asyncio.sleep(0.1)
                
                elif self.state == AssistantState.LISTENING:
                    # En écoute...
                    await asyncio.sleep(0.05)
                
                elif self.state == AssistantState.PROCESSING:
                    # Traitement des commandes actives
                    if self.active_sessions:
                        session_id = list(self.active_sessions.keys())[0]
                        ctx = self.active_sessions[session_id]
                        
                        if self.face_gui:
                            await self.face_gui.set_state(AssistantState.PROCESSING)
                        
                        # Appel au Brain Engine
                        if self.brain_engine:
                            response = await self.brain_engine.process_command(
                                text=ctx.user_input,
                                room=ctx.room.value,
                                context={
                                    "user_room": ctx.room.value,
                                    "timestamp": ctx.timestamp.isoformat()
                                }
                            )
                            
                            # Exécuter les actions (Function Calling)
                            if response.get("function_calls"):
                                await self._execute_functions(
                                    response["function_calls"],
                                    room=ctx.room
                                )
                            
                            # Envoyer la réponse TTS
                            if response.get("text"):
                                if self.face_gui:
                                    await self.face_gui.set_state(AssistantState.RESPONDING)
                                # await self.hardware_accel.text_to_speech(response["text"])
                        
                        # Nettoyage
                        del self.active_sessions[session_id]
                        self.state = AssistantState.IDLE
                
                elif self.state == AssistantState.RESPONDING:
                    await asyncio.sleep(0.05)
                
                elif self.state == AssistantState.ERROR:
                    if self.face_gui:
                        await self.face_gui.set_state(AssistantState.ERROR)
                    await asyncio.sleep(1)
                    self.state = AssistantState.IDLE
                
            except Exception as e:
                logger.error(f"Erreur machine d'états: {e}")
                self.state = AssistantState.ERROR

    async def _on_audio_frame(self, frame: AudioFrame):
        """Callback du serveur Wyoming - réception d'un cadre audio."""
        await self.audio_queue.put((frame.priority, frame))
        logger.debug(f"📦 Frame ajoutée à la queue (session: {frame.session_id})")
    
    async def _on_local_audio_available(self, audio_bytes: bytes):
        """Callback audio local - quand audio local capturé."""
        import uuid
        session_id = str(uuid.uuid4())[:8]
        
        # Créer frame audio comme si venu de Wyoming
        frame = AudioFrame(
            timestamp=datetime.now().timestamp(),
            room=AudioRoom.UNKNOWN,  # Local = UNKNOWN room
            audio_bytes=audio_bytes,
            session_id=session_id,
            priority=0
        )
        
        await self.audio_queue.put((frame.priority, frame))
        logger.info(f"🎤 Local audio captured ({len(audio_bytes)} bytes, session: {session_id})")

    async def _on_text_input(self, text: str, room: AudioRoom, session_id: str):
        """Callback texte direct (bypass STT)."""
        ctx = CommandContext(
            user_input=text,
            room=room,
            timestamp=datetime.now(),
            session_id=session_id
        )
        self.active_sessions[session_id] = ctx
        self.state = AssistantState.PROCESSING
        logger.info(f"📝 Texte reçu: {text} (pièce: {room.value})")

    async def _execute_functions(self, function_calls: List[Dict], room: AudioRoom):
        """Exécute les fonction calls (Function Calling)."""
        for func in function_calls:
            func_name = func.get("name")
            func_args = func.get("arguments", {})
            
            if not func_name:
                logger.warning("Function call without name")
                continue
            
            logger.info(f"🔧 Exécution fonction: {func_name}")
            
            try:
                # Dispatcher aux modules appropriés
                if func_name.startswith("home."):
                    if self.home_bridge:
                        await self.home_bridge.call_function(func_name, func_args)
                
                elif func_name.startswith("music."):
                    # Contrôle Mopidy/TIDAL
                    if self.hardware_accel:
                        await self.hardware_accel.control_music(func_name, func_args)
                
                elif func_name.startswith("room."):
                    # Actions contextuelles à la pièce
                    func_args["room"] = room.value
                    if self.home_bridge:
                        await self.home_bridge.call_function(func_name, func_args)
                
                elif func_name.startswith("petkit."):
                    # Statut Petkit
                    if self.home_bridge:
                        await self.home_bridge.get_petkit_status(func_args)
            except Exception as e:
                logger.error(f"Error executing function {func_name}: {e}")

    async def shutdown(self):
        """Arrête proprement l'assistant."""
        logger.info("🛑 Arrêt de l'Assistant...")
        
        if self.local_audio_input:
            await self.local_audio_input.stop_capture()
        
        if self.home_bridge:
            await self.home_bridge.disconnect()
        
        if self.wyoming_server:
            await self.wyoming_server.stop()
        
        if self.face_gui:
            await self.face_gui.shutdown()
        
        if self.brain_engine:
            await self.brain_engine.close()
        
        logger.info("✅ Assistant arrêté")
