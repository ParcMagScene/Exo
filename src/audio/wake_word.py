"""wake_word.py - Détection du mot d'activation "EXO" + VAD.

Écoute continue du microphone avec détection d'activité vocale (VAD).
Quand une utterance est captée, elle est transcrite et analysée pour le wake word.

Fonctionnalités:
- VAD (Voice Activity Detection) par RMS energy avec seuil adaptatif
- Capture d'utterance complète (voix → silence = fin)
- Détection du mot "EXO" dans la transcription Whisper
- Extraction de la commande après le wake word
"""

import asyncio
import logging
import os
import re
import time
from collections import deque
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)

# ─── Wake word variants ──────────────────────────────────
# Whisper peut transcrire "Exo" de plusieurs façons selon l'accent
WAKE_WORDS = [
    "exo", "écho", "echo", "expo", "ego", "exc", "exot",
    "x.o", "x o", "exau", "exeau", "exos", "exho",
    # Variantes supplémentaires observées avec Whisper FR
    "exeau", "esso", "ekso", "ex-o", "axo", "hecho",
    "ex o", "ex-eau", " exo", "exo ", "ecso",
    # Variantes observées dans les logs réels (Whisper base, FR)
    "et que", "èque", "ek-o", "l'exo", "l'écho",
    "exa", "eko", "exau", "equo",
]

# ─── VAD Configuration ───────────────────────────────────
# Seuils abaissés pour capter les voix douces et commandes courtes
DEFAULT_VOICE_THRESHOLD = 300       # RMS seuil pour "voix active" (abaissé de 500)
DEFAULT_SILENCE_CHUNKS = 5         # ~0.32s de silence consécutif = fin rapide
DEFAULT_MIN_UTTERANCE_SEC = 0.5    # Ignorer bruits < 0.5s (abaissé pour commandes courtes)
DEFAULT_MAX_UTTERANCE_SEC = 10.0   # Sécurité max
DEFAULT_MIN_VOICE_CHUNKS = 5       # Au moins 5 chunks vocaux (~0.32s de voix réelle)

# ─── Seuil adaptatif ─────────────────────────────────────
ADAPTIVE_MULTIPLIER = float(os.environ.get("EXO_VAD_MULTIPLIER", "3.0"))
NOISE_FLOOR_SAMPLES = 30           # Nb chunks pour calibrer le bruit ambiant
SILENCE_WINDOW_SIZE = 15           # ~1.0s fenêtre glissante pour fin de parole (réduit de 25)
SILENCE_END_RATIO = 0.20           # < 20% voix dans la fenêtre → parole terminée (réduit de 0.25)

# ─── Hallucinations Whisper connues (filtrées) ───────────
WHISPER_HALLUCINATIONS = [
    # Patterns classiques de hallucination Whisper FR
    "sous-titres", "sous-titrage", "sous-titré",
    "amara.org",
    "merci d'avoir regardé", "merci de votre attention",
    "traduisez", "subscribe", "abonnez",
    "...", "…", "♪", "🎵",
    "fin de la vidéo", "fin de votre vidéo",
    "contributions de",
    "[musique]", "[applaudissements]", "[rires]",
    # Patterns observés dans les logs réels
    "je vous invite",
    "visage de sauvage", "visage de la vise",
    "caractéristiques",
    "je vous remercie",
    "l'économie de la",
    "il y a un visage",
    "la fin de votre",
    "je suis venu",
    "c'est le cas de",
    "il est au courant",
    "alors qu'on va",
    "s'il vous plaît",
    "faire une autre vidéo",
    "c'est pas le truc",
    "l'écran",
    "l'exil",
    "à protection",
    "au-delà",
    "c'est la vie",
    "c'est une bonne",
    "si la vie",
]


def rms_energy(audio_bytes: bytes) -> float:
    """Calcule l'énergie RMS d'un buffer audio PCM16."""
    samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    if len(samples) == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples ** 2)))


def is_hallucination(text: str, audio_duration_sec: float = 0.0) -> bool:
    """Détecte les hallucinations connues de Whisper sur le silence.

    Args:
        text: Texte transcrit par Whisper
        audio_duration_sec: Durée de l'audio source (0 = pas de vérif ratio)
    """
    text_lower = text.lower().strip()
    # Texte trop court ou que de la ponctuation/espaces
    clean = re.sub(r'[^\w]', '', text_lower)  # Ne garder que lettres/chiffres
    if len(clean) < 3:
        return True
    # Phrases connues de hallucination
    for h in WHISPER_HALLUCINATIONS:
        if h in text_lower:
            return True
    # Heuristique ratio : si trop de mots par seconde d'audio → hallucination
    # Parole normale FR ≈ 2-4 mots/sec. Whisper qui hallucine produit 6+ mots/sec
    # Seulement fiable pour audio > 1.0s (ratio peu fiable sur clips très courts)
    if audio_duration_sec > 1.0:
        word_count = len(text_lower.split())
        words_per_sec = word_count / audio_duration_sec
        if words_per_sec > 6.0:
            logger.debug("Hallucination ratio: %.1f mots/s pour %.1fs audio: %s",
                         words_per_sec, audio_duration_sec, text[:60])
            return True
    # Texte avec beaucoup de répétitions → hallucination
    words = text_lower.split()
    if len(words) >= 6:
        unique = set(words)
        if len(unique) / len(words) < 0.5:  # < 50% mots uniques
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


