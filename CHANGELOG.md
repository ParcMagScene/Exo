# CHANGELOG — EXO

> Minimal. Ce qui a changé, supprimé, ajouté, refactoré.
> Source de vérité : `PROMPT_MAITRE.md`

---

## v30.3 — SafeBootAutoRepair + UI-first Boot — Mai 2026

### Ajouté
- **SafeBootAutoRepair** (`SafeBootAutoRepair.h/.cpp`) — Module de réparation automatique des services KO
  - `autoRepairAll()` — collecte les services Failed/Crashed, lance la file de réparation séquentielle
  - `attemptRepair(name)` — pipeline : clearCache → checkPort → killZombie → restartService → waitForReady
  - Kill zombie via `netstat + TerminateProcess` (Windows)
  - Readiness probe via QWebSocket (polling 200ms, timeout 1500ms)
  - 3 tentatives max par service, 500ms entre réparations
  - Q_PROPERTY `running` + `repairTimeline` exposées au QML
- **UI-first Boot Sequence** — `engine.load()` avant `serviceSupervisor.start()` dans main.cpp, l'écran splash est visible immédiatement
- **AutoRepair visual mode** dans ExoSplashScreen — panneau bleu "Réparation automatique en cours…" avec timeline temps réel
- **Status `repairing`** dans la liste des services du splash (icône 🔧, couleur `Theme.info`)
- **AssistantManager.autoRepairRunning / repairTimeline** — Q_PROPERTYs + slots `onRepairAttempt`, `onRepairCompleted`
- **SafeBootController.repairTimeline()** — accesseur délégué vers AutoRepair

### Modifié
- `SafeBootController.h/.cpp` — intégration AutoRepair (setAutoRepair, startAutoRepair, onAutoRepairCompleted, auto-launch dans enableSafeBoot)
- `main.cpp` — UI-first restructuration, création AutoRepair, 4 connexions signal→AssistantManager, version → v30.3
- `AssistantManager.h/.cpp` — autoRepairRunning, repairTimeline, onRepairAttempt, onRepairCompleted, version → v30.3
- `ExoSplashScreen.qml` — autoRepair properties, panneau bleu, status repairing, version → v30.3
- `CMakeLists.txt` — SafeBootAutoRepair.cpp/.h ajoutés

---

## v30.2b — Activation complète Safe Boot — Mai 2026

### Ajouté
- **Force-start UI** — `enableSafeBoot()` émet `criticalServicesReady` pour forcer le démarrage en mode dégradé quand un service critique est KO
- **Signal `safeBootEnabledChanged`** — Q_PROPERTY NOTIFY correcte (émis sur enable, disable et restartNormalMode)
- **Émission `serviceFailed` pour non-critiques** — `onServiceTimeout` émet maintenant le signal pour les non-critiques aussi
- **SafeBootPanel overlay dans MainWindow.qml** — Panneau automatique côté droit (35% largeur, z:90), visible dès `safeBootEnabled`
- **Forwarding service events** (`main.cpp`) — `serviceRecovered`→`onServiceReady`, `serviceFailed`→`onServiceFailed` vers AssistantManager
- **AssistantManager.onServiceReady/onServiceFailed** — Méthodes Q_INVOKABLE + signaux pour relayer état services vers QML
- **test_safeboot.cpp** — 9 tests unitaires : timeout critique, non-critique degraded, service lent, crash, all-ready, markFailed, timeline, restartNormalMode

### Modifié
- `SafeBootController.h` — Q_PROPERTY NOTIFY `safeBootActivated` → `safeBootEnabledChanged`
- `SafeBootController.cpp` — force-start dans enableSafeBoot, safeBootEnabledChanged dans disable/restart, serviceFailed non-critique
- `main.cpp` — 2 nouvelles connexions (serviceRecovered, serviceFailed)
- `AssistantManager.h/.cpp` — onServiceReady/onServiceFailed + signals, version → v30.2
- `MainWindow.qml` — SafeBootPanel overlay avec bindings safeBootController
- `tests/cpp/CMakeLists.txt` — Sources/headers SafeBoot dans exo_testlib, exo_add_test(test_safeboot)

---

## v30.2 — SafeBootController (module complet Safe Boot) — Mai 2026

### Ajouté
- **SafeBootController** (`app/safeboot/SafeBootController.h/.cpp`) — Module complet remplaçant SafeBootManager
  - Timeout 2s par service (indépendant des 30s de ServiceSupervisor)
  - 7 services critiques (orchestrator, system, memory, context, planner, executor, verifier)
  - 13 services non critiques (lazy-load après UI avec 3 tentatives de reconnexion)
  - Timeline complète de tous les événements de boot
  - Boutons Réessayer / Redémarrer en mode normal
  - Signaux : `criticalServicesReady`, `safeBootActivated/Deactivated`, `serviceFailed/Recovered`
- **SafeBootEnums** (`app/safeboot/SafeBootEnums.h`) — ServiceCriticality {Critical, NonCritical}, ServiceStatus {Pending, Ready, Failed, Degraded}
- **SafeBootState** (`app/safeboot/SafeBootState.h`) — Struct état par service (nom, criticité, status, temps de réponse, erreur)
- **SafeBootTimeline** (`app/safeboot/SafeBootTimeline.h`) — Struct événement timeline (event, timestamp, serviceName, detail)
- **SafeBootPanel** (`qml/panels/SafeBootPanel.qml`) — Panneau complet avec services échoués/dégradés, timeline scrollable, boutons retry/restart

