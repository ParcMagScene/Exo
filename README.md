# 🤖 Assistant Personnel Haut de Gamme

Assistant IA distribué multi-room pour domotique intégrée. Architecture modulaire asynchrone optimisée pour latence ultra-faible (<500ms).

## 🏗️ Architecture Distribuée

### Matériel
- **Serveur Central** : PC Windows/Linux (Intel Core i9, RAM 48Go, GPU AMD RX 6750 XT)
- **Satellites Audio** : 
  - Raspberry Pi Zero 2 W (STT via Whisper)
  - Raspberry Pi 5 (STT + GUI Media offscreen)
- **Domotique** : Home Assistant (HUE, IKEA, Samsung, EZWIZ, Petkit)

### Structure du Projet

```
.
├── src/
│   ├── core/
│   │   └── core.py                 # Orchestrateur principal (machine d'états)
│   ├── brain/
│   │   └── brain_engine.py          # LLM (GPT-4o) + RAG (ChromaDB) + Tools
│   ├── hardware/
│   │   └── hardware_accel.py        # STT/TTS (OpenVINO optimisé)
│   ├── integrations/
│   │   └── home_bridge.py           # Home Assistant WebSocket + REST
│   ├── gui/
│   │   └── visage_gui.py            # Interface Pygame 144Hz (avatar expressif)
│   └── protocols/
│       └── wyoming.py               # Serveur Wyoming (audio multi-room)
├── data/
│   └── chroma/                      # Base vectorielle ChromaDB
├── config/                          # Fichiers configuration
├── main.py                          # Point d'entrée application
├── requirements.txt                 # Dépendances Python
├── .env.example                     # Variables d'environnement (à copier en .env)
└── README.md                        # Ce fichier
```

## 🔧 Installation

### Prérequis
- Python 3.11+
- pip ou conda
- (Optionnel) CUDA toolkit pour GPU NVIDIA

### Étapes

1. **Cloner/Copier le projet**
```bash
cd d:/Exo
```

2. **Créer un environnement virtuel** (recommandé)
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

4. **Configurer les variables d'environnement**
```bash
# Copier .env.example en .env
cp .env.example .env
# Ou sur Windows:
copy .env.example .env

# Éditer .env avec vos clés API
# Requis:
# - AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_KEY
# - HA_URL + HA_TOKEN
```

## 🚀 Démarrage

```bash
python main.py
```

## 📋 Flux de Fonctionnement

### 1️⃣ Réception Audio (Wyoming Protocol)
```
Pi Zero / Pi 5 → Wyoming Server (10700) → Core
```

### 2️⃣ Traitement Audio → Texte
```
Core → Hardware Accel (STT) → Whisper + OpenVINO
```

### 3️⃣ Enrichissement Contexte
```
Brain Engine → ChromaDB (animaux, plan maison, prefs)
```

### 4️⃣ Appel GPT-4o
```
Brain Engine → Azure OpenAI (GPT-4o avec Function Calling)
```

### 5️⃣ Exécution des Actions
```
Function Calls → Home Bridge → Home Assistant WebSocket
                             → Contrôle lumières, TV, caméras, Petkit
```

### 6️⃣ Génération Réponse Audio
```
Brain Engine → Hardware Accel (TTS) → Fish-Speech / XTTS v2
```

### 7️⃣ Affichage et Feedback
```
Core → Face GUI (Pygame 144Hz) → Avatar expressif
```

## 🧠 Modules Clés

### `core.py` - Orchestrateur Principal
- Machine d'états : IDLE → LISTENING → PROCESSING → RESPONDING
- Gestion priorité audio multi-room
- Identification pièce source
- Coordination tous modules

### `brain_engine.py` - Cerveau IA
- Appels GPT-4o (Azure SDK + fallback REST)
- Injection contexte ChromaDB
- **Function Calling** :
  - `control_light` : HUE/IKEA
  - `control_media` : Samsung TV/Soundbar
  - `play_music` : TIDAL via Mopidy
  - `check_camera` : EZWIZ
  - `check_petkit` : Statut litière
  - `store_memory` : Mise à jour ChromaDB
