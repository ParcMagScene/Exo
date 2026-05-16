import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"
import "../core"

// ═══════════════════════════════════════════════════════════════
//  PipelinePageExpert — Fusion Voice Pipeline + Cognitive Timeline
//  MODE EXPERT uniquement
// ═══════════════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    property string pipelineState: "Idle"
    property real micLevel: 0.0
    property string partialTranscript: ""

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Header ──
        ExoPanelHeader {
            title: SettingsLabels.t("pipeline.titleExpert")
            subtitle: SettingsLabels.t("pipeline.subtitleExpert")
        }

        // ── Onglets ──
        TabBar {
            id: tabBar
            Layout.fillWidth: true
            background: Rectangle {
                color: Theme.bgSecondary
                border.color: Theme.border
                border.width: 1
            }

            TabButton {
                text: SettingsLabels.t("pipeline.tabVoice")
                contentItem: Text {
                    text: parent.text
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSmall
                    color: parent.checked ? Theme.accent : Theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
            TabButton {
                text: SettingsLabels.t("pipeline.tabCognitive")
                contentItem: Text {
                    text: parent.text
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSmall
                    color: parent.checked ? Theme.accent : Theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
            TabButton {
                text: SettingsLabels.t("pipeline.tabMetrics")
                contentItem: Text {
                    text: parent.text
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSmall
                    color: parent.checked ? Theme.accent : Theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }

        // ── Contenu onglets ──
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabBar.currentIndex

            // Index 0: Voice Pipeline
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing12

                    // ── État du pipeline ──
                    Rectangle {
                        Layout.fillWidth: true
                        height: 60
                        color: Theme.bgSecondary
                        border.color: Theme.border
                        border.width: 1
                        radius: Theme.radiusSmall

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing8
                            spacing: Theme.spacing16

                            Text {
                                text: SettingsLabels.t("common.state")
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSmall
                                color: Theme.accent
                            }

                            Text {
                                text: root.pipelineState
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontLarge
                                color: root.pipelineState === "Idle" ? Theme.success :
                                       root.pipelineState === "Thinking" ? Theme.warning :
                                       root.pipelineState === "Speaking" ? Theme.info : Theme.accent
                                font.weight: Font.Bold
                            }

                            Item { Layout.fillWidth: true }

                            Rectangle {
                                width: 24
                                height: 24
                                radius: 12
                                color: root.pipelineState === "Idle" ? Theme.success :
                                       root.pipelineState === "Thinking" ? Theme.warning :
                                       root.pipelineState === "Speaking" ? Theme.info : Theme.accent

                                SequentialAnimation {
                                    id: pulseAnim
                                    loops: Animation.Infinite
                                    running: root.pipelineState !== "Idle"

                                    PropertyAnimation {
                                        target: pulseRect
                                        property: "opacity"
                                        from: 1.0
                                        to: 0.3
                                        duration: 600
                                    }
                                    PropertyAnimation {
                                        target: pulseRect
                                        property: "opacity"
                                        from: 0.3
                                        to: 1.0
                                        duration: 600
                                    }
                                }

                                Rectangle {
                                    id: pulseRect
                                    anchors.fill: parent
                                    radius: parent.radius
                                    color: parent.color
                                }
                            }
                        }
                    }

                    // ── Waveform ──
                    Text {
                        text: SettingsLabels.t("pipeline.audio")
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSmall
                        color: Theme.accent
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 80
                        color: Theme.bgSecondary
                        border.color: Theme.border
                        border.width: 1
                        radius: Theme.radiusSmall

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing8
                            spacing: Theme.spacing4

                            // Waveform bars
                            Repeater {
                                model: 32

                                Rectangle {
                                    width: 2
                                    height: Math.random() * 50 + 5
                                    color: root.pipelineState !== "Idle" ? Theme.accent : Theme.border
                                    radius: 1

                                    NumberAnimation {
                                        id: barAnim
                                        target: parent
                                        property: "height"
                                        from: 5
                                        to: Math.random() * 50 + 5
                                        duration: 100
                                        running: root.pipelineState !== "Idle"
                                        loops: Animation.Infinite
                                    }
                                }
                            }
                        }
                    }

                    // ── Mic level ──
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing8

                        Text {
                            text: SettingsLabels.t("pipeline.micLevel")
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSmall
                            color: Theme.textSecondary
                        }

                        ExoProgressBar {
                            value: root.micLevel
                            Layout.fillWidth: true
                            height: 8
                        }

                        Text {
                            text: Math.round(root.micLevel * 100) + "%"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSmall
                            color: Theme.textSecondary
                            Layout.preferredWidth: 40
                        }
                    }

                    // ── Transcript partial ──
                    Text {
                        text: SettingsLabels.t("pipeline.partialTranscript")
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSmall
                        color: Theme.accent
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 60
                        color: Theme.bgSecondary
                        border.color: Theme.border
                        border.width: 1
                        radius: Theme.radiusSmall

                        Text {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing8
                            text: root.partialTranscript || "(vide)"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSmall
                            color: root.partialTranscript ? Theme.textPrimary : Theme.textSecondary
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            verticalAlignment: Text.AlignTop
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            // Index 1: Cognitive Timeline
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("pipeline.cognitiveSteps")
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSmall
                        color: Theme.accent
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: Theme.bgSecondary
                        border.color: Theme.border
                        border.width: 1
                        radius: Theme.radiusSmall

                        Flickable {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing8
                            contentWidth: width
                            contentHeight: stepsCol.height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            ColumnLayout {
                                id: stepsCol
                                width: parent.width
                                spacing: Theme.spacing6

                                // Step 1
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 40
                                    color: Theme.bgPrimary
                                    border.color: Theme.success
                                    border.width: 1
                                    radius: Theme.radiusSmall

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: Theme.spacing6
                                        spacing: Theme.spacing8

                                        Rectangle {
                                            width: 8
                                            height: 8
                                            radius: 4
                                            color: Theme.success
                                        }

                                        Text {
                                            text: "1. Détection VAD"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSmall
                                            color: Theme.textPrimary
                                        }

                                        Item { Layout.fillWidth: true }

                                        Text {
                                            text: "45ms"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontMicro
                                            color: Theme.textSecondary
                                        }
                                    }
                                }

                                // Step 2
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 40
                                    color: Theme.bgPrimary
                                    border.color: Theme.success
                                    border.width: 1
                                    radius: Theme.radiusSmall

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: Theme.spacing6
                                        spacing: Theme.spacing8

                                        Rectangle {
                                            width: 8
                                            height: 8
                                            radius: 4
                                            color: Theme.success
                                        }

                                        Text {
                                            text: "2. Transcription STT"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSmall
                                            color: Theme.textPrimary
                                        }

                                        Item { Layout.fillWidth: true }

                                        Text {
                                            text: "2.8s"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontMicro
                                            color: Theme.textSecondary
                                        }
                                    }
                                }

                                // Step 3
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 40
                                    color: Theme.bgPrimary
                                    border.color: Theme.warning
                                    border.width: 1
                                    radius: Theme.radiusSmall

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: Theme.spacing6
                                        spacing: Theme.spacing8

                                        Rectangle {
                                            width: 8
                                            height: 8
                                            radius: 4
                                            color: Theme.warning
                                        }

                                        Text {
                                            text: "3. Appel LLM"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSmall
                                            color: Theme.textPrimary
                                        }

                                        Item { Layout.fillWidth: true }

                                        Text {
                                            text: "1.5s (en cours)"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontMicro
                                            color: Theme.textSecondary
                                        }
                                    }
                                }

                                // Step 4
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 40
                                    color: Theme.bgPrimary
                                    border.color: Theme.textSecondary
                                    border.width: 1
                                    radius: Theme.radiusSmall
                                    opacity: 0.5

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: Theme.spacing6
                                        spacing: Theme.spacing8

                                        Rectangle {
                                            width: 8
                                            height: 8
                                            radius: 4
                                            color: Theme.textSecondary
                                        }

                                        Text {
                                            text: "4. Génération TTS"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSmall
                                            color: Theme.textSecondary
                                        }

                                        Item { Layout.fillWidth: true }

                                        Text {
                                            text: SettingsLabels.t("common.waiting")
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontMicro
                                            color: Theme.textSecondary
                                        }
                                    }
                                }

                                Item { Layout.fillHeight: true }
                            }

                            ScrollBar.vertical: ScrollBar {
                                policy: ScrollBar.AsNeeded
                            }
                        }
                    }
                }
            }

            // Index 2: Métriques
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing12

                    GridLayout {
                        columns: 2
                        columnSpacing: Theme.spacing12
                        rowSpacing: Theme.spacing12
                        Layout.fillWidth: true

                        // VAD latency
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.border
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: SettingsLabels.t("observability.latencyVAD")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.accent
                                }

                                Text {
                                    text: "45ms"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.success
                                }
                            }
                        }

                        // STT latency
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.border
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: SettingsLabels.t("observability.latencySTT")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.accent
                                }

                                Text {
                                    text: "2.8s"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.success
                                }
                            }
                        }

                        // LLM latency
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.border
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: SettingsLabels.t("observability.latencyLLM")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.accent
                                }

                                Text {
                                    text: "1.5s"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.success
                                }
                            }
                        }

                        // TTS latency
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.border
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: SettingsLabels.t("observability.latencyTTS")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.accent
                                }

                                Text {
                                    text: "750ms"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.success
                                }
                            }
                        }

                        // Total
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.accent
                            border.width: 2
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: SettingsLabels.t("common.total")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.accent
                                    font.bold: true
                                }

                                Text {
                                    text: "7.1s"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.accent
                                    font.bold: true
                                }
                            }
                        }

                        Item { Layout.fillWidth: true }
                    }

                    Item { Layout.fillHeight: true }
                }
            }
        }
    }
}
