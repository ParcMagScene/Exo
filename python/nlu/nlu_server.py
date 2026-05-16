#!/usr/bin/env python3
"""

# Patch global EXO : forcer le working directory à D:/EXO/ pour tous les services
import os
os.chdir("D:/EXO/")
EXO v10 — IntentEngine v3 / NLU Server (WebSocket)
Port 8772 — Compréhension avancée des intentions

IntentEngine v3 :
  - Classification fine des intentions (7 types)
  - Extraction des objectifs, contraintes, préférences, dépendances
  - Détection des intentions implicites
  - Fallback regex (toujours disponible)

Protocol WebSocket :
  → {"action":"classify","text":"..."}           ← classification simple
  → {"action":"parse_intent","text":"..."}        ← intent complète v3
  → {"action":"extract_goals","text":"..."}       ← objectifs
  → {"action":"extract_constraints","text":"..."}  ← contraintes
  → {"action":"extract_preferences","text":"..."}  ← préférences
"""

import asyncio
try:
    import ujson as json  # v6.0 perf : 3-5x plus rapide que stdlib (audit perf)
except ImportError:
    import json
import logging
import re
import sys
import argparse
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")

# Singleton guard — prevent duplicate instances
from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9, json_loads, json_dumps


# --- Logging EXO centralisé (identique C++) ---
import os
from pathlib import Path
def _get_exo_logfile():
    # Correction : tous les logs doivent aller dans D:/EXO/logs/
    project_root = Path(__file__).resolve().parent.parent.parent
    log_dir = os.environ.get("EXO_LOGS_DIR", str(project_root / "logs"))
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    ts = os.environ.get("EXO_SESSION_TIMESTAMP")
    if not ts:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(log_dir, f"exo_{ts}.log")

logfile = _get_exo_logfile()

_file_handler = logging.FileHandler(logfile, encoding="utf-8", delay=False)
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [NLU] %(message)s"))
_file_handler.flush = _file_handler.stream.flush
log = logging.getLogger("nlu_server")
log.addHandler(_file_handler)
log.propagate = True
log.info("=== EXO NLU_SERVER STARTUP ===")
_file_handler.flush()

# ─────────────────────────────────────────────────────
#  Intent definitions — commandes locales reconnues
# ─────────────────────────────────────────────────────

INTENTS = {
    "weather": {
        "patterns": [
            r"(quel|quelle).*(temps|météo|température|meteo)",
            r"(il|va).*(pleuvoir|neiger|faire\s+(beau|chaud|froid))",
            r"(météo|meteo)\s+(à|au|en|de|du)",
            r"(prévisions?|forecast)",
        ],
        "entities": ["city", "date"],
    },
    "time": {
        "patterns": [
            r"(quelle\s+heure|l'heure|heure\s+(est|actuelle))",
            r"(quel\s+jour|quelle\s+date|date\s+(d'aujourd'hui|actuelle))",
        ],
        "entities": [],
    },
    "timer": {
        "patterns": [
            r"(mets?|lance|démarre?|start)\s+(un\s+)?(minuteur|timer|chrono)",
            r"(rappelle|réveille)[\s-]moi\s+(dans|en)\s+\d+",
        ],
        "entities": ["duration"],
    },
    "home_control": {
        "patterns": [
            r"(allume|éteins?|ouvre|ferme|monte|baisse|active|désactive)\s+(la|le|les|l'|l'|mon|ma|mes)\s+",
            r"(lumière|lampe|volet|store|chauffage|ventilateur|climatisation|clim)\s+(du|de la|des|de)\s+",
        ],
        "entities": ["device", "room", "action"],
    },
    "music": {
        "patterns": [
            r"(joue|mets?|lance|écoute)\s+(de\s+la\s+musique|une?\s+(chanson|morceau|playlist))",
            r"(spotify|musique|playlist|artiste|album)\s+",
            r"(volume)\s+(plus|moins|à|au)\s+",
            r"(pause|stop|suivant|précédent|reprend)",
        ],
        "entities": ["artist", "song", "action"],
    },
    "reminder": {
        "patterns": [
            r"rappelle[\s-]moi\s+de\s+",
            r"n'oublie\s+pas\s+de\s+",
            r"(rappelle|n'oublie\s+pas|note|retiens)\s+",
            r"(ajoute|créer?|fais)\s+(une?\s+)?(rappel|note|tâche|todo)",
        ],
        "entities": ["text", "time"],
    },
    "greeting": {
        "patterns": [
            r"^(bonjour|salut|hey|coucou|bonsoir|hello|hi)\b",
            r"^(ça\s+va|comment\s+(ça\s+va|vas[\s-]tu|allez[\s-]vous))",
        ],
        "entities": [],
    },
    "goodbye": {
        "patterns": [
            r"(au\s+revoir|bonne\s+(nuit|soirée|journée)|à\s+(plus|bientôt|demain))",
            r"^(bye|ciao|tchao|salut)\b",
        ],
        "entities": [],
    },
}

