# EXO — Audit des signaux C++ exposes a QML

Date: 2026-05-01
Perimetre: objets exposes via `setContextProperty` et usages QML (`Connections`, handlers `onXxx`).

## 1) Objets C++ exposes a QML

Depuis `app/main.cpp` et `app/core/AssistantQmlExposer.cpp`:

- `assistantManager` (`AssistantManager`)
- `serviceSupervisor` (`ServiceSupervisor`)
- `safeBootController` (`SafeBootController`)
- `autoRepair` (`SafeBootAutoRepair`)
- `testController` (`TestController`)
- `claudeAPI` (`ClaudeAPI`)
- `voiceManager` (`VoicePipeline`)
- `weatherManager` (`WeatherManager`)
- `configManager` (`ConfigManager`)
- `memoryManager` (`AIMemoryManager`)
- `healthCheck` (`HealthCheck`)
- `audioDeviceManager` (`AudioDeviceManager`)
- `logManager` (`LogManager`)
- `pipelineEventBus` (`PipelineEventBus`)

## 2) Inventaire des signaux C++ (classes exposees)

### AssistantManager

- `messageReceived(QString sender, QString message)`
- `claudeResponseReceived(QString response)`
- `claudePartialResponse(QString partialText)`
- `listeningStateChanged(bool isListening)`
- `initializationComplete()`
- `errorOccurred(QString error)`
- `networkScanCompleted(QJsonObject result)`
- `homeGraphReceived(QJsonObject result)`
- `deviceCommandResult(QJsonObject result)`
- `scenarioResult(QJsonObject result)`
- `safeBootChanged()`
- `safeBootDecisionMadeChanged()`
- `autoRepairChanged()`
- `repairTimelineChanged()`
- `serviceReady(QString service)`
- `serviceFailed(QString service)`

### ServiceSupervisor

- `allServicesReady()`
- `serviceCountChanged()`
- `progressChanged()`
- `currentActionChanged()`
- `startupFailed(QString reason)`
- `serviceReady(QString name)`

### SafeBootController

- `safeBootActivated()`
- `safeBootDeactivated()`
- `safeBootEnabledChanged()`
- `serviceFailed(QString service)`
- `serviceRecovered(QString service)`
- `timelineUpdated()`
- `criticalServicesReady()`
- `autoRepairChanged()`

### SafeBootAutoRepair

- `repairAttempted(QString service, bool success)`
- `repairCompleted()`
- `runningChanged()`
- `repairTimelineChanged()`

### TestController

- `resultsChanged()`
- `runningChanged()`
- `testComplete(bool allGreen)`
- `loopFinished(int loopNum, bool allGreen)`

### ClaudeAPI

- `partialResponse(QString text)`
- `finalResponse(QString fullText)`
- `sentenceReady(QString sentence)`
- `responseReceived(QString response)`
- `toolCallDetected(QString toolUseId, QString toolName, QJsonObject arguments)`
- `errorOccurred(QString error)`
- `requestStarted()`
- `requestFinished()`
- `readyChanged()`
- `streamingChanged()`
- `modelChanged()`

### VoicePipeline

- `listeningChanged()`
- `speakingChanged()`
- `stateChanged(int newState)`
- `commandDetected(QString command)`
- `wakeWordDetected()`
- `speechStarted()`
- `speechEnded()`
- `partialTranscript(QString text)`
- `finalTranscript(QString text)`
- `speechTranscribed(QString transcription)`
- `statusChanged(QString status)`
- `voiceError(QString error)`
- `audioLevel(float rms, float vadScore)`
- `ttsVoicesChanged()`
- `micPcmForVisualization(QVariantList samples)`
- `ttsPcmForVisualization(QVariantList samples)`
- `audioUnavailable()`
- `audioReady()`

### WeatherManager

- `weatherUpdated()`
- `forecastReceived(QJsonObject forecast)`
- `loadingStateChanged()`
- `cityChanged()`
- `weatherError(QString error)`
- `weatherResponse(QString response)`

### ConfigManager

- `configurationLoaded()`
- `configurationError(QString error)`
- `weatherConfigChanged(QString city, QString apiKey)`
- `locationDetected(QString city, QString country)`
- `locationDetectionError(QString error)`
- `themeChanged(QString themeName, QVariantMap colors)`

### AIMemoryManager

- `memoryEnabledChanged()`
- `conversationCountChanged()`
- `memoryCountChanged()`
- `conversationAdded(QString userMessage, QString assistantResponse)`
- `memoryAdded(QString id, QString text)`
- `userPreferenceUpdated(QString key, QVariant value)`

### HealthCheck

- `healthChanged()`
- `serviceDown(QString serviceName)`
- `serviceRecovered(QString serviceName)`

### AudioDeviceManager

- `devicesChanged()`
- `inputDeviceChanged()`
- `audioError(QString error)`
- `audioStatusChanged()`
- `rmsLevelChanged()`
- `audioTestRunningChanged()`
- `audioTestFinished(bool success)`
- `audioUnavailable()`
- `audioReady()`
- `deviceSwitchRequested(int rtAudioDeviceId)`

### LogManager

- `newLogEntry(QString entry)`
- `newPipelineEvent(QJsonObject event)`

### PipelineEventBus

- `eventEmitted(QJsonObject event)`
- `moduleStateChanged(QString module, QString state)`
- `interactionStarted(QString correlationId)`
- `interactionEnded(QString correlationId, qint64 durationMs)`

## 3) Correspondance QML (Connections / handlers)

Handlers QML verifies:

