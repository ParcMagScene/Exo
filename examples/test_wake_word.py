"""test_wake_word.py — Test complet : écoute continue avec mot d'activation "Exo".

Pipeline:
  1. Écoute micro en continu (Brio 500, device_index=1)
  2. VAD : accumule toute l'utterance (voix → silence = fin de phrase)
  3. Transcrit L'UTTERANCE COMPLÈTE avec Whisper
  4. Si "Exo" détecté → extrait la commande après le wake word
  5. Si commande vide (juste "Exo") → capture une 2e utterance
  6. Commande → BrainEngine (GPT-4o) → TTSClient (OpenAI nova) → playback
"""

import sys
import os
import asyncio
import logging
import time
import io
import numpy as np

# Path setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("wake_word")

# ─── Configuration ────────────────────────────────────────
DEVICE_INDEX = 1            # Brio 500 webcam mic
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
CHANNELS = 1

# VAD (Voice Activity Detection)
VOICE_THRESHOLD = 250       # RMS seuil pour "voix active"
SILENCE_CHUNKS_END = 20     # ~1.3s de silence consécutif = fin d'utterance
                            # (20 * 1024 / 16000 ≈ 1.28s)
MIN_UTTERANCE_SEC = 0.8     # Ignorer les bruits < 0.8s
MAX_UTTERANCE_SEC = 20.0    # Sécurité max

# Après wake word sans commande : attente 2e utterance
FOLLOWUP_TIMEOUT_SEC = 5.0  # Max attente après "Exo" seul

# Wake word variants (Whisper peut transcrire "Exo" de plusieurs façons)
WAKE_WORDS = ["exo", "écho", "echo", "expo", "ego", "exc", "exot",
              "x.o", "x o", "exau", "exeau"]


def rms_energy(audio_bytes: bytes) -> float:
    """Calcule l'énergie RMS d'un buffer audio PCM16."""
    samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    if len(samples) == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples ** 2)))


def contains_wake_word(text: str) -> bool:
    """Vérifie si le texte contient le mot d'activation."""
    text_lower = text.lower().strip()
    for w in WAKE_WORDS:
        if w in text_lower:
            return True
    return False