# ─── Noise floor adaptatif (partagé entre appels) ────────
_noise_floor: float = 0.0
_noise_calibrated: bool = False


def calibrate_noise_floor(stream, chunk_size: int = 1024, num_samples: int = NOISE_FLOOR_SAMPLES) -> float:
    """Mesure le bruit ambiant sur N chunks pour calibrer le seuil VAD.

    Appelé au démarrage et périodiquement pour s'adapter à l'environnement.
    """
    global _noise_floor, _noise_calibrated
    energies = []
    for _ in range(num_samples):
        try:
            data = stream.read(chunk_size, exception_on_overflow=False)
            energies.append(rms_energy(data))
        except Exception:
            continue
    if energies:
        _noise_floor = float(np.median(energies))
        _noise_calibrated = True
        logger.info("🎤 Bruit ambiant calibré : %.0f RMS (seuil adaptatif : %.0f)",
                     _noise_floor, _noise_floor * ADAPTIVE_MULTIPLIER)
    return _noise_floor


def get_adaptive_threshold(fixed_threshold: float) -> float:
    """Retourne le seuil VAD adaptatif (max entre fixe et adaptatif)."""
    if _noise_calibrated and _noise_floor > 0:
        adaptive = _noise_floor * ADAPTIVE_MULTIPLIER
        # Prendre le max pour éviter les faux positifs, mais plafonner
        # pour ne pas devenir sourd dans un environnement bruyant
        return max(min(adaptive, fixed_threshold * 2.5), fixed_threshold * 0.5)
    return fixed_threshold


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

    Utilise un seuil adaptatif basé sur le bruit ambiant calibré au démarrage.

    Args:
        stream: PyAudio stream ouvert en input
        sample_rate: Fréquence d'échantillonnage
        chunk_size: Taille de chaque chunk lu
        voice_threshold: Seuil RMS fixe pour détecter la voix (ajusté par adaptif)
        silence_chunks_end: Nombre de chunks silencieux consécutifs = fin d'utterance
        min_sec: Durée minimum d'une utterance valide
        max_sec: Durée maximum (sécurité)
        timeout_sec: Abandon si aucune voix après ce délai (None = infini)

    Returns:
        Audio bytes PCM16 de l'utterance, ou b"" si timeout/trop court
    """
    # Calibration initiale du bruit ambiant (une seule fois)
    global _noise_calibrated
    if not _noise_calibrated:
        calibrate_noise_floor(stream, chunk_size)

    # Seuil adaptatif
    effective_threshold = get_adaptive_threshold(voice_threshold)

    buffer = b""
    silent_count = 0
    voice_detected = False
    voice_chunks = 0       # Nombre de chunks avec de la voix réelle
    total_chunks = 0
    max_chunks = int(max_sec * sample_rate / chunk_size)
    timeout_chunks = int(timeout_sec * sample_rate / chunk_size) if timeout_sec else None
    wait_chunks = 0
    min_voice = DEFAULT_MIN_VOICE_CHUNKS
    recent_voice = deque(maxlen=SILENCE_WINDOW_SIZE)  # Fenêtre glissante

    while total_chunks < max_chunks:
        try:
            data = stream.read(chunk_size, exception_on_overflow=False)
        except Exception:
            await asyncio.sleep(0.01)
            continue

        energy = rms_energy(data)

        if not voice_detected:
            if energy > effective_threshold:
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
            is_voice_chunk = energy >= effective_threshold
            recent_voice.append(is_voice_chunk)

            if not is_voice_chunk:
                silent_count += 1
                if silent_count >= silence_chunks_end:
                    break
            else:
                silent_count = 0
                voice_chunks += 1

            # Fin de parole robuste : fenêtre glissante
            # Résiste aux pics de bruit sporadiques qui reset le compteur consécutif
            if (voice_chunks >= min_voice
                    and len(recent_voice) >= SILENCE_WINDOW_SIZE):
                voice_ratio = sum(recent_voice) / len(recent_voice)
                if voice_ratio < SILENCE_END_RATIO:
                    break

        await asyncio.sleep(0.001)

    # Vérifier durée minimum
    duration = len(buffer) / (sample_rate * 2)  # PCM16 = 2 bytes/sample
    if duration < min_sec:
        return b""

    # Vérifier qu'il y avait assez de voix réelle (pas juste un pic de bruit)
    if voice_chunks < min_voice:
        return b""

    return buffer
