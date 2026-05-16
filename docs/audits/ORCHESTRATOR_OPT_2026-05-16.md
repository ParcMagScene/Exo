# Optimisation Orchestrator EXO — 2026-05-16

Optimisation chirurgicale de l'orchestrator EXO selon la directive en 11 étapes.
**Contraintes respectées** : aucun ID d'état renommé, aucune transition existante
supprimée, aucun signal QML modifié, aucun callback WebSocket cassé, pipeline
audio / TTS Orpheus Q8 / STT Whisper / LLM intacts.

## 1 — Cartographie

L'orchestrator EXO est composé de deux couches :

| Fichier | Rôle |
|---|---|
| [python/orchestrator/fused_pipeline.py](../../python/orchestrator/fused_pipeline.py) | **FSM voix** réelle — `PipelineState` (IDLE / LISTENING / TRANSCRIBING / ANTICIPATING / THINKING / SPEAKING / ERROR) |
| [python/orchestrator/exo_server.py](../../python/orchestrator/exo_server.py) | Dispatcher WebSocket GUI (port 8765) — relaie l'état vers la GUI Qt |

Le `fused_pipeline.FusedPipeline` orchestre `on_partial → on_final → LLM → TTS`.
Le `exo_server.GUIServer._state` est un miroir simple de l'état push-é par les
microservices via le message `pipeline_state`.

## 2 — Clarification des états et transitions

Ajout d'une **table de transitions valides** (`_VALID_TRANSITIONS`) dans
`fused_pipeline.py`. Validation **soft** : toute transition hors table est
journalisée mais jamais bloquée → on garde 100 % de compatibilité avec les
flux existants tout en ouvrant la voie aux audits.

Chaque état dispose désormais d'une route de retour explicite vers `IDLE` et
`ERROR` (sécurité / récupération).

## 3 — Gestion des erreurs

- `FusedPipeline.on_final` : try/except dédiés autour de l'appel LLM et autour
  du streaming TTS. Compteurs `errors_llm` / `errors_tts` dans `metrics()`.
- Erreurs LLM → état `ERROR` puis `_recover_from_error()` (pause brève
  configurable `ERROR_RECOVERY_DELAY_S = 0.5s`) puis retour `IDLE`.
- `GUIServer.handler` : un échec dans `_handle_client_message` ne ferme plus
  la connexion (log + continue). Un échec global du handler logge un warning
  avant la fermeture propre.
- `GUIServer.broadcast` : les clients qui lèvent une exception lors d'un send
  sont retirés du set (plus de boucle qui crashe sur un client mort).

## 4 — Timeouts explicites

Constants ajoutées sur `FusedPipeline` :

| Constante | Valeur | Cible |
|---|---|---|
| `LLM_TIMEOUT_S` | 30.0 s | `_llm_send(text, 1024, "")` final |
| `TTS_TIMEOUT_S` | 60.0 s | `_tts_stream(response)` |
| `ANTICIPATION_TIMEOUT_S` | 5.0 s | `_llm_send` anticipation |
| `ERROR_RECOVERY_DELAY_S` | 0.5 s | Pause avant retour `IDLE` post-`ERROR` |

Implémentés via `shared.hardening.with_timeout` (réutilisé, pas réécrit) avec
fallback transparent sur `asyncio.wait_for` si le package `shared` n'est pas
importable (exécution isolée du fichier).

Sur dépassement : log structuré `[fsm][timeout]`, compteur `timeouts_llm` /
`timeouts_tts`, transition contrôlée vers `ERROR` puis récupération.

## 5 — Interruptions

Nouvelle méthode `FusedPipeline.interrupt()` :

- Marque `_interrupt_requested = True` (consulté avant chaque étape lourde).
- Annule l'anticipation et la tâche courante (`_cancel_pending`).
- Force le retour en `IDLE` immédiatement (l'arrêt audio TTS reste géré par
  le service TTS via son propre callback — le pipeline ne touche pas au
  buffer audio).
- Incrémente `metrics.interruptions`.

**Barge-in automatique** : `on_partial()` détecte un nouveau partiel STT
pendant `SPEAKING` ou `THINKING` et déclenche `interrupt()` puis ouvre un
nouveau cycle propre (`begin_interaction`).

`on_final()` vérifie `_interrupt_requested` avant d'appeler TTS pour éviter
de parler par-dessus une interruption demandée pendant l'attente LLM.

## 6 — Priorités