def extract_command_after_wake(text: str) -> str:
    """Extrait la commande après le mot d'activation.
    
    Gère les cas : "Exo, quelle heure est-il ?"
                   "Exo quelle heure est-il"
                   "Exot. Quelle heure est-il ?"
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


async def capture_utterance(stream, min_sec=MIN_UTTERANCE_SEC, max_sec=MAX_UTTERANCE_SEC,
                             timeout_sec=None) -> bytes:
    """Capture une utterance complète : attend la voix, puis accumule jusqu'au silence.
    
    Args:
        stream: PyAudio stream
        min_sec: Durée minimum pour considérer l'utterance valide
        max_sec: Durée maximum de sécurité
        timeout_sec: Si set, abandon si aucune voix dans ce délai
    
    Returns:
        Audio bytes PCM16 de l'utterance, ou b"" si timeout
    """
    buffer = b""
    silent_count = 0
    voice_detected = False
    total_chunks = 0
    max_chunks = int(max_sec * SAMPLE_RATE / CHUNK_SIZE)
    timeout_chunks = int(timeout_sec * SAMPLE_RATE / CHUNK_SIZE) if timeout_sec else None
    wait_chunks = 0
    
    while total_chunks < max_chunks:
        try:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
        except Exception:
            await asyncio.sleep(0.01)
            continue
        
        energy = rms_energy(data)
        
        if not voice_detected:
            # Attendre début de voix
            if energy > VOICE_THRESHOLD:
                voice_detected = True
                buffer = data
                silent_count = 0
                total_chunks = 1
            else:
                wait_chunks += 1
                if timeout_chunks and wait_chunks >= timeout_chunks:
                    return b""  # Timeout, personne n'a parlé
                await asyncio.sleep(0.001)
                continue
        else:
            # Voix en cours — accumuler
            buffer += data
            total_chunks += 1
            
            if energy < VOICE_THRESHOLD:
                silent_count += 1
                if silent_count >= SILENCE_CHUNKS_END:
                    # Fin d'utterance
                    break
            else:
                silent_count = 0
        
        await asyncio.sleep(0.001)
    
    # Vérifier durée minimum
    duration = len(buffer) / (SAMPLE_RATE * 2)
    if duration < min_sec:
        return b""  # Trop court, bruit
    
    return buffer


async def main():
    import pyaudio  # type: ignore
    import pygame  # type: ignore

    # ─── Init composants ──────────────────────────────────
    logger.info("=" * 60)
    logger.info("  EXO — Wake Word Listener v2")
    logger.info("  Dites 'Exo' suivi de votre commande")
    logger.info("  Ex: 'Exo, quelle heure est-il ?'")
    logger.info("=" * 60)

    # Faster-Whisper — modèle "small" pour meilleure précision en français
    logger.info("Chargement Faster-Whisper (small)...")
    from faster_whisper import WhisperModel  # type: ignore
    whisper = WhisperModel("small", device="cpu", compute_type="float32")
    logger.info("Whisper OK (modele: small)")

    # BrainEngine
    logger.info("Initialisation BrainEngine...")
    from src.brain.brain_engine import BrainEngine
    brain = BrainEngine()
    await brain.initialize()
    logger.info("Brain OK")

    # TTSClient
    logger.info("Initialisation TTSClient...")
    from src.assistant.tts_client import TTSClient
    tts = TTSClient()
    logger.info("TTS OK")

    # Pygame mixer pour playback
    pygame.mixer.init(frequency=24000, size=-16, channels=1)
    logger.info("Pygame mixer OK")

    # PyAudio
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        input_device_index=DEVICE_INDEX,
        frames_per_buffer=CHUNK_SIZE
    )
    logger.info(f"Micro ouvert (device {DEVICE_INDEX}, {SAMPLE_RATE}Hz)")

    loop = asyncio.get_event_loop()

    def transcribe_buffer(audio_bytes: bytes) -> str:
        """Transcrit un buffer audio PCM16 avec Whisper."""
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if len(samples) < 4800:  # Moins de 0.3s → trop court
            return ""
        segments, _ = whisper.transcribe(samples, language="fr", beam_size=5)
        return " ".join(seg.text for seg in segments).strip()

    def play_audio_bytes(audio_data: bytes):
        """Joue des bytes WAV via pygame."""
        try:
            sound = pygame.mixer.Sound(io.BytesIO(audio_data))
            sound.play()
            while pygame.mixer.get_busy():
                pygame.time.wait(50)
        except Exception as e:
            logger.error(f"Erreur playback: {e}")

    async def process_command(command_text: str):
        """Traite une commande : Brain → TTS → Playback."""
        logger.info(f"COMMANDE: '{command_text}'")

        # Brain (GPT-4o)
        logger.info("Reflexion EXO...")
        t0 = time.time()
        result = await brain.process_command(
            text=command_text,
            room="local",
            context={"source": "wake_word"}
        )
        brain_time = time.time() - t0
        response_text = result.get("text", "")
        logger.info(f"Reponse ({brain_time:.1f}s): {response_text[:150]}")

        # TTS + Playback
        if response_text:
            logger.info("Synthese vocale...")
            t0 = time.time()
            audio = await tts.speak(response_text)
            tts_time = time.time() - t0
            logger.info(f"TTS OK ({tts_time:.1f}s, {len(audio)//1024}KB)")
            play_audio_bytes(audio)
            logger.info("Playback termine")

    # ─── Boucle principale ────────────────────────────────
    logger.info("")
    logger.info("En ecoute... Dites 'Exo' pour activer.")
    logger.info("Ctrl+C pour quitter.")
    logger.info("-" * 50)

    try:
        while True:
            # ─── Étape 1: Capturer une utterance complète ─
            utterance_bytes = await capture_utterance(stream)
            
            if not utterance_bytes:
                continue  # Bruit trop court, on ignore
            
            duration = len(utterance_bytes) / (SAMPLE_RATE * 2)
            
            # ─── Étape 2: Transcrire l'utterance entière ──
            logger.info(f"Transcription utterance ({duration:.1f}s)...")
            transcript = await loop.run_in_executor(None, transcribe_buffer, utterance_bytes)
            
            if not transcript:
                continue
            
            logger.info(f"Entendu: '{transcript}'")
            
            # ─── Étape 3: Chercher le wake word ───────────
            if not contains_wake_word(transcript):
                # Pas de wake word, on ignore
                continue
            
            logger.info("=" * 50)
            logger.info(" WAKE WORD 'EXO' DETECTE!")
            logger.info("=" * 50)
            
            # ─── Étape 4: Extraire la commande ────────────
            command = extract_command_after_wake(transcript)
            
            if len(command.split()) >= 2:
                # Commande déjà dans l'utterance ("Exo, quelle heure est-il ?")
                logger.info(f"Commande dans l'utterance: '{command}'")
                await process_command(command)
            else:
                # Juste "Exo" tout seul → attendre 2e utterance
                if command:
                    logger.info(f"Fragment: '{command}' — trop court, attente suite...")
                else:
                    logger.info("Juste 'Exo' — attente commande...")
                logger.info(f"Parlez maintenant (timeout {FOLLOWUP_TIMEOUT_SEC}s)...")
                
                followup_bytes = await capture_utterance(
                    stream, 
                    min_sec=0.5,
                    timeout_sec=FOLLOWUP_TIMEOUT_SEC
                )
                
                if not followup_bytes:
                    logger.warning("Timeout — aucune commande recue apres 'Exo'")
                    logger.info("En ecoute... Dites 'Exo' pour activer.")
                    continue
                
                followup_duration = len(followup_bytes) / (SAMPLE_RATE * 2)
                logger.info(f"Transcription commande ({followup_duration:.1f}s)...")
                followup_text = await loop.run_in_executor(None, transcribe_buffer, followup_bytes)
                
                if not followup_text:
                    logger.warning("Commande vide apres transcription")
                    logger.info("En ecoute... Dites 'Exo' pour activer.")
                    continue
                
                # Combiner fragment + followup si nécessaire
                if command:
                    full_command = command + " " + followup_text
                else:
                    full_command = followup_text
                
                logger.info(f"Commande complete: '{full_command}'")
                await process_command(full_command)
            
            logger.info("-" * 50)
            logger.info("En ecoute... Dites 'Exo' pour activer.")

    except KeyboardInterrupt:
        logger.info("\nArret demande par l'utilisateur")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
        pygame.mixer.quit()
        await brain.close()
        logger.info("Ressources liberees. Au revoir!")


if __name__ == "__main__":
    asyncio.run(main())
