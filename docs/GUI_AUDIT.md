# GUI_AUDIT.md — Audit complet de la GUI EXO (QML)

**Date :** 2025-05-01  
**Analyseur :** GitHub Copilot (Claude Sonnet 4.6)  
**Portée :** Tous les fichiers QML du projet EXO (`qml/`)  
**Statut :** Correctifs appliqués pour les bugs critiques et majeurs

---

## Table des matières

1. [Architecture GUI](#1-architecture-gui)
2. [Inventaire des fichiers QML](#2-inventaire-des-fichiers-qml)
3. [Rapport de bugs](#3-rapport-de-bugs)
4. [Plan de correction](#4-plan-de-correction)
5. [Statut des correctifs](#5-statut-des-correctifs)

---

## 1. Architecture GUI

### Fenêtre principale
- `qml/MainWindow.qml` — `ApplicationWindow` racine
  - **Sidebar** (`qml/panels/Sidebar.qml`) — navigation latérale dynamique
  - **HeaderBar** (`qml/panels/HeaderBar.qml`) — en-tête avec titre + `ModeSwitch` + `ExoPipelineStatus`
  - **StackLayout** (41 items, indices 0–40) — contenu central
  - **BottomBar** (`qml/panels/BottomBar.qml`) — barre du bas
  - **SafeBootPanel** (`qml/panels/SafeBootPanel.qml`) — overlay mode dégradé (z=999)

### Singletons QML
| Fichier | Déclaration qmldir | pragma Singleton | Utilisation |
|---|---|---|---|
| `qml/core/UIState.qml` | `UIState 1.0 UIState.qml` (sans `singleton`) | ✅ | `UIState.expertMode`, `UIState.setExpertMode()` |
| `qml/core/PageRouter.qml` | `PageRouter 1.0 PageRouter.qml` (sans `singleton`) | ✅ | ❌ jamais utilisé |
| `qml/navigation/MenuStructure.qml` | `singleton MenuStructure 1.0` ✅ | ✅ | `MenuStructure.getCategories()`, `MenuStructure.refreshMenu()` |

### Mapping StackLayout (41 items)
| Index | Contenu | État |
|---|---|---|
| 0 | `HomePage` | ✅ Actif |
| 1 | `SettingsPage` | ✅ Actif |
| 2 | `HistoryPage` | ✅ Actif |
| 3 | `Item {}` | ❌ Vide (mappé à "logs") |
| 4 | `PipelinePage` | ✅ Actif |
| 5 | `MaisonPage` | ⚠️ Doublon (aussi dans HomePage) |
| 6 | `ReseauPage` | ⚠️ Doublon (aussi dans HomePage) |
| 7 | `CognitiveTimeline` | ✅ Actif |
| 8 | `EngineHeatmap` | ✅ Actif |
| 9 | `VoicePipelineView` | ✅ Actif |
| 10 | `MemoryInspector` | ✅ Actif |
| 11 | `GovernancePanel` | ✅ Actif |
| 12 | `ObservabilityDashboard` | ✅ Actif |
| 13 | `FloorPlanPage` | ✅ Actif |
| 14 | `Item {}` | ❌ Vide (mappé à "stability") |
| 15 | `Item {}` | ❌ Vide (mappé à "simulation" mode normal) |
| 16 | `Item {}` | ❌ Vide (mappé à "safeboot"/"services"/"development" mode normal) |
| 17–33 | `Item {}` × 17 | ❌ Tous vides (anciens panneaux cognitifs migrés) |
| 34 | `ObservabilityPage` | ✅ Actif |
| 35 | `PipelinePageExpert` | ✅ Actif |
| 36 | `VisionPageExpert` | ✅ Actif |
| 37 | `SimulationPageExpert` | ✅ Actif |
| 38 | `SpatialCognitionPageExpert` | ✅ Actif |
| 39 | `SecurityPageExpert` | ✅ Actif |
| 40 | `DevelopmentPageExpert` | ✅ Actif |

---

## 2. Inventaire des fichiers QML

### `qml/` — Racine
- `MainWindow.qml`

### `qml/core/`
- `UIState.qml` — Singleton état (expertMode, safeboot)
- `PageRouter.qml` — Singleton mapping panelName→page (non utilisé)

### `qml/navigation/`
- `MenuStructure.qml` — Singleton structure menu Normal/Expert

### `qml/panels/`
- `Sidebar.qml` — Repeater dynamique depuis MenuStructure
- `HeaderBar.qml` — Barre d'en-tête, titre, ModeSwitch
- `BottomBar.qml` — Barre inférieure
- `SafeBootPanel.qml` — Overlay plein écran mode dégradé

### `qml/pages/`
- `HomePage.qml` — Page principale (chat, onglets maison/réseau/plan)
- `SettingsPage.qml` — Paramètres complets
- `HistoryPage.qml` — Historique des conversations
- `PipelinePage.qml` — Pipeline monitoring simple
- `MaisonPage.qml` — Domotique
- `ReseauPage.qml` — Réseau
- `FloorPlanPage.qml` — Plan de maison 2D
- `ObservabilityPage.qml` — Logs + métriques (mode expert)
- `PipelinePageExpert.qml` — Pipeline expert
- `VisionPageExpert.qml` — Vision artificielle
- `SimulationPageExpert.qml` — Simulation de scénarios
- `SpatialCognitionPageExpert.qml` — Cognition spatiale
- `SecurityPageExpert.qml` — Sécurité
- `DevelopmentPageExpert.qml` — Services & développement

### `qml/components/`
- `ModeSwitch.qml` — Toggle Expert/Simple
- `ExoStatusIndicator.qml` — Dot + texte statut vocal
- `ExoPipelineStatus.qml` — Pill état pipeline dans HeaderBar
- `ExoSplashScreen.qml` — Écran de démarrage
- `VoicePipelineView.qml` — Visualisation 9 étapes pipeline
- `CognitiveTimeline.qml`, `EngineHeatmap.qml`, `MemoryInspector.qml`
- `GovernancePanel.qml`, `ObservabilityDashboard.qml`
- `ExoContextPanel.qml`, `ExoPlanProgress.qml`
- `PipelineView.qml`, `FloorPlanTools.qml`, etc.

---

## 3. Rapport de bugs

### BUG-GUI-01 [CRITIQUE] — ModeSwitch déconnecté de UIState

**Fichier :** `qml/panels/HeaderBar.qml`  
**Sévérité :** CRITIQUE — Fonctionnalité principale cassée  
**Impact :** Cliquer le bouton Simple/Expert dans la barre d'en-tête ne change pas le mode global

**Description :**  
`HeaderBar.qml` instancie `ModeSwitch { id: modeSwitch }` sans aucun handler `onModeChanged` et sans binding vers `UIState.expertMode`. Le composant `ModeSwitch.qml` expose `signal modeChanged(bool isExpert)` mais ce signal n'est jamais connecté. Résultat : le toggle visuel fonctionne en local mais n'affecte ni `UIState.expertMode`, ni le menu, ni la navigation.

Seul le `Switch expertModeToggle` dans `SettingsPage.qml` fonctionne correctement.

**Code problématique :**
```qml
// HeaderBar.qml
ModeSwitch {
    id: modeSwitch
    // Manque: expertMode binding + onModeChanged handler
}
```

**Correctif :**
```qml
ModeSwitch {
    id: modeSwitch
    expertMode: typeof UIState !== 'undefined' ? UIState.expertMode : false
    onModeChanged: function(isExpert) {
        if (typeof UIState !== 'undefined') UIState.setExpertMode(isExpert)
        if (typeof MenuStructure !== 'undefined') MenuStructure.refreshMenu()
    }
    Connections {
        target: typeof UIState !== 'undefined' ? UIState : null
        function onExpertModeChanged() {
            modeSwitch.expertMode = UIState.expertMode
        }
    }
}
```

---

### BUG-GUI-02 [CRITIQUE] — MenuStructure : items maison/réseau routent vers "home"

**Fichier :** `qml/navigation/MenuStructure.qml`  
**Sévérité :** CRITIQUE — Navigation cassée  
**Impact :** Cliquer "MAISON → Appareils" ou "RÉSEAU → Topologie" en mode normal navigue toujours vers "Accueil" au lieu des sections maison/réseau de HomePage

**Description :**  
Dans `normalCategories`, les catégories "maison" et "reseau" ont leurs items avec `name: "home"` au lieu de `name: "maison"` et `name: "reseau"`. La Sidebar émet `panelSelected("home")` quand on clique ces items, ce qui déclenche `homePage.showSection("home")` au lieu de `showSection("maison")` ou `showSection("reseau")`.

Même bug dans `expertCategories` pour la catégorie "maison" (MAISON + RÉSEAU).

**Code problématique :**
```js
// normalCategories — ligne ~30
{ id: "maison", label: "MAISON", items: [
    { name: "home", icon: "icons/maison.svg", label: "Appareils" }  // BUG: name devrait être "maison"
]},
{ id: "reseau", label: "RÉSEAU", items: [
    { name: "home", icon: "icons/reseau.svg", label: "Topologie" }  // BUG: name devrait être "reseau"
]},

// expertCategories — ligne ~185
{ id: "maison", label: "MAISON + RÉSEAU", items: [
    { name: "home", icon: "icons/maison.svg", label: "Maison & Réseau" }  // BUG: devrait être "maison"
]},
```

**Correctif :** Changer `name: "home"` → `name: "maison"` et `name: "reseau"` pour les items concernés.

---

### BUG-GUI-03 [MAJEUR] — StackLayout : indices fantômes (Item{} vides)

**Fichier :** `qml/MainWindow.qml`  
**Sévérité :** MAJEURE — Écrans blancs sur certaines navigations  
**Impact :** Plusieurs cases du switch de navigation routent vers des `Item {}` vides (indices 3, 14, 15, 16, 17–33)

**Détail des cas problématiques :**

| Case(s) | Index actuel | Contenu | Devrait aller vers |
|---|---|---|---|
| `"logs"`, `"debug"` | 3 | `Item {}` vide | 34 (`ObservabilityPage`) |
| `"stability"` | 14 | `Item {}` vide | 40 (`DevelopmentPageExpert`) ou supprimer |
| `"simulation"` (mode normal) | 15 | `Item {}` vide | 37 (`SimulationPageExpert`) |
| `"development"` (mode normal) | 16 | `Item {}` vide | 40 (`DevelopmentPageExpert`) |
| `"safeboot"`, `"services"` | 16 | `Item {}` vide | 40 (`DevelopmentPageExpert`) |
| `"pipelineTimeline"` | 33 | `Item {}` vide | 35 (`PipelinePageExpert`) |
| `"spatialCognition"` (mode normal) | 17 | `Item {}` vide | 38 (`SpatialCognitionPageExpert`) |
| `"security"` (mode normal) | 22 | `Item {}` vide | 39 (`SecurityPageExpert`) |
| Cognitifs anciens (18–32) | 18–32 | `Item {}` vides | Supprimer les cases obsolètes |

**Correctif :** Mettre à jour le switch de `onPanelSelected` pour pointer vers les nouveaux indices valides.

---

### BUG-GUI-04 [MAJEUR] — Doublons MaisonPage / ReseauPage

**Fichier :** `qml/MainWindow.qml`  
**Sévérité :** MAJEURE — Double instanciation, double connexions C++  
**Impact :** `MaisonPage` et `ReseauPage` sont instanciées deux fois : indices 5-6 dans `centralStack` ET comme onglets dans `HomePage.qml`

**Description :**  
Les instances aux indices 5 et 6 de `centralStack` ne sont jamais navigables (le routing "maison"/"reseau" va toujours à index 0 + `showSection()`). Ces doublons créent des connexions C++ en double et des ressources inutiles.

**Correctif :** Remplacer les instances aux indices 5 et 6 par `Item {}`.

---

### BUG-GUI-05 [MOYEN] — HeaderBar.pageTitles : clés incohérentes et manquantes

**Fichier :** `qml/panels/HeaderBar.qml`  
**Sévérité :** MOYENNE — Titres de page incorrects  
**Impact :** Le nom brut du panel s'affiche dans le breadcrumb pour de nombreuses pages (ex: "voicePipeline" au lieu de "Voice Pipeline")

**Description :**  
La map `pageTitles` utilise des clés en minuscules ("voicepipeline") alors que les `panelName` réels sont en camelCase ("voicePipeline"). De plus, plusieurs pages n'ont pas d'entrée.

**Entrées manquantes/incorrectes :**
- `"voicepipeline"` devrait être `"voicePipeline"`
- Manquants : `"home"`, `"development"`, `"vision"`, `"simulation"`, `"spatialCognition"`, `"security"`, `"pipeline"` (camelCase)

**Correctif :** Corriger les clés et ajouter les entrées manquantes.

---

### BUG-GUI-06 [MOYEN] — Sidebar : activePanel initial "chat" inconnu

**Fichier :** `qml/panels/Sidebar.qml`  
**Sévérité :** MOYENNE — Aucun item actif visuellement au démarrage  
**Impact :** La valeur initiale `activePanel: "chat"` ne correspond à aucun item dans MenuStructure (les items s'appellent "home", "settings", etc.) → aucun item n'est surligné au démarrage

**Correctif :** Changer `activePanel: "chat"` → `activePanel: "home"`.

---

### BUG-GUI-07 [MINEUR] — core/qmldir : UIState et PageRouter non déclarés singletons

**Fichier :** `qml/core/qmldir`  
**Sévérité :** MINEURE — Comportement singleton potentiellement invalide  
**Impact :** Sans le mot-clé `singleton` dans le qmldir, le comportement de `pragma Singleton` pour les imports de répertoire est non garanti en Qt 6

**Code actuel :**
```
UIState 1.0 UIState.qml
PageRouter 1.0 PageRouter.qml
```

**Correctif :**
```
singleton UIState 1.0 UIState.qml
singleton PageRouter 1.0 PageRouter.qml
```

---

### BUG-GUI-08 [MINEUR] — PageRouter singleton non utilisé (dead code)

**Fichier :** `qml/core/PageRouter.qml`  
**Sévérité :** MINEURE — Incohérence d'architecture  
**Impact :** `PageRouter.qml` définit un mapping `panelName → composant QML` mais `MainWindow.qml` utilise un `switch/case` avec indices numériques bruts. Les deux mécanismes coexistent sans interaction.

**Recommandation :** Soit migrer le routing vers `PageRouter`, soit supprimer `PageRouter.qml`. Pas bloquant.

---

## 4. Plan de correction

| Priorité | Bug | Fichier | Effort |
|---|---|---|---|
| 🔴 CRITIQUE | BUG-GUI-01 ModeSwitch déconnecté | `HeaderBar.qml` | ~10 lignes |
| 🔴 CRITIQUE | BUG-GUI-02 MenuStructure name:"home" | `MenuStructure.qml` | ~3 lignes |
| 🟠 MAJEUR | BUG-GUI-03 Indices fantômes switch | `MainWindow.qml` | ~20 lignes |
| 🟠 MAJEUR | BUG-GUI-04 Doublons MaisonPage/ReseauPage | `MainWindow.qml` | ~5 lignes |
| 🟡 MOYEN | BUG-GUI-05 pageTitles incomplets | `HeaderBar.qml` | ~10 lignes |
| 🟡 MOYEN | BUG-GUI-06 activePanel initial "chat" | `Sidebar.qml` | ~1 ligne |
| 🟢 MINEUR | BUG-GUI-07 qmldir singleton manquant | `core/qmldir` | ~2 lignes |
| 🟢 MINEUR | BUG-GUI-08 PageRouter dead code | — | Refactoring |

---

## 5. Statut des correctifs

| Bug | Statut | Commit/Note |
|---|---|---|
| BUG-GUI-01 | ✅ **CORRIGÉ** | HeaderBar.qml : ModeSwitch bindé à UIState |
| BUG-GUI-02 | ✅ **CORRIGÉ** | MenuStructure.qml : name "maison"/"reseau" |
| BUG-GUI-03 | ✅ **CORRIGÉ** | MainWindow.qml : cases fantômes redirigées |
| BUG-GUI-04 | ✅ **CORRIGÉ** | MainWindow.qml : doublons remplacés par Item{} |
| BUG-GUI-05 | ✅ **CORRIGÉ** | HeaderBar.qml : pageTitles complets camelCase |
| BUG-GUI-06 | ✅ **CORRIGÉ** | Sidebar.qml : activePanel initial = "home" |
| BUG-GUI-07 | ✅ **CORRIGÉ** | core/qmldir : singleton keyword ajouté |
| BUG-GUI-08 | 🔲 EN ATTENTE | PageRouter dead code — refactoring futur |
