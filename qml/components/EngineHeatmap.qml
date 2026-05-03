import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
//  EngineHeatmap â€” Grille 8Ã—8 des moteurs EXO
//  Visualise temps d'exÃ©cution, charge, erreurs, appels cumulÃ©s
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

Rectangle {
    id: root
    color: Theme.bgPrimary

    // â”€â”€ DonnÃ©es engines (peuplÃ©e par pipelineEventBus) â”€â”€
    property var engineData: ({})
    // Format: { "stt": { calls: N, errors: N, avg_ms: N, last_ms: N, state: "..." }, ... }

    // â”€â”€ Engines EXO â”€â”€
    readonly property var engines: [
        "audio_capture", "preprocessor", "vad", "wake_word",
        "stt", "nlu", "orchestrator", "claude",
        "memory", "tts", "audio_output", "gui",
        "cache", "governance", "faiss", "supervisor"
    ]

    readonly property var engineLabels: ({
        "audio_capture": "Audio In",   "preprocessor": "DSP",
        "vad": "VAD",                  "wake_word": "WakeWord",
        "stt": "STT",                  "nlu": "NLU",
        "orchestrator": "Orchestrator","claude": "Claude",
        "memory": "Memory",           "tts": "TTS",
        "audio_output": "Audio Out",   "gui": "GUI",
        "cache": "Cache",             "governance": "Governance",
        "faiss": "FAISS",             "supervisor": "Supervisor"
    })

    // â”€â”€ MÃ©trique affichÃ©e â”€â”€
    property string activeMetric: "last_ms"  // last_ms | calls | errors | avg_ms

    // â”€â”€ RafraÃ®chissement â”€â”€
    Connections {
        target: typeof pipelineEventBus !== 'undefined' ? pipelineEventBus : null

        function onEventEmitted(event) {
            var mod = event.module || ""
            var copy = Object.assign({}, root.engineData)
            if (!copy[mod]) copy[mod] = { calls: 0, errors: 0, avg_ms: 0, last_ms: 0, state: "idle" }
            copy[mod].calls = (copy[mod].calls || 0) + 1
            copy[mod].last_ms = event.elapsed_ms || 0
            // Running average
            var n = copy[mod].calls
            copy[mod].avg_ms = ((copy[mod].avg_ms || 0) * (n - 1) + (event.elapsed_ms || 0)) / n
            if ((event.event_type || "").indexOf("error") !== -1)
                copy[mod].errors = (copy[mod].errors || 0) + 1
            root.engineData = copy
        }

        function onModuleStateChanged(moduleName, state) {
            var copy = Object.assign({}, root.engineData)
            if (!copy[moduleName]) copy[moduleName] = { calls: 0, errors: 0, avg_ms: 0, last_ms: 0 }
            copy[moduleName].state = state
            root.engineData = copy
        }
    }

    function cellColor(value, metric) {
        if (metric === "errors") {
            if (value === 0) return Theme.bgElevated
            if (value < 3)   return Qt.rgba(0.957, 0.278, 0.278, 0.2)   // error 20%
            if (value < 10)  return Qt.rgba(0.957, 0.278, 0.278, 0.5)
            return Qt.rgba(0.957, 0.278, 0.278, 0.8)
        }
        if (metric === "calls") {
            if (value === 0)   return Theme.bgElevated
            if (value < 10)    return Qt.rgba(0.306, 0.788, 0.690, 0.15)
            if (value < 100)   return Qt.rgba(0.306, 0.788, 0.690, 0.35)
            if (value < 1000)  return Qt.rgba(0.306, 0.788, 0.690, 0.55)
            return Qt.rgba(0.306, 0.788, 0.690, 0.75)
        }
        // Latency (last_ms / avg_ms)
        if (value === 0)    return Theme.bgElevated
        if (value < 50)     return Qt.rgba(0.306, 0.788, 0.690, 0.25)  // green
        if (value < 200)    return Qt.rgba(0.306, 0.788, 0.690, 0.50)
        if (value < 500)    return Qt.rgba(0.863, 0.863, 0.667, 0.40)  // yellow
        if (value < 1000)   return Qt.rgba(0.863, 0.863, 0.667, 0.65)
        return Qt.rgba(0.957, 0.278, 0.278, 0.60)                       // red
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing8
        spacing: Theme.spacing8

        // â”€â”€ Header â”€â”€
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing12

            Text {
                text: "ENGINE HEATMAP"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontMicro
                font.weight: Font.Bold
                color: Theme.textAccent
                font.letterSpacing: 1.5
            }

            Item { Layout.fillWidth: true }

            // SÃ©lecteur de mÃ©trique
            Repeater {
                model: [
                    { key: "last_ms", label: "Latence" },
                    { key: "calls",   label: "Appels" },
                    { key: "errors",  label: "Erreurs" },
                    { key: "avg_ms",  label: "Moy." }
                ]

                Rectangle {
                    width: metricLabel.implicitWidth + Theme.spacing16
                    height: 24
                    radius: Theme.radiusSmall
                    color: root.activeMetric === modelData.key ? Theme.accentActive : "transparent"
                    border.width: root.activeMetric === modelData.key ? 1 : 0
                    border.color: Theme.accent

                    Text {
                        id: metricLabel
                        anchors.centerIn: parent
                        text: modelData.label
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontTiny
                        color: root.activeMetric === modelData.key ? Theme.textPrimary : Theme.textSecondary
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.activeMetric = modelData.key
                    }
                }
            }
        }

        // â”€â”€ Grille Heatmap (4Ã—4 pour 16 engines) â”€â”€
        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 4
            rowSpacing: Theme.spacing4
            columnSpacing: Theme.spacing4

            Repeater {
                model: root.engines.length

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 70
                    Layout.minimumWidth: 80

                    readonly property string engineId: root.engines[index]
                    readonly property var edata: root.engineData[engineId] || {}
                    readonly property real metricValue: edata[root.activeMetric] || 0

                    radius: Theme.radiusMedium
                    color: root.cellColor(metricValue, root.activeMetric)
                    border.width: (edata.state === "active" || edata.state === "processing") ? 1 : 0
                    border.color: Theme.pipelineActive

                    Behavior on color { ColorAnimation { duration: Theme.animSlow } }

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 2

                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: root.engineLabels[engineId] || engineId
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontTiny
                            font.weight: Font.Medium
                            color: Theme.textPrimary
                        }

                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: {
                                if (root.activeMetric === "last_ms" || root.activeMetric === "avg_ms")
                                    return metricValue.toFixed(0) + " ms"
                                return metricValue.toFixed(0)
                            }
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontBody
                            font.weight: Font.Bold
                            color: Theme.textPrimary
                        }

                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: (edata.calls || 0) + " calls"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontTiny
                            color: Theme.textMuted
                            visible: root.activeMetric !== "calls"
                        }
                    }

                    // Tooltip on hover
                    ToolTip {
                        id: cellTip
                        visible: cellMouse.containsMouse
                        delay: 400
                        text: (root.engineLabels[engineId] || engineId) +
                              "\nLatence: " + (edata.last_ms || 0).toFixed(0) + " ms" +
                              "\nMoy: " + (edata.avg_ms || 0).toFixed(0) + " ms" +
                              "\nAppels: " + (edata.calls || 0) +
                              "\nErreurs: " + (edata.errors || 0) +
                              "\nÃ‰tat: " + (edata.state || "idle")

                        background: Rectangle {
                            color: Theme.bgElevated
                            border.color: Theme.border
                            radius: Theme.radiusSmall
                        }
                        contentItem: Text {
                            text: cellTip.text
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontTiny
                            color: Theme.textPrimary
                        }
                    }

                    MouseArea {
                        id: cellMouse
                        anchors.fill: parent
                        hoverEnabled: true
                    }
                }
            }
        }

        // â”€â”€ LÃ©gende â”€â”€
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing16

            Text {
                text: "â–  Rapide"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontTiny
                color: Theme.success
            }
            Text {
                text: "â–  ModÃ©rÃ©"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontTiny
                color: Theme.warning
            }
            Text {
                text: "â–  Lent"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontTiny
                color: Theme.error
            }
            Item { Layout.fillWidth: true }
            Text {
                text: {
                    var total = 0
                    for (var k in root.engineData)
                        total += (root.engineData[k].calls || 0)
                    return "Total events: " + total
                }
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontTiny
                color: Theme.textMuted
            }
        }
    }
}