# ─────────────────────────────────────────────────────
#  Regex-based NLU engine (always available fallback)
# ─────────────────────────────────────────────────────

class RegexNLU:
    """Lightweight regex-based intent classifier for common commands."""

    def __init__(self):
        self._compiled = {}
        for intent, data in INTENTS.items():
            self._compiled[intent] = [
                re.compile(p, re.IGNORECASE) for p in data["patterns"]
            ]

    def classify(self, text: str) -> dict:
        text_lower = text.lower().strip()
        best_intent = None
        best_score = 0.0

        for intent, patterns in self._compiled.items():
            for pat in patterns:
                m = pat.search(text_lower)
                if m:
                    # Score based on match length vs text length
                    match_len = m.end() - m.start()
                    score = min(0.95, 0.5 + 0.5 * match_len / max(len(text_lower), 1))
                    if score > best_score:
                        best_score = score
                        best_intent = intent

        if best_intent and best_score > 0.4:
            entities = self._extract_entities(text_lower, best_intent)
            return {
                "intent": best_intent,
                "entities": entities,
                "confidence": round(best_score, 3),
                "use_claude": best_score < 0.7,
                "engine": "regex",
            }

        return {
            "intent": "unknown",
            "entities": {},
            "confidence": 0.0,
            "use_claude": True,
            "engine": "regex",
        }

    def _extract_entities(self, text: str, intent: str) -> dict:
        entities = {}

        # Duration extraction (for timer/reminder)
        dur_match = re.search(r"(\d+)\s*(minute|min|seconde|sec|heure|h)\b", text)
        if dur_match:
            entities["duration_value"] = int(dur_match.group(1))
            entities["duration_unit"] = dur_match.group(2)

        # Room extraction for home_control
        rooms = ["salon", "chambre", "cuisine", "bureau", "salle de bain",
                 "garage", "jardin", "terrasse", "entrée", "couloir"]
        for room in rooms:
            if room in text:
                entities["room"] = room
                break

        # Device extraction for home_control
        devices = ["lumière", "lampe", "volet", "store", "chauffage",
                   "ventilateur", "climatisation", "clim", "télé", "tv"]
        for device in devices:
            if device in text:
                entities["device"] = device
                break

        # Action extraction
        if re.search(r"(allume|ouvre|monte|active|augmente)", text):
            entities["action"] = "on"
        elif re.search(r"(éteins?|ferme|baisse|désactive|diminue)", text):
            entities["action"] = "off"

        return entities


# ─────────────────────────────────────────────────────
#  IntentEngine v3 — Classification avancée
# ─────────────────────────────────────────────────────

class IntentType(str, Enum):
    SIMPLE = "action_simple"
    COMPLEX = "action_complex"
    SCENARIO = "scenario"
    MULTI_STEP = "multi_step"
    CONDITIONAL = "conditional"
    PARALLEL = "parallel"
    RECURRING = "recurring"


