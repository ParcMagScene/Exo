import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// ═══════════════════════════════════════════════════════════════
//  ObservabilityPage — Fusion Logs + Metrics + Traces + Health
//  MODE EXPERT uniquement
// ═══════════════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Header ──
        ExoPanelHeader {
            title: "OBSERVABILITÉ"
            subtitle: "Logs, Métriques, Traces & Santé des services"
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
                text: "Logs"
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
                text: "Métriques"
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
                text: "Traces"
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
                text: "Santé"
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

            // Index 0: Logs
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    // ── Filtres ──
                    RowLayout {
                        spacing: Theme.spacing8
                        Layout.fillWidth: true

                        TextField {
                            placeholderText: "Filtrer logs..."
                            Layout.fillWidth: true
                            background: Rectangle {
                                color: Theme.bgSecondary
                                border.color: Theme.border
                                border.width: 1
                                radius: Theme.radiusSmall
                            }
                        }

                        ExoButton {
                            text: "Effacer"
                            onClicked: console.log("[Observability] Clearing logs")
                        }
                    }

                    // ── Liste logs ──
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
                            contentHeight: logsCol.height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            ColumnLayout {
                                id: logsCol
                                width: parent.width
                                spacing: Theme.spacing4

                                Text {
                                    text: "[08:45:12] Pipeline vocal initialisé"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.textSecondary
                                    Layout.fillWidth: true
                                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                }

                                Text {
                                    text: "[08:45:15] Service STT connecté (port 8766)"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.textSecondary
                                    Layout.fillWidth: true
                                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                }

                                Text {
                                    text: "[08:45:17] Wakeword server en ligne (port 8770)"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.textSecondary
                                    Layout.fillWidth: true
                                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
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

            // Index 1: Métriques
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing12

                    // ── Grille métriques ──
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: Theme.spacing12
                        rowSpacing: Theme.spacing12

                        // CPU
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 100
                            color: Theme.bgSecondary
                            border.color: Theme.border
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: "CPU"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.accent
                                }

                                Text {
                                    text: "45%"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.textPrimary
                                    Layout.alignment: Qt.AlignCenter
                                    Layout.fillHeight: true
                                }

                                ExoProgressBar {
                                    value: 0.45
                                    Layout.fillWidth: true
                                    height: 8
                                }
                            }
                        }

                        // Mémoire
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 100
                            color: Theme.bgSecondary
                            border.color: Theme.border
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: "Mémoire"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.accent
                                }

                                Text {
                                    text: "1.2 GB"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.textPrimary
                                    Layout.alignment: Qt.AlignCenter
                                    Layout.fillHeight: true
                                }

                                ExoProgressBar {
                                    value: 0.38
                                    Layout.fillWidth: true
                                    height: 8
                                }
                            }
                        }

                        // Latence STT
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 100
                            color: Theme.bgSecondary
                            border.color: Theme.border
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: "Latence STT"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.accent
                                }

                                Text {
                                    text: "2.8s"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.success
                                    Layout.alignment: Qt.AlignCenter
                                    Layout.fillHeight: true
                                }
                            }
                        }

                        // Latence LLM
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 100
                            color: Theme.bgSecondary
                            border.color: Theme.border
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: "Latence LLM"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.accent
                                }

                                Text {
                                    text: "1.5s"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.success
                                    Layout.alignment: Qt.AlignCenter
                                    Layout.fillHeight: true
                                }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            // Index 2: Traces
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: "Timeline du Pipeline"
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

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing8
                            spacing: Theme.spacing4

                            Text {
                                text: "00:00 → Idle"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontMicro
                                color: Theme.textSecondary
                            }

                            Text {
                                text: "00:12 → DetectingSpeech"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontMicro
                                color: Theme.textSecondary
                            }

                            Text {
                                text: "00:45 → Listening"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontMicro
                                color: Theme.textSecondary
                            }

                            Text {
                                text: "02:100 → Transcribing"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontMicro
                                color: Theme.textSecondary
                            }

                            Text {
                                text: "05:850 → Thinking"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontMicro
                                color: Theme.textSecondary
                            }

                            Text {
                                text: "07:450 → Speaking"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontMicro
                                color: Theme.textSecondary
                            }

                            Item { Layout.fillHeight: true }
                        }
                    }
                }
            }

            // Index 3: Santé
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: "État des Services"
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
                            contentHeight: servicesCol.height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            ColumnLayout {
                                id: servicesCol
                                width: parent.width
                                spacing: Theme.spacing8

                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 32
                                    color: Theme.bgPrimary
                                    border.color: Theme.success
                                    border.width: 1
                                    radius: Theme.radiusSmall

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: Theme.spacing8
                                        anchors.rightMargin: Theme.spacing8
                                        spacing: Theme.spacing8

                                        Rectangle {
                                            width: 12
                                            height: 12
                                            radius: 6
                                            color: Theme.success
                                        }

                                        Text {
                                            text: "STT Server"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSmall
                                            color: Theme.textPrimary
                                        }

                                        Item { Layout.fillWidth: true }

                                        Text {
                                            text: "Port 8766"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontMicro
                                            color: Theme.textSecondary
                                        }
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 32
                                    color: Theme.bgPrimary
                                    border.color: Theme.success
                                    border.width: 1
                                    radius: Theme.radiusSmall

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: Theme.spacing8
                                        anchors.rightMargin: Theme.spacing8
                                        spacing: Theme.spacing8

                                        Rectangle {
                                            width: 12
                                            height: 12
                                            radius: 6
                                            color: Theme.success
                                        }

                                        Text {
                                            text: "Wakeword Server"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSmall
                                            color: Theme.textPrimary
                                        }

                                        Item { Layout.fillWidth: true }

                                        Text {
                                            text: "Port 8770"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontMicro
                                            color: Theme.textSecondary
                                        }
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 32
                                    color: Theme.bgPrimary
                                    border.color: Theme.warning
                                    border.width: 1
                                    radius: Theme.radiusSmall

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: Theme.spacing8
                                        anchors.rightMargin: Theme.spacing8
                                        spacing: Theme.spacing8

                                        Rectangle {
                                            width: 12
                                            height: 12
                                            radius: 6
                                            color: Theme.warning
                                        }

                                        Text {
                                            text: "Memory Service"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSmall
                                            color: Theme.textPrimary
                                        }

                                        Item { Layout.fillWidth: true }

                                        Text {
                                            text: "Timeout"
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
        }
    }
}
