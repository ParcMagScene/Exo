"""local_audio_input.py - Gestion capture audio locale pour le core.

Permet de capturer l'audio directement depuis le PC pour:
- Tests et développement
- Mode demo interactif
- Contrôle sans Raspberry Pi
"""

import asyncio
import logging
from typing import Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)

try:
    from ..audio.audio_capture import AudioCapture, AudioFrame
    HAS_AUDIO_CAPTURE = True
except Exception as e:
    HAS_AUDIO_CAPTURE = False
    logger.warning(f"Audio capture not available: {e}")


class LocalAudioInputMode(Enum):
    """Mode de capture audio locale."""
    DISABLED = "disabled"       # Pas d'audio local
    DEMO = "demo"              # Mode demo (entrée texte simulée)
    MIC_DURATION = "mic_duration"   # Enregistrer X secondes
    MIC_SILENCE = "mic_silence"     # Enregistrer jusqu'au silence


class LocalAudioInput:
    """Gère la capture audio locale pour le core."""
    
    def __init__(
        self,
        mode: LocalAudioInputMode = LocalAudioInputMode.DISABLED,
        on_audio_available: Optional[Callable] = None
    ):
        """
        Initialise capture audio locale.
        
        Args:
            mode: Mode de capture (DISABLED, DEMO, MIC_DURATION, MIC_SILENCE)
            on_audio_available: Callback quand audio disponible
        """
        self.mode = mode
        self.on_audio_available = on_audio_available
        self.audio_capture: Optional[AudioCapture] = None
        self.recording = False
        
        if mode != LocalAudioInputMode.DISABLED and HAS_AUDIO_CAPTURE:
            try:
                self.audio_capture = AudioCapture()
                logger.info(f"✅ Audio local initialized (mode: {mode.value})")
            except Exception as e:
                logger.warning(f"Audio capture unavailable: {e}")
                self.mode = LocalAudioInputMode.DISABLED
    
    async def start_capture(self) -> None:
        """Démarre la capture audio locale."""
        if self.mode == LocalAudioInputMode.DISABLED or not self.audio_capture:
            logger.debug("Local audio capture is disabled")
            return
        
        self.recording = True
        logger.info(f"🎤 Starting local audio capture (mode: {self.mode.value})")
        
        try:
            if self.mode == LocalAudioInputMode.MIC_DURATION:
                # Record for 3 seconds
                await self._capture_duration(3.0)
            
            elif self.mode == LocalAudioInputMode.MIC_SILENCE:
                # Record until silence
                await self._capture_until_silence()
            
            elif self.mode == LocalAudioInputMode.DEMO:
                # Demo mode - no actual recording
                logger.info("📝 DEMO mode: Use text input or mic can be selected")
        
        except Exception as e:
            logger.error(f"Error during audio capture: {e}")
        
        finally:
            self.recording = False
    
    async def _capture_duration(self, duration: float) -> None:
        """Capture audio pour une durée spécifiée."""
        if not self.audio_capture:
            return
        
        logger.info(f"⏱️ Recording for {duration}s...")
        
        try:
            audio_data = await self.audio_capture.record_duration(duration)
            
            if audio_data:
                logger.info(f"✅ Captured {len(audio_data)} bytes")
                
                # Callback avec audio disponible
                if self.on_audio_available:
                    await self.on_audio_available(audio_data)
            else:
                logger.warning("No audio data captured")
        
        except Exception as e:
            logger.error(f"Error recording duration: {e}")
    
    async def _capture_until_silence(self) -> None:
        """Capture audio jusqu'au silence."""
        if not self.audio_capture:
            return
        
        logger.info("🎙️ Recording until silence detected...")
        
        try:
            audio_data = await self.audio_capture.record_until_silence(
                silence_threshold=500,
                silence_duration=1.0,
                max_recording=30.0
            )
            
            if audio_data:
                logger.info(f"✅ Captured {len(audio_data)} bytes")
                
                # Callback avec audio disponible
                if self.on_audio_available:
                    await self.on_audio_available(audio_data)
            else:
                logger.warning("No audio data captured")
        
        except Exception as e:
            logger.error(f"Error recording until silence: {e}")
    
    async def stop_capture(self) -> None:
        """Arrête la capture audio locale."""
        if self.audio_capture and self.recording:
            await self.audio_capture.stop_recording()
            self.recording = False
            logger.info("🎤 Audio capture stopped")
    
    def list_devices(self) -> None:
        """Liste les périphériques audio disponibles."""
        if self.audio_capture:
            self.audio_capture.list_devices()
        else:
            logger.warning("Audio capture not available")
    
    def enable_mode(self, mode: LocalAudioInputMode) -> None:
        """Change le mode de capture."""
        self.mode = mode
        logger.info(f"Audio mode changed to: {mode.value}")