@dataclass
class Intent:
    """Résultat d'analyse d'intention complète."""
    text: str
    intent: str = "unknown"
    intent_type: str = IntentType.SIMPLE.value
    confidence: float = 0.0
    entities: dict = field(default_factory=dict)
    goals: list = field(default_factory=list)
    constraints: list = field(default_factory=list)
    preferences: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    implicit_intents: list = field(default_factory=list)
    use_claude: bool = True
    engine: str = "regex"

    def to_dict(self) -> dict:
        return asdict(self)


# Patterns pour détection du type d'intention
_MULTI_STEP_PATTERNS = [
    re.compile(r"(d'abord|ensuite|puis|après|enfin|finalement)", re.I),
    re.compile(r"(étape|step)\s*\d+", re.I),
]
_CONDITIONAL_PATTERNS = [
    re.compile(r"(si|quand|lorsque|à condition|seulement si|dans le cas)", re.I),
]
_PARALLEL_PATTERNS = [
    re.compile(r"(en même temps|simultanément|pendant que|et aussi|en parallèle)", re.I),
]
_RECURRING_PATTERNS = [
    re.compile(r"(tous les|chaque|chaque jour|toutes les|hebdomadaire|quotidien)", re.I),
    re.compile(r"(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)s?\b", re.I),
]
_SCENARIO_PATTERNS = [
    re.compile(r"(scénario|routine|automatisation|programme|séquence)", re.I),
    re.compile(r"(mode|ambiance)\s+(cinéma|nuit|matin|soirée|travail|détente)", re.I),
]
_COMPLEX_PATTERNS = [
    re.compile(r"(recherche|analyse|compare|résume|explique|planifie)", re.I),
    re.compile(r"(et|puis)\s+(aussi|ensuite|après)", re.I),
]

# Patterns pour extraction des contraintes
_CONSTRAINT_PATTERNS = [
    (re.compile(r"(avant|d'ici|pas plus tard que)\s+(\d{1,2}[h:]\d{0,2}|\d{1,2}\s*heures?)", re.I), "temporal"),
    (re.compile(r"(maximum|max|pas plus de|moins de)\s+(\d+)", re.I), "limit"),
    (re.compile(r"(sans|sauf|excepté|hormis)\s+(.{3,30}?)(?:\.|,|$)", re.I), "exclusion"),
    (re.compile(r"(uniquement|seulement|que)\s+(.{3,30}?)(?:\.|,|$)", re.I), "restriction"),
]

# Patterns pour extraction des préférences
_PREFERENCE_PATTERNS = [
    (re.compile(r"(je préfère|j'aime mieux|plutôt|de préférence)\s+(.{3,40}?)(?:\.|,|$)", re.I), "preference"),
    (re.compile(r"(en français|en anglais|en [a-zé]+)\b", re.I), "language"),
    (re.compile(r"(rapide|rapidement|vite|lentement|doucement)", re.I), "speed"),
]

# Patterns pour extraction des objectifs
_GOAL_PATTERNS = [
    (re.compile(r"(je veux|je voudrais|j'aimerais|peux-tu|pourr(?:ais|iez)-(?:tu|vous))\s+(.{5,80}?)(?:\.|!|\?|$)", re.I), "explicit_goal"),
    (re.compile(r"(fais|fait|lance|démarre|commence|exécute)\s+(.{3,50}?)(?:\.|,|$)", re.I), "imperative_goal"),
]

# Intentions implicites
_IMPLICIT_INTENT_MAP = {
    "weather": ["time"],  # météo → souvent aussi l'heure
    "home_control": [],
    "music": [],
    "reminder": ["time"],
    "timer": [],
    "greeting": [],
    "goodbye": [],
}


