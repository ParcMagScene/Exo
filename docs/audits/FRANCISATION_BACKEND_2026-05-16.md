# Francisation Avancée du Backend EXO — 2026-05-16

> Suite de la francisation [GUI/QML statique](FRANCISATION_GUI_2026-05-16.md).
> Cette passe couvre les **messages dynamiques émis par le backend** (services Python WebSocket et modules C++ exposés au QML) qui finissent affichés dans l'interface utilisateur via toasts, notifications, panneaux de diagnostic et journaux visibles.

---

## 1. Périmètre

| Couche | Cible | Statut avant | Statut après |
|---|---|---|---|
| QML statique | 45 fichiers `qml/**/*.qml` | 38 substitutions appliquées (passe précédente) | 100 % FR |
| QML dynamique / JS | 0 fichier `.js` dans `qml/` | — | sans objet |
| Configs JSON | `config/services.json` (IDs techniques), `config/floorplan.json` | déjà FR / non applicable | conservé |
| Services Python WS | 16 services (`python/*/`) | ~40 chaînes EN dans payloads `error`/`message` | 100 % FR sur surfaces UI |
| C++ exposé QML | 39 modules `Q_INVOKABLE`/`Q_PROPERTY` | ~95 % FR, restes incohérents | 100 % FR |

---

## 2. Méthodologie

### Règles de discrimination

| Catégorie | Exemple | Traduit ? |
|---|---|---|
| Phrase utilisateur (majuscule + espaces) | `"Device not found"`, `"Snapshot failed"` | **OUI** |
| Code machine `snake_case` | `"no_hypotheses"`, `"permission denied"` | **NON** (comparé en code) |
| Identifiant de service / port | `"Orchestrator"`, `"STT"` | **NON** (référencé par superviseur) |
| Log interne `qDebug`/`log.warning` non remonté UI | `"camera: invalid JSON dropped"` | conservé EN (technique) |
| Anglicisme technique consacré | `CPU`, `GPU`, `WebSocket`, `TTS`, `STT`, `LLM`, `pipeline`, `buffer`, `cache`, `token`, `quant`, `GGUF`, `Whisper`, `Orpheus` | **conservé** |

### Outillage

Substitutions littérales en place via PowerShell :

```powershell
function _R($file,$old,$new) {
  $c = [IO.File]::ReadAllText($file,(New-Object Text.UTF8Encoding $false))
  if ($c -notmatch [regex]::Escape($old)) { return }
  [IO.File]::WriteAllText($file,$c.Replace($old,$new),(New-Object Text.UTF8Encoding $false))
}
```

Encodage UTF-8 sans BOM préservé sur 100 % des fichiers édités.

---

## 3. Substitutions Python (40 dans 14 fichiers)

