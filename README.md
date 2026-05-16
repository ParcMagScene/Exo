# EXO — Assistant vocal local

Pipeline temps réel local-first, LLM externe `claude-opus-4.7` verrouillé.

```text
Micro → RtAudio WASAPI → DSP (noisereduce) → VAD (Silero :8768)
  → WakeWord (OpenWakeWord :8770) → STT (Whisper.cpp small Vulkan :8766)
  → NLU (:8772) → Claude Opus 4.7 (SSE + Function Calling)
  → TTS (Orpheus 3B FR GGUF Q8 CUDA :8767) → TTSManager (C++ DSP) → Speaker
```

| Étape | Technologie | Latence cible |
|-------|-------------|---------------|
| VAD | Silero neural (hybrid) | < 50 ms |
| WakeWord | OpenWakeWord | < 100 ms |
| STT | Whisper.cpp small, Vulkan, beam=1, int8 | < 2 s |
| LLM | Claude Opus 4.7 (SSE) | first token < 500 ms |
| TTS | Orpheus 3B FR GGUF Q8, CUDA, streaming | first chunk < 1.5 s |
| DSP | EQ → Compressor → Normalizer → Fade | < 5 ms |

### État actuel des performances (v28)

Les latences ci‑dessus représentent les objectifs cibles.
Les mesures actuelles observées sur la configuration de développement sont :

- STT Whisper.cpp small Vulkan : ~18 s pour 3.2 s d'audio (optimisation en cours)
- TTS Orpheus 3B FR GGUF Q8 : first chunk ~1.0–1.5 s, RTF ~1.5 (CUDA RTX 3070)

Ces valeurs seront progressivement alignées avec les objectifs (< 2 s STT, < 1.5 s TTS).

---

## Services Python

### Core (7 services)

| Service | Port | Technologie | Rôle |
|---------|------|-------------|------|
| **Orchestrator** | 8765 | Python 3.13 (.venv) | GUI WebSocket, bridge entre tous les services |
| **STT** | 8766 | Whisper.cpp (Vulkan, small, beam=1, int8) | Reconnaissance vocale GPU temps réel |
| **TTS** | 8767 | Orpheus 3B FR GGUF Q8 (CUDA, llama.cpp + SNAC) | Synthèse vocale neurale, streaming PCM16 24 kHz |
| **VAD** | 8768 | Silero VAD | Détection d'activité vocale neurale |
| **WakeWord** | 8770 | OpenWakeWord | Détection du mot-clé « EXO » |
| **Memory** | 8771 | FAISS + SentenceTransformers | Mémoire sémantique vectorielle |
| **NLU** | 8772 | Transformers / regex | Classification d'intention locale |

### Intelligence (8 services)

| Service | Port | Rôle |
|---------|------|------|
| **WebSearch** | 8773 | Recherche web |
| **News** | 8774 | Actualités |
| **Knowledge** | 8775 | Base de connaissances |
| **Tools** | 8776 | Routeur d'outils |
| **Context** | 8777 | Moteur de contexte conversationnel |
| **Planner** | 8778 | Planification de tâches (HTN) |
| **Executor** | 8779 | Exécution de tâches planifiées |
| **Verifier** | 8780 | Vérification post-exécution |

### Outils (3 services)

| Service | Port | Rôle |
|---------|------|------|
| **FileService** | 8781 | Opérations fichiers |
| **Calendar** | 8782 | Agenda / calendrier |
| **System** | 8783 | Infos système |

### Domotique (6 services)

| Service | Port | Rôle |
|---------|------|------|
| **HomeGraph** | 8784 | Graphe des appareils connectés |
| **Domotic** | 8785 | Actions domotiques (Home Assistant) |
| **Camera** | 8786 | Flux caméras IP |
| **Samsung** | 8787 | Samsung SmartThings |
| **Voltalis** | 8788 | Gestion énergie Voltalis |
| **Echo** | 8789 | Amazon Echo / Alexa |

### Réseau (1 service)

| Service | Port | Rôle |
|---------|------|------|
| **NetworkMap** | 8790 | Cartographie réseau (ARP, mDNS, SSDP, ping) |

---

## Moteur C++ / Qt

