"""wake_word.py - Détection du mot d'activation "EXO" + VAD.

Écoute continue du microphone avec détection d'activité vocale (VAD).
Quand une utterance est captée, elle est transcrite et analysée pour le wake word.

Fonctionnalités:
- VAD (Voice Activity Detection) par RMS energy
- Capture d'utterance complète (voix → silence = fin)
- Détection du mot "EXO" dans la transcription Whisper
- Extraction de la commande après le wake word
"""

import asyncio
import logging
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)

# ─── Wake word variants ──────────────────────────────────
# Whisper peut transcrire "Exo" de plusieurs façons selon l'accent
WAKE_WORDS = [
    "exo", "écho", "echo", "expo", "ego", "exc", "exot",
    "x.o", "x o", "exau", "exeau", "exos", "exho",
]

# ─── VAD Configuration ───────────────────────────────────
DEFAULT_VOICE_THRESHOLD = 500       # RMS seuil pour "voix active" (relevé pour filtrer bruit)
DEFAULT_SILENCE_CHUNKS = 12        # ~0.8s de silence = fin d'utterance (réactif)
DEFAULT_MIN_UTTERANCE_SEC = 0.8    # Ignorer bruits < 0.8s
DEFAULT_MAX_UTTERANCE_SEC = 15.0   # Sécurité max
DEFAULT_MIN_VOICE_CHUNKS = 8       # Au moins 8 chunks vocaux pour valider

# ─── Hallucinations Whisper connues (filtrées) ───────────
WHISPER_HALLUCINATIONS = [
    "sous-titres", "sous-titre", "amara.org", "amara",
    "merci d'avoir regardé", "merci de votre attention",
    "traduisez", "subscribe", "abonnez",
    "...", "…", "♪", "🎵",
]


def rms_energy(audio_bytes: bytes) -> float:
    """Calcule l'énergie RMS d'un buffer audio PCM16."""
    samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    if len(samples) == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples ** 2)))


def is_hallucination(text: str) -> bool:
    """Détecte les hallucinations connues de Whisper sur le silence."""
    text_lower = text.lower().strip()
    # Texte trop court ou que des points/espaces
    clean = text_lower.replace(".", "").replace(" ", "").replace("…", "")
    if len(clean) < 3:
        return True
    for h in WHISPER_HALLUCINATIONS:
        if h in text_lower:
            return True
    return False


def contains_wake_word(text: str) -> bool:
    """Vérifie si le texte contient le mot d'activation 'EXO'."""
    if is_hallucination(text):
        return False
    text_lower = text.lower().strip()
    for w in WAKE_WORDS:
        if w in text_lower:
            return True
    return False


def extract_command_after_wake(text: str) -> str:
    """Extrait la commande après le mot d'activation.

    Exemples:
        "Exo, quelle heure est-il ?" → "quelle heure est-il ?"
        "Exo allume la lumière"       → "allume la lumière"
        "Exo"                         → ""
    """
    text_clean = text.strip()
    text_lower = text_clean.lower()

    best_idx = -1
    best_len = 0
    for w in WAKE_WORDS:
        idx = text_lower.find(w)
        if idx >= 0 and (best_idx < 0 or len(w) > best_len):
            best_idx = idx
            best_len = len(w)

    if best_idx < 0:
        return text_clean

    after = text_clean[best_idx + best_len:]
    # Nettoyer ponctuation/espaces résiduels au début
    after = after.lstrip(" ,.:;!?·\t\n")
    return after


async def capture_utterance(
    stream,
    sample_rate: int = 16000,
    chunk_size: int = 1024,
    voice_threshold: float = DEFAULT_VOICE_THRESHOLD,
    silence_chunks_end: int = DEFAULT_SILENCE_CHUNKS,
    min_sec: float = DEFAULT_MIN_UTTERANCE_SEC,
    max_sec: float = DEFAULT_MAX_UTTERANCE_SEC,
    timeout_sec: Optional[float] = None,
) -> bytes:
    """Capture une utterance complète : attend la voix, accumule jusqu'au silence.

    Args:
        stream: PyAudio stream ouvert en input
        sample_rate: Fréquence d'échantillonnage
        chunk_size: Taille de chaque chunk lu
        voice_threshold: Seuil RMS pour détecter la voix
        silence_chunks_end: Nombre de chunks silencieux consécutifs = fin d'utterance
        min_sec: Durée minimum d'une utterance valide
        max_sec: Durée maximum (sécurité)
        timeout_sec: Abandon si aucune voix après ce délai (None = infini)

    Returns:
        Audio bytes PCM16 de l'utterance, ou b"" si timeout/trop court
    """
    buffer = b""
    silent_count = 0
    voice_detected = False
    voice_chunks = 0       # Nombre de chunks avec de la voix réelle
    total_chunks = 0
    max_chunks = int(max_sec * sample_rate / chunk_size)
    timeout_chunks = int(timeout_sec * sample_rate / chunk_size) if timeout_sec else None
    wait_chunks = 0
    min_voice = DEFAULT_MIN_VOICE_CHUNKS

    while total_chunks < max_chunks:
        try:
            data = stream.read(chunk_size, exception_on_overflow=False)
        except Exception:
            await asyncio.sleep(0.01)
            continue

        energy = rms_energy(data)

        if not voice_detected:
            if energy > voice_threshold:
                voice_detected = True
                buffer = data
                silent_count = 0
                voice_chunks = 1
                total_chunks = 1
            else:
                wait_chunks += 1
                if timeout_chunks and wait_chunks >= timeout_chunks:
                    return b""  # Timeout, personne n'a parlé
                await asyncio.sleep(0.001)
                continue
        else:
            buffer += data
            total_chunks += 1

            if energy < voice_threshold:
                silent_count += 1
                if silent_count >= silence_chunks_end:
                    break
            else:
                silent_count = 0
                voice_chunks += 1

        await asyncio.sleep(0.001)

    # Vérifier durée minimum
    duration = len(buffer) / (sample_rate * 2)  # PCM16 = 2 bytes/sample
    if duration < min_sec:
        return b""

    # Vérifier qu'il y avait assez de voix réelle (pas juste un pic de bruit)
    if voice_chunks < min_voice:
        return b""

    return buffer
