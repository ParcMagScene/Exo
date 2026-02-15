# 🤖 EXO — Assistant Vocal Personnel

Assistant IA vocal avec wake word, domotique intégrée et architecture distribuée multi-room.

**Stack** : Faster-Whisper (STT) → GPT-4o-mini (LLM) → Kokoro TTS (voix) → Pygame (playback)

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

## 🏗️ Architecture

```
Micro (PyAudio) → VAD adaptatif → Faster-Whisper STT
    → Wake word "Exo" → BrainEngine (GPT-4o-mini + RAG ChromaDB)
    → Kokoro TTS (24kHz) → Pygame playback
```

### Matériel
- **Serveur** : PC Windows/Linux (CPU suffisant, GPU optionnel)
- **Satellites** : Raspberry Pi Zero 2 W / Pi 5 (via Wyoming protocol)
- **Domotique** : Home Assistant (HUE, IKEA, Samsung, EZWIZ, Petkit)

### Structure

```
src/
├── core/
│   ├── core.py              # Orchestrateur (machine d'états)
│   └── listener.py          # Boucle d'écoute permanente (cœur d'EXO)
├── audio/
│   └── wake_word.py         # VAD adaptatif + détection wake word
├── brain/
│   ├── brain_engine.py      # LLM (GPT-4o-mini) + RAG + Function Calling
│   └── local_info.py        # Contexte temps réel (heure, météo)
├── assistant/
│   └── tts_client.py        # TTS : Kokoro → Piper → OpenAI (cascade)
├── integrations/
│   └── home_bridge.py       # Home Assistant WebSocket + REST
├── gui/
│   └── visage_gui.py        # Avatar Pygame (états synchronisés)
└── protocols/
    └── wyoming.py           # Serveur audio distribué multi-room
examples/
├── test_pipeline_monitor.py # Diagnostic micro/VAD/STT en temps réel
├── test_e2e_vocal.py        # Test E2E complet (micro → voix)
├── test_conversation.py     # Test BrainEngine isolé
└── pi_satellite.py          # Client Wyoming pour Raspberry Pi
```

## 🔧 Configuration

### Variables d'environnement (.env)

```env
# ── LLM (requis — au moins un) ──
OPENAI_API_KEY=sk-...                # OpenAI standard (GPT-4o-mini)
# ou Azure :
# AZURE_OPENAI_ENDPOINT=https://...
# AZURE_OPENAI_KEY=...

# ── Domotique (optionnel) ──
HA_URL=http://homeassistant.local:8123
HA_TOKEN=eyJ0eXAi...

# ── TTS ──
TTS_ENGINE=kokoro              # kokoro|piper|openai|fish|coqui
KOKORO_VOICE=ff_siwis          # ff_siwis, ff_alma, fm_music

# ── STT ──
WHISPER_MODEL=base             # tiny|base|small|medium|large

# ── VAD ──
EXO_VAD_MULTIPLIER=2.5        # Sensibilité micro (plus bas = plus sensible)
```

Référence complète : [ENV_REFERENCE.md](ENV_REFERENCE.md)

## 🧠 Modules Clés

| Module | Rôle |
|--------|------|
| `listener.py` | Boucle d'écoute permanente : micro → VAD → Whisper → wake word → Brain → TTS → playback |
| `wake_word.py` | VAD par RMS avec seuil adaptatif, calibration bruit ambiant au démarrage |
| `brain_engine.py` | GPT-4o-mini + RAG ChromaDB (3 collections) + Function Calling domotique |
| `tts_client.py` | Cascade TTS : Kokoro (local, 24kHz) → Piper → OpenAI → Fish-Speech → Coqui |
| `home_bridge.py` | Intégration Home Assistant (WebSocket temps réel + REST fallback) |

## 📊 Pipeline & Latence

| Étape | Durée typique |
|-------|---------------|
| Capture VAD | ~0.5-1s (durée parole + 0.5s silence) |
| Whisper STT (base) | ~0.5-1s |
| Brain GPT-4o-mini | ~0.5-1.5s |
| Kokoro TTS | ~0.8s |
| **Total E2E** | **~2-4s** |

Diagnostic en temps réel : `python examples/test_pipeline_monitor.py`

## 🛠️ Tests

```bash
# Diagnostic micro + VAD + STT
python examples/test_pipeline_monitor.py --rounds 5

# Test E2E complet (micro → Brain → TTS → playback)
python examples/test_e2e_vocal.py

# Test BrainEngine seul (LLM + RAG)
python examples/test_conversation.py
```

## 🐳 Docker

```bash
docker-compose up -d
```

Guide détaillé : [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)

## 📡 Raspberry Pi (satellites)

```bash
# Sur le Pi
python examples/pi_satellite.py
```

Guide : [PI_SETUP.md](PI_SETUP.md)

## 📝 Documentation

| Document | Contenu |
|----------|---------|
| [SETUP.md](SETUP.md) | Installation détaillée (PC + Pi + domotique) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Architecture technique complète |
| [ENV_REFERENCE.md](ENV_REFERENCE.md) | Toutes les variables d'environnement |
| [VOICE_INTEGRATION.md](VOICE_INTEGRATION.md) | Pipeline vocal détaillé |
| [PI_SETUP.md](PI_SETUP.md) | Déploiement Raspberry Pi |
| [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md) | Déploiement Docker |

## 📜 Licence

Projet privé. Usage personnel uniquement.