class IntentEngine:
    """IntentEngine v3 — Moteur d'intention avancé."""

    def __init__(self, nlu: RegexNLU):
        self._nlu = nlu

    def parse_intent(self, text: str) -> Intent:
        """Analyse complète de l'intention."""
        base = self._nlu.classify(text)
        intent = Intent(
            text=text,
            intent=base["intent"],
            confidence=base["confidence"],
            entities=base["entities"],
            use_claude=base["use_claude"],
            engine=base["engine"],
        )
        intent.intent_type = self._detect_type(text)
        intent.goals = self.extract_goals(text)
        intent.constraints = self.extract_constraints(text)
        intent.preferences = self.extract_preferences(text)
        intent.dependencies = self._extract_dependencies(text)
        intent.implicit_intents = self._detect_implicit(intent.intent, text)
        # Action complexe si multi-step / conditionnel / parallèle
        if intent.intent_type != IntentType.SIMPLE.value:
            intent.use_claude = True
        return intent

    def _detect_type(self, text: str) -> str:
        """Détecte le type d'intention."""
        for pat in _SCENARIO_PATTERNS:
            if pat.search(text):
                return IntentType.SCENARIO.value
        for pat in _MULTI_STEP_PATTERNS:
            if pat.search(text):
                return IntentType.MULTI_STEP.value
        for pat in _CONDITIONAL_PATTERNS:
            if pat.search(text):
                return IntentType.CONDITIONAL.value
        for pat in _PARALLEL_PATTERNS:
            if pat.search(text):
                return IntentType.PARALLEL.value
        for pat in _RECURRING_PATTERNS:
            if pat.search(text):
                return IntentType.RECURRING.value
        for pat in _COMPLEX_PATTERNS:
            if pat.search(text):
                return IntentType.COMPLEX.value
        return IntentType.SIMPLE.value

    def extract_goals(self, text: str) -> list[dict]:
        """Extrait les objectifs explicites et implicites."""
        goals = []
        for pat, gtype in _GOAL_PATTERNS:
            m = pat.search(text)
            if m:
                goals.append({"type": gtype, "text": m.group(2).strip()})
        if not goals and len(text) > 3:
            goals.append({"type": "inferred", "text": text.strip()})
        return goals

    def extract_constraints(self, text: str) -> list[dict]:
        """Extrait les contraintes."""
        constraints = []
        for pat, ctype in _CONSTRAINT_PATTERNS:
            m = pat.search(text)
            if m:
                constraints.append({"type": ctype, "value": m.group(2).strip()})
        return constraints

    def extract_preferences(self, text: str) -> list[dict]:
        """Extrait les préférences utilisateur."""
        prefs = []
        for pat, ptype in _PREFERENCE_PATTERNS:
            m = pat.search(text)
            if m:
                val = m.group(2).strip() if m.lastindex >= 2 else m.group(1).strip()
                prefs.append({"type": ptype, "value": val})
        return prefs

    def _extract_dependencies(self, text: str) -> list[dict]:
        """Extrait les dépendances inter-actions."""
        deps = []
        dep_pats = [
            (re.compile(r"(après avoir|une fois que|quand)\s+(.{5,50}?)(?:,|\.|$)", re.I), "sequential"),
            (re.compile(r"(il faut d'abord|avant de|avant que)\s+(.{5,50}?)(?:,|\.|$)", re.I), "prerequisite"),
        ]
        for pat, dtype in dep_pats:
            m = pat.search(text)
            if m:
                deps.append({"type": dtype, "condition": m.group(2).strip()})
        return deps

    def _detect_implicit(self, intent: str, text: str) -> list[str]:
        """Détecte les intentions implicites."""
        return list(_IMPLICIT_INTENT_MAP.get(intent, []))


# ─────────────────────────────────────────────────────
#  Transformer-based NLU (optional, better accuracy)
# ─────────────────────────────────────────────────────

_transformer_nlu = None

def _try_load_transformer(model_name: str):
    """Try to load a small local LLM for NLU. Returns None if unavailable."""
    global _transformer_nlu
    try:
        from transformers import pipeline as hf_pipeline
        log.info(f"Loading local NLU model: {model_name}")
        _transformer_nlu = hf_pipeline(
            "text-classification",
            model=model_name,
            device="cpu",
            max_length=128,
            truncation=True,
        )
        log.info(f"Local NLU model loaded: {model_name}")
    except Exception as e:
        log.warning(f"Could not load transformer NLU ({model_name}): {e}")
        _transformer_nlu = None