### Modifié
- `AssistantManager.h/.cpp` — Q_PROPERTY safeBootEnabled, failedServices, degradedServices, startupTimeline + `setSafeBootController()`
- `main.cpp` — SafeBootManager → SafeBootController, ajout `startMonitoring()`, connexion `criticalServicesReady`
- `MainWindow.qml` — Bindings `safeBootManager` → `safeBootController`
- `ExoSplashScreen.qml` — SafeBootPanel composant remplacé par section inline Safe Boot, version → v30.2
- `CMakeLists.txt` — SafeBootManager → SafeBootController (4 headers + 1 source), SafeBootPanel déplacé vers panels/

### Obsolète
- `app/core/SafeBootManager.h/.cpp` — Remplacé par SafeBootController (fichiers conservés mais non compilés)
- `qml/components/SafeBootPanel.qml` — Remplacé par `qml/panels/SafeBootPanel.qml` (fichier conservé mais non compilé)

---

## v30.1 — Safe Boot Orchestrator — Mai 2026

### Ajouté
- **SafeBootManager** (`app/core/SafeBootManager.h/.cpp`) — Permet à EXO de démarrer même si des services non critiques sont bloqués/lents/en erreur
  - Classification services : 12 critiques (orchestrator, stt, tts, vad, wakeword, memory, nlu, context, planner, executor, verifier, system) + 13 non critiques (lazy load)
  - Signal `safeBootReady` émis quand tous les critiques sont Ready → déclenche `initializeWithConfig()` sans attendre les lazy
  - Signal `allServicesNormalized` quand les lazy rattrapent → sortie automatique du mode Safe Boot
  - Diagnostic complet : `diagnosticReport()` exposé QML (timestamp, services critiques/lazy/failed, compteurs)
  - Connecté au `ServiceRegistry::serviceStateChanged` — réaction temps réel
- **SafeBootPanel** (`qml/components/SafeBootPanel.qml`) — Panneau d'alerte Safe Boot dans le splash screen
  - Barres de progression séparées : critiques (vert) + lazy (bleu)
  - Liste des services en échec avec couleur critique/non-critique
  - Apparaît uniquement quand `safeBootActive = true`
- **Intégration MainWindow** — `servicesReady` accepte désormais `safeBootManager.criticalReady` en alternative à `serviceSupervisor.allReady`
- **Intégration main.cpp** — Double connexion : `allServicesReady` + `safeBootReady` → `initializeWithConfig()`

### Modifié
- `ExoSplashScreen.qml` — 8 nouvelles propriétés Safe Boot, SafeBootPanel intégré avant le spinner
- `MainWindow.qml` — `servicesReady` élargi, propriétés safeBootManager passées au splash
- `CMakeLists.txt` — SafeBootManager.h/.cpp + SafeBootPanel.qml ajoutés
- `qmldir` (components) — SafeBootPanel enregistré

---

## v30.0 — Module de vision IA embarquée — Mai 2026

### Ajouté
- **Module vision** (`app/vision/`) — 15 fichiers C++ (8 headers + 7 implémentations)
  - `VisionEnums.h` — 7 enums (DetectionType, VisionPhase, CameraState, VisionModel, Posture, Behavior, VisionSeverity) + 12 constantes (kDefaultConfidenceThreshold=0.5, kDefaultFps=15, kFrameBufferSize=30, kMaxDetectionsPerFrame=100, kMaxVisionEvents=5000)
  - `VisionDetections` — 4 structs (BoundingBox, VisionDetection, FrameDetections, VisionEvent) + gestionnaire QObject avec requêtes par caméra/type/pièce/sévérité, éviction LRU
  - `CameraStreamManager` — Gestion flux caméras (register/open/close/read), buffer circulaire, capture simulée QPainter (1920×1080), QTimer au targetFps
  - `VisionModelRunner` — 6 modèles IA simulés : ObjectDetection (personnes+animaux), Segmentation (contours elliptiques), FireSmoke (2% feu + 3% fumée), PoseEstimation, BehaviorAnalysis, IntrusionDetection (point-in-polygon + line intersection). Struct IntrusionZone
  - `VisionContext` — État par caméra (CameraSubsystemState), heatmap activité par pièce (EMA α=0.3), niveau activité global, requêtes spatiales (roomsWithPersons, roomsWithAnomalies, busiestRoom), snapshot/diff
  - `VisionMemory` — Mémoire d'incidents vision persistante (JSON, similarité Jaccard sur tags 0.4 + bonus type/room/camera, éviction LRU pondérée résolu)
  - `VisionEventRouter` — Routage événements vers Security (intrusion/fire/smoke/obstruction/fall/anomaly), Cognition (detections→Reasoner, behavior→Planner, anomaly→Supervisor), Simulation (validation), QML (overlay+display)
  - `CameraVisionEngine` — Orchestrateur pipeline 6 phases (Capture→Preprocessing→Inference→PostProcessing→EventRouting→CognitionSync), QML_ELEMENT, auto-cycle, gestion caméras et zones intrusion
- **11 panneaux QML** (`qml/cognitive/`)
  - `VisionPanel` — Dashboard vision (indicateur phase, barre activité, métriques caméras/détections/personnes, contrôle start/stop)
  - `VisionCameraPanel` — Liste caméras avec indicateurs état, compteurs personnes/détections par caméra
  - `VisionEventsPanel` — Flux événements avec couleurs sévérité et pourcentages confiance
  - `VisionOverlay` — Overlay FloorPlan avec positions caméras, alertes feu/fumée
  - `VisionDetectionsLayer` — Rendu bounding boxes avec couleurs par type, labels posture/comportement
  - `VisionHeatmap` — Heatmap activité pièces avec barres progression et code couleur
  - `VisionAnomalyPanel` — Compteurs feu/fumée/obstruction/chute + liste événements
  - `VisionBehaviorPanel` — Analyse comportementale — badges rôdage/agitation/mouvement anormal + liste
  - `VisionFirePanel` — Panneau dédié feu & fumée avec alertes animées et historique
  - `VisionIntrusionPanel` — Alertes intrusion avec compteur zones et bannière avertissement animée
  - `VisionExplanationPanel` — Vue détail/explication événement avec incidents similaires

