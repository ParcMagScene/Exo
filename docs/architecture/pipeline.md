# NOTE : Depuis la migration 2026-05, tous les chemins EXO sont sous D:/EXO/<nom>/ (voir docs/index.md).
# Pipeline vocal EXO — FSM et flux

Mis à jour 2026-05-16 (FULL SAFE REFACTOR).

## États (FSM applicative)

```
idle
  → detecting_speech   (VAD : énergie > seuil)
  → listening          (capture audio en cours, wakeword acquis)
  → transcribing       (STT whisper.cpp, port 8766)
  → thinking           (LLM claude-opus-4.7 via orchestrateur 8765)
  → speaking           (TTS Orpheus, port 8767, streaming SNAC)
  → idle
```

Barge-in : tout évènement VAD `frame_speech` reçu pendant `speaking` interrompt
le TTS et bascule directement en `listening` (cf. `app/audio/VoicePipeline.cpp`,
invariant — non modifié).

## Flux WebSocket

```
[mic] ─▶ VAD (8770) ─▶ wakeword (8771) ─┐
                                        ▼
                              orchestrateur (8765) ◀─▶ NLU (8773)
                                  │   │   │             context (8774)
                                  │   │   │             memory (8772)
                                  │   │   │             planner (8775)
                                  │   │   │             executor (8776)
                                  │   │   │             verifier (8777)
                                  │   │   │             tools (8783) / websearch (8780) /
                                  │   │   │             news (8781) / knowledge (8782) /
                                  │   │   │             system (8778)
                                  │   │   ▼
                                  │   │  LLM claude-opus-4.7
                                  │   ▼
                                  │  STT (8766) — whisper.cpp Vulkan AMD RX 6750 XT
                                  ▼
                                 TTS (8767) — Orpheus 3B FR GGUF Q8 + SNAC ─▶ [haut-parleur]
```

Protocoles JSON et signatures **non modifiables** (invariant strict).

## Budgets de latence (cibles)

| Étape                          | Cible        | Référence mesurée |
|--------------------------------|--------------|-------------------|
| Warmup STT (whisper small)     | < 400 ms     | 297 ms (audit)    |
| Premier token TTS              | < 350 ms     | dépend Orpheus    |
| Boucle complète (court énoncé) | < 2 s        | —                 |

Le watchdog optionnel `LatencyWatchdog` (`app/utils/Hardening.h`) est
activable via la variable d'environnement `EXO_AUDIO_WATCHDOG_MS` (opt-in,
désactivé par défaut).

## Résilience

- Reconnexion WS exponentielle bornée (`shared.ws_resilient.WsBackoff`).
- CircuitBreaker par service distant (`shared.resilience.CircuitBreaker`,
  seuil 3 échecs, cooldown 15 s, paramètres `BaseService.CB_*`).
- `shared.hardening.with_timeout` enveloppe les opérations critiques et
  loggue les exceptions sans les propager.
- `singleton_guard.ensure_single_instance` interdit le double démarrage par
  service.

## Observabilité

- Logs JSON-line par service via `shared.log_manager`.
- Helper `shared.log_event(logger, domaine, évènement, **ctx)` pour le
  format applicatif normalisé `[domaine][évènement] k=v`.
- Métriques exposées par `shared.metrics_manager`, traces par
  `shared.trace_manager`, erreurs structurées par `shared.error_manager`.
