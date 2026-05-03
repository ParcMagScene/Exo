# GUI EXO — Rapport de restructuration

**Date :** Session de refactoring (après IMPLEMENTATION_PHASE3_COMPLETE)  
**Portée :** Architecture QML complète — navigation, layout, icônes, registre de pages  
**Statut :** ✅ Implémenté — 0 erreur QML

---

## 1. Résumé exécutif

La GUI EXO souffrait d'un StackLayout dégradé avec 41 slots dont 23 morts (`Item {}`),
d'un switch/case avec des indices incohérents et des alias obsolètes, d'une icône SVG
manquante, et d'une référence vers un slot mort dans SettingsPage.
Toutes ces régressions ont été corrigées dans cette session.

---

## 2. StackLayout — Avant / Après

### Avant (41 slots, 23 morts)

| Ancien index | Composant | État |
|---|---|---|
| 0 | HomePage | ✅ Actif |
| 1 | SettingsPage | ✅ Actif |
| 2 | HistoryPage | ✅ Actif |
| **3** | **`Item {}`** | ❌ Mort (Logs migré → index 34) |
| 4 | PipelinePage | ✅ Actif |
| **5** | **`Item {}`** | ❌ Mort (MaisonPage → HomePage tabs) |
| **6** | **`Item {}`** | ❌ Mort (ReseauPage → HomePage tabs) |
| 7 | CognitiveTimeline | ✅ Actif |
| 8 | EngineHeatmap | ✅ Actif |
| 9 | VoicePipelineView | ✅ Actif |
| 10 | MemoryInspector | ✅ Actif |
| 11 | GovernancePanel | ✅ Actif |
| 12 | ObservabilityDashboard | ✅ Actif |
| 13 | FloorPlanPage | ✅ Actif |
| **14** | **`Item {}`** | ❌ Mort (StabilityTests → index 40) |
| **15** | **`Item {}`** | ❌ Mort (SimulationSpatiale → index 37) |
| **16** | **`Item {}`** | ❌ Mort (État/Services → index 40) |
| **17–33** | **17× `Item {}`** | ❌ Morts (panneaux cognitifs migrés) |
| 34 | ObservabilityPage | ✅ Actif |
| 35 | PipelinePageExpert | ✅ Actif |
| 36 | VisionPageExpert | ✅ Actif |
| 37 | SimulationPageExpert | ✅ Actif |
| 38 | SpatialCognitionPageExpert | ✅ Actif |
| 39 | SecurityPageExpert | ✅ Actif |
| 40 | DevelopmentPageExpert | ✅ Actif |

### Après (18 slots, 0 mort)

| Nouvel index | Composant | Ancien index |
|---|---|---|
| 0 | HomePage | 0 (inchangé) |
| 1 | SettingsPage | 1 (inchangé) |
| 2 | HistoryPage | 2 (inchangé) |
| 3 | PipelinePage | 4 |
| 4 | CognitiveTimeline | 7 |
| 5 | EngineHeatmap | 8 |
| 6 | VoicePipelineView | 9 |
| 7 | MemoryInspector | 10 |
| 8 | GovernancePanel | 11 |
| 9 | ObservabilityDashboard | 12 |
| 10 | FloorPlanPage | 13 |
| 11 | ObservabilityPage | 34 |
| 12 | PipelinePageExpert | 35 |
| 13 | VisionPageExpert | 36 |
| 14 | SimulationPageExpert | 37 |
| 15 | SpatialCognitionPageExpert | 38 |
| 16 | SecurityPageExpert | 39 |
| 17 | DevelopmentPageExpert | 40 |

**Résultat : -23 slots inutiles, code 2× plus lisible.**

---

## 3. Switch/case navigation — Changements

### Problèmes corrigés

- `case "logs": case "debug":` — indentation invalide (cas imbriqués au lieu de fallthrough)
- Indices obsolètes pointant vers des slots morts ou décalés
- Alias éparpillés dans des sections séparées (`SÉCURITÉ`, `SIMULATION`, `MODE EXPERT`)
- Commentaires `// OBSOLETE:` laissés dans le code de production

### Structure après réorganisation

| Groupe | Cas couverts | Nouvel index |
|---|---|---|
| Pages communes | chat, home, settings, history, maison, reseau, floorplan | 0–2 / showSection |
| Panneaux directs | pipelineLogs, cognitiveTimeline, heatmap | 3, 4, 5 |
| Pipeline/Voice | voicePipeline, pipelineTimeline | 12 (expert) / 6 (normal) |
| Memory/Governance | memory, governance | 7, 8 (expert only) |
| Logs/Observabilité | logs, debug, observability | 11 (expert) / 9 (normal) |
| Vision | vision | 13 (expert only) |
| Simulation | simulation, simScenarios, simTimeline, simComparison | 14 |
| Cognition spatiale | spatialCognition, raisonnement, explications, predictions | 15 |
| Sécurité | security, intrusion, fire, electrical, networkRisk, domoticAnomaly, causality, recommendations | 16 |
| Développement | development, safeboot, services, stability, agents | 17 |