### Modifié
- `CMakeLists.txt` — 7 sources, 9 headers, 11 QML, include dir `app/vision`
- `qml/cognitive/qmldir` — 11 nouvelles entrées vision
- Version bump 29.5.0 → 30.0.0 (CMakeLists.txt, __init__.py, assistant.conf.example, main.cpp, README.md)

---

## v29.5 — Module de sécurité spatiale avancée — Mai 2026

### Ajouté
- **Module spatialsecurity** (`app/spatialsecurity/`) — 18 fichiers C++ (9 headers + 9 implémentations)
  - `SpatialSecurityEnums.h` — 6 enums (RiskType, SecuritySeverity, SecurityPhase, DetectorType, SecurityActionType, SubsystemStatus) + 10 constantes seuil
  - `SpatialSecurityContext` — État sécurité multi-sous-systèmes, pondération risque (fire=0.30, intrusion=0.25, electrical=0.15, network=0.10, domotic=0.10, simulation=0.05, cognition=0.05)
  - `SpatialSecurityMemory` — Mémoire d'incidents persistante (JSON, Jaccard similarity, éviction LRU pondérée résolu)
  - `IntrusionDetector` — Détection intrusion (mouvement pièce vide, mouvement sans chaleur humaine, ouverture inattendue, vitesse suspecte >5m/s, zones interdites). Struct `SecurityAlert` partagée par tous les détecteurs
  - `FireDetector` — Détection incendie (température ≥50°C, hausse >2°C/min, fumée ≥0.3, CO2 ≥1500ppm, anomalie thermique >0.7)
  - `ElectricalRiskDetector` — Détection risque électrique (surcharge circuit, proche surcharge ≥85%, surcharge globale, appareil défaillant >150% nominal, consommation fantôme >50W, anomalie tension/fréquence)
  - `NetworkRiskDetector` — Détection risque réseau (appareil hors-ligne, déconnexion massive >33%, latence ≥500ms, perte paquets >10%, zone morte <-80dBm)
  - `DomoticAnomalyDetector` — Détection anomalies domotiques (lumière pièce vide, HVAC fenêtre ouverte, incohérence capteurs >5°C, boucle automation >5 actions, caméra hors-ligne)
  - `SpatialSecurityEngine` — Orchestrateur pipeline 6 phases (Perception→Analyse→Détection→Évaluation→Planification→Supervision), QML_ELEMENT, auto-cycle 3s, escalade urgence
- **8 panneaux QML** (`qml/cognitive/`)
  - `SecurityPanel` — Dashboard sécurité (niveau global, barre sévérité, alertes actives, contrôle cycle)
  - `IntrusionPanel` — Détail alertes intrusion filtrées (riskType===0)
  - `FirePanel` — Détail alertes incendie/fumée (riskType===1||2) avec indicateurs seuil
  - `ElectricalRiskPanel` — Détail alertes risque électrique (riskType===3)
  - `NetworkRiskPanel` — Détail alertes réseau (riskType===4)
  - `DomoticAnomalyPanel` — Détail alertes anomalies domotiques (riskType===5)
  - `SecurityExplanationPanel` — Sélecteur ComboBox + vue explication détaillée (type, pièce, confiance, analyse)
  - `SecurityDecisionPanel` — Section urgence, actions recommandées, historique incidents

