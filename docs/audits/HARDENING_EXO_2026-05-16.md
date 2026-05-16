# HARDENING EXO — 2026-05-16

> Objectif : rendre EXO plus **robuste**, **résilient**, **stable**, **sécurisé**,
> **cohérent** et **tolérant aux erreurs**, **sans jamais casser** les composants
> critiques (Orpheus Q8, Whisper C++, WebSocket audio, pipeline audio,
> orchestrateur LLM).

## 1. Stratégie adoptée

Mass-edit destructeur impossible sur 250+ fichiers Python + 100+ fichiers C++ +
dizaines de QML. La stratégie retenue est **modulaire et incrémentale** :

1. **Fondations partagées** réutilisables (`python/shared/`, `app/utils/`).
2. **Câblage automatique** via `python/shared/__init__.py` — tout service qui
   importe `shared.*` hérite immédiatement de l'`excepthook` global.
3. **Composants QML wrappers** non invasifs (`SafeButton.qml`).
4. **Préflight** au démarrage (`launch_exo_silent.ps1`) — détection précoce des
   manques (modèles, binaires, ports, venvs).
5. **Aucune modification** des fichiers EXCLUS par la politique du projet.

## 2. Composants EXCLUS (jamais touchés)

| Langage | Fichier | Raison |
|---|---|---|
| Python | `services/orpheus/server_ws.py` | TTS production critique |
| Python | `services/orpheus/server_gguf.py` | LLM GGUF critique |
| Python | `python/stt/server_stt.py` (et équivalents) | Whisper C++ |
| C++ | `app/audio/VoicePipeline.cpp` | Boucle audio temps-réel |
| C++ | `app/audio/AudioEngine.cpp` | Moteur audio bas niveau |
| C++ | `app/audio/WebSocketClient.cpp` | Transport audio |
| C++ | `app/audio/OrpheusDecoder.cpp` | Décodage PCM Orpheus |
| QML | IDs, bindings, imports existants | Compat. Qt6 |

## 3. Modules livrés (Python)

### 3.1 `python/shared/hardening.py` (nouveau)

Toolkit défensif central :

- **`install_global_excepthook()`** — idempotent, intercepte `sys.excepthook`,
  `threading.excepthook` et `asyncio` loop exception handler. Loggue toutes les
  exceptions non rattrapées via `logging.getLogger("exo.hardening")`.
- **Préflight** :
  - `preflight_file(path, min_size_bytes=0)` — existence + taille.
  - `preflight_port_free(port)` / `preflight_port_listen(host, port)` — état réseau.
  - `preflight_model_gguf(path)` — magic `b"GGUF"` + taille min 1 MiB.
  - `preflight_binary(path)` — exécutabilité (Windows / POSIX X_OK).
  - `preflight_dependencies([modules])` — importlib loop.
  - Retourne un `PreflightReport` (errors / warnings / ok / `is_ok` / `summary()`).
- **JSON sûr** :
  - `safe_json_loads(raw, *, default=None)` — capture JSONDecodeError/TypeError/ValueError.
  - `safe_json_dumps(obj, *, default="{}")`.
- **`with_timeout(coro_or_callable, timeout_s, *args, fallback=None, label, **kwargs)`** —
  supporte coroutines, coroutine functions et callables synchrones (via
  `run_in_executor`). Retourne `fallback` sur expiration au lieu de lever.
- **`debounce_async(min_interval_s=0.25)`** — décorateur (verrou asyncio).
- **`RateLimiter(max_events, period_s)`** — token-bucket thread-safe.

### 3.2 `python/shared/config_validator.py` (nouveau)

Validation défensive des `config/*.json` au démarrage :

- `validate_config_file(path, *, required_keys, port_keys, path_keys, defaults)`
- Détection automatique des **collisions de ports** entre clés.
- Application de **valeurs par défaut** avec trace `fixed`.
- **Ne lève jamais** — retourne `ConfigValidationReport(file, errors, warnings, fixed, data, is_ok, summary())`.

### 3.3 `python/shared/ws_resilient.py` (nouveau)

Helpers WebSocket défensifs (services périphériques uniquement) :

- **`WsBackoff`** — exponentiel borné (initial 0.5 s, max 30 s, factor 2.0) +
  jitter ±20 % + **rate-limit anti-tempête** (20 reconnexions/min ⇒ pause 60 s).
- **`parse_ws_message(raw, *, default={})`** — défensif (str/bytes/dict), log
  structuré si non-dict ou JSON invalide.
- **`safe_send_json(ws, payload, timeout_s=5.0, label=…)`** — compatible
  `websockets`, `aiohttp` et tout objet exposant `send()`. Retourne `bool`.
- **`make_reconnect_loop(connect, on_connected, backoff, label)`** — boucle de
  reconnexion défensive, encaisse `CancelledError` proprement.

### 3.4 `python/shared/__init__.py` (modifié)

- Exporte tous les symboles ci-dessus (`hardening`, `ws_resilient`,
  `config_validator`).
- **Appelle `install_global_excepthook()` à l'import** — tout service qui fait
  `from shared import …` hérite automatiquement de la capture globale.

## 4. Modules livrés (C++ / Qt6)

### 4.1 `app/utils/Hardening.h` (nouveau, opt-in)

Macros défensives qui routent via `qWarning(…)` → `LogManager` → panneau GUI
« Journaux » (déjà francisé phase précédente).

