import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  CognitiveTimeline v2 — Timeline verticale temps réel
//  8 couches : Perception → Supervision
//  PERF FIX: Timer guard + layerColor cached in delegate
// ═══════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    property bool compact: false
    property var layerData: ({})

    readonly property var layers: [
        { id: "perception",     label: "Perception",      icon: "🎤", mapModule: "audio_capture", desc: "Capture audio brute" },
        { id: "preprocessing",  label: "Preprocessing",   icon: "🔧", mapModule: "preprocessor",  desc: "Filtrage & normalisation" },
        { id: "detection",      label: "Détection",       icon: "📡", mapModule: "vad",            desc: "Voice Activity Detection" },
        { id: "recognition",    label: "Reconnaissance",  icon: "💬", mapModule: "stt",            desc: "Speech-to-Text (Whisper)" },
        { id: "understanding",  label: "Compréhension",   icon: "🧠", mapModule: "nlu",            desc: "Natural Language Understanding" },
        { id: "reasoning",      label: "Raisonnement",    icon: "⚡", mapModule: "claude",         desc: "LLM (Claude Opus)" },
        { id: "synthesis",      label: "Synthèse",        icon: "🔊", mapModule: "tts",            desc: "Text-to-Speech (Orpheus 3B FR)" },
        { id: "supervision",    label: "Supervision",     icon: "🛡", mapModule: "orchestrator",   desc: "Pipeline orchestration" }
    ]

    // ── Connexions temps réel ──
    Connections {
        target: typeof pipelineEventBus !== 'undefined' ? pipelineEventBus : null

        function onModuleStateChanged(moduleName, state) {
            var copy = Object.assign({}, root.layerData)
            for (var i = 0; i < root.layers.length; i++) {
                if (root.layers[i].mapModule === moduleName) {
                    if (!copy[root.layers[i].id]) copy[root.layers[i].id] = {}
                    copy[root.layers[i].id].state = state
                    break
                }
            }
            root.layerData = copy
        }

        function onEventEmitted(event) {
            var copy = Object.assign({}, root.layerData)
            for (var i = 0; i < root.layers.length; i++) {
                if (root.layers[i].mapModule === (event.module || "")) {
                    var lid = root.layers[i].id
                    if (!copy[lid]) copy[lid] = {}
                    copy[lid].elapsed_ms = event.elapsed_ms || 0
                    copy[lid].engine     = event.engine || ""
                    copy[lid].confidence = event.confidence || 0
                    copy[lid].lastEvent  = event.event_type || ""
                    copy[lid].timestamp  = event.timestamp || ""
                    break
                }
            }
            root.layerData = copy
        }
    }

    // ── Timer polling 500 ms (PERF FIX: guard running sur présence du bus) ──
    Timer {
        id: snapTimer
        interval: 500
        repeat: true
        running: root.visible && typeof pipelineEventBus !== 'undefined'
        onTriggered: {
            var snap = pipelineEventBus.getPipelineSnapshot()
            if (!snap || !snap.modules) return
            var copy = Object.assign({}, root.layerData)
            for (var i = 0; i < root.layers.length; i++) {
                var mod = root.layers[i].mapModule
                var lid = root.layers[i].id
                if (snap.modules[mod]) {
                    if (!copy[lid]) copy[lid] = {}
                    copy[lid].state = snap.modules[mod].state || "idle"
                    if (snap.modules[mod].elapsed_ms !== undefined)
                        copy[lid].elapsed_ms = snap.modules[mod].elapsed_ms
                }
            }
            root.layerData = copy
        }
    }

    function layerColor(state) {
        switch (state) {
        case "active":      return Theme.pipelineActive
        case "processing":  return Theme.pipelineProcessing
        case "error":       return Theme.pipelineError
        case "unavailable": return Theme.pipelineUnavail
        default:            return Theme.pipelineIdle
        }
    }

    function durationColor(ms) {
        if (ms <= 0)   return Theme.textMuted
        if (ms < 1000) return Theme.success
        if (ms < 3000) return Theme.warning
        return Theme.error
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: compact ? Theme.spacing4 : Theme.spacing8
        spacing: 0

        // ── Header ──
        RowLayout {
            Layout.fillWidth: true
            Layout.bottomMargin: Theme.spacing6
            visible: !compact

            Text {
                text: "COGNITIVE TIMELINE"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontMicro
                font.weight: Font.Bold
                color: Theme.textAccent
                font.letterSpacing: 1.5
            }

            Item { Layout.fillWidth: true }

            Text {
                property int activeCount: {
                    var c = 0
                    for (var i = 0; i < root.layers.length; i++) {
                        var d = root.layerData[root.layers[i].id]
                        if (d && (d.state === "active" || d.state === "processing")) c++
                    }
                    return c
                }
                text: activeCount + "/8 actives"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontTiny
                color: activeCount > 0 ? Theme.pipelineActive : Theme.textMuted
            }
        }

        Text {
            visible: compact
            text: "COGNITION"
            font.family: Theme.fontFamily
            font.pixelSize: 9
            font.weight: Font.Bold
            font.letterSpacing: 1.2
            color: Theme.textAccent
            Layout.bottomMargin: Theme.spacing4
        }

        // ── Timeline ──
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ListView {
                id: timelineList
                model: root.layers.length
                spacing: 0
                boundsBehavior: Flickable.StopAtBounds

                delegate: Item {
                    width: timelineList.width
                    height: compact ? 44 : 68

                    readonly property var layerInfo: root.layers[index]
                    readonly property var ldata:     root.layerData[layerInfo.id] || {}
                    readonly property string lstate: ldata.state || "idle"
                    readonly property real elapsed:  ldata.elapsed_ms || 0
                    // PERF FIX: layerColor calculé une seule fois par delegate
                    readonly property color cachedLayerColor: root.layerColor(lstate)

                    Behavior on height { NumberAnimation { duration: Theme.animNormal } }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin:  compact ? Theme.spacing4 : Theme.spacing12
                        anchors.rightMargin: compact ? Theme.spacing4 : Theme.spacing12
                        spacing: compact ? Theme.spacing6 : Theme.spacing12

                        // ── Nœud timeline ──
                        Item {
                            Layout.preferredWidth: compact ? 20 : 32
                            Layout.fillHeight: true

                            Rectangle {
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: 2; height: parent.height
                                color: cachedLayerColor
                                opacity: 0.3
                                visible: index < root.layers.length - 1
                            }

                            Rectangle {
                                id: nodeCircle
                                anchors.centerIn: parent
                                width: compact ? 18 : 24
                                height: width; radius: width / 2
                                color: cachedLayerColor
                                border.width: (lstate === "active" || lstate === "processing") ? 2 : 0
                                border.color: Qt.lighter(cachedLayerColor, 1.4)

                                Behavior on color { ColorAnimation { duration: Theme.animNormal } }

                                Text {
                                    anchors.centerIn: parent
                                    text: compact ? "" : (index + 1).toString()
                                    font.family: Theme.fontMono
                                    font.pixelSize: compact ? 7 : Theme.fontTiny
                                    font.bold: true
                                    color: "#FFFFFF"
                                }

                                SequentialAnimation on scale {
                                    running: lstate === "active" || lstate === "processing"
                                    loops: Animation.Infinite
                                    NumberAnimation { to: 1.2; duration: 500; easing.type: Easing.InOutSine }
                                    NumberAnimation { to: 1.0; duration: 500; easing.type: Easing.InOutSine }
                                }
                            }

                            Rectangle {
                                anchors.centerIn: nodeCircle
                                width: nodeCircle.width + 10
                                height: width; radius: width / 2
                                color: "transparent"
                                border.width: 2
                                border.color: cachedLayerColor
                                visible: lstate === "active" || lstate === "processing"
                                opacity: 0

                                SequentialAnimation on opacity {
                                    running: lstate === "active" || lstate === "processing"
                                    loops: Animation.Infinite
                                    NumberAnimation { to: 0.5; duration: 600; easing.type: Easing.OutQuad }
                                    NumberAnimation { to: 0;   duration: 600; easing.type: Easing.InQuad }
                                }
                            }
                        }

                        // ── Contenu couche ──
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.topMargin:    compact ? 2 : 4
                            Layout.bottomMargin: compact ? 2 : 4
                            radius: Theme.radiusMedium
                            color: {
                                if (lstate === "active")
                                    return Qt.rgba(cachedLayerColor.r, cachedLayerColor.g, cachedLayerColor.b, 0.08)
                                if (lstate === "processing")
                                    return Qt.rgba(cachedLayerColor.r, cachedLayerColor.g, cachedLayerColor.b, 0.06)
                                return Theme.bgElevated
                            }
                            border.width: lstate === "active" ? 1 : 0
                            border.color: cachedLayerColor

                            Behavior on color { ColorAnimation { duration: Theme.animNormal } }

                            Rectangle {
                                anchors.bottom: parent.bottom
                                anchors.left:   parent.left
                                anchors.right:  parent.right
                                anchors.margins: 1
                                height: 3; radius: 2
                                color: Theme.bgInput
                                visible: !compact

                                Rectangle {
                                    width: parent.width * Math.min(1, elapsed / 3000)
                                    height: parent.height; radius: 2
                                    color: root.durationColor(elapsed)
                                    Behavior on width { NumberAnimation { duration: Theme.animNormal } }
                                    Behavior on color { ColorAnimation { duration: Theme.animNormal } }
                                }
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: compact ? Theme.spacing4 : Theme.spacing8
                                spacing: compact ? Theme.spacing4 : Theme.spacing8

                                ColumnLayout {
                                    Layout.preferredWidth: compact ? 100 : 160
                                    spacing: compact ? 0 : 2

                                    Text {
                                        text: layerInfo.icon + " " + layerInfo.label
                                        font.family: Theme.fontFamily
                                        font.pixelSize: compact ? Theme.fontTiny : Theme.fontSmall
                                        font.weight: Font.Medium
                                        color: Theme.textPrimary
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        visible: !compact
                                        text: layerInfo.desc
                                        font.family: Theme.fontMono
                                        font.pixelSize: 9
                                        color: Theme.textMuted
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                }

                                Text {
                                    text: elapsed > 0 ? elapsed.toFixed(0) + " ms" : "—"
                                    font.family: Theme.fontMono
                                    font.pixelSize: compact ? 9 : Theme.fontSmall
                                    font.weight: Font.Bold
                                    color: root.durationColor(elapsed)
                                    Layout.preferredWidth: compact ? 45 : 60
                                    horizontalAlignment: Text.AlignRight
                                }

                                Rectangle {
                                    visible: !compact
                                    width: stText.implicitWidth + 8
                                    height: 18; radius: Theme.radiusSmall
                                    color: Qt.rgba(cachedLayerColor.r, cachedLayerColor.g, cachedLayerColor.b, 0.2)

                                    Text {
                                        id: stText
                                        anchors.centerIn: parent
                                        text: lstate
                                        font.family: Theme.fontMono
                                        font.pixelSize: 8
                                        font.weight: Font.Bold
                                        color: cachedLayerColor
                                    }
                                }

                                Item {
                                    Layout.fillWidth: true
                                    visible: !compact

                                    Text {
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: ldata.lastEvent || ""
                                        font.family: Theme.fontMono
                                        font.pixelSize: 9
                                        color: Theme.textMuted
                                        elide: Text.ElideRight
                                        width: Math.min(implicitWidth, parent.width)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
