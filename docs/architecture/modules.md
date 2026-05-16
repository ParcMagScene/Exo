# NOTE : Depuis la migration 2026-05, tous les chemins EXO sont sous D:/EXO/<nom>/ (voir docs/index.md).
# Index des modules EXO

Mis à jour 2026-05-16 (FULL SAFE REFACTOR).

## Python — couche partagée `python/shared/`

| Module                  | Rôle                                                              |
|-------------------------|-------------------------------------------------------------------|
| `base_service`          | `BaseService(name, port)` : WS, ping, circuit-breaker, retry      |
| `log_manager`           | Logger JSON-line, rotation 10 MB×3, `ContextVar` request/session  |
| `log_event`             | Helper `log_event(logger, domaine, évènement, **ctx)` (nouveau)   |
| `hardening`             | `safe_json_*`, `with_timeout`, `RateLimiter`, `debounce_async`,
                            `install_global_excepthook`, `preflight_*`         |
| `ws_resilient`          | `WsBackoff`, `parse_ws_message`, `safe_send_json`, reconnect loop |
| `config_validator`      | `validate_config_file(...) → ConfigValidationReport`              |
| `config_manager`        | Singleton de configuration (lecture `config/exo_v9.json`)         |
| `security_manager`      | Politique de sécurité côté service                                |
| `supervisor_manager`    | Supervision intra-service                                         |
| `trace_manager`         | Traces structurées                                                |
| `metrics_manager`       | Métriques temps réel                                              |
| `error_manager`         | `ExoError` + catégorisation                                       |
| `resilience`            | `CircuitBreaker`                                                  |
| `singleton_guard`       | `ensure_single_instance`                                          |
| `graceful_shutdown`     | Arrêt propre                                                      |
| `cache`                 | Cache mémoire bornée                                              |

## Python — services applicatifs

Voir `docs/architecture/services.md` pour la liste exhaustive (ports,
venvs, fichiers).

## Python — orchestrateur `python/orchestrator/`

- `exo_server.py` (entrée principale, port 8765, validation `exo_v9.json`).
- Moteurs : routage WS, supervision globale, dispatch NLU/contexte/planner.
- Les modules suffixés `_vX` (versions historiques) sont gelés (zones
  intouchables, cf. `docs/AUDIT_PRE_NETTOYAGE_2026-05-16.md`).

## Python — domaines métier

- `python/domotique/` — pont domotique.
- `python/network/` — utilitaires réseau partagés.
- `python/memory/` — index vectoriel FAISS + persistance.
- `python/nlu/`, `python/context/`, `python/planner/`,
  `python/executor/`, `python/verifier/` — chaîne intent → action.
- `python/tools/` — outils LLM + service système.
- `python/websearch/`, `python/news/`, `python/knowledge/` — IO externes.
- `python/stt/`, `python/tts/`, `python/vad/`, `python/wakeword/` — audio.

## Services natifs

- `services/orpheus/server_ws.py` + `server_gguf.py` — backend TTS Orpheus
  3B FR GGUF Q8 (port 8767). **Zone strictement intouchable.**

## C++ — application Qt (`app/`)

| Sous-module          | Contenu (résumé)                                            |
|----------------------|-------------------------------------------------------------|
| `app/main.cpp`       | Point d'entrée Qt                                           |
| `app/audio/`         | `AudioEngine`, `VoicePipeline`, `WebSocketClient`,
                         `OrpheusDecoder` — **zones intouchables**           |
| `app/core/`          | Cœur applicatif (état, dispatch)                            |
| `app/floorplan/`     | Plan d'étage / spatial                                      |
| `app/llm/`           | Interface LLM côté client                                   |
| `app/safeboot/`      | Démarrage protégé                                           |
| `app/simulation/`    | Mode simulation                                             |
| `app/spatialcognition/`, `app/spatialsecurity/` | Cognition spatiale     |
| `app/test/`          | Tests C++ (non modifiés)                                    |
| `app/utils/`         | `Hardening.h` (LatencyWatchdog opt-in), `SafeIO.h`,
                         `WeatherManager`                                    |
| `app/vision/`        | Vision                                                      |

## QML (`qml/`)

50 fichiers, **zones intouchables** (aucun `id`, aucun layout ne doit
bouger).

## Build C++

Qt 6.9.3 / CMake / MSVC 2022, sortie
`D:/EXO/build/Release/RaspberryAssistant.exe`.

## Tests Python

Répertoire `tests/python/` (venv `.venv` requis pour pytest). Aucun test
existant ne doit être modifié — seuls de nouveaux tests sont ajoutés.
Dernières additions (2026-05-16) : `test_log_event.py`,
`test_config_validator.py` (en complément de `test_ws_resilient.py`).
