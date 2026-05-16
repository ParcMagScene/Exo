# AUDIT COMPLET PRÉ-NETTOYAGE — EXO

**Date** : 2026-05-16  
**Auteur** : Copilot (audit automatisé, lecture seule)  
**Contrainte stricte** : aucune suppression, aucune modification, aucun déplacement effectué. Le présent document est un **rapport** uniquement.  
**Périmètre exclu** : `.venv/`, `.venv_stt_tts/`, `services/orpheus/venv/`, `.git/`, `whisper.cpp/`, `whispercpp/`, `build/`, `cache/` (déjà gitignorés).

---

## Synthèse exécutive

| Catégorie | Constat clé | Sévérité |
|---|---|---|
| **Référence cassée** | `python/tts/tts_server.py` est référencé par 13 fichiers (tasks.json, launch_exo*.ps1, README, scripts) mais **n'existe pas** sur disque. Le TTS de production est `services/orpheus/server_ws.py`. | 🔴 CRITIQUE |
| **Doc dupliquée** | 16 paires `docs/X.md` (vrai, 3-37 KB) vs `docs/audits/<cat>/X.md` (stub 0.2 KB). Structure cible visiblement `docs/audits/<cat>/` mais migration incomplète. | 🟠 HAUTE |
| **Modèles GGUF Orpheus** | 3 quantizations Q5/Q6/Q8 = **8.2 GB**. Q5+Q6 = 4.87 GB référencés uniquement par scripts de benchmark (`bench_quants.py`, `ab_validate_j2.py`, `models_manifest.json`). Production = Q8. | 🟡 MOYENNE |
| **`python/orchestrator/`** | 170 modules cognitifs. 11 variantes "explainability_engine", 9 variantes "coherence_engine". `_archived/` contient déjà v2-v6, mais doublons potentiels en racine. | 🟡 MOYENNE |
| **Tests versionnés en racine** | `test_agent_v10`, `test_context_engine_v8`, `test_memory_v2/v8`, `test_pipeline_v82`, `test_task_planner_v8` non archivés (alors que v9-v25 le sont dans `tests/python/archive/`). | 🟡 MOYENNE |
| **WAV racine** | 4 fichiers d'audit/test (~1.4 MB) à la racine du dépôt. | 🟢 BASSE |
| **Scripts bench dupliqués** | `bench_tts_5x.py` + `bench_tts_10x.py`. | 🟢 BASSE |

---

## 1. Arborescence top-level (taille)

| Dossier | Taille | Commit ? | Statut |
|---|---:|---|---|
| `.venv_stt_tts/` | 12 712 MB | non (gitignore) | ✅ exclu |
| `models/` | 8 694 MB | non | ✅ artefacts ML |
| `services/` | 6 452 MB | partiel (venv exclu) | ⚠️ contient `services/orpheus/venv/` ≈ 6 GB |
| `whisper.cpp/` | 3 902 MB | dépend de `.gitignore` | source vendored |
| `.venv/` | 1 082 MB | non | ✅ exclu |
| `cache/` | 534 MB | non (ajouté 2026-05-16) | ✅ exclu |
| `.git/` | 487 MB | — | git interne |
| `build/` | 410 MB | non | ✅ exclu |
| `whispercpp/` | 58.9 MB | dépend | source vendored |
| `tools/` | 46.3 MB | oui | binaires `llama_cpp/` (41 .exe/.dll) |
| `logs/` | 25.6 MB | non | runtime |
| `rtaudio/` | 4 MB | oui | source vendored |
| `python/` | 2.4 MB | oui | code applicatif |
| `app/` | 1.3 MB | oui | code C++ Qt |
| `tests/` | 0.9 MB | oui | |
| `qml/` | 0.7 MB | oui | |

---

## 2. Services (16 tâches VS Code) — actifs / cassés

