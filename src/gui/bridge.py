"""bridge.py — Pont Python ↔ QML pour EXO.

Expose l'état du pipeline vocal, la domotique et les réglages
au monde QML via des signaux/slots Qt.
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QObject,
    Property,
    Signal,
    Slot,
    QTimer,
    QThread,
    QUrl,
)

logger = logging.getLogger(__name__)


class ExoBridge(QObject):
    """Pont bidirectionnel Python ↔ QML.

    - Expose l'état du pipeline (idle/listening/processing/responding)
    - Reçoit les actions utilisateur depuis QML (domotique, réglages)
    - Gère la sauvegarde/chargement des plans de maison
    """

    # ─── Signaux vers QML ─────────────────────────────────

    # Pipeline vocal
    stateChanged = Signal(str)           # "idle", "listening", "processing", "responding"
    transcriptChanged = Signal(str)      # Texte transcrit en temps réel
    responseChanged = Signal(str)        # Réponse de l'assistant
    listeningChanged = Signal(bool)      # Micro actif ou non

    # Domotique
    haConnectedChanged = Signal(bool)
    entitiesChanged = Signal(str)        # JSON string des entités HA
    entityStateChanged = Signal(str, str, str)  # entity_id, state, attributes_json

    # Plans
    floorPlansChanged = Signal(str)      # JSON string des plans

    # Horloge
    timeChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._state = "idle"
        self._transcript = ""
        self._response = ""
        self._listening = False
        self._ha_connected = False
        self._floor_plans_path = Path("config/floor_plans.json")
        self._floor_plans = self._load_floor_plans()

        # Listener reference (set by app.py)
        self._listener = None
        self._home_bridge = None

        # Horloge
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

    # ─── État pipeline ────────────────────────────────────

    @Property(str, notify=stateChanged)
    def state(self):
        return self._state

    @state.setter  # type: ignore
    def state(self, value: str):
        if self._state != value:
            self._state = value
            self.stateChanged.emit(value)

    @Property(str, notify=transcriptChanged)
    def transcript(self):
        return self._transcript

    @Property(str, notify=responseChanged)
    def response(self):
        return self._response

    @Property(bool, notify=listeningChanged)
    def listening(self):
        return self._listening

    # ─── Méthodes appelées par le pipeline Python ─────────

    def set_pipeline_state(self, state: str):
        """Appelé depuis listener.py pour mettre à jour l'état."""
        self.state = state

    def set_transcript(self, text: str):
        """Appelé quand un transcript est disponible."""
        self._transcript = text
        self.transcriptChanged.emit(text)

    def set_response(self, text: str):
        """Appelé quand la réponse de l'assistant est prête."""
        self._response = text
        self.responseChanged.emit(text)

    # ─── Slots appelés depuis QML ─────────────────────────

    @Slot(str, str, result=bool)
    def callService(self, entity_id: str, action: str) -> bool:
        """Appelle un service HA depuis l'interface."""
        logger.info("🏠 GUI → HA : %s → %s", entity_id, action)
        if self._home_bridge:
            domain = entity_id.split(".")[0]
            service = f"turn_{action}" if action in ("on", "off") else action
            asyncio.ensure_future(
                self._home_bridge.call_service(domain, service, {"entity_id": entity_id})
            )
            return True
        return False

    @Slot(str, int)
    def setLightBrightness(self, entity_id: str, brightness: int):
        """Règle la luminosité d'une lumière."""
        if self._home_bridge:
            asyncio.ensure_future(
                self._home_bridge.call_service(
                    "light", "turn_on",
                    {"entity_id": entity_id, "brightness": int(brightness * 255 / 100)}
                )
            )

    @Slot(str, str)
    def setLightColor(self, entity_id: str, color: str):
        """Change la couleur d'une lumière."""
        if self._home_bridge:
            asyncio.ensure_future(
                self._home_bridge.call_service(
                    "light", "turn_on",
                    {"entity_id": entity_id, "color_name": color}
                )
            )

    # ─── Plans de maison ──────────────────────────────────

    @Slot(result=str)
    def getFloorPlans(self) -> str:
        """Retourne les plans en JSON."""
        return json.dumps(self._floor_plans, ensure_ascii=False)

    @Slot(str)
    def saveFloorPlans(self, plans_json: str):
        """Sauvegarde les plans depuis QML."""
        try:
            self._floor_plans = json.loads(plans_json)
            self._floor_plans_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._floor_plans_path, "w", encoding="utf-8") as f:
                json.dump(self._floor_plans, f, indent=2, ensure_ascii=False)
            logger.info("✅ Plans sauvegardés : %s", self._floor_plans_path)
        except Exception as e:
            logger.error("Erreur sauvegarde plans : %s", e)

    @Slot(str, float, float, str)
    def addDeviceToFloorPlan(self, plan_id: str, x: float, y: float, entity_id: str):
        """Ajoute un appareil sur un plan à une position donnée."""
        for plan in self._floor_plans.get("plans", []):
            if plan.get("id") == plan_id:
                if "devices" not in plan:
                    plan["devices"] = []
                plan["devices"].append({
                    "entity_id": entity_id,
                    "x": x,
                    "y": y,
                })
                self.saveFloorPlans(json.dumps(self._floor_plans))
                self.floorPlansChanged.emit(self.getFloorPlans())
                return

    @Slot(str, str, float, float)
    def moveDeviceOnPlan(self, plan_id: str, entity_id: str, x: float, y: float):
        """Déplace un appareil sur le plan."""
        for plan in self._floor_plans.get("plans", []):
            if plan.get("id") == plan_id:
                for dev in plan.get("devices", []):
                    if dev["entity_id"] == entity_id:
                        dev["x"] = x
                        dev["y"] = y
                        self.saveFloorPlans(json.dumps(self._floor_plans))
                        return

    @Slot(str, str, result=str)
    def addFloorPlan(self, name: str, image_path: str) -> str:
        """Crée un nouveau plan de maison."""
        import uuid
        plan_id = str(uuid.uuid4())[:8]
        if "plans" not in self._floor_plans:
            self._floor_plans["plans"] = []
        self._floor_plans["plans"].append({
            "id": plan_id,
            "name": name,
            "image": image_path,
            "devices": [],
            "rooms": [],
        })
        self.saveFloorPlans(json.dumps(self._floor_plans))
        self.floorPlansChanged.emit(self.getFloorPlans())
        return plan_id

    # ─── Réglages ─────────────────────────────────────────

    @Slot(result=str)
    def getSettings(self) -> str:
        """Retourne les réglages actuels en JSON."""
        return json.dumps({
            "whisper_model": os.environ.get("WHISPER_MODEL", "base"),
            "tts_engine": os.environ.get("TTS_ENGINE", "kokoro"),
            "vad_multiplier": float(os.environ.get("EXO_VAD_MULTIPLIER", "2.5")),
            "ha_url": os.environ.get("HA_URL", ""),
            "ha_connected": self._ha_connected,
        }, ensure_ascii=False)

    @Slot(str, str)
    def setSetting(self, key: str, value: str):
        """Modifie un réglage (et l'env var correspondante)."""
        env_map = {
            "whisper_model": "WHISPER_MODEL",
            "tts_engine": "TTS_ENGINE",
            "vad_multiplier": "EXO_VAD_MULTIPLIER",
            "ha_url": "HA_URL",
        }
        env_key = env_map.get(key)
        if env_key:
            os.environ[env_key] = value
            logger.info("⚙️ Réglage modifié : %s = %s", env_key, value)

    # ─── Privé ────────────────────────────────────────────

    def _update_clock(self):
        from datetime import datetime
        now = datetime.now().strftime("%H:%M")
        self.timeChanged.emit(now)

    def _load_floor_plans(self) -> dict:
        """Charge les plans depuis le fichier JSON."""
        if self._floor_plans_path.exists():
            try:
                with open(self._floor_plans_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"plans": []}
