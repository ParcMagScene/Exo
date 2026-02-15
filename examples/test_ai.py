#!/usr/bin/env python3
"""
Test pipeline complet : Écoute micro → Transcription Whisper → Réponse GPT-4o.

Pipeline E2E:
  1. AudioCapture     → capture micro (PyAudio, 16kHz mono PCM16)
  2. HardwareAccel    → transcription Faster-Whisper (STT)
  3. BrainEngine      → réponse GPT-4o (LLM + Function Calling)

Modes:
  --mode full      Pipeline complet (micro → whisper → GPT-4o)
  --mode text      Texte tapé → GPT-4o (sans micro)
  --mode stt       Micro → Whisper uniquement (pas de GPT-4o)
  --duration 5     Durée d'écoute en secondes (défaut: 5)
  --silence        Écouter jusqu'au silence au lieu d'une durée fixe
  --loop           Boucle continue (parler, réponse, parler...)
"""

import asyncio
import sys
import os
import time
import logging
import argparse
from pathlib import Path

os.environ["SUPPRESS_CONFIG_WARNINGS"] = "1"
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_section(title: str):
    print(f"\n  ── {title} ──")


# ─────────────────────────────────────────────────────────────
#  ÉTAPE 1 : Vérification des dépendances
# ─────────────────────────────────────────────────────────────

async def check_dependencies() -> dict:
    """Vérifie toutes les dépendances du pipeline."""
    print_header("VÉRIFICATION DES DÉPENDANCES")

    status = {"pyaudio": False, "whisper": False, "openai": False, "api_key": False}

    # PyAudio
    try:
        import pyaudio  # type: ignore
        pa = pyaudio.PyAudio()
        dev_count = pa.get_device_count()
        default_input = pa.get_default_input_device_info()
        print(f"  ✓ PyAudio OK — {dev_count} devices, défaut: {default_input['name']}")
        pa.terminate()
        status["pyaudio"] = True
    except Exception as e:
        print(f"  ✗ PyAudio — {e}")

    # Faster-Whisper
    try:
        import faster_whisper  # type: ignore
        print(f"  ✓ Faster-Whisper OK")
        status["whisper"] = True
    except ImportError:
        print(f"  ✗ Faster-Whisper — pip install faster-whisper")

    # OpenAI SDK
    try:
        import openai
        print(f"  ✓ OpenAI SDK {openai.__version__}")
        status["openai"] = True
    except ImportError:
        print(f"  ✗ OpenAI SDK — pip install openai")

    # Clé API
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key and api_key.startswith("sk-"):
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        print(f"  ✓ Clé API OpenAI configurée (modèle: {model})")
        status["api_key"] = True
    else:
        azure_key = os.getenv("AZURE_OPENAI_KEY", "")
        if azure_key and azure_key != "your-azure-api-key-here":
            print(f"  ✓ Clé API Azure OpenAI configurée")
            status["api_key"] = True
        else:
            print(f"  ✗ Aucune clé API (OPENAI_API_KEY ou AZURE_OPENAI_KEY)")

    return status


# ─────────────────────────────────────────────────────────────
#  ÉTAPE 2 : Capture audio micro
# ─────────────────────────────────────────────────────────────

async def capture_audio(duration: float = 5.0, use_silence: bool = False) -> bytes:
    """Capture l'audio depuis le microphone."""
    from src.audio.audio_capture import AudioCapture

    capture = AudioCapture(sample_rate=16000, channels=1)

    if use_silence:
        print(f"\n  🎤 Parlez maintenant... (arrêt automatique au silence)")
        audio_data = await capture.record_until_silence(
            silence_threshold=500,
            silence_duration=1.5,
            max_recording=30.0
        )
    else:
        print(f"\n  🎤 Parlez maintenant... (enregistrement {duration}s)")
        # Compte à rebours visuel
        audio_data = await capture.record_duration(duration)

    duration_real = len(audio_data) / (16000 * 2)  # 16kHz, 16-bit = 2 bytes/sample
    print(f"  ✓ Audio capturé : {len(audio_data)} bytes ({duration_real:.1f}s)")

    return audio_data


# ─────────────────────────────────────────────────────────────
#  ÉTAPE 3 : Transcription (Faster-Whisper STT)
# ─────────────────────────────────────────────────────────────

async def transcribe_audio(audio_data: bytes) -> str:
    """Transcrit l'audio capturé en texte via Faster-Whisper."""
    from src.hardware.hardware_accel import HardwareAccelerator

    print_section("TRANSCRIPTION (Faster-Whisper)")

    accel = HardwareAccelerator()
    await accel.initialize()

    start = time.time()
    text = await accel.transcribe_audio(audio_data)
    elapsed = time.time() - start

    if text:
        print(f"  📝 Transcription ({elapsed:.2f}s) :")
        print(f"     \"{text}\"")
    else:
        print(f"  ⚠ Aucun texte détecté (silence ou audio trop court)")

    return text


# ─────────────────────────────────────────────────────────────
#  ÉTAPE 4 : Réponse IA (GPT-4o via BrainEngine)
# ─────────────────────────────────────────────────────────────

async def get_ai_response(text: str, brain=None) -> tuple:
    """Envoie le texte transcrit au BrainEngine et obtient la réponse."""
    from src.brain.brain_engine import BrainEngine

    print_section("RÉPONSE IA (GPT-4o)")

    own_brain = brain is None
    if own_brain:
        brain = BrainEngine()
        await brain.initialize()

    print(f"  💬 Envoi : \"{text}\"")

    start = time.time()
    result = await brain.process_command(text)
    elapsed = time.time() - start

    response = result.get("text", "")
    function_calls = result.get("function_calls", [])

    print(f"\n  🤖 Réponse IA ({elapsed:.2f}s) :")
    print(f"  ─────────────────────────────────")
    for line in response.split("\n"):
        print(f"    {line}")
    print(f"  ─────────────────────────────────")

    if function_calls:
        print(f"\n  🔧 Function Calls détectés :")
        for fc in function_calls:
            print(f"    → {fc['name']}({fc['arguments']})")

    if own_brain:
        await brain.close()

    return response, function_calls, brain


