# 🏗️ Architecture Détaillée de l'Assistant Personnel

## Vue d'ensemble

**Assistant distribué multi-room** conçu pour latence ultra-faible (<500ms) et haute performance sur mini-ordinateurs (Raspberry Pi) et PC.

```
┌──────────────────────────────────────────────────────────────┐
│                    SERVEUR CENTRAL (PC)                      │
│                 Intel i9 + GPU AMD RX 6750                   │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              CORE (core.py)                              │ │
│  │  Machine d'états: IDLE→LISTENING→PROCESSING→RESPONDING  │ │
│  └─────────────────────────────────────────────────────────┘ │
│              ▲              ▲              ▲                   │
│              │              │              │                   │
│    ┌─────────▼──┐  ┌───────▼────┐  ┌──────▼──────┐           │
│    │   WYOMING  │  │   BRAIN    │  │     HOME    │           │
│    │   (audio)  │  │   (LLM)    │  │   BRIDGE    │           │
│    └────────────┘  └────────────┘  └─────────────┘           │
│         │                 │                │                  │
│         ├─────────┬───────┼───────┬───────┤                  │
│         │         │       │       │       │                  │
│    ┌────▼──┐ ┌────▼──┐ ┌──▼──┐ ┌──▼──┐ ┌──▼──┐            │
│    │HARDWARE│ │MEMORY │ │  GUI  │ │  HA │ │MUSIC│            │
│    │ ACCEL  │ │(CHROMA)│ │(PYGAME)│ │(WS)│ │(MPD)│           │
│    └────────┘ └────────┘ └───────┘ └─────┘ └─────┘           │
│                                                               │
└──────────────────────────────────────────────────────────────┘
         ▲                                  │
         │                                  │
         │ Wyoming Protocol                 │
         │ (WebSocket + Audio)              │
         │                                  │
    ┌────┴──────┐                  ┌───────▼────────┐
    │ Pi Zero 2W │                  │ Home Assistant │
    │    (STT)   │                  │  + Domotique   │
    └────────────┘                  └────────────────┘
         │
         │ Wyoming +
         │ PyAudio
         │
    ┌────▼──────┐
    │   Pi 5     │
    │(STT + GUI?)│
    └────────────┘
```

## 📋 Flux de Données

### 1️⃣ Réception Audio (Wyoming Protocol)

```
Pi Zero / Pi 5 
    │ PyAudio capture
    ▼
Wyoming JSON + PCM16 audio
    │ ws://SERVER:10700
    ▼
WyomingServer.receive_audio()
    │ Valide format + Identifie pièce
    ▼
Core._on_audio_frame() 
    │ PriorityQueue
    ▼
Audio traité selon pièce source
```

### 2️⃣ Traitement STT → Texte

```
AudioFrame (PCM16)
    ▼
HardwareAccelerator.transcribe_audio()
    │ Exécutif dans executor (non-blocking)
    ├─ Faster-Whisper
    ├─ OpenVINO optimisé
    └─ Multi-threaded (8 workers sur i9)
    ▼
String texte (français)
    ▼
Core.active_sessions[session_id] = CommandContext
```

### 3️⃣ Enrichissement Contexte RAG

```
User Input: "Allume la lumière du salon à 50%"
    ▼
BrainEngine.process_command()
    │
    ├─ ChromaDB.animals.query()
    │  → "Felix est un chat noir, aime les zones chaudes"
    │
    ├─ ChromaDB.house.query()
    │  → "Salon: 6 lumières Philips Hue en réseau"
    │
    └─ ChromaDB.preferences.query()
       → "Préfère lumière chaude le soir (2700K)"
    ▼
Contexte injecté dans prompt système
```

### 4️⃣ Appel GPT-4o avec Function Calling

```
Prompt complet (système + contexte + user input)
    │ Temperature=0.7, Max_tokens=1000
    ▼
Azure OpenAI (SDK async ou REST fallback)
    │ Timeout: 10s
    ▼
Choice[0].message.content + tool_calls
    ├─ Text: "D'accord, je vais allumer..."
    └─ Function Calls:
       ├─ control_light(action=on, room=salon, brightness=50)
       └─ store_memory(category=preference, "Aime 50% au salon")
```

### 5️⃣ Exécution des Actions

```
Function Calls:
    ├─ control_light → HomeBridge.call_service("light", "turn_on", {...})
    │                    → Home Assistant WebSocket
    │                    → Philips Hue API
    │
    ├─ control_media → HA media_player service
    │
    ├─ play_music → Mopidy TIDAL API
    │
    ├─ check_petkit → HA sensor query
    │
    └─ store_memory → ChromaDB.add_document()
```

### 6️⃣ Génération Réponse TTS

```
Response text: "Lumière du salon allumée à 50%"
    ▼
TTSClient.speak()
    │ Kokoro TTS local (24kHz, ff_siwis)
    │ Fallback: Piper → OpenAI → Fish-Speech → Coqui
    ▼
Audio WAV bytes
    ▼
Play on system speakers
```

### 7️⃣ Affichage & Feedback