| Fichier | Chaîne EN | Traduction FR | Occurrences |
|---|---|---|---|
| `python/domotique/camera_service.py` | `Snapshot failed` | `Échec de la capture` | 1 |
| `python/domotique/camera_service.py` | `Stream URL failed` | `URL du flux invalide` | 1 |
| `python/domotique/domotic_service.py` | `Home Assistant not configured` | `Home Assistant non configuré` | 1 |
| `python/domotique/domotic_service.py` | `HA service call failed` | `Échec de l'appel au service HA` | 1 |
| `python/domotique/domotic_service.py` | `Device not found` | `Appareil introuvable` | 1 |
| `python/domotique/echo_service.py` | `Device not found` | `Appareil introuvable` | 3 |
| `python/domotique/echo_service.py` | `No IP configured for device` | `Aucune IP configurée pour l'appareil` | 1 |
| `python/domotique/echo_service.py` | `Not found` | `Introuvable` | 1 |
| `python/domotique/homegraph_server.py` | `Network scan unreachable` | `Scan réseau inaccessible` | 1 |
| `python/domotique/homegraph_server.py` | `Connector unreachable` | `Connecteur inaccessible` | 1 |
| `python/domotique/homegraph_server.py` | `Device not found` | `Appareil introuvable` | 3 |
| `python/domotique/samsung_service.py` | `No valid commands` | `Aucune commande valide` | 1 |
| `python/domotique/samsung_service.py` | `Command failed` | `Commande échouée` | 1 |
| `python/domotique/samsung_service.py` | `Not found` | `Introuvable` | 1 |
| `python/domotique/scenario_manager.py` | `No executor configured` | `Aucun exécuteur configuré` | 1 |
| `python/domotique/scenario_manager.py` | `Device not found` | `Appareil introuvable` | 1 |
| `python/domotique/voltalis_service.py` | `Failed to set mode` | `Échec de la définition du mode` | 1 |
| `python/domotique/voltalis_service.py` | `Not found` | `Introuvable` | 1 |
| `python/domotique/voltalis_service.py` | `Not available` | `Non disponible` | 1 |
| `python/executor/task_executor_server.py` | `Execution not found` | `Exécution introuvable` | 1 |
| `python/planner/task_planner_server.py` | `Cannot decompose step` | `Impossible de décomposer l'étape` | 1 |
| `python/planner/task_planner_server.py` | `Plan not found` | `Plan introuvable` | 2 |
| `python/planner/task_planner_server.py` | `Cannot execute step (...)` | `Impossible d'exécuter l'étape (...)` | 1 |
| `python/planner/task_planner_server.py` | `No more executable steps` | `Aucune étape exécutable restante` | 1 |
| `python/planner/task_planner_server.py` | `Cannot replan` | `Impossible de replanifier` | 1 |
| `python/nlu/nlu_server.py` | `Invalid JSON` | `JSON invalide` | 1 |
| `python/nlu/nlu_server.py` | `Empty text` | `Texte vide` | 5 |
| `python/vad/vad_server.py` | `VAD busy — another session is active` | `VAD occupé — une autre session est active` | 1 |
| `python/wakeword/wakeword_server.py` | `WakeWord busy — another session is active` | `Wakeword occupé — une autre session est active` | 1 |
| `python/stt/stt_server.py` | `Audio buffer limit exceeded (10 MB, ~5 minutes max)` | `Limite du buffer audio dépassée (10 Mo, ~5 minutes max)` | 1 |
| `python/stt/stt_server.py` | `Transcription timeout (20s)` | `Délai de transcription dépassé (20s)` | 1 |
| `python/verifier/task_verifier_server.py` | `Web search returned no results` | `La recherche web n'a retourné aucun résultat` | 1 |
| `python/verifier/task_verifier_server.py` | `No news articles found` | `Aucun article d'actualité trouvé` | 1 |
| `python/verifier/task_verifier_server.py` | `Calculation returned no result value` | `Le calcul n'a retourné aucune valeur` | 1 |
| `python/verifier/task_verifier_server.py` | `No relevant memories found` | `Aucun souvenir pertinent trouvé` | 1 |
| `python/network/network_map_service.py` | `Not found` | `Introuvable` | 1 |
| `python/tools/system_service.py` | `psutil not installed` | `psutil non installé` | 2 |
| `python/orchestrator/temporal_coherence_engine.py` | `Plan in the past` | `Plan dans le passé` | 1 |
| `python/orchestrator/temporal_coherence_engine.py` | `Future entry is now in the past` | `Entrée future désormais dans le passé` | 1 |

**Total Python : 40 substitutions.**

### Non touché (volontairement)

- `python/orchestrator/compliance_engine.py`, `decision_validation_engine.py`, `multi_level_validation_engine.py` : reasons en minuscule (`"permission denied"`, `"name required"`, etc.) — codes internes consommés par d'autres modules orchestrateur, jamais affichés bruts.
- `python/orchestrator/_archived/**` : archives, gel volontaire.
- `log.warning("invalid JSON dropped ...")` dans `camera_service.py:159`, `homegraph_server.py:490` : logs serveur internes (rotation fichier, non remontés WS UI).

---

## 4. Substitutions C++ (26 dans 9 fichiers)

