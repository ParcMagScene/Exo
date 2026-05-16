import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"
import "../core"

// ═══════════════════════════════════════════════════════════════
//  VisionPageExpert — Fusion Vision panels (Camera, Heatmap, etc.)
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
            title: SettingsLabels.t("vision.title")
            subtitle: SettingsLabels.t("vision.subtitle")
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
                text: SettingsLabels.t("vision.tabCamera")
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
                text: SettingsLabels.t("vision.tabHeatmap")
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
                text: SettingsLabels.t("vision.tabDetections")
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
                text: SettingsLabels.t("vision.tabRisks")
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
                text: SettingsLabels.t("vision.tabEvents")
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

            // Index 0: Camera
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: "#1a1a1a"
                        border.color: Theme.border
                        border.width: 1
                        radius: Theme.radiusSmall

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing12
                            spacing: Theme.spacing8

                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                width: 200
                                height: 150
                                color: Theme.bgSecondary
                                radius: Theme.radiusSmall
                                border.color: Theme.border
                                border.width: 1

                                Text {
                                    anchors.centerIn: parent
                                    text: "📹 Flux caméra"
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.textSecondary
                                }
                            }

                            RowLayout {
                                spacing: Theme.spacing8

                                ExoButton {
                                    text: "▶ Démarrer"
                                }

                                ExoButton {
                                    text: "⏹ Arrêter"
                                }

                                Item { Layout.fillWidth: true }

                                Text {
                                    text: "FPS: 30"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.textSecondary
                                }
                            }

                            Item { Layout.fillHeight: true }
                        }
                    }
                }
            }

            // Index 1: Heatmap
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("vision.heatmapTitle")
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

                        // Gradient heatmap placeholder
                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 1
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: "#1a0000" }
                                GradientStop { position: 0.5; color: "#ff6600" }
                                GradientStop { position: 1.0; color: "#ffff00" }
                            }
                            radius: Theme.radiusSmall - 1

                            Text {
                                anchors.centerIn: parent
                                text: SettingsLabels.t("vision.tabHeatmap")
                                font.pixelSize: Theme.fontLarge
                                color: "#ffffff"
                                opacity: 0.3
                            }
                        }
                    }
                }
            }

            // Index 2: Détections
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("vision.detectedObjects")
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
                            contentHeight: detectionsCol.height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            ColumnLayout {
                                id: detectionsCol
                                width: parent.width
                                spacing: Theme.spacing6

                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 40
                                    color: Theme.bgPrimary
                                    border.color: Theme.info
                                    border.width: 1
                                    radius: Theme.radiusSmall

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: Theme.spacing6
                                        spacing: Theme.spacing8

                                        Text {
                                            text: "👤"
                                            font.pixelSize: Theme.fontSmall
                                        }

                                        Text {
                                            text: SettingsLabels.t("vision.person")
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSmall
                                            color: Theme.textPrimary
                                        }

                                        Item { Layout.fillWidth: true }

                                        Text {
                                            text: "94%"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSmall
                                            color: Theme.info
                                        }
                                    }
                                }

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

                                        Text {
                                            text: "🚗"
                                            font.pixelSize: Theme.fontSmall
                                        }

                                        Text {
                                            text: SettingsLabels.t("vision.car")
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSmall
                                            color: Theme.textPrimary
                                        }

                                        Item { Layout.fillWidth: true }

                                        Text {
                                            text: "87%"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSmall
                                            color: Theme.warning
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

            // Index 3: Risques
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
                                    text: SettingsLabels.t("vision.fire")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.accent
                                }

                                Text {
                                    text: SettingsLabels.t("vision.low")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.success
                                }

                                ExoProgressBar {
                                    value: 0.15
                                    Layout.fillWidth: true
                                    height: 4
                                }
                            }
                        }

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
                                    text: SettingsLabels.t("vision.intrusion")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.accent
                                }

                                Text {
                                    text: SettingsLabels.t("vision.critical")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.error
                                }

                                ExoProgressBar {
                                    value: 0.85
                                    Layout.fillWidth: true
                                    height: 4
                                }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            // Index 4: Événements
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("vision.videoEvents")
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
                            contentHeight: eventsCol.height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            ColumnLayout {
                                id: eventsCol
                                width: parent.width
                                spacing: Theme.spacing6

                                Text {
                                    text: "[08:45:23] Personne détectée — Pièce salon"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.textSecondary
                                }

                                Text {
                                    text: "[08:46:10] Mouvement anormal — Fenêtre"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.warning
                                }

                                Text {
                                    text: "[08:47:45] Voiture détectée — Rue"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.textSecondary
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