```
State transitions:
    IDLE → LISTENING (reçoit audio)
         → PROCESSING (LLM en cours)
         → RESPONDING (TTS joue)
         → IDLE
    ▼
FaceGUI.render_loop() @ 144Hz
    ├─ Avatar yeux changent couleur selon état
    ├─ Spectre audio en temps réel
    └─ Clignotement naturel
```

## 🎯 Cibles de Latence

| Composant | Latence typique | Status |
|-----------|----------------|--------|
| Capture VAD | 0.5-1s | ✅ |
| STT (Whisper base) | 0.5-1.5s | ✅ |
| RAG (ChromaDB) | <50ms | ✅ |
| LLM (GPT-4o-mini) | 0.5-1.5s | ✅ |
| Function Call (HA) | <50ms | ✅ |
| TTS (Kokoro) | ~0.8s | ✅ |
| **TOTAL E2E** | **~2-4s** | ✅ |

### Optimisations Appliquées

- **Asyncio/await** : Pas de blocage I/O
- **uvloop** : 2-4x plus rapide que asyncio std
- **Whisper beam_size=1** : Greedy decode rapide
- **Parallel RAG + Local** : Context fetch en asyncio.gather()
- **WebSocket HA** : Latence ultra-faible vs REST
- **ChromaDB local** : RAG sans réseau
- **Cache GPU** : Gardien modèles LLM chargés
- **Pygame 144Hz** : Rendu fluide i9

## 🔌 Interfaces

### 1. Wyoming Protocol

**Port**: 10700 (WebSocket)

**Format message** :
```json
{
  "event": "audio|recognize|audio-start|audio-stop",
  "room": "pi_zero|pi_5",
  "session_id": "unique-id",
  "timestamp": 0,
  "format": "pcm16",
  "rate": 16000,
  "channels": 1
}
[\x00][Binary Audio Data]
```

### 2. Home Assistant WebSocket

**Port**: 8123 (WS)

**Flow**:
1. Connect → auth_required
2. Send auth + token
3. Receive auth_ok
4. Call services via `call_service` message

### 5. Kokoro TTS (Local)

**Moteur** : Kokoro 0.9.4 — synthèse neurale locale

**Config** : voix `ff_siwis`, langue `f` (français), 24kHz

**Cascade** : Kokoro → Piper → OpenAI → Fish-Speech → Coqui

## 🗃️ Données ChromaDB

### Collections

**animals** (informations animaux)
- Doc: "Felix est un chat noir, aime les zones chaudes"
- Métadonnées: id, timestamp

**house_plan** (architecture maison)
- Doc: "Salon: 3 HUE, 1 IKEA, TV Samsung, caméra EZWIZ"
- Doc: "Chambre: 2 HUE connectées"

**user_preferences** (préférences perso)
- Doc: "Lumière chaude le soir (2700K), forte le jour (4000K)"
- Doc: "Musique préférée: Indie, Jazz au réveil"

## 🔐 Sécurité

- **Azure OpenAI Key** : Variables d'env (jamais hardcoded)
- **HA Token** : Long-lived access token HA
- **WebSocket auth** : Token Bearer sur HA
- **No plaintext** : Tout HTTPS/WSS en prod

## 📊 Monitoring

### Logs

Fichier: `assistant.log` (rotate daily)
```
2024-02-14 10:30:45 [INFO] core - ▶️ Démarrage...
2024-02-14 10:30:46 [DEBUG] hardware - ⏱️ transcribe_audio pris 150.2ms
2024-02-14 10:30:47 [INFO] brain - 🧠 Traitement: 'allume salon'
```

### Metrics

Stats collectées dans `AssistantCore.stats`:
- `total_commands` : nombre demandes traitées
- `avg_latency` : moyenne latence E2E
- `errors` : nombre erreurs

## 🛼 Déploiement

### Sur Serveur Central

```bash
python main.py
```

### Sur Satellites (Pi Zero / Pi 5)

```bash
# Installation
pip install faster-whisper wyoming-faster-whisper pyaudio

# Exécution
python examples/pi_satellite.py \
  --server-url ws://192.168.1.100:10700 \
  --room pi_zero
```

## 🔄 État Machine

```
    ┌────────────────────────┐
    │       IDLE             │
    │  (Welcome aux commandes)│
    └────┬───────────────────┘
         │ Audio reçu
         ▼
    ┌────────────────────────┐
    │     LISTENING          │
    │  (Capture audio)       │
    └────┬───────────────────┘
         │ Audio complet
         ▼
    ┌────────────────────────┐
    │    PROCESSING          │
    │  (STT + LLM + Actions) │
    └────┬───────────────────┘
         │ Réponse générée
         ▼
    ┌────────────────────────┐
    │    RESPONDING          │
    │  (TTS play)            │
    └────┬───────────────────┘
         │ Audio complété
         ▼
    ┌────────────────────────┐
    │    IDLE (retour)       │
    └────────────────────────┘
```

## 🚀 Évolutions Futures

- [ ] WebRTC pour audio temps réel (latence <100ms)
- [ ] Multi-user simultané avec queuing
- [ ] TTS générative (Voice Cloning)
- [ ] Vision (caméras EZWIZ) + multimodal understanding
- [ ] Offline-first mode (local LLM fallback)
- [ ] Mobile app pour contrôle intuitif
