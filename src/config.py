"""config.py - Centralisé de la configuration.

Charge depuis:
1. Variables d'environnement (.env)
2. Fichiers config (JSON/YAML)
3. Valeurs par défaut
"""

import os
import json
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv

# Charger .env
load_dotenv()


class Config:
    """Configuration centralisée de l'assistant."""

    # ==================== AZURE OPENAI ====================
    AZURE_OPENAI_ENDPOINT: str = os.getenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://your-resource.openai.azure.com/"
    )
    AZURE_OPENAI_KEY: str = os.getenv("AZURE_OPENAI_KEY", "")
    AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    AZURE_OPENAI_MODEL: str = os.getenv("AZURE_OPENAI_MODEL", "gpt-4o")
    AZURE_OPENAI_API_VERSION: str = os.getenv(
        "AZURE_OPENAI_API_VERSION",
        "2024-02-15-preview"
    )

    # ==================== HOME ASSISTANT ====================
    HA_URL: str = os.getenv("HA_URL", "http://homeassistant.local:8123")
    HA_TOKEN: str = os.getenv("HA_TOKEN", "")

    # ==================== HARDWARE ====================
    DEVICE: str = os.getenv("DEVICE", "auto")
    WHISPER_WORKERS: int = int(os.getenv("WHISPER_WORKERS", "8"))
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")

    # ==================== TTS ====================
    TTS_ENGINE: str = os.getenv("TTS_ENGINE", "kokoro")  # kokoro|piper|openai|fish|coqui
    KOKORO_VOICE: str = os.getenv("KOKORO_VOICE", "ff_siwis")  # ff_siwis, ff_alma, fm_music
    KOKORO_LANG: str = os.getenv("KOKORO_LANG", "f")  # f=français, e=english, j=japanese
    KOKORO_ENABLED: bool = os.getenv("KOKORO_ENABLED", "true").lower() == "true"
    FISH_SPEECH_ENDPOINT: str = os.getenv("FISH_SPEECH_ENDPOINT", "http://localhost:8000")

    # ==================== MOPIDY ====================
    MOPIDY_URL: str = os.getenv("MOPIDY_URL", "http://localhost:6680")
    TIDAL_QUALITY: str = os.getenv("TIDAL_QUALITY", "LOSSLESS")

    # ==================== GUI ====================
    GUI_WIDTH: int = int(os.getenv("GUI_WIDTH", "800"))
    GUI_HEIGHT: int = int(os.getenv("GUI_HEIGHT", "600"))
    GUI_FPS: int = int(os.getenv("GUI_FPS", "144"))
    ENABLE_PYGAME: bool = os.getenv("ENABLE_PYGAME", "true").lower() == "true"

    # ==================== WYOMING ====================
    WYOMING_HOST: str = os.getenv("WYOMING_HOST", "0.0.0.0")
    WYOMING_PORT: int = int(os.getenv("WYOMING_PORT", "10700"))

    # ==================== LOGGING ====================
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ==================== DÉVELOPPEMENT ====================
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    MOCK_HA: bool = os.getenv("MOCK_HA", "false").lower() == "true"

    # ==================== CHROME DB ====================
    CHROMADB_PATH: str = "./data/chroma"

    # ==================== CONSTANTES ====================
    TARGET_LATENCY_MS: int = 500
    LLM_TEMPERATURE: float = 0.6  # Balance créativité/cohérence pour conversations
    LLM_MAX_TOKENS: int = 2000   # Réponses long-form plus détaillées
    CONVERSATION_HISTORY_SIZE: int = 50  # Contexte étendu pour vraies conversations
    RAG_TOP_K: int = 5  # Plus de contexte personnalisé

    # Mapping pièces (immutable, utiliser load_custom_rooms pour modifier)
    _DEFAULT_ROOMS: Dict[str, str] = {
        "salon": "light.salon_hue",
        "chambre": "light.chambre_hue",
        "cuisine": "light.cuisine_ikea",
        "salle_bain": "light.salle_bain_hue",
    }
    ROOMS_MAP: Dict[str, str] = dict(_DEFAULT_ROOMS)

    @classmethod
    def validate(cls) -> bool:
        """Valide la configuration requise."""
        # Au moins une API OpenAI doit être configurée
        has_openai = bool(os.getenv("OPENAI_API_KEY"))
        has_azure = bool(cls.AZURE_OPENAI_KEY and cls.AZURE_OPENAI_KEY != "")
        
        if not has_openai and not has_azure:
            print("⚠️ Aucune clé API configurée (OPENAI_API_KEY ou AZURE_OPENAI_KEY)")
            print("Copier .env.example en .env et remplir les valeurs")
            return False

        return True

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Exporte la configuration en dictionnaire."""
        return {
            k: v for k, v in cls.__dict__.items()
            if not k.startswith("_") and not callable(v)
        }

    @classmethod
    def load_custom_rooms(cls, filepath: str) -> None:
        """Charge un mapping personnalisé de pièces."""
        try:
            with open(filepath, "r") as f:
                cls.ROOMS_MAP.update(json.load(f))
        except Exception as e:
            print(f"Erreur chargement pièces: {e}")


# Valider au démarrage (optionnel)
_suppress_warnings = os.getenv("SUPPRESS_CONFIG_WARNINGS", "0") == "1"
if __name__ != "__main__" and not _suppress_warnings:
    if not Config.validate():
        pass  # Continuer sans erreur critique