| Module | Dossier | Rôle |
|--------|---------|------|
| AssistantManager | `app/core/` | Orchestrateur global, FSM |
| VoicePipeline | `app/audio/` | Pipeline audio : capture → DSP → VAD → STT |
| TTSManager | `app/audio/` | Lecture TTS, chaîne DSP (EQ, compressor, normalizer, fade) |
| ClaudeAPI | `app/llm/` | LLM SSE streaming + Function Calling |
| AIMemoryManager | `app/llm/` | Mémoire 3 couches + FAISS |
| ConfigManager | `app/core/` | Configuration 2 couches (env > global) |
| HealthCheck | `app/core/` | Monitoring santé des services WebSocket |
| ServiceManager | `app/core/` | Lancement / arrêt des microservices Python |
| PipelineTracer | `app/core/` | Tracing du pipeline vocal (timestamps) |
| LatencyMetrics | `app/core/` | 9 timestamps, 6 métriques dérivées |
| SecurityManager | `app/core/` | Permissions, masquage API keys, audit |
| TestController | `app/test/` | Contrôleur C++ pour le Stability Test Runner QML |
| FloorPlanController | `app/floorplan/` | Modèle + contrôleur plan d'étage interactif |
| WeatherManager | `app/utils/` | Météo OpenWeatherMap |
| SimulationController | `app/simulation/` | Simulation spatiale avancée (propagation, entités, risques, causalité) |

---

## Modules QML

### Pages principales (10) + Panels avancés

| Page | Fichier | Rôle |
|------|---------|------|
| Accueil | `HomePage.qml` | Dashboard principal, orbe visualizer |
| Maison | `MaisonPage.qml` | Vue domotique / appareils |
| Plan | `FloorPlanPage.qml` | Plan d'étage interactif |
| Réseau | `ReseauPage.qml` | Cartographie réseau |
| Pipeline | `PipelinePage.qml` | Visualisation pipeline vocal temps réel |
| Scénarios | `ScenariosPage.qml` | Scénarios domotiques |
| Historique | `HistoryPage.qml` | Historique des conversations |
| Logs | `LogsPage.qml` | Console de logs temps réel |
| Paramètres | `SettingsPage.qml` | Configuration de l'assistant |
| Simulation | `SimulationPage.qml` | Simulation spatiale avancée |

### Panels avancés

- Chat
- Cognitif
- Heatmap
- Voice Flow
- Mémoire
- Gouvernance
- Observabilité
- Stabilité
- Simulation spatiale

### Composants clés (56)

| Composant | Rôle |
|-----------|------|
| `ExoOrbVisualizer` | Visualizer GPU ShaderEffect GLSL 60 FPS |
| `VoicePipelineView` | Vue Voice Flow — état FSM + latences temps réel |
| `PipelineView` | Vue pipeline détaillée (étapes, timestamps) |
| `ObservabilityDashboard` | Tableau de bord métriques / tracing / santé |
| `GovernancePanel` | Panneau gouvernance (permissions, audit) |
| `StabilityPanel` | Panneau Stability Test Runner (résultats, autoheal) |
| `ExoServiceStatus` | Indicateur santé par service |
| `ExoPipelineStatus` | Status pipeline vocal global |
| `ExoTranscriptView` | Transcription STT temps réel |
| `ExoResponseView` | Réponse LLM streaming |
| `MemoryInspector` | Inspecteur mémoire sémantique |
| `CognitiveTimeline` | Timeline du framework cognitif |
| `EngineHeatmap` | Heatmap des moteurs cognitifs |
| `SimulationScenarioPanel` | Contrôle scénarios simulation spatiale |
| `SimulationOverlay` | Overlay multi-couches propagation |
| `SimulationCausalityGraph` | Graphe de causalité interactif |
| `SimulationRiskPanel` | Panneau risques simulation |
| `SimulationTimeline` | Timeline 5 couches simulation |
| `SimulationMinimap` | Minimap simulation spatiale |
| `AudioWaveformView` | Forme d'onde audio en direct |
| `ExoContextPanel` | Panneau de contexte conversationnel |

---

## Stability Test Runner

Le **Stability Test Runner** (`python/test/exo_test_runner.py`) est un outil de diagnostic qui teste la santé de tous les microservices en boucle.

### Fonctionnalités

- Connexion WebSocket directe à chaque service
- Ping/pong applicatif avec mesure de latence
- Détection des timeouts, déconnexions et flapping
- Boucle de tests configurable (nombre de passes, timeout)
- Mode **autoheal** : redémarrage automatique des services DOWN

### Utilisation

```powershell
# Test simple (10 boucles)
python python/test/exo_test_runner.py --loops 10

# Avec autoheal (détecte les services DOWN et les relance)
python python/test/exo_test_runner.py --autoheal --loops 10 --timeout 5000
```

### Services testés

