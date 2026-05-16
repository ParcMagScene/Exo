import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "pages"
import "panels"
import "components"
import "navigation"
import "theme"
import "core"
import RaspberryAssistant  // FloorPlanModel QML_ELEMENT

ApplicationWindow {
    id: mainWindow
    visible: true
    width: 1280
    height: 800
    minimumWidth: 900
    minimumHeight: 600
    title: "EXO Assistant"
    color: Theme.bgPrimary

    // ── Icône d'application unifiée ──
    readonly property string appIcon: "qrc:/qt/qml/RaspberryAssistant/assets/icons/app/exo.svg"

    // ── Floor Plan Model (QML_ELEMENT) ──
    FloorPlanModel { id: floorPlanModel }

    // ── État global ──
    property string appStatus: "Idle"
    property real micLevel: 0.0
    property string partialTranscript: ""
    property string currentResponse: ""
    property bool isStreaming: false
     property bool startupFallbackVisible: false
     property bool startupFallbackLogged: false
    property bool startupSplashBypassed: false
    property bool servicesReady: typeof serviceSupervisor !== 'undefined'
                                 ? (serviceSupervisor.allReady
                                    || (typeof safeBootController !== 'undefined' && safeBootController.safeBootEnabled))
                                 : true

    // ── Safe Boot — état décisionnel ──
    readonly property bool _safeBootActive: typeof assistantManager !== 'undefined'
                                             ? assistantManager.safeBootEnabled : false
    readonly property bool _safeBootDecisionMade: typeof assistantManager !== 'undefined'
                                                    ? assistantManager.safeBootDecisionMade : false

    // ══════════════════════════════════════════════
    //  Connexions aux context properties C++
    // ══════════════════════════════════════════════

    Connections {
        target: typeof voiceManager !== 'undefined' ? voiceManager : null

        function onListeningChanged() {
            if (voiceManager.isListening) {
                mainWindow.appStatus = "Listening"
            } else if (mainWindow.appStatus === "Listening") {
                mainWindow.appStatus = "Idle"
            }
        }

        function onSpeakingChanged() {
            if (voiceManager.isSpeaking) {
                mainWindow.appStatus = "Speaking"
            } else if (mainWindow.appStatus === "Speaking") {
                mainWindow.appStatus = "Idle"
            }
        }

        function onSpeechTranscribed(transcription) {
            mainWindow.appStatus = "Transcribing"
            mainWindow.partialTranscript = ""
            homePage.transcriptView.addMessage(transcription, true, false)
        }

        function onCommandDetected(command) {
            mainWindow.partialTranscript = command
        }

        function onWakeWordDetected() {
            mainWindow.appStatus = "Listening"
        }

        function onAudioLevel(rms, vadScore) {
            mainWindow.micLevel = rms
        }

        function onMicPcmForVisualization(samples) {
            micWaveform.updateSamples(samples)
        }

        function onTtsPcmForVisualization(samples) {
            ttsWaveform.updateSamples(samples)
        }

        function onPartialTranscript(text) {
            mainWindow.partialTranscript = text
        }

        function onStateChanged(newState) {
            var states = ["Idle", "DetectingSpeech", "Listening", "Transcribing", "Thinking", "Speaking"]
            if (newState >= 0 && newState < states.length)
                mainWindow.appStatus = states[newState]
        }
    }

    Connections {
        target: typeof claudeAPI !== 'undefined' ? claudeAPI : null

        function onRequestStarted() {
            mainWindow.appStatus = "Thinking"
            mainWindow.isStreaming = true
            mainWindow.currentResponse = ""
        }

        function onErrorOccurred(error) {
            mainWindow.currentResponse = "Erreur: " + error
            mainWindow.isStreaming = false
            mainWindow.appStatus = "Idle"
        }
    }

    Connections {
        target: typeof assistantManager !== 'undefined' ? assistantManager : null

        function onErrorOccurred(error) {
            mainWindow.currentResponse = "Erreur: " + error
            mainWindow.appStatus = "Idle"
        }

        function onNetworkScanCompleted(result) {
            homePage.reseauPanel.scanning = false
            if (result.status === "success") {
                var nodes = result.devices || result.nodes || []
                var topo = result.topology || {}
                var links = topo.links || result.links || result.edges || []
                homePage.reseauPanel.nodes = nodes
                homePage.reseauPanel.links = links
            }
        }

        function onHomeGraphReceived(result) {
            if (result.status === "success") {
                homePage.maisonPanel.devices = result.devices || []
                homePage.maisonPanel.rooms = result.rooms || []
                homePage.maisonPanel.scenarios = result.scenarios || []
            }
        }

        function onDeviceCommandResult(result) {
            // Refresh home graph after a device command
            if (result.status === "success" && typeof assistantManager !== 'undefined')
                assistantManager.requestHomeGraph()
        }

        function onScenarioResult(result) {
            // Refresh after scenario execution
            if (typeof assistantManager !== 'undefined')
                assistantManager.requestHomeGraph()
        }

        // Important: couvre les réponses émises par AssistantManager (welcome + fast-path)
        // qui ne passent pas forcément par claudeAPI.
        function onClaudePartialResponse(partialText) {
            mainWindow.currentResponse = partialText
            mainWindow.isStreaming = true
            mainWindow.appStatus = "Thinking"
        }

        function onClaudeResponseReceived(response) {
            if (!response || response.length === 0)
                return

            // Anti-duplication: en mode normal, claudeAPI peut déjà avoir alimenté l'UI.
            if (!mainWindow.isStreaming && mainWindow.currentResponse === response)
                return

            mainWindow.currentResponse = response
            mainWindow.isStreaming = false
            mainWindow.appStatus = "Idle"
            homePage.transcriptView.addMessage(response, false, false)
        }
    }

    // ══════════════════════════════════════════════
    //  Layout principal — masqué en Safe Boot
    // ══════════════════════════════════════════════

    RowLayout {
        id: mainLayout
        anchors.fill: parent
        spacing: 0
        visible: !mainWindow._safeBootActive

        // ── Sidebar gauche ──
        Sidebar {
            id: sidebar
            Layout.fillHeight: true
            currentStatus: mainWindow.appStatus
            micLevel: mainWindow.micLevel

            onPanelSelected: function(panelName) {
                // Bloquer la navigation en Safe Boot
                if (mainWindow._safeBootActive) return

                // Logique adaptée MODE NORMAL vs EXPERT
                var isExpert = typeof UIState !== 'undefined' ? UIState.expertMode : false
                var index = -1

                switch (panelName) {
                // ── Pages communes ───────────────────────────────────────
                case "chat":
                case "home":
                    index = 0
                    homePage.showSection("home")
                    break
                case "settings":
                    index = 1
                    break
                case "history":
                    index = 2
                    break
                case "maison":
                    index = 0
                    homePage.showSection("maison")
                    break
                case "reseau":
                    index = 0
                    homePage.showSection("reseau")
                    break
                case "floorplan":
                    index = 0
                    homePage.showSection("floorplan")
                    break

                // ── Panneaux directs (composants standalone) ─────────────
                case "pipelineLogs":
                    index = 3   // PipelinePage
                    break
                case "cognitiveTimeline":
                    index = 4   // CognitiveTimeline
                    break
                case "heatmap":
                    index = 5   // EngineHeatmap
                    break
                case "voicePipeline":
                case "pipelineTimeline":
                    index = isExpert ? 12 : 6   // PipelinePageExpert / VoicePipelineView
                    break
                case "memory":
                    index = isExpert ? 7 : -1   // MemoryInspector
                    break
                case "governance":
                    index = isExpert ? 8 : -1   // GovernancePanel
                    break

                // ── Logs / Observabilité ─────────────────────────────────
                case "logs":
                case "debug":
                case "observability":
                    index = isExpert ? 11 : 9   // ObservabilityPage / ObservabilityDashboard
                    break
                case "logsFull":
                    index = 18                   // LogsPage (full runtime log viewer)
                    break
                // ── Pages EXPERT uniquement ──────────────────────────────
                case "vision":
                    index = isExpert ? 13 : -1  // VisionPageExpert
                    break

                // ── Pages accessibles dans les deux modes ────────────────
                case "simulation":
                case "simScenarios":
                case "simTimeline":
                case "simComparison":
                    index = 14  // SimulationPageExpert
                    break
                case "spatialCognition":
                case "raisonnement":
                case "explications":
                case "predictions":
                    index = 15  // SpatialCognitionPageExpert
                    break
                case "security":
                case "intrusion":
                case "fire":
                case "electrical":
                case "networkRisk":
                case "domoticAnomaly":
                case "causality":
                case "recommendations":
                    index = 16  // SecurityPageExpert
                    break
                case "development":
                case "safeboot":
                case "services":
                case "stability":
                case "agents":
                    index = 17  // DevelopmentPageExpert
                    break

                default:
                    console.warn("[MainWindow] panelName unknown:", panelName)
                    return
                }

                // Vérifier si index valide
                if (index < 0) {
                    console.warn("[MainWindow] Page non accessible en mode:", isExpert ? "EXPERT" : "NORMAL", "- panelName:", panelName)
                    return
                }

                centralStack.currentIndex = index
                console.log("[MainWindow] Navigation:", panelName, "→ index", index, "(mode:", isExpert ? "EXPERT" : "NORMAL", ")")

                // Appels backend si nécessaire
                if (panelName === "maison") {
                    if (typeof assistantManager !== 'undefined')
                        assistantManager.requestHomeGraph()
                }
            }
        }

        // ── Zone centrale ──
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // ── Bannière erreur micro ──
            Rectangle {
                id: micErrorBanner
                Layout.fillWidth: true
                height: visible ? 36 : 0
                visible: typeof audioDeviceManager !== 'undefined'
                         && !audioDeviceManager.hasValidInputDevice
                color: "#4B1E1E"
                border.color: Theme.error
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacing12
                    anchors.rightMargin: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: "⚠ Mode vocal indisponible — passage en mode clavier"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontCaption
                        color: Theme.error
                        Layout.fillWidth: true
                    }

                    Text {
                        text: "Ouvrir paramètres ›"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontMicro
                        color: Theme.info

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                sidebar.activePanel = "settings"
                                centralStack.currentIndex = 1
                            }
                        }
                    }
                }

                Behavior on height { NumberAnimation { duration: 200 } }
            }

            StackLayout {
                id: centralStack
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: 0

                // Index 0 : Chat (Transcript + Response)
                HomePage {
                    id: homePage
                    partialTranscript: mainWindow.partialTranscript
                    currentResponse: mainWindow.currentResponse
                    isStreaming: mainWindow.isStreaming
                    floorModel: floorPlanModel

                    onDeviceCommand: function(deviceId, command, params) {
                        if (typeof assistantManager !== 'undefined')
                            assistantManager.requestDeviceCommand(deviceId, command, params || {})
                    }
                    onHomeRefreshRequested: {
                        if (typeof assistantManager !== 'undefined')
                            assistantManager.requestHomeGraph()
                    }
                    onScenarioRequested: function(name) {
                        if (typeof assistantManager !== 'undefined')
                            assistantManager.requestRunScenario(name)
                    }
                    onNetworkScanRequested: {
                        if (typeof assistantManager !== 'undefined') {
                            homePage.reseauPanel.scanning = true
                            assistantManager.requestNetworkScan(false)
                        }
                    }
                    onNetworkScanFastRequested: {
                        if (typeof assistantManager !== 'undefined') {
                            homePage.reseauPanel.scanning = true
                            assistantManager.requestNetworkScan(true)
                        }
                    }
                }

                // Index 1 : Settings
                SettingsPage {
                    id: settingsPage
                }

                // Index 2 : History
                HistoryPage {
                    id: historyPage
                }

                // Index 3 : Pipeline Monitor
                PipelinePage {
                    id: pipelinePage
                }

                // Index 4 : Cognitive Timeline
                CognitiveTimeline {}

                // Index 5 : Engine Heatmap
                EngineHeatmap {}

                // Index 6 : Voice Pipeline Flow
                VoicePipelineView {}

                // Index 7 : Memory Inspector
                MemoryInspector {}

                // Index 8 : Gouvernance
                GovernancePanel {}

                // Index 9 : Observability Dashboard
                ObservabilityDashboard {}

                // Index 10 : Floor Plan Editor
                FloorPlanPage {
                    id: floorPlanPage
                    floorModel: floorPlanModel
                }

                // ══════════════════════════════════════════
                //  Pages EXPERT — EXO v2.0  (indices 11-17)
                //  PERF OPT-A : Loader asynchrone — chaque page n'est instanciée
                //  qu'à la première navigation (active reste true après, pas de
                //  destruction). Gain démarrage : ~400-800 ms CPU + mémoire QML.
                // ══════════════════════════════════════════

                // Index 11 : ObservabilityPage
                Loader {
                    id: loader11
                    active: false
                    asynchronous: true
                    sourceComponent: Component { ObservabilityPage {} }
                    onStatusChanged: if (status === Loader.Error) console.error("[QML] Loader ObservabilityPage failed:", sourceComponent ? sourceComponent.errorString() : "unknown")
                    Connections {
                        target: centralStack
                        function onCurrentIndexChanged() { if (centralStack.currentIndex === 11) loader11.active = true }
                    }
                }

                // Index 12 : PipelinePageExpert
                Loader {
                    id: loader12
                    active: false
                    asynchronous: true
                    sourceComponent: Component { PipelinePageExpert {} }
                    onStatusChanged: if (status === Loader.Error) console.error("[QML] Loader PipelinePageExpert failed:", sourceComponent ? sourceComponent.errorString() : "unknown")
                    Connections {
                        target: centralStack
                        function onCurrentIndexChanged() { if (centralStack.currentIndex === 12) loader12.active = true }
                    }
                }

                // Index 13 : VisionPageExpert
                Loader {
                    id: loader13
                    active: false
                    asynchronous: true
                    sourceComponent: Component { VisionPageExpert {} }
                    onStatusChanged: if (status === Loader.Error) console.error("[QML] Loader VisionPageExpert failed:", sourceComponent ? sourceComponent.errorString() : "unknown")
                    Connections {
                        target: centralStack
                        function onCurrentIndexChanged() { if (centralStack.currentIndex === 13) loader13.active = true }
                    }
                }

                // Index 14 : SimulationPageExpert
                Loader {
                    id: loader14
                    active: false
                    asynchronous: true
                    sourceComponent: Component { SimulationPageExpert {} }
                    onStatusChanged: if (status === Loader.Error) console.error("[QML] Loader SimulationPageExpert failed:", sourceComponent ? sourceComponent.errorString() : "unknown")
                    Connections {
                        target: centralStack
                        function onCurrentIndexChanged() { if (centralStack.currentIndex === 14) loader14.active = true }
                    }
                }

                // Index 15 : SpatialCognitionPageExpert
                Loader {
                    id: loader15
                    active: false
                    asynchronous: true
                    sourceComponent: Component { SpatialCognitionPageExpert {} }
                    onStatusChanged: if (status === Loader.Error) console.error("[QML] Loader SpatialCognitionPageExpert failed:", sourceComponent ? sourceComponent.errorString() : "unknown")
                    Connections {
                        target: centralStack
                        function onCurrentIndexChanged() { if (centralStack.currentIndex === 15) loader15.active = true }
                    }
                }

                // Index 16 : SecurityPageExpert
                Loader {
                    id: loader16
                    active: false
                    asynchronous: true
                    sourceComponent: Component { SecurityPageExpert {} }
                    onStatusChanged: if (status === Loader.Error) console.error("[QML] Loader SecurityPageExpert failed:", sourceComponent ? sourceComponent.errorString() : "unknown")
                    Connections {
                        target: centralStack
                        function onCurrentIndexChanged() { if (centralStack.currentIndex === 16) loader16.active = true }
                    }
                }

                // Index 17 : DevelopmentPageExpert
                Loader {
                    id: loader17
                    active: false
                    asynchronous: true
                    sourceComponent: Component { DevelopmentPageExpert {} }
                    onStatusChanged: if (status === Loader.Error) console.error("[QML] Loader DevelopmentPageExpert failed:", sourceComponent ? sourceComponent.errorString() : "unknown")
                    Connections {
                        target: centralStack
                        function onCurrentIndexChanged() { if (centralStack.currentIndex === 17) loader17.active = true }
                    }
                }

                // Index 18 : LogsPage — visualiseur runtime complet (tri/filtre/copie)
                Loader {
                    id: loader18
                    active: false
                    asynchronous: true
                    sourceComponent: Component { LogsPage {} }
                    onStatusChanged: if (status === Loader.Error) console.error("[QML] Loader LogsPage failed:", sourceComponent ? sourceComponent.errorString() : "unknown")
                    Connections {
                        target: centralStack
                        function onCurrentIndexChanged() { if (centralStack.currentIndex === 18) loader18.active = true }
                    }
                }
            }

            // ── Fallback clavier (quand pas de micro) ──
            Rectangle {
                id: keyboardFallback
                Layout.fillWidth: true
                height: visible ? 44 : 0
                visible: typeof audioDeviceManager !== 'undefined'
                         && !audioDeviceManager.hasValidInputDevice
                color: Theme.bgSecondary

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacing12
                    anchors.rightMargin: Theme.spacing12
                    spacing: Theme.spacing8

                    Rectangle {
                        Layout.fillWidth: true
                        height: 30
                        radius: Theme.radiusSmall
                        color: Theme.bgPrimary
                        border.color: keyboardInput.activeFocus ? Theme.borderFocus : Theme.border

                        TextInput {
                            id: keyboardInput
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            verticalAlignment: TextInput.AlignVCenter
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSmall
                            color: "#D4D4D4"
                            clip: true

                            Text {
                                anchors.fill: parent
                                verticalAlignment: Text.AlignVCenter
                                text: "Tapez votre message ici…"
                                font.family: parent.font.family
                                font.pixelSize: parent.font.pixelSize
                                color: Theme.textMuted
                                visible: !keyboardInput.text && !keyboardInput.activeFocus
                            }

                            Keys.onReturnPressed: {
                                if (text.trim().length > 0) {
                                    if (typeof assistantManager !== 'undefined')
                                        assistantManager.sendMessage(text.trim())
                                    homePage.transcriptView.addMessage(text.trim(), true, false)
                                    text = ""
                                }
                            }
                        }
                    }

                    Button {
                        text: "Envoyer"
                        Layout.preferredWidth: 80
                        Layout.preferredHeight: 30

                        onClicked: {
                            if (keyboardInput.text.trim().length > 0) {
                                if (typeof assistantManager !== 'undefined')
                                    assistantManager.sendMessage(keyboardInput.text.trim())
                                homePage.transcriptView.addMessage(keyboardInput.text.trim(), true, false)
                                keyboardInput.text = ""
                            }
                        }

                        background: Rectangle {
                            color: parent.hovered ? Theme.accentHover : Theme.accent
                            radius: Theme.radiusSmall
                        }
                        contentItem: Text {
                            text: parent.text
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontCaption
                            color: "#FFFFFF"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }

                Behavior on height { NumberAnimation { duration: 200 } }
            }

            // ── Waveform Visualizers ──
            AudioWaveformView {
                id: micWaveform
                Layout.fillWidth: true
                Layout.preferredHeight: 64
                waveColor: "#00FF88"
                amplitude: 0.45
                thickness: 2.0
                glowAmount: 0.018
                active: mainWindow.appStatus === "Listening"
                        || mainWindow.appStatus === "DetectingSpeech"
                visible: mainWindow.appStatus === "Listening"
                         || mainWindow.appStatus === "DetectingSpeech"
                         || micFadeOut.running

                Behavior on opacity { NumberAnimation { id: micFadeOut; duration: 400 } }
            }

            AudioWaveformView {
                id: ttsWaveform
                Layout.fillWidth: true
                Layout.preferredHeight: 64
                waveColor: "#00AEEF"
                amplitude: 0.5
                thickness: 2.2
                glowAmount: 0.02
                active: mainWindow.appStatus === "Speaking"
                visible: mainWindow.appStatus === "Speaking"
                         || ttsFadeOut.running

                Behavior on opacity { NumberAnimation { id: ttsFadeOut; duration: 400 } }
            }

            // ── Bottom bar ──
            BottomBar {
                Layout.fillWidth: true
                audioLevel: mainWindow.micLevel
            }
        }
    }

    // ══════════════════════════════════════════════
    //  Splash Screen — gatekeeper avant décision
    // ══════════════════════════════════════════════

    ExoSplashScreen {
        id: splashScreen
        anchors.fill: parent
        z: 1000
        visible: !mainWindow._safeBootDecisionMade && !mainWindow.startupSplashBypassed
        allReady: mainWindow.servicesReady
        readyCount: typeof serviceSupervisor !== 'undefined' ? serviceSupervisor.readyCount : 0
        totalServices: typeof serviceSupervisor !== 'undefined' ? serviceSupervisor.totalServices : 0
        currentAction: typeof serviceSupervisor !== 'undefined' ? serviceSupervisor.currentAction : "Initialisation…"
        serviceStatuses: typeof serviceSupervisor !== 'undefined' ? serviceSupervisor.serviceStatuses : []
        safeBootActive: typeof safeBootController !== 'undefined' ? safeBootController.safeBootEnabled : false
        criticalReady: typeof safeBootController !== 'undefined' ? (safeBootController.readyCount >= safeBootController.totalCount - safeBootController.degradedCount) : false
        criticalReadyCount: typeof safeBootController !== 'undefined' ? safeBootController.readyCount : 0
        criticalTotal: typeof safeBootController !== 'undefined' ? safeBootController.totalCount : 0
        lazyReadyCount: 0
        lazyTotal: typeof safeBootController !== 'undefined' ? safeBootController.degradedCount : 0
        failedCount: typeof safeBootController !== 'undefined' ? safeBootController.failedCount : 0
        failedServices: typeof safeBootController !== 'undefined' ? safeBootController.failedServices : []
        onDismissed: splashScreen.visible = false
    }

    // ══════════════════════════════════════════════
    //  Safe Boot Panel — fullscreen exclusif
    // ══════════════════════════════════════════════

    SafeBootPanel {
        id: safeBootPanel
        anchors.fill: parent
        z: 999
        visible: mainWindow._safeBootDecisionMade && mainWindow._safeBootActive

        safeBootEnabled: typeof safeBootController !== 'undefined' ? safeBootController.safeBootEnabled : false
        failedCount: typeof safeBootController !== 'undefined' ? safeBootController.failedCount : 0
        degradedCount: typeof safeBootController !== 'undefined' ? safeBootController.degradedCount : 0
        readyCount: typeof safeBootController !== 'undefined' ? safeBootController.readyCount : 0
        totalCount: typeof safeBootController !== 'undefined' ? safeBootController.totalCount : 0
        failedServices: typeof safeBootController !== 'undefined' ? safeBootController.failedServices : []
        degradedServices: typeof safeBootController !== 'undefined' ? safeBootController.degradedServices : []
        startupTimeline: typeof safeBootController !== 'undefined' ? safeBootController.startupTimeline : []

        onRetryRequested: {
            if (typeof safeBootController !== 'undefined')
                safeBootController.retryNonCriticalServices()
        }
        onRestartRequested: {
            if (typeof safeBootController !== 'undefined')
                safeBootController.restartNormalMode()
        }
    }

    Rectangle {
        id: startupFallbackOverlay
        anchors.fill: parent
        z: 1100
        visible: mainWindow.startupFallbackVisible
        color: "#CC111111"

        ColumnLayout {
            anchors.centerIn: parent
            width: Math.min(parent.width * 0.8, 760)
            spacing: Theme.spacing12

            Rectangle {
                Layout.fillWidth: true
                radius: Theme.radiusMedium
                color: Theme.bgSecondary
                border.color: Theme.warning
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing16
                    spacing: Theme.spacing8

                    Text {
                        Layout.fillWidth: true
                        text: "Interface en mode secours"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontBody
                        font.bold: true
                        color: Theme.warning
                    }

                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: "L'interface principale n'est pas visible alors que la fenetre est lancee."
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSmall
                        color: Theme.textPrimary
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "Etat: splash=" + splashScreen.visible
                              + " | safeboot=" + safeBootPanel.visible
                              + " | main=" + mainLayout.visible
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontMicro
                        color: Theme.textMuted
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing8

                        Button {
                            text: "Reafficher l'interface"
                            onClicked: {
                                mainWindow.startupFallbackVisible = false
                                mainLayout.visible = true
                            }
                        }

                        Button {
                            text: "Ouvrir Services"
                            onClicked: {
                                mainWindow.startupFallbackVisible = false
                                sidebar.activePanel = "services"
                                centralStack.currentIndex = 17
                            }
                        }
                    }
                }
            }
        }
    }

    // ══════════════════════════════════════════════
    //  Raccourcis clavier
    // ══════════════════════════════════════════════

    Shortcut {
        sequence: "Space"
        enabled: !mainWindow._safeBootActive
        onActivated: {
            if (typeof assistantManager !== 'undefined') {
                if (mainWindow.appStatus === "Listening") {
                    assistantManager.stopListening()
                } else {
                    assistantManager.startListening()
                }
            }
        }
    }

    Shortcut {
        sequence: "Escape"
        onActivated: {
            if (typeof assistantManager !== 'undefined') {
                assistantManager.stopListening()
            }
            mainWindow.appStatus = "Idle"
        }
    }

    Shortcut {
        sequence: "Ctrl+,"
        enabled: !mainWindow._safeBootActive
        onActivated: {
            sidebar.activePanel = "settings"
            centralStack.currentIndex = 1
        }
    }

    Shortcut {
        sequence: "Ctrl+H"
        enabled: !mainWindow._safeBootActive
        onActivated: {
            sidebar.activePanel = "history"
            centralStack.currentIndex = 2
        }
    }

    // ══════════════════════════════════════════════
    //  Persistance géométrie fenêtre
    // ══════════════════════════════════════════════

    function saveGeometry() {
        if (typeof configManager === 'undefined') return
        configManager.setUserValue("Window", "x", mainWindow.x)
        configManager.setUserValue("Window", "y", mainWindow.y)
        configManager.setUserValue("Window", "width", mainWindow.width)
        configManager.setUserValue("Window", "height", mainWindow.height)
    }

    onXChanged: saveGeometryTimer.restart()
    onYChanged: saveGeometryTimer.restart()
    onWidthChanged: saveGeometryTimer.restart()
    onHeightChanged: saveGeometryTimer.restart()

    Timer {
        id: saveGeometryTimer
        interval: 500
        onTriggered: mainWindow.saveGeometry()
    }

    Timer {
        id: startupBlankWatchdog
        interval: 12000
        running: true
        repeat: false
        onTriggered: {
            var looksBlank = !splashScreen.visible && !safeBootPanel.visible && !mainLayout.visible
            mainWindow.startupFallbackVisible = looksBlank
            if (looksBlank && !mainWindow.startupFallbackLogged) {
                mainWindow.startupFallbackLogged = true
                console.error("[UI][watchdog] Fenetre potentiellement vide detectee",
                              "splash=" + splashScreen.visible,
                              "safeBoot=" + safeBootPanel.visible,
                              "main=" + mainLayout.visible,
                              "decision=" + mainWindow._safeBootDecisionMade)
            }
        }
    }

    Timer {
        id: startupSplashWatchdog
        interval: 15000
        running: true
        repeat: false
        onTriggered: {
            if (!mainWindow._safeBootDecisionMade) {
                mainWindow.startupSplashBypassed = true
                console.error("[UI][watchdog] Timeout decision SafeBoot: bypass splash pour afficher l'interface",
                              "servicesReady=" + mainWindow.servicesReady,
                              "safeBootActive=" + mainWindow._safeBootActive)
            }
        }
    }

    // ══════════════════════════════════════════════
    //  Initialisation
    // ══════════════════════════════════════════════

    Component.onCompleted: {
        if (typeof configManager !== 'undefined') {
            var sx = configManager.getInt("Window", "x", -1)
            var sy = configManager.getInt("Window", "y", -1)
            var sw = configManager.getInt("Window", "width", 0)
            var sh = configManager.getInt("Window", "height", 0)
            if (sw > 0 && sh > 0) {
                mainWindow.width = sw
                mainWindow.height = sh
            }
            if (sx >= 0 && sy >= 0) {
                mainWindow.x = sx
                mainWindow.y = sy
            }
        }
    }
}
