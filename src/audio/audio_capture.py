"""Capture audio en temps réel depuis le microphone."""

import asyncio
import logging
from typing import Optional, Callable, List, Any
from dataclasses import dataclass
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

# Importation conditionnelle de PyAudio
try:
    import pyaudio  # type: ignore
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False
    logger.warning("PyAudio non disponible. Audio capture désactivée.")


@dataclass
class AudioFrame:
    """Représente une frame audio capturée."""
    data: bytes          # PCM16 audio data
    sample_rate: int
    channels: int
    timestamp: datetime
    
    def to_numpy(self) -> np.ndarray:
        """Convertit en array numpy."""
        return np.frombuffer(self.data, dtype=np.int16)


class AudioCapture:
    """Capture audio en temps réel avec mise en buffer."""
    
    SAMPLE_RATE = 16000
    CHUNK_SIZE = 1024
    CHANNELS = 1
    FORMAT = 'int16'
    
    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        chunk_size: int = CHUNK_SIZE,
        channels: int = CHANNELS,
        device_index: Optional[int] = None
    ):
        """
        Initialise le capteur audio.
        
        Args:
            sample_rate: Fréquence d'échantillonnage (Hz)
            chunk_size: Taille du buffer 
            channels: Nombre de canaux (1=mono, 2=stéréo)
            device_index: Indice du périphérique (None = défaut)
        """
        if not HAS_PYAUDIO:
            raise RuntimeError("PyAudio not available. Install with: pip install pyaudio")
        
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.device_index = device_index
        
        self.stream: Optional[pyaudio.Stream] = None
        self._is_recording = False
        self._buffer: List[bytes] = []
        self._callbacks: List[Callable[[AudioFrame], None]] = []
        
        self._pa = pyaudio.PyAudio()
    
    def __del__(self):
        """Nettoie les ressources."""
        if self._pa:
            self._pa.terminate()
    
    def list_devices(self) -> None:
        """Liste tous les périphériques audio disponibles."""
        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            logger.info(f"Device {i}: {info.get('name')}")
            logger.info(f"  Channels: {info.get('maxInputChannels')}, Sample Rate: {info.get('defaultSampleRate')}")
    
    async def start_recording(self) -> None:
        """Démarre l'enregistrement."""
        if not HAS_PYAUDIO:
            logger.error("PyAudio pas disponible")
            return
        
        try:
            self.stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=None  # Non-callback mode pour asyncio
            )
            self.stream.start_stream()
            self._is_recording = True
            logger.info(f"🎤 Enregistrement démarré ({self.sample_rate}Hz, {self.channels} canal)")
        except Exception as e:
            logger.error(f"Erreur démarrage enregistrement: {e}")
    
    async def stop_recording(self) -> None:
        """Arrête l'enregistrement."""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self._is_recording = False
            logger.info("🎙️ Enregistrement arrêté")
    
    async def capture_chunk(self) -> Optional[AudioFrame]:
        """Capture une chunk audio depuis le microphone."""
        if not self.stream or not self._is_recording:
            return None
        
        try:
            # Vérifier que le stream est disponible
            if not self.stream:
                raise RuntimeError("Flux audio non initialisé")
            
            # Lire async avec timeout court
            loop = asyncio.get_event_loop()
            stream = self.stream  # Capturer dans une variable locale pour type checking
            data = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: stream.read(self.chunk_size, exception_on_overflow=False)
                ),
                timeout=2.0
            )
            
            frame = AudioFrame(
                data=data,
                sample_rate=self.sample_rate,
                channels=self.channels,
                timestamp=datetime.now()
            )
            
            # Appeler les callbacks
            for callback in self._callbacks:
                try:
                    callback(frame)
                except Exception as e:
                    logger.error(f"Erreur callback audio: {e}")
            
            return frame
            
        except asyncio.TimeoutError:
            logger.debug("Timeout audio capture")
            return None
        except Exception as e:
            logger.error(f"Erreur capture audio: {e}")
            return None
    
    def add_callback(self, callback: Callable[[AudioFrame], None]) -> None:
        """Ajoute un callback pour chaque frame capturée."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[AudioFrame], None]) -> None:
        """Supprime un callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def get_buffer(self) -> bytes:
        """Récupère et vide le buffer audio."""
        audio_data = b"".join(self._buffer)
        self._buffer.clear()
        return audio_data
    
    def clear_buffer(self) -> None:
        """Vide le buffer audio."""
        self._buffer.clear()
    
    async def record_duration(self, duration_seconds: float) -> bytes:
        """Enregistre pendant une durée spécifiée."""
        await self.start_recording()
        start_time = datetime.now()
        
        try:
            while (datetime.now() - start_time).total_seconds() < duration_seconds:
                frame = await self.capture_chunk()
                if frame:
                    self._buffer.append(frame.data)
                await asyncio.sleep(0.01)  # Petit délai pour ne pas bloquer
        finally:
            await self.stop_recording()
        
        return self.get_buffer()
    
    async def record_until_silence(
        self,
        silence_threshold: int = 500,  # Amplitude RMS
        silence_duration: float = 1.0,   # Secondes
        max_recording: float = 30.0    # Max 30s
    ) -> bytes:
        """Enregistre jusqu'à silence détecté."""
        await self.start_recording()
        
        silent_chunks = 0
        chunks_for_silence = int(silence_duration * self.sample_rate / self.chunk_size)
        start_time = datetime.now()
        
        try:
            while True:
                # Vérifier timeout de sécurité
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= max_recording:
                    logger.warning(f"Enregistrement dépassé max_recording ({max_recording}s)")
                    break
                
                frame = await self.capture_chunk()
                if not frame:
                    await asyncio.sleep(0.01)
                    continue
                
                # Calculer RMS (energy)
                audio_array = frame.to_numpy()
                rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
                
                self._buffer.append(frame.data)
                
                # Détecter silence
                if rms < silence_threshold:
                    silent_chunks += 1
                    if silent_chunks >= chunks_for_silence:
                        logger.info(f"🤐 Silence détecté (RMS: {rms:.0f})")
                        break
                else:
                    silent_chunks = 0
                
                await asyncio.sleep(0.01)
        finally:
            await self.stop_recording()
        
        return self.get_buffer()