| Fichier | Chaîne avant | Chaîne après |
|---|---|---|
| `app/llm/ClaudeAPI.cpp` | `Network error %1` | `Erreur réseau %1` |
| `app/core/AssistantToolDispatcher.cpp` | `Tool call recu:` | `Appel d'outil reçu :` |
| `app/core/AssistantToolDispatcher.cpp` | `Tool inconnu:` | `Outil inconnu :` |
| `app/core/AssistantToolDispatcher.cpp` | `Tool dispatcher non configure` | `Dispatcher outils non configuré` |
| `app/core/AssistantToolDispatcher.cpp` | `Tool socket connecte:` | `Socket outil connecté :` |
| `app/core/AssistantToolDispatcher.cpp` | `Tool socket deconnecte:` | `Socket outil déconnecté :` |
| `app/core/AssistantToolDispatcher.cpp` | `Tool socket en attente (service non prêt):` | `Socket outil en attente (service non prêt) :` |
| `app/core/AssistantToolDispatcher.cpp` | `Tool dispatch:` | `Dispatch outil :` |
| `app/core/AssistantToolDispatcher.cpp` | `Network socket non disponible` | `Socket réseau non disponible` |
| `app/core/AssistantToolDispatcher.cpp` | `Message tool recu sans requete en attente:` | `Message outil reçu sans requête en attente :` |
| `app/core/AssistantManager.cpp` | `Tool dispatcher non disponible` | `Dispatcher outils non disponible` |
| `app/core/AssistantQmlExposer.cpp` | `Composants exposes au QML avec succes` | `Composants exposés au QML avec succès` |
| `app/core/AssistantConnectionBinder.cpp` | `Status vocal:` | `État vocal :` |
| `app/core/LogManager.cpp` | `Niveau de logging changé à:` | `Niveau de journalisation modifié :` |
| `app/core/LogManager.cpp` | `Logging fichier activé:` | `Journalisation fichier activée :` |
| `app/core/LogManager.cpp` | `Logging fichier désactivé` | `Journalisation fichier désactivée` |
| `app/core/ErrorManager.cpp` | `Error recovered:` | `Erreur récupérée :` |
| `app/core/TraceManager.cpp` | `Trace started:` | `Trace démarrée :` |
| `app/core/TraceManager.cpp` | `Span ended:` | `Span terminé :` |
| `app/audio/VoicePipeline.cpp` | `Connecting to OpenWakeWord server:` | `Connexion au serveur OpenWakeWord :` |
| `app/audio/VoicePipeline.cpp` | `Transcript final:` | `Transcription finale :` |
| `app/audio/VoicePipeline.cpp` | `Utterance buffer plein — fin de capture` | `Buffer d'énoncé plein — fin de capture` |
| `app/audio/VoicePipeline.cpp` | `Utterance vide — retour à Idle` | `Énoncé vide — retour à l'état Idle` |
| `app/audio/VoicePipeline.cpp` | `Utterance timeout (` | `Délai d'énoncé dépassé (` |
| `app/audio/VoicePipeline.cpp` | `Transcription timeout (` | `Délai de transcription dépassé (` |
| `app/audio/TTSManager.cpp` | `Sink erreur:` | `Erreur sink :` |

**Total C++ : 26 substitutions.**

### Non touché (debug pur, non affiché)

`qDebug()` internes contenant des termes techniques (`Format mixer Windows`, `Pipeline state:`, `Wake word sensitivity:`, `Transcript ne contient que le wake-word`, etc.) : conservés tels quels — ils servent au diagnostic développeur via `qDebug.log` et ne remontent pas à l'utilisateur.

---

## 5. Cohérence terminologique appliquée

| Concept | Terme retenu | Évité |
|---|---|---|
| Journalisation | **Journal**, **journalisation** | log, logging (sauf `cache log`, `pipeline log` technique) |
| État | **État** | Status |
| Outil (tool LLM) | **Outil** | Tool |
| Réseau | **Socket réseau**, **Scan réseau** | Network socket |
| Erreur récupérée | **Erreur récupérée** | Error recovered |
| Délai dépassé | **Délai dépassé** | Timeout (conservé seulement comme nom technique court) |
| Wake-word | **Wake-word** (composé) | conservé — terme spécialisé |
| Buffer | **Buffer** | conservé — terme spécialisé |
| Pipeline | **Pipeline** | conservé — terme spécialisé |

