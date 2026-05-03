import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  PipelineView — Pipeline vocal horizontal temps réel
//  5 étapes : Audio → VAD → STT → LLM → TTS
//  Latence par étape, couleur = durée
//  Vert <1s · Jaune <3s · Rouge >3s
// ═══════════════════════════════════════════════════════

Rectangle {
    id: root
    color: "transparent"
    implicitHeight: 140

    // ── Propriété: collapsed (pour mode simple) ──
    property bool collapsed: false

    // ── Latences par étape (ms) ──
    property real audioMs: 0
    property real vadMs:   0
    property real sttMs:   0
    property real llmMs:   0
    property real ttsMs:   0

    // ── État courant du pipeline ──
    property string pipelineState: "Idle"

    // ── Mapping module → stage ──
    readonly property var stages: [
        { id: "audio", label: "Audio",  icon: "🎤", module: "audio_capture" },
        { id: "vad",   label: "VAD",    icon: "📡", module: "vad" },
        { id: "stt",   label: "STT",    icon: "💬", module: "stt" },
        { id: "llm",   label: "LLM",    icon: "⚡", module: "claude" },
        { id: "tts",   label: "TTS",    icon: "🔊", module: "tts" }
    ]

    function latencyForStage(stageId) {
        switch (stageId) {
        case "audio": return root.audioMs
        case "vad":   return root.vadMs
        case "stt":   return root.sttMs
        case "llm":   return root.llmMs
        case "tts":   return root.ttsMs
        default: return 0
        }
    }

    function latencyColor(ms) {
        if (ms <= 0)    return Theme.textMuted
        if (ms < 1000)  return Theme.success
        if (ms < 3000)  return Theme.warning
        return Theme.error
    }

    function stageIsActive(moduleId) {
        var map = {
            "audio_capture": ["DetectingSpeech", "Listening"],
            "vad":           ["DetectingSpeech", "Listening"],
            "stt":           ["Transcribing"],
            "claude":        ["Thinking"],
            "tts":           ["Speaking"]
        }
        var states = map[moduleId] || []
        return states.indexOf(root.pipelineState) !== -1
    }

    function stageIsPast(idx) {
        var activeIdx = -1
        for (var i = stages.length - 1; i >= 0; i--) {
            if (stageIsActive(stages[i].module)) { activeIdx = i; break }
        }
        return activeIdx > idx
    }

    // ── Connexions temps réel ──
    Connections {
        target: typeof pipelineEventBus !== 'undefined' ? pipelineEventBus : null

        function onEventEmitted(event) {
            var mod = event.module || ""
            var ms  = event.elapsed_ms || 0
            if (mod === "audio_capture") root.audioMs = ms
            else if (mod === "vad")      root.vadMs = ms
            else if (mod === "stt")      root.sttMs = ms
            else if (mod === "claude")   root.llmMs = ms
            else if (mod === "tts")      root.ttsMs = ms
        }

        function onInteractionStarted() {
            root.audioMs = 0; root.vadMs = 0
            root.sttMs = 0;   root.llmMs = 0; root.ttsMs = 0
        }
    }

    Connections {
        target: typeof voiceManager !== 'undefined' ? voiceManager : null
        function onStateChanged(newState) {
            var states = ["Idle", "DetectingSpeech", "Listening", "Transcribing", "Thinking", "Speaking"]
            if (newState >= 0 && newState < states.length)
                root.pipelineState = states[newState]
        }
    }

    // ── Layout ──
    visible: !collapsed
    height: collapsed ? 0 : implicitHeight
    Behavior on height { NumberAnimation { duration: Theme.animSlow; easing.type: Easing.InOutQuad } }
    clip: true

    Rectangle {
        anchors.fill: parent
        anchors.margins: Theme.spacing4
        radius: Theme.radiusMedium
        color: Theme.bgElevated

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Theme.spacing8
            spacing: Theme.spacing6

            // ── Header ──
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacing8

                Text {
                    text: "PIPELINE VOCAL"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontTiny
                    font.weight: Font.Bold
                    font.letterSpacing: 1.2
                    color: Theme.textAccent
                }

                Item { Layout.fillWidth: true }

                // FSM State badge
                Rectangle {
                    width: stLabel.implicitWidth + Theme.spacing12
                    height: 20
                    radius: Theme.radiusRound
                    color: Qt.rgba(Theme.stateColor(root.pipelineState).r,
                                   Theme.stateColor(root.pipelineState).g,
                                   Theme.stateColor(root.pipelineState).b, 0.15)
                    border.width: 1
                    border.color: Theme.stateColor(root.pipelineState)
                    Behavior on border.color { ColorAnimation { duration: Theme.animNormal } }

                    Text {
                        id: stLabel
                        anchors.centerIn: parent
                        text: root.pipelineState
                        font.family: Theme.fontMono
                        font.pixelSize: 9
                        font.weight: Font.Medium
                        color: Theme.stateColor(root.pipelineState)
                    }
                }

                // Latence totale
                Text {
                    property real totalMs: root.audioMs + root.vadMs + root.sttMs + root.llmMs + root.ttsMs
                    text: totalMs > 0 ? ("Σ " + totalMs.toFixed(0) + " ms") : ""
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontTiny
                    color: latencyColor(totalMs)
                }
            }

            // ── Pipeline horizontal ──
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                Row {
                    anchors.centerIn: parent
                    spacing: 0

                    Repeater {
                        model: root.stages.length

                        Row {
                            spacing: 0

                            // ── Nœud ──
                            Rectangle {
                                id: stageRect
                                width: 90; height: 72
                                radius: Theme.radiusMedium

                                readonly property bool isActive: root.stageIsActive(root.stages[index].module)
                                readonly property bool isPast: root.stageIsPast(index)
                                readonly property real latMs: root.latencyForStage(root.stages[index].id)
                                readonly property color latColor: root.latencyColor(latMs)

                                color: stageRect.isActive
                                       ? Qt.rgba(Theme.stateColor(root.pipelineState).r,
                                                 Theme.stateColor(root.pipelineState).g,
                                                 Theme.stateColor(root.pipelineState).b, 0.12)
                                       : stageRect.isPast
                                         ? Qt.rgba(Theme.success.r, Theme.success.g, Theme.success.b, 0.06)
                                         : "transparent"
                                border.width: stageRect.isActive ? 2 : 1
                                border.color: stageRect.isActive ? Theme.stateColor(root.pipelineState)
                                            : stageRect.isPast   ? Theme.success
                                            : Theme.border

                                Behavior on border.color { ColorAnimation { duration: Theme.animNormal } }
                                Behavior on color { ColorAnimation { duration: Theme.animNormal } }

                                // Pulse quand actif
                                SequentialAnimation on opacity {
                                    running: stageRect.isActive
                                    loops: Animation.Infinite
                                    NumberAnimation { to: 0.7; duration: 500; easing.type: Easing.InOutSine }
                                    NumberAnimation { to: 1.0; duration: 500; easing.type: Easing.InOutSine }
                                }

                                // Glow overlay
                                Rectangle {
                                    anchors.fill: parent
                                    radius: parent.radius
                                    color: "transparent"
                                    border.width: stageRect.isActive ? 3 : 0
                                    border.color: Qt.rgba(Theme.stateColor(root.pipelineState).r,
                                                          Theme.stateColor(root.pipelineState).g,
                                                          Theme.stateColor(root.pipelineState).b, 0.2)
                                    visible: stageRect.isActive
                                }

                                ColumnLayout {
                                    anchors.centerIn: parent
                                    spacing: 2

                                    Text {
                                        Layout.alignment: Qt.AlignHCenter
                                        text: root.stages[index].icon
                                        font.pixelSize: 18
                                    }

                                    Text {
                                        Layout.alignment: Qt.AlignHCenter
                                        text: root.stages[index].label
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontTiny
                                        font.weight: Font.Medium
                                        color: stageRect.isActive ? Theme.textPrimary : Theme.textSecondary
                                    }

                                    // Latence colorée
                                    Text {
                                        Layout.alignment: Qt.AlignHCenter
                                        text: stageRect.latMs > 0 ? stageRect.latMs.toFixed(0) + " ms" : "—"
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontTiny
                                        font.weight: Font.Bold
                                        color: stageRect.latColor
                                    }
                                }
                            }

                            // ── Flèche ──
                            Item {
                                width: 28; height: 72
                                visible: index < root.stages.length - 1

                                // Barre
                                Rectangle {
                                    anchors.centerIn: parent
                                    width: 18; height: 2; radius: 1
                                    color: root.stageIsPast(index) ? Theme.success
                                         : root.stageIsActive(root.stages[index].module)
                                           ? Theme.stateColor(root.pipelineState)
                                           : Theme.border
                                    Behavior on color { ColorAnimation { duration: Theme.animNormal } }
                                }
                                // Pointe
                                Text {
                                    anchors.centerIn: parent
                                    anchors.horizontalCenterOffset: 6
                                    text: "›"
                                    font.pixelSize: 14
                                    color: root.stageIsPast(index) ? Theme.success
                                         : root.stageIsActive(root.stages[index].module)
                                           ? Theme.stateColor(root.pipelineState)
                                           : Theme.border
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