class AudioStats:
    """Collecte des statistiques sur l'audio capturé."""
    
    def __init__(self):
        self.frames: List[AudioFrame] = []
    
    def add_frame(self, frame: AudioFrame) -> None:
        """Ajoute une frame aux stats."""
        self.frames.append(frame)
    
    def get_duration(self) -> float:
        """Retourne la durée totale en secondes."""
        if len(self.frames) < 2:
            return 0.0
        
        start = self.frames[0].timestamp
        end = self.frames[-1].timestamp
        return (end - start).total_seconds()
    
    def get_energy(self) -> dict:
        """Calcule l'énergie (RMS) des frames."""
        if not self.frames:
            return {}
        
        rms_values = []
        for frame in self.frames:
            audio_array = frame.to_numpy()
            rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
            rms_values.append(rms)
        
        return {
            "min": float(min(rms_values)),
            "max": float(max(rms_values)),
            "mean": float(np.mean(rms_values)),
            "std": float(np.std(rms_values)),
            "count": len(rms_values)
        }
    
    def get_summary(self) -> dict:
        """Résumé complet des stats."""
        energy = self.get_energy()
        duration = self.get_duration()
        
        return {
            "frames": len(self.frames),
            "duration_sec": duration,
            "energy": energy,
            "sample_rate": self.frames[0].sample_rate if self.frames else 0,
            "channels": self.frames[0].channels if self.frames else 0
        }


class AudioDevice:
    """Wrapper pour périphérique audio avec infos détaillées."""
    
    def __init__(self, index: int, info: Any):
        self.index = index
        self.name = info.get("name", "Unknown") if hasattr(info, 'get') else getattr(info, 'name', 'Unknown')
        self.max_input_channels = info.get("maxInputChannels", 0) if hasattr(info, 'get') else getattr(info, 'maxInputChannels', 0)
        self.max_output_channels = info.get("maxOutputChannels", 0) if hasattr(info, 'get') else getattr(info, 'maxOutputChannels', 0)
        self.default_sample_rate = info.get("defaultSampleRate", 0) if hasattr(info, 'get') else getattr(info, 'defaultSampleRate', 0)
        self.host_api = info.get("hostApi", -1) if hasattr(info, 'get') else getattr(info, 'hostApi', -1)
    
    def __str__(self) -> str:
        return f"Device {self.index}: {self.name} ({self.max_input_channels} in, {self.max_output_channels} out)"
    
    @property
    def is_input(self) -> bool:
        """Vrai si le device supporte l'input."""
        return self.max_input_channels > 0
    
    @property
    def is_output(self) -> bool:
        """Vrai si le device supporte l'output."""
        return self.max_output_channels > 0


def list_audio_devices() -> List[AudioDevice]:
    """Liste tous les périphériques audio disponibles."""
    if not HAS_PYAUDIO:
        logger.error("PyAudio non disponible")
        return []
    
    pa = pyaudio.PyAudio()
    devices = []
    
    try:
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            device = AudioDevice(i, info)
            devices.append(device)
    finally:
        pa.terminate()
    
    return devices


def get_default_input_device() -> Optional[int]:
    """Récupère l'index du périphérique input par défaut."""
    if not HAS_PYAUDIO:
        return None
    
    try:
        pa = pyaudio.PyAudio()
        index = pa.get_default_input_device()  # type: ignore
        pa.terminate()
        return index
    except Exception as e:
        logger.error(f"Erreur récupération device par défaut: {e}")
        return None