---

## 4. Bugs corrigés

### BUG-NAV-01 — SettingsPage : index 14 → slot mort
**Fichier :** `qml/pages/SettingsPage.qml`  
**Ligne :** ~1862  
**Symptôme :** Clic sur le bouton "Stabilité" affichait un écran vide (`Item {}`)  
**Cause :** `centralStack.currentIndex = 14` pointait vers un slot réservé supprimé  
**Correction :** `centralStack.currentIndex = 17` (DevelopmentPageExpert)

### BUG-NAV-02 — Overlay de secours : index 40 → hors limites après compaction
**Fichier :** `qml\MainWindow.qml`  
**Ligne :** ~1190  
**Symptôme :** Bouton "Ouvrir Services" dans le fallback overlay aurait planté après compaction  
**Correction :** `centralStack.currentIndex = 17`

### BUG-NAV-03 — MenuStructure : icône `icons/vision.svg` inexistante
**Fichier :** `qml/navigation/MenuStructure.qml`  
**Lignes :** 75, 77  
**Symptôme :** Icône Vision absente (Qt affiche un rectangle vide / warning console)  
**Correction :** Remplacé par `icons/heatmap.svg` (icône visuellement cohérente disponible)

### BUG-NAV-04 — switch/case : `case "logs": case "debug":` imbriqués invalides
**Fichier :** `qml/MainWindow.qml`  
**Symptôme :** Indentation trompeuse — `case "debug"` semblait être dans `case "logs"` en JS  
**Correction :** Restructuré en fallthrough propres `case "logs": case "debug": case "observability":`

---

## 5. PageRouter.qml — Transformation

**Avant :** Simple mappeur nom→classe QML, jamais utilisé par MainWindow, références  
de classe sans les indices de StackLayout.

**Après :** Registre canonique documentant les 18 indices, le composant associé et  
les listes de pages par mode. Sert de source de vérité pour les futurs développeurs.

---

## 6. Responsabilités des dossiers QML

| Dossier | Responsabilité | État |
|---|---|---|
| `qml/pages/` | Pages complètes (Normal + Expert) | ✅ Clair |
| `qml/panels/` | Panneaux de monitoring intégrables | ✅ Clair |
| `qml/components/` | Widgets UI réutilisables + vues full-panel | ⚠️ Mixte (voir ci-dessous) |
| `qml/navigation/` | MenuStructure, Sidebar, BottomBar, HeaderBar | ✅ Clair |
| `qml/core/` | Singletons (UIState, PageRouter, Theme) | ✅ Clair |
| `qml/theme/` | Constantes de design (Theme.qml) | ✅ Clair |

### Fichiers orphelins identifiés

| Fichier | Situation | Recommandation |
|---|---|---|
| `qml/pages/MaisonPage.qml` | Contenu migré dans `HomePage.qml` — standalone non utilisé | Conserver (fallback potentiel) ou supprimer après audit |
| `qml/pages/ReseauPage.qml` | Idem — contenu dans `HomePage.qml` | Idem |

### Vues panel-level dans `components/` (à clarifier)

Ces fichiers sont des **pages complètes** mais logés dans `components/` :

- `CognitiveTimeline.qml` (index 4)
- `EngineHeatmap.qml` (index 5)
- `VoicePipelineView.qml` (index 6)
- `MemoryInspector.qml` (index 7)
- `GovernancePanel.qml` (index 8)
- `ObservabilityDashboard.qml` (index 9)
- `PipelineView.qml` (utilisé par PipelinePage)

**Recommandation long terme :** Déplacer vers `qml/panels/` pour clarifier la séparation
widgets réutilisables vs vues standalone.

---

## 7. Recommandations futures

1. **Créer `qml/panels/`** et y déplacer les 6 vues full-panel hors de `components/`
2. **Supprimer MaisonPage.qml et ReseauPage.qml** après confirmation que HomePage les couvre intégralement
3. **Utiliser PageRouter comme seule source de vérité** — brancher MainWindow sur `PageRouter.pageIndex` plutôt que des littéraux en dur
4. **Ajouter un test unitaire QML** vérifiant que chaque `panelName` du MenuStructure a un index valide dans PageRouter
5. **Créer `icons/vision.svg`** dédié (actuellement remplacé par heatmap.svg)

---

## 8. Récapitulatif des fichiers modifiés

| Fichier | Modifications |
|---|---|
| `qml/MainWindow.qml` | StackLayout 41→18 slots ; switch/case réécrit ; index 40→17 (fallback) |
| `qml/pages/SettingsPage.qml` | Index 14→17 (StabilityPanel → DevelopmentPageExpert) |
| `qml/navigation/MenuStructure.qml` | `icons/vision.svg` → `icons/heatmap.svg` (×2) |
| `qml/core/PageRouter.qml` | Réécrit comme registre canonique avec table index↔composant |
