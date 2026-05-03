import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

Rectangle {
    id: root
    color: Theme.bgPrimary

    // ── Données internes ──
    property var moduleStates: ({})
    ListModel { id: eventListModel }
    property string selectedModule: ""

    // Couleurs par état (via Theme)
    function stateColor(state) {
        return Theme.pipelineStateColor(state)
    }

    function stateBorderColor(state) {
        switch (state) {
        case "active":      return Theme.pipelineActive
        case "processing":  return Theme.warning
        case "error":       return Theme.pipelineError
        case "unavailable": return Theme.pipelineUnavail
        default:            return Theme.accent
        }
    }

    // ── Chargement initial + timer de rafraîchissement ──
    Timer {
        id: refreshTimer
        interval: 500
        repeat: true
        running: root.visible  // fix audit M4: ne tourne que si la page est visible
        onTriggered: root.refreshSnapshot()
    }

    Component.onCompleted: {
        refreshSnapshot()
        loadRecentEvents()
    }

    function refreshSnapshot() {
        if (typeof pipelineEventBus === 'undefined') return
        var snap = pipelineEventBus.getPipelineSnapshot()
        if (snap && snap.modules) {
            var newStates = {}
            for (var key in snap.modules) {
                newStates[key] = snap.modules[key]
            }
            root.moduleStates = newStates
        }
    }

    function loadRecentEvents() {
        if (typeof pipelineEventBus === 'undefined') return
        eventListModel.clear()
        var evts = pipelineEventBus.getRecentEvents(80)
        for (var i = 0; i < evts.length; i++) {
            eventListModel.append({
                "timestamp": evts[i].timestamp || "",
                "module": evts[i].module || "",
                "event_type": evts[i].event_type || "",
                "elapsed_ms": evts[i].elapsed_ms || 0
            })
        }
    }

    // Écouter les nouveaux événements en temps réel
    Connections {
        target: typeof pipelineEventBus !== 'undefined' ? pipelineEventBus : null

        function onEventEmitted(event) {
            // fix audit M2: insertion ListModel au lieu de copie array JS
            eventListModel.insert(0, {
                "timestamp": event.timestamp || "",
                "module": event.module || "",
                "event_type": event.event_type || "",
                "elapsed_ms": event.elapsed_ms || 0
            })
            while (eventListModel.count > 200)
                eventListModel.remove(eventListModel.count - 1)
        }

        function onModuleStateChanged(moduleName, state) {
            var copy = Object.assign({}, root.moduleStates)
            if (!copy[moduleName]) copy[moduleName] = {}
            copy[moduleName].state = state
            root.moduleStates = copy
        }
    }

    // ── Pipeline DAG definition ──
    readonly property var pipelineNodes: [
        { id: "audio_capture",  label: "Audio\nCapture",   col: 0, row: 1 },
        { id: "preprocessor",   label: "Preprocessor",     col: 1, row: 1 },
        { id: "vad",            label: "VAD",              col: 2, row: 1 },
        { id: "stt",            label: "STT",              col: 3, row: 1 },
        { id: "wake_word",      label: "Wake\nWord",       col: 2, row: 0 },
        { id: "nlu",            label: "NLU",              col: 4, row: 0 },
        { id: "orchestrator",   label: "Orchestrator",     col: 4, row: 1 },
        { id: "claude",         label: "Claude",           col: 5, row: 1 },
        { id: "memory",         label: "Memory",           col: 5, row: 0 },
        { id: "tts",            label: "TTS",              col: 6, row: 1 },
        { id: "audio_output",   label: "Audio\nOutput",    col: 7, row: 1 },
        { id: "gui",            label: "GUI",              col: 4, row: 2 }
    ]

    readonly property var pipelineEdges: [
        { from: "audio_capture", to: "preprocessor" },
        { from: "preprocessor",  to: "vad" },
        { from: "vad",           to: "stt" },
        { from: "vad",           to: "wake_word" },
        { from: "stt",           to: "orchestrator" },
        { from: "stt",           to: "nlu" },
        { from: "nlu",           to: "orchestrator" },
        { from: "orchestrator",  to: "claude" },
        { from: "orchestrator",  to: "gui" },
        { from: "claude",        to: "memory" },
        { from: "claude",        to: "tts" },
        { from: "tts",           to: "audio_output" }
    ]

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Header ──
        ExoPanelHeader {
            title: "PIPELINE MONITOR"

            rightContent: [
                Text {
                    text: {
                        if (typeof pipelineEventBus !== 'undefined') {
                            var cid = pipelineEventBus.getCorrelationId()
                            return cid ? ("CID: " + cid) : "No active interaction"
                        }
                        return ""
                    }
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontTiny
                    color: Theme.textMuted
                }
            ]
        }

        // ── SplitView vertical : DAG en haut, Timeline en bas ──
        SplitView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Vertical

            // ── DAG Pipeline View ──
            Rectangle {
                id: dagContainer
                SplitView.fillWidth: true
                SplitView.preferredHeight: 280
                SplitView.minimumHeight: 180
                color: Theme.bgPrimary

                // Canvas pour dessiner les arêtes
                Canvas {
                    id: edgeCanvas
                    anchors.fill: parent

                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        ctx.strokeStyle = Theme.border
                        ctx.lineWidth = 1.5

                        for (var i = 0; i < root.pipelineEdges.length; i++) {
                            var edge = root.pipelineEdges[i]
                            var fromNode = dagContainer.findNode(edge.from)
                            var toNode = dagContainer.findNode(edge.to)
                            if (!fromNode || !toNode) continue

                            var fx = dagContainer.nodeX(fromNode) + dagContainer.nodeW / 2
                            var fy = dagContainer.nodeY(fromNode) + dagContainer.nodeH / 2
                            var tx = dagContainer.nodeX(toNode) + dagContainer.nodeW / 2
                            var ty = dagContainer.nodeY(toNode) + dagContainer.nodeH / 2

                            var sourceState = dagContainer.getModuleState(edge.from)
                            if (sourceState === "active" || sourceState === "processing")
                                ctx.strokeStyle = Qt.rgba(0.306, 0.788, 0.690, 0.31)  // pipelineActive 50%
                            else
                                ctx.strokeStyle = Theme.border

                            ctx.beginPath()
                            ctx.moveTo(fx, fy)
                            var mx = (fx + tx) / 2
                            ctx.bezierCurveTo(mx, fy, mx, ty, tx, ty)
                            ctx.stroke()
                        }
                    }

                    Connections {
                        target: root
                        function onModuleStatesChanged() { edgeCanvas.requestPaint() }
                    }

                    Timer {
                        interval: 600
                        repeat: true
                        running: root.visible  // fix audit M4: pas de repaint Canvas quand invisible
                        onTriggered: edgeCanvas.requestPaint()
                    }
                }

                readonly property int dagCols: 8
                readonly property int dagRows: 3
                readonly property real nodeW: 90
                readonly property real nodeH: 52
                readonly property real padX: 16
                readonly property real padY: 20

                function nodeX(node) {
                    var usable = edgeCanvas.width - 2 * padX - nodeW
                    return padX + (node.col / (dagCols - 1)) * usable
                }
                function nodeY(node) {
                    var usable = edgeCanvas.height - 2 * padY - nodeH
                    return padY + (node.row / (dagRows - 1)) * usable
                }

                function findNode(id) {
                    for (var i = 0; i < root.pipelineNodes.length; i++) {
                        if (root.pipelineNodes[i].id === id)
                            return root.pipelineNodes[i]
                    }
                    return null
                }

                function getModuleState(id) {
                    if (root.moduleStates[id] && root.moduleStates[id].state)
                        return root.moduleStates[id].state
                    return "idle"
                }

                // Nœuds du pipeline
                Repeater {
                    model: root.pipelineNodes

                    Rectangle {
                        id: nodeRect
                        x: edgeCanvas.parent.nodeX(modelData)
                        y: edgeCanvas.parent.nodeY(modelData)
                        width: edgeCanvas.parent.nodeW
                        height: edgeCanvas.parent.nodeH
                        radius: Theme.radiusMedium
                        color: root.stateColor(edgeCanvas.parent.getModuleState(modelData.id))
                        border.width: root.selectedModule === modelData.id ? 2 : 1
                        border.color: {
                            if (root.selectedModule === modelData.id) return "#FFFFFF"
                            return root.stateBorderColor(edgeCanvas.parent.getModuleState(modelData.id))
                        }
                        opacity: 0.9

                        SequentialAnimation on opacity {
                            running: edgeCanvas.parent.getModuleState(modelData.id) === "processing"
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.5; duration: 600; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 0.9; duration: 600; easing.type: Easing.InOutSine }
                        }

                        Text {
                            anchors.centerIn: parent
                            text: modelData.label
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontTiny
                            font.bold: true
                            color: "#FFFFFF"
                            horizontalAlignment: Text.AlignHCenter
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.selectedModule = (root.selectedModule === modelData.id)
                                                      ? "" : modelData.id
                            }
                        }
                    }
                }

                // ── Légende des états ──
                Row {
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.margins: Theme.spacing10
                    spacing: Theme.spacing12

                    Repeater {
                        model: [
                            { label: "Idle",       color: Theme.pipelineIdle },
                            { label: "Active",     color: Theme.pipelineActive },
                            { label: "Processing", color: Theme.pipelineProcessing },
                            { label: "Error",      color: Theme.pipelineError }
                        ]

                        Row {
                            spacing: Theme.spacing4
                            Rectangle {
                                width: 10; height: 10; radius: 2
                                color: modelData.color
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                text: modelData.label
                                font.pixelSize: 9
                                font.family: Theme.fontMono
                                color: Theme.textMuted
                            }
                        }
                    }
                }
            }

            // ── Bottom half: Event Timeline + Inspector ──
            SplitView {
                SplitView.fillWidth: true
                SplitView.fillHeight: true
                SplitView.minimumHeight: 200
                orientation: Qt.Horizontal

                // ── Event Timeline ──
                Rectangle {
                    SplitView.fillWidth: true
                    SplitView.minimumWidth: 300
                    color: Theme.bgPrimary

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 0

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 28
                            color: Theme.bgSecondary

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacing10
                                anchors.rightMargin: Theme.spacing10

                                Text {
                                    text: "EVENT TIMELINE"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontTiny
                                    font.bold: true
                                    color: Theme.textMuted
                                    font.letterSpacing: 1
                                }

                                Item { Layout.fillWidth: true }

                                Text {
                                    text: eventListModel.count + " events"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontTiny
                                    color: Theme.textMuted
                                }
                            }
                        }

                        ListView {
                            id: eventList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: eventListModel  // fix audit M2: ListModel au lieu d'array JS

                            delegate: Rectangle {
                                width: eventList.width
                                height: 26
                                color: index % 2 === 0 ? Theme.bgPrimary : Theme.bgSecondary

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: Theme.spacing8
                                    anchors.rightMargin: Theme.spacing8
                                    spacing: Theme.spacing8

                                    Text {
                                        text: {
                                            var ts = model.timestamp || ""
                                            return ts.length > 12 ? ts.substring(11, 23) : ts
                                        }
                                        font.family: Theme.fontMono
                                        font.pixelSize: 9
                                        color: Theme.textMuted
                                        Layout.preferredWidth: 80
                                    }

                                    Rectangle {
                                        Layout.preferredWidth: 72
                                        Layout.preferredHeight: 16
                                        radius: 3
                                        color: root.stateColor(model.module === root.selectedModule ? "active" : "idle")
                                        opacity: 0.8

                                        Text {
                                            anchors.centerIn: parent
                                            text: model.module || ""
                                            font.family: Theme.fontMono
                                            font.pixelSize: 8
                                            font.bold: true
                                            color: "#FFFFFF"
                                        }
                                    }

                                    Text {
                                        text: model.event_type || ""
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontTiny
                                        color: Theme.textPrimary
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        text: {
                                            var ms = model.elapsed_ms
                                            return (ms !== undefined && ms > 0) ? (ms + "ms") : ""
                                        }
                                        font.family: Theme.fontMono
                                        font.pixelSize: 9
                                        color: Theme.warning
                                        Layout.preferredWidth: 50
                                        horizontalAlignment: Text.AlignRight
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (model.module)
                                            root.selectedModule = model.module
                                    }
                                }
                            }

                            ScrollBar.vertical: ScrollBar {
                                policy: ScrollBar.AsNeeded
                            }
                        }
                    }
                }

                // ── Module Inspector ──
                Rectangle {
                    id: inspectorPanel
                    SplitView.preferredWidth: 280
                    SplitView.minimumWidth: 200
                    color: Theme.bgSecondary

                    function logFilterForModule(moduleId) {
                        switch (moduleId) {
                        case "stt":            return "STT"
                        case "tts":            return "TTS"
                        case "vad":            return "VAD"
                        case "claude":         return "CLAUDE"
                        case "wake_word":      return "WAKE"
                        case "memory":         return "MEMORY"
                        case "nlu":            return "NLU"
                        case "orchestrator":   return "ORCHESTR"
                        case "audio_capture":  return "CAPTURE"
                        case "audio_output":   return "AUDIO_OUT"
                        case "preprocessor":   return "PREPROCESS"
                        case "gui":            return "GUI"
                        default:               return moduleId.toUpperCase()
                        }
                    }

                    property var moduleLogs: []
                    property bool logsCopied: false

                    function refreshModuleLogs() {
                        if (!root.selectedModule) { moduleLogs = []; return }
                        if (typeof logManager === 'undefined') { moduleLogs = []; return }
                        var filter = logFilterForModule(root.selectedModule)
                        var logs = logManager.getLogsByFilter(filter)
                        var arr = []
                        for (var i = 0; i < logs.length; i++) arr.push(logs[i])
                        moduleLogs = arr
                    }

                    Timer {
                        id: inspectorLogRefresh
                        interval: 1000
                        repeat: true
                        running: root.visible && !!root.selectedModule  // fix audit M4
                        onTriggered: inspectorPanel.refreshModuleLogs()
                    }

                    TextEdit {
                        id: inspectorClipHelper
                        visible: false
                    }

                    Timer {
                        id: copiedFeedbackTimer
                        interval: 1500
                        onTriggered: inspectorPanel.logsCopied = false
                    }

                    Connections {
                        target: root
                        function onSelectedModuleChanged() {
                            inspectorPanel.refreshModuleLogs()
                            inspectorPanel.logsCopied = false
                        }
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 0

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 28
                            color: Theme.bgPrimary

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: Theme.spacing10
                                text: root.selectedModule
                                      ? ("INSPECTOR: " + root.selectedModule.toUpperCase())
                                      : "INSPECTOR"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontTiny
                                font.bold: true
                                color: Theme.textMuted
                                font.letterSpacing: 1
                            }
                        }

                        Flickable {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            contentHeight: inspectorCol.height
                            clip: true

                            ColumnLayout {
                                id: inspectorCol
                                width: parent.width
                                spacing: Theme.spacing8

                                Text {
                                    visible: !root.selectedModule
                                    text: "Cliquer sur un module\npour l'inspecter"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.textMuted
                                    Layout.alignment: Qt.AlignHCenter
                                    Layout.topMargin: 40
                                    horizontalAlignment: Text.AlignHCenter
                                }

                                ColumnLayout {
                                    visible: !!root.selectedModule
                                    Layout.fillWidth: true
                                    Layout.margins: Theme.spacing12
                                    spacing: Theme.spacing6

                                    RowLayout {
                                        spacing: Theme.spacing8
                                        Text {
                                            text: "État:"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontMicro
                                            color: Theme.textMuted
                                        }
                                        Rectangle {
                                            width: stateText.width + Theme.spacing12
                                            height: 20
                                            radius: Theme.radiusSmall
                                            color: root.stateColor(inspectorState())

                                            Text {
                                                id: stateText
                                                anchors.centerIn: parent
                                                text: inspectorState()
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontTiny
                                                font.bold: true
                                                color: "#FFFFFF"
                                            }
                                        }
                                    }

                                    Text {
                                        text: "Dernier event: " + inspectorLastEvent()
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontTiny
                                        color: Theme.textPrimary
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                    }

                                    Text {
                                        visible: inspectorError() !== ""
                                        text: "Erreur: " + inspectorError()
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontTiny
                                        color: Theme.error
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 1
                                        color: Theme.border
                                        Layout.topMargin: Theme.spacing4
                                        Layout.bottomMargin: Theme.spacing4
                                    }

                                    Text {
                                        text: "Métriques"
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontTiny
                                        font.bold: true
                                        color: Theme.textMuted
                                    }

                                    Text {
                                        text: inspectorMetrics()
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontTiny
                                        color: Theme.warning
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 1
                                        color: Theme.border
                                        Layout.topMargin: Theme.spacing4
                                        Layout.bottomMargin: Theme.spacing4
                                    }

                                    Text {
                                        text: "Événements récents"
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontTiny
                                        font.bold: true
                                        color: Theme.textMuted
                                    }

                                    Repeater {
                                        model: moduleFilteredEvents()

                                        Text {
                                            text: modelData.event_type + (modelData.elapsed_ms > 0 ? (" +" + modelData.elapsed_ms + "ms") : "")
                                            font.family: Theme.fontMono
                                            font.pixelSize: 9
                                            color: Theme.textPrimary
                                        }
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 1
                                        color: Theme.border
                                        Layout.topMargin: Theme.spacing6
                                        Layout.bottomMargin: Theme.spacing4
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: Theme.spacing8

                                        Text {
                                            text: "Logs du service"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontTiny
                                            font.bold: true
                                            color: Theme.textMuted
                                        }

                                        Item { Layout.fillWidth: true }

                                        Text {
                                            text: inspectorPanel.moduleLogs.length + " lignes"
                                            font.family: Theme.fontMono
                                            font.pixelSize: 9
                                            color: Theme.textMuted
                                        }
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 26
                                        radius: Theme.radiusSmall
                                        color: inspectorPanel.logsCopied ? "#2D4F2D"
                                             : copyLogsMa.containsMouse ? Theme.bgInput
                                             : Theme.bgElevated
                                        border.width: 1
                                        border.color: inspectorPanel.logsCopied ? Theme.success : Theme.textDisabled

                                        RowLayout {
                                            anchors.centerIn: parent
                                            spacing: Theme.spacing6

                                            Text {
                                                text: inspectorPanel.logsCopied ? "✓" : "📋"
                                                font.pixelSize: Theme.fontMicro
                                            }
                                            Text {
                                                text: inspectorPanel.logsCopied ? "Copié !" : "Copier les logs"
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontTiny
                                                color: inspectorPanel.logsCopied ? Theme.success : Theme.textPrimary
                                            }
                                        }

                                        MouseArea {
                                            id: copyLogsMa
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                if (inspectorPanel.moduleLogs.length === 0) return
                                                var text = inspectorPanel.moduleLogs.join("\n")
                                                if (typeof logManager !== 'undefined' && logManager.copyToClipboard)
                                                    logManager.copyToClipboard(text)
                                                else {
                                                    inspectorClipHelper.text = text
                                                    inspectorClipHelper.selectAll()
                                                    inspectorClipHelper.copy()
                                                    inspectorClipHelper.text = ""
                                                }
                                                inspectorPanel.logsCopied = true
                                                copiedFeedbackTimer.restart()
                                            }
                                        }
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: Math.min(inspectorPanel.moduleLogs.length * 18 + 4, 300)
                                        color: Theme.bgPrimary
                                        radius: Theme.radiusSmall
                                        border.width: 1
                                        border.color: Theme.border
                                        visible: inspectorPanel.moduleLogs.length > 0

                                        ListView {
                                            id: inspectorLogList
                                            anchors.fill: parent
                                            anchors.margins: 2
                                            clip: true
                                            model: inspectorPanel.moduleLogs.slice(-20)  // fix audit T9: limiter à 20 lignes

                                            delegate: Text {
                                                width: inspectorLogList.width
                                                text: modelData
                                                font.family: Theme.fontMono
                                                font.pixelSize: 8
                                                color: {
                                                    if (modelData.indexOf("CRIT") !== -1 || modelData.indexOf("FATAL") !== -1) return Theme.error
                                                    if (modelData.indexOf("WARN") !== -1) return Theme.warning
                                                    return Theme.info
                                                }
                                                elide: Text.ElideRight

                                                MouseArea {
                                                    anchors.fill: parent
                                                    acceptedButtons: Qt.RightButton
                                                    onClicked: function(mouse) {
                                                        inspectorLineMenu.logLine = modelData
                                                        inspectorLineMenu.popup()
                                                    }
                                                }
                                            }

                                            ScrollBar.vertical: ScrollBar {
                                                policy: ScrollBar.AsNeeded
                                            }
                                        }
                                    }

                                    Text {
                                        visible: inspectorPanel.moduleLogs.length === 0
                                        text: "(aucun log pour ce module)"
                                        font.family: Theme.fontMono
                                        font.pixelSize: 9
                                        font.italic: true
                                        color: Theme.textMuted
                                    }
                                }
                            }
                        }
                    }

                    Menu {
                        id: inspectorLineMenu
                        property string logLine: ""

                        MenuItem {
                            text: "Copier cette ligne"
                            onTriggered: {
                                if (typeof logManager !== 'undefined' && logManager.copyToClipboard)
                                    logManager.copyToClipboard(inspectorLineMenu.logLine)
                                else {
                                    inspectorClipHelper.text = inspectorLineMenu.logLine
                                    inspectorClipHelper.selectAll()
                                    inspectorClipHelper.copy()
                                    inspectorClipHelper.text = ""
                                }
                            }
                        }

                        MenuItem {
                            text: "Copier tous les logs du module"
                            onTriggered: {
                                if (inspectorPanel.moduleLogs.length === 0) return
                                var text = inspectorPanel.moduleLogs.join("\n")
                                if (typeof logManager !== 'undefined' && logManager.copyToClipboard)
                                    logManager.copyToClipboard(text)
                                else {
                                    inspectorClipHelper.text = text
                                    inspectorClipHelper.selectAll()
                                    inspectorClipHelper.copy()
                                    inspectorClipHelper.text = ""
                                }
                            }
                        }
                    }
                }

                handle: Rectangle {
                    implicitWidth: 1
                    color: Theme.border
                }
            }

            handle: Rectangle {
                implicitHeight: 1
                color: Theme.border
            }
        }
    }

    // ── Helper functions pour l'inspecteur ──
    function inspectorState() {
        if (!root.selectedModule) return "idle"
        var info = root.moduleStates[root.selectedModule]
        return info ? (info.state || "idle") : "idle"
    }

    function inspectorLastEvent() {
        if (!root.selectedModule) return "-"
        var info = root.moduleStates[root.selectedModule]
        return info ? (info.last_event || "-") : "-"
    }

    function inspectorError() {
        if (!root.selectedModule) return ""
        var info = root.moduleStates[root.selectedModule]
        return info ? (info.last_error || "") : ""
    }

    function inspectorMetrics() {
        if (!root.selectedModule) return "-"
        var info = root.moduleStates[root.selectedModule]
        if (!info || !info.metrics) return "(aucune)"
        var lines = []
        for (var key in info.metrics) {
            lines.push(key + ": " + JSON.stringify(info.metrics[key]))
        }
        return lines.length > 0 ? lines.join("\n") : "(aucune)"
    }

    function moduleFilteredEvents() {
        if (!root.selectedModule) return []
        var filtered = []
        for (var i = 0; i < eventListModel.count && filtered.length < 15; i++) {
            var evt = eventListModel.get(i)
            if (evt.module === root.selectedModule)
                filtered.push(evt)
        }
        return filtered
    }
}