| Service (tâche) | Fichier cible | Existe ? | Venv |
|---|---|---|---|
| `exo_server` | `python/orchestrator/exo_server.py` | ✅ | `.venv_stt_tts` |
| `stt_server` | `python/stt/stt_server.py` | ✅ | `.venv_stt_tts` |
| **`tts_server`** | **`python/tts/tts_server.py`** | **❌ MANQUANT** | `.venv_stt_tts` |
| `vad_server` | `python/vad/vad_server.py` | ✅ | `.venv_stt_tts` |
| `wakeword_server` | `python/wakeword/wakeword_server.py` | ✅ | `.venv_stt_tts` |
| `memory_server` | `python/memory/memory_server.py` | ✅ | `.venv_stt_tts` |
| `nlu_server` | `python/nlu/nlu_server.py` | ✅ | `.venv_stt_tts` |
| `context_server` | `python/context/context_engine.py` | ✅ | `.venv_stt_tts` |
| `planner_server` | `python/planner/task_planner_server.py` | ✅ | `.venv_stt_tts` |
| `executor_server` | `python/executor/task_executor_server.py` | ✅ | `.venv_stt_tts` |
| `verifier_server` | `python/verifier/task_verifier_server.py` | ✅ | `.venv_stt_tts` |
| `system_server` | `python/tools/system_service.py` | ✅ | `.venv_stt_tts` |
| `websearch_server` | `python/websearch/websearch_server.py` | ✅ | `.venv` |
| `news_server` | `python/news/news_server.py` | ✅ | `.venv` |
| `knowledge_server` | `python/knowledge/knowledge_server.py` | ✅ | `.venv` |
| `tools_server` | `python/tools/tools_server.py` | ✅ | `.venv` |

### 🔴 Référence cassée — `tts/tts_server.py`

Contenu réel de `python/tts/` :
- `audio_streamer.py`
- `tts_client.py`
- `__init__.py`

Le serveur TTS de production est en réalité `services/orpheus/server_ws.py` (Orpheus 3B FR GGUF Q8) — confirmé par `requirements-ml.txt` (« Le serveur Orpheus utilise sa propre venv »).

**Référence cassée présente dans** : `.vscode/tasks.json`, `.vscode/launch.json`, `.vscode/settings.json`, `launch_exo.ps1`, `launch_exo_silent.ps1`, `README.md`, `python/orchestrator/tts_predictive.py`, `python/test/exo_test_runner.py`, `python/start_missing_services.py`, `scripts/auto_kill_zombies.py`, `scripts/patch_ujson.ps1`, `docs/TTS_MODEL_NOT_LOADED_FIX_REPORT.md`, `docs/TTS_PROVIDER_ROOT_CAUSE_REPORT.md`.

**À DÉCIDER manuellement avant tout nettoyage** : (a) recréer le shim `python/tts/tts_server.py` qui proxy vers Orpheus, ou (b) refactor des 13 références pour pointer vers `services/orpheus/start_orpheus.ps1`.

---

## 3. Modèles (`models/`, 8.7 GB)

| Fichier | Taille | Référencé par | Classification |
|---|---:|---|---|
| `models/orpheus_fr_gguf/Orpheus-3b-French-FT-Q8_0.gguf` | 3 353 MB | `services/orpheus/server_gguf.py`, `models_manifest.json` (production) | ✅ ACTIF |
| `models/orpheus_fr_gguf/Orpheus-3b-French-FT-Q6_K.gguf` | 2 591 MB | `bench_quants.py`, `ab_validate_j2.py`, `models_manifest.json`, `docs/PERF_REPORT_*` | 🟡 SUSPECT (benchmarks uniquement) |
| `models/orpheus_fr_gguf/Orpheus-3b-French-FT-Q5_K_M.gguf` | 2 284 MB | idem | 🟡 SUSPECT (benchmarks uniquement) |
| `models/whisper/ggml-small.bin` | 465 MB | STT (`stt_server.py` / `whisper_cpp.py`) | ✅ ACTIF |
| `models/orpheus_fr_gguf/.cache/huggingface/*` | 0 MB | — | metadata HF |
| `models/orpheus_fr_src/.cache/huggingface/.gitignore` | 0 MB | — | source HF (vide ?) |

**Note** : `models/orpheus_fr_src/` contient seulement `.cache/huggingface/.gitignore` → dossier source HF non rempli (peut être placeholder de download).

---

## 4. Assets / Resources

| Fichier | Statut |
|---|---|
| `assets/icons/app/exo.{ico,png,svg}` | ✅ ACTIFS (référencés `app/main.cpp` + `exo.rc`) |
| `resources/fonts/Roboto-Regular.ttf` | ✅ ACTIF (Qt resources) |

Aucun asset orphelin détecté.

---

## 5. QML (50 fichiers)

Tous les fichiers QML listés correspondent aux entrées `qt_add_qml_module` de `CMakeLists.txt` (vérifié sur les 9 pages standard, 7 pages Expert, 3 panels, 23 components, theme + navigation + core). Pas de QML orphelin.

