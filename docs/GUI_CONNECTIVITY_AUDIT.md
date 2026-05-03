# GUI_CONNECTIVITY_AUDIT.md — EXO v30.3
> Audit complet de l'interface QML/C++ — Connexions, orphelins, bindings cassés
> Généré le : 2025-07-15 | Périmètre : `qml/`, `app/`, `config/`, `scripts/`

---

## Table des matières
1. [Pages QML fonctionnelles](#1-pages-qml-fonctionnelles)
2. [Pages QML orphelines / non connectées](#2-pages-qml-orphelines--non-connectées)
3. [Panneaux non connectés](#3-panneaux-non-connectés)
4. [Composants non utilisés / mal câblés](#4-composants-non-utilisés--mal-câblés)
5. [Signaux C++ non reliés dans QML](#5-signaux-c-non-reliés-dans-qml)
6. [Slots / méthodes jamais appelés](#6-slots--méthodes-jamais-appelés)
7. [Bindings cassés](#7-bindings-cassés)
8. [Timers inutiles](#8-timers-inutiles)
9. [WebSockets non utilisés / mal configurés](#9-websockets-non-utilisés--mal-configurés)
10. [Pages qui ne réagissent plus à l état C++](#10-pages-qui-ne-réagissent-plus-à-létat-c)
11. [Problèmes critiques](#11-problèmes-critiques)
12. [Plan de correction détaillé](#12-plan-de-correction-détaillé)

---

## Référence — Context Properties exposées à QML

### Via `main.cpp` (root context direct)
| Identifiant QML | Type C++ | Fichier source |
|---|---|---|
| `assistantManager` | `AssistantManager*` | `app/core/AssistantManager.h` |
| `serviceSupervisor` | `ServiceSupervisor*` | `app/core/ServiceSupervisor.h` |
| `safeBootController` | `SafeBootController*` | `app/safeboot/SafeBootController.h` |
| `autoRepair` | `SafeBootAutoRepair*` | `app/safeboot/SafeBootAutoRepair.h` |
| `testController` | `TestController*` | `app/test/TestController.h` |

### Via `AssistantQmlExposer` (initialisé par `assistantManager.setQmlEngine()`)
| Identifiant QML | Type C++ |
|---|---|
| `claudeAPI` | `ClaudeAPI*` |
| `voiceManager` | `VoicePipeline*` |
| `weatherManager` | `WeatherManager*` |
| `configManager` | `ConfigManager*` |
| `memoryManager` | `AIMemoryManager*` |
| `healthCheck` | `HealthCheck*` |
| `audioDeviceManager` | `AudioDeviceManager*` |
| `logManager` | `LogManager*` (singleton) |
| `pipelineEventBus` | `PipelineEventBus*` (singleton) |

### Types QML enregistrés (QML_ELEMENT)
| Type QML | Type C++ |
|---|---|
| `FloorPlanModel` | `FloorPlanModel` (module `RaspberryAssistant`) |
| `FloorPlanController` | `FloorPlanController` (module `RaspberryAssistant`) |

### MANQUANTS — Backends C++ NON exposés à QML
| Backend attendu | Pages QML concernées | Statut |
|---|---|---|
| `simulationController` | `SimulationPageExpert` (index 37) | NON exposé, non créé dans main.cpp |
| `spatialSecurityEngine` | `SecurityPageExpert` (index 39) | NON exposé, non créé dans main.cpp |
| `visionContext` / `CameraStreamManager` | `VisionPageExpert` (index 36) | NON exposé, non créé dans main.cpp |
| `spatialCognitionEngine` | `SpatialCognitionPageExpert` (index 38) | NON exposé, non créé dans main.cpp |

---

## 1. Pages QML fonctionnelles

| Page | Fichier | Index StackLayout | Connexions C++ actives |
|---|---|---|---|
| HomePage | `qml/pages/HomePage.qml` | 0 | `voiceManager`, `claudeAPI`, `assistantManager` via MainWindow |
| SettingsPage | `qml/pages/SettingsPage.qml` | 1 | `configManager`, `UIState`, `weatherManager` |
| HistoryPage | `qml/pages/HistoryPage.qml` | 2 | `memoryManager.clearConversationHistory()` |
| PipelinePage | `qml/pages/PipelinePage.qml` | 4 | `pipelineEventBus.getPipelineSnapshot()`, `onEventEmitted`, `onModuleStateChanged` |
| MaisonPage | `qml/pages/MaisonPage.qml` | 5 | Données injectées depuis `onHomeGraphReceived` (MainWindow) |
| ReseauPage | `qml/pages/ReseauPage.qml` | 6 | Données injectées depuis `onNetworkScanCompleted` (MainWindow) |
| FloorPlanPage | `qml/pages/FloorPlanPage.qml` | 13 | `FloorPlanModel` (QML_ELEMENT), `FloorPlanController` (QML_ELEMENT) |
| PipelinePageExpert | `qml/pages/PipelinePageExpert.qml` | 35 | `pipelineEventBus` partiellement — `voiceManager` absent |

**Composants embarqués fonctionnels (utilisés comme pages aux indices 7-12) :**
| Composant | Index | Connexions actives |
|---|---|---|
| `CognitiveTimeline` | 7 | `pipelineEventBus.onModuleStateChanged`, `onEventEmitted`, Timer snapshot |
| `EngineHeatmap` | 8 | `pipelineEventBus.onEventEmitted`, `onModuleStateChanged` |
| `VoicePipelineView` | 9 | `pipelineEventBus.onEventEmitted`, `voiceManager.onStateChanged` |
| `MemoryInspector` | 10 | `pipelineEventBus.onEventEmitted` (events `memory_*`) |
| `GovernancePanel` | 11 | `pipelineEventBus.onEventEmitted` (events `governance`) |
| `ObservabilityDashboard` | 12 | `serviceSupervisor.onAllServicesReady`, `pipelineEventBus.onEventEmitted`, Timer |

---

## 2. Pages QML orphelines / non connectées

### 2.1 Pages avec données entièrement hardcodées

| Page | Fichier | Index | Problème |
|---|---|---|---|
| DevelopmentPageExpert | `qml/pages/DevelopmentPageExpert.qml` | 40 | `readyCount: 14`, `failedCount: 1`, `degradedCount: 2`, `totalCount: 17` hardcodés — aucune connexion à `serviceSupervisor` ni `safeBootController` |
| ObservabilityPage | `qml/pages/ObservabilityPage.qml` | 34 | Onglet Logs = texte statique hardcodé — non connecté à `logManager` |
| SimulationPageExpert | `qml/pages/SimulationPageExpert.qml` | 37 | Scénarios = `Repeater { model: ["Incendie cuisine", ...] }` hardcodés — `simulationController` inexistant dans QML |
| SecurityPageExpert | `qml/pages/SecurityPageExpert.qml` | 39 | Grille avec compteurs statiques — `spatialSecurityEngine` inexistant dans QML |
| SpatialCognitionPageExpert | `qml/pages/SpatialCognitionPageExpert.qml` | 38 | Onglets Spatial/Décisions/Explications/Prédictions avec modèles statiques — `spatialCognitionEngine` inexistant |
| VisionPageExpert | `qml/pages/VisionPageExpert.qml` | 36 | Camera = icône emoji placeholder, boutons Start/Stop non fonctionnels — `visionContext` inexistant |

### 2.2 Placeholders vides — `Item {}` sans contenu

| Index | Commentaire | État |
|---|---|---|
| 3 | Logs migré vers index 34 | `Item {}` vide |
| 14 | Stability Tests migré vers index 40 | `Item {}` vide |
| 15 | Simulation Spatiale migré vers index 37 | `Item {}` vide |
| 16 | Services migré vers index 40 | `Item {}` vide |
| 17 à 33 | Aucun commentaire (17 items) | `Item {}` vide |

**Total : 21 indices sur 41 = 51 % du StackLayout occupé par des vides.**

### 2.3 Composants utilisés directement comme pages (navigation ancienne)

Les composants aux indices 7-12 sont destinés à être embarqués dans des pages, pas utilisés comme pages autonomes. Ils n'ont pas de `ExoPanelHeader`, ni de gestion du cycle de vie page.

| Composant | Index | Problème |
|---|---|---|
| `CognitiveTimeline {}` | 7 | Pas de header, navigation ancienne pré-Expert |
| `EngineHeatmap {}` | 8 | Pas de header, pas d'onglets |
| `VoicePipelineView {}` | 9 | Pas de header, pas d'onglets |
| `MemoryInspector {}` | 10 | Pas de header, pas d'onglets |
| `GovernancePanel {}` | 11 | Pas de header, pas d'onglets |
| `ObservabilityDashboard {}` | 12 | Doublon fonctionnel avec `ObservabilityPage` (index 34) |

---

## 3. Panneaux non connectés

### SafeBootPanel
- **Fichier :** `qml/panels/SafeBootPanel.qml`
- **Statut :** Fonctionnel — reçoit ses données via propriétés injectées par MainWindow depuis `safeBootController`.

### HeaderBar
- **Fichier :** `qml/panels/HeaderBar.qml`
- **Statut :** Partiellement connecté.
- **Problème :** `pageTitles` couvre 14 panelNames mais pas les pages Expert (vision, simulation, cognition, security, development). Les pages Expert affichent le `panelName` brut non traduit.

### Sidebar
- **Fichier :** `qml/panels/Sidebar.qml`
- **Statut :** Bien connecté — `UIState.onExpertModeChanged`, `MenuStructure.onForceRefreshChanged`, `assistantManager.safeBootEnabled`.

### BottomBar
- **Fichier :** `qml/panels/BottomBar.qml`
- **Statut :** Connecté (corrigé session précédente). 20 services surveillés via `serviceSupervisor.serviceState(key)`.
- **Problème mineur :** La clé `"domotic"` n'est probablement pas enregistrée dans `ServiceSupervisor` (service Python domotique non documenté dans `config/services.json`). Dot toujours gris.

---

## 4. Composants non utilisés / mal câblés

### SpatialNetworkIntegration — Jamais instancié
- **Fichier :** `qml/components/SpatialNetworkIntegration.qml`
- **Problème :** Déclaré dans `qmldir` mais jamais instancié dans aucune page ni panneau. `FloorPlanProperties.qml` déclare `property var networkIntegration: null` mais la valeur est toujours `null` (jamais injectée).
- **Impact :** Les WebSockets ws://8790 et ws://8784 de ce composant ne se connectent jamais. Les données spatiales réseau/domotique pour FloorPlan ne sont jamais disponibles.

### Composants UI jamais référencés dans les pages
| Composant | Fichier | Remarque |
|---|---|---|
| `AudioWaveformView` | `AudioWaveformView.qml` | Non utilisé |
| `ExoContextPanel` | `ExoContextPanel.qml` | Non utilisé |
| `ExoOrbVisualizer` | `ExoOrbVisualizer.qml` | Non utilisé |
| `ExoWaveform` | `ExoWaveform.qml` | Non utilisé — doublon possible avec `ExoVisualizer` |
| `ExoMicrophoneLevel` | `ExoMicrophoneLevel.qml` | Non utilisé — doublon possible avec `ExoVisualizer` |

### Doublon fonctionnel PipelineView / VoicePipelineView
- `PipelineView.qml` : Pipeline 5 étapes — connexions `pipelineEventBus` + `voiceManager`
- `VoicePipelineView.qml` : Pipeline 9 étapes — connexions identiques, granularité supérieure
- Les deux font la même chose. `VoicePipelineView` devrait être le composant canonique.

---

## 5. Signaux C++ non reliés dans QML

### AssistantManager — Signaux orphelins
| Signal | Paramètres | Connecté dans QML ? |
|---|---|---|
| `messageReceived(QString)` | message utilisateur | Non trouvé dans les Connections visibles |
| `claudeResponseReceived(QString)` | réponse complète | Non trouvé |
| `claudePartialResponse(QString)` | réponse streaming | Non trouvé |
| `listeningStateChanged(bool)` | état écoute | Non trouvé dans MainWindow |
| `initializationComplete()` | init terminée | Non trouvé |
| `autoRepairChanged()` | réparation auto | Non connecté à SafeBootPanel ni ExoSplashScreen |
| `repairTimelineChanged(QVariantList)` | timeline réparation | Non connecté à ExoSplashScreen |
| `serviceReady(QString)` | service prêt | Non connecté à ExoSplashScreen |
| `serviceFailed(QString)` | service échoué | Non connecté à ExoSplashScreen |

### SafeBootController — Signaux orphelins
| Signal | Connecté dans QML ? |
|---|---|
| `safeBootActivated()` | Non trouvé dans MainWindow |
| `safeBootDeactivated()` | Non trouvé dans MainWindow |
| `timelineUpdated(QVariantList)` | Non connecté à ExoSplashScreen |
| `autoRepairChanged()` | Non connecté à ExoSplashScreen |

### ServiceSupervisor — Signaux orphelins
| Signal | Connecté dans QML ? |
|---|---|
| `progressChanged(int)` | Non connecté (ExoSplashScreen utilise un Timer de polling) |
| `currentActionChanged(QString)` | Non connecté à ExoSplashScreen |
| `startupFailed()` | Non trouvé dans QML |
| `serviceReady(QString)` | Non connecté |

---

## 6. Slots / méthodes jamais appelés

| Méthode C++ | Objet QML | Statut |
|---|---|---|
| `simulationController.*` | — | Backend inexistant dans QML |
| `spatialSecurityEngine.*` | — | Backend inexistant dans QML |
| `visionContext.*` | — | Backend inexistant dans QML |
| `spatialCognitionEngine.*` | — | Backend inexistant dans QML |
| `logManager.getRecentLogs()` | ObservabilityPage | Jamais appelé — logs hardcodés à la place |
| `logManager.getLogsByFilter()` | ObservabilityPage | Jamais appelé |
| `serviceSupervisor.serviceStatuses` | DevelopmentPageExpert | Jamais lu — valeurs hardcodées à la place |

---

## 7. Bindings cassés

| Binding | Fichier | Problème |
|---|---|---|
| `pipelineState` dans PipelinePageExpert | `qml/pages/PipelinePageExpert.qml` | Déclaré `"Idle"` — aucun `Connections {}` ne le met à jour depuis `voiceManager` |
| `micLevel` dans PipelinePageExpert | `qml/pages/PipelinePageExpert.qml` | Déclaré `0.0` — jamais mis à jour |
| `partialTranscript` dans PipelinePageExpert | `qml/pages/PipelinePageExpert.qml` | Déclaré `""` — jamais mis à jour |
| `readyCount` dans DevelopmentPageExpert | `qml/pages/DevelopmentPageExpert.qml` | Hardcodé `14` — aucun binding vers `serviceSupervisor.readyCount` |
| `failedCount` dans DevelopmentPageExpert | `qml/pages/DevelopmentPageExpert.qml` | Hardcodé `1` — aucun binding vers `safeBootController.failedCount` |
| `degradedCount` dans DevelopmentPageExpert | `qml/pages/DevelopmentPageExpert.qml` | Hardcodé `2` — aucun binding vers `safeBootController.degradedCount` |
| `totalCount` dans DevelopmentPageExpert | `qml/pages/DevelopmentPageExpert.qml` | Hardcodé `17` — aucun binding vers `serviceSupervisor.totalServices` |
| Onglet Logs dans ObservabilityPage | `qml/pages/ObservabilityPage.qml` | Texte statique hardcodé au lieu de `logManager.getRecentLogs()` |
| `networkIntegration` dans FloorPlanProperties | `qml/components/FloorPlanProperties.qml` | Propriété toujours `null` — `SpatialNetworkIntegration` jamais instancié |
| Titres dans HeaderBar | `qml/panels/HeaderBar.qml` | Dictionnaire `pageTitles` incomplet — pages Expert manquantes |

---

## 8. Timers inutiles

| Timer | Fichier | Problème |
|---|---|---|
| `refreshTimer` PipelinePage | `qml/pages/PipelinePage.qml` | `running: root.visible` — optimisé, OK |
| Timer snapshot CognitiveTimeline | `qml/components/CognitiveTimeline.qml` | `running: root.visible` — OK |
| Timer `interval: 2000` ObservabilityDashboard | `qml/components/ObservabilityDashboard.qml` | `running: root.visible` — OK mais redondant si `allServicesReady` suffit |
| Timer horloge BottomBar | `qml/panels/BottomBar.qml` | `triggeredOnStart: true` — OK |
| `networkReconnectTimer` SpatialNetworkIntegration | `qml/components/SpatialNetworkIntegration.qml` | INUTILE — le composant n'est jamais instancié ; timer mort |

---

## 9. WebSockets non utilisés / mal configurés

| WebSocket | URL cible | Instancié ? | Service existant ? |
|---|---|---|---|
| NetworkMap WS | `ws://localhost:8790/ws` | Non instancié | Port 8790 absent de `config/services.json` |
| HomeGraph WS | `ws://localhost:8784/ws` | Non instancié | Port 8784 absent de `config/services.json` |

**Services Python réels (ports) :** STT=8765, TTS=8766, VAD=8770, WakeWord=8771, Memory=8772, NLU=8773, Context=8774, Planner=8775, Tools=8776, Executor=8777, Verifier=8778, System=8779.

Les ports 8784 et 8790 ne correspondent à aucun service existant. Ces WebSockets ciblent des services Python non implémentés.

---

## 10. Pages qui ne réagissent plus à l'état C++

### CRITIQUE — Données 100% statiques

| Page | Index | Ce qui est figé | Données attendues |
|---|---|---|---|
| DevelopmentPageExpert | 40 | Compteurs 14/1/2/17, grille services statique | `serviceSupervisor.serviceStatuses`, `safeBootController.*Count` |
| ObservabilityPage onglet Logs | 34 | Texte `"[08:45:12] Pipeline vocal initialisé"` | `logManager.getRecentLogs()` |
| SimulationPageExpert | 37 | Liste 3 scénarios hardcodés | `simulationController` (inexistant) |
| SecurityPageExpert | 39 | Compteurs Intrusions/Incendies statiques | `spatialSecurityEngine` (inexistant) |
| SpatialCognitionPageExpert | 38 | Grille données spatiales statiques | `spatialCognitionEngine` (inexistant) |
| VisionPageExpert | 36 | Camera = emoji, boutons inactifs | `visionContext` / `CameraStreamManager` (inexistant) |

### DÉGRADÉ — Partiellement réactif

| Page | Index | Ce qui ne réagit pas |
|---|---|---|
| PipelinePageExpert | 35 | `pipelineState`, `micLevel`, `partialTranscript` toujours aux valeurs initiales |
| ExoSplashScreen | overlay | Progression via polling Timer plutôt que signaux directs |

---

## 11. Problèmes critiques

### P0 — Bloquants

| ID | Problème | Impact |
|---|---|---|
| P0-1 | `DevelopmentPageExpert` : compteurs hardcodés (14/1/2/17) | Monitoring services affiche de fausses données permanentes |
| P0-2 | `ObservabilityPage` onglet Logs : texte statique | Diagnostic système impossible depuis cette page |
| P0-3 | 4 backends manquants : `simulationController`, `spatialSecurityEngine`, `spatialCognitionEngine`, `visionContext` non créés ni exposés dans `main.cpp` | Pages SimulationPageExpert, SecurityPageExpert, SpatialCognitionPageExpert, VisionPageExpert 100% inutilisables |
| P0-4 | `SpatialNetworkIntegration` jamais instancié + services 8784/8790 inexistants | Intégration spatiale réseau/domotique complètement brisée |

### P1 — Sérieux

| ID | Problème | Impact |
|---|---|---|
| P1-1 | 21 `Item {}` vides dans le StackLayout | Page blanche si un panelName pointe vers un indice vide |
| P1-2 | `PageRouter` ne mappe pas ~25 panelNames du switch MainWindow | Routes orphelines, navigation incohérente |
| P1-3 | `PipelinePageExpert` : état pipeline jamais mis à jour depuis C++ | Page Expert Pipeline figée |
| P1-4 | Signaux `timelineUpdated`, `progressChanged`, `currentActionChanged` non connectés à ExoSplashScreen | Splash screen statique pendant le démarrage |

### P2 — Modérés

| ID | Problème | Impact |
|---|---|---|
| P2-1 | `HeaderBar.pageTitles` incomplet — 7 pages Expert manquantes | Titre brut affiché dans le header Expert |
| P2-2 | Composants aux indices 7-12 sans header ni cycle de vie page | Incohérence visuelle en mode Normal |
| P2-3 | Clé `"domotic"` dans BottomBar absente de `ServiceSupervisor` | Indicateur domotique toujours gris |
| P2-4 | `ObservabilityDashboard` (index 12) redondant avec `ObservabilityPage` (index 34) | Confusion navigation |

### P3 — Mineurs

| ID | Problème |
|---|---|
| P3-1 | Composants morts : `AudioWaveformView`, `ExoContextPanel`, `ExoOrbVisualizer`, `ExoWaveform`, `ExoMicrophoneLevel` |
| P3-2 | Duplication `PipelineView` vs `VoicePipelineView` |
| P3-3 | Commentaires `// migré` sans suppression des `Item {}` correspondants |

---

## 12. Plan de correction détaillé

### Phase A — Sans C++ supplémentaire (~2h)

#### A1 — DevelopmentPageExpert : bindings serviceSupervisor + safeBootController
**Fichier :** `qml/pages/DevelopmentPageExpert.qml`

```qml
// Remplacer les valeurs hardcodées par :
property int readyCount:    typeof serviceSupervisor    !== 'undefined' ? serviceSupervisor.readyCount      : 0
property int failedCount:   typeof safeBootController  !== 'undefined' ? safeBootController.failedCount    : 0
property int degradedCount: typeof safeBootController  !== 'undefined' ? safeBootController.degradedCount  : 0
property int totalCount:    typeof serviceSupervisor    !== 'undefined' ? serviceSupervisor.totalServices   : 0
```

Remplacer la liste services statique par `Repeater { model: serviceSupervisor.serviceStatuses }`.

#### A2 — ObservabilityPage : brancher logManager
**Fichier :** `qml/pages/ObservabilityPage.qml`

Supprimer le texte hardcodé. Ajouter un `ListView` avec `ListModel { id: logModel }` et :

```qml
Connections {
    target: typeof logManager !== 'undefined' ? logManager : null
    function onLogAdded(entry) {
        logModel.insert(0, { text: entry })
        while (logModel.count > 500) logModel.remove(logModel.count - 1)
    }
}
Component.onCompleted: {
    if (typeof logManager !== 'undefined') {
        var logs = logManager.getRecentLogs()
        for (var i = 0; i < logs.length; i++) logModel.append({ text: logs[i] })
    }
}
```

#### A3 — PipelinePageExpert : brancher voiceManager
**Fichier :** `qml/pages/PipelinePageExpert.qml`

```qml
Connections {
    target: typeof voiceManager !== 'undefined' ? voiceManager : null
    function onStateChanged(newState) {
        var states = ["Idle","DetectingSpeech","Listening","Transcribing","Thinking","Speaking"]
        if (newState >= 0 && newState < states.length) root.pipelineState = states[newState]
    }
    function onMicLevelChanged(level) { root.micLevel = level }
    function onPartialTranscriptChanged(text) { root.partialTranscript = text }
}
```

#### A4 — HeaderBar : compléter pageTitles
**Fichier :** `qml/panels/HeaderBar.qml`

Ajouter dans le dictionnaire :
```qml
"vision":       "Vision & Caméras",
"simulation":   "Simulation",
"cognition":    "Cognition Spatiale",
"security":     "Sécurité Spatiale",
"development":  "Développement",
"floorplan":    "Plan de logement"
```

#### A5 — Nettoyage des Item{} vides (indices 17-33)
**Fichier :** `qml/MainWindow.qml`

Supprimer les 17 `Item {}` groupés (indices 17-33). Mettre à jour le switch de navigation. Vérifier qu'aucune route ne pointe vers ces indices avant suppression.

---

### Phase B — Connexions C++ existants (~1-2h)

#### B1 — ExoSplashScreen : signaux de progression
**Fichier :** `qml/MainWindow.qml`

```qml
Connections {
    target: serviceSupervisor
    function onProgressChanged(p)           { splashScreen.readyCount = serviceSupervisor.readyCount }
    function onCurrentActionChanged()       { splashScreen.currentAction = serviceSupervisor.currentAction }
}
Connections {
    target: safeBootController
    function onTimelineUpdated(timeline)    { splashScreen.autoRepairTimeline = timeline }
    function onAutoRepairChanged()          { splashScreen.autoRepairActive = safeBootController.autoRepairRunning }
}
```

#### B2 — PageRouter : étendre le mapping
**Fichier :** `qml/core/PageRouter.qml`

Ajouter tous les panelNames du switch MainWindow qui ne sont pas encore dans `normalPages` ou `expertPages`. Supprimer les entrées qui pointent vers des indices vides.

---

### Phase C — Backends C++ manquants (long terme)

#### C1 — VisionPageExpert
- Créer `app/vision/VisionContext.h` : signaux `frameAvailable(QImage)`, `detectionUpdated(QVariantList)`, `riskUpdated(QVariantList)`
- Exposer dans `main.cpp` : `engine.rootContext()->setContextProperty("visionContext", &visionContext)`

#### C2 — SimulationPageExpert
- Créer / compléter `app/simulation/SimulationController.h` : Q_PROPERTY `scenarios`, méthodes `runScenario(name)`, `stopSimulation()`
- Exposer dans `main.cpp`

#### C3 — SecurityPageExpert
- Créer `app/spatialsecurity/SpatialSecurityEngine.h` : Q_PROPERTY `riskZones`, `activeThreats`, signal `threatDetected`
- Exposer dans `main.cpp`

#### C4 — SpatialCognitionPageExpert
- Créer `app/spatialcognition/SpatialCognitionEngine.h` : Q_PROPERTY `spatialMap`, `decisions`, `predictions`
- Exposer dans `main.cpp`

#### C5 — SpatialNetworkIntegration
- Créer `python/network/network_map_server.py` (port 8790) et `python/homegraph/homegraph_server.py` (port 8784)
- Instancier `SpatialNetworkIntegration {}` dans `FloorPlanPage` et injecter dans `FloorPlanProperties.networkIntegration`
- Ajouter ces services dans `config/services.json` et les VS Code tasks

---

### Phase D — Nettoyage (~2h)

#### D1 — Supprimer les composants morts
`AudioWaveformView.qml`, `ExoContextPanel.qml`, `ExoOrbVisualizer.qml`, `ExoWaveform.qml`, `ExoMicrophoneLevel.qml`

#### D2 — Résoudre la duplication PipelineView / VoicePipelineView
Garder `VoicePipelineView` (9 étapes) comme composant canonique. Remplacer `PipelineView` par `VoicePipelineView collapsed: true` dans `PipelinePage`. Supprimer `PipelineView.qml`.

#### D3 — Convertir composants des indices 7-12 en pages complètes
Soit les déplacer dans `qml/pages/` avec un `ExoPanelHeader {}`, soit les retirer du StackLayout et les embarquer uniquement dans les pages Expert correspondantes.

---

## Récapitulatif des priorités

| Priorité | ID | Effort | Impact |
|---|---|---|---|
| P0 | A1 — DevelopmentPageExpert bindings | 30 min | Compteurs services réels |
| P0 | A2 — ObservabilityPage logs | 45 min | Logs réels dans l'UI |
| P0 | A3 — PipelinePageExpert state | 20 min | État pipeline temps réel |
| P0 | C1-C4 — Backends Vision/Simulation/Security/Cognition | 3-5 jours | 4 pages Expert fonctionnelles |
| P1 | B1 — Splash screen signals | 1h | Démarrage dynamique |
| P1 | B2 — PageRouter complet | 1h | Navigation cohérente |
| P1 | A5 — Nettoyage Item{} vides | 30 min | MainWindow lisible |
| P2 | A4 — HeaderBar titres | 15 min | Titres corrects Expert |
| P2 | C5 — Services Python 8784/8790 | 2-3 jours | Intégration spatiale réseau |
| P3 | D1-D3 — Nettoyage code mort | 2h | Dette technique réduite |

---

*Fin de l'audit — EXO v30.3 GUI Connectivity Audit*
