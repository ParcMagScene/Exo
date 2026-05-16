import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../core"

// ═══════════════════════════════════════════════════════
//  VoicePipelineView — Visualisation pipeline vocal
//  Audio → DSP → VAD → WakeWord → STT → NLU → LLM → TTS → Playback
//  Transitions FSM, latence par étape, état courant
// ═══════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    // ── FSM State ──
    property string pipelineState: "Idle"
    // Idle, DetectingSpeech, Listening, Transcribing, Thinking, Speaking

    // ── Latencies per stage (ms) ──
    property var stageTimes: ({})
    // Format: { "audio": 0, "dsp": 0, "vad": 0, "wakeword": 0, "stt": 0,
    //           "nlu": 0, "llm": 0, "tts": 0, "playback": 0 }

    // ── Pipeline stages ──
    readonly property var stages: [
        { id: "audio",    label: "Audio",    icon: "🎤", fsmStates: ["DetectingSpeech", "Listening"] },
        { id: "dsp",      label: "DSP",      icon: "🔧", fsmStates: ["Listening"] },
        { id: "vad",      label: "VAD",      icon: "📡", fsmStates: ["DetectingSpeech", "Listening"] },
        { id: "wakeword", label: "WakeWord", icon: "🔔", fsmStates: ["DetectingSpeech"] },
        { id: "stt",      label: "STT",      icon: "💬", fsmStates: ["Transcribing"] },
        { id: "nlu",      label: "NLU",      icon: "🧠", fsmStates: ["Transcribing"] },
        { id: "llm",      label: "LLM",      icon: "⚡", fsmStates: ["Thinking"] },
        { id: "tts",      label: "TTS",      icon: "🔊", fsmStates: ["Speaking"] },
        { id: "playback", label: "Playback", icon: "🔉", fsmStates: ["Speaking"] }
    ]

    // ── PERF FIX: currentActiveIdx calculé une seule fois (O(n)), stageIsPast est O(1) ──
    function stageIsActive(stageId) {
        var s = stages
        for (var i = 0; i < s.length; i++) {
            if (s[i].id === stageId)
                return s[i].fsmStates.indexOf(root.pipelineState) !== -1
        }
        return false
    }

    readonly property int currentActiveIdx: {
        for (var i = stages.length - 1; i >= 0; i--) {
            if (stageIsActive(stages[i].id)) return i
        }
        return -1
    }

    function stageIsPast(stageIdx) { return currentActiveIdx > stageIdx }

    // ── Rafraîchissement depuis pipelineEventBus ──
    Connections {
        target: typeof pipelineEventBus !== 'undefined' ? pipelineEventBus : null

        function onEventEmitted(event) {
            var moduleToStage = {
                "audio_capture": "audio", "preprocessor": "dsp",
                "vad": "vad", "wake_word": "wakeword",
                "stt": "stt", "nlu": "nlu",
                "claude": "llm", "tts": "tts",
                "audio_output": "playback"
            }
            var stageId = moduleToStage[event.module || ""]
            if (stageId) {
                var copy = Object.assign({}, root.stageTimes)
                copy[stageId] = event.elapsed_ms || 0
                root.stageTimes = copy
            }
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

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing8
        spacing: Theme.spacing12

        // ── Header ──
        RowLayout {
            Layout.fillWidth: true

            Text {
                text: SettingsLabels.t("pipeline.vocal")
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontMicro
                font.weight: Font.Bold
                color: Theme.textAccent
                font.letterSpacing: 1.5
            }

            Item { Layout.fillWidth: true }

            // FSM State Badge
            Rectangle {
                width: fsmLabel.implicitWidth + Theme.spacing16
                height: 24
                radius: Theme.radiusRound
                color: Qt.rgba(Theme.stateColor(root.pipelineState).r,
                               Theme.stateColor(root.pipelineState).g,
                               Theme.stateColor(root.pipelineState).b, 0.15)
                border.width: 1
                border.color: Theme.stateColor(root.pipelineState)

                Behavior on border.color { ColorAnimation { duration: Theme.animNormal } }

                Text {
                    id: fsmLabel
                    anchors.centerIn: parent
                    text: root.pipelineState
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontTiny
                    font.weight: Font.Medium
                    color: Theme.stateColor(root.pipelineState)
                }
            }
        }

        // ── Pipeline Flow (horizontal) ──
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 120
            color: Theme.bgElevated
            radius: Theme.radiusMedium

            ScrollView {
                anchors.fill: parent
                anchors.margins: Theme.spacing8
                contentWidth: pipelineRow.implicitWidth
                clip: true

                Row {
                    id: pipelineRow
                    spacing: 0
                    anchors.verticalCenter: parent.verticalCenter

                    Repeater {
                        model: root.stages.length

                        Row {
                            spacing: 0

                            // ── Stage node ──
                            Rectangle {
                                id: stageNode
                                width: 80; height: 80
                                radius: Theme.radiusMedium

                                readonly property bool isActive: root.stageIsActive(root.stages[index].id)
                                readonly property bool isPast: root.stageIsPast(index)
                                readonly property real latMs: root.stageTimes[root.stages[index].id] || 0

                                color: stageNode.isActive ? Qt.rgba(Theme.stateColor(root.pipelineState).r,
                                                          Theme.stateColor(root.pipelineState).g,
                                                          Theme.stateColor(root.pipelineState).b, 0.15)
                                     : stageNode.isPast   ? Qt.rgba(Theme.success.r, Theme.success.g, Theme.success.b, 0.08)
                                     : "transparent"
                                border.width: stageNode.isActive ? 2 : 1
                                border.color: stageNode.isActive ? Theme.stateColor(root.pipelineState)
                                            : stageNode.isPast ? Theme.success
                                            : Theme.border

                                Behavior on border.color { ColorAnimation { duration: Theme.animNormal } }
                                Behavior on color { ColorAnimation { duration: Theme.animNormal } }

                                // Pulse for active
                                SequentialAnimation on border.width {
                                    running: stageNode.isActive
                                    loops: Animation.Infinite
                                    NumberAnimation { to: 3; duration: 600; easing.type: Easing.InOutSine }
                                    NumberAnimation { to: 1; duration: 600; easing.type: Easing.InOutSine }
                                }

                                ColumnLayout {
                                    anchors.centerIn: parent
                                    spacing: 2

                                    Text {
                                        Layout.alignment: Qt.AlignHCenter
                                        text: root.stages[index].icon
                                        font.pixelSize: 20
                                    }

                                    Text {
                                        Layout.alignment: Qt.AlignHCenter
                                        text: root.stages[index].label
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fontTiny
                                        font.weight: Font.Medium
                                        color: stageNode.isActive ? Theme.textPrimary : Theme.textSecondary
                                    }

                                    Text {
                                        Layout.alignment: Qt.AlignHCenter
                                        text: stageNode.latMs > 0 ? stageNode.latMs.toFixed(0) + " ms" : "—"
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontTiny
                                        color: stageNode.latMs > 1000 ? Theme.error
                                             : stageNode.latMs > 500  ? Theme.warning
                                             : Theme.textMuted
                                    }
                                }
                            }

                            // ── Arrow between stages ──
                            Item {
                                width: 24; height: 80
                                visible: index < root.stages.length - 1

                                Rectangle {
                                    anchors.centerIn: parent
                                    width: 16; height: 2
                                    color: root.stageIsPast(index) ? Theme.success
                                         : root.stageIsActive(root.stages[index].id) ? Theme.stateColor(root.pipelineState)
                                         : Theme.border
                                    radius: 1

                                    Behavior on color { ColorAnimation { duration: Theme.animNormal } }
                                }
                                // Arrow head
                                Text {
                                    anchors.centerIn: parent
                                    anchors.horizontalCenterOffset: 4
                                    text: "›"
                                    font.pixelSize: 16
                                    color: root.stageIsPast(index) ? Theme.success
                                         : root.stageIsActive(root.stages[index].id) ? Theme.stateColor(root.pipelineState)
                                         : Theme.border
                                }
                            }
                        }
                    }
                }
            }
        }

        // ── FSM Transition log ──
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.bgElevated
            radius: Theme.radiusMedium

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.spacing8
                spacing: Theme.spacing4

                Text {
                    text: SettingsLabels.t("pipeline.transitions")
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontTiny
                    font.weight: Font.Bold
                    color: Theme.textMuted
                    font.letterSpacing: 1
                }

                ListView {
                    id: fsmLog
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    model: ListModel { id: fsmModel }

                    delegate: RowLayout {
                        width: fsmLog.width
                        height: 22
                        spacing: Theme.spacing8

                        Text {
                            text: model.timestamp
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontTiny
                            color: Theme.textMuted
                            Layout.preferredWidth: 70
                        }

                        Rectangle {
                            width: 6; height: 6; radius: 3
                            color: Theme.stateColor(model.toState)
                        }

                        Text {
                            text: model.fromState + " → " + model.toState
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontTiny
                            color: Theme.textPrimary
                            Layout.fillWidth: true
                        }

                        Text {
                            text: model.duration_ms > 0 ? model.duration_ms + " ms" : ""
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontTiny
                            color: Theme.textMuted
                        }
                    }
                }
            }
        }
    }

    // ── Enregistrement des transitions FSM ──
    property string _prevState: "Idle"
    property real _prevStateTime: 0

    onPipelineStateChanged: {
        var now = Date.now()
        var dur = _prevStateTime > 0 ? (now - _prevStateTime) : 0
        fsmModel.insert(0, {
            timestamp: Qt.formatTime(new Date(), "HH:mm:ss"),
            fromState: _prevState,
            toState: pipelineState,
            duration_ms: Math.round(dur)
        })
        while (fsmModel.count > 100)
            fsmModel.remove(fsmModel.count - 1)
        _prevState = pipelineState
        _prevStateTime = now
    }
}