| Catégorie | Fichiers |
|---|---|
| Pages standard | HomePage, SettingsPage, PipelinePage, HistoryPage, LogsPage, FloorPlanPage, MaisonPage, ReseauPage |
| Pages Expert | ObservabilityPage, PipelinePageExpert, VisionPageExpert, SimulationPageExpert, SpatialCognitionPageExpert, SecurityPageExpert, DevelopmentPageExpert |
| Panels | Sidebar, BottomBar, SafeBootPanel |
| Components | 23 (Exo*, FloorPlan*, AudioWaveformView, CognitiveTimeline, EngineHeatmap, GovernancePanel, MemoryInspector, ObservabilityDashboard, PipelineView, VoicePipelineView, FurniturePalette) |
| Theme / Navigation / Core | Theme.qml, MenuStructure.qml, UIState.qml |

---

## 6. Python (`python/`, ~230 fichiers `.py` hors venvs)

### 6.1 Modules ACTIFS (référencés par tâches VS Code ou `__init__.py`)

- **Services racine** : `context/`, `executor/`, `knowledge/`, `memory/`, `news/`, `nlu/`, `planner/`, `stt/`, `tts/` (partiel), `vad/`, `verifier/`, `wakeword/`, `websearch/`, `tools/`
- **Domaine métier** : `domotique/` (13 fichiers), `network/` (9 fichiers)
- **Shared** : `python/shared/` (12 fichiers utilitaires : config, log, metrics, security, resilience, supervisor, etc.)
- **Orchestrator (cœur)** : `python/orchestrator/exo_server.py` + dépendances

### 6.2 Doublons SUSPECTS dans `python/orchestrator/`

#### Famille « explainability » (11 variantes)
- `explainability_engine.py` (racine, actif)
- `explainability_engine_v5.py` ⚠️
- `auto_explanation.py`
- `governance_explainability_engine.py`
- `layered_explainability_engine.py`
- `modular_explainability_engine.py`
- `neurosymbolic_explainability_engine.py`
- `observability_explainability_engine.py`
- `optimization_explainability_engine.py`
- `planning_explainability_engine.py`
- `simulation_explainability_engine.py`
- `symbolic_explainability_v2.py` ⚠️
- Déjà archivés (`_archived/`) : v2, v3, v4, v6 — **v5 reste en racine**, suffixe `_v2` reste pour `symbolic_explainability_v2.py`.

#### Famille « coherence » (9 variantes)
- `layered_consistency_engine.py`
- `logical_coherence_engine.py`
- `neurosymbolic_coherence_engine.py`
- `plan_coherence_engine.py`
- `self_consistency_engine.py`
- `simulation_coherence_engine.py`
- `temporal_coherence_engine.py`
- `distributed_consistency_engine.py`
- `multi_level_validation_engine.py`

#### Suffixes versionnés non archivés
- `knowledge_graph.py` + `knowledge_graph_v2.py`
- `pipeline_v9.py`
- `global_supervisor_v5.py`
- `_version_registry.py`

→ Vérifier manuellement quels modules sont réellement importés via `grep "from orchestrator\." python/`.

### 6.3 `python/start_missing_services.py`

Référence `python/tts/tts_server.py` (cassé). À aligner après décision §2.

### 6.4 `python/tts/`

Manque `tts_server.py` ou `tts_streaming.py` (anciens fichiers déjà archivés selon contexte). Le dossier ne contient que `audio_streamer.py` + `tts_client.py` → la pile TTS active vit dans `services/orpheus/`.

---

## 7. C++ (`app/`, 162 fichiers .cpp/.h)

Tous les fichiers .cpp/.h dans `app/` correspondent aux variables `SOURCES`/`HEADERS` de `CMakeLists.txt` (≈75 SOURCES, ≈73 HEADERS). Aucun orphelin C++ détecté.

Modules :
| Sous-dossier | Fichiers | Rôle |
|---|---:|---|
| `app/audio/` | 18 | I/O audio (RtAudio + Qt), pipeline voix, TTS backend (XTTS optionnel) |
| `app/core/` | ~40 | AssistantManager + 8 sub-managers, ConfigManager, Health, Log, Metrics, Security, Service*, Trace, WebSocketClient |
| `app/floorplan/` | ? | Floorplan model |
| `app/llm/` | 4 | AIMemoryManager, ClaudeAPI |
| `app/safeboot/` | 10 | Controller + AutoRepair + Enums + State + Timeline |
| `app/simulation/` | 7 | |
| `app/spatialcognition/` | 8 | |
| `app/spatialsecurity/` | 8 | |
| `app/vision/` | 7 | |
| `app/utils/` | 2 | SafeIO.h, WeatherManager |
| `app/test/` | 1 | TestController |

