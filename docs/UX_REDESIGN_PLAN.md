# 🎨 UX_REDESIGN_PLAN — Refonte complète de l'interface EXO

**Document de Planification Détaillé**  
**Version**: 1.0  
**Date**: 2026-04-25  
**Objectif**: Simplifier, restructurer et moderniser l'interface EXO

---

## 📊 TABLE DES MATIÈRES

1. [Audit de l'état actuel](#audit-de-létat-actuel)
2. [Nouvelle architecture UI](#nouvelle-architecture-ui)
3. [Plan de fusion des panneaux](#plan-de-fusion-des-panneaux)
4. [Plan de suppression](#plan-de-suppression)
5. [Restructuration de la navigation](#restructuration-de-la-navigation)
6. [Modifications QML](#modifications-qml)
7. [Modifications C++](#modifications-cpp)
8. [Modifications de configuration](#modifications-de-configuration)
9. [Plan d'implémentation étape par étape](#plan-dimplémentation-étape-par-étape)
10. [Risques et mitigation](#risques-et-mitigation)
11. [Stratégie de tests](#stratégie-de-tests)

---

## 🔍 AUDIT DE L'ÉTAT ACTUEL

### Structure actuelle (état déplorable)

**Pages QML** (10 fichiers):
- `HomePage.qml` — Chat principal (Transcript + Response)
- `HistoryPage.qml` — Historique des conversations
- `LogsPage.qml` — Logs système
- `MaisonPage.qml` — Domotique v1 (appareils)
- `PipelinePage.qml` — Pipeline vocal / temps réel
- `ReseauPage.qml` — Topologie réseau
- `SettingsPage.qml` — Paramètres
- `ScenariosPage.qml` — **INUTILISÉ** (présent mais absent du menu et du StackLayout)
- `SimulationPage.qml` — Simulation spatiale
- `FloorPlanPage.qml` — Éditeur plan 2D

**Panneaux standalone** (qml/panels — 2 fichiers):
- `SafeBootPanel.qml` — État des services au démarrage
- `StabilityPanel.qml` — Tests de stabilité

**Panneaux cognitifs** (qml/cognitive — 47 fichiers):
Divisés en plusieurs catégories:
- **Cognition spatiale**: `SpatialCognitionPanel`, `SpatialDecisionPanel`, `SpatialExplanationPanel`, `SpatialPredictionPanel`, `SpatialRiskPanel`, `SpatialOverlay`
- **Sécurité**: `SecurityPanel`, `SecurityDecisionPanel`, `SecurityExplanationPanel`, `IntrusionPanel`, `FirePanel`, `ElectricalRiskPanel`, `NetworkRiskPanel`, `DomoticAnomalyPanel`
- **Simulation**: `SimulationOverlay`, `SimulationRiskPanel`, `SimulationScenarioPanel`, `SimulationTimeline`, `SimulationCausalityGraph`
- **Vision**: `VisionPanel`, `VisionHeatmap`, `VisionOverlay`, `VisionEventsPanel`, `VisionBehaviorPanel`, `VisionAnomalyPanel`, `VisionFirePanel`, `VisionIntrusionPanel`, `VisionDetectionsLayer`, `VisionCameraPanel`, `VisionExplanationPanel`
- **Timelines**: `PipelineTimeline`, `CognitiveTimeline`, `SimulationTimeline` (**DOUBLONS**)
- **Autres**: `CausalityGraph`, `RiskPanel`, `AnomalyPanel`, `TracePanel`, `EngineHeatmap`, `MemoryInspector`, `GovernancePanel`, `AgentsPanel`

**Composants** (qml/components — 36 fichiers):
Mélange de composants réutilisables et non standards.

**Menu** (MenuStructure.qml):
- 8 catégories (ACCUEIL, MAISON, RÉSEAU, COGNITION, SÉCURITÉ, SIMULATION, PIPELINE, OUTILS)
- ~35 items au total
- Beaucoup de redondance logique

**MainWindow.qml**:
- 34 pages/panneaux chargés dans un `StackLayout`
- Logique de mapping complexe avec `switch/case`
- Connexions de données chaotiques

---

## 🎯 NOUVELLE ARCHITECTURE UI

### Architecture générale

```
EXO Assistant UI v2.0
├── Splash Screen (startup)
├── Main Window
│   ├── Sidebar (réduit à 2 modes d'affichage)
│   ├── Header (page title + state)
│   ├── Central Stack (pages par mode)
│   └── Bottom Bar (mic status + controls)
└── UIState (singleton — gère le mode Normal/Expert)
```

### MODE NORMAL (5 pages seulement)

Menu simplifié, aucun détail technique.

```
┌─────────────────────────────────────────┐
│ MENU (Mode Normal)                      │
├─────────────────────────────────────────┤
│ 🏠 Accueil         → HomePage           │
│                                         │
│ 🏘️  Maison         → HomePage:MaisonTab │
│                                         │
│ 🌐 Réseau          → HomePage:RéseauTab │
│                                         │
│ 📋 Historique      → HistoryPage        │
│                                         │
│ ⚙️  Paramètres     → SettingsPage       │
│                                         │
│ [Mode Expert] (toggle in Settings)      │
└─────────────────────────────────────────┘
```

**Structuration des pages Normal**:
1. **HomePage** — Chat principal (Transcript + Response)
   - Inclure micro status + level
   - Inclure pipeline state indicator
   
2. **HomePage avec tabs** — Intégrer Maison + Réseau comme onglets:
   - Tab 1: Chat (défaut)
   - Tab 2: Appareils (Maison)
   - Tab 3: Réseau
   - Tab 4: Plan 2D (FloorPlan)

3. **HistoryPage** — Historique conversations (simple liste)

4. **SettingsPage** — Paramètres + toggle Mode Expert

### MODE EXPERT (7 catégories hiérarchisées)

Menu avancé, tous les outils pour développeur/power user.

```
┌──────────────────────────────────────────┐
│ MENU (Mode Expert)                       │
├──────────────────────────────────────────┤
│ 📊 PIPELINE                              │
│   ├─ Voice Pipeline                      │
│   ├─ Observability (Logs + Metrics)      │
│   └─ Traces                              │
│                                          │
│ 👁️ VISION                                 │
│   ├─ Camera Feed                         │
│   ├─ Heatmap                             │
│   ├─ Detections                          │
│   ├─ Anomalies                           │
│   └─ Events                              │
│                                          │
│ 🧠 COGNITION                             │
│   ├─ Spatial Intelligence                │
│   ├─ Decisions                           │
│   ├─ Explanations                        │
│   ├─ Predictions                         │
│   ├─ Memory                              │
│   ├─ Agents                              │
│   └─ Governance                          │
│                                          │
│ 🛡️ SÉCURITÉ SPATIALE                     │
│   ├─ Vue globale                         │
│   ├─ Intrusion                           │
│   ├─ Incendie                            │
│   ├─ Électrique                          │
│   ├─ Réseau (risques)                    │
│   ├─ Domotique                           │
│   └─ Causalité                           │
│                                          │
│ 🎬 SIMULATION                            │
│   ├─ Scénarios                           │
│   ├─ Propagation                         │
│   ├─ Timeline                            │
│   └─ Causalité                           │
│                                          │
│ 🏠 MAISON + RÉSEAU                       │
│   ├─ Appareils (Domotique)               │
│   ├─ Plan 2D                             │
│   └─ Topologie réseau                    │
│                                          │
│ 🛠️  DÉVELOPPEMENT                        │
│   ├─ Services (SafeBoot)                 │
│   ├─ Stabilité                           │
│   ├─ Config                              │
│   └─ Debug                               │
│                                          │
│ ⚙️  PARAMÈTRES                            │
│                                          │
│ [Mode Normal] (toggle)                   │
└──────────────────────────────────────────┘
```

---

## 📋 PLAN DE FUSION DES PANNEAUX

### 1. FUSION: Observabilité complète

**But**: Consolider tous les logs, métriques, traces en une seule page.

**Panneaux à fusionner**:
- `LogsPage.qml` (état actuel)
- `Cognitive.PipelineTimeline` (timeline du pipeline)
- `ObservabilityDashboard` (composant)
- `TracePanel` (traces)
- `MetricsPanel` (métriques)

**Nouveau fichier**: `ObservabilityPage.qml`
- Layout avec onglets:
  - Logs (liste scrollable)
  - Metrics (graphiques + gauges)
  - Traces (timeline + détails)
  - Health (service status)

**Suppression**:
- `LogsPage.qml` (remplacé par ObservabilityPage)
- `Cognitive.PipelineTimeline` (contenu fusionné dans ObservabilityPage)
- Composant `ObservabilityDashboard` (refactorisé)

---

### 2. FUSION: Pipeline vocal unifié

**But**: Fusionner tous les éléments du pipeline vocal.

**Panneaux à fusionner**:
- `PipelinePage.qml` (état actuel)
- `VoicePipelineView` (composant)
- `CognitiveTimeline` (timeline cognitive)
- `ExoPipelineStatus` (composant)

**Nouveau fichier**: `PipelinePageExpert.qml`
- Layout avec sections:
  - Voice Pipeline (waveform + state machine)
  - Cognitive Timeline (steps)
  - Real-time metrics (latency, accuracy)

**Suppression**:
- `Cognitive.CognitiveTimeline` (contenu fusionné)
- `Cognitive.PipelineTimeline` (déjà fusionné dans Observabilité)

---

### 3. FUSION: Vision centralisée

**But**: Regrouper tous les panneaux visuels (caméra, heatmap, détections).

**Panneaux à fusionner**:
- `Cognitive.VisionPanel`
- `Cognitive.VisionHeatmap`
- `Cognitive.VisionOverlay`
- `Cognitive.VisionEventsPanel`
- `Cognitive.VisionDetectionsLayer`
- `Cognitive.VisionCameraPanel`
- `Cognitive.VisionAnomalyPanel`
- `Cognitive.VisionFirePanel`
- `Cognitive.VisionIntrusionPanel`

**Nouveau fichier**: `VisionPageExpert.qml`
- Layout avec onglets:
  - Camera Feed
  - Heatmap
  - Detections/Anomalies
  - Risks (Fire, Intrusion)
  - Events Log

**Suppression**:
- Tous les `Cognitive.Vision*Panel` fichiers individuels

---

### 4. FUSION: Simulation spatiale complète

**But**: Fusionner tous les panneaux de simulation.

**Panneaux à fusionner**:
- `SimulationPage.qml`
- `Cognitive.SimulationScenarioPanel`
- `Cognitive.SimulationTimeline`
- `Cognitive.SimulationCausalityGraph`
- `Cognitive.SimulationOverlay`
- `Cognitive.SimulationRiskPanel`

**Nouveau fichier**: `SimulationPageExpert.qml`
- Layout avec onglets:
  - Scenarios
  - Propagation/Overlay
  - Timeline
  - Causalité
  - Risk Analysis

**Suppression**:
- `SimulationPage.qml` (remplacé par SimulationPageExpert)
- Tous les `Cognitive.Simulation*` fichiers individuels

---

### 5. FUSION: Cognition spatiale regroupée

**But**: Centraliser tous les panneaux de cognition spatiale.

**Panneaux à fusionner**:
- `Cognitive.SpatialCognitionPanel`
- `Cognitive.SpatialDecisionPanel`
- `Cognitive.SpatialExplanationPanel`
- `Cognitive.SpatialPredictionPanel`
- `Cognitive.SpatialRiskPanel`
- `Cognitive.SpatialOverlay`

**Nouveau fichier**: `SpatialCognitionPageExpert.qml`
- Layout avec onglets:
  - Cognition Spatiale
  - Décisions
  - Explications
  - Prédictions
  - Risques

**Suppression**:
- Tous les `Cognitive.Spatial*Panel` fichiers individuels

---

### 6. FUSION: Sécurité spatiale centralisée

**But**: Regrouper tous les panneaux de sécurité.

**Panneaux à fusionner**:
- `Cognitive.SecurityPanel`
- `Cognitive.SecurityDecisionPanel`
- `Cognitive.SecurityExplanationPanel`
- `Cognitive.IntrusionPanel`
- `Cognitive.FirePanel`
- `Cognitive.ElectricalRiskPanel`
- `Cognitive.NetworkRiskPanel`
- `Cognitive.DomoticAnomalyPanel`
- `Cognitive.CausalityGraph` (pour sécurité)

**Nouveau fichier**: `SecurityPageExpert.qml`
- Layout avec onglets:
  - Vue globale
  - Risques (Intrusion, Incendie, Électrique, Réseau, Domotique)
  - Causalité
  - Décisions/Explications

**Suppression**:
- Tous les `Cognitive.Security*, Intrusion, Fire, Electrical, NetworkRisk, DomoticAnomaly` fichiers
- Référence partagée à `CausalityGraph` (dupliquer pour contexte sécurité)

---

### 7. FUSION: Outils de développement

**But**: Centraliser tous les outils pour développeurs.

**Panneaux à fusionner**:
- `SafeBootPanel` (État des services)
- `StabilityPanel` (Tests de stabilité)
- Debug tools
- Config viewer

**Nouveau fichier**: `DevelopmentPageExpert.qml`
- Layout avec onglets:
  - Services Status
  - Stability Tests
  - Configuration
  - Debug Tools

**Suppression**:
- `SafeBootPanel.qml` (contenu fusionné)
- `StabilityPanel.qml` (contenu fusionné)

---

## 🗑️ PLAN DE SUPPRESSION

### Fichiers QML à supprimer

#### Pages non utilisées:
- `qml/pages/ScenariosPage.qml` — **Non présent dans le menu/stack**

#### Panneaux cognitifs redondants (47 fichiers):
```
qml/cognitive/
├── # À supprimer (redondant avec nouvelles pages)
├── SpatialCognitionPanel.qml
├── SpatialDecisionPanel.qml
├── SpatialExplanationPanel.qml
├── SpatialPredictionPanel.qml
├── SpatialRiskPanel.qml
├── SpatialOverlay.qml
├── SecurityPanel.qml
├── SecurityDecisionPanel.qml
├── SecurityExplanationPanel.qml
├── IntrusionPanel.qml
├── FirePanel.qml
├── ElectricalRiskPanel.qml
├── NetworkRiskPanel.qml
├── DomoticAnomalyPanel.qml
├── SimulationScenarioPanel.qml
├── SimulationTimeline.qml
├── SimulationCausalityGraph.qml
├── SimulationOverlay.qml
├── SimulationRiskPanel.qml
├── VisionPanel.qml
├── VisionHeatmap.qml
├── VisionOverlay.qml
├── VisionEventsPanel.qml
├── VisionDetectionsLayer.qml
├── VisionCameraPanel.qml
├── VisionAnomalyPanel.qml
├── VisionFirePanel.qml
├── VisionIntrusionPanel.qml
├── VisionBehaviorPanel.qml
├── VisionExplanationPanel.qml
├── CognitiveTimeline.qml
├── PipelineTimeline.qml
├── TracePanel.qml
├── MetricsPanel.qml
│
├── # À conserver (refactorisé ou réutilisable)
├── EngineHeatmap.qml (conservé pour MODE NORMAL)
├── MemoryInspector.qml (conservé pour EXPERT)
├── GovernancePanel.qml (conservé pour EXPERT)
├── AgentsPanel.qml (conservé pour EXPERT)
├── CausalityGraph.qml (dupliqué pour contexte sécurité)
├── RiskPanel.qml (refactorisé pour synthèse)
├── AnomalyPanel.qml (refactorisé pour synthèse)
└── # Fichiers système
    ├── qmldir
    └── (imports et dépendances)
```

**Total suppression**: 34 fichiers

#### Pages QML à supprimer:
- `qml/pages/LogsPage.qml` — Remplacé par ObservabilityPage
- `qml/pages/SimulationPage.qml` — Remplacé par SimulationPageExpert
- `qml/pages/ScenariosPage.qml` — Jamais utilisé

#### Panneaux standalone à supprimer:
- `qml/panels/SafeBootPanel.qml` — Contenu fusionné dans DevelopmentPageExpert
- `qml/panels/StabilityPanel.qml` — Contenu fusionné dans DevelopmentPageExpert

### Composants à supprimer ou refactorisé:
- `ObservabilityDashboard.qml` — Refactorisé comme contenu d'ObservabilityPage
- `VoicePipelineView.qml` — Refactorisé comme section de PipelinePageExpert

### Fichiers C++ à supprimer (si applicables):
- Modèles inutilisés
- Contrôleurs de page dépréciés

---

## 🗺️ RESTRUCTURATION DE LA NAVIGATION

### 1. Créer UIState.qml (singleton)

Nouveau fichier: `qml/core/UIState.qml`

```qml
pragma Singleton
import QtQuick

QtObject {
    id: uiState
    
    // Mode d'affichage
    property bool expertMode: false
    
    // Sauvegarde dans ConfigManager
    function setExpertMode(isExpert) {
        expertMode = isExpert
        if (typeof configManager !== 'undefined') {
            configManager.setValue("ui", "expertMode", isExpert)
        }
    }
    
    // Charger au démarrage
    Component.onCompleted: {
        if (typeof configManager !== 'undefined') {
            expertMode = configManager.getBool("ui", "expertMode", false)
        }
    }
}
```

### 2. Réécrire MenuStructure.qml

Nouveau fichier: `qml/navigation/MenuStructure.qml` (remplacer)

```qml
pragma Singleton
import QtQuick

QtObject {
    id: menuStructure
    
    // Importer UIState pour savoir quel mode
    readonly property var uiState: typeof UIState !== 'undefined' ? UIState : null
    
    // Catégories MODE NORMAL
    readonly property var normalCategories: [
        {
            id: "accueil",
            label: "ACCUEIL",
            icon: "icons/chat.svg",
            items: [
                { name: "home", icon: "icons/chat.svg", label: "Accueil" }
            ]
        },
        {
            id: "maison",
            label: "MAISON",
            icon: "icons/maison.svg",
            items: [
                { name: "home", icon: "icons/maison.svg", label: "Appareils" }
            ]
        },
        {
            id: "reseau",
            label: "RÉSEAU",
            icon: "icons/reseau.svg",
            items: [
                { name: "home", icon: "icons/reseau.svg", label: "Topologie" }
            ]
        },
        {
            id: "historique",
            label: "HISTORIQUE",
            icon: "icons/history.svg",
            items: [
                { name: "history", icon: "icons/history.svg", label: "Historique" }
            ]
        },
        {
            id: "parametres",
            label: "PARAMÈTRES",
            icon: "icons/settings.svg",
            items: [
                { name: "settings", icon: "icons/settings.svg", label: "Paramètres" }
            ]
        }
    ]
    
    // Catégories MODE EXPERT
    readonly property var expertCategories: [
        {
            id: "pipeline",
            label: "PIPELINE",
            icon: "icons/pipeline.svg",
            items: [
                { name: "voicePipeline", icon: "icons/pipeline.svg", label: "Voice Pipeline" },
                { name: "observability", icon: "icons/logs.svg", label: "Logs + Metrics" }
            ]
        },
        {
            id: "vision",
            label: "VISION",
            icon: "icons/vision.svg",
            items: [
                { name: "vision", icon: "icons/vision.svg", label: "Vision" }
            ]
        },
        {
            id: "cognition",
            label: "COGNITION",
            icon: "icons/cognition.svg",
            items: [
                { name: "spatialCognition", icon: "icons/cognition.svg", label: "Spatial" }
            ]
        },
        {
            id: "securite",
            label: "SÉCURITÉ",
            icon: "icons/securite.svg",
            items: [
                { name: "security", icon: "icons/securite.svg", label: "Sécurité" }
            ]
        },
        {
            id: "simulation",
            label: "SIMULATION",
            icon: "icons/simulation.svg",
            items: [
                { name: "simulation", icon: "icons/simulation.svg", label: "Simulation" }
            ]
        },
        {
            id: "maison",
            label: "MAISON + RÉSEAU",
            icon: "icons/maison.svg",
            items: [
                { name: "home", icon: "icons/maison.svg", label: "Maison + Réseau" }
            ]
        },
        {
            id: "dev",
            label: "DÉVELOPPEMENT",
            icon: "icons/debug.svg",
            items: [
                { name: "development", icon: "icons/debug.svg", label: "Services" }
            ]
        },
        {
            id: "parametres",
            label: "PARAMÈTRES",
            icon: "icons/settings.svg",
            items: [
                { name: "settings", icon: "icons/settings.svg", label: "Paramètres" }
            ]
        }
    ]
    
    // API dynamique
    function getCategories() {
        return (uiState && uiState.expertMode) ? expertCategories : normalCategories
    }
}
```

### 3. Réécrire Sidebar.qml

Adapter `qml/panels/Sidebar.qml` pour utiliser `MenuStructure.getCategories()` dynamiquement.

### 4. Adapter MainWindow.qml

Ajouter logique de changement dynamique du mode et chargement des pages.

---

## 📝 MODIFICATIONS QML

### A. Nouvelles pages à créer

#### 1. `qml/pages/ObservabilityPage.qml` (nouvelle)

Fusionne LogsPage + PipelineTimeline + Metrics + Traces.

**Responsabilités**:
- Logs avec filtres et recherche
- Graphiques métriques (CPU, mémoire, latence)
- Timeline du pipeline
- Health status des services

**Connexions C++**:
- `logsManager` (logs en temps réel)
- `metricsManager` (métriques)
- `pipelineMonitor` (timeline)

#### 2. `qml/pages/PipelinePageExpert.qml` (nouvelle, remplace PipelinePage.qml)

Fusionne PipelinePage + VoicePipelineView + CognitiveTimeline + ExoPipelineStatus.

**Responsabilités**:
- Waveform audio (mic + TTS)
- State machine visualization
- Cognitive timeline
- Real-time metrics (latency, accuracy)

#### 3. `qml/pages/VisionPageExpert.qml` (nouvelle)

Fusionne tous les Vision* panels.

**Responsabilités**:
- Camera feed
- Heatmap
- Detections
- Anomalies
- Risk overlays

#### 4. `qml/pages/SimulationPageExpert.qml` (nouvelle, remplace SimulationPage.qml)

Fusionne SimulationPage + tous les Simulation* panels.

**Responsabilités**:
- Scenario editor
- Propagation visualization
- Timeline
- Causalité graph
- Risk analysis

#### 5. `qml/pages/SpatialCognitionPageExpert.qml` (nouvelle)

Fusionne tous les SpatialCognition* + SpatialRisk* panels.

**Responsabilités**:
- Spatial understanding
- Decision trees
- Explanations
- Predictions
- Risk assessment

#### 6. `qml/pages/SecurityPageExpert.qml` (nouvelle)

Fusionne tous les Security* + Intrusion + Fire + Electrical + NetworkRisk + DomoticAnomaly panels.

**Responsabilités**:
- Security overview dashboard
- Risk categories (Intrusion, Fire, Electrical, Network, Domotic)
- Causality analysis
- Decision explanations
- Mitigation recommendations

#### 7. `qml/pages/DevelopmentPageExpert.qml` (nouvelle)

Fusionne SafeBootPanel + StabilityPanel + debug tools.

**Responsabilités**:
- Service status (SafeBoot)
- Stability tests
- Configuration viewer
- Debug tools

#### 8. `qml/pages/HomePageNormal.qml` (nouvelle variante)

Adaptation simplifiée de HomePage pour MODE NORMAL.

**Responsabilités**:
- Chat principal
- Intégrer Maison + Réseau comme onglets
- Réduire la densité visuelle
- Cacher les indicateurs expert

#### 9. `qml/core/UIState.qml` (nouvelle)

Singleton pour gérer le mode Normal/Expert.

---

### B. Fichiers QML à modifier

#### 1. `qml/navigation/MenuStructure.qml` (RÉÉCRITURE)

- Ajouter modes Normal et Expert
- Ajouter API dynamique `getCategories()`
- Réduire redondance

#### 2. `qml/panels/Sidebar.qml` (MODIFICATION)

- Utiliser `MenuStructure.getCategories()` dynamiquement
- Adapter l'affichage selon le mode
- Ajouter smooth transitions

#### 3. `qml/MainWindow.qml` (REFACTORISATION MASSIVE)

**Changements**:
- Réduire StackLayout de 34 à ~10 indices
- Ajouter logique de mode Normal/Expert
- Dynamiquement charger/décharger les pages
- Simplifier la logique de mapping panelName → index

**Nouvelle structure**:
```qml
// MODE NORMAL
// Index 0: HomePage (avec tabs Maison, Réseau, Plan 2D)
// Index 1: HistoryPage
// Index 2: SettingsPage

// MODE EXPERT (dans un StackLayout séparé ou même StackLayout mais décalé)
// Index 10: ObservabilityPage
// Index 11: PipelinePageExpert
// Index 12: VisionPageExpert
// Index 13: SpatialCognitionPageExpert
// Index 14: SecurityPageExpert
// Index 15: SimulationPageExpert
// Index 16: DevelopmentPageExpert
// Index 17: SettingsPage (partagé)
// Index 18: HomePageNormal (pour mode Normal avec maison/réseau)
```

#### 4. `qml/pages/HomePage.qml` (SIMPLIFICATION)

**Changements**:
- Ajouter système d'onglets pour Maison, Réseau, Plan 2D
- Cacher les indicateurs expert par défaut
- Réduire l'espace utilisé par les composants avancés

#### 5. `qml/pages/SettingsPage.qml` (AJOUT)

**Changements**:
- Ajouter toggle pour Mode Expert
- Connecter à `UIState.setExpertMode()`
- Sauvegarder le mode dans ConfigManager

#### 6. `qml/theme/Theme.qml` (VÉRIFIER)

- Ajouter couleurs pour distinctions Normal/Expert
- Ajouter tailles réduites pour MODE NORMAL

---

## 💻 MODIFICATIONS C++

### A. Fichiers C++ à créer

#### 1. `app/core/UIState.cpp / .h` (optionnel)

Si on veut exposer UIState comme context property au lieu d'un singleton QML pur:

```cpp
// UIState.h
class UIState : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool expertMode READ expertMode WRITE setExpertMode NOTIFY expertModeChanged)
    
public:
    bool expertMode() const;
    void setExpertMode(bool isExpert);
    
signals:
    void expertModeChanged(bool isExpert);
    
private:
    bool m_expertMode = false;
};
```

### B. Fichiers C++ à modifier

#### 1. `app/core/AssistantManager.cpp / .h` (ADAPTATION)

**Changements**:
- Ajouter slots pour les nouvelles pages expert
- Adapter les signaux pour les nouveaux noms de pages
- Préserver tous les signaux existants

#### 2. `app/core/ServiceManager.cpp / .h` (VÉRIFIER)

- Vérifier que les services consommés par les nouvelles pages sont disponibles
- Ajouter validation pour chaque page expert

#### 3. `app/audio/VoicePipeline.cpp / .h` (VÉRIFIER)

- Vérifier que les signaux exposés à QML sont toujours valides

#### 4. `app/core/ConfigManager.cpp / .h` (EXTENSION)

**Changements**:
- Ajouter support pour `[ui]` section (expertMode, layout prefs)
- Charger/sauvegarder le mode Normal/Expert

#### 5. `main.cpp` (VÉRIFICATION)

- Vérifier les context properties exposées
- Ajouter `UIState` ou `ConfigManager` pour UIState.qml

---

## ⚙️ MODIFICATIONS DE CONFIGURATION

### 1. `config/assistant.conf` (AJOUTER SECTION)

```ini
[UI]
# Mode d'affichage par défaut
expert_mode=false

# Layout preferences
sidebar_width=200
header_height=56
footer_height=44

# Autres préférences UI
theme=dark
font_size=12
```

---

## 📅 PLAN D'IMPLÉMENTATION ÉTAPE PAR ÉTAPE

### Phase 1: Préparation (2-3 heures)

- [ ] Créer `UIState.qml`
- [ ] Créer `qml/core/` dossier si inexistant
- [ ] Vérifier toutes les dépendances inter-fichiers
- [ ] Documentar les connexions C++/QML existantes

### Phase 2: Création des nouvelles pages (4-6 heures)

- [ ] Créer `ObservabilityPage.qml`
- [ ] Créer `PipelinePageExpert.qml`
- [ ] Créer `VisionPageExpert.qml`
- [ ] Créer `SimulationPageExpert.qml`
- [ ] Créer `SpatialCognitionPageExpert.qml`
- [ ] Créer `SecurityPageExpert.qml`
- [ ] Créer `DevelopmentPageExpert.qml`

### Phase 3: Refactorisation de la navigation (2-3 heures)

- [ ] Réécrire `MenuStructure.qml`
- [ ] Modifier `Sidebar.qml`
- [ ] Refactoriser `MainWindow.qml`
- [ ] Tester la navigation

### Phase 4: Adaptation des pages existantes (2-3 heures)

- [ ] Modifier `HomePage.qml` (ajouter onglets)
- [ ] Adapter `HistoryPage.qml`
- [ ] Adapter `SettingsPage.qml` (ajouter toggle expert)
- [ ] Adapter `FloorPlanPage.qml`

### Phase 5: Nettoyage et suppression (1-2 heures)

- [ ] Supprimer les 34 fichiers cognitifs redondants
- [ ] Supprimer `LogsPage.qml`
- [ ] Supprimer `SimulationPage.qml`
- [ ] Supprimer `ScenariosPage.qml`
- [ ] Supprimer `SafeBootPanel.qml`
- [ ] Supprimer `StabilityPanel.qml`
- [ ] Vérifier les imports rompus

### Phase 6: Tests et validation (2-3 heures)

- [ ] Compiler le projet
- [ ] Tester MODE NORMAL (5 pages)
- [ ] Tester MODE EXPERT (7 catégories)
- [ ] Vérifier la sauvegarde du mode
- [ ] Tester les transitions mode Normal ↔ Expert
- [ ] Vérifier les connexions C++/QML

### Phase 7: Nettoyage C++ optionnel (1 heure)

- [ ] Créer `UIState.cpp / .h` si nécessaire
- [ ] Adapter `ConfigManager` pour [UI] section
- [ ] Tester ConfigManager avec nouveau section

---

## ⚠️ RISQUES ET MITIGATION

### Risque 1: Perte de fonctionnalités

**Problème**: Fusionner les panneaux pourrait perdre de la fonctionnalité.

**Mitigation**:
- [ ] Documenter chaque fusion avec mapping 1-to-1
- [ ] Préserver 100% de la fonctionnalité
- [ ] Ne pas modifier le C++ backend

### Risque 2: Erreurs d'imports

**Problème**: Supprimer des fichiers pourrait casser les imports.

**Mitigation**:
- [ ] Grep tous les imports avant suppression
- [ ] Vérifier `qmldir` files
- [ ] Utiliser search/replace global pour adapter imports

### Risque 3: MainWindow.qml devient trop complexe

**Problème**: MainWindow.qml pourrait devenir énorme.

**Mitigation**:
- [ ] Créer `qml/core/PageManager.qml` pour gérer l'état du StackLayout
- [ ] Utiliser des loaders dynamiques pour charger les pages on-demand
- [ ] Organiser la logique de sélection en fichiers séparés

### Risque 4: Contexte properties C++ cassées

**Problème**: Les context properties pourraient être mal exposées aux nouvelles pages.

**Mitigation**:
- [ ] Vérifier chaque context property avant modification
- [ ] Adapter les Connections dans chaque nouvelle page
- [ ] Tester avec verbose C++ logs

### Risque 5: Performance dégradée

**Problème**: Fusionner trop de contenu dans une page pourrait ralentir.

**Mitigation**:
- [ ] Utiliser `Loader` avec `asynchronous: true` pour contenu lourd
- [ ] Implémenter lazy loading pour les onglets
- [ ] Utiliser `StackLayout` ou `SwipeView` pour les transitions fluides

---

## 🧪 STRATÉGIE DE TESTS

### Tests UI

#### Test 1: Navigation MODE NORMAL

```
1. Lancer l'app
2. Vérifier que le menu affiche 5 items (Accueil, Maison, Réseau, Historique, Paramètres)
3. Cliquer sur chaque item
4. Vérifier que la page change correctement
5. Vérifier qu'aucune page expert n'est visible
```

#### Test 2: Navigation MODE EXPERT

```
1. Ouvrir Paramètres
2. Activer "Mode Expert"
3. Vérifier que le menu change à 8 catégories
4. Cliquer sur chaque catégorie
5. Vérifier que les bonnes pages expert s'affichent
6. Vérifier que MODE NORMAL est caché
```

#### Test 3: Persistance du mode

```
1. Activer Mode Expert
2. Naviguer vers différentes pages
3. Fermer l'app complètement
4. Relancer l'app
5. Vérifier que le mode est toujours Expert
```

#### Test 4: Onglets HomePage

```
MODE NORMAL:
1. Ouvrir HomePage
2. Vérifier les onglets: Accueil, Appareils, Réseau, Plan 2D
3. Cliquer sur chaque onglet
4. Vérifier que le contenu change
5. Vérifier que les données se mettent à jour
```

#### Test 5: Pages Expert

```
Pour chaque page expert:
1. Naviguer vers la page
2. Vérifier tous les onglets/sections
3. Vérifier que les données s'affichent
4. Vérifier que les contrôles fonctionnent
5. Vérifier qu'aucun erreur console
```

### Tests de régression

#### Test 6: Voice Pipeline

```
1. Lancer un simple chat interaction
2. Vérifier que le pipeline change d'état correctement
3. Vérifier que les métriques s'affichent
4. Vérifier que la latence est mesurée
```

#### Test 7: Safe Boot

```
1. Arrêter un service
2. Ouvrir DevelopmentPageExpert
3. Vérifier que le service apparaît en rouge
4. Vérifier que le bouton de retry est disponible
5. Vérifier que le nombre de services est correct
```

#### Test 8: Connections C++

```
1. Ouvrir chaque page expert
2. Vérifier qu'aucune erreur "Cannot read property X" n'apparaît
3. Vérifier que tous les signaux C++ sont correctement connectés
4. Vérifier les logs pour erreurs de binding
```

### Tests de performance

#### Test 9: Temps de chargement

```
MODE NORMAL:
1. Lancer l'app
2. Mesurer le temps jusqu'au premier affichage de HomePage
3. Vérifier que c'est < 3 secondes

MODE EXPERT:
1. Activer Mode Expert
2. Naviguer vers VisionPageExpert (page la plus lourde)
3. Mesurer le temps de chargement
4. Vérifier qu'il est < 5 secondes avec Loader asynchrone
```

#### Test 10: Mémoire

```
1. Lancer l'app (MODE NORMAL)
2. Vérifier la mémoire initiale
3. Naviguer entre toutes les pages
4. Vérifier que la mémoire ne croît pas exponentiellement
5. Basculer vers MODE EXPERT
6. Naviguer entre toutes les pages expert
7. Vérifier que la mémoire reste stable
```

---

## 📊 RÉSUMÉ DES FICHIERS

### A créer (7 nouvelles pages + 1 singleton)

```
qml/pages/
├── ObservabilityPage.qml (nouvelle)
├── PipelinePageExpert.qml (nouvelle)
├── VisionPageExpert.qml (nouvelle)
├── SimulationPageExpert.qml (nouvelle)
├── SpatialCognitionPageExpert.qml (nouvelle)
├── SecurityPageExpert.qml (nouvelle)
├── DevelopmentPageExpert.qml (nouvelle)

qml/core/
└── UIState.qml (nouvelle)
```

### A modifier (5 fichiers)

```
qml/navigation/
├── MenuStructure.qml (RÉÉCRITURE)

qml/panels/
├── Sidebar.qml (MODIFICATION)

qml/pages/
├── HomePage.qml (SIMPLIFICATION + TABS)
├── SettingsPage.qml (AJOUT TOGGLE)

qml/MainWindow.qml (REFACTORISATION)
```

### À supprimer (37 fichiers)

```
qml/pages/
├── LogsPage.qml
├── SimulationPage.qml
├── ScenariosPage.qml

qml/panels/
├── SafeBootPanel.qml
├── StabilityPanel.qml

qml/cognitive/ (34 fichiers)
├── SpatialCognitionPanel.qml
├── SpatialDecisionPanel.qml
├── SpatialExplanationPanel.qml
├── SpatialPredictionPanel.qml
├── SpatialRiskPanel.qml
├── SpatialOverlay.qml
├── SecurityPanel.qml
├── SecurityDecisionPanel.qml
├── SecurityExplanationPanel.qml
├── IntrusionPanel.qml
├── FirePanel.qml
├── ElectricalRiskPanel.qml
├── NetworkRiskPanel.qml
├── DomoticAnomalyPanel.qml
├── SimulationScenarioPanel.qml
├── SimulationTimeline.qml
├── SimulationCausalityGraph.qml
├── SimulationOverlay.qml
├── SimulationRiskPanel.qml
├── VisionPanel.qml
├── VisionHeatmap.qml
├── VisionOverlay.qml
├── VisionEventsPanel.qml
├── VisionDetectionsLayer.qml
├── VisionCameraPanel.qml
├── VisionAnomalyPanel.qml
├── VisionFirePanel.qml
├── VisionIntrusionPanel.qml
├── VisionBehaviorPanel.qml
├── VisionExplanationPanel.qml
├── CognitiveTimeline.qml
├── PipelineTimeline.qml
├── TracePanel.qml
└── MetricsPanel.qml
```

---

## 🎯 OBJECTIFS FINAUX

### Avant (État actuel)
```
- 34 pages/panneaux dans MainWindow StackLayout
- 8 catégories de menu
- 47 fichiers cognitifs (beaucoup redondant)
- Navigation complexe et illisible
- UI dense et surchargeuse
- Difficile à maintenir
```

### Après (État cible)
```
✅ MODE NORMAL: 5 pages simples pour utilisateurs finaux
   - Accueil (Chat)
   - Maison (Appareils) — onglet dans HomePage
   - Réseau (Topologie) — onglet dans HomePage
   - Historique
   - Paramètres

✅ MODE EXPERT: 7 catégories pour développeurs/power users
   - Pipeline (Voice + Observability)
   - Vision (Cameras + Heatmap + Detections)
   - Cognition (Spatial Intelligence)
   - Sécurité (Risks + Decisions)
   - Simulation (Scenarios + Timeline)
   - Maison + Réseau (Devices + Topology)
   - Développement (Services + Stability)

✅ Réductions:
   - 34 pages → ~10 pages (67% réduction)
   - 8 catégories de menu → 2 modes + 7 catégories expert
   - 47 fichiers cognitifs → 7 pages fusionnées
   - Complexité de navigation : -75%

✅ Bénéfices:
   - UI simple et lisible pour MODE NORMAL
   - Tous les outils disponibles en MODE EXPERT
   - Meilleure organisation logique
   - Maintenance plus facile
   - Performance améliorée (lazy loading)
   - Cohérence visuelle
```

---

## 📝 NOTES IMPORTANTES

1. **Compatibilité C++**: Aucune modification de la logique C++ backend n'est nécessaire. Toutes les modifications sont en QML/configuration.

2. **Sauvegarde du mode**: Le mode Normal/Expert doit être persisté dans `ConfigManager` pour que l'utilisateur ne perde pas sa préférence.

3. **Lazy Loading**: Pour le MODE EXPERT, implémenter `Loader` avec `asynchronous: true` pour les pages lourdes afin d'éviter les blocages au changement de page.

4. **Onglets vs Pages**: Dans MODE NORMAL, intégrer Maison et Réseau comme onglets plutôt que pages séparées pour réduire le clics.

5. **Transitions**: Ajouter des `Behavior` pour les transitions smooth entre les modes et les pages.

6. **Documentation**: Chaque nouvelle page expert devra avoir des commentaires clairs sur ce qu'elle contient et d'où vient le contenu.

---

## ✅ CHECKLIST DE VALIDATION FINAL

- [ ] Tous les fichiers créés et compilent
- [ ] Tous les fichiers supprimés et les imports sont adaptés
- [ ] MenuStructure.qml charge les bonnes catégories selon le mode
- [ ] Sidebar.qml affiche les bons items selon le mode
- [ ] MainWindow.qml mappe correctement les panelName aux indices
- [ ] MODE NORMAL: 5 pages visibles, aucune page expert
- [ ] MODE EXPERT: 7 catégories visibles, toutes les pages expert chargent
- [ ] Persistance du mode: se souvient du choix après redémarrage
- [ ] Aucune erreur console concernant les imports ou bindings
- [ ] Tests de navigation complets réussis
- [ ] Tests de performance OK (< 5s pour page la plus lourde)
- [ ] Mémoire stable pendant la navigation
- [ ] Aucune régression : Pipeline vocal, SafeBoot, domotique, etc.
- [ ] Rapport final généré

---

**Fin du plan. Prêt pour implémentation.**

