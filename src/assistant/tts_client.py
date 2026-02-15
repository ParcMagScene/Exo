import os
import asyncio
import logging
import wave
import io
import aiohttp
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Kokoro TTS (local, haute qualité) ──────────────────
try:
    from kokoro import KPipeline  # type: ignore
    HAS_KOKORO = True
except ImportError:
    HAS_KOKORO = False

# ─── Piper TTS (local, ultra-rapide) ────────────────────
try:
    from piper import PiperVoice  # type: ignore
    HAS_PIPER = True
except ImportError:
    HAS_PIPER = False


class TTSClient:
    """TTS Client - Pipeline vocal d'EXO.

    Priorité (configurable via TTS_ENGINE):
    1. **Kokoro TTS** (24kHz, qualité quasi-humaine, local, Apache 2.0)
    2. **Piper TTS local** (22kHz, <0.3s, offline, gratuit)
    3. OpenAI TTS-1 (voix "nova", via API, fallback réseau)
    4. Fish-Speech via HTTP (si configuré)
    5. Coqui French VITS (fallback offline lourd)

    Env vars:
    - TTS_ENGINE: Moteur préféré (kokoro|piper|openai|fish|coqui, default: kokoro)
    - KOKORO_VOICE: Voix Kokoro (default: ff_siwis, alternatives: ff_alma, fm_music)
    - KOKORO_LANG: Langue Kokoro (default: f = français)
    - KOKORO_ENABLED: Activer Kokoro (default: true)
    - PIPER_MODEL: Chemin vers le modèle .onnx Piper (default: models/piper/fr_FR-siwis-medium.onnx)
    - PIPER_ENABLED: Activer Piper (default: true)
    - OPENAI_API_KEY: Clé API OpenAI (pour TTS-1)
    - TTS_VOICE: Voix OpenAI (default: nova)
    - TTS_MODEL: Modèle OpenAI (default: tts-1)
    - TTS_SPEED: Vitesse parole (default: 1.0)
    - FISH_SPEECH_URL: Fish-Speech endpoint (optionnel)
    - TTS_FALLBACK: Enable Coqui fallback (default: true)
    - TTS_TIMEOUT: Timeout in seconds (default: 30)
    """

    def __init__(self, endpoint: str | None = None):
        # ── Moteur préféré ──
        self.preferred_engine = os.environ.get("TTS_ENGINE", "kokoro").lower()

        # ── Kokoro TTS config (local, haute qualité) ──
        self.kokoro_voice = os.environ.get("KOKORO_VOICE", "ff_siwis")
        self.kokoro_lang = os.environ.get("KOKORO_LANG", "f")  # 'f' = français
        self.kokoro_enabled = os.environ.get("KOKORO_ENABLED", "true").lower() in ("true", "1", "yes")
        self._kokoro_pipeline = None
        self._kokoro_loaded = False
        self._kokoro_sample_rate = 24000

        # ── Piper TTS config (local, ultra-rapide) ──
        self.piper_model_path = os.environ.get(
            "PIPER_MODEL", "models/piper/fr_FR-siwis-medium.onnx"
        )
        self.piper_enabled = os.environ.get("PIPER_ENABLED", "true").lower() in ("true", "1", "yes")
        self._piper_voice: Optional[PiperVoice] = None  # type: ignore
        self._piper_loaded = False
        self._piper_sample_rate = 22050  # sera mis à jour au chargement

        # ── OpenAI TTS config ──
        self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        self.tts_voice = os.environ.get("TTS_VOICE", "nova")
        self.tts_model = os.environ.get("TTS_MODEL", "tts-1")
        self.tts_speed = float(os.environ.get("TTS_SPEED", "1.0"))

        # ── Fish-Speech config ──
        self.fish_speech_url = endpoint or \
                               os.environ.get("FISH_SPEECH_URL") or \
                               os.environ.get("FISH_SPEECH_ENDPOINT")

        # ── Fallback config ──
        self.use_fallback = os.environ.get("TTS_FALLBACK", "true").lower() in ("true", "1", "yes")
        self.timeout = int(os.environ.get("TTS_TIMEOUT", "30"))

        self._coqui_cache = None
        self._coqui_loaded = False

        # Déterminer le moteur principal
        if HAS_KOKORO and self.kokoro_enabled:
            primary = "Kokoro TTS (local, haute qualité)"
        elif HAS_PIPER and self.piper_enabled and os.path.isfile(self.piper_model_path):
            primary = "Piper TTS (local, rapide)"
        elif self.openai_api_key:
            primary = "OpenAI TTS (API)"
        elif self.fish_speech_url:
            primary = "Fish-Speech"
        else:
            primary = "Coqui VITS"

        logger.info(f"TTSClient initialized - Primary: {primary}")

    # ─── Kokoro TTS (local, haute qualité) ──────────────────

    def _load_kokoro(self):
        """Charge le pipeline Kokoro (lazy, première utilisation)."""
        if self._kokoro_loaded:
            return self._kokoro_pipeline

        if not HAS_KOKORO:
            logger.warning("kokoro non installé (pip install kokoro soundfile)")
            return None

        try:
            logger.info(f"Chargement Kokoro TTS (lang={self.kokoro_lang}, voice={self.kokoro_voice})")
            self._kokoro_pipeline = KPipeline(lang_code=self.kokoro_lang)
            self._kokoro_loaded = True
            logger.info(f"✅ Kokoro TTS chargé (24kHz, voix={self.kokoro_voice})")
            return self._kokoro_pipeline
        except Exception as e:
            logger.error(f"Erreur chargement Kokoro : {e}")
            return None

    def _speak_kokoro_sync(self, text: str) -> Optional[bytes]:
        """Synthèse Kokoro synchrone (appelée dans un executor)."""
        pipeline = self._load_kokoro()
        if not pipeline:
            return None

        try:
            import soundfile as sf

            # Kokoro génère par segments, on les concatène
            audio_segments = []
            for _gs, _ps, audio in pipeline(
                text, voice=self.kokoro_voice, speed=1.0
            ):
                if audio is not None:
                    audio_segments.append(audio)

            if not audio_segments:
                logger.warning("Kokoro TTS : aucun segment audio généré")
                return None

            # Concaténer tous les segments
            full_audio = np.concatenate(audio_segments)

            # Convertir en WAV bytes
            buf = io.BytesIO()
            sf.write(buf, full_audio, self._kokoro_sample_rate, format='WAV')
            data = buf.getvalue()
            logger.info(
                f"Kokoro TTS : {len(data) // 1024}KB WAV "
                f"({self._kokoro_sample_rate}Hz, {len(full_audio)/self._kokoro_sample_rate:.1f}s)"
            )
            return data
        except Exception as e:
            logger.error(f"Erreur synthèse Kokoro : {e}")
            return None

    async def _speak_kokoro(self, text: str) -> Optional[bytes]:
        """Kokoro TTS local (async wrapper)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._speak_kokoro_sync, text)

    # ─── Piper TTS (local) ─────────────────────────────────

    def _load_piper(self):
        """Charge le modèle Piper (lazy, première utilisation)."""
        if self._piper_loaded:
            return self._piper_voice

        if not HAS_PIPER:
            logger.warning("piper-tts non installé")
            return None

        if not os.path.isfile(self.piper_model_path):
            logger.warning(f"Modèle Piper introuvable : {self.piper_model_path}")
            return None

        try:
            logger.info(f"Chargement Piper TTS : {self.piper_model_path}")
            self._piper_voice = PiperVoice.load(self.piper_model_path)
            self._piper_sample_rate = self._piper_voice.config.sample_rate
            self._piper_loaded = True
            logger.info(f"✅ Piper TTS chargé (sample_rate={self._piper_sample_rate})")
            return self._piper_voice
        except Exception as e:
            logger.error(f"Erreur chargement Piper : {e}")
            return None

    def preload(self):
        """Pré-charge le modèle TTS au démarrage."""
        if HAS_KOKORO and self.kokoro_enabled:
            self._load_kokoro()
        if HAS_PIPER and self.piper_enabled:
            self._load_piper()

    def _speak_piper_sync(self, text: str) -> Optional[bytes]:
        """Synthèse Piper synchrone (appelée dans un executor)."""
        voice = self._load_piper()
        if not voice:
            return None

        try:
            buf = io.BytesIO()
            wf = wave.open(buf, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self._piper_sample_rate)

            for chunk in voice.synthesize(text):
                wf.writeframes(chunk.audio_int16_bytes)

            wf.close()
            data = buf.getvalue()
            logger.info(f"Piper TTS : {len(data) // 1024}KB WAV ({self._piper_sample_rate}Hz)")
            return data
        except Exception as e:
            logger.error(f"Erreur synthèse Piper : {e}")
            return None

    async def _speak_piper(self, text: str) -> Optional[bytes]:
        """Piper TTS local (async wrapper)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._speak_piper_sync, text)

    # ─── OpenAI TTS (API) ──────────────────────────────────

    async def _speak_openai(self, text: str) -> Optional[bytes]:
        """OpenAI TTS-1 via API (fallback réseau)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.tts_model,
                        "input": text,
                        "voice": self.tts_voice,
                        "response_format": "wav",
                        "speed": self.tts_speed
                    },
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as resp:
                    if resp.status >= 400:
                        error_text = await resp.text()
                        logger.warning(f"OpenAI TTS erreur {resp.status}: {error_text[:200]}")
                        return None
                    audio = await resp.read()
                    logger.info(f"OpenAI TTS : {len(audio) // 1024}KB, voice={self.tts_voice}")
                    return audio
        except asyncio.TimeoutError:
            logger.warning(f"OpenAI TTS timeout ({self.timeout}s)")
            return None
        except Exception as e:
            logger.warning(f"OpenAI TTS erreur : {e}")
            return None

    # ─── Fish-Speech ───────────────────────────────────────

    async def _speak_fish_speech(self, text: str) -> Optional[bytes]:
        """Fish-Speech via HTTP."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.fish_speech_url,
                    json={"text": text},
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as resp:
                    if resp.status >= 400:
                        logger.warning(f"Fish-Speech erreur {resp.status}")
                        return None
                    return await resp.read()
        except Exception as e:
            logger.warning(f"Fish-Speech erreur : {e}")
            return None

    # ─── Coqui VITS (fallback lourd) ──────────────────────

    async def _speak_coqui(self, text: str) -> Optional[bytes]:
        """Coqui French VITS (fallback offline lourd)."""
        try:
            if not self._coqui_loaded:
                from TTS.api import TTS  # type: ignore
                logger.info("Chargement Coqui French VITS...")
                self._coqui_cache = TTS("tts_models/fr/css10/vits")
                self._coqui_loaded = True

            if not self._coqui_cache:
                return None

            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self._coqui_cache.tts_to_file, text, tmp_path
            )

            with open(tmp_path, 'rb') as f:
                audio_bytes = f.read()
            os.unlink(tmp_path)
            return audio_bytes
        except Exception as e:
            logger.error(f"Coqui VITS erreur : {e}")
            return None

    # ─── API publique ──────────────────────────────────────

    @property
    def sample_rate(self) -> int:
        """Sample rate du moteur TTS actif."""
        if HAS_KOKORO and self.kokoro_enabled:
            return self._kokoro_sample_rate
        if HAS_PIPER and self.piper_enabled:
            return self._piper_sample_rate
        return 24000  # OpenAI TTS / Fish-Speech

    async def speak(self, text: str) -> bytes:
        """Synthétise du texte en audio WAV.

        Priorité (par défaut) :
        1. Kokoro TTS (qualité quasi-humaine, local, 24kHz)
        2. Piper TTS local (<0.3s, offline)
        3. OpenAI TTS-1 (~1-2s, API)
        4. Fish-Speech (si configuré)
        5. Coqui VITS (fallback)
        """
        # 1. Kokoro TTS (local, haute qualité)
        if HAS_KOKORO and self.kokoro_enabled:
            audio = await self._speak_kokoro(text)
            if audio:
                logger.info("✓ Kokoro TTS OK (local, haute qualité)")
                return audio
            logger.warning("Kokoro TTS échoué, fallback Piper...")

        # 2. Piper TTS (local, ultra-rapide)
        if HAS_PIPER and self.piper_enabled:
            audio = await self._speak_piper(text)
            if audio:
                logger.info("✓ Piper TTS OK (local)")
                return audio
            logger.warning("Piper TTS échoué, fallback OpenAI...")

        # 3. OpenAI TTS (API)
        if self.openai_api_key:
            audio = await self._speak_openai(text)
            if audio:
                logger.info("✓ OpenAI TTS OK")
                return audio
            logger.warning("OpenAI TTS échoué, fallback suivant...")

        # 4. Fish-Speech
        if self.fish_speech_url:
            audio = await self._speak_fish_speech(text)
            if audio:
                logger.info("✓ Fish-Speech OK")
                return audio

        # 5. Coqui VITS
        if self.use_fallback:
            audio = await self._speak_coqui(text)
            if audio:
                logger.info("✓ Coqui VITS OK")
                return audio

        raise RuntimeError(
            "TTS indisponible : Kokoro, Piper, OpenAI, Fish-Speech et Coqui ont tous échoué."
        )