Services testés automatiquement :
STT, TTS, VAD, WakeWord, Memory, NLU, Context, Planner, NetworkMap, Domotic, HomeGraph (11 services).
Les services Executor et Verifier ne sont pas testés automatiquement (choix volontaire : ils ne sont activés que lors d'une exécution de plan).

### Intégration QML

Le panneau **StabilityPanel** dans l'interface QML affiche les résultats en temps réel via le `TestController` C++.

---

## Framework Cognitif (`exo/`)

Package Python standalone implémentant l'architecture cognitive complète : modulaire, testable, déterministe, explicable, gouverné.

| Composant | Fichiers | Rôle |
|-----------|----------|------|
| Core | 4 | CognitiveKernel, Context, State, Flow |
| Engines | 8 | Règles, causal, inférence, HTN, simulation, optimisation, observabilité, gouvernance |
| Layers | 8 | Perception → Extraction → Symbolic → Inference → Planning → Simulation → Decision → Supervision |
| Pipelines | 3 | Cognitive, Simulation, Planning |
| Agents macro | 5 | Cognition, Simulation, Planning, Observability, Governance |
| Agents micro | 8 | Extraction, vérification, analyse causale, HTN, simulation locale, risque, logique, métriques |
| Governance | 4 | Permissions, validation, compliance, audit |
| Observability | 4 | Télémétrie, tracing, métriques, dashboard |
| Tests | 5 | 117 tests couvrant tous les modules |

---

## Installation

### 1. C++ — Compilation

```powershell
cmake -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="C:\Qt\6.9.3\msvc2022_64"
cmake --build build --config Release
```

### 2. Python — Venv microservices IA

```powershell
python -m venv .venv_stt_tts
.\.venv_stt_tts\Scripts\Activate.ps1
pip install websockets numpy soundfile "transformers>=4.40,<4.50"
pip install "torch==2.4.1" "torchaudio==2.4.1" --index-url https://download.pytorch.org/whl/cu121
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
pip install silero-vad onnxruntime noisereduce openwakeword faiss-cpu sentence-transformers
```

### 3. Python — Venv orchestrator

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4. Variables d'environnement (`.env`)

```ini
CLAUDE_API_KEY=sk-ant-api03-...
OWM_API_KEY=...
HA_URL=http://localhost:8123
HA_TOKEN=votre-token-longue-duree
```

### 5. Modèles & données

Stockés sur `D:\EXO\` :

| Dossier | Contenu |
|---------|---------|
| `D:\EXO\models\whisper` | Modèles Whisper.cpp (ggml-small.bin) |
| `D:\EXO\models\orpheus_fr_gguf` | Modèle Orpheus 3B FR GGUF Q8 + SNAC |
| `D:\EXO\models\wakeword` | Modèles OpenWakeWord |
| `D:\EXO\faiss\semantic_memory` | Index FAISS |
| `D:\EXO\cache\huggingface` | Cache HuggingFace |

---

## Démarrage

### Tout-en-un (recommandé, silencieux)

```powershell
powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "D:\EXO\launch_exo_silent.ps1"
```

Stop / restart / status (dot-source) :

```powershell
. D:\EXO\launch_exo_silent.ps1 ; Stop-EXO   # ou Restart-EXO / Get-EXOStatus
```

Ou via VS Code : `Ctrl+Shift+P` → `Tasks: Run Task` → `launch_all`.

### Lancement manuel (services core)

```powershell
# Orchestrator (port 8765)
.\.venv\Scripts\python.exe python/orchestrator/exo_server.py

# STT Whisper.cpp small Vulkan (port 8766)
.\.venv_stt_tts\Scripts\python.exe python/stt/stt_server.py --backend whispercpp --model small --beam-size 1 --device vulkan --compute-type int8

# TTS Orpheus 3B FR GGUF Q8 (port 8767)
.\services\orpheus\venv\Scripts\python.exe services/orpheus/server_ws.py

# VAD Silero (port 8768)
.\.venv_stt_tts\Scripts\python.exe python/vad/vad_server.py

# WakeWord (port 8770)
.\.venv_stt_tts\Scripts\python.exe python/wakeword/wakeword_server.py

# Mémoire FAISS (port 8771)
.\.venv_stt_tts\Scripts\python.exe python/memory/memory_server.py

# NLU (port 8772)
.\.venv_stt_tts\Scripts\python.exe python/nlu/nlu_server.py

# Context Engine (port 8777)
.\.venv_stt_tts\Scripts\python.exe python/context/context_engine.py

# Task Planner (port 8778)
.\.venv_stt_tts\Scripts\python.exe python/planner/task_planner_server.py

# Task Executor (port 8779)
.\.venv_stt_tts\Scripts\python.exe python/executor/task_executor_server.py

# Task Verifier (port 8780)
.\.venv_stt_tts\Scripts\python.exe python/verifier/task_verifier_server.py

# System Service (port 8783)
.\.venv_stt_tts\Scripts\python.exe python/tools/system_service.py

# GUI C++
build\Release\RaspberryAssistant.exe
```

---

## Configuration

Fichier `config/assistant.conf` — format INI, priorité : **Variables d'environnement > `assistant_local.conf` > `assistant.conf`**

```ini
[Claude]
api_key=${CLAUDE_API_KEY}
model=claude-opus-4.7
; VERROU LLM 2026-05-16 : aucun fallback autorise (claude-opus-4.7 strict, wire-ID claude-opus-4-7)

[STT]
server_url=ws://localhost:8766
backend=whispercpp
model=small
beam_size=1

[TTS]
server_url=ws://localhost:8767
voice=fr_vivienne
language=fr
sample_rate=24000

[VAD]
backend=hybrid
server_url=ws://localhost:8768
threshold=0.45

[WakeWord]
neural_enabled=false
server_url=ws://localhost:8770

[Memory]
semantic_enabled=true
semantic_server_url=ws://localhost:8771

[NLU]
local_enabled=false
server_url=ws://localhost:8772
```

Les 25 services sont définis dans `config/services.json` avec ports, venvs et arguments.

---

## Troubleshooting

| Problème | Solution |
|----------|----------|
| STT lent (> 5 s) | Vérifier `beam_size=1` dans `assistant.conf` et `--device vulkan --compute-type int8` |
| TTS pas de son | Vérifier que le modèle Orpheus est dans `D:\EXO\models\orpheus_fr_gguf` et CUDA disponible (venv `services\orpheus\venv`) |
| Service DOWN | Lancer `python python/test/exo_test_runner.py --autoheal` |
| HealthCheck flapping | `WS_PING_INTERVAL=None` dans `base_service.py` (déjà corrigé) |
| Erreur Vulkan STT | Vérifier `vulkaninfo` et que whisper-server.exe est compilé avec Vulkan |
| Mémoire FAISS vide | Vérifier `EXO_FAISS_DIR=D:\EXO\faiss\semantic_memory` |
| WebSocket timeout | Augmenter `startup_timeout_ms` dans `services.json` |

---

## Arborescence du projet

```
EXO/
├── app/                           C++ — moteur principal
│   ├── main.cpp                    Point d'entrée Qt
│   ├── core/                       AssistantManager, ConfigManager, HealthCheck,
│   │                               ServiceManager, PipelineTracer, LatencyMetrics,
│   │                               LogManager, MetricsManager, TraceManager,
│   │                               ErrorManager, SecurityManager, ContextCache
│   ├── audio/                      VoicePipeline, TTSManager, AudioInput, DSP
│   ├── llm/                        ClaudeAPI, AIMemoryManager
│   ├── floorplan/                   FloorPlanController, Model, Item, Serializer, Enums
│   ├── test/                       TestController (Stability Test Runner QML)
│   ├── utils/                      WeatherManager
│   └── simulation/                 SimulationController, Engine, Entity,
│                                   Scenario, Propagation, Result, Enums
│
├── exo/                           Framework cognitif standalone
│   ├── core/                       CognitiveKernel, Context, State, Flow
│   ├── engines/                    8 moteurs cognitifs
│   ├── layers/                     8 couches de traitement
│   ├── pipelines/                  3 pipelines (Cognitive, Simulation, Planning)
│   ├── agents/                     5 macro + 8 micro agents
│   ├── governance/                 Permissions, Validation, Compliance, Audit
│   ├── observability/              Telemetry, Tracing, Metrics, Dashboard
│   └── tests/                      117 tests
│
├── python/                        25 Microservices Python
│   ├── orchestrator/               exo_server.py (8765)
│   ├── stt/                        stt_server.py + whisper_cpp.py (8766)
│   ├── tts/                        tts_server.py (legacy stub) — serveur actif : services/orpheus/server_ws.py (8767)
│   ├── vad/                        vad_server.py (8768)
│   ├── wakeword/                   wakeword_server.py (8770)
│   ├── memory/                     memory_server.py (8771)
│   ├── nlu/                        nlu_server.py (8772)
│   ├── websearch/                  websearch_server.py (8773)
│   ├── news/                       news_server.py (8774)
│   ├── knowledge/                  knowledge_server.py (8775)
│   ├── tools/                      tools_server, file_service, calendar, system
│   ├── context/                    context_engine.py (8777)
│   ├── planner/                    task_planner_server.py (8778)
│   ├── executor/                   task_executor_server.py (8779)
│   ├── verifier/                   task_verifier_server.py (8780)
│   ├── domotique/                  homegraph, domotic, camera, samsung, voltalis, echo
│   ├── network/                    network_map_service.py (8790)
│   ├── test/                       exo_test_runner.py (Stability Test Runner)
│   └── shared/                     Modules partagés (base_service, cache, etc.)
│
├── qml/                           Interface QML
│   ├── MainWindow.qml              Fenêtre principale
│   ├── pages/                      10 pages (Home, Maison, Pipeline, Réseau, Simulation, etc.)
│   ├── panels/                     Sidebar, HeaderBar, BottomBar, StabilityPanel
│   ├── components/                 34 composants (Visualizer, PipelineView, etc.)
│   ├── cognitive/                  18 panneaux cognitifs (12 originaux + 6 simulation)
│   └── theme/                      Thème VS Code / Fluent Design
│
├── config/                        Configuration
│   ├── assistant.conf              Config INI principale
│   └── services.json               Définition des 25 services (ports, args)
│
├── docs/                          Documentation technique
├── rtaudio/                       RtAudio WASAPI (sous-module)
├── whisper.cpp/                   Whisper.cpp (sous-module)
├── resources/                     Polices, icônes
├── scripts/                       Utilitaires PowerShell
├── tests/                         Tests (2349 pytest + Qt Test)
├── .env                           Clés API (non versionné)
├── requirements.txt               Dépendances Python orchestrator
└── CMakeLists.txt                 Build CMake
```

---

## Roadmap

### ✅ Réalisé (v28)
- **Orpheus 3B FR GGUF Q8** — TTS neural streaming CUDA (llama.cpp + SNAC), moteur unique (politique 2026-05-03)
- **STT beam=1** — Whisper.cpp small, Vulkan GPU, int8, greedy decoding (~60 % plus rapide)
- **25 microservices Python** — architecture complète (core, intelligence, outils, domotique, réseau)
- **Stability Test Runner** — diagnostic + autoheal automatique des services
- **Domotique étendue** — HomeGraph, Samsung SmartThings, Voltalis, Echo, caméras IP
- **NetworkMap** — cartographie réseau (ARP, mDNS, SSDP, ping, classification)
- RtAudio WASAPI — capture audio faible latence
- Interface QML 10 pages + 56 composants style VS Code / Fluent Design
- **Simulation spatiale avancée** — module C++ complet (propagation 2D, entités, risques, graphe causal) + 7 panneaux QML + 50 tests unitaires
- Pipeline vocal VoicePipeline v4 (FSM, VAD, StreamingSTT)
- Claude API SSE streaming + Function Calling
- Mémoire 3 couches + FAISS vectoriel
- Silero VAD + OpenWakeWord neural
- DSP noisereduce spectral + chaîne audio complète
- NLU local (classification d'intention)
- Visualizer GPU ShaderEffect GLSL 60 FPS
- ContextCache, LatencyMetrics, warmup/keepalive ClaudeAPI
- Observabilité complète (logging structuré, métriques, tracing distribué)
- Résilience (retry, timeout, fallback, circuit breaker)
- Sécurité (permissions, audit log)
- Framework cognitif standalone (`exo/`) — 8 moteurs, 8 couches, 3 pipelines, 13 agents
- **2349 tests automatisés** (2224 Python + 117 cognitif + 8 C++)

### 🔄 À venir
- Streaming musical — Spotify / Tidal
- Déploiement Raspberry Pi 5
- Interface mobile companion
- Docker — déploiement containerisé

---

## Contribuer

1. Fork le repo
2. Créer une branche (`git checkout -b feature/ma-fonctionnalite`)
3. Lancer les tests : `ctest --test-dir build` + `pytest tests/python/`
4. Commit (`git commit -m "feat: description"`)
5. Push + Pull Request

### Conventions
- **C++** : C++17, Qt 6.9.3, nommage Qt (`camelCase`, `m_` pour membres)
- **Python** : PEP 8, asyncio, websockets
- **QML** : Design system EXO (voir `docs/`)
- **Commits** : format conventionnel (`feat:`, `fix:`, `docs:`, `refactor:`)

---

## Licence

Ce projet est sous licence **MIT**. Voir [LICENSE](LICENSE) pour les détails.

---

**EXO** — C++ / Qt 6.9.3 · Python 3.13 · Orpheus 3B FR GGUF Q8 · Whisper.cpp (Vulkan GPU) · FAISS · Silero · OpenWakeWord · Framework Cognitif