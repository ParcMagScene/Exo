"""main.py - Point d'entrée de l'assistant vocal EXO.

Pipeline permanent:
  Micro en continu → VAD → Whisper STT → Détection « EXO »
  → GPT-4o (BrainEngine) → TTS Kokoro → Playback

Utilisation:
  python main.py                   # Console seule
  python main.py --gui             # Interface graphique PySide6
  python main.py --device 1        # Micro index 1 (ex: Brio 500)
  python main.py --whisper base    # Modèle Whisper plus léger
"""

import asyncio
import argparse
import logging
import sys
import os
from dotenv import load_dotenv

# Load .env en premier
load_dotenv()

# Setup logging
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("assistant.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


async def main():
    """Démarre EXO en écoute permanente."""
    parser = argparse.ArgumentParser(description="EXO — Assistant vocal permanent")
    parser.add_argument(
        "--gui", action="store_true",
        help="Lancer l'interface graphique PySide6/QML"
    )
    parser.add_argument(
        "--device", type=int, default=None,
        help="Index du micro PyAudio (None = défaut système)"
    )
    parser.add_argument(
        "--whisper", type=str, default="base",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Taille du modèle Whisper (défaut: base)"
    )
    args = parser.parse_args()

    if args.gui:
        # Mode GUI — lance PySide6/QML avec pipeline en arrière-plan
        from src.gui.app import ExoApp
        app = ExoApp(
            device_index=args.device,
            whisper_model=args.whisper,
        )
        app.run()  # Bloquant (Qt event loop)
    else:
        # Mode console — pipeline seul
        from src.core.listener import ExoListener
        listener = ExoListener(
            device_index=args.device,
            whisper_model=args.whisper,
        )
        await listener.start()


if __name__ == "__main__":
    # En mode GUI, main() n'est pas async (Qt gère la boucle)
    import sys as _sys
    if "--gui" in _sys.argv:
        import asyncio as _asyncio
        _asyncio.run(main())
    else:
        asyncio.run(main())