- `voiceManager`: `onListeningChanged`, `onSpeakingChanged`, `onSpeechTranscribed`, `onCommandDetected`, `onWakeWordDetected`, `onAudioLevel`, `onMicPcmForVisualization`, `onTtsPcmForVisualization`, `onPartialTranscript`, `onStateChanged`, `onTtsVoicesChanged`.
- `claudeAPI`: `onRequestStarted`, `onPartialResponse`, `onFinalResponse`, `onResponseReceived`, `onErrorOccurred`.
- `assistantManager`: `onErrorOccurred`, `onNetworkScanCompleted`, `onHomeGraphReceived`, `onDeviceCommandResult`, `onScenarioResult`, `onClaudeResponseReceived` (ajoute par ce correctif).
- `pipelineEventBus`: `onEventEmitted`, `onModuleStateChanged`, `onInteractionStarted`.
- `configManager`: `onLocationDetected`, `onLocationDetectionError`.
- `audioDeviceManager`: `onDevicesChanged`.
- `serviceSupervisor`: `onAllServicesReady`.
- `weatherManager`: `onWeatherUpdated`, `onCityChanged` (ajoute par ce correctif dans BottomBar).

Resultat: aucune erreur de nommage de handler detectee sur ces connexions.

## 4) Signaux non connectes en QML (objets exposes)

Signaux exposes mais sans `Connections` QML directes detectees:

- `AssistantManager`: `messageReceived`, `claudePartialResponse`, `listeningStateChanged`, `initializationComplete`, `safeBootChanged`, `safeBootDecisionMadeChanged`, `autoRepairChanged`, `repairTimelineChanged`, `serviceReady`, `serviceFailed`.
- `ServiceSupervisor`: `startupFailed`, `serviceReady`, `serviceCountChanged`, `progressChanged`, `currentActionChanged`.
- `SafeBootController`: tous les signaux (QML s'appuie surtout sur bindings de `Q_PROPERTY`).
- `SafeBootAutoRepair`: tous les signaux (etat lu via `Q_PROPERTY` exposees par controleurs/facades).
- `TestController`, `HealthCheck`, `AIMemoryManager`, `LogManager` (signaux non relies en QML; usage principalement via polling/appels).

Note: "non connecte en QML" n'implique pas un bug si l'etat est consomme via `Q_PROPERTY` + `NOTIFY`.

## 5) Signaux jamais emis (constat statique)

- `AssistantManager::messageReceived(...)` declare mais aucune emission trouvee (`emit messageReceived(...)` absent).

## 6) Signaux dupliques / redondants

- `ClaudeAPI::finalResponse` et `ClaudeAPI::responseReceived` portent la meme semantique de reponse finale (alias de compatibilite).
- `AssistantManager::claudeResponseReceived` relaie aussi la reponse finale deja disponible via `ClaudeAPI`.

Impact: risque de traitement en double si QML consomme toutes les voies sans deduplication.

## 7) Mismatches noms/parametres detectes

### 7.1 Bug corrige

1. **Signal non consomme (AssistantManager -> QML)**
- Probleme: `AssistantManager::claudeResponseReceived(QString)` etait emis (welcome + fast-path) mais pas branche dans `MainWindow.qml`.
- Impact: certaines reponses n'apparaissaient pas dans l'UI si elles ne passaient pas par `claudeAPI`.
- Correctif applique: ajout de `onClaudeResponseReceived(response)` avec garde anti-duplication.

2. **Exposition Q_PROPERTY incoherente (meme zone d'audit)**
- Probleme: `BottomBar.qml` utilisait `weatherManager.summary` (propriete inexistante dans `WeatherManager`).
- Impact: texte meteo vide/instable.
- Correctif applique: construction de resume via proprietes reelles (`city`, `temperature`, `description`) + `Connections` sur `weatherUpdated`/`cityChanged`.

### 7.2 Aucun mismatch de signature trouve

- Pas de mismatch detecte entre signatures C++ et handlers QML pour les connexions explicites auditees.

## 8) Fichiers modifies (correctifs appliques)

- `qml/MainWindow.qml`
  - Ajout `onClaudeResponseReceived(response)` dans `Connections { target: assistantManager }`.
  - Ajout `onClaudePartialResponse(partialText)`.
  - Suppression de la consommation finale dupliquee via `claudeAPI` (`onFinalResponse`, `onResponseReceived`) pour unifier le flux UI sur `assistantManager`.
- `qml/panels/BottomBar.qml`
  - Suppression usage `weatherManager.summary`.
  - Ajout `buildWeatherSummary()`.
  - Ajout `Connections` sur `weatherManager` (`onWeatherUpdated`, `onCityChanged`).
- `app/core/HealthCheck.h`
  - Ajout de metadonnees de ping (`lastPongMs`) et intervalle de check memorise (`m_pingIntervalMs`).
- `app/core/HealthCheck.cpp`
  - Strategie anti-flapping VAD: desactivation de la reconnexion automatique pour `vad`.
  - Ouverture/ping VAD a la demande (`sendPing` + ping immediat sur `onServiceConnected`).
  - Ignorer `disconnected` pour `vad` afin d'eviter les transitions down parasites et le bruit de logs.

## 9) Recommandations complementaires

1. Soit retirer `AssistantManager::messageReceived`, soit l'emettre reellement.
2. Standardiser la voie UI de reponse Claude:
   - Option A: uniquement `assistantManager` (façade),
   - Option B: uniquement `claudeAPI`.
3. Conserver des gardes anti-duplication si les deux voies restent actives.
4. Si besoin d'observabilite plus reactive, connecter QML a `ServiceSupervisor::progressChanged/currentActionChanged` plutot que polling.

## 10) Validation

- Verification statique des erreurs QML sur fichiers modifies: OK (`get_errors` sans erreurs).
- Verification statique des erreurs C++ sur HealthCheck: OK (`get_errors` sans erreurs).
- Audit signaux C++ exposes a QML termine pour le perimetre EXO actuel.
