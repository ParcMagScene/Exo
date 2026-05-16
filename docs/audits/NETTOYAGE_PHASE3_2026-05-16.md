# RAPPORT NETTOYAGE PHASE 3 — Doc & Scripts

**Date** : 2026-05-16 (après-midi/soir)
**Périmètre** : harmonisation documentation + suppression scripts obsolètes/doublons + alignement LLM/TTS.
**Politique** : suppressions sur consentement explicite par lot (cf interview utilisateur), aucune modification du code source fonctionnel C++/Python/QML productif.

> Phases 1 et 2 du nettoyage déjà exécutées le même jour (cf [NETTOYAGE_RAPPORT_2026-05-16.md](NETTOYAGE_RAPPORT_2026-05-16.md)) : 104 items / 4,89 Go libérés, shim TTS Orpheus créé, `requirements-ml.txt` purgé, EXO 17/17 services UP.

---

## 1. Lot 1 — Évidences (risque nul)

| Action | Cible | Statut |
|---|---|---|
| Patch README L33 | `Claude Sonnet SSE` → `Claude Opus 4.7 (SSE)` (cohérence consigne LLM verrouillée) | ✅ |
| Patch README L25 | `Claude API (SSE + Function Calling)` → `Claude Opus 4.7 (SSE + Function Calling)` | ✅ |
| Patch README §Démarrage | `.\launch_exo.ps1` → `launch_exo_silent.ps1` (policy stricte silencieuse) | ✅ |
| Supprimé | `docs/audits/audio/` (vide post-Phase 1) | ✅ |
| Supprimé | `docs/audits/backend/` (vide) | ✅ |
| Supprimé | `docs/audits/gui/` (vide) | ✅ |
| Supprimé | `docs/audits/pipeline/` (vide, jamais peuplé) | ✅ |
| Supprimé | `docs/audits/services/` (vide, jamais peuplé) | ✅ |
| Supprimé | `scripts/cleanup_phase2.ps1` (one-shot exécuté) | ✅ |
| Régénéré | `docs/index.md` (anti-doublons, refs réelles post-Phase 1+2+3, politique LLM/TTS explicite) | ✅ |

## 2. Lot 2 — Consolidation scripts

| Action | Cible | Justification |
|---|---|---|
| Supprimé | `scripts/bench_tts_5x.py` | Doublon paramétrique de `bench_tts_10x.py` |
| Supprimé | `scripts/maintain_docs.py` | Englobé par `auto_maintain.py` (commande `docs`) |
| Supprimé | `scripts/normalize_docs.py` | Idem |
| Conservé | `scripts/auto_maintain.py` | 30 KB, utilisé par `setup_maintenance.ps1` (cron) |
| Conservé | `scripts/bench_tts_10x.py` | Référencé bench régulier |
| Conservé | `scripts/_aggregate_profile.ps1` + `runtime_profiler.ps1` + `runtime_profile_report.ps1` | Pipeline profilage actif |

## 3. Lot 3 — Décisions

### 3.1 Launcher legacy (`launch_exo.ps1`)
| Action | Statut |
|---|---|
| Supprimé `launch_exo.ps1` (visible, contenait branches XTTS L157-173) | ✅ |
| Patch `scripts/create_desktop_shortcut.ps1` → pointe vers `launch_exo_silent.ps1` + `-WindowStyle Hidden` | ✅ |

**Conséquence** : seul `launch_exo_silent.ps1` reste comme point d'entrée — conforme à la policy `EXO launch policy (strict)`.

### 3.2 Tests versionnés archivés (6 fichiers)
Déplacés `tests/python/` → `tests/python/archive/` :
- `test_agent_v10.py`
- `test_context_engine_v8.py`
- `test_memory_v2.py`
- `test_memory_v8.py`
- `test_pipeline_v82.py`
- `test_task_planner_v8.py`

Pattern aligné sur l'existant `tests/python/archive/v9-v25/`.

### 3.3 Modules orchestrator versionnés — **ROLLBACK**
Tentative d'archivage de 5 modules (`explainability_engine_v5`, `symbolic_explainability_v2`, `knowledge_graph_v2`, `pipeline_v9`, `global_supervisor_v5`). **Rollback immédiat** après détection : `docs/audits/OPTIMISATION_FINALE_2026-05-16.md` §3 indique explicitement *« Tous ont ≥ 1 import actif »* via `_version_registry.create_all_versions` (lazy load) dans `python/orchestrator/exo_server.py:57`. Modules **restaurés en place** ✅. Aucune perte fonctionnelle.

### 3.4 Audits caducs supprimés (16 fichiers, ~270 KB)
Tous figés au 2026-04 ou 2026-05-01, contenu rendu obsolète par Phase 1+2+3 et par les rapports actifs 2026-05-16 :

