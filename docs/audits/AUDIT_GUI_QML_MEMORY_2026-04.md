# 🔍 AUDIT GUI Qt/QML — EXO v5.2

**Date** : 1er avril 2026
**Scope** : GUI Qt 6.9.3 / QML — Fuites mémoire, cycle de vie, performance rendu
**Fichiers audités** : 26 fichiers QML + 6 fichiers C++ (audio/core)

---

## Table des matières

1. [Résumé exécutif](#1-résumé-exécutif)
2. [Cycle de vie QML](#2-cycle-de-vie-qml)
3. [Fuites mémoire QML](#3-fuites-mémoire-qml)
4. [Textures GPU / Canvas / ShaderEffect](#4-textures-gpu--canvas--shadereffect)
5. [WebSocket](#5-websocket)
6. [AudioSink / Buffers PCM](#6-audiosink--buffers-pcm)
7. [Performance du rendu](#7-performance-du-rendu)
8. [Matrice des risques](#8-matrice-des-risques)
9. [Plan d'action](#9-plan-daction)

---

## 1. Résumé exécutif

| Métrique | Valeur |
|----------|--------|
| Findings critiques | **5** |
| Findings importants | **9** |
| Findings optionnels | **6** |
| Score global | **6.5/10** (bon, avec des points chauds ciblés) |

**Verdict** : La GUI EXO est globalement bien architecturée — pas de `StackView` dynamique (utilisation de `StackLayout` statique), pas de `Loader` dynamique pour la navigation, pas de `createComponent()` / `Qt.createQmlObject()`. Les composants sont déclaratifs et statiques. Les risques principaux se concentrent sur :

1. **ListModel sans purge** (transcript, logs, events pipeline) — accumulation continue
2. **Canvas repaint permanent** (PipelinePage + ExoVisualizer) — pression GPU inutile
3. **Animations infinies non stoppées** sur composants invisibles
4. **Tableau JS `recentEvents` qui grossit** sans être lié au cycle de vie
5. **Timers qui tournent sur des pages non visibles**

---

## 2. Cycle de vie QML

### 2.1 Navigation — StackLayout (pas de fuite structurelle)

**Constat** : `MainWindow.qml` utilise `StackLayout` (L218–L249) avec 5 pages statiques (`HomePage`, `SettingsPage`, `HistoryPage`, `LogsPage`, `PipelinePage`). Toutes sont instanciées une seule fois au démarrage.

**Verdict** : ✅ **Aucune fuite liée à la navigation**. Pas de `StackView.push()` / `pop()` qui accumulerait des pages. Pas de `Loader` dynamique.

> ⚠️ **Effet secondaire** : les 5 pages sont vivantes en permanence, même quand elles ne sont pas visibles. Cela a des implications sur les Timers et Canvas (voir §2.3 et §4).

### 2.2 Composants dynamiques

**Constat** : Aucune utilisation de `Qt.createComponent()`, `Qt.createQmlObject()`, ou `Component.createObject()` dans les 26 fichiers QML.

**Verdict** : ✅ **Aucun risque de composants dynamiques non détruits**.

### 2.3 ⚠️ [IMPORTANT] Objets invisibles mais vivants — Timers sur pages non visibles

Les pages non affichées dans le `StackLayout` restent instanciées et leurs Timers continuent de tourner :

| Fichier | Timer | Intervalle | Impact |
|---------|-------|------------|--------|
| `PipelinePage.qml` L38 | `refreshTimer` | 500 ms | Appelle `refreshSnapshot()` en continu **même quand invisible** |
| `PipelinePage.qml` L186 | `edgeCanvas` Timer | 600 ms | Appelle `edgeCanvas.requestPaint()` **même quand invisible** |
| `PipelinePage.qml` inspect | `inspectorLogRefresh` | 1000 ms | Appelle `refreshModuleLogs()` **même quand invisible** |
| `BottomBar.qml` L138 | Horloge | 30000 ms | Minime, acceptable |

**Severité** : 🟠 IMPORTANT
**Impact** : CPU gaspillé, repaints Canvas GPU inutiles toutes les 500-600 ms même quand l'onglet Pipeline n'est pas visible.

**Correctif recommandé** :

```qml
// PipelinePage.qml — conditionner les timers à la visibilité
Timer {
    id: refreshTimer
    interval: 500
    repeat: true
    running: root.visible  // ← AJOUT: ne tourne que si la page est visible
    onTriggered: root.refreshSnapshot()
}

// Idem pour le timer du Canvas
Timer {
    interval: 600
    repeat: true
    running: root.visible  // ← AJOUT
    onTriggered: edgeCanvas.requestPaint()
}
```

### 2.4 ExoSplashScreen — Cycle de vie correct

Le SplashScreen est rendu `visible: false` via `onDismissed` et son Timer interne (`dismissTimer`) est one-shot. ✅ Pas de fuite.

### 2.5 ExoNotification — Cycle de vie non géré

**Constat** (`ExoNotification.qml` L77) : L'animation `showAnim` enchaîne slide-in → pause → fade-out → `ScriptAction { script: root.dismissed() }`. Cependant, le composant n'est jamais détruit après — il émet `dismissed()` mais reste vivant.

**Severité** : 🟡 OPTIONNEL (dépend de l'utilisation côté appelant)
**Correctif** : S'assurer que l'appelant détruise la notification ou la place dans un pool :

```qml
ExoNotification {
    onDismissed: this.destroy()  // ou visible = false + réutilisation
}
```

---

## 3. Fuites mémoire QML

### 3.1 🔴 [CRITIQUE] messageListModel — Croissance infinie

**Fichier** : `ExoTranscriptView.qml` L15–L23

```qml
ListModel { id: messageListModel }

function addMessage(text, isUser, isPartial) {
    messageListModel.append({...})
    messageListView.positionViewAtEnd()
}
```

**Problème** : Le `ListModel` ne dispose d'aucun mécanisme de purge. Chaque message vocal (user + assistant) s'accumule indéfiniment. Sur une session longue (8h), avec ~2 échanges/min = ~960 éléments. Chaque élément contenant 4 rôles (message, isUser, isPartial, timestamp), la mémoire JS croît linéairement.

**Severité** : 🔴 CRITIQUE
**Impact** : Mémoire JS croissante + `ListView` qui pré-crée des delegates au-delà du viewport (cache).

**Correctif** :

```qml
function addMessage(text, isUser, isPartial) {
    messageListModel.append({
        "message": text,
        "isUser": isUser,
        "isPartial": isPartial || false,
        "timestamp": Qt.formatTime(new Date(), "hh:mm")
    })
    // Purger les anciens messages au-delà de 200
    while (messageListModel.count > 200)
        messageListModel.remove(0)
    messageListView.positionViewAtEnd()
}
```

### 3.2 🔴 [CRITIQUE] recentEvents (PipelinePage) — Tableau JS sans borne effective

**Fichier** : `PipelinePage.qml` L70–L75

```qml
function onEventEmitted(event) {
    var arr = root.recentEvents.slice()   // copie complète à chaque événement!
    arr.unshift(event)
    if (arr.length > 200) arr.length = 200
    root.recentEvents = arr
}
```

**Problème double** :
1. **Copie complète** à chaque événement : `slice()` crée un nouveau tableau de N éléments. Avec le pipeline temps réel (événements toutes les ~100 ms), c'est ~10 copies/sec de tableaux de 200 objets.
2. Le cap à 200 est correct **mais** le `ListView` direct sur un array JS (`model: root.recentEvents`) force Qt à recréer tous les delegates à chaque réaffectation de la property.

**Severité** : 🔴 CRITIQUE
**Impact** : GC pressure massive (allocation/désallocation de tableaux), re-création complète des delegates à chaque événement.

**Correctif** :

```qml
// Remplacer le tableau JS par un ListModel
ListModel { id: eventListModel }

// Dans onEventEmitted:
function onEventEmitted(event) {
    eventListModel.insert(0, event)
    if (eventListModel.count > 200)
        eventListModel.remove(200, eventListModel.count - 200)
}

// ListView:
ListView {
    model: eventListModel
    // ...
}
```

### 3.3 🔴 [CRITIQUE] logModel — Purge partielle insuffisante

**Fichier** : `LogsPage.qml` L15–L18

```qml
function appendLog(entry) {
    logModel.append({ text: entry })
    if (logModel.count > 500)
        logModel.remove(0)
}
```

**Analyse** : La purge à 500 est présente ✅, mais elle retire un seul élément à la fois (`remove(0)`). Si les logs arrivent en rafale (ex: burst de 50 logs lors d'un reconnect WebSocket), le modèle peut temporairement dépasser 500. De plus, les logs sont alimentés par `logManager.getRecentLogs()` au `Component.onCompleted` sans limite.

**Severité** : 🟠 IMPORTANT (partiellement mitigé)
**Impact** : Acceptable en fonctionnement normal mais peut déborder en burst.

**Correctif** :

```qml
function appendLog(entry) {
    logModel.append({ text: entry })
    while (logModel.count > 500)
        logModel.remove(0)
}
```

### 3.4 🔴 [CRITIQUE] historyModel — Chargement sans borne

**Fichier** : `HistoryPage.qml` L118–L130

```qml
function loadHistory() {
    historyModel.clear()
    var conversations = memoryManager.getRecentConversations(50)
    for (var i = 0; i < conversations.length; i += 2) {
        historyModel.append({...})
    }
}
```

**Analyse** : Limité à 50 conversations via le backend ✅. Cependant, `loadHistory()` n'est appelé qu'au `Component.onCompleted` — le modèle ne se met pas à jour automatiquement, ce qui n'est pas une fuite mais un bug fonctionnel.

**Severité** : 🟡 OPTIONNEL

### 3.5 🟠 [IMPORTANT] Connections QML — target dynamique non nettoyé

**Fichier** : `MainWindow.qml` L34–L112

```qml
Connections {
    target: typeof voiceManager !== 'undefined' ? voiceManager : null
    // 7 signal handlers
}

Connections {
    target: typeof claudeAPI !== 'undefined' ? claudeAPI : null  
    // 5 signal handlers
}
```

**Analyse** : Les `Connections` sont correctement déclarées avec des targets conditionnels (`typeof ... !== 'undefined'`). Quand `target` est `null`, les handlers ne sont pas connectés. C'est la bonne pratique Qt 6.

**Verdict** : ✅ Pas de fuite. Les connexions vivent avec le composant parent (MainWindow) qui ne meurt jamais.

### 3.6 🟠 [IMPORTANT] Animations infinies actives en permanence

Plusieurs animations `loops: Animation.Infinite` tournent même quand le composant est invisible :

| Composant | Animation | Condition `running` | Problème |
|-----------|-----------|---------------------|----------|
| `ExoPipelineStatus.qml` L41 | Pulse dot opacity | `root.state !== "Idle"` | OK si état change, mais le composant est toujours vivant |
| `ExoResponseView.qml` L65 | Streaming dot pulse | `root.isStreaming` | ✅ Conditionné |
| `ExoResponseView.qml` L106 | Cursor blink | `root.isStreaming` | ✅ Conditionné |
| `ExoStatusIndicator.qml` L43 | Status dot pulse | `Listening \|\| Thinking` | ✅ Conditionné |
| `ExoMicButton.qml` L35-42 | Halo pulse (2 anims) | `Listening` | ✅ Conditionné |
| `ExoMicButton.qml` L94 | Ring sweep | `ring.visible` | ✅ Conditionné |
| `ExoWaveform.qml` L56 | Bars idle anim | `state !== "Idle" && level < 0.05` | ✅ Conditionné |
| `PipelinePage.qml` L210 | Node processing pulse | `getModuleState() === "processing"` | ⚠️ Évaluation complexe dans `running` |
| `ExoSplashScreen.qml` | Service dot pulse | `status !== "ready"` | ✅ Conditionné |
| `ExoProgressBar.qml` | Indeterminate slider | `indeterminate && visible` | ✅ Bien conditionné |

**Severité** : 🟡 OPTIONNEL — La plupart sont bien conditionnées. Seul le node processing pulse évalue une fonction complexe dans `running`.

### 3.7 🟠 [IMPORTANT] Bindings lourds dans PipelinePage — `moduleFilteredEvents()`

**Fichier** : `PipelinePage.qml` L658

```qml
Repeater {
    model: moduleFilteredEvents()
    // ...
}
```

Cette fonction est appelée à chaque changement de `recentEvents` ou `selectedModule`, et le `Repeater` recrée tous ses enfants à chaque appel. Couplé au problème §3.2, cela provoque des re-créations massives de composants.

**Severité** : 🟠 IMPORTANT

---

## 4. Textures GPU / Canvas / ShaderEffect

### 4.1 ✅ Pas de ShaderEffect

**Constat** : Contrairement au README qui mentionne "Visualizer GPU ShaderEffect GLSL 60 FPS", le code actuel utilise `Canvas` (`ExoVisualizer.qml`) et non `ShaderEffect`. Pas de texture GPU allouée côté QML.

**Verdict** : ✅ Aucune fuite de texture GPU possible via ShaderEffect.

### 4.2 🔴 [CRITIQUE] Canvas ExoVisualizer — Repaint 30 FPS permanent

**Fichier** : `ExoVisualizer.qml` L69–L76

```qml
Timer {
    interval: 33          // ~30 FPS
    running: root.active
    repeat: true
    onTriggered: {
        root.iTime += interval / 1000.0
        waveCanvas.requestPaint()
    }
}
```

**Analyse** : Le timer est conditionné par `root.active` (lié à `audioLevel > 0.01`). Quand l'audio est actif (listening ou speaking), le Canvas repaint 30x/sec. Le Canvas utilise `renderStrategy: Canvas.Cooperative`, ce qui est correct (partage du thread de rendu).

**Points d'attention** :
- Le Canvas crée un nouveau contexte 2D à chaque `onPaint` via `getContext("2d")` — en Qt 6, c'est optimisé (cache du contexte), mais chaque paint alloue des paths sur le GPU scene graph.
- Le `clearRect` + repaint complet est le pattern standard.
- **Le Visualizer est dans la `BottomBar`**, donc visible en permanence. Quand l'audio est actif, 30 repaints/sec sur la BottomBar.

**Severité** : 🟠 IMPORTANT (impact GPU modéré, mais continu pendant toute la durée d'écoute/parole)

**Correctif optionnel** : Réduire à 20 FPS pour une animation aussi simple :

```qml
Timer {
    interval: 50   // 20 FPS — suffisant pour une onde sinusoïdale
    running: root.active && root.visible
    // ...
}
```

### 4.3 🟠 [IMPORTANT] Canvas PipelinePage — Double repaint permanent

**Fichier** : `PipelinePage.qml`

Le `edgeCanvas` est repaint par :
1. Un Timer à 600 ms (L186)
2. Le signal `onModuleStatesChanged` (L183)
3. Le timer `refreshTimer` à 500 ms qui modifie `moduleStates`, ce qui déclenche (2)

Résultat : **Le Canvas est repaint ~3.5x/sec même quand la page Pipeline n'est pas visible**.

**Severité** : 🟠 IMPORTANT

**Correctif** : voir §2.3 — conditionner les timers à `root.visible`.

### 4.4 ✅ Images / Icônes

Les icônes SVG dans la Sidebar (`icons/chat.svg`, etc.) sont chargées via `Image { source: ... }` avec `sourceSize` défini. Qt cache les textures SVG rasterisées. Aucune fuite détectée.

### 4.5 `layer.enabled: true` — Coût GPU

Deux composants utilisent `layer.enabled: true` :

| Composant | Fichier | Impact |
|-----------|---------|--------|
| ExoMicButton halo | `ExoMicButton.qml` L33 | Crée un FBO (Framebuffer Object) GPU permanent |
| ExoWaveform bars | `ExoWaveform.qml` L37 | Crée un FBO GPU permanent |

**Severité** : 🟡 OPTIONNEL — 2 FBOs supplémentaires est acceptable. Le halo du MicButton pourrait être simplifié sans `layer.enabled`.

---

## 5. WebSocket

### 5.1 ✅ WebSocketClient C++ — Bien géré

**Fichiers** : `WebSocketClient.h/cpp`

- Reconnexion avec backoff exponentiel ✅
- `destroySocket()` déconnecte tous les signaux avant `deleteLater()` ✅
- `m_closing` flag empêche les reconnexions après `close()` ✅
- Socket recréé proprement lors de la reconnexion (v5.1 fix) ✅

**Vertex** : ✅ Aucune fuite WebSocket détectée côté C++.

### 5.2 ✅ TTSManager WebSocket — Pas de fuite

Le `m_ws` dans TTSManager est un pointeur nu non owné (set par `setWebSocket()`). Les broadcasts vérifient `m_ws->state()` avant envoi. ✅

### 5.3 🟠 [IMPORTANT] Connections QML vers C++ — Pas de gestion de déconnexion

**Fichier** : `MainWindow.qml`

Les `Connections` vers `voiceManager`, `claudeAPI`, `assistantManager`, `pipelineEventBus` ne gèrent pas le cas où le context property C++ serait détruit puis recréé (hot-reload, restart de service). Si un C++ object est détruit, le `target` QML reste un pointeur mort.

**Severité** : 🟠 IMPORTANT (uniquement si les objets C++ peuvent être recréés à runtime)

**Analyse du risque** : Les context properties sont typiquement définis une fois au démarrage et ne changent pas. Risque faible en pratique.

---

## 6. AudioSink / Buffers PCM

### 6.1 ✅ Sink persistant — Conception correcte

**Fichier** : `TTSManager.cpp`

Le `QAudioSink` est créé une seule fois via `ensureSinkReady()` et persiste entre les phrases TTS :

```cpp
void TTSManager::ensureSinkReady()
{
    if (m_sink) return;  // ← Singleton persistant
    // ...
    m_sink = std::make_unique<QAudioSink>(dev, m_sinkFormat);
}
```

**Verdict** : ✅ Le sink n'est PAS recréé à chaque phrase. `unique_ptr` garantit le cleanup.

### 6.2 ✅ PCMRingBuffer — Pas de fuite

Le `PCMRingBuffer` est à capacité fixe (480000 bytes ≈ 10s). Les overflow sont loggés (`ringbuffer_write OVERFLOW`). Le buffer est `clear()` lors de `cancelSpeech()` et `destroySink()`.

**Verdict** : ✅ Aucune fuite possible — capacité fixe pré-allouée.

### 6.3 🟠 [IMPORTANT] Pump timer jamais nettoyé

**Fichier** : `TTSManager.cpp` L870

```cpp
if (!m_pumpTimer) {
    m_pumpTimer = new QTimer(this);
    m_pumpTimer->setInterval(10);
    connect(m_pumpTimer, &QTimer::timeout, this, &TTSManager::pumpBuffer);
}
```

Le `m_pumpTimer` est un `QTimer *` alloué avec `new` et parented à `this`. Il sera détruit avec TTSManager. Cependant, il est démarré/stoppé manuellement et pourrait tourner à 100 Hz sans données à pomper si le ring buffer est vide et `m_synthesizing` est true.

**Severité** : 🟠 IMPORTANT (CPU gaspillé, 100 appels/sec de `pumpBuffer()` qui retournent immédiatement)

**Correctif** : Dans `pumpBuffer()`, stopper le timer s'il n'y a rien à pomper et si on n'est pas en synthèse :

```cpp
void TTSManager::pumpBuffer()
{
    if (!m_sinkIO || !m_sink) return;
    const qint64 canWrite = m_sink->bytesFree();
    if (canWrite <= 0) return;

    if (!m_ringBuffer.isEmpty()) {
        // Feed audio...
        return;
    }

    if (!m_synthesizing) {
        // Rien à pomper, pas de synthèse en cours
        // Le timer sera relancé par le prochain onWorkerChunk
        m_pumpTimer->stop();  // ← AJOUT
    }
}
```

### 6.4 ✅ DSP — Pas de fuite

Le `TTSDSPProcessor` réutilise un `std::vector<float> m_fbuf` (grow-only, jamais shrink). Acceptable — allocation one-shot.

---

## 7. Performance du rendu

### 7.1 🟠 [IMPORTANT] Bindings JavaScript dans les delegates ListView

**ExoTranscriptView.qml** — Le delegate de la `messageListView` contient des bindings JS complexes :

```qml
delegate: Rectangle {
    color: index % 2 === 0 ? Theme.bgPrimary : "#1F1F1F"  // re-évalué au scroll
    // ...
    Rectangle { color: model.isUser ? Theme.accent : Theme.success }
}
```

Ces bindings sont évalués pour chaque delegate visible. Avec 200 messages et du scrolling, cela génère de la charge. Le même pattern est utilisé dans `LogsPage.qml` (L224) avec une condition encore plus lourde :

```qml
color: {
    if (model.text.indexOf("WARN") !== -1) return Theme.warning
    if (model.text.indexOf("CRIT") !== -1 || ...) return Theme.error
    // 7 conditions indexOf
}
```

**Severité** : 🟠 IMPORTANT
**Correctif** : Pré-calculer le niveau de log côté C++ ou dans le `ListModel` lors de l'insertion :

```qml
function appendLog(entry) {
    var level = "info"
    if (entry.indexOf("WARN") !== -1) level = "warning"
    else if (entry.indexOf("CRIT") !== -1) level = "error"
    // ...
    logModel.append({ text: entry, level: level })
}
```

### 7.2 🟠 [IMPORTANT] `typeof` checks dans les bindings

De nombreux bindings évaluent `typeof xxx !== 'undefined'` :

```qml
// MainWindow.qml L22
property bool servicesReady: typeof serviceSupervisor !== 'undefined'
                             ? serviceSupervisor.allReady : true
```

```qml
// BottomBar.qml L100
color: {
    if (typeof serviceSupervisor === 'undefined') return Theme.textMuted
    var s = serviceSupervisor.serviceState(modelData.key)
    return Theme.healthColor(s)
}
```

Ces `typeof` checks sont évalués à chaque réévaluation du binding. En pratique, le coût est minime car `typeof` est O(1) en V4.

**Severité** : 🟡 OPTIONNEL — pattern défensif acceptable.

### 7.3 🟠 [IMPORTANT] PipelinePage — Re-render massif de l'EventList

Comme décrit en §3.2, la réaffectation de `root.recentEvents` (un `var` array) force `ListView` à recréer tous ses delegates via le model binding. Avec 200 events qui changent ~10x/sec quand le pipeline est actif, cela représente ~2000 delegate creations/sec.

**Severité** : 🔴 CRITIQUE (combinaison de §3.2 + §4.3)
**Correctif** : voir §3.2 — utiliser un `ListModel` au lieu d'un array JS.

### 7.4 ✅ Pas de JSON parsing dans le thread UI QML

Les JSON sont parsés côté C++ (`QJsonDocument`), pas dans le JS QML. ✅

### 7.5 🟡 [OPTIONNEL] SettingsPage — ComboBox ListModel inline

Les `ComboBox` dans `SettingsPage.qml` utilisent des `ListModel { ListElement { ... } }` inline. C'est le pattern standard Qt, mais ces modèles sont toujours en mémoire (5 pages vivantes). Impact négligeable.

### 7.6 🟡 [OPTIONNEL] `inspectorPanel.refreshModuleLogs()` — Copie complète

**Fichier** : `PipelinePage.qml` L470–L480

```qml
function refreshModuleLogs() {
    var logs = logManager.getLogsByFilter(filter)
    var arr = []
    for (var i = 0; i < logs.length; i++) arr.push(logs[i])
    moduleLogs = arr
}
```

Ce pattern copie l'intégralité des logs filtrés toutes les 1000 ms. La boucle `for` + `push` est O(n) en JS. Avec un service actif générant beaucoup de logs, c'est coûteux.

**Severité** : 🟡 OPTIONNEL (seulement quand un module est sélectionné + page Pipeline visible)

---

## 8. Matrice des risques

| ID | Finding | Sévérité | Composant | Effort fix |
|----|---------|----------|-----------|------------|
| M1 | `messageListModel` croissance infinie | 🔴 CRITIQUE | ExoTranscriptView | 5 min |
| M2 | `recentEvents` copie array + delegate recreation | 🔴 CRITIQUE | PipelinePage | 30 min |
| M3 | Event timeline re-render massif (conséquence M2) | 🔴 CRITIQUE | PipelinePage | inclus M2 |
| M4 | Canvas + Timers actifs sur pages invisibles | 🔴 CRITIQUE | PipelinePage | 10 min |
| M5 | ExoVisualizer Canvas repaint sans check `visible` | 🟠 IMPORTANT | ExoVisualizer | 2 min |
| T1 | Timers PipelinePage tournent en continu | 🟠 IMPORTANT | PipelinePage | 5 min |
| T2 | Pump timer 100 Hz sans données | 🟠 IMPORTANT | TTSManager.cpp | 5 min |
| T3 | `logModel.remove(0)` un seul à la fois | 🟠 IMPORTANT | LogsPage | 2 min |
| T4 | Bindings indexOf dans delegate logs | 🟠 IMPORTANT | LogsPage | 15 min |
| T5 | moduleFilteredEvents() recrée le Repeater | 🟠 IMPORTANT | PipelinePage | inclus M2 |
| T6 | `layer.enabled` sur halo MicButton | 🟡 OPTIONNEL | ExoMicButton | 5 min |
| T7 | ExoNotification non détruit après dismiss | 🟡 OPTIONNEL | ExoNotification | 2 min |
| T8 | `typeof` checks dans bindings | 🟡 OPTIONNEL | MainWindow | N/A |
| T9 | inspectorPanel.refreshModuleLogs copie | 🟡 OPTIONNEL | PipelinePage | 10 min |
| T10 | historyModel pas de refresh auto | 🟡 OPTIONNEL | HistoryPage | 10 min |
| T11 | Réduire Canvas Visualizer à 20 FPS | 🟡 OPTIONNEL | ExoVisualizer | 1 min |

---

## 9. Plan d'action

### Phase 1 — Immédiat (critiques, < 1h)

#### 1.1 Purger `messageListModel` (M1)

**Fichier** : `qml/components/ExoTranscriptView.qml`

```qml
function addMessage(text, isUser, isPartial) {
    messageListModel.append({
        "message": text,
        "isUser": isUser,
        "isPartial": isPartial || false,
        "timestamp": Qt.formatTime(new Date(), "hh:mm")
    })
    // Purge: garder les 200 derniers messages
    while (messageListModel.count > 200)
        messageListModel.remove(0)
    messageListView.positionViewAtEnd()
}
```

#### 1.2 Migrer `recentEvents` vers ListModel (M2 + M3 + T5)

**Fichier** : `qml/pages/PipelinePage.qml`

Remplacer :
```qml
property var recentEvents: []
```

Par :
```qml
ListModel { id: eventListModel }
```

Et modifier `onEventEmitted` :
```qml
function onEventEmitted(event) {
    eventListModel.insert(0, {
        "timestamp": event.timestamp || "",
        "module": event.module || "",
        "event_type": event.event_type || "",
        "elapsed_ms": event.elapsed_ms || 0
    })
    while (eventListModel.count > 200)
        eventListModel.remove(eventListModel.count - 1)
}
```

Et le `ListView` :
```qml
ListView {
    model: eventListModel
    // delegate accède via model.timestamp, model.module, etc.
}
```

#### 1.3 Conditionner tous les timers à `visible` (M4 + T1)

**Fichier** : `qml/pages/PipelinePage.qml`

```qml
Timer {
    id: refreshTimer
    interval: 500
    repeat: true
    running: root.visible   // ← AJOUT
}

// Timer du Canvas edges:
Timer {
    interval: 600
    repeat: true
    running: root.visible   // ← AJOUT
}

// Inspector log refresh:
Timer {
    id: inspectorLogRefresh
    interval: 1000
    repeat: true
    running: root.visible && !!root.selectedModule  // ← AJOUT root.visible
}
```

#### 1.4 ExoVisualizer — Ajouter check `visible` (M5)

**Fichier** : `qml/components/ExoVisualizer.qml`

```qml
Timer {
    interval: 33
    running: root.active && root.visible   // ← AJOUT visible
    repeat: true
}
```

### Phase 2 — Court terme (importants, < 2h)

#### 2.1 Fix logModel purge (T3)

```qml
function appendLog(entry) {
    logModel.append({ text: entry })
    while (logModel.count > 500)
        logModel.remove(0)
}
```

#### 2.2 Pré-calculer le niveau de log (T4)

```qml
function appendLog(entry) {
    var lvl = "info"
    if (entry.indexOf("CRIT") !== -1 || entry.indexOf("FATAL") !== -1) lvl = "error"
    else if (entry.indexOf("WARN") !== -1) lvl = "warning"
    else if (entry.indexOf("[VOICE]") !== -1 || entry.indexOf("[TTS]") !== -1
             || entry.indexOf("[STT]") !== -1) lvl = "voice"
    else if (entry.indexOf("[CLAUDE]") !== -1) lvl = "thinking"
    else if (entry.indexOf("[WEATHER]") !== -1) lvl = "weather"

    logModel.append({ text: entry, level: lvl })
    while (logModel.count > 500)
        logModel.remove(0)
    if (autoScroll) logList.positionViewAtEnd()
}

// Dans le delegate:
color: {
    switch (model.level) {
    case "error":    return Theme.error
    case "warning":  return Theme.warning
    case "voice":    return Theme.info
    case "thinking": return Theme.stateThinking
    case "weather":  return "#CE9178"
    default:         return Theme.textSecondary
    }
}
```

#### 2.3 Pump timer stop quand idle (T2)

**Fichier** : `app/audio/TTSManager.cpp`, dans `pumpBuffer()` :

```cpp
// Après le check "ring buffer empty + not synthesizing":
if (!m_synthesizing && !hasMore) {
    m_pumpTimer->stop();
}
```

### Phase 3 — Optionnel (< 1h)

- T6 : Retirer `layer.enabled: true` du halo MicButton pour économiser un FBO GPU
- T7 : Ajouter `onDismissed: destroy()` dans l'appelant de ExoNotification
- T9 : Limiter `refreshModuleLogs()` à N lignes côté C++ (`getLogsByFilter(filter, 50)`)
- T11 : Réduire le Timer ExoVisualizer de 33ms à 50ms (20 FPS)

---

## Annexe — Points positifs

| Aspect | Verdict |
|--------|---------|
| Navigation StackLayout (pas de StackView dynamique) | ✅ Excellent |
| Pas de composants créés dynamiquement | ✅ Excellent |
| Pas de ShaderEffect (Canvas simple) | ✅ Bon choix |
| WebSocketClient C++ avec reconnexion propre | ✅ Excellent |
| QAudioSink persistant (pas recréé) | ✅ Excellent |
| PCMRingBuffer à capacité fixe | ✅ Excellent |
| DSP buffer réutilisé (grow-only) | ✅ Bon |
| Theme singleton centralisé | ✅ Excellent |
| Animations conditionnées à l'état | ✅ Bon |
| Pas de JSON parsing en JS QML | ✅ Excellent |

---

**Fin de l'audit** — 1er avril 2026
