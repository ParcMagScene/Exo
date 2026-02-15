"""app.py — Application Qt/QML pour EXO.

Lance la fenêtre principale et intègre le pipeline vocal
dans un thread asyncio séparé.
"""

import asyncio
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QUrl, QCoreApplication, Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

from src.gui.theme import ExoTheme
from src.gui.bridge import ExoBridge

logger = logging.getLogger(__name__)

# Répertoire racine du projet
PROJECT_DIR = Path(__file__).parent.parent.parent
QML_DIR = Path(__file__).parent / "qml"


class ExoApp:
    """Application Qt pour EXO avec pipeline vocal intégré."""

    def __init__(self, device_index=None, whisper_model="base"):
        self.device_index = device_index
        self.whisper_model = whisper_model

        self._qt_app: Optional[QGuiApplication] = None
        self._engine: Optional[QQmlApplicationEngine] = None
        self._theme = None
        self._bridge = None
        self._async_thread: Optional[threading.Thread] = None
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None

    def run(self):
        """Lance l'application (bloquant)."""
        # Forcer le style QML Basic pour permettre la personnalisation
        os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

        # Attributs Qt
        QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

        self._qt_app = QGuiApplication(sys.argv)
        self._qt_app.setApplicationName("EXO")
        self._qt_app.setOrganizationName("EXO")

        # Icône
        icon_path = PROJECT_DIR / "assets" / "exo_icon.png"
        if icon_path.exists():
            self._qt_app.setWindowIcon(QIcon(str(icon_path)))

        # Thème et bridge
        self._theme = ExoTheme()
        self._bridge = ExoBridge()

        # Moteur QML
        self._engine = QQmlApplicationEngine()

        # Ajouter les chemins d'import QML pour les composants
        for subdir in ["components", "pages", "floorplan"]:
            import_path = QML_DIR / subdir
            if import_path.exists():
                self._engine.addImportPath(str(import_path))

        # Exposer les objets Python au QML
        self._engine.rootContext().setContextProperty("Theme", self._theme)
        self._engine.rootContext().setContextProperty("Bridge", self._bridge)

        # Charger le QML principal
        qml_file = QML_DIR / "Main.qml"
        if not qml_file.exists():
            logger.error("Fichier QML introuvable : %s", qml_file)
            sys.exit(1)

        self._engine.load(QUrl.fromLocalFile(str(qml_file)))

        if not self._engine.rootObjects():
            logger.error("Impossible de charger le QML")
            sys.exit(1)

        logger.info("Interface EXO chargee")

        # Lancer le pipeline vocal dans un thread asyncio
        self._start_async_pipeline()

        # Boucle Qt (bloquant)
        exit_code = self._qt_app.exec()

        # Nettoyage
        self._stop_async_pipeline()
        sys.exit(exit_code)

    def _start_async_pipeline(self):
        """Démarre le pipeline vocal dans un thread séparé."""
        self._async_loop = asyncio.new_event_loop()

        def _run_loop():
            asyncio.set_event_loop(self._async_loop)
            self._async_loop.run_until_complete(self._pipeline_main())

        self._async_thread = threading.Thread(
            target=_run_loop, name="exo-pipeline", daemon=True
        )
        self._async_thread.start()
        logger.info("Pipeline vocal demarre (thread asyncio)")

    async def _pipeline_main(self):
        """Coroutine principale du pipeline vocal."""
        try:
            from src.core.listener import ExoListener

            listener = ExoListener(
                device_index=self.device_index,
                whisper_model=self.whisper_model,
            )

            # Connecter le listener au bridge pour les mises à jour d'état
            self._bridge._listener = listener

            # Patcher le listener pour notifier le bridge
            original_process = listener._process_command

            async def _patched_process(command_text):
                self._bridge.set_pipeline_state("processing")
                self._bridge.set_transcript(command_text)
                result = await original_process(command_text)
                self._bridge.set_pipeline_state("idle")
                return result

            listener._process_command = _patched_process

            await listener.start()

        except Exception as e:
            logger.error("Erreur pipeline : %s", e, exc_info=True)

    def _stop_async_pipeline(self):
        """Arrête proprement le pipeline."""
        if self._async_loop and self._async_loop.is_running():
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
        if self._async_thread:
            self._async_thread.join(timeout=3)
        logger.info("Pipeline vocal arrete")
