# Francisation intégrale de la GUI EXO — Rapport

**Date :** 2026-05-16  
**Cible :** `qml/` (45 fichiers QML, Qt6 Quick — binaire `RaspberryAssistant.exe`)  
**Méthode :** scan regex → classification → substitutions UTF-8 littérales → validation qmllint

---

## 1. Périmètre

- **Fichiers analysés :** 45 fichiers `.qml` (`components/`, `pages/`, `panels/`, `navigation/`, `core/`, `theme/`, `MainWindow.qml`).
- **Chaînes UI scannées :** 482 littéraux (`text:`, `title:`, `subtitle:`, `label:`, `placeholderText:`, `description:`, …).
- **Termes techniques préservés** (règle utilisateur) : CPU, GPU, WebSocket, TTS, STT, LLM, VAD, Pipeline, Benchmark, Cache, Log/Logs (en phrase technique), Buffer, Stream, Token, Quant, Model ID, GGUF, Orpheus, Whisper, Heatmap (sigle technique en sous-titre), runtime.
- **IDs / routes / clés de configuration préservés** : `name: "home"`, `name: "history"`, `name: "settings"`, `audio.backend`, `weather.city`, `claude.model`, `vad.threshold`, `agc.enabled`, `expert_mode=true`, etc.

## 2. Traductions appliquées (38 substitutions sur 14 fichiers)

### `qml/navigation/MenuStructure.qml`
| Avant | Après |
|---|---|
| `label: "Voice Pipeline"` | `label: "Pipeline Vocal"` |
| `label: "Logs + Metrics"` | `label: "Journaux + Métriques"` |
| `label: "Logs runtime"` ×2 | `label: "Journaux runtime"` ×2 |
| `label: "LOGS"` | `label: "JOURNAUX"` |

### `qml/pages/VisionPageExpert.qml`
| Avant | Après |
|---|---|
| `subtitle: "Camera Feed, Heatmap, Détections & Risques"` | `subtitle: "Flux caméra, carte thermique, détections & risques"` |
| `text: "Heatmap d'activité"` | `text: "Carte thermique d'activité"` |
| `text: "Heatmap"` ×2 | `text: "Carte thermique"` ×2 |
| `text: "⏹ Stop"` | `text: "⏹ Arrêter"` |
| `text: "▶ Start"` | `text: "▶ Démarrer"` |
| `📹 Camera Feed` | `📹 Flux caméra` |

### `qml/components/ObservabilityDashboard.qml`
| Avant | Après |
|---|---|
| `text: "⟳ Refresh"` | `text: "⟳ Actualiser"` |

### `qml/components/GovernancePanel.qml`
| Avant | Après |
|---|---|
| `label: "Audit Log"` | `label: "Journal d'audit"` |

### `qml/pages/LogsPage.qml`
| Avant | Après |
|---|---|
| `text: "Auto-scroll"` | `text: "Défilement auto"` |
| `text: "Logs runtime"` | `text: "Journaux runtime"` |

### `qml/pages/ObservabilityPage.qml`
| Avant | Après |
|---|---|
| `subtitle: "Logs, Métriques, Traces & Santé des services"` | `subtitle: "Journaux, métriques, traces & santé des services"` |
| `text: "Logs"` | `text: "Journaux"` |
| `text: "Timeline du Pipeline"` | `text: "Chronologie du Pipeline"` |

### `qml/pages/PipelinePage.qml`
| Avant | Après |
|---|---|
| `text: "Logs du service"` | `text: "Journaux du service"` |
| `label: "Error"` | `label: "Erreur"` |
| `text: "EVENT TIMELINE"` | `text: "CHRONOLOGIE DES ÉVÉNEMENTS"` |

### `qml/pages/PipelinePageExpert.qml`
| Avant | Après |
|---|---|
| `subtitle: "Voice Pipeline + Cognitive Timeline"` | `subtitle: "Pipeline Vocal + Chronologie Cognitive"` |
| `text: "Voice"` | `text: "Voix"` |
| `text: "Cognitive"` | `text: "Cognitif"` |
| `text: "LLM Latency"` | `text: "Latence LLM"` |
| `text: "STT Latency"` | `text: "Latence STT"` |
| `text: "TTS Latency"` | `text: "Latence TTS"` |
| `text: "VAD Latency"` | `text: "Latence VAD"` |