| Fichier supprimé |
|---|
| `docs/GUI_AUDIT.md` |
| `docs/BACKEND_AUDIT.md` |
| `docs/SIGNALS_AUDIT.md` |
| `docs/GUI_CONNECTIVITY_AUDIT.md` |
| `docs/GUI_DEAD_CODE_AUDIT.md` |
| `docs/GUI_MEMORY_AUDIT.md` |
| `docs/GUI_PERF_AUDIT.md` |
| `docs/GUI_RESTRUCTURE.md` |
| `docs/UX_REDESIGN_PLAN.md` |
| `docs/ACCOMPLISHMENTS_AUDIO_AUDIT.md` |
| `docs/INVENTORY_FINAL_AUDIO_AUDIT.md` |
| `docs/MANIFEST_AUDIO_AUDIT.md` |
| `docs/README_AUDIO_AUDIT.md` |
| `docs/TTS_MODEL_NOT_LOADED_FIX_REPORT.md` |
| `docs/TTS_PROVIDER_ROOT_CAUSE_REPORT.md` |
| `docs/audits/AUDIT_GUI_QML_MEMORY_2026-04.md` |

Aucune référence externe depuis le code (Python, C++, QML, JSON) — seules occurrences résiduelles dans rapports d'audit historiques eux-mêmes figés.

---

## 4. État après Phase 3

### 4.1 Documentation `docs/` (vue finale)
- 3 rapports perf : `PERF_REPORT_J1-J5.md`, `PERF_REPORT_J2-J3bis-J4bis.md`, `PROFILING_LOAD_REPORT.md`
- `index.md` régénéré
- `CONTRIBUTING_DOCS.md` + `.structure.lock`
- `audits/` : 7 rapports 2026-05-16 (PRE_NETTOYAGE, NETTOYAGE_RAPPORT, NETTOYAGE_PHASE3 [ce fichier], HARDENING_EXO, OPTIMISATION_FINALE, ORCHESTRATOR_OPT, FRANCISATION_BACKEND, FRANCISATION_GUI) + 2 snapshots JSON QML
- `architecture/`, `implementation/`, `troubleshooting/` : structures conservées

### 4.2 Scripts `scripts/` (vue finale)
- Maintenance : `auto_maintain.py`, `setup_maintenance.ps1`, `auto_kill_zombies.py`, `cleanup.ps1`
- Bench/profil : `bench_tts_10x.py`, `benchmark_stt.py`, `audit_orpheus_wav.py`, `runtime_profiler.ps1`, `runtime_profile_report.ps1`, `_aggregate_profile.ps1`, `_franc_logs_batch.ps1`
- Build/install : `check_dependencies.ps1`, `install_dependencies.ps1`, `quick_build.ps1`, `verify_project.ps1`, `test_environment.ps1`, `create_desktop_shortcut.ps1`
- Diagnostic : `diagnose_tts_provider.ps1`, `patch_ujson.ps1`
- Génération : `generate_icon.py`, `generate_toc.py`
- Hooks git : `hooks/pre-commit`, `hooks/post-commit`

### 4.3 Racine `D:\EXO\` (vue finale)
| Type | Fichiers |
|---|---|
| Doc | `README.md`, `CHANGELOG.md`, `PROMPT_MAITRE.md`, `.copilot-instructions.md` |
| Build | `CMakeLists.txt`, `pyproject.toml`, `requirements*.txt` |
| Launch | **`launch_exo_silent.ps1`** (unique entrée), `copy_exo_logs.ps1` |
| Config | `spk_list.txt` |

---

## 5. Vérifications post-nettoyage

| Vérification | Résultat |
|---|---|
| Aucune référence active vers `launch_exo.ps1` (hors rapports figés) | ✅ |
| Aucune référence active vers scripts supprimés (hors rapports figés) | ✅ |
| Aucune référence active vers audits caducs supprimés | ✅ |
| Modules orchestrator versionnés restaurés (rollback) | ✅ |
| C++/Python/QML/JSON config non modifiés | ✅ |
| Politique LLM `claude-opus-4.7` préservée et harmonisée dans README | ✅ |
| Politique TTS Orpheus-only préservée | ✅ |
| Pas de réintroduction XTTS/QtTTS/SAPI | ✅ |
| `launch_exo_silent.ps1` intact | ✅ |
| `services/orpheus/server_ws.py` intact (avec compat `LEGACY_XTTS_VOICES` sécurité) | ✅ |

---

## 6. Bilan global (Phase 1+2+3)

| Phase | Items | Espace |
|---|---:|---:|
| Phase 1 (stubs + dossiers vides) | 25 | 165,9 ko |
| Phase 2 (GGUF + logs + bench + WAV + shim TTS) | 84 | ~4,89 Go |
| **Phase 3 (doc/scripts harmonisation)** | **27 supprimés + 6 archivés + 4 patchés + 1 régénéré** | ~370 ko + cohérence doc |
| **TOTAL** | **~152 items** | **~4,89 Go + dette doc résorbée** |

**FIN PHASE 3.**
