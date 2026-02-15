"""hardware_accel.py - Accélération matérielle (OpenVINO, GPU AMD, STT/TTS).

Exploite:
- Intel Core i9-11900KF
- GPU AMD Radeon RX 6750 XT
- OpenVINO pour Faster-Whisper (multi-threaded)
- Fish-Speech pour TTS haute fidélité
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

try:
    import faster_whisper  # type: ignore
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False
    logger.warning("⚠️ faster_whisper non disponible")

try:
    from openvino.runtime import Core  # type: ignore
    HAS_OPENVINO = True
except ImportError:
    HAS_OPENVINO = False
    logger.warning("⚠️ OpenVINO runtime non disponible")

try:
    import requests  # type: ignore
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class HardwareAccelerator:
    """Gestionnaire d'accélération matérielle pour STT/TTS."""

    def __init__(self):
        """Initialise l'accélérateur."""
        self.whisper_model = None
        self.openvino_core = None
        self.use_openvino = HAS_OPENVINO
        self.device = "cuda"  # Sera ajusté selon dispo
        
        # Configuration TTS
        self.tts_endpoint = os.getenv("FISH_SPEECH_ENDPOINT", "http://localhost:8000")
        
        logger.info("✅ HardwareAccelerator initialisé")

    async def initialize(self):
        """Initialisation asynchrone des ressources."""
        loop = asyncio.get_running_loop()
        
        # Charger Faster-Whisper avec OpenVINO si dispo
        if HAS_WHISPER:
            try:
                self.whisper_model = await loop.run_in_executor(
                    None,
                    self._setup_whisper
                )
                logger.info("✅ Faster-Whisper chargé")
            except Exception as e:
                logger.error(f"Erreur Whisper: {e}")
        
        # Initialiser OpenVINO
        if HAS_OPENVINO:
            try:
                self.openvino_core = Core()
                logger.info(f"✅ OpenVINO initialisé - Devices: {self.openvino_core.available_devices}")
            except Exception as e:
                logger.error(f"Erreur OpenVINO: {e}")

    def _setup_whisper(self):
        """Setup Faster-Whisper (exécuté dans executor)."""
        # Essayer de détecter le GPU
        device = "cuda"
        try:
            import torch  # type: ignore
            if not torch.cuda.is_available():
                device = "cpu"
                logger.info("ℹ️ GPU CUDA non disponible, utilisation CPU")
        except ImportError:
            device = "cpu"
        
        self.device = device
        
        # Charger modèle Faster-Whisper avec compute type adapté
        compute_type = "float16" if device == "cuda" else "float32"
        
        return faster_whisper.WhisperModel(
            "base",
            device=device,
            compute_type=compute_type,
            num_workers=8  # Multi-threading pour i9
        )

    async def transcribe_audio(self, audio_bytes: bytes, room: Optional[str] = None) -> str:
        """
        Transcrit l'audio en texte (Faster-Whisper + OpenVINO).
        
        Args:
            audio_bytes: Données audio raw
            room: Pièce source (optionnel)
        
        Returns:
            Texte transcrit
        """
        if not HAS_WHISPER or not self.whisper_model:
            logger.warning("Whisper non disponible")
            return ""
        
        try:
            loop = asyncio.get_running_loop()
            
            # Transcrire dans executor
            segments, info = await loop.run_in_executor(
                None,
                self._transcribe_sync,
                audio_bytes
            )
            
            text = " ".join([seg.text for seg in segments]).strip()
            if info:
                logger.info(f"📝 Transcription: '{text}' (confiance: {info.language_probability:.2f})")
            else:
                logger.info(f"📝 Transcription: '{text}'")
            
            return text
        
        except Exception as e:
            logger.error(f"Erreur transcription: {e}")
            return ""

    def _transcribe_sync(self, audio_bytes: bytes) -> tuple:
        """Transcrire en sync (executé dans thread pool).
        
        Attend des bytes PCM16 mono 16kHz (format AudioCapture).
        Convertit directement en float32 normalisé pour Whisper.
        """
        # Convertir PCM16 bytes → float32 normalisé [-1.0, 1.0]
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        samples = samples / 32768.0
        
        if len(samples) == 0:
            logger.warning("Audio vide, rien à transcrire")
            return [], None
        
        # Transcrire
        if not self.whisper_model:
            logger.error("Modèle Whisper non disponible")
            return [], None
        
        segments, info = self.whisper_model.transcribe(
            samples,
            language="fr",
            beam_size=5
        )
        
        # Matérialiser le générateur dans ce thread (sinon consommé hors contexte)
        segment_list = list(segments)
        
        return segment_list, info

    async def text_to_speech(self, text: str) -> Optional[bytes]:
        """
        Convertit le texte en parole (Fish-Speech TTS).
        
        Args:
            text: Texte à convertir
        
        Returns:
            Audio bytes (WAV)
        """
        if not HAS_REQUESTS:
            logger.warning("requests non disponible")
            return None
        
        try:
            loop = asyncio.get_running_loop()
            
            audio_data = await loop.run_in_executor(
                None,
                self._tts_sync,
                text
            )
            
            if audio_data:
                logger.info(f"🔊 TTS généré ({len(audio_data)} bytes)")
            return audio_data
        
        except Exception as e:
            logger.error(f"Erreur TTS: {e}")
            return None

    def _tts_sync(self, text: str) -> Optional[bytes]:
        """TTS en sync (executé dans thread pool)."""
        try:
            response = requests.post(
                f"{self.tts_endpoint}/v1/tts",
                json={
                    "text": text,
                    "language": "fr",
                    "speaker": "default",
                    "format": "wav"
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"TTS error {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"TTS request failed: {e}")
            return None

    async def control_music(self, func_name: str, args: Dict[str, Any]):
        """Contrôle Mopidy/TIDAL."""
        logger.info(f"🎵 Contrôle musique: {func_name} {args}")
        # TODO: Implémentation Mopidy WebSocket
        pass

    async def optimize_inference(self, model_path: str, device: str = "AUTO") -> Any:
        """Optimise un modèle avec OpenVINO pour déploiement."""
        if not HAS_OPENVINO or not self.openvino_core:
            logger.warning("OpenVINO non disponible")
            return None
        
        try:
            compiled_model = self.openvino_core.compile_model(
                model_path,
                device
            )
            logger.info(f"✅ Modèle compilé pour {device}")
            return compiled_model
        
        except Exception as e:
            logger.error(f"Erreur optimisation OpenVINO: {e}")
            return None

    async def benchmark_performance(self) -> Dict[str, Any]:
        """Benchmark des performances hardware."""
        results = {
            "cpu": os.cpu_count(),
            "device": self.device,
            "openvino_available": HAS_OPENVINO,
            "whisper_available": HAS_WHISPER,
        }
        
        # Benchmark Whisper
        if HAS_WHISPER and self.whisper_model:
            try:
                import time
                # Dummy audio de 1 seconde
                dummy_audio = np.zeros(16000, dtype=np.float32)
                
                start = time.time()
                # Exécuter une fois pour warm-up
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._transcribe_sync, dummy_audio.tobytes())
                elapsed = time.time() - start
                
                results["whisper_latency_ms"] = elapsed * 1000
            except Exception as e:
                logger.error(f"Erreur benchmark: {e}")
        
        logger.info(f"📊 Perf: {results}")
        return results

    async def close(self):
        """Ferme les ressources."""
        logger.info("🔌 HardwareAccelerator fermé")