# ─────────────────────────────────────────────────────
#  NLU Server — WebSocket handler
# ─────────────────────────────────────────────────────

regex_nlu = RegexNLU()
intent_engine = IntentEngine(regex_nlu)
CONFIDENCE_THRESHOLD = 0.65  # above this → direct action (skip Claude)


async def handle_client(ws):
    remote = ws.remote_address
    log.info(f"Client connected: {remote}")
    try:
        # Envoyer le message ready au client (ReadinessProtocol v5)
        await ws.send(json_dumps({
            "type": "ready",
            "service": "nlu",
            "intents": list(INTENTS.keys()),
        }))
        async for raw in ws:
            # --- v9.1 standard protocol delegation ---
            v9_resp = await _v9.handle_ws_message(ws, raw)
            if v9_resp is not None:
                await ws.send(v9_resp)
                continue

            try:
                msg = json_loads(raw)
            except Exception:
                await ws.send(json_dumps({"type": "error", "message": "Invalid JSON"}))
                continue

            action = msg.get("action", "")

            if action == "classify":
                text = msg.get("text", "").strip()
                if not text:
                    await ws.send(json_dumps({"type": "error", "message": "Empty text"}))
                    continue
                _v9.begin_request()
                result = regex_nlu.classify(text)
                result["type"] = "nlu_result"
                await ws.send(json_dumps(result))
                _v9.end_request()

            elif action == "parse_intent":
                text = msg.get("text", "").strip()
                if not text:
                    await ws.send(json_dumps({"type": "error", "message": "Empty text"}))
                    continue
                _v9.begin_request()
                intent = intent_engine.parse_intent(text)
                resp = intent.to_dict()
                resp["type"] = "intent_result"
                await ws.send(json_dumps(resp))
                _v9.end_request()

            elif action == "extract_goals":
                text = msg.get("text", "").strip()
                if not text:
                    await ws.send(json_dumps({"type": "error", "message": "Empty text"}))
                    continue
                _v9.begin_request()
                goals = intent_engine.extract_goals(text)
                await ws.send(json_dumps({"type": "goals", "goals": goals}))
                _v9.end_request()

            elif action == "extract_constraints":
                text = msg.get("text", "").strip()
                if not text:
                    await ws.send(json_dumps({"type": "error", "message": "Empty text"}))
                    continue
                _v9.begin_request()
                constraints = intent_engine.extract_constraints(text)
                await ws.send(json_dumps({"type": "constraints", "constraints": constraints}))
                _v9.end_request()

            elif action == "extract_preferences":
                text = msg.get("text", "").strip()
                if not text:
                    await ws.send(json_dumps({"type": "error", "message": "Empty text"}))
                    continue
                _v9.begin_request()
                prefs = intent_engine.extract_preferences(text)
                await ws.send(json_dumps({"type": "preferences", "preferences": prefs}))
                _v9.end_request()

            elif action == "list_intents":
                intents = list(INTENTS.keys())
                await ws.send(json_dumps({"type": "intents", "intents": intents}))

            else:
                await ws.send(json_dumps({"type": "error", "message": f"Unknown action: {action}"}))

    except websockets.ConnectionClosed:
        pass
    finally:
        log.info(f"Client disconnected: {remote}")


async def main(host: str, port: int, model: Optional[str]):
    global _v9

    # Prevent duplicate instances
    ensure_single_instance(port, "nlu_server")
    _v9 = init_v9("nlu_server", port)

    if model:
        _try_load_transformer(model)

    log.info(f"NLU server starting on ws://{host}:{port}")
    async with websockets.serve(
        handle_client, host, port,
        **_v9.ws_serve_kwargs(),
    ):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    pa = argparse.ArgumentParser(description="EXO NLU Local Server")
    pa.add_argument("--host", default="localhost")
    pa.add_argument("--port", type=int, default=8772)
    pa.add_argument("--model", default=None,
                    help="HuggingFace model name for transformer NLU (optional)")
    args = pa.parse_args()
    asyncio.run(main(args.host, args.port, args.model))