Backend TTS C++ (`TTSBackend.{h,cpp}`, `TTSAudioSinkRtAudio.{h,cpp}`, `TTSManager.{h,cpp}`) — confirmer si actif (option CMake `ENABLE_XTTS=ON`) ou en attente du proxy Orpheus.

---

## 8. Dépendances Python (`requirements*.txt`)

| Fichier | Contenu | Audit |
|---|---|---|
| `requirements.txt` | méta : `-r base` + `-r ml` | ✅ propre |
| `requirements-base.txt` | aiohttp, websockets, pytest, pytest-asyncio | ✅ minimal |
| `requirements-ml.txt` | faster-whisper, hyperpyyaml, **conformer**, **modelscope**, torch 2.4, torchaudio 2.4, soundfile, transformers 4.40-4.55, numpy, silero-vad, onnxruntime, noisereduce, openwakeword, faiss-cpu, sentence-transformers | ⚠️ **`conformer` et `modelscope`** : restes de la pile CosyVoice (déjà supprimée selon le contexte) — probablement obsolètes. |
| `services/orpheus/requirements.txt` | (séparé) llama-cpp-python CUDA + snac | ✅ isolé en venv dédié |

→ **Vérifier** si `conformer` / `modelscope` / `hyperpyyaml` sont encore importés dans `python/`. Si non, supprimables.

---

## 9. Logs / Caches

### `logs/` (25.6 MB)
17 services × 2 fichiers (`<svc>.log` + `<svc>.err.log`) + `exo_*.log`, `gui.log`, `launcher.log`, `exo_pids.json`. Tous datés 2026-05-16 (run actuel). Politique de rotation à confirmer.

### `cache/` (534 MB)
- `huggingface/` : 534 MB (modèles téléchargés HF par sentence-transformers / transformers).
- ✅ Ajouté à `.gitignore` le 2026-05-16 (commit `d160969`).

### `__test_mem_dir__/`
Contient `metadata_v2.json` à la racine du dépôt → **artefact de test mal localisé** (devrait être sous `tests/` ou `.gitignore`).

---

## 10. Fichiers racine — anomalies

### 10.1 WAV à la racine (1.4 MB total)
| Fichier | Taille | Origine probable |
|---|---:|---|
| `audit_orpheus.wav` | 465 KB | Audit Orpheus (sortie de test) |
| `test_instruct2.wav` | 613 KB | Test TTS |
| `test_fr_nofrontend.wav` | 178 KB | Test FR sans frontend |
| `test_fr_zero_shot.wav` | 150 KB | Test FR zero-shot |
| `orpheus_stream_capture.wav` | 133 KB | Capture stream Orpheus |

→ Candidats à déplacer vers `tests/fixtures/audio/` ou `docs/audits/audio/samples/`.

### 10.2 `spk_list.txt`, `build_log.txt`
- `spk_list.txt` (0.6 KB) — speaker list, peut-être référencé par la pile TTS XTTS supprimée.
- `build_log.txt` (162 KB) — log de build à la racine, devrait être dans `logs/` ou gitignoré.

### 10.3 Scripts dupliqués (`scripts/`)
| Fichier | Doublon de | Décision suggérée |
|---|---|---|
| `bench_tts_5x.py` | `bench_tts_10x.py` | Garder un seul (paramétrable) |
| `cleanup.ps1` + `cleanup_phase2.ps1` | — | Vérifier si `phase2` complète ou remplace |

---

## 11. Documentation — doublons massifs (16 paires)

Pattern systématique : `docs/X.md` (3-37 KB, contenu réel) coexiste avec `docs/audits/<categorie>/X.md` (0.2 KB, **stub**).