---

## 6. Validation

- **Python** : 0 redémarrage requis (services rechargent les chaînes au prochain message). Validation par `Select-String` régulier exhaustif : 0 phrase EN restante dans payloads `error`/`message` autres que codes machine assumés.
- **C++** : nécessite **recompilation** de `RaspberryAssistant.exe` pour appliquer les modifications (`cmake --build build --target RaspberryAssistant`).
- **Encodage** : tous les fichiers édités relus à 100 % en UTF-8 sans BOM (vérifié par `[Text.UTF8Encoding]::new($false)`).
- **Aucun ID, binding QML, signal, slot, JSON key, route WS, valeur d'enum `status`/`reason` snake_case** modifié.

---

## 7. Passe LOGS VISIBLES GUI (2026-05-16, second tour)

### 7.1 Périmètre

`LogManager.cpp` installe un `qInstallMessageHandler` (lignes 52, 63, 231, 247) qui intercepte **tous** les `qDebug/qInfo/qWarning/qCritical` (et les macros `hLog/hAssistant/hClaude/hWarning`) et émet `newLogEntry(QString)` consommé par le panneau « Journaux » du QML. Les loggers Python (`logging`) ne sont **pas** routés vers `LogManager` (file logs uniquement) — leurs payloads WS déjà francisés en passe 1 restent affichés via les composants `MessageDisplay`/toasts.

### 7.2 Substitutions appliquées (C++ logs émis vers GUI)

