"""Module audio: capture, traitement et streaming en temps réel.

Classes principales:
- AudioCapture: Capture microphone PCM16 @ 16kHz (asyncio)
- AudioFrame: Structure pour les frames audio capturées
- AudioStats: Analyse statistiques de l'audio
- AudioDevice: Wrapper périphérique audio

Fonctions utiles:
- list_audio_devices(): Liste tous les périphériques
- get_default_input_device(): Récupère le device par défaut
"""

from .audio_capture import (
    AudioCapture,
    AudioFrame,
    AudioStats,
    AudioDevice,
    list_audio_devices,
    get_default_input_device,
    HAS_PYAUDIO
)

__all__ = [
    "AudioCapture",
    "AudioFrame",
    "AudioStats",
    "AudioDevice",
    "list_audio_devices",
    "get_default_input_device",
    "HAS_PYAUDIO"
]
