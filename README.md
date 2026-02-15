# 🤖 EXO — Assistant Vocal Personnel

Assistant IA vocal avec wake word, domotique intégrée et architecture distribuée multi-room.

**Stack** : Faster-Whisper (STT) → GPT-4o-mini (LLM) → Kokoro TTS (voix) → Pygame (playback)

---

## Table des matières

- [Démarrage rapide](#-démarrage-rapide)
- [Architecture](#-architecture)
- [Pipeline vocal](#-pipeline-vocal)
- [Configuration](#-configuration)
- [Variables d'environnement](#-variables-denvironnement)
- [Tests](#-tests)
- [Installation & Déploiement](#-installation--déploiement)

---

## ⚡ Démarrage Rapide

```bash
# 1. Clone + virtual env
cd d:/Exo
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# 2. Installer
pip install -r requirements.txt

# 3. Config
copy .env.example .env
# Éditer .env : ajouter OPENAI_API_KEY (minimum requis)

# 4. Lancer
python main.py
```

Dites **« Exo »** suivi de votre commande. Ctrl+C pour quitter.

---

## 🏗️ Architecture

### Vue d'ensemble

```
┌──────────────────────────────────────────────────────────────┐
│                    SERVEUR CENTRAL (PC)                      │
├──────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              CORE (core.py)                              │ │
│  │  Machine d'états: IDLE→LISTENING→PROCESSING→RESPONDING  │ │
│  └─────────────────────────────────────────────────────────┘ │
│              ▲              ▲              ▲                  │
│    ┌─────────▼──┐  ┌───────▼────┐  ┌──────▼──────┐          │
│    │   WYOMING  │  │   BRAIN    │  │     HOME    │          │
│    │   (audio)  │  │   (LLM)    │  │   BRIDGE    │          │
│    └────────────┘  └────────────┘  └─────────────┘          │
│         │                 │                │                 │
│    ┌────▼──┐ ┌────▼──┐ ┌──▼──┐ ┌──▼──┐ ┌──▼──┐            │
│    │HARDWARE│ │MEMORY │ │ GUI │ │ HA  │ │MUSIC│             │
│    │ ACCEL  │ │(CHROMA)│ │(PYG)│ │(WS) │ │(MPD)│            │
│    └────────┘ └────────┘ └─────┘ └─────┘ └─────┘            │
└──────────────────────────────────────────────────────────────┘
         ▲                                  │
         │ Wyoming Protocol (WS)            │ WebSocket
    ┌────┴──────┐                  ┌───────▼────────┐
    │ Pi Zero/5 │                  │ Home Assistant  │
    │(satellites)│                  │  + Domotique   │
    └────────────┘                  └────────────────┘
```

### Structure du code

```
src/
├── core/
│   ├── core.py              # Orchestrateur (machine d'états)
│   └── listener.py          # Boucle d'écoute : micro → VAD → STT → Brain → TTS
├── audio/
│   └── wake_word.py         # VAD adaptatif + détection wake word "Exo"
├── brain/
│   ├── brain_engine.py      # LLM (GPT-4o-mini) + RAG ChromaDB + Function Calling
│   └── local_info.py        # Contexte temps réel (heure, météo)
├── assistant/
│   └── tts_client.py        # TTS cascade : Kokoro → Piper → OpenAI
├── integrations/
│   └── home_bridge.py       # Home Assistant WebSocket + REST
├── gui/
│   └── visage_gui.py        # Avatar Pygame (états synchronisés, 144Hz)
└── protocols/
    └── wyoming.py           # Serveur audio distribué multi-room (port 10700)
```

### Matériel

| Composant | Description |
|-----------|-------------|
| **Serveur** | PC Windows/Linux (CPU suffisant, GPU optionnel) |
| **Satellites** | Raspberry Pi Zero 2 W / Pi 5 (via Wyoming protocol) |
| **Domotique** | Home Assistant (HUE, IKEA, Samsung, EZWIZ, Petkit) |

### Flux de données

```
1. Audio capturé (PyAudio 16kHz mono PCM16)
       ▼
2. VAD adaptatif détecte la parole (RMS energy + calibration bruit)
       ▼
3. Whisper STT transcrit en texte français
       ▼
4. Wake word "Exo" détecté → commande extraite
       ▼
5. BrainEngine : contexte RAG (ChromaDB) + contexte local (heure/météo)
   → GPT-4o-mini avec Function Calling
       ▼
6. Actions exécutées (domotique, musique, mémoire)
       ▼
7. Réponse vocale : Kokoro TTS → Pygame playback
```

### ChromaDB — Base de connaissances

| Collection | Contenu |
|------------|---------|
| **animals** | Infos animaux ("Felix est un chat noir, aime les zones chaudes") |
| **house_plan** | Architecture maison ("Salon: 3 HUE, 1 IKEA, TV Samsung") |
| **user_preferences** | Préférences ("Lumière chaude le soir 2700K, Jazz au réveil") |

### Machine d'états

```
IDLE → LISTENING (audio reçu) → PROCESSING (STT + LLM) → RESPONDING (TTS) → IDLE
```

L'avatar GUI synchronise ses animations (yeux, spectre audio) sur ces états.

---

## 🎤 Pipeline Vocal

```
Microphone (PyAudio 16kHz)
    → VAD Adaptatif (RMS energy, calibration auto)
    → Faster-Whisper "base" (beam=1, CPU)
    → Wake Word "Exo" (13 variantes)
    → BrainEngine (GPT-4o-mini + RAG)
    → Kokoro TTS (24kHz, ff_siwis)
    → Pygame playback
```

### VAD — Voice Activity Detection

Détection par énergie RMS avec seuil adaptatif calibré au démarrage.

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| `VOICE_THRESHOLD` | 300 RMS | Seuil fixe (ajusté par l'adaptatif) |
| `SILENCE_CHUNKS` | 8 (~0.5s) | Silence requis pour fin d'utterance |
| `MIN_UTTERANCE_SEC` | 0.5s | Durée minimum valide |
| `MIN_VOICE_CHUNKS` | 4 | Chunks vocaux minimum (filtre bruit) |
| `EXO_VAD_MULTIPLIER` | 2.5 | Multiplicateur bruit → seuil |

**Calibration** : 30 chunks de bruit ambiant (médiane RMS) × multiplicateur, borné ±50% du seuil fixe.

### STT — Faster-Whisper

Exécution dans un thread executor (non-bloquant). Filtre automatique des hallucinations Whisper ("sous-titres", "amara.org"...).

| Paramètre | Valeur |
|-----------|--------|
| Modèle | `base` (configurable : tiny/base/small/medium/large) |
| beam_size | 1 (greedy) |
| Langue | FR forcé |
| Latence | ~0.5-1.5s |

### Wake Word

13 variantes reconnues : exo, écho, echo, expo, ego, exc, exot, x.o, x o, exau, exeau, exos, exho

Extraction : "Exo, quelle heure ?" → "quelle heure ?"

### TTS — Cascade

| Priorité | Moteur | Type | Latence |
|----------|--------|------|---------|
| 1 | **Kokoro** | Local 24kHz | ~0.8s |
| 2 | Piper | Local | ~0.3s |
| 3 | OpenAI TTS-1 | API | ~1-2s |
| 4 | Fish-Speech | API | Variable |
| 5 | Coqui VITS | Local | ~2-3s |

### Latence End-to-End

| Étape | Durée typique |
|-------|---------------|
| Capture VAD | 0.5-1s |
| Whisper STT | 0.5-1.5s |
| Brain GPT-4o-mini | 0.5-1.5s |
| Kokoro TTS | ~0.8s |
| **Total** | **~2-4s** |

---

## 🔧 Configuration

### .env minimal

```env
# LLM (au moins un requis)
OPENAI_API_KEY=sk-...                # OpenAI standard (prioritaire)
# ou Azure :
# AZURE_OPENAI_ENDPOINT=https://...
# AZURE_OPENAI_KEY=...

# Domotique (optionnel)
HA_URL=http://homeassistant.local:8123
HA_TOKEN=eyJ0eXAi...
```

---

## 📋 Variables d'environnement

### LLM

```env
# ── OpenAI standard (prioritaire) ──
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini           # Modèle à utiliser

# ── Azure OpenAI (fallback) ──
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### Home Assistant

```env
HA_URL=http://homeassistant.local:8123
HA_TOKEN=eyJ0eXAi...               # Long-lived access token
```

### STT & VAD

```env
WHISPER_MODEL=base                  # tiny|base|small|medium|large
WHISPER_WORKERS=8                   # Workers multi-thread (adapter au CPU)
DEVICE=auto                         # auto|cuda|cpu|hip
EXO_VAD_MULTIPLIER=2.5             # Sensibilité (plus bas = plus sensible)
```

### TTS

```env
TTS_ENGINE=kokoro                   # kokoro|piper|openai|fish|coqui
KOKORO_VOICE=ff_siwis               # ff_siwis|ff_alma|fm_music
KOKORO_LANG=f                       # f=français|e=english|j=japanese
KOKORO_ENABLED=true
PIPER_MODEL=models/piper/fr_FR-siwis-medium.onnx
PIPER_ENABLED=true
FISH_SPEECH_URL=http://localhost:8000
TTS_FALLBACK=true
TTS_TIMEOUT=30
TTS_RETRIES=2
```

### Musique / GUI / Wyoming / Logging

```env
# Musique
MOPIDY_URL=http://localhost:6680
TIDAL_QUALITY=LOSSLESS              # LOSSLESS|HI_RES|MASTER|NORMAL

# GUI
GUI_WIDTH=800
GUI_HEIGHT=600
GUI_FPS=144
ENABLE_PYGAME=true

# Wyoming (multi-room)
WYOMING_HOST=0.0.0.0
WYOMING_PORT=10700

# Logging
LOG_LEVEL=INFO                      # DEBUG|INFO|WARNING|ERROR
DEBUG=false
MOCK_HA=false
```

### Sécurité

- Ne **jamais** committer `.env` dans Git
- Ne **jamais** exposer les clés API publiquement
- Token HA = permissions minimales nécessaires

---

## 🛠️ Tests

```bash
# Diagnostic micro + VAD + STT en temps réel
python examples/test_pipeline_monitor.py --rounds 5

# Test E2E complet (micro → Brain → TTS → playback)
python examples/test_e2e_vocal.py

# Test BrainEngine seul (LLM + RAG, sans micro)
python examples/test_conversation.py
```

---

## 📦 Installation & Déploiement

Guide complet (PC, Raspberry Pi, Docker, troubleshooting) : **[SETUP.md](SETUP.md)**

```bash
# PC — Lancer
python main.py

# Raspberry Pi satellite
python examples/pi_satellite.py --server 192.168.1.50 --port 10700

# Docker
docker-compose up -d
```

---

## 📜 Licence

Projet privé. Usage personnel uniquement.