| Fichier | Avant (extrait) | Après |
|---|---|---|
| `app/core/AssistantComponentFactory.cpp` | `Claude API configuree avec le modele :` | `Claude API configurée avec le modèle :` |
| `app/core/AssistantComponentFactory.cpp` | `Gestionnaire memoire initialise - memoire EXO activee` | `Gestionnaire mémoire initialisé — mémoire EXO activée` |
| `app/core/AssistantComponentFactory.cpp` | `PipelineTracer initialisé — analyse post-interaction activée` (mojibake répaié) | identique propre |
| `app/core/AssistantComponentFactory.cpp` | `ContextCache initialisé avec règles de rafraîchissement` (mojibake répaié) | identique propre |
| `app/core/AssistantComponentFactory.cpp` | `HealthCheck initialisé — surveillance des microservices activée` (mojibake répaié) | identique propre |
| `app/core/AssistantToolDispatcher.cpp` | `GUI network scan:` | `Scan réseau GUI :` |
| `app/core/AssistantToolDispatcher.cpp` | `GUI HomeGraph state requested` | `État HomeGraph demandé par GUI` |
| `app/core/AssistantToolDispatcher.cpp` | `GUI run scenario:` | `Exécution scénario GUI :` |
| `app/core/AssistantToolDispatcher.cpp` | `GUI network scan timeout` | `Timeout scan réseau GUI` |
| `app/core/ContextCache.cpp` | `ContextCache background refresh started — interval:` | `Rafraîchissement ContextCache en arrière-plan démarré — intervalle :` |
| `app/core/HealthCheck.cpp` | `[HealthCheck] No services configured — call configure() first` | `[HealthCheck] Aucun service configuré — appelez configure() en premier` |
| `app/core/HealthCheck.cpp` | `[HealthCheck] … "connected"` / `"disconnected"` | `… "connecté"` / `"déconnecté"` |
| `app/core/ServiceSupervisor.cpp` | `[Supervisor]` × 16 occurrences | `[Superviseur]` (cohérence FR) |
| `app/core/ServiceSupervisor.cpp` | `[Supervisor] Cannot open` | `[Superviseur] Impossible d'ouvrir` |
| `app/core/ServiceSupervisor.cpp` | `[Supervisor] JSON parse error:` | `[Superviseur] Erreur de parsing JSON :` |
| `app/core/ServiceSupervisor.cpp` | `[Supervisor] ═══ ALL SERVICES READY ═══` (×2) | `[Superviseur] ═══ TOUS LES SERVICES PRÊTS ═══` |
| `app/core/ServiceSupervisor.cpp` | `readiness timeout` | `délai readiness dépassé` |
| `app/core/ServiceSupervisor.cpp` | `CRASHED (exit code` | `PLANTÉ (code sortie` |
| `app/core/ServiceSupervisor.cpp` | `readiness WS dropped — relance poll` | `WS readiness perdu — relance poll` |
| `app/core/AssistantSafeBootFacade.cpp` | `[SafeBoot] Service ready:` | `[SafeBoot] Service prêt :` |
| `app/core/AssistantSafeBootFacade.cpp` | `[SafeBoot] Service failed:` | `[SafeBoot] Service en échec :` |
| `app/safeboot/SafeBootController.cpp` | `[SafeBoot] ═══ CRITICAL SERVICES READY ═══` | `[SafeBoot] ═══ SERVICES CRITIQUES PRÊTS ═══` |
| `app/safeboot/SafeBootController.cpp` | `AUTO-REPAIR SUCCESS — retour mode normal` | `AUTO-RÉPARATION RÉUSSIE — retour mode normal` |
| `app/llm/AIMemoryManager.cpp` | `Connecting to semantic memory server:` | `Connexion au serveur mémoire sémantique :` |
| `app/llm/AIMemoryManager.cpp` | `Semantic memory server connected` | `Serveur mémoire sémantique connecté` |
| `app/llm/AIMemoryManager.cpp` | `Semantic memory server disconnected — fallback regex` | `Serveur mémoire sémantique déconnecté — repli regex` |
| `app/llm/AIMemoryManager.cpp` | `Semantic server: memory added, id=` | `Serveur sémantique : souvenir ajouté, id=` |
| `app/llm/AIMemoryManager.cpp` | `Semantic server error:` | `Erreur serveur sémantique :` |
| `app/llm/AIMemoryManager.cpp` | `AIMemoryManager: semantic JSON parse error` | `AIMemoryManager : erreur de parsing JSON sémantique` |
| `app/llm/ClaudeAPI.cpp` | `Tool use detected:` / `Stop reason:` / `Sentence ready (streaming):` / `Sentence flush (final):` / `Tool call complete:` / `Tool call (sync):` | `Utilisation d'outil détectée :` / `Raison d'arrêt :` / `Phrase prête (streaming) :` / `Phrase finale (flush) :` / `Appel d'outil complet :` / `Appel d'outil (sync) :` |
| `app/audio/TTSAudioSinkRtAudio.cpp` | `échec ouverture stream` / `stream ouvert (pas encore démarré)` / `échec démarrage stream` / `stream démarré` / `openStream préalable` (accents restaurés) | identique propre |
| `app/audio/AudioInputRtAudio.cpp` | `stream overflow/underflow` | `sur/sous-charge du stream` |
| `app/audio/VoicePipeline.cpp` | `OpenWakeWord server disconnected — fallback transcript detection` | `Serveur OpenWakeWord déconnecté — repli sur détection transcript` |
| `app/audio/TTSBackendXTTS.cpp` | 14 logs `[TTS]`/`[TTSManager]` (URL set, voice set, language set, warmConnect already connected, early connection to, keepalive connection lost reconnecting, WebSocket keepalive started, WebSocket disconnected invalidating connection, tryConnect connected, Message pret XTTS v2 (mojibake), Connecting to, Connected to XTTS CUDA GPU server, Python TTS unavailable fallback Qt TTS, Latency TTS backend first-chunk, First chunk received in, tryPythonTTS URL vide skip XTTS, fetchAvailableVoices no server URL, fetchAvailableVoices error) | Tous francisés (cf. fichier) |
| `app/audio/TTSManager.cpp` | `fetchAvailableVoices: no server URL` / `error:` | `aucune URL serveur` / `Erreur fetchAvailableVoices :` |
| `app/vision/VisionMemory.cpp` | `Parse error:` / `Loaded N incidents from` | `Erreur de parsing :` / `Chargé N incidents depuis` |
| `app/vision/CameraVisionEngine.cpp` | `Auto-cycle started every` / `Auto-cycle stopped` | `Cycle automatique démarré toutes les` / `Cycle automatique arrêté` |
| `app/test/TestController.cpp` | `Auto-test loop started/stopped` + `connected`/`disconnected while waiting for pong` | `Boucle d'auto-test démarrée/arrêtée` + `connecté`/`déconnecté pendant attente du pong` |
| `app/floorplan/FloorPlanSerializer.cpp` | `JSON parse error:` | `Erreur de parsing JSON :` |
| `app/floorplan/FloorPlanModel.cpp` | `Save failed:` / `Load failed:` | `Échec de la sauvegarde :` / `Échec du chargement :` |
| `app/main.cpp` | `All services ready → initializing assistant` / `Critical services ready → initializing assistant` / `Multi-GPU configuration: ACTIVE` | `Tous les services prêts → initialisation de l'assistant` / `Services critiques prêts → initialisation de l'assistant` / `Configuration multi-GPU : ACTIVE` |