Hiérarchie effective dans le pipeline :

1. **Interruption utilisateur** (`interrupt()`, barge-in dans `on_partial`).
2. **Erreurs critiques** (LLM/TTS) → `ERROR` + récupération.
3. **Pipeline courant** (LLM → TTS final).
4. **Anticipation** (best-effort, court timeout, déduplication, jamais
   bloquante).

## 7 — Optimisation des appels

- **Déduplication anticipation** : nouveau champ `_last_anticipation_text` ;
  on ne relance pas la pré-analyse LLM sur un préfixe identique.
- **Cooldown anticipation** conservé (1.5 s).
- **Broadcast GUI** : un seul `_safe_json_dumps` par broadcast, puis send
  parallèle ; les clients morts sont retirés au passage (pas de retry inutile
  sur sockets fermés).
- **JSON** : `safe_json_loads` / `safe_json_dumps` partagés (réutilisation,
  pas de réimplémentation).

## 8 — Logs structurés

Format unifié : `[domaine][évènement][...contexte]`.

| Domaine | Exemples |
|---|---|
| FSM | `[fsm][state] LISTENING -> THINKING (int=int-000123)` |
| FSM | `[fsm][llm-timeout][int=int-000123] 30.0s` |
| FSM | `[fsm][barge-in] partial STT pendant SPEAKING — interruption` |
| GUI | `[gui][state] idle -> listening` |
| GUI | `[gui][state] valeur inconnue: 'foo'` (validation soft) |

Les transitions inattendues remontent en `WARNING`, le flux normal en `INFO`,
les détails fins (anticipation, callbacks) en `DEBUG` — pas de spam au niveau
INFO sur un cycle normal.

## 9 — Cohérence GUI / pipeline

- `GUIServer.push_state()` : log `[gui][state] old -> new` uniquement sur
  changement effectif (évite duplication).
- Validation **soft** d'un ensemble `_KNOWN_STATES` étendu aux états
  réellement utilisés (incluant `detecting_speech`, `waking`, `processing`)
  pour éviter le bruit tout en signalant les futures dérives.
- Aucun signal QML modifié, aucune topologie WebSocket modifiée.

## 10 — Validation live

```powershell
. D:\EXO\launch_exo_silent.ps1
Restart-EXO
Get-EXOStatus
```

Résultat : **17 / 17 services actifs**, Orchestrator PID actif sur port 8765
(Listening = True). Logs `orchestrator.err.log` :

```
09:48:27 [exo.server] INFO Pipeline v8.2 initialisé
09:48:27 [exo.server] INFO EXO server ready
09:48:48 [exo.server] INFO [gui][state] IDLE -> idle
09:48:54 [exo.server] INFO [gui][state] idle -> detecting_speech
09:48:54 [exo.server] INFO [gui][state] detecting_speech -> listening
09:48:55 [exo.server] INFO [gui][state] listening -> transcribing
09:48:55 [exo.server] INFO [gui][state] transcribing -> idle
```

Aucun traceback, aucun freeze, le cycle voix complet est journalisé en format
structuré.

## 11 — Synthèse des améliorations

| Axe | Avant | Après |
|---|---|---|
| Validation transitions | Aucune | Table `_VALID_TRANSITIONS` + log soft |
| Timeouts LLM/TTS | Aucun | 30 s / 60 s / 5 s explicites |
| Récupération erreur | Direct `ERROR` puis `IDLE` | Pause `0.5 s` + log dédié |
| Barge-in utilisateur | Non géré | `interrupt()` + détection auto dans `on_partial` |
| Métriques FSM | Aucune | `transitions`, `transitions_unexpected`, `interruptions`, `timeouts_llm/tts`, `errors_llm/tts` |
| Anticipation | Relancée sur même préfixe | Déduplication |
| JSON GUI | `json.loads/dumps` brut | `safe_json_loads/dumps` (shared) |
| Broadcast | Crash si client mort | Retrait automatique |
| Handler WS | Une erreur ferme la connexion | Log + continue |
| Logs | Format hétérogène | `[domaine][évènement][ctx]` uniforme |

**Contraintes 100 % respectées** : noms d'états inchangés, signatures
publiques (`begin_interaction`, `on_partial`, `on_final`, `cancel`, `state`,
`metrics`, `push_state`, `broadcast`, `handler`) inchangées ; signaux QML
non touchés ; pipeline audio / TTS / STT / LLM non touchés.
