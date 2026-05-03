import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  ObservabilityDashboard — Services & métriques agrégées
// ═══════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    // ── Service statuses ──
    property var services: []
    // Format: [ { name, host, port, status, latency_ms, uptime } ]

    // ── Métriques agrégées ──
    property real avgLatency: 0
    property int totalRequests: 0
    property int totalErrors: 0
    property real uptime: 0

    property int activeTab: 0  // 0=Services, 1=Métriques, 2=Logs, 3=Traces

    // ── Logs & Traces ──
    property var logs: []
    property var traces: []
    property string moduleFilter: ""  // "" = tous
    readonly property var moduleList: ["audio_capture", "vad", "stt", "claude", "tts", "nlu", "orchestrator"]

    function refreshLogs() {
        if (typeof logManager === 'undefined') return
        if (root.moduleFilter !== "")
            root.logs = logManager.getLogsByFilter(root.moduleFilter) || []
        else
            root.logs = logManager.getRecentLogs() || []
    }

    function refreshTraces() {
        if (typeof pipelineEventBus === 'undefined') return
        if (root.moduleFilter !== "")
            root.traces = pipelineEventBus.getModuleTimeline(root.moduleFilter, 100) || []
        else
            root.traces = pipelineEventBus.getRecentEvents(100) || []
    }

    onModuleFilterChanged: { refreshLogs(); refreshTraces() }

    // ── Connexions ──
    Connections {
        target: typeof serviceSupervisor !== 'undefined' ? serviceSupervisor : null

        function onAllServicesReady() {
            root.services = serviceSupervisor.serviceStatuses || []
        }
    }

    Connections {
        target: typeof pipelineEventBus !== 'undefined' ? pipelineEventBus : null

        function onEventEmitted(event) {
            // Update aggregate metrics only (traces are in PipelinePage)
            root.totalRequests++
            var n = root.totalRequests
            root.avgLatency = (root.avgLatency * (n - 1) + (event.elapsed_ms || 0)) / n
            if ((event.event_type || "").indexOf("error") !== -1)
                root.totalErrors++
        }
    }

    // Initial service load
    Timer {
        interval: 2000
        repeat: true
        running: root.visible
        onTriggered: {
            if (typeof serviceSupervisor !== 'undefined')
                root.services = serviceSupervisor.serviceStatuses || []
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing8
        spacing: Theme.spacing8

        // ── Header ──
        RowLayout {
            Layout.fillWidth: true

            Text {
                text: "OBSERVABILITY"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontMicro
                font.weight: Font.Bold
                color: Theme.textAccent
                font.letterSpacing: 1.5
            }

            Item { Layout.fillWidth: true }

            // Quick stats
            Row {
                spacing: Theme.spacing16

                Text {
                    text: "Avg: " + root.avgLatency.toFixed(0) + "ms"
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontTiny
                    color: root.avgLatency > 1000 ? Theme.warning : Theme.textMuted
                }
                Text {
                    text: "Req: " + root.totalRequests
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontTiny
                    color: Theme.textMuted
                }
                Text {
                    text: "Err: " + root.totalErrors
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontTiny
                    color: root.totalErrors > 0 ? Theme.error : Theme.textMuted
                }
            }
        }

        // ── Module Filter ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing8

            Text {
                text: "Module:"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontTiny
                color: Theme.textSecondary
            }

            Repeater {
                model: [""].concat(root.moduleList)

                Rectangle {
                    width: fLabel.implicitWidth + 12
                    height: 22; radius: Theme.radiusSmall
                    color: root.moduleFilter === modelData ? Theme.accent : Theme.bgElevated
                    border.width: 1
                    border.color: root.moduleFilter === modelData ? Theme.accent : Theme.border

                    Text {
                        id: fLabel
                        anchors.centerIn: parent
                        text: modelData === "" ? "Tous" : modelData
                        font.family: Theme.fontMono
                        font.pixelSize: 9
                        color: root.moduleFilter === modelData ? "#FFFFFF" : Theme.textSecondary
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.moduleFilter = modelData
                    }
                }
            }
        }

        // ── Tab Bar ──
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            Repeater {
                model: [
                    { label: "Services",  idx: 0 },
                    { label: "Métriques", idx: 1 },
                    { label: "Logs",      idx: 2 },
                    { label: "Traces",    idx: 3 }
                ]

                Rectangle {
                    Layout.fillWidth: true
                    height: 32
                    color: root.activeTab === modelData.idx ? Theme.bgElevated : "transparent"

                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width; height: 2
                        color: root.activeTab === modelData.idx ? Theme.accent : Theme.border
                    }

                    Text {
                        anchors.centerIn: parent
                        text: modelData.label
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSmall
                        color: root.activeTab === modelData.idx ? Theme.textPrimary : Theme.textSecondary
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.activeTab = modelData.idx
                    }
                }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.activeTab

            // ── Tab 0: Services ──
            ListView {
                id: serviceList
                clip: true
                spacing: Theme.spacing4
                boundsBehavior: Flickable.StopAtBounds
                model: root.services.length

                delegate: Rectangle {
                    width: serviceList.width
                    height: 56
                    radius: Theme.radiusSmall
                    color: Theme.bgElevated

                    readonly property var svc: root.services[index] || {}
                    readonly property bool isUp: (svc.status || "") === "ready" || (svc.status || "") === "online"

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacing8
                        spacing: Theme.spacing12

                        // Status dot
                        Rectangle {
                            width: 10; height: 10; radius: 5
                            color: isUp ? Theme.success : Theme.error

                            SequentialAnimation on opacity {
                                running: !isUp
                                loops: Animation.Infinite
                                NumberAnimation { to: 0.3; duration: 500 }
                                NumberAnimation { to: 1.0; duration: 500 }
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                text: svc.name || "Unknown"
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSmall
                                font.weight: Font.Medium
                                color: Theme.textPrimary
                            }
                            Text {
                                text: (svc.host || "localhost") + ":" + (svc.port || "?")
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontTiny
                                color: Theme.textMuted
                            }
                        }

                        Text {
                            text: (svc.latency_ms || 0) > 0 ? (svc.latency_ms || 0).toFixed(0) + " ms" : "—"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSmall
                            color: (svc.latency_ms || 0) > 500 ? Theme.warning : Theme.textSecondary
                        }

                        Rectangle {
                            width: statusText.implicitWidth + 10
                            height: 20; radius: Theme.radiusSmall
                            color: isUp ? Qt.rgba(Theme.success.r, Theme.success.g, Theme.success.b, 0.15)
                                       : Qt.rgba(Theme.error.r, Theme.error.g, Theme.error.b, 0.15)

                            Text {
                                id: statusText
                                anchors.centerIn: parent
                                text: (svc.status || "unknown").toUpperCase()
                                font.family: Theme.fontMono
                                font.pixelSize: 9
                                font.weight: Font.Bold
                                color: isUp ? Theme.success : Theme.error
                            }
                        }
                    }
                }

                // Default services when empty
                Component.onCompleted: {
                    if (root.services.length === 0) {
                        root.services = [
                            { name: "STT Server",      host: "localhost", port: 8766, status: "ready" },
                            { name: "TTS Server",      host: "localhost", port: 8767, status: "ready" },
                            { name: "VAD Server",      host: "localhost", port: 8768, status: "ready" },
                            { name: "WakeWord Server", host: "localhost", port: 8769, status: "ready" },
                            { name: "Memory Server",   host: "localhost", port: 8770, status: "ready" },
                            { name: "NLU Server",      host: "localhost", port: 8771, status: "ready" },
                            { name: "Orchestrator",    host: "localhost", port: 8765, status: "ready" }
                        ]
                    }
                }
            }

            // ── Tab 1: Métriques ──
            ScrollView {
                clip: true

            GridLayout {
                columns: 2
                rowSpacing: Theme.spacing8
                columnSpacing: Theme.spacing8

                // Metric cards
                Repeater {
                    model: [
                        { label: "Latence moyenne",   value: root.avgLatency.toFixed(0) + " ms", color: root.avgLatency > 1000 ? Theme.warning : Theme.success },
                        { label: "Requêtes totales",  value: root.totalRequests.toString(),       color: Theme.info },
                        { label: "Erreurs",           value: root.totalErrors.toString(),         color: root.totalErrors > 0 ? Theme.error : Theme.success },
                        { label: "Services actifs",   value: root.services.length.toString(),     color: Theme.success }
                    ]

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 80
                        radius: Theme.radiusMedium
                        color: Theme.bgElevated

                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 4

                            Text {
                                Layout.alignment: Qt.AlignHCenter
                                text: modelData.value
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontH2
                                font.weight: Font.Bold
                                color: modelData.color
                            }
                            Text {
                                Layout.alignment: Qt.AlignHCenter
                                text: modelData.label
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontTiny
                                color: Theme.textMuted
                            }
                        }
                    }
                }
            }
            } // ScrollView

            // ── Tab 2: Logs ──
            Item {
                Timer {
                    interval: 2000
                    repeat: true
                    running: root.visible && root.activeTab === 2
                    onTriggered: root.refreshLogs()
                }
                Component.onCompleted: root.refreshLogs()

                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.spacing4

                    // Actions bar
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing8

                        Text {
                            text: root.logs.length + " entrées"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontTiny
                            color: Theme.textMuted
                        }
                        Item { Layout.fillWidth: true }
                        Rectangle {
                            width: refreshLabel.implicitWidth + 12
                            height: 22; radius: Theme.radiusSmall
                            color: Theme.bgElevated
                            border.width: 1; border.color: Theme.border

                            Text {
                                id: refreshLabel
                                anchors.centerIn: parent
                                text: "⟳ Refresh"
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontTiny
                                color: Theme.textSecondary
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.refreshLogs()
                            }
                        }
                        Rectangle {
                            width: clearLabel.implicitWidth + 12
                            height: 22; radius: Theme.radiusSmall
                            color: Theme.bgElevated
                            border.width: 1; border.color: Theme.border

                            Text {
                                id: clearLabel
                                anchors.centerIn: parent
                                text: "✕ Clear"
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontTiny
                                color: Theme.textSecondary
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: { if (typeof logManager !== 'undefined') logManager.clearLogs(); root.refreshLogs() }
                            }
                        }
                    }

                    ListView {
                        id: logList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 2
                        boundsBehavior: Flickable.StopAtBounds
                        model: root.logs.length

                        delegate: Rectangle {
                            width: logList.width
                            height: logContent.implicitHeight + 12
                            radius: Theme.radiusSmall
                            color: Theme.bgElevated

                            readonly property var entry: root.logs[index] || {}
                            readonly property string lvl: (entry.level || "info").toLowerCase()

                            RowLayout {
                                id: logContent
                                anchors.fill: parent
                                anchors.margins: Theme.spacing4
                                spacing: Theme.spacing6

                                // Level badge
                                Rectangle {
                                    width: 38; height: 16; radius: 3
                                    color: lvl === "error" ? Qt.rgba(Theme.error.r, Theme.error.g, Theme.error.b, 0.2)
                                         : lvl === "warning" ? Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.2)
                                         : Qt.rgba(Theme.info.r, Theme.info.g, Theme.info.b, 0.1)

                                    Text {
                                        anchors.centerIn: parent
                                        text: lvl.substring(0, 4).toUpperCase()
                                        font.family: Theme.fontMono
                                        font.pixelSize: 8; font.bold: true
                                        color: lvl === "error" ? Theme.error : lvl === "warning" ? Theme.warning : Theme.textMuted
                                    }
                                }

                                // Timestamp
                                Text {
                                    text: (entry.timestamp || "").substring(11, 19)
                                    font.family: Theme.fontMono
                                    font.pixelSize: 9
                                    color: Theme.textMuted
                                    Layout.preferredWidth: 55
                                }

                                // Module
                                Text {
                                    text: entry.module || ""
                                    font.family: Theme.fontMono
                                    font.pixelSize: 9
                                    color: Theme.pipelineActive
                                    Layout.preferredWidth: 80
                                    elide: Text.ElideRight
                                }

                                // Message
                                Text {
                                    text: entry.message || ""
                                    font.family: Theme.fontMono
                                    font.pixelSize: 9
                                    color: Theme.textPrimary
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    wrapMode: Text.NoWrap
                                }
                            }
                        }
                    }
                }
            }

            // ── Tab 3: Traces ──
            Item {
                Timer {
                    interval: 2000
                    repeat: true
                    running: root.visible && root.activeTab === 3
                    onTriggered: root.refreshTraces()
                }
                Component.onCompleted: root.refreshTraces()

                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.spacing4

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            text: root.traces.length + " events"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontTiny
                            color: Theme.textMuted
                        }
                        Item { Layout.fillWidth: true }

                        // Correlation ID
                        Text {
                            property string cid: typeof pipelineEventBus !== 'undefined' ? (pipelineEventBus.getCorrelationId() || "") : ""
                            text: cid !== "" ? "CID: " + cid.substring(0, 8) : ""
                            font.family: Theme.fontMono
                            font.pixelSize: 9
                            color: Theme.textAccent
                        }
                    }

                    ListView {
                        id: traceList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 2
                        boundsBehavior: Flickable.StopAtBounds
                        model: root.traces.length

                        delegate: Rectangle {
                            width: traceList.width
                            height: 40
                            radius: Theme.radiusSmall
                            color: Theme.bgElevated

                            readonly property var evt: root.traces[index] || {}

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing4
                                spacing: Theme.spacing8

                                // Module dot
                                Rectangle {
                                    width: 8; height: 8; radius: 4
                                    color: {
                                        var s = evt.module_state || "idle"
                                        return s === "active" ? Theme.pipelineActive
                                             : s === "processing" ? Theme.pipelineProcessing
                                             : s === "error" ? Theme.pipelineError
                                             : Theme.pipelineIdle
                                    }
                                }

                                // Module
                                Text {
                                    text: evt.module || "?"
                                    font.family: Theme.fontMono
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                    color: Theme.pipelineActive
                                    Layout.preferredWidth: 80
                                    elide: Text.ElideRight
                                }

                                // Event type
                                Text {
                                    text: evt.event_type || ""
                                    font.family: Theme.fontMono
                                    font.pixelSize: 9
                                    color: Theme.textPrimary
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }

                                // Elapsed
                                Text {
                                    text: (evt.elapsed_ms || 0) > 0 ? (evt.elapsed_ms).toFixed(0) + " ms" : ""
                                    font.family: Theme.fontMono
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                    color: (evt.elapsed_ms || 0) > 3000 ? Theme.error
                                         : (evt.elapsed_ms || 0) > 1000 ? Theme.warning
                                         : Theme.success
                                    Layout.preferredWidth: 50
                                    horizontalAlignment: Text.AlignRight
                                }

                                // Timestamp
                                Text {
                                    text: (evt.timestamp || "").substring(11, 19)
                                    font.family: Theme.fontMono
                                    font.pixelSize: 9
                                    color: Theme.textMuted
                                    Layout.preferredWidth: 55
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