# ─────────────────────────────────────────────────────────────
#  MODE COMPLET : Micro → Whisper → GPT-4o
# ─────────────────────────────────────────────────────────────

async def run_full_pipeline(duration: float, use_silence: bool, loop: bool):
    """Pipeline complet : écoute → transcription → réponse IA."""
    print_header("PIPELINE COMPLET : Micro → Whisper → GPT-4o")

    from src.brain.brain_engine import BrainEngine

    brain = BrainEngine()
    await brain.initialize()

    iteration = 0

    try:
        while True:
            iteration += 1
            if loop:
                print(f"\n  ━━━ Tour {iteration} ━━━")

            # Étape 1 : Écoute micro
            print_section("ÉCOUTE MICRO")
            audio_data = await capture_audio(duration, use_silence)

            if len(audio_data) < 3200:  # Moins de 0.1s d'audio
                print(f"  ⚠ Audio trop court, ignoré")
                if not loop:
                    break
                continue

            # Étape 2 : Transcription
            text = await transcribe_audio(audio_data)

            if not text or not text.strip():
                print(f"  ⚠ Rien détecté. Réessayez.")
                if not loop:
                    break
                continue

            # Étape 3 : Réponse IA
            response, fc, brain = await get_ai_response(text, brain=brain)

            if not loop:
                break

            # Pause avant prochain tour
            print(f"\n  ⏳ Prêt pour la prochaine question...")
            await asyncio.sleep(1.0)

    except KeyboardInterrupt:
        print(f"\n\n  ⚠ Arrêt demandé (Ctrl+C)")

    finally:
        await brain.close()
        print(f"\n  ✅ Pipeline terminé ({iteration} échange(s))")


# ─────────────────────────────────────────────────────────────
#  MODE TEXTE : Taper → GPT-4o
# ─────────────────────────────────────────────────────────────

async def run_text_mode(loop: bool):
    """Mode texte : taper sa question au clavier."""
    print_header("MODE TEXTE : Clavier → GPT-4o")
    print("  Tapez votre question (ou 'quit' pour quitter)\n")

    from src.brain.brain_engine import BrainEngine

    brain = BrainEngine()
    await brain.initialize()

    try:
        while True:
            try:
                user_input = input("  Vous > ").strip()
            except EOFError:
                break

            if user_input.lower() in ("quit", "exit", "q"):
                break

            if not user_input:
                continue

            response, fc, brain = await get_ai_response(user_input, brain=brain)

            if not loop:
                break

    except KeyboardInterrupt:
        print(f"\n\n  ⚠ Arrêt demandé")

    finally:
        await brain.close()
        print(f"  ✅ Session terminée")


# ─────────────────────────────────────────────────────────────
#  MODE STT : Micro → Whisper uniquement
# ─────────────────────────────────────────────────────────────

async def run_stt_mode(duration: float, use_silence: bool, loop: bool):
    """Mode STT uniquement : écoute et transcrit (sans appel IA)."""
    print_header("MODE STT : Micro → Whisper (sans IA)")

    iteration = 0

    try:
        while True:
            iteration += 1
            if loop:
                print(f"\n  ━━━ Tour {iteration} ━━━")

            audio_data = await capture_audio(duration, use_silence)

            if len(audio_data) < 3200:
                print(f"  ⚠ Audio trop court")
                if not loop:
                    break
                continue

            text = await transcribe_audio(audio_data)

            if not loop:
                break

            await asyncio.sleep(0.5)

    except KeyboardInterrupt:
        print(f"\n\n  ⚠ Arrêt demandé")

    print(f"  ✅ STT terminé ({iteration} transcription(s))")


# ─────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="Test pipeline : Écoute → Transcription → Réponse IA"
    )
    parser.add_argument(
        "--mode", choices=["full", "text", "stt"], default="full",
        help="Mode: full (micro→whisper→GPT), text (clavier→GPT), stt (micro→whisper)"
    )
    parser.add_argument(
        "--duration", type=float, default=5.0,
        help="Durée d'écoute en secondes (défaut: 5)"
    )
    parser.add_argument(
        "--silence", action="store_true",
        help="Écouter jusqu'au silence (au lieu d'une durée fixe)"
    )
    parser.add_argument(
        "--loop", action="store_true",
        help="Boucle continue (conversation multi-tours)"
    )

    args = parser.parse_args()

    # Vérification dépendances
    status = await check_dependencies()

    if args.mode in ("full", "stt"):
        if not status["pyaudio"]:
            print("\n  ABANDON — PyAudio requis pour le micro")
            return
        if not status["whisper"]:
            print("\n  ABANDON — Faster-Whisper requis pour la transcription")
            return

    if args.mode in ("full", "text"):
        if not status["api_key"]:
            print("\n  ABANDON — Clé API requise pour GPT-4o")
            return

    # Lancement du mode choisi
    if args.mode == "full":
        await run_full_pipeline(args.duration, args.silence, args.loop)

    elif args.mode == "text":
        await run_text_mode(args.loop)

    elif args.mode == "stt":
        await run_stt_mode(args.duration, args.silence, args.loop)

    print_header("TEST TERMINÉ")


if __name__ == "__main__":
    asyncio.run(main())
