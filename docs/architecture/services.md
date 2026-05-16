# NOTE : Depuis la migration 2026-05, tous les chemins EXO sont sous D:/EXO/<nom>/ (voir docs/index.md).
# Services EXO — Inventaire

Mis à jour 2026-05-16 (FULL SAFE REFACTOR).
Source d'autorité : `D:/EXO/launch_exo_silent.ps1` + `D:/EXO/config/exo_v9.json`.

Tous les services sont des microservices WebSocket Python pilotés par
`launch_exo_silent.ps1` (silencieux, idempotent, PID store
`D:/EXO/logs/exo_pids.json`).

## Démarrage / arrêt / statut (politique stricte)

```powershell
powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass \
    -File "D:\EXO\launch_exo_silent.ps1"

. D:\EXO\launch_exo_silent.ps1
Get-EXOStatus    # 22/22 UP attendus
Stop-EXO
Restart-EXO
```

Aucun service ne doit être démarré individuellement (cf.
`docs/HARDENING_EXO_2026-05-16.md`).

## Inventaire (ports fixes — invariants)

| Service             | Port | Venv               | Fichier                                       | Rôle                                                       |
|---------------------|-----:|--------------------|-----------------------------------------------|------------------------------------------------------------|
| `exo_server`        | 8765 | `.venv_stt_tts`    | `python/orchestrator/exo_server.py`           | Orchestrateur principal, routage WS, validation config     |
| `stt_server`        | 8766 | `.venv_stt_tts`    | `python/stt/stt_server.py`                    | Transcription whisper.cpp Vulkan (small.bin)               |
| `tts_server`        | 8767 | `.venv_stt_tts`    | `python/tts/tts_server.py`                    | Wrapper TTS Orpheus (proxy `services/orpheus/server_ws.py`) |
| `vad_server`        | 8770 | `.venv_stt_tts`    | `python/vad/vad_server.py`                    | Voice activity detection                                   |
| `wakeword_server`   | 8771 | `.venv_stt_tts`    | `python/wakeword/wakeword_server.py`          | Détection « hey exo »                                      |
| `memory_server`     | 8772 | `.venv_stt_tts`    | `python/memory/memory_server.py`              | Mémoire sémantique FAISS                                   |
| `nlu_server`        | 8773 | `.venv_stt_tts`    | `python/nlu/nlu_server.py`                    | Compréhension d'intentions                                 |
| `context_server`    | 8774 | `.venv_stt_tts`    | `python/context/context_engine.py`            | Suivi de contexte conversationnel                          |
| `planner_server`    | 8775 | `.venv_stt_tts`    | `python/planner/task_planner_server.py`       | Planification de tâches                                    |
| `executor_server`   | 8776 | `.venv_stt_tts`    | `python/executor/task_executor_server.py`     | Exécution de plans                                         |
| `verifier_server`   | 8777 | `.venv_stt_tts`    | `python/verifier/task_verifier_server.py`     | Vérification de résultats                                  |
| `system_server`     | 8778 | `.venv_stt_tts`    | `python/tools/system_service.py`              | Outils système (cmds locales)                              |
| `websearch_server`  | 8780 | `.venv`            | `python/websearch/websearch_server.py`        | Recherche web                                              |
| `news_server`       | 8781 | `.venv`            | `python/news/news_server.py`                  | Actualités                                                 |
| `knowledge_server`  | 8782 | `.venv`            | `python/knowledge/knowledge_server.py`        | Base de connaissances                                      |
| `tools_server`      | 8783 | `.venv`            | `python/tools/tools_server.py`                | Outils LLM (function-calls)                                |
| `orpheus` (interne) | 8767 | dédié              | `services/orpheus/server_ws.py` + `server_gguf.py` | Backend TTS Orpheus 3B FR GGUF Q8 + SNAC                |
| `domotique`         | —    | `.venv_stt_tts`    | `python/domotique/`                            | Pont domotique (intégration via orchestrateur)            |

Deux venvs distincts :
- `.venv_stt_tts` (audio + ML lourd, sans pytest) ;
- `.venv` (tests + services HTTP).

## Politique LLM

Modèle unique : `claude-opus-4.7`. Aucun fallback, aucune température ni
`top_p` / `top_k`. Voir `docs/HARDENING_EXO_2026-05-16.md` §LLM lock.

## Politique TTS

Orpheus 3B FR GGUF Q8 (3.35 GB) exclusif sur le port `8767`. XTTS, QtTTS et
SAPI sont interdits.

## Journaux

- `D:/EXO/logs/<service>.log` (stdout)
- `D:/EXO/logs/<service>.err.log` (stderr)
- `D:/EXO/logs/<service>.jsonl` (structuré via `shared.log_manager`)
- `D:/EXO/logs/launcher.log` (journal du lanceur)
- `D:/EXO/logs/exo_pids.json` (PID store)

Format des messages applicatifs (helper `shared.log_event`) :
`[domaine][évènement] k1=v1 k2=v2 ...`.