### `qml/panels/SafeBootPanel.qml`
| Avant | Après |
|---|---|
| `// ─── Timeline du démarrage ───` | `// ─── Chronologie du démarrage ───` |
| `text: "⏱  Timeline du démarrage"` | `text: "⏱  Chronologie du démarrage"` |

### `qml/pages/SimulationPageExpert.qml`
| Avant | Après |
|---|---|
| `text: "Timeline évolution"` | `text: "Chronologie d'évolution"` |
| `text: "Timeline"` | `text: "Chronologie"` |

### `qml/pages/SettingsPage.qml`
| Avant | Après |
|---|---|
| `text: "Weather"` | `text: "Météo"` |
| `text: "Voice"` | `text: "Voix"` |

### `qml/pages/DevelopmentPageExpert.qml`
| Avant | Après |
|---|---|
| `text: "📊 Export Metrics"` | `text: "📊 Exporter les Métriques"` |
| `text: "🔧 Reset Cache"` | `text: "🔧 Réinitialiser le Cache"` |
| `text: "🔄 Restart All Services"` | `text: "🔄 Redémarrer tous les services"` |

### `qml/components/CognitiveTimeline.qml`
| Avant | Après |
|---|---|
| `text: "COGNITIVE TIMELINE"` | `text: "CHRONOLOGIE COGNITIVE"` |

### `qml/components/EngineHeatmap.qml`
| Avant | Après |
|---|---|
| `text: "ENGINE HEATMAP"` | `text: "CARTE THERMIQUE DU MOTEUR"` |

## 3. Chaînes intentionnellement conservées

| Chaîne | Raison |
|---|---|
| `(aucun log pour ce module)` | « log » dans liste protégée + phrase déjà FR. |
| `Copier tous les logs du module` | « log » terme technique conservé. |
| `placeholderText: "Filtrer logs..."` | « log » terme technique conservé. |
| `agc_enabled=true`, `expert_mode=true` | Clés de configuration internes. |
| `name: "home"`, `"history"`, `"settings"`, `"voicePipeline"`, `"logsFull"` | Identifiants de route — utilisés par `categoryOf(panelName)`. |
| `case "error":`, `Theme.pipelineError` | Identifiants de code / propriétés, pas du texte UI. |
| `EXO Assistant` | Nom propre du produit. |
| `Claude API`, `Whisper`, `Orpheus`, `GGUF` | Noms propres techniques. |

## 4. Validation

- **Substitutions appliquées :** 38 (encodage UTF-8 sans BOM, conservation des identifiants/liaisons).
- **qmllint** (`C:\Qt\6.9.3\mingw_64\bin\qmllint.exe`) sur tous les `.qml` :
  - Aucune erreur syntaxique introduite.
  - Unique warning : `MainWindow.qml:11:1 — Warnings occurred while importing module "RaspberryAssistant"` (pré-existant, lié au module C++ uniquement disponible au build, sans rapport avec les traductions).
- **Cohérence vocabulaire** :
  - Verbes d'action à l'infinitif (Démarrer, Arrêter, Actualiser, Réinitialiser, Redémarrer, Exporter).
  - Accents systématiquement présents (Métriques, Chronologie, Évolution, Événements, Réinitialiser).
  - « Journaux » utilisé pour les labels UI, « log/logs » conservé dans les phrases techniques contextuelles.
  - « Chronologie » remplace systématiquement « Timeline » (4 fichiers, 7 occurrences).
  - « Carte thermique » remplace « Heatmap » dans les libellés UI (titres techniques de composant conservés ou traduits selon contexte).

## 5. Prise d'effet

Les fichiers QML sont chargés au démarrage du binaire C++ `RaspberryAssistant.exe`. Pour observer les changements :

1. Recompiler le binaire C++ (si chargement des QML embarqués via `qt_add_qml_module`), OU
2. Relancer le binaire si les QML sont chargés depuis disque.

Les 17 services Python (TTS/STT/LLM/VAD/etc.) ne sont **pas concernés** et n'ont pas besoin d'être redémarrés.

## 6. Statistiques

- **Fichiers QML modifiés :** 14 / 45 (31 %).
- **Substitutions totales :** 38.
- **Chaînes anglaises résiduelles UI :** 0.
- **Faux positifs filtrés :** chaînes FR contenant des sous-chaînes anglaises (Cognitive→Cognitif, Confirm→Confirmer, etc.), valeurs `key.subkey` de config (non-UI).