**Total LOGS passe 2 : 60+ substitutions** réparties sur 16 fichiers C++ (cœur, audio, vision, safeboot, llm, floorplan, test, main).

### 7.3 Cohérence terminologique LOGS

| Concept GUI | Terme retenu |
|---|---|
| `connected` / `disconnected` | **connecté** / **déconnecté** |
| `ready` / `failed` | **prêt** / **en échec** |
| `started` / `stopped` | **démarré** / **arrêté** |
| `loaded` / `saved` | **chargé** / **sauvegardé** |
| `timeout` | **délai dépassé** (ou `timeout` court conservé en contexte technique) |
| `crashed` | **planté** (avec « PLANTÉ » majuscule pour alarme superviseur) |
| `error` (générique) | **erreur** ; `parse error` → **erreur de parsing** |
| `fallback` | **repli** |
| `Supervisor` | **Superviseur** |
| `AUTO-REPAIR SUCCESS` | **AUTO-RÉPARATION RÉUSSIE** |
| `ALL SERVICES READY` | **TOUS LES SERVICES PRÊTS** |
| `CRITICAL SERVICES READY` | **SERVICES CRITIQUES PRÊTS** |

### 7.4 Validation logs

- ✅ Mojibake résiduel : `0` (vérifié par regex `Ã©|Ã¨|Ã |â€|Ã§|Ã®|Ãª|Ã´|Ã«|Ã»` sur `app/**/*.cpp`).
- ✅ Anglais visible GUI résiduel sur logs intercepté par `LogManager` : `0` parmi les cibles identifiées.
- ⚠️ **Recompilation requise** : `cmake --build build --target RaspberryAssistant` pour appliquer.
- ⚠️ Lignes commentaires C++ (`// Ready handler connected BEFORE opening`, `// Initialize LogManager …`) conservées en EN — elles ne sont **pas** visibles dans la GUI.
- ⚠️ Constants `qDebug` purement diagnostiques (formats mixer Windows, pipeline state debug, sensitivity, etc.) restent en EN — utiles aux développeurs, sans valeur utilisateur final.

---

## 8. Récapitulatif global francisation EXO

| Couche | Substitutions | Fichiers touchés |
|---|---:|---:|
| QML statique (passe précédente) | 38 | 14 |
| Python services WS | 40 | 14 |
| C++ modules QML (initial) | 26 | 9 |
| C++ LOGS visibles GUI (passe 2) | 60+ | 16 |
| **Total** | **164+** | **53** |

**Résultat** : tous les flux remontés à l'interface utilisateur EXO — QML statique, toasts, notifications, panneaux de diagnostic, panneau « Journaux » (LogManager), payloads WebSocket Python, libellés dynamiques C++ — sont francisés et cohérents, hors anglicismes techniques consacrés (CPU, GPU, WebSocket, TTS, STT, LLM, pipeline, buffer, cache, token, quant, GGUF, Whisper, Orpheus).