- Historique conversation (10 derniers messages)

### `hardware_accel.py` - Accélération Matérielle
- **STT** : Faster-Whisper + OpenVINO + multi-threading (8 workers pour i9)
- **TTS** : Fish-Speech REST endpoint
- GPU auto-detection (CUDA / AMD ROCm / CPU)
- Benchmark performance

### `home_bridge.py` - Intégration Domotique
- WebSocket HA (temps réel)
- REST API fallback
- Mapping pièces → entités HA
- Support HUE, IKEA, Samsung, EZWIZ, Petkit

### `visage_gui.py` - Interface 2D
- Rendu Pygame @ 144Hz (fluide i9)
- Avatar minimaliste (cercles + lignes)
- États synchronisés : IDLE / LISTENING / PROCESSING / RESPONDING / ERROR
- Clignotement automatique
- Spectre audio temps réel

### `wyoming.py` - Serveur Audio Distribué
- Protocol Wyoming (JSON + audio brut)
- Multi-client WebSocket
- Identification pièce source
- Fallback texte direct (bypass STT)

## ⚙️ Configuration Variables d'Environnement

Voir `.env.example` pour la liste complète. Minimum requis :

```env
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=sk-...

# Home Assistant
HA_URL=http://homeassistant.local:8123
HA_TOKEN=eyJ0eXAi...

# Optional
LOG_LEVEL=INFO
DEBUG=false
```

## 📊 Performance

### Cibles de Latence
- **STT** : <200ms (Faster-Whisper + GPU)
- **LLM Appeal** : <200ms (GPT-4o)
- **Function Call** : <50ms (HA WebSocket)
- **TTS** : <100ms (Fish-Speech)
- **Total E2E** : <500ms ✅

### Optimisations
- ✅ Asyncio/await (non-blocking I/O)
- ✅ uvloop (meilleure perf que asyncio std)
- ✅ OpenVINO (accélération CPU/GPU)
- ✅ Pygame 144Hz (fluidité max)
- ✅ WebSocket HA (latence ultra-faible vs REST)
- ✅ ChromaDB local (RAG sans réseau)
- ✅ Multi-threading Whisper (exploitation i9)

## 🛠️ Développement

### Ajouter une Nouvelle Action (Function Call)

1. Définir dans `brain.py::_define_tools()` :
```python
{
    "type": "function",
    "function": {
        "name": "my_action",
        "description": "...",
        "parameters": {...}
    }
}
```

2. Implémenter handler dans `brain.py::_execute_functions()` ou `home_bridge.py`

3. Tester avec `curl` (à venir)

### Satellites Raspberry Pi

**Pi Zero 2 W** : Exécute Wyoming client STT
```bash
# Sur le Pi Zero
pip install wyoming-faster-whisper
python -m wyoming_faster_whisper --uri tcp://0.0.0.0:10700 --room pi_zero
```

**Pi 5** : Wyoming client + GUI optionnelle
```bash
# Sur le Pi 5
python -m wyoming_faster_whisper --uri tcp://0.0.0.0:10700 --room pi_5
# Optionnel : afficher la GUI sur Pi 5 (offscreen buffer)
```

## 📝 Logs

Logs écrits dans `assistant.log` + stdout.
```bash
tail -f assistant.log
```

## 🐛 Troubleshooting

### "AZURE_OPENAI_ENDPOINT requis"
→ Vérifier `.env` présent et rempli

### "Connexion HA échouée"
→ Vérifier HA_URL accessible, token valide

### "Whisper pas disponible"
→ Installer : `pip install faster-whisper`

### "Pygame non disponible"
→ Installer : `pip install pygame`

### "GUI lente (<144fps)"
→ Réduire résolution GUI dans `.env`
→ Vérifier GPU accessible

## 📜 Licence

Projet privé. Utilisation personnelle uniquement.

## 🤝 Support

Pour questions/bugs, consulter la documentation Azure OpenAI, Home Assistant, Faster-Whisper.
