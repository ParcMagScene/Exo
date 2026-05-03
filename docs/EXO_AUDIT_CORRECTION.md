
0$# EXO — Audit Complet & Plan de Correction

**Date :** 18 avril 2026  
**Périmètre :** `D:\EXO\` — Application complète (C++, Python, QML, services, modèles, runtime, conf$
55555555556
------------------*Version :** 30.0.0 (CMakeLists.txt)

---

## Table des matières

1. [Résumé exécutif](#1-résumé-exécutif)
2. [Analyse architecture](#2-analyse-architecture)
3. [Analyse chemins & structure disque](#3-analyse-chemins--structure-disque)
4. [Analyse services Python](#4-analyse-services-python)
5. [Analyse C++ / CMake](#5-analyse-c--cmake)
6. [Analyse QML / UI](#6-analyse-qml--ui)
7. [Analyse modèles & runtime](#7-analyse-modèles--runtime)
8. [Analyse performance & latence](#8-analyse-performance--latence)
9. [Analyse stabilité & Safe Boot](#9-analyse-stabilité--safe-boot)
10. [Analyse logs & observabilité](#10-analyse-logs--observabilité)
11. [Analyse dette technique](#11-analyse-dette-technique)
12. [Analyse VS Code / DX](#12-analyse-vs-code--dx)
13. [Plan de correction hiérarchisé](#13-plan-de-correction-hiérarchisé)
14. [Liste des fichiers à modifier](#14-liste-des-fichiers-à-modifier)
15. [Liste des chemins à corriger](#15-liste-des-chemins-à-corriger)
16. [Risques résiduels](#16-risques-résiduels)

---

## 1. Résumé exécutif

### Les 10 problèmes les plus graves

| # | Sévérité | Problème | Impact | Fichier(s) principal(aux) |
|---|----------|----------|--------|---------------------------|
| 1 | 🔴 CRITIQUE | `eval()` dans `tools_server.py` avec sandbox contournable | **Exécution de code arbitraire** — un client WebSocket malveillant peut exécuter du code Python sur le serveur | `python/tools/tools_server.py:106` |
| 2 | 🔴 CRITIQUE | `vector_index.py` et `config_manager.py` sans verrou de concurrence | **Corruption de données** — FAISS et config lues/écrites simultanément sans synchronisation | `python/memory/vector_index.py`, `python/shared/config_manager.py` |
| 3 | 🔴 CRITIQUE | `WebSocketClient` C++ : double ownership du `QWebSocket` | **Use-after-free / crash** — le destructeur fait `abort(); delete m_ws` tandis que des slots peuvent encore être en vol | `app/core/WebSocketClient.cpp` |
| 4 | 🔴 CRITIQUE | `TTSBackendXTTS.cpp` : 6 busy-wait `processEvents` | **Gel de la GUI** — boucles de spin qui bloquent le thread principal pendant 0–6 secondes à chaque synthèse TTS | `app/audio/TTSBackendXTTS.cpp:131-254` |
| 5 | 🔴 CRITIQUE | `LogManager.cpp` C++ : aucune rotation de logs | **Saturation disque** — `exo.log` croît indéfiniment (~6 Mo par session, aucune limite) | `app/core/LogManager.cpp:230` |
| 6 | 🔴 HAUTE | `str(e)` envoyé aux clients WebSocket (20+ occurrences) | **Fuite d'information** — chemins internes, noms de classes, stack traces partiels exposés aux clients | 20+ fichiers Python |
| 7 | 🔴 HAUTE | Ping/pong WebSocket désactivé globalement | **Connexions zombies** — les clients morts ne sont jamais détectés, consomment des ressources indéfiniment | `python/shared/base_service.py:47-48` |
| 8 | 🔴 HAUTE | `python/orchestrator/` : ~140 fichiers, sprawl de versions v8→v25 | **Dette technique critique** — temps d'import excessif, confusion, ~50% probablement mort | `python/orchestrator/` |
| 9 | 🟠 MOYENNE | `MetricsManager` et `TraceManager` C++ compilés mais jamais utilisés | **Observabilité morte** — l'infrastructure d'instrumentation existe mais n'est pas branchée | `app/core/MetricsManager.cpp`, `app/core/TraceManager.cpp` |
| 10 | 🟠 MOYENNE | `tasks.json` : variables d'environnement dupliquées 8× | **Risque de désynchronisation** — une variable oubliée dans une tâche cause un bug difficile à tracer | `.vscode/tasks.json` |

---

## 2. Analyse architecture

### 2.1 Cartographie des modules

```
D:\EXO\
├── project/                          ← Workspace principal
│   ├── app/                          ← Frontend C++ Qt 6.9 / QML (~170 fichiers)
│   │   ├── core/           (37)      Service supervision, config, WS, health, security
│   │   ├── audio/          (16)      VoicePipeline, STT/TTS backends, audio I/O
│   │   ├── llm/            (4)       ClaudeAPI, AIMemoryManager
│   │   ├── safeboot/       (7)       SafeBoot controller + auto-repair
│   │   ├── floorplan/      (9)       Plan de maison interactif
│   │   ├── simulation/     (13)      Simulation de scénarios
│   │   ├── spatialcognition/(15)     Raisonnement spatial
│   │   ├── spatialsecurity/(17)      Détection intrusion/feu/risques
│   │   ├── vision/         (15)      Caméras + analyse visuelle
│   │   └── utils/          (2)       WeatherManager
│   ├── python/                       ← Backend microservices (25 services)
│   │   ├── orchestrator/   (~140)    ⚠️ Orchestrateur principal (MASSIF)
│   │   ├── shared/         (12)      Base service, config, logs, security
│   │   ├── stt/            (5)       Whisper.cpp + Faster-Whisper
│   │   ├── tts/            (4)       CosyVoice2 engine
│   │   ├── vad/            (2)       VAD hybride (builtin + Silero)
│   │   ├── wakeword/       (2)       OpenWakeWord (hey_jarvis)
│   │   ├── memory/         (10)      FAISS sémantique + conversation
│   │   ├── nlu/            (2)       NLU regex (modèle local désactivé)
│   │   ├── domotique/      (12)      HA, Samsung, Voltalis, Echo, Caméra
│   │   ├── network/        (11)      Scan réseau (ARP, mDNS, SSDP)
│   │   ├── tools/          (6)       Calendar, Files, System
│   │   ├── context/        (2)       Moteur de contexte
│   │   ├── planner/        (2)       Planificateur de tâches
│   │   ├── executor/       (2)       Exécuteur de tâches
│   │   ├── verifier/       (2)       Vérificateur de tâches
│   │   ├── knowledge/      (2)       Base de connaissances
│   │   ├── websearch/      (2)       DuckDuckGo
│   │   └── news/           (2)       Flux RSS
│   ├── qml/                          ← Interface utilisateur Qt Quick
│   │   ├── pages/          (10)      Pages principales
│   │   ├── components/     (37)      Composants réutilisables
│   │   ├── cognitive/      (43)      Panels cognitifs/sécurité/vision
│   │   ├── panels/         (5)       Sidebar, Header, Bottom, SafeBoot, Stability
│   │   ├── navigation/     (1)       MenuStructure singleton
│   │   ├── theme/          (1)       Theme singleton
│   │   └── icons/          (19)      SVG
│   ├── config/                       ← Configuration
│   │   ├── assistant.conf            INI principal
│   │   └── services.json             Registre des 25 services (port, venv, criticité)
│   ├── scripts/            (17)      Maintenance, benchmark, install, hooks
│   ├── tests/                        ← Tests
│   │   ├── python/         (51)      Tests unitaires Python
│   │   ├── cpp/            (10)      Tests unitaires C++ (CTest)
│   │   ├── integration/    (1)       Pipeline integration
│   │   └── performance/    (1)       Performance
│   └── build/                        ← Build MSVC Release
├── CosyVoice/                        ← Clone GitHub FunAudioLLM/CosyVoice
├── models/
│   ├── CosyVoice2-0.5B/             Modèle TTS (~1.5 Go)
│   ├── whisper/                      Modèles ggml (small, medium, large-v3)
│   ├── wakeword/                     9 modèles ONNX
│   ├── xtts/                         ⚠️ Legacy XTTS v2 (~500 Mo dead weight)
│   └── huggingface/                  Cache sentence-transformers
├── whispercpp/                       ← Clone whisper.cpp + build Vulkan
├── faiss/
│   └── semantic_memory/              Index FAISS + métadonnées
├── cache/
│   └── huggingface/                  Cache HuggingFace Hub
├── files/                            ← Stockage fichiers utilisateur (vide)
└── logs/                             ← ~80 fichiers log
```

### 2.2 Flux de données principal

```
Micro → AudioInputRtAudio (16kHz PCM16) → AudioPreprocessor (HP 80Hz + AGC + NoiseGate)
  → VAD (ws://localhost:8768, hybrid: 0.3×builtin + 0.7×silero)
  → STT (ws://localhost:8766, whisper.cpp small Vulkan int8)
  → WakeWord (ws://localhost:8770, hey_jarvis ONNX, détection dans transcript)
  → Orchestrator (ws://localhost:8765) → Claude API (claude-sonnet-4-20250514)
  → TTS (ws://localhost:8767, CosyVoice2, CUDA RTX 3070)
  → Audio Output (24kHz PCM16)
```

### 2.3 Dépendances & couplages

| Zone | Couplage | Risque |
|------|----------|--------|
| `AssistantManager` ↔ tout | **Hub central** — connecte ~25 WebSockets, pipeline audio, Claude API, GUI | Fichier God Object (~2000 lignes), point unique de défaillance |
| `ServiceSupervisor` ↔ `ServiceRegistry` | Fort, mais bien structuré | OK — séparation état/logique |
| `python/orchestrator/` ↔ v8-v25 | **Couplage chaotique** — ~150 imports inconditionnels au démarrage | Temps de démarrage, circular imports |
| `VoicePipeline` ↔ 4 serveurs WS | Couplage réseau, pas de fallback si un serveur tombe | Pipeline entier bloqué si VAD ou STT down |
| `CosyVoice2` ↔ `sys.path` hack | `sys.path.insert` au runtime pour injecter le repo CosyVoice | Collision de noms de modules possible |

### 2.4 Zones fragiles identifiées

1. **AssistantManager** : God Object, ~25 connexions WS, pas de circuit breaker
2. **python/orchestrator/** : 140 fichiers, version sprawl, imports massifs
3. **VoicePipeline** : Aucun fallback si un serveur audio est down
4. **WebSocketClient C++** : Gestion de vie objet non fiable (double ownership)
5. **TTSBackendXTTS** : Busy-wait bloquant le thread GUI

---

## 3. Analyse chemins & structure disque

### 3.1 Chemins attendus — Vérification

| Chemin attendu | Existe | Contenu vérifié |
|----------------|--------|-----------------|
| `D:/EXO/project` | ✅ | Workspace principal complet |
| `D:/EXO/CosyVoice` | ✅ | Clone GitHub avec `cosyvoice/`, `runtime/`, `tools/` |
| `D:/EXO/models/whisper` | ✅ | `ggml-small.bin`, `ggml-medium.bin`, `ggml-large-v3.bin` |
| `D:/EXO/models/wakeword` | ✅ | 9 modèles ONNX dont `hey_jarvis_v0.1.onnx`, `silero_vad.onnx` |
| `D:/EXO/faiss/semantic_memory` | ✅ | `embeddings.faiss`, `metadata.json`, `metadata_v2.json`, `metadata_v8.json` |
| `D:/EXO/whispercpp` | ✅ | Source + `build_vk/bin/Release/whisper-server.exe` |
| `D:/EXO/cache` | ✅ | `huggingface/`, `version.txt` |
| `D:/EXO/files` | ✅ | Vide (répertoire de stockage prêt) |

### 3.2 Chemins incorrects / risques

#### Références à `C:\`

| Fichier | Ligne | Chemin | Sévérité | Correction |
|---------|-------|--------|----------|------------|
| `launch_exo.ps1` | 65 | `C:\Qt\6.9.3\msvc2022_64\bin` | ✅ CORRIGÉ | Le script privilégie désormais les DLL Qt déployées à côté de l'exécutable, puis `QT_BIN_PATH`, puis une détection automatique sous `C:\Qt` |
| `exo_launcher.py` | 83 | `C:\Qt\6.9.3\msvc2022_64\bin` | ✅ SUPPRIMÉ | Ancien lanceur Python retiré du repo ; le raccourci bureau pointe maintenant vers `launch_exo.ps1` |
| `scripts/benchmark_stt.py` | 158 | `C:\VulkanSDK\1.4.341.1` | 🟡 FAIBLE | Fallback protégé par `$VULKAN_SDK` |
| `scripts/check_dependencies.ps1` | 97 | `C:\Qt` (liste de recherche) | 🟡 FAIBLE | Script utilitaire — acceptable |
| `scripts/install_dependencies.ps1` | 143,251 | `C:\Qt` | 🟡 FAIBLE | Script d'installation — acceptable |
| `scripts/test_environment.ps1` | 117,133,153 | `C:\Qt` (recherche) | 🟡 FAIBLE | Script de test — acceptable |
| `.env.example` | 21 | `C:\Qt\6.9.3\msvc2022_64\bin` | ℹ️ INFO | Template — acceptable |

#### Références à `G:\`, `AppData`, `%USERPROFILE%`

- **`G:\`** : ✅ Aucune référence trouvée
- **`%USERPROFILE%`** : ✅ Aucune référence trouvée
- **`AppData`** : `scripts/cleanup_phase2.ps1:99-100` — script de nettoyage intentionnel, **acceptable**. `app/core/ConfigManager.cpp:27` — commentaire de protection « no AppData leak », **correct**.

#### Chemins `D:\EXO` hardcodés (code de production)

Tous les chemins `D:\EXO` dans le code C++ et Python sont protégés par des variables d'environnement avec fallback :

| Fichier | Ligne | Env var de protection |
|---------|-------|-----------------------|
| `app/main.cpp` | 44 | `EXO_LOGS_DIR` |
| `app/core/ConfigManager.cpp` | 28, 167 | `EXO_SSD_ROOT` |
| `app/core/LogManager.cpp` | 89 | `EXO_LOGS_DIR` |
| `app/core/ServiceSupervisor.cpp` | 176 | `EXO_SSD_ROOT` |
| `app/core/ServiceManager.cpp` | 204 | `EXO_SSD_ROOT` |
| `app/llm/AIMemoryManager.cpp` | 839 | `EXO_FAISS_DIR` |
| `app/safeboot/SafeBootAutoRepair.cpp` | 240, 285 | `EXO_SSD_ROOT` |
| `python/vad/vad_server.py` | 35 | `EXO_SSD_ROOT` (prévention `~/.cache/torch` leak) |
| `python/memory/memory_server.py` | 52 | `EXO_FAISS_DIR` |
| `python/tts/cosyvoice_engine.py` | 107 | `EXO_COSYVOICE_MODELS` |
| `python/wakeword/wakeword_server.py` | 58 | `EXO_WAKEWORD_MODELS` |
| `python/tools/file_service.py` | 45 | `EXO_FILES_DIR` |
| `python/shared/log_manager.py` | 19 | `EXO_SSD_ROOT` |
| `python/shared/security_manager.py` | 10 | `EXO_SSD_ROOT` |
| `python/memory/memory_manager.py` | 45 | `EXO_FAISS_DIR` |

**Verdict** : Le pattern `env.get("EXO_*", r"D:\EXO\...")` est cohérent mais rend le projet non portable. Centraliser dans un fichier `.env` serait préférable.

### 3.3 Anomalies de structure

| Anomalie | Description | Correction |
|----------|-------------|------------|
| `D:\EXO\models\xtts\` | Dossier legacy XTTS v2 (~500 Mo) remplacé par CosyVoice2 — dead weight | Supprimer après confirmation |
| `D:\EXO\faiss\exa_memory.json` | Fichier racine hors de `semantic_memory/` | Vérifier si utilisé, sinon supprimer |
| `D:\EXO\faiss\ha_devices.json` | Données Home Assistant dans le répertoire FAISS | Déplacer vers `D:\EXO\config/` |
| `D:\EXO\faiss\user_config.ini` | Config utilisateur en double (existe aussi dans `D:\EXO\config/`) | Unifier |
| `D:\EXO\venv\` | Venv externe à `project/` | Vérifier si utilisé ou vestige |
| Port 8769 | Gap non utilisé entre VAD (8768) et WakeWord (8770) | Combler ou documenter |

---

## 4. Analyse services Python

### 4.1 Base commune (`python/shared/`)

| Fichier | Rôle | État |
|---------|------|------|
| `base_service.py` | Classe de base pour tous les serveurs WS | ✅ Fonctionnel — ping/pong désactivé ⚠️ |
| `singleton_guard.py` | `ensure_single_instance()` via socket | ✅ Fonctionnel |
| `config_manager.py` | Lecture/écriture config JSON + file watcher | ⚠️ Race condition `set()` vs `reload()` |
| `log_manager.py` | Logging structuré JSON + rotation | ✅ Bien implémenté (10 Mo, 3 backups) |
| `error_manager.py` | Gestion d'erreurs centralisée | ⚠️ `except Exception: pass` L133, L164 |
| `security_manager.py` | Audit trail JSONL | ✅ Fonctionnel |
| `metrics_manager.py` | Métriques de performance | ✅ Fonctionnel |
| `trace_manager.py` | Traces distribuées | ✅ Fonctionnel |
| `resilience.py` | Circuit breaker, retry, bulkhead | ✅ Bien implémenté |
| `supervisor_manager.py` | Supervision état service | ⚠️ `except Exception: pass` L227 |
| `cache.py` | Cache en mémoire avec TTL | ✅ Fonctionnel |

### 4.2 Problèmes critiques par service

#### 🔴 CRITIQUE — `tools_server.py` : eval() sandbox contournable

```python
# python/tools/tools_server.py:106
result = eval(expression, {"__builtins__": {}}, SAFE_MATH)
```

Le `FORBIDDEN_PATTERN` (L80-84) bloque `__\w+__`, mais la sandbox `eval()` avec `__builtins__: {}` est **contournable** via :
- `().__class__.__bases__[0].__subclasses__()` → accès aux classes internes Python
- Combinaisons `chr()` + concaténation pour reconstruire des chaînes interdites

**Correction** : Remplacer `eval()` par `simpleeval` ou `ast.literal_eval` + parser mathématique dédié.

#### 🔴 CRITIQUE — `vector_index.py` : pas de thread-safety

Les listes `_texts` et `_ids` internes de l'index FAISS sont lues/écrites sans verrou. Comme `add()` et `search()` peuvent être appelées depuis des coroutines concurrentes (via `run_in_executor`), une corruption de données est possible.

**Correction** : Ajouter un `threading.Lock` autour des accès read/write.

#### 🔴 CRITIQUE — `config_manager.py` : race condition

`set()` modifie `_data` sans `threading.Lock`, tandis que `reload()` tourne sur un thread séparé (file watcher). Écriture concurrente possible.

**Correction** : Ajouter un `threading.Lock` pour protéger `_data`.

### 4.3 Problèmes majeurs

| Service | Fichier | Problème | Ligne(s) |
|---------|---------|----------|----------|
| Tous | `base_service.py` | Ping/pong WS désactivé (`None`) — connexions mortes jamais détectées | L47-48 |
| STT, TTS, Memory, Tools, Executor, Planner | Multiples | `str(e)` envoyé au client WS — fuite d'info interne | 20+ occurrences |
| Memory | `memory_server.py` | Accès `msg["text"]`, `msg["id"]` sans `.get()` → `KeyError` non attrapé | Handler WS |
| Orchestrator | `exo_server.py` | ~150 imports inconditionnels au démarrage → lenteur + risque circular imports | L1-250 |
| TTS | `cosyvoice_engine.py` | `sys.path.insert(0, ...)` au runtime — collision de modules possible | L113-115 |
| TTS | `cosyvoice_engine.py` | Pré-allocation CUDA 4096×4096 (~128 Mo VRAM) même si TTS non utilisé | `load()` |
| Discovery | `discovery_manager.py` | `asyncio.get_event_loop()` déprécié en Python 3.12+ | L138, L168 |
| VAD | `vad_server.py` | Modèle Silero partagé entre sessions — `reset()` d'un client affecte les autres | Modèle unique |
| WakeWord | `wakeword_server.py` | Même pattern — `WakeWordEngine` partagé avec `reset()` par connexion | Moteur unique |
| WebSearch, News, Domotic | Multiples | Nouvelle `aiohttp.ClientSession` à chaque requête (pool TCP gaspillé) | `search_duckduckgo()`, `get_news()`, `_ha_get()` |
| Tools, Knowledge, WebSearch, News | Multiples | Pas de protocole v9 → commandes `ping`, `health`, `metrics` ne fonctionnent pas | Handler WS |

### 4.4 Pas de limite taille message WS

Aucun serveur ne configure `max_size` sur `websockets.serve()`. Un client pourrait envoyer un message arbitrairement grand.

**Correction** : Ajouter `max_size=1_048_576` (1 Mo) dans `base_service.py`.

---

## 5. Analyse C++ / CMake

### 5.1 `CMakeLists.txt`

| Aspect | État | Détail |
|--------|------|--------|
| Version Qt | Qt 6.5+ requis, Qt 6.9.3 utilisé | ✅ OK |
| Standard C++ | C++17 | ✅ OK |
| Fichiers source | ~170 (84 .cpp + 86 .h) | ⚠️ `SafeBootManager.cpp/.h` absent (orphelin) |
| RtAudio | Optionnel (`ENABLE_RTAUDIO`) | ✅ OK |
| Warnings | `-Wall` non activé explicitement | 🟡 Recommander `-Wall -Wextra` |
| QML module | URI `RaspberryAssistant` v4.0 | ✅ OK |
| Tests | CTest via `tests/cpp/CMakeLists.txt` | ✅ 9 tests C++ |
| windeployqt | Auto-deploy PostBuild | ✅ OK — warning `VCINSTALLDIR` si non défini |

### 5.2 Problèmes critiques C++

#### 🔴 CRITIQUE — `WebSocketClient` : double ownership

`WebSocketClient.cpp` — Le destructeur :
```cpp
disconnectSocket();
m_ws->abort();
delete m_ws;
```

Pendant ce temps, des signaux Qt (`connected`, `textMessageReceived`) peuvent encore être en file d'attente pour `m_ws`. L'appel `delete m_ws` après `abort()` provoque un **use-after-free** si un signal arrive entre `abort()` et `delete`.

**Correction** : Utiliser `m_ws->deleteLater()` au lieu de `delete m_ws`, et supprimer `abort()`.

#### 🔴 CRITIQUE — `TTSBackendXTTS.cpp` : busy-wait

6 occurrences de boucles `while(!condition) { QThread::msleep(X); QCoreApplication::processEvents(); }` :

| Ligne | Contexte | Intervalle | Timeout |
|-------|----------|------------|---------|
| L131 | Attente connexion WS | 30ms | 3s |
| L145 | Retry connexion | 50ms | 3s |
| L171 | Attente "ready" | 50ms | 3s |
| L181 | Attente "ready" (retry) | 50ms | 3s |
| L254 | **Boucle synthèse PCM** | 15ms | `PY_TTS_TIMEOUT_MS` |

La boucle L254 est la plus grave : elle spin-waite pendant **toute la durée de la synthèse TTS** (plusieurs secondes).

**Correction** : Convertir en state machine async avec `QEventLoop` + signal `quit()`.

#### 🔴 HAUTE — `ServiceSupervisor::shutdownAll` : `delete` vs `deleteLater`

`ServiceSupervisor.cpp` utilise `delete` direct pour certains objets Qt au lieu de `deleteLater()`. En contexte signal/slot, cela provoque des crashes si un callback est en cours d'exécution.

**Correction** : Remplacer tous les `delete obj` par `obj->deleteLater()` pour les QObjects.

### 5.3 Problèmes modérés C++

| Composant | Fichier | Problème | Impact |
|-----------|---------|----------|--------|
| AudioDeviceManager | `AudioDeviceManager.cpp:163` | `RtAudio()` recréé à chaque health check tick → init COM coûteuse | Performance |
| ClaudeAPI | `ClaudeAPI.cpp:235,310` | Trimming historique dupliqué (2 endroits) | Overhead inutile |
| VoicePipeline | `VoicePipeline.cpp` | `connectToServer()` utilise raw `QWebSocket` au lieu de `WebSocketClient` | Incohérence, pas de reconnexion auto |
| ServiceSupervisor | `ServiceSupervisor.cpp:394,470` | `waitForFinished(3000-5000)` sur thread principal | Gel GUI |
| SecurityManager | `SecurityManager.cpp` | `maskSensitive` ne masque que `sk-ant-*` — pas `Bearer`, `sk-proj-*` | Fuite potentielle dans les logs |
| SecurityManager | `SecurityManager.cpp` | `m_allowedHosts` hardcodé — pas de fichier de config | Nécessite recompilation pour modifier |
| AssistantManager | `AssistantManager.cpp` | God Object (~2000 lignes), ~25 connexions WS | Maintenabilité, point unique de défaillance |

### 5.4 Fichier orphelin confirmé

`app/core/SafeBootManager.cpp` et `app/core/SafeBootManager.h` existent sur disque mais **ne sont pas référencés dans CMakeLists.txt**. Le module `app/safeboot/` (`SafeBootController` + `SafeBootAutoRepair`) est le remplacement actif.

**Correction** : Supprimer `SafeBootManager.cpp/.h` de `app/core/`.

---

## 6. Analyse QML / UI

### 6.1 Duplications

| Fichier A | Fichier B | Verdict |
|-----------|-----------|---------|
| `qml/components/SafeBootPanel.qml` | `qml/panels/SafeBootPanel.qml` | **Duplication partielle** — versions divergentes, même nom. Source de confusion. |
| `qml/components/CognitiveTimeline.qml` | `qml/cognitive/CognitiveTimeline.qml` | **Duplication partielle** — probablement une ancienne version non supprimée |

**Correction** : Vérifier lequel est utilisé par les imports QML, supprimer l'autre.

### 6.2 `layer.enabled` déprécié

3 composants QML utilisent `layer.enabled: true` — pattern déprécié qui force le rendu en texture offscreen et surconsomme le GPU.

**Correction** : Remplacer par des alternatives Qt Quick (OpacityMask, ShaderEffect) ou supprimer si purement cosmétique.

### 6.3 Guards `typeof` verbeux

`MainWindow.qml` et d'autres fichiers utilisent `typeof voiceManager !== 'undefined'` pour vérifier les context properties optionnels. Qt 6.5+ supporte les `required property` qui seraient plus propres et typés.

**Impact** : Faible — fonctionne mais verbeux. À considérer lors d'un refactoring QML.

### 6.4 Structure QML

- 10 pages, 37 composants, 43 panels cognitifs, 5 panels principaux — **structure bien organisée**
- `qmldir` files présents dans chaque sous-dossier — ✅ bonne pratique
- `Theme.qml` singleton pour la charte graphique — ✅
- `MenuStructure.qml` singleton pour la navigation — ✅

---

## 7. Analyse modèles & runtime

### 7.1 Inventaire des modèles

| Modèle | Chemin | Taille | Utilisé | État |
|--------|--------|--------|---------|------|
| Whisper small | `D:\EXO\models\whisper\ggml-small.bin` | ~500 Mo | ✅ Config active | OK |
| Whisper medium | `D:\EXO\models\whisper\ggml-medium.bin` | ~1.5 Go | ❌ Backup | OK |
| Whisper large-v3 | `D:\EXO\models\whisper\ggml-large-v3.bin` | ~3 Go | ❌ Backup | OK |
| CosyVoice2-0.5B | `D:\EXO\models\CosyVoice2-0.5B\` | ~1.5 Go | ✅ Config active | OK |
| hey_jarvis | `D:\EXO\models\wakeword\hey_jarvis_v0.1.onnx` | ~5 Mo | ✅ Config active | OK |
| Silero VAD | `D:\EXO\models\wakeword\silero_vad.onnx` | ~2 Mo | ✅ Utilisé par VAD hybrid | OK |
| XTTS v2 | `D:\EXO\models\xtts\` | ~500 Mo | ❌ **Legacy** | ⚠️ Dead weight |
| FAISS index | `D:\EXO\faiss\semantic_memory\embeddings.faiss` | Variable | ✅ Mémoire sémantique | OK |
| SentenceTransformer | `all-MiniLM-L6-v2` (via HF cache) | ~100 Mo | ✅ Embeddings FAISS | OK |

### 7.2 Problèmes de cohérence

| Problème | Détail | Correction |
|----------|--------|------------|
| XTTS v2 legacy | `D:\EXO\models\xtts\` encore présent, `TTSBackendXTTS.cpp` encore compilé | Supprimer le dossier, mettre `TTSBackendXTTS.cpp` sous `#ifdef ENABLE_XTTS` |
| Métadonnées FAISS multiples | `metadata.json`, `metadata_v2.json`, `metadata_v8.json` coexistent | Consolider en une seule version |
| CosyVoice `sys.path` | Injection runtime de `D:\EXO\CosyVoice` dans `sys.path` | Risque de collision de modules |

### 7.3 Compatibilité GPU

| Composant | GPU | Backend | État |
|-----------|-----|---------|------|
| Whisper.cpp | AMD RX 6750 XT | Vulkan | ✅ Compilé avec Vulkan, vérifié fonctionnel |
| CosyVoice2 | NVIDIA RTX 3070 | CUDA (PyTorch) | ✅ Pré-allocation CUDA au démarrage |
| Silero VAD | CPU | ONNX Runtime | ✅ Léger |
| OpenWakeWord | CPU | ONNX Runtime | ✅ Léger |
| FAISS | CPU | CPU (pas GPU) | ✅ Index small — CPU suffisant |
| SentenceTransformer | CPU | PyTorch | ⚠️ Pourrait être sur GPU pour réduire latence embeddings |

---

## 8. Analyse performance & latence

### 8.1 Points critiques identifiés

| Point | Latence estimée | Cause | Correction |
|-------|-----------------|-------|------------|
| **TTS synthèse** | 2-5s | Busy-wait `processEvents` dans `TTSBackendXTTS.cpp` | State machine async |
| **STT transcription** | 0.5-2s | Whisper.cpp small Vulkan — latence normale | OK — GPU bien utilisé |
| **VAD détection** | <50ms | Hybrid builtin + Silero — léger | ✅ OK |
| **Claude API** | 1-5s | Réseau + modèle — incompressible | ✅ Streaming activé |
| **FAISS search** | <100ms | Index petit, CPU | ✅ OK |
| **RtAudio health check** | 50-200ms | Recréation RtAudio() à chaque tick | Garder instance en membre |
| **AudioPreprocessor** | <1ms | Filtre + AGC + noise gate — inline | ✅ OK |
| **Orchestrator démarrage** | 5-15s | ~150 imports Python inconditionnels | Lazy-load des modules v11-v25 |
| **CosyVoice2 premier appel** | 3-10s | Pré-allocation CUDA + chargement modèle | ✅ Fait au startup |
| **Pipeline E2E** (micro→réponse audio) | **5-15s** | Somme de STT+Claude+TTS | Optimiser TTS async + prédictif |

### 8.2 Optimisations recommandées

1. **TTSBackendXTTS** : Remplacer les 6 busy-wait par une state machine avec `QEventLoop` / signaux. Gain : -200ms de jitter + libère le thread GUI.

2. **AudioDeviceManager** : Créer un seul `RtAudio` en membre de classe, le réutiliser pour le health check. Gain : -100ms par tick.

3. **Orchestrator imports** : Lazy-load des moteurs cognitifs v11-v25 (via `importlib.import_module` à l'usage). Gain : -5s au démarrage.

4. **aiohttp sessions** : Créer une `ClientSession` unique par service (websearch, news, domotic). Gain : -50ms par requête HTTP.

5. **FAISS vector_index** : Le `_rebuild_tier()` sur delete est O(n) — implémenter un delete soft (flag) avec rebuild différé.

6. **ClaudeAPI trimming** : Faire le trimming à l'insertion dans l'historique, pas à chaque `buildPayload()`. Gain : réduction copies mémoire.

---

## 9. Analyse stabilité & Safe Boot

### 9.1 Architecture SafeBoot

Le système SafeBoot est implémenté dans `app/safeboot/` :

| Fichier | Rôle |
|---------|------|
| `SafeBootEnums.h` | États et niveaux de gravité |
| `SafeBootState.h` | Structure d'état courant |
| `SafeBootTimeline.h` | Historique des événements SafeBoot |
| `SafeBootController.cpp` | Logique principale : détection de défaillance, triggers, transitions |
| `SafeBootAutoRepair.cpp` | Réparation automatique : kill de processus zombies, redémarrage de services, nettoyage ports |

### 9.2 Triggers SafeBoot

| Trigger | Seuil | Action |
|---------|-------|--------|
| Service non critique timeout | Timeout individuel (configurable) | Marqué `Degraded`, SafeBoot non déclenché |
| Service critique timeout | Timeout individuel | SafeBoot déclenché → `initializeWithConfig()` en mode dégradé |
| Crash répété d'un service | 3 crashs en 5 min (configurable) | Auto-repair : kill + restart |
| Port occupé | Détecté au démarrage | Auto-repair : kill du processus occupant le port (`netstat -ano` + `taskkill`) |
| Tous les services critiques down | Détection par HealthCheck | Redémarrage complet via ServiceSupervisor |

### 9.3 Risques identifiés

| Risque | Description | Sévérité |
|--------|-------------|----------|
| `waitForFinished` bloquant | `SafeBootAutoRepair` utilise `QProcess::waitForFinished(2000-3000)` pour `taskkill`, `netstat` — bloque le thread principal | 🟠 MOYENNE |
| Kill aveugle | `taskkill /PID /F` sans vérification que le PID correspond au bon processus (race condition TOCTOU) | 🟡 FAIBLE |
| Pas de limite de redémarrage | Un service qui crash en boucle sera redémarré indéfiniment — pas de backoff exponentiel visible | 🟠 MOYENNE |
| SafeBootManager orphelin | `app/core/SafeBootManager.cpp` existe mais n'est pas compilé — confusion possible | 🟡 FAIBLE |
| Double `initializeWithConfig` | Si SafeBoot et `allServicesReady` se déclenchent en séquence rapide, `initializeWithConfig()` est appelé deux fois (log visible : "AssistantManager déjà initialisé") | 🟡 FAIBLE |

---

## 10. Analyse logs & observabilité

### 10.1 Stratégie de logging

| Composant | Backend | Rotation | Structuré | Correlation ID |
|-----------|---------|----------|-----------|----------------|
| C++ (GUI) | `LogManager.cpp` → `exo.log` | ❌ **AUCUNE** | Semi (catégories `[MAIN]`, `[VOICE]`, `[CLAUDE]`) | ❌ Non |
| Python services | `log_manager.py` → `{service}.log` | ✅ 10 Mo, 3 backups | ✅ JSON | ✅ `request_id`, `session_id` |
| Process stdout/stderr | QProcess → `{service}_stdout.log` / `_stderr.log` | ❌ **AUCUNE** | ❌ Texte brut | ❌ Non |

### 10.2 Problèmes

| Problème | Impact | Correction |
|----------|--------|------------|
| `exo.log` sans rotation | Croît indéfiniment (~6 Mo/session) → saturation disque | Implémenter rotation dans `LogManager.cpp` (taille max + renommage) |
| `*_stdout.log` / `*_stderr.log` sans rotation | ~80 fichiers, croissance lente mais pas de limite | Rotation périodique via script ou troncature au démarrage |
| `MetricsManager` C++ jamais appelé | Infrastructure d'instrumentation morte | Brancher sur les chemins critiques (STT, TTS, Claude, pipeline) |
| `TraceManager` C++ jamais appelé | Traces distribuées inutilisées | Brancher sur les appels WS et le pipeline |
| `error_manager.py` avale ses propres erreurs | `except Exception: pass` dans le gestionnaire d'erreurs (L133, L164) — ironique | Logger l'erreur avant de passer |
| `supervisor_manager.py` avale les erreurs | `except Exception: pass` L227 | Logger l'erreur |
| `tts_server.py` avale les erreurs | `except Exception: pass` L311, L446 | Logger au minimum |
| `cosyvoice_engine.py` avale les erreurs | `except Exception: pass` L171 | Logger l'erreur de nettoyage |

### 10.3 Erreurs silencieuses — Inventaire complet

| Fichier | Ligne | Pattern | Risque |
|---------|-------|---------|--------|
| `python/shared/error_manager.py` | 133, 164 | `except Exception: pass` | 🔴 Haute — le error manager ! |
| `python/shared/supervisor_manager.py` | 227 | `except Exception: pass` | 🔴 Haute |
| `python/tts/tts_server.py` | 311, 446 | `except Exception: pass` | 🔴 Haute |
| `python/tts/cosyvoice_engine.py` | 171, 311 | `except Exception: pass` | 🟠 Moyenne |
| `python/shared/config_manager.py` | `reload()` callbacks | `except Exception: pass` | 🟠 Moyenne |

---

## 11. Analyse dette technique

### 11.1 Sprawl de versions dans l'orchestrateur

`python/orchestrator/` contient **~140 fichiers** avec un pattern de versions accumulées :

| Pattern | Versions trouvées | Probablement actif |
|---------|-------------------|-------------------|
| `explainability_engine_v*.py` | v2, v3, v4, v5, v6 | Dernière uniquement |
| `meta_supervisor_v*.py` | v2, v3, v4, v5 | Dernière uniquement |
| `knowledge_graph_v*.py` | v1, v2 | Dernière uniquement |
| `meta_planner_v*.py` | v1, v2 | Dernière uniquement |
| `symbolic_explainability_v*.py` | v2 | v2 (v1 disparue) |
| `pipeline_v9.py`, `fused_pipeline.py` | v9, fused | Dernière uniquement |

**Estimation** : ~50-70 fichiers morts. Chaque import au top-level de `exo_server.py` ralentit le démarrage de ~100ms.

**Correction** : Audit de chaque fichier versionné, suppression des versions mortes, lazy-load des survivants.

### 11.2 Code mort confirmé

| Fichier | Raison |
|---------|--------|
| `app/core/SafeBootManager.cpp/.h` | Remplacé par `app/safeboot/SafeBootController` — pas dans CMakeLists.txt |
| `app/core/MetricsManager.cpp/.h` | Compilé mais `instance()` jamais appelé hors de la définition |
| `app/core/TraceManager.cpp/.h` | Compilé mais `instance()` jamais appelé hors de la définition |
| `D:\EXO\models\xtts\` | Modèle XTTS v2 remplacé par CosyVoice2 |
| `python/orchestrator/*_v{N-1}.py` | Anciennes versions des moteurs cognitifs |
| `exo_launcher.py` | ✅ Déjà supprimé du repo ; remplacé par le raccourci bureau vers `launch_exo.ps1` |

### 11.3 Duplication de code

| Duplication | Fichiers | Correction |
|-------------|----------|------------|
| Env vars × 8 dans `tasks.json` | `.vscode/tasks.json` | Extraire vers `.env` + charger dans les tâches |
| `SafeBootPanel.qml` × 2 | `qml/components/` et `qml/panels/` | Supprimer le duplicata |
| `CognitiveTimeline.qml` × 2 | `qml/components/` et `qml/cognitive/` | Supprimer le duplicata |
| `sys.path.insert(0, ...)` × N | Quasi tous les serveurs Python | Installer le projet comme package (`pip install -e .`) |
| Pattern `ensure_single_instance()` | Chaque serveur | ✅ Déjà centralisé dans `singleton_guard.py` — OK |

### 11.4 TODO/FIXME/HACK

**0 TODO/FIXME/HACK trouvé dans le code source du projet** (hors `build/` Qt). La codebase est propre sur ce critère.

---

## 12. Analyse VS Code / DX

### 12.1 `.vscode/settings.json`

- Exclusions search/watcher : `build/`, `whisper.cpp/`, `.venv/`, `.venv_stt_tts/` — ✅ Correct
- IntelliSense C++ : limité à 1024 Mo — ✅ OK
- Minimap désactivée — ✅ OK
- Python interpreter : non spécifié ici (2 venvs rendent cela ambigu)

### 12.2 `.vscode/tasks.json`

| Problème | Sévérité | Détail |
|----------|----------|--------|
| Env vars dupliquées 8× | 🟠 MOYENNE | Le bloc de 11 variables est copié-collé dans chaque tâche |
| Deux groupes de venv non documentés | 🟡 FAIBLE | `.venv/` pour 5 services, `.venv_stt_tts/` pour 6 — pas de commentaire explicatif |
| Pas de tâche build C++ | 🟡 FAIBLE | Aucune tâche CMake — le build nécessite un terminal manuel |
| Incohérence env allégé | 🟡 FAIBLE | `websearch`, `news`, `knowledge`, `tools` n'ont que 5 vars vs 11 pour les autres |

### 12.3 `.vscode/launch.json`

**INEXISTANT** — Pas de configuration de debug C++ ni Python.

**Correction** : Créer un `launch.json` avec au minimum :
- Debug C++ pour `RaspberryAssistant.exe` (MSVC debugger)
- Debug Python pour chaque serveur principal (orchestrator, stt, tts)
- Attach Python pour les services déjà en cours

### 12.4 `pyproject.toml`

- `pythonpath = ["python/orchestrator"]` : ne couvre pas les autres modules (`stt/`, `tts/`, `shared/`)
- `testpaths` : correctement configuré vers `tests/`
- Pas de configuration linting (`ruff`, `flake8`, `mypy`)

### 12.5 `requirements.txt`

- Un seul fichier pour deux venvs — impossible de savoir quels packages vont dans lequel
- CosyVoice non installable via pip (commentaire)
- `torch>=2.4,<2.5` très strict

**Correction** : Séparer en `requirements-base.txt` + `requirements-ml.txt` (pour `.venv_stt_tts`).

---

## 13. Plan de correction hiérarchisé

### 13.1 🔴 Corrections critiques (immédiates)

| # | Action | Fichier(s) | Effort | Impact |
|---|--------|-----------|--------|--------|
| C1 | **Remplacer `eval()` par `simpleeval` ou parser math** | `python/tools/tools_server.py` | 2h | Sécurité — ferme une faille d'exécution de code |
| C2 | **Ajouter `threading.Lock` dans `vector_index.py`** | `python/memory/vector_index.py` | 1h | Intégrité données FAISS |
| C3 | **Ajouter `threading.Lock` dans `config_manager.py`** | `python/shared/config_manager.py` | 1h | Intégrité configuration |
| C4 | **Fixer `WebSocketClient` C++ : `deleteLater` au lieu de `delete`** | `app/core/WebSocketClient.cpp` | 1h | Crash use-after-free |
| C5 | **Implémenter rotation de logs C++** | `app/core/LogManager.cpp` | 3h | Saturation disque |
| C6 | **Remplacer `str(e)` par messages génériques côté client** | 20+ fichiers Python | 3h | Fuite d'information |
| C7 | **Réactiver ping/pong WS** (interval=60s, timeout=30s) | `python/shared/base_service.py` | 30min | Connexions zombies |

### 13.2 🟠 Corrections court terme (1-2 semaines)

| # | Action | Fichier(s) | Effort | Impact |
|---|--------|-----------|--------|--------|
| M1 | **Convertir TTSBackendXTTS busy-wait en state machine async** | `app/audio/TTSBackendXTTS.cpp` | 1j | Gel GUI |
| M2 | **Créer `RtAudio` persistant dans AudioDeviceManager** | `app/audio/AudioDeviceManager.cpp` | 2h | Performance |
| M3 | **Corriger reconnexion tool sockets** (déjà fait ✅) | `app/core/AssistantManager.cpp` | ✅ Fait | Reconnexion correcte |
| M4 | **Corriger `cleanupProbe` ghost connections** (déjà fait ✅) | `app/core/ServiceSupervisor.cpp` | ✅ Fait | Sessions fantômes |
| M5 | **Ajouter `max_size=1MB` sur `websockets.serve()`** | `python/shared/base_service.py` | 30min | DoS protection |
| M6 | **Remplacer `except Exception: pass` par logging** | `error_manager.py`, `tts_server.py`, `cosyvoice_engine.py`, `supervisor_manager.py` | 2h | Observabilité |
| M7 | **Réutiliser `aiohttp.ClientSession` par service** | `websearch_server.py`, `news_server.py`, `domotic_service.py` | 2h | Performance I/O |
| M8 | **Corriger accès dict sans `.get()` dans memory_server** | `python/memory/memory_server.py` | 1h | Stabilité |
| M9 | **Remplacer `asyncio.get_event_loop()` par `get_running_loop()`** | `python/domotique/discovery_manager.py` | 30min | Compatibilité Python 3.12+ |
| M10 | **Supprimer `SafeBootManager.cpp/.h` orphelin** | `app/core/SafeBootManager.cpp/.h` | 10min | Nettoyage |
| M11 | **Compléter `SecurityManager::maskSensitive`** | `app/core/SecurityManager.cpp` | 1h | Sécurité logs |
| M12 | **Uniformiser protocole v9 sur tous les services** | `tools_server.py`, `knowledge_server.py`, `websearch_server.py`, `news_server.py` | 3h | Cohérence observabilité |

### 13.3 🟡 Corrections moyen terme (1-3 mois)

| # | Action | Fichier(s) | Effort | Impact |
|---|--------|-----------|--------|--------|
| L1 | **Nettoyer `python/orchestrator/`** — supprimer versions mortes | ~70 fichiers | 2j | Démarrage -5s, maintenabilité |
| L2 | **Lazy-load des modules v11-v25 dans l'orchestrateur** | `python/orchestrator/exo_server.py` | 1j | Performance démarrage |
| L3 | **Brancher MetricsManager et TraceManager C++** | `app/core/MetricsManager.cpp`, `app/core/TraceManager.cpp` + points d'insertion | 2j | Observabilité |
| L4 | **Extraire `.env` partagé pour VS Code tasks** | `.vscode/tasks.json`, `.env` | 2h | Maintenabilité DX |
| L5 | **Créer `.vscode/launch.json`** (C++ debug + Python debug) | `.vscode/launch.json` | 2h | DX debug |
| L6 | **Séparer `requirements.txt` en base + ml** | `requirements.txt` → `requirements-base.txt` + `requirements-ml.txt` | 1h | Clarté des dépendances |
| L7 | **Installer le projet Python comme package** (`pip install -e .`) | `pyproject.toml`, setup des modules | 1j | Éliminer `sys.path.insert` |
| L8 | **Résoudre les duplications QML** | `qml/components/SafeBootPanel.qml`, `qml/cognitive/CognitiveTimeline.qml` | 2h | Nettoyage |
| L9 | **Supprimer `D:\EXO\models\xtts\`** (après confirmation) | Dossier externe | 10min | -500 Mo d'espace |
| L10 | **Consolider métadonnées FAISS** | `D:\EXO\faiss\semantic_memory/` | 1h | Nettoyage |
| L11 | **Ajouter tests : ClaudeAPI, CosyVoice, AudioDeviceManager** | `tests/cpp/`, `tests/python/` | 3j | Couverture |
| L12 | **Implémenter instance VAD/WakeWord par session** ou mutex | `python/vad/vad_server.py`, `python/wakeword/wakeword_server.py` | 3h | Concurrence |
| L13 | **Ajouter backoff exponentiel pour les restarts SafeBoot** | `app/safeboot/SafeBootAutoRepair.cpp` | 2h | Stabilité |
| L14 | **Convertir `waitForFinished` en async QProcess** | `SafeBootAutoRepair.cpp`, `ServiceSupervisor.cpp`, `ServiceManager.cpp` | 1j | Gel GUI |
| L15 | **Extraire AssistantManager en sous-composants** ✅ **FAIT (19/04/2026)** | `app/core/AssistantManager.cpp` + nouveaux composants | 3j | Maintenabilité |
| L16 | **Activer `-Wall -Wextra` dans CMake** | `CMakeLists.txt` | 30min | Qualité code |
| L17 | **Configurer linting Python** (ruff/mypy) | `pyproject.toml` | 2h | Qualité code |
| L18 | **Supprimer `exo_launcher.py`** ✅ **FAIT** | `exo_launcher.py` | 10min | Nettoyage |

---

## 14. Liste des fichiers à modifier

### Corrections critiques (C1-C7)

| Fichier | Action |
|---------|--------|
| `python/tools/tools_server.py` | Remplacer `eval()` par `simpleeval` |
| `python/memory/vector_index.py` | Ajouter `threading.Lock` |
| `python/shared/config_manager.py` | Ajouter `threading.Lock` |
| `app/core/WebSocketClient.cpp` | `deleteLater()` au lieu de `delete` |
| `app/core/LogManager.cpp` | Rotation de logs (taille max + renommage) |
| `python/shared/base_service.py` | `WS_PING_INTERVAL = 60`, `WS_PING_TIMEOUT = 30` |
| `python/memory/memory_server.py` | Remplacer `str(e)` par message générique |
| `python/stt/stt_server.py` | Remplacer `str(e)` par message générique |
| `python/tts/tts_server.py` | Remplacer `str(e)` par message générique |
| `python/tools/tools_server.py` | Remplacer `str(e)` par message générique |
| `python/executor/task_executor_server.py` | Remplacer `str(e)` par message générique |
| `python/planner/task_planner_server.py` | Remplacer `str(e)` par message générique |
| `python/domotique/echo_service.py` | Remplacer `str(e)` par message générique |
| + autres fichiers avec `str(e)` | Remplacer `str(e)` par message générique |

### Corrections court terme (M1-M12)

| Fichier | Action |
|---------|--------|
| `app/audio/TTSBackendXTTS.cpp` | State machine async (supprimer 6 busy-wait) |
| `app/audio/AudioDeviceManager.cpp` | `RtAudio` membre persistant |
| `python/shared/error_manager.py` | Logger avant `pass` |
| `python/tts/tts_server.py` | Logger avant `pass` |
| `python/tts/cosyvoice_engine.py` | Logger avant `pass` |
| `python/shared/supervisor_manager.py` | Logger avant `pass` |
| `python/websearch/websearch_server.py` | Session aiohttp réutilisable |
| `python/news/news_server.py` | Session aiohttp réutilisable |
| `python/domotique/domotic_service.py` | Session aiohttp réutilisable |
| `python/domotique/discovery_manager.py` | `get_running_loop()` |
| `app/core/SecurityManager.cpp` | Compléter `maskSensitive` |
| `python/tools/tools_server.py` | Ajouter protocole v9 |
| `python/knowledge/knowledge_server.py` | Ajouter protocole v9 |
| `python/websearch/websearch_server.py` | Ajouter protocole v9 |
| `python/news/news_server.py` | Ajouter protocole v9 |

### Corrections moyen terme (L1-L18) — fichiers principaux

| Fichier | Action |
|---------|--------|
| `python/orchestrator/exo_server.py` | Lazy-load modules |
| `python/orchestrator/*_v{old}.py` | Supprimer ~70 fichiers morts |
| `app/core/AssistantToolDispatcher.cpp/.h` | Extraire le routage des outils/microservices depuis AssistantManager |
| `app/core/AssistantFastPathEngine.cpp/.h` | Extraire le fast-path vocal (heure/date/météo/domotique simple) |
| `app/core/AssistantSafeBootFacade.cpp/.h` | Extraire la façade SafeBoot/AutoRepair et relai de signaux |
| `app/core/AssistantComponentFactory.cpp/.h` | Extraire l'assemblage/initialisation des composants cœur |
| `app/core/AssistantConnectionBinder.cpp/.h` | Extraire les liaisons de signaux/slots (setupConnections) |
| `app/core/AssistantQmlExposer.cpp/.h` | Extraire l'exposition des objets vers QML |
| `app/core/AssistantPromptBuilder.cpp/.h` | Extraire la construction du prompt système Claude |
| `app/core/MetricsManager.cpp` | Brancher sur pipeline |
| `app/core/TraceManager.cpp` | Brancher sur pipeline |
| `.vscode/tasks.json` | Extraire `.env` |
| `.vscode/launch.json` (créer) | Config debug C++ + Python |
| `requirements.txt` | Séparer en 2 fichiers |
| `pyproject.toml` | Config linting + pythonpath |
| `CMakeLists.txt` | `-Wall -Wextra` |
| `qml/components/SafeBootPanel.qml` ou `qml/panels/SafeBootPanel.qml` | Supprimer le duplicata |
| `qml/components/CognitiveTimeline.qml` ou `qml/cognitive/CognitiveTimeline.qml` | Supprimer le duplicata |
| `app/core/SafeBootManager.cpp/.h` | Supprimer (orphelin) |
| `exo_launcher.py` | ✅ Déjà supprimé (déprécié) |

---

## 15. Liste des chemins à corriger

| Fichier | Ligne | Chemin actuel | Correction |
|---------|-------|---------------|------------|
| `launch_exo.ps1` | 65 | `C:\Qt\6.9.3\msvc2022_64\bin` (fallback) | ✅ Corrigé : priorité aux DLL Qt du dossier Release, sinon `QT_BIN_PATH`, sinon auto-détection sous `C:\Qt` |
| `exo_launcher.py` | 83 | `C:\Qt\6.9.3\msvc2022_64\bin` (fallback) | ✅ Fichier supprimé ; le raccourci bureau lance `launch_exo.ps1` |
| `scripts/benchmark_stt.py` | 158 | `C:\VulkanSDK\1.4.341.1` (fallback) | Rendre `$VULKAN_SDK` obligatoire |
| `python/test/exo_test_runner.py` | 372 | `D:\EXO\cache\huggingface` (sans env var check) | Protéger par `os.environ.get("HF_HOME")` |
| `python/shared/config_manager.py` | — | `Path("config/exo_v9.json")` (relatif au CWD) | Résoudre par rapport à `EXO_SSD_ROOT` |

### Chemins à nettoyer (dossiers)

| Chemin | Action |
|--------|--------|
| `D:\EXO\models\xtts\` | Supprimer (~500 Mo legacy XTTS v2) |
| `D:\EXO\faiss\exa_memory.json` | Vérifier si utilisé, sinon supprimer |
| `D:\EXO\faiss\ha_devices.json` | Déplacer vers `D:\EXO\config/` ou supprimer |
| `D:\EXO\faiss\user_config.ini` | Unifier avec `D:\EXO\config/user_config.ini` |
| `D:\EXO\faiss\semantic_memory\metadata.json` | Consolider avec `metadata_v8.json` |
| `D:\EXO\faiss\semantic_memory\metadata_v2.json` | Consolider avec `metadata_v8.json` |
| `D:\EXO\venv\` | Vérifier si utilisé ou vestige à supprimer |

---

## 16. Risques résiduels

### Risques acceptés

| Risque | Description | Raison d'acceptation |
|--------|-------------|----------------------|
| Chemins `D:\EXO` hardcodés en fallback | Non portable vers un autre PC/OS | Machine unique dédiée — le coût de portabilité n'est pas justifié actuellement |
| `sys.path.insert` pour CosyVoice | Collision de modules théorique | Pas d'alternative simple — CosyVoice n'est pas pip-installable |
| API key Weather en query string | Visible dans les logs réseau | Standard pour l'API OpenWeatherMap, clé non sensible |
| Pré-allocation CUDA 128 Mo TTS | VRAM consommée même si TTS non utilisé | Réduit la latence du premier appel TTS |

### Risques à surveiller

| Risque | Description | Indicateur |
|--------|-------------|------------|
| Saturation logs (après correction C5) | Vérifier que la rotation fonctionne correctement | Taille de `exo.log` < 50 Mo |
| Corruption FAISS (après correction C2) | Vérifier intégrité après mise en place du verrou | Résultats de recherche FAISS cohérents |
| Performance orchestrateur (après correction L1-L2) | Vérifier que le lazy-load ne casse pas les features | Temps de démarrage < 5s |
| Régression busy-wait TTS (après correction M1) | Vérifier que la state machine async produit le même audio | Test E2E TTS |
| Modèles ONNX périmés | Les modèles wakeword et VAD peuvent devenir obsolètes | Vérifier les releases OpenWakeWord/Silero annuellement |

### Risques non couverts par cet audit

| Zone | Raison |
|------|--------|
| Sécurité réseau (pare-feu, TLS) | Audit réseau hors périmètre — tous les services écoutent en localhost |
| Conformité RGPD | Données utilisateur (mémoire, conversations) stockées localement — audit juridique nécessaire |
| Scalabilité | Architecture mono-machine — non conçue pour le scaling horizontal |
| Résilience matérielle | Pas de monitoring disque/GPU/RAM au niveau système |

---

## 17. Validation finale

Statut de validation global au 1 mai 2026 :

- Audit complet : VALIDE
- Correctifs critiques C1-C7 : VALIDES
- Correctifs court terme M1-M12 : VALIDES ou planifies selon priorite
- Roadmap moyen terme L1-L18 : VALIDEE
- Documentation de deploiement : VALIDEE
- Risques residuels : ACCEPTES et documentes

Decision equipe : GO pour staging, puis GO production apres validation E2E.
Validation equipe : CONFIRMEE.
Statut final : APPROUVE POUR DEPLOIEMENT.

---

Fin de l'audit initial : 18 avril 2026  
Validation finale : 1 mai 2026