| Vrai contenu (à conserver) | Stub à investiguer |
|---|---|
| `docs/GUI_AUDIT.md` (13.3 KB) | `docs/audits/gui/GUI_AUDIT.md` (0.2 KB) |
| `docs/BACKEND_AUDIT.md` (26.8 KB) | `docs/audits/backend/BACKEND_AUDIT.md` (0.2 KB) |
| `docs/GUI_CONNECTIVITY_AUDIT.md` (24 KB) | `docs/audits/gui/GUI_CONNECTIVITY_AUDIT.md` (0.2 KB) |
| `docs/GUI_DEAD_CODE_AUDIT.md` (5.1 KB) | `docs/audits/gui/GUI_DEAD_CODE_AUDIT.md` (0.2 KB) |
| `docs/GUI_MEMORY_AUDIT.md` (13.8 KB) | `docs/audits/gui/GUI_MEMORY_AUDIT.md` (0.2 KB) |
| `docs/GUI_PERF_AUDIT.md` (8.9 KB) | `docs/audits/gui/GUI_PERF_AUDIT.md` (0.2 KB) |
| `docs/GUI_RESTRUCTURE.md` (8.1 KB) | `docs/audits/gui/GUI_RESTRUCTURE.md` (0.2 KB) |
| `docs/SIGNALS_AUDIT.md` (9.9 KB) | `docs/audits/backend/SIGNALS_AUDIT.md` (0.2 KB) |
| `docs/INVENTORY_FINAL_AUDIO_AUDIT.md` (12 KB) | `docs/audits/audio/...` (0.2 KB) |
| `docs/MANIFEST_AUDIO_AUDIT.md` (11.5 KB) | `docs/audits/audio/...` (0.2 KB) |
| `docs/README_AUDIO_AUDIT.md` (10.7 KB) | `docs/audits/audio/...` (0.2 KB) |
| `docs/TTS_MODEL_NOT_LOADED_FIX_REPORT.md` (3.6 KB) | `docs/audits/audio/...` (0.2 KB) |
| `docs/TTS_PROVIDER_ROOT_CAUSE_REPORT.md` (5.7 KB) | `docs/audits/audio/...` (0.2 KB) |
| `docs/UX_REDESIGN_PLAN.md` (37.8 KB) | `docs/audits/gui/UX_REDESIGN_PLAN.md` (0.2 KB) |
| `docs/ACCOMPLISHMENTS_AUDIO_AUDIT.md` (14.4 KB) | `docs/audits/audio/...` (0.2 KB) |
| `docs/audits/AUDIT_GUI_QML_MEMORY_2026-04.md` (27.2 KB, vrai) | `docs/audits/gui/AUDIT_GUI_QML_MEMORY_2026-04.md` (0.2 KB stub) |

**Hypothèse** : la migration `docs/X.md` → `docs/audits/<cat>/X.md` a créé les stubs (probablement des redirections en frontmatter) mais les vrais fichiers n'ont pas été déplacés. **Lire 1-2 stubs pour confirmer leur contenu** (redirection ? déprécation ?) avant toute opération.

Aussi présents :
- `docs/audits/qml_dead_scan_2026-05-01.json` ↔ `docs/audits/gui/qml_dead_scan_2026-05-01.json` (à comparer)
- `docs/audits/qml_dead_scan_post_cleanup_2026-05-01.json` ↔ `docs/audits/gui/qml_dead_scan_post_cleanup_2026-05-01.json`

---

## 12. Tests (`tests/`)

### 12.1 Cohérent
- `tests/cpp/` : 11 fichiers test_*.cpp + CMakeLists.txt → ✅ utilisés par `BUILD_TESTS=ON`.
- `tests/python/archive/` : v9-v25 (21 fichiers) — déjà archivés.
- `tests/integration/`, `tests/performance/` : 1 fichier chacun.

### 12.2 SUSPECTS (versions historiques en racine `tests/python/`)
| Fichier | Statut probable |
|---|---|
| `test_agent_v10.py` | versionné — à archiver si v11+ existe |
| `test_context_engine_v8.py` | doublon de `test_context_engine.py` |
| `test_memory_v2.py`, `test_memory_v8.py` | versionnés — `test_memory_server.py` existe |
| `test_pipeline_v82.py` | versionné isolé |
| `test_task_planner_v8.py` | doublon de `test_task_planner.py` |

→ Aligner sur le pattern `tests/python/archive/test_v*.py` déjà établi.

---

## 13. Synthèse — tables ACTIFS / SUSPECTS / OBSOLÈTES PROBABLES / DUPLIQUÉS

### 🟢 ACTIFS (à préserver absolument)
- Tous les services VS Code (15/16 — sauf `tts_server`)
- `app/` (162 fichiers C++/H, 100% mappés CMake)
- `qml/` (50 fichiers, 100% mappés `qt_add_qml_module`)
- `models/orpheus_fr_gguf/Orpheus-3b-French-FT-Q8_0.gguf`, `models/whisper/ggml-small.bin`
- `assets/icons/app/exo.*`, `resources/fonts/Roboto-Regular.ttf`
- `services/orpheus/{server_ws.py, server_gguf.py, models_manifest.json, start_orpheus.ps1}`
- `python/shared/`, `python/domotique/`, `python/network/`
- `requirements-base.txt`