- **Macros préconditions** (toutes en français) :
  - `EXO_REQUIRE_PTR(ptr, msgFr)` / `EXO_REQUIRE_PTR_RET(ptr, msgFr, retVal)`
  - `EXO_REQUIRE_SIZE(value, minSz, msgFr)` (cast `qsizetype`)
  - `EXO_REQUIRE_RANGE(value, lo, hi, msgFr)`
  - `EXO_SAFE_DIV(num, den, fallback)` — anti-division-par-zéro.
  - `EXO_REQUIRE_OK(expr, msgFr)`, `EXO_REQUIRE_STATE(cond, msgFr)`.
- **Namespace `exo::hardening`** :
  - `Throttle(minIntervalMs)` — `QHash<QString,QElapsedTimer>` + `QMutex`,
    méthodes `allow(key)` / `reset(key)`.
  - `ExpBackoff(initialMs=250, maxMs=30000, factor=2.0)` — `next()` / `reset()`
    / `current()`.
  - `LatencyWatchdog(thresholdMs)` — `tick()` retourne `bool` + `qWarning` si
    dépassement (utilisable dans audio non-exclu).

> **Opt-in** : aucun fichier existant n'est modifié. Les modules audio non
> critiques peuvent intégrer ces macros progressivement.

## 5. Composants livrés (QML)

### 5.1 `qml/components/SafeButton.qml` (nouveau)

Wrapper anti-clic-multiple, **compatible** avec le pattern `ExoButton` :

- **`debounceMs`** (défaut 350 ms) — intervalle minimal entre deux émissions de
  `safeClicked`.
- **`busy`** — verrou visuel (opacité 0.45 + curseur d'attente).
- **`autoReleaseMs`** — libération automatique si le backend ne répond pas
  (anti-état-bloqué).
- **`precondition`** — fonction QML retournant `bool` (validation locale).
- Signaux : `safeClicked`, `clicked` (compat, non-débouncé), `blocked(reason)`
  pour diagnostic (`"disabled"`, `"busy"`, `"debounce"`, `"precondition"`,
  `"precondition_error"`).
- Méthode : `releaseBusy()` pour libérer manuellement après réponse backend.

Inscrit dans `qml/components/qmldir`.

## 6. Préflight launcher (`launch_exo_silent.ps1`)

Section **« Preflight Hardening 2026 »** ajoutée dans `Start-EXO`,
juste après la résolution des venvs et avant le démarrage des services :

- **Test-Path** sur 7 cibles critiques : `whisper-cli.exe`, modèle Whisper
  `ggml-small.bin`, dossier `models/orpheus_fr_gguf`, venv Orpheus, venv
  principal, venv STT/TTS, `RaspberryAssistant.exe`.
- **Test-PortListening** sur ports 8766–8777 (avertissement si déjà occupé).
- Compteur d'erreurs critiques + bilan `OK` / `WARN`.
- **Politique** : mode dégradé toléré (poursuite tentée), aucune fenêtre
  visible, journal complet dans `D:\EXO\logs\launcher.log`.

## 7. Politique de démarrage strict (rappel)

> Conformément à la mémoire utilisateur `exo-launch-policy.md` :
>
> **SEULE commande autorisée** pour démarrer EXO :
>
> ```powershell
> powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass `
>   -File "D:\EXO\launch_exo_silent.ps1"
> ```
>
> Stop/Restart/Status : dot-sourcer puis `Stop-EXO` / `Restart-EXO` /
> `Get-EXOStatus`. PID store : `D:\EXO\logs\exo_pids.json`.

## 8. Validation

| Contrôle | Résultat |
|---|---|
| Import `python.shared` + sous-modules | OK (15 symboles publics dont `RateLimiter`, `WsBackoff`, `ConfigValidationReport`, `PreflightReport`, `install_global_excepthook`) |
| Lint Python (Pylance) sur 4 nouveaux fichiers | 0 erreur |
| `validate_config_file('config/services.json')` | Détecte correctement « Racine non-objet : list » (services.json est une liste — comportement attendu) |
| Inscription `SafeButton` dans `qmldir` | OK |
| Préflight launcher | Section ajoutée, compatible Write-Launcher (Level `OK` validé) |

## 9. Récapitulatif des fichiers

**Créés** :

- [python/shared/hardening.py](python/shared/hardening.py)
- [python/shared/config_validator.py](python/shared/config_validator.py)
- [python/shared/ws_resilient.py](python/shared/ws_resilient.py)
- [app/utils/Hardening.h](app/utils/Hardening.h)
- [qml/components/SafeButton.qml](qml/components/SafeButton.qml)

**Modifiés** (ajouts uniquement, aucune régression) :

- [python/shared/__init__.py](python/shared/__init__.py) — exports + auto-install excepthook
- [qml/components/qmldir](qml/components/qmldir) — déclaration `SafeButton`
- [launch_exo_silent.ps1](launch_exo_silent.ps1) — section préflight dans `Start-EXO`

**Non touchés (politique d'exclusion stricte respectée)** :

- `services/orpheus/server_ws.py`, `services/orpheus/server_gguf.py`,
  `python/stt/server_stt.py` (et équivalents).
- `app/audio/VoicePipeline.cpp`, `app/audio/AudioEngine.cpp`,
  `app/audio/WebSocketClient.cpp`, `app/audio/OrpheusDecoder.cpp`.
- Aucun ID, binding ou import QML existant.

## 10. Étapes suivantes recommandées (hors scope immédiat)

- Intégrer `LatencyWatchdog` dans les sinks audio non-exclus
  (`TTSAudioSinkRtAudio.cpp`, `AudioInputRtAudio.cpp`).
- Brancher `validate_config_file` au boot de `exo_server.py` pour `services.json`
  (variante liste) et tout futur `config/*.json` objet.
- Démontrer `make_reconnect_loop` dans un service périphérique (ex : NLU) sans
  toucher au transport audio.