### Modifié
- **SpatialOverlay.qml** — 5 couches sécurité ajoutées (zones interdites avec hachures, alertes sécurité avec pulse urgence, propagation incendie canvas, trajectoires suspectes canvas, appareils hors-ligne)
- **CognitiveTimeline.qml** — Couche "Sécurité" ajoutée (9ème couche, 🔒, #FF4060) + mapping modules sécurité
- **CausalityGraph.qml** — 6 types de nœuds sécurité (intrusion, fire, electrical, network_risk, domotic, security_action) + fonctions `addSecurityAlert()`, `addSecurityAction()` + légende étendue
- `CMakeLists.txt` — 8 sources, 9 headers, 8 QML, include dir `app/spatialsecurity`
- `qml/cognitive/qmldir` — 8 nouvelles entrées
- Version bump 29.0.0 → 29.5.0 (CMakeLists.txt, __init__.py, assistant.conf.example, main.cpp, README.md)

---

## v29.0 — Module de cognition spatiale — Mai 2026

### Ajouté
- **Module spatialcognition** (`app/spatialcognition/`) — 8 fichiers C++, moteur cognitif complet
  - `SpatialEnums.h` — 8 enums (SpatialRelation, KnowledgeNodeType, InferenceType, CognitiveSeverity, GoalType, ActionType, CognitivePhase, SupervisorDecision)
  - `SpatialKnowledgeGraph` — Graphe de connaissances spatial (nœuds, arêtes, BFS, inférence adjacence/accessibilité/visibilité)
  - `SpatialContext` — État contextuel temps réel (pièces, capteurs, appareils, réseau, simulation)
  - `SpatialMemory` — Mémoire épisodique persistante (JSON, Jaccard similarity, éviction LRU pondérée)
  - `SpatialReasoner` — Moteur d'inférence à règles (5 règles par défaut, détection anomalies/risques)
  - `SpatialPlanner` — Planification par objectif (Secure, Illuminate, Ventilate, SaveEnergy, Monitor, Alert)
  - `SpatialSupervisor` — Gouvernance cognitive (validation plans, contraintes sécurité, cohérence, précédent historique)
  - `SpatialCognitiveEngine` — Orchestrateur pipeline 7 phases (Perception→Symbolique→Inférence→Planification→Simulation→Décision→Supervision), QML_ELEMENT, auto-cycle
- **5 panneaux QML** (`qml/cognitive/`)
  - `SpatialCognitionPanel` — Vue d'ensemble (phase, cycle, risque global, métriques graphe, boutons cycle/auto)
  - `SpatialExplanationPanel` — Explications des inférences (sévérité, confiance, détail sélectionnable)
  - `SpatialPredictionPanel` — Prédictions spatiales (confiance, pièce, barre visuelle)
  - `SpatialRiskPanel` — Risques cognitifs (distinct de SimulationRiskPanel, basé sur inférence)
  - `SpatialDecisionPanel` — Plans validés et actions recommandées (priorité, type, cible)

### Modifié
- `CMakeLists.txt` — 7 sources, 8 headers, 5 QML, include dir `app/spatialcognition`
- `qml/cognitive/qmldir` — 5 nouvelles entrées (SpatialCognitionPanel, SpatialExplanationPanel, SpatialPredictionPanel, SpatialRiskPanel, SpatialDecisionPanel)
- Version bump 28.1.0 → 29.0.0 (CMakeLists.txt, __init__.py, assistant.conf.example, main.cpp, README.md)

---

## v28.1 — Intégration réseau/domotique spatiale — Avril 2026

### Ajouté
- **SpatialNetworkIntegration** (`qml/components/SpatialNetworkIntegration.qml`) — bridge WebSocket vers NetworkMap (8790) et HomeGraph (8784)
  - Connexion automatique avec reconnexion, polling 30s
  - Modèles JS : networkDevices, networkLinks, wifiZones, deadZones, domoticEntities, cameras, rooms
  - API publique : refreshNetwork(), refreshHomeGraph(), getDeviceById(), getEntityById(), getCameraById(), getDevicesInRoom(), linkDeviceToItem()
- **5 nouvelles couches SpatialOverlay** (couches 6-10)
  - Couche 6 : Appareils réseau (icône protocole, badge vendor, indicateur RSSI)
  - Couche 7 : Liens réseau (Canvas, couleur par protocole, épaisseur par bande passante, label latence)
  - Couche 8 : Caméras (cône de vision Canvas, angle/FOV/range)
  - Couche 9 : Entités domotiques (icône type, badge valeur, couleur état)
  - Couche 10 : Heatmap WiFi + zones mortes (gradients radiaux, rectangles tirets rouges)
- **Onglet Réseau** dans CognitiveSpatialView — 8ème onglet (🌐), stats connexion, toggles couches overlay
- **Device Picker** dans FloorPlanProperties — popup recherche/sélection d'appareil réseau, affichage vendor/protocol/RSSI/latence

### Étendu
- **FloorPlanController** — 4 nouvelles méthodes C++ : `linkDevice()`, `unlinkDevice()`, `linkedDeviceForItem()`, `deviceInfoForItem()` + signaux `deviceLinked`/`deviceUnlinked` + `m_deviceLinks` hash
- **SpatialOverlay** — 6 nouvelles propriétés (networkDevices, networkLinks, cameras, domoticEntities, wifiZones, deadZones) + 6 toggles show* + 3 signaux (networkDeviceClicked, cameraClicked, domoticEntityClicked)
- **FloorPlanProperties** — injection networkIntegration, section info appareil enrichie, bouton device picker
- **CognitiveSpatialView** — SpatialNetworkIntegration wiring, connexion signaux overlay réseau, tab Réseau

### Fichiers modifiés
- `app/floorplan/FloorPlanController.h` — +12 lignes (méthodes, signal, membre)
- `app/floorplan/FloorPlanController.cpp` — +65 lignes (implémentations device linking)
- `qml/cognitive/SpatialOverlay.qml` — +340 lignes (propriétés, couches 6-10, helpers)
- `qml/cognitive/CognitiveSpatialView.qml` — +120 lignes (netIntegration, tab Réseau, signaux)
- `qml/components/FloorPlanProperties.qml` — +130 lignes (device info, picker popup)
- `qml/components/SpatialNetworkIntegration.qml` — nouveau, ~300 lignes
- `CMakeLists.txt` — +1 QML_FILES (69 total)
- `qml/components/qmldir` — +1 entrée

---

## v28.0 — Simulation spatiale avancée — Avril 2026

### Ajouté
- **Module Simulation C++** (`app/simulation/`) — 7 classes, 13 fichiers (headers + sources)
  - `SimulationEnums` — 7 enums (ScenarioType, EntityType, PropagationType, EntityState, SimState, Severity, CausalNodeType) + constantes
  - `SimulationEntity` — entité légère (UUID, position, vitesse, trajectoire, rayon, intensité, expiration)
  - `SimulationScenario` — scénario configurable + 5 presets (Fire, Intrusion, Blackout, NetworkFailure, Flood) + triggers + JSON persistence
  - `SimulationPropagation` — grille 2D diffusion : fumée, chaleur, bruit, lumière, eau + obstacles + A* pathfinding + heatmap export
  - `SimulationResult` — événements, risques (P×I), graphe causal (nœuds + liens), snapshots par tick
  - `SimulationEngine` — moteur principal : chargement scénario, step entities/propagation/triggers/risks, intégration FloorPlanModel
  - `SimulationController` — bridge QML (14 Q_PROPERTY, 10 Q_INVOKABLE, QTimer playback)
- **6 panneaux cognitifs QML** (`qml/cognitive/`)
  - `SimulationScenarioPanel` — sélection preset, sliders vitesse/intensité/durée, contrôles play/pause/step/stop
  - `SimulationOverlay` — Canvas multi-couches (fumée, chaleur, eau, entités, trajectoires, capteurs)
  - `SimulationCausalityGraph` — graphe interactif (colonnes par type, liens Bézier, pan/zoom)
  - `SimulationRiskPanel` — cartes risques (score global, jauge, barres sévérité/probabilité/impact)
  - `SimulationTimeline` — timeline 5 couches (propagation/capteur/appareil/agent/risque), zoomable
  - `SimulationMinimap` — minimap (pièces, propagation, entités, trajectoires)
- **SimulationPage** (`qml/pages/SimulationPage.qml`) — page 3 colonnes : scénario+minimap | overlay/causalité/timeline | risques
- **50 tests unitaires C++** (`tests/cpp/test_simulation.cpp`) — 50/50 PASS en 11 ms
  - 7 tests SimulationEntity, 7 tests SimulationScenario, 7 tests SimulationPropagation
  - 7 tests SimulationResult, 12 tests SimulationEngine, 1 test constantes

### Modifié
- **Sidebar.qml** — ajout entrée "Simulation" (index 15, icône pipeline.svg)
- **MainWindow.qml** — ajout routage case "simulation" → centralStack index 15
- **CMakeLists.txt** — 6 .cpp sources, 7 .h headers, 7 QML files, include `app/simulation`
- **qml/pages/qmldir** — ajout `SimulationPage 1.0 SimulationPage.qml`
- **qml/cognitive/qmldir** — ajout 6 entrées Simulation*
- **tests/cpp/CMakeLists.txt** — ajout sources simulation + floorplan + LatencyMetrics à exo_testlib
- **PROMPT_MAITRE.md** — v26 → v28, ajout SimulationController aux modules C++, tests → 2349

### Architecture
- **10 pages QML** (était 9) — nouvelle page Simulation
- **56 composants QML** (était 50) — 6 panneaux cognitifs simulation ajoutés
- **Total tests** : 2349 (2299 existants + 50 simulation C++)

---

## v26.1 — Optimisation latence (3 objectifs) — 5 avril 2026

### Modifié
- **ClaudeAPI** : historique conversation limité à **10 derniers messages** (`MAX_HISTORY_TURNS`) — payload réduit, first-token accéléré
- **ClaudeAPI** : cache statique des tool schemas (`buildEXOTools()`) — construction JSON unique au lieu de ~18 tools rebâties à chaque appel
- **TTS Server** : `CHUNK_SIZE` 2048 → **1024** (~21ms @ 24kHz) — streaming plus fins, first-chunk plus rapide
- **TTS Server** : `STREAM_CHUNK_SIZE` 8 → **4** — GPT génère des chunks plus petits, first-audio plus tôt
- **TTSManager** : pré-ouverture audio sink dans `initDSP()` — zéro latence au premier chunk (sink + pump timer actifs dès le boot)
- **TTSManager** : pré-allocation buffer DSP float (`preAllocate(4096)`) — évite l'allocation heap au premier chunk

---

## v26.0 — Conformité architecture + STT performance — 5 avril 2026

### Ajouté
- **MetricsManager** (`app/core/MetricsManager.cpp/h`) — façade métriques unifiée : compteurs, gauges, histogrammes + délégation à LatencyMetrics
- **TraceManager** (`app/core/TraceManager.cpp/h`) — tracing distribué : spans hiérarchiques (trace_id → span_id → parent_id) + délégation à PipelineTracer
- **ErrorManager** (`app/core/ErrorManager.cpp/h`) — gestion centralisée des erreurs : catégorisation (Warning/Error/Critical/Fatal), recovery, compteurs par sévérité, API QML
- **SecurityManager** (`app/core/SecurityManager.cpp/h`) — sécurité et audit : permissions par module, masquage clés API, validation hosts réseau, journal d'audit

### Modifié
- **STT beam-size** : 3 → **1** (greedy decoding) — latence STT réduite de ~60% (`stt_server.py`, `tasks.json`)
- **TRANSCRIBE_TIMEOUT_MS** : 10000 → **20000** (`VoicePipeline.h`) — aligné sur le timeout serveur STT
- **Hallucination filter** : ajout logging `logger.debug()` pour traçabilité des transcriptions filtrées (`stt_server.py`)
- **exo/main.py** : 13 `print()` → `logger.info()` — conformité règle nettoyage Prompt Maître
- **PROMPT_MAITRE.md** : v25.1 → v26, 7 → 15 services documentés, 4 managers C++ ajoutés

### Architecture
- **15 microservices Python** documentés (était 7) : orchestrator, stt, tts, vad, wakeword, memory, nlu, websearch, news, knowledge, tools, planner, executor, verifier, homegraph
- **16 modules C++** : AssistantManager, VoicePipeline, TTSManager, ClaudeAPI, AIMemoryManager, ConfigManager, LogManager, MetricsManager, TraceManager, ErrorManager, SecurityManager, LatencyMetrics, PipelineTracer, ContextCache, WeatherManager + ServiceManager

---

## v25.1 — Framework cognitif standalone — 5 avril 2026

### Ajouté
- **Package `exo/`** — framework cognitif standalone, 61 fichiers, 4299 lignes
- **Core** (`exo/core/`) — `CognitiveKernel` (BaseAgent, MacroAgent, MicroAgent, CognitiveEngine, CognitiveLayer, CognitivePipeline, CognitiveSupervisor), `CognitiveContext` (Rule, Plan, Scenario, SimulationResult, GovernanceDecision, Metric, TraceSpan), `CognitiveState` (KnowledgeGraph, faits/croyances/buts/plans), `CognitiveFlow` (buffers, traces, stats)
- **8 moteurs cognitifs** (`exo/engines/`) — AdvancedRuleEngine, CausalGraphEngine, DeductiveReasoner, InductiveReasoner, AbductiveReasoner, ConstraintSolver, HTNPlusEngine, MultiObjectivePlanner, ScenarioPlanner, SimulationSandbox, PredictiveModelingEngine, OutcomeAnalysisEngine, CognitiveOptimizer, CognitiveTelemetryEngine, StructuredTracingEngine, CognitiveMetricsEngine, GovernancePermissionSystem, GovernanceMultiLevelValidation, GovernanceComplianceEngine, GovernanceAuditEngine
- **8 couches** (`exo/layers/`) — Perception (tokenisation), Extraction (entités/intent/mots-clés), Symbolic (faits/relations), Inference (raisonnement par règles), Planning (HTN), Simulation (sandbox), Decision (arbitrage), Supervision (validation superviseur)
- **3 pipelines** (`exo/pipelines/`) — MainCognitivePipeline (chaîne 8 couches), SimulationPipeline (scénarios → simulation → analyse → arbitrage), PlanningPipeline (HTN → contraintes → multi-objectif)
- **5 agents macro** (`exo/agents/macro/`) — CognitionAgent, SimulationAgent, PlanningAgent, ObservabilityAgent, GovernanceAgent
- **8 agents micro** (`exo/agents/micro/`) — EntityExtractionAgent, RuleVerificationAgent, CausalAnalysisAgent, HTNExpansionAgent, LocalSimulationAgent, RiskAnalysisAgent, LogicValidationAgent, MetricsCollectionAgent
- **Gouvernance** (`exo/governance/`) — PermissionManager, MultiLevelValidator (5 niveaux), ComplianceChecker (4 domaines), AuditLogger
- **Observabilité** (`exo/observability/`) — TelemetryCollector, TracingService, MetricsRegistry, ObservabilityDashboard
- **117 tests** (`exo/tests/`) — test_engines, test_pipelines, test_agents, test_governance, test_observability
- **Point d'entrée** (`exo/main.py`) — démo build_system() + run_demo()
- Total tests : **2335 passés** (2218 existants + 117 nouveaux), 6 skipped, 0 regressions

---

## v25.0 — Gouvernance cognitive renforcée — 5 avril 2026

### Ajouté
- Gouvernance cognitive : permissions, validation multi-niveaux, compliance, audit
- 60 tests gouvernance
- Total tests : **2218 passés**, 6 skipped

---

## v24.0 — Observabilité cognitive — 5 avril 2026

### Ajouté
- Observabilité cognitive : télémétrie, tracing distribué, métriques, dashboard
- 60 tests observabilité
- Total tests : **2158 passés**

---

## v23.0 — Simulation contextuelle — 5 avril 2026

### Ajouté
- Simulation contextuelle : scénarios, sandbox, modèles prédictifs, analyse outcomes
- 55 tests simulation
- Total tests : **2098 passés**

---

## v22.0 — Planification stratégique — 5 avril 2026

### Ajouté
- Planification stratégique : HTN+, multi-objectif, contraintes
- 67 tests planification
- Total tests : **2043 passés**

---

## v21.0 — Système expert étendu — 5 avril 2026

### Ajouté
- Système expert étendu : moteurs de règles avancés, raisonnement causal, inférence abductive
- 66 tests système expert
- Total tests : **1976 passés**

---

## v20.0 — Architecture modulaire ultra-scalable — 5 avril 2026

### Ajouté
- Architecture modulaire ultra-scalable : 9 modules, interfaces abstraites
- 73 tests architecture
- Total tests : **1910 passés**

---

## v19.0 — Optimisation cognitive — 5 avril 2026

### Ajouté
- Optimisation cognitive : optimizer multi-critères, scoring pondéré
- 70 tests optimisation
- Total tests : **1837 passés**

---

## v18.0 — Cognition hiérarchique multi-niveaux — 4 avril 2026

### Ajouté
- Cognition hiérarchique multi-niveaux : orchestration multi-couches
- 71 tests cognition hiérarchique
- Total tests : **1767 passés**

---

## v17.0 — Architecture neuro-symbolique — 4 avril 2026

### Ajouté
- Architecture neuro-symbolique : graphes de connaissance, raisonnement symbolique
- 60 tests neuro-symbolique
- Total tests : **1696 passés**

---

## v16.0 — Agents autonomes supervisés — 4 avril 2026

### Ajouté
- Agents autonomes supervisés, cognition émergente, collaboration multi-agents
- Tests agents autonomes
- Total tests : **1636 passés**

---

## v15.0 — Architecture cognitive complète — 4 avril 2026

### Ajouté
- Architecture cognitive complète : pipeline cognitif end-to-end
- Total tests : **1570 passés**

---

## v14.0 — Cognition distribuée — 4 avril 2026

### Ajouté
- Cognition distribuée, agents spécialisés, communication inter-agents, supervision multi-niveaux, cohérence globale
- Total tests : **1425 passés**

---

## v13.0 — Auto-simulation — 4 avril 2026

### Ajouté
- Auto-simulation, prévision, planification prospective

---

## v12.0 — Auto-réflexion — 4 avril 2026

### Ajouté
- Auto-réflexion, méta-raisonnement, auto-cohérence
- Mémoire v2 — architecture modulaire (6 modules + orchestrateur)

---

## v11.0 — NetworkMap v2 — 30 mars 2026

### Ajouté
- **ARPScanner** (`python/network/arp_scanner.py`) — scan ARP local, extraction IP+MAC, détection gateway, enrichissement vendor
- **MDNSScanner** (`python/network/mdns_scanner.py`) — résolution DNS inverse parallèle, inférence services/type mDNS
- **SSDPScanner** (`python/network/ssdp_scanner.py`) — découverte SSDP/UPnP M-SEARCH multicast, extraction manufacturer
- **PingScanner** (`python/network/ping_scanner.py`) — ping sweep ICMP parallèle (semaphore 20), mesure latence
- **VendorLookup** (`python/network/vendor_lookup.py`) — base OUI IEEE locale, lookup MAC → fabricant
- **DeviceClassifier** (`python/network/device_classifier.py`) — classification automatique par vendor, hostname, services mDNS, SSDP (12 types)
- **TopologyBuilder** (`python/network/topology_builder.py`) — reconstruction topologie étoile, détection gateway/EXO, liens typés (eth/wifi/iot), latence
- **NetworkMapManager** (`python/network/network_map_manager.py`) — orchestrateur unifié : scan_full (ARP+mDNS+SSDP+Ping), scan_fast (ARP), résilience fallback, 14 capabilities

### Modifié
- **NetworkMapService** (`python/network/network_map_service.py`) — réécriture complète : délègue au NetworkMapManager, 15 handlers WS (scan, scan_fast, list_nodes, list_links, get_node, get_topology, get_vendor, get_latency, classify, export, health, restart, metrics, capabilities, metadata)
- **HomeGraph v2** (`python/domotique/homegraph_server.py`) — ajout `run_network_scan()`, `get_network_topology()`, handlers WS "network_scan"/"network_topology"
- **ReseauPage.qml** (`qml/pages/ReseauPage.qml`) — réécriture complète : graphe dynamique Canvas, filtre par type, scan rapide/complet, latence couleur (vert <5ms, jaune <20ms, rouge), sélection nœud + panneau détail, liens typés (eth=bleu, wifi=gris, iot=orange)
- **81 nouveaux tests** — ARPScanner (6), MDNSScanner (9), SSDPScanner (6), PingScanner (8), VendorLookup (5), DeviceClassifier (14), TopologyBuilder (8), NetworkMapManager (12), NetworkMapService (13)
- Total tests : **689 passés** (608 existants + 81 nouveaux)

---

## v10.0 — Domotique v2 — 30 mars 2026

### Ajouté
- **DomoticCache** (`python/domotique/domotic_cache.py`) — cache d'état par device avec TTL, invalidation, stats (hits/misses/hit_rate), thread-safe
- **DiscoveryManager** (`python/domotique/discovery_manager.py`) — moteur de découverte réseau (ARP + mDNS + SSDP + vendor lookup OUI), fusion et dédup
- **EventManager** (`python/domotique/event_manager.py`) — événements push + polling intelligent, subscriptions par device/wildcard, intervalles adaptatifs
- **ScenarioManager** (`python/domotique/scenario_manager.py`) — 6 scénarios prédéfinis (cinéma, nuit, absence, réveil, sécurité, éco), scénarios custom, exécution parallèle, wildcards
- **ScenariosPage.qml** (`qml/pages/ScenariosPage.qml`) — page GUI scénarios (liste, exécution, built-in vs custom)
- **models.py v2** — Protocol (8 valeurs), Connectivity (4 valeurs), DeviceEvent, champs v2 Device (protocol, connectivity, signal_strength, last_event, energy, tags)

### Modifié
- **HomeGraph v2** (`python/domotique/homegraph_server.py`) — intégration DomoticCache, EventManager, ScenarioManager, DiscoveryManager ; nouvelles API : `refresh_device`, `list_by_type`, `get_capabilities`, `get_vendor`, `list_scenarios`, `run_scenario`, `discovery`, `cache_stats`, `event_stats`, `capabilities`, `metadata`
- **5 services domotiques → v2** — samsung, voltalis, echo, domotic, camera : ajout `capabilities()`, `metadata()`, version bump "v2", handlers WS
- **NetworkMapService → v2** (`python/network/network_map_service.py`) — ajout `capabilities()`, `metadata()`
- **MaisonPage.qml** — v2 : section scénarios rapides, signal `scenarioRequested`
- **ReseauPage.qml** — v2 : commentaire header mis à jour
- **43 nouveaux tests** — DomoticCache (8), EventManager (7), ScenarioManager (7), Models v2 (5), HomeGraph v2 (8), Service capabilities (8)
- Total tests : **608 passés** (565 existants + 43 nouveaux)

---

## v9.0 — Observability, Resilience & Security — 30 mars 2026

### Ajouté
- **LogManager** (`python/shared/log_manager.py`) — structured JSON logging, correlation IDs (request_id, session_id), RotatingFileHandler, singleton par service
- **MetricsManager** (`python/shared/metrics_manager.py`) — Counter, Gauge, Histogram, Timer, built-in uptime/requests/errors, snapshot export
- **TraceManager** (`python/shared/trace_manager.py`) — Span/Trace model, distributed tracing, 200-entry history, JSON export
- **ErrorManager** (`python/shared/error_manager.py`) — ErrorCategory (10 catégories), ExoError + sous-classes typées, RETRY_POLICIES, TIMEOUT_POLICIES, with_retry/with_timeout/with_fallback decorators
- **ConfigManager** (`python/shared/config_manager.py`) — config centralisée, dot-notation get/set, hot-reload file watcher, deep merge avec defaults, 12 sections
- **SecurityManager** (`python/shared/security_manager.py`) — PERMISSION_DEFAULTS (4 modules × 10+ actions), AuditLog JSONL append-only, check_permission/authorize/export
- **Resilience** (`python/shared/resilience.py`) — CircuitBreaker (closed→open→half_open), @resilient combined decorator (retry+backoff+timeout+fallback+circuit_breaker)
- **BaseService** (`python/shared/base_service.py`) — classe unifiée intégrant tous les modules v9, health_check(), handle_ws_message() pour protocol v9, begin_request()/end_request() instrumentation, init_v9() one-liner factory
- **Intégration v9 dans 25 microservices** — import + init_v9() dans tous les serveurs (8765–8790)
- **125 nouveaux tests** — test_v9_observability (40), test_v9_resilience (31), test_v9_security (22), test_v9_config (15), test_v9_integration (17)
- Total tests : **565 passés** (440 existants + 125 nouveaux)

### Modifié
- Tous les 25 serveurs Python : ajout `from shared.base_service import init_v9` + `_v9 = init_v9(...)` dans main()
- `python/shared/__init__.py` — docstring v9

---

## v8.1 — Ultra-Low Latency — 30 mars 2026

### Ajouté
- **ContextCache** (`app/core/ContextCache.h/.cpp`) — cache in-process avec TTL par clé, éviction automatique (timer 10 s), refresh en arrière-plan via signaux Qt, thread-safe (QMutex)
- **LatencyMetrics** (`app/core/LatencyMetrics.h/.cpp`) — singleton d'instrumentation pipeline, 9 timestamps (sttStart → responseDone), 6 métriques dérivées (perceivedLatency, endToEnd…), historique rolling 100 snapshots, `getLatencyReport()` exposé au QML
- **ClaudeAPI warmup** — `initWarmup()` envoie un ping léger non-streaming au démarrage (1 token max), `startKeepAlive()` maintient la connexion TCP chaude (timer 240 s)
- **Instrumentation pipeline** — marks LatencyMetrics dans VoicePipeline (sttStart, sttPartialFirst, sttFinal), ClaudeAPI (llmRequest, llmFirstToken, llmComplete), TTSManager (ttsFirstChunk, ttsFirstAudio, responseDone + finalize)
- **Cache tool calls** — AssistantManager wrappe `get_weather` (TTL 60 s) et `get_datetime` (TTL 10 s) via ContextCache, évite les appels réseau redondants
- **27 nouveaux tests** (`tests/python/test_ull.py`) — TestContextCache (11), TestLatencySnapshot (5), TestWarmupKeepAlive (6), TestCacheIntegration (5)
- Total tests : **440 passés** (413 existants + 27 nouveaux)

### Modifié
- `ClaudeAPI.h/.cpp` — ajout warmup/keepalive + 3 marks latency
- `VoicePipeline.cpp` — ajout 3 marks latency (sttStart, sttPartialFirst, sttFinal)
- `TTSManager.h/.cpp` — ajout `m_firstAudioPumped` flag + 3 marks latency + finalize
- `AssistantManager.h/.cpp` — intégration ContextCache + warmup/keepalive init
- `CMakeLists.txt` — ajout ContextCache.cpp/.h et LatencyMetrics.cpp/.h

---

## v5.2 — 29 mars 2026

### Corrigé
- **SIGSEGV startup** : `cleanupProbe()` utilise `deleteLater()` au lieu de `delete` (use-after-free)
- **Wildcards disconnect** : `destroySocket()` via `deleteLater()`, poll timer sans `close()`, filtre LogManager
- **Volume TTS** : crossfade `kSmooth = 0.7` (était 0.3, causait des sauts)
- **Double log TTS** : suppression appel redondant `setXTTSVoice()` dans `TTSManager::setVoice()`
- **Log DSP** : `norm -14dBFS` dans le message (correspondait pas à la vraie valeur)
- **Géolocalisation** : désactivée par défaut (IP retournait ville ISP, pas ville réelle)
- **Config overwrite** : `detectLocation()` ne surcharge plus les villes non-default
- **TTS WARN→INFO** : "Connexion Python réinitialisée" + 3 autres messages backend
- **Météo FR** : localisation forcée `lang=fr` dans l'appel API
- **Startup apply** : pitch, rate, noiseGate, AGC appliqués au démarrage depuis la config

### Ajouté
- 10+ bindings GUI↔Config synchronisés (VAD threshold, audio backend, TTS style/pitch/rate, etc.)

### Supprimé
- Code mort : 7 fichiers QML legacy, 2 backends TTS inutilisés, `handleVoiceCommand()`
- Renommage logging `henri` → `exo`
- **75 fichiers de documentation obsolètes** (archives, doublons, prompts historiques, site HTML)
- Dossiers `docs/`, `docs_site/`, `COPILOT_MASTER_DIRECTIVE.md`

### Refactoré
- Documentation vivante : 3 documents uniques (`PROMPT_MAITRE.md`, `PLAN_IMPLEMENTATION.md`, `CHANGELOG.md`)

---

## v4.2 — 28 mars 2026

### Ajouté
- Design System complet : 19 composants QML, tokens couleur/typo/espacement
- Migration QML pages, panels, components
- ServiceManager auto-launch + SplashScreen + launcher Python

### Refactoré
- Refactoring massif, anti-doublons, documentation (v4.2.1)

---

## v4.1 — Mars 2026

### Ajouté
- STT GPU Vulkan (passage CPU → GPU)
- Dual backend STT (whispercpp + faster-whisper fallback)
- Pipeline FSM 6 états

---

## v4.0 — Juillet 2025

### Ajouté
- Reconception complète depuis zéro
- GUI VS Code dark theme (QML)
- Pipeline FSM initial
- 3 premiers microservices Python (STT, TTS, VAD)
- Claude API avec Function Calling
- Home Assistant integration