### 🟡 SUSPECTS (vérification manuelle requise avant action)
| Élément | Raison |
|---|---|
| `python/tts/tts_server.py` | **manquant alors que référencé par 13 fichiers** |
| `models/orpheus_fr_gguf/Orpheus-3b-French-FT-Q5_K_M.gguf` (2.28 GB) | référencé uniquement par bench |
| `models/orpheus_fr_gguf/Orpheus-3b-French-FT-Q6_K.gguf` (2.59 GB) | idem |
| `python/orchestrator/explainability_engine_v5.py` | suffixe `_v5` (v2-v4-v6 archivés) |
| `python/orchestrator/symbolic_explainability_v2.py` | suffixe `_v2` |
| `python/orchestrator/knowledge_graph_v2.py` | doublon `knowledge_graph.py` |
| `python/orchestrator/pipeline_v9.py` | suffixe versionné |
| `python/orchestrator/global_supervisor_v5.py` | suffixe versionné |
| `tests/python/test_*_v{2,8,10,82}.py` (6 fichiers) | versionnés non archivés |
| `requirements-ml.txt` : `conformer`, `modelscope`, `hyperpyyaml` | restes pile CosyVoice supprimée |
| `services/orpheus/{ab_validate_j2.py, bench_quants*}` | scripts bench A/B (gardés si benchs réguliers) |

### 🔴 OBSOLÈTES PROBABLES (haute confiance, mais NON supprimés)
| Élément | Justification |
|---|---|
| 16 stubs `docs/audits/<cat>/X.md` (0.2 KB) | redondants avec contenu réel sous `docs/X.md` |
| `build_log.txt` (162 KB racine) | log de build, devrait être en `logs/` |
| `__test_mem_dir__/metadata_v2.json` | artefact test mal localisé |
| WAV racine (5 fichiers, 1.4 MB) | échantillons de test/audit non déplacés |
| `scripts/bench_tts_5x.py` OR `scripts/bench_tts_10x.py` | doublon paramétrique |

### 🔁 DUPLIQUÉS (paires identiques par nom, contenu différent)
- 16 paires docs (cf §11)
- 2 paires `qml_dead_scan*.json` (cf §11)
- `tests/python/test_context_engine.py` ↔ `test_context_engine_v8.py`
- `tests/python/test_memory_server.py` ↔ `test_memory_v2.py` ↔ `test_memory_v8.py`
- `tests/python/test_task_planner.py` ↔ `test_task_planner_v8.py`

---

## 14. Recommandations d'investigation (avant tout `rm`)

1. **🔴 PRIORITÉ 1** — Décider du sort de `python/tts/tts_server.py` (créer shim Orpheus OU refactorer 13 références).
2. Lire 2-3 stubs `docs/audits/<cat>/X.md` pour confirmer s'ils sont des redirections ou de vrais documents tronqués.
3. `grep -r "from orchestrator.explainability_engine_v5\|from orchestrator.symbolic_explainability_v2\|from orchestrator.knowledge_graph_v2\|from orchestrator.pipeline_v9\|from orchestrator.global_supervisor_v5"` — voir si encore importés.
4. `grep -r "import conformer\|import modelscope\|import hyperpyyaml"` dans `python/` — confirmer obsolescence.
5. Vérifier `services/orpheus/server_gguf.py:79` : Q5/Q6 chargés en config par défaut ou seulement en bench ?
6. Confirmer politique de rétention `logs/` et taille cible `cache/`.

---

## 15. Volume total estimé récupérable (si validations OK)

| Source | Espace | Conditions |
|---|---:|---|
| Modèles Q5/Q6 GGUF | ~4.87 GB | si benchs gelés |
| Cache HF (`cache/`) | 534 MB | déjà gitignoré, peut être purgé localement |
| Stubs docs | < 5 KB | impact symbolique |
| WAV racine + `build_log.txt` + `__test_mem_dir__` | ~1.6 MB | déplacement, pas suppression |
| Tests versionnés | ~quelques KB | déplacement vers `archive/` |
| Doublons orchestrator | ~quelques KB | si imports zéro |

**Gain disque réel potentiel : ~5.4 GB** (essentiellement modèles GGUF non production).

---

**FIN DU RAPPORT — aucune action destructive effectuée.**
