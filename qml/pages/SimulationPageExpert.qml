import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"
import "../core"

// ═══════════════════════════════════════════════════════════════
//  SimulationPageExpert — Fusion Simulation panels
//  MODE EXPERT uniquement
// ═══════════════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ExoPanelHeader {
            title: SettingsLabels.t("simulation.title")
            subtitle: SettingsLabels.t("simulation.subtitle")
        }

        TabBar {
            id: tabBar
            Layout.fillWidth: true
            background: Rectangle {
                color: Theme.bgSecondary
                border.color: Theme.border
                border.width: 1
            }

            TabButton {
                text: SettingsLabels.t("simulation.tabScenarios")
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
                text: SettingsLabels.t("simulation.tabPropagation")
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
                text: SettingsLabels.t("simulation.tabTimeline")
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
                text: SettingsLabels.t("simulation.tabCausality")
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

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabBar.currentIndex

            // Scénarios
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

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
                            spacing: Theme.spacing6

                            Text {
                                text: SettingsLabels.t("simulation.scenarios")
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSmall
                                color: Theme.accent
                            }

                            Repeater {
                                model: ["Incendie cuisine", "Intrusion fenêtre", "Fuite eau salle bain"]

                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 40
                                    color: Theme.bgPrimary
                                    border.color: Theme.border
                                    border.width: 1
                                    radius: Theme.radiusSmall

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: Theme.spacing6
                                        spacing: Theme.spacing8

                                        Text {
                                            text: modelData
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSmall
                                            color: Theme.textPrimary
                                        }

                                        Item { Layout.fillWidth: true }

                                        ExoButton {
                                            text: SettingsLabels.t("common.launch")
                                            onClicked: console.log("Scenario:", modelData)
                                        }
                                    }
                                }
                            }

                            Item { Layout.fillHeight: true }
                        }
                    }
                }
            }

            // Propagation
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("simulation.propagation")
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

                        // Placeholder animation
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing8
                            spacing: Theme.spacing8

                            Text {
                                text: SettingsLabels.t("simulation.overlay")
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSmall
                                color: Theme.textSecondary
                                Layout.alignment: Qt.AlignHCenter
                                Layout.topMargin: Theme.spacing32
                            }

                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                width: 150
                                height: 150
                                radius: 75
                                gradient: Gradient {
                                    GradientStop { position: 0.0; color: "#ff0000" }
                                    GradientStop { position: 1.0; color: "#00000000" }
                                }
                            }

                            Item { Layout.fillHeight: true }
                        }
                    }
                }
            }

            // Timeline
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("simulation.timeline")
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
                            contentHeight: timelineCol.height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            ColumnLayout {
                                id: timelineCol
                                width: parent.width
                                spacing: Theme.spacing6

                                Repeater {
                                    model: [
                                        {time: "00:00s", event: "Détection foyer"},
                                        {time: "00:30s", event: "Propagation cuisine"},
                                        {time: "01:15s", event: "Atteinte salon"},
                                        {time: "02:00s", event: "Activation sprinklers"}
                                    ]

                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 40
                                        color: Theme.bgPrimary
                                        border.color: Theme.border
                                        border.width: 1
                                        radius: Theme.radiusSmall

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: Theme.spacing6
                                            spacing: Theme.spacing8

                                            Text {
                                                text: modelData.time
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontSmall
                                                color: Theme.accent
                                            }

                                            Text {
                                                text: modelData.event
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontSmall
                                                color: Theme.textPrimary
                                            }

                                            Item { Layout.fillWidth: true }
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

            // Causalité
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("simulation.causalGraph")
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
                            anchors.margins: Theme.spacing12
                            spacing: Theme.spacing16

                            Text {
                                text: SettingsLabels.t("simulation.rootCause")
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSmall
                                color: Theme.accent
                            }

                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                width: 150
                                height: 40
                                color: Theme.bgPrimary
                                border.color: Theme.error
                                border.width: 2
                                radius: Theme.radiusSmall

                                Text {
                                    anchors.centerIn: parent
                                    text: "Flamme cuisinière"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.error
                                }
                            }

                            Text {
                                text: "↓"
                                font.pixelSize: Theme.fontLarge
                                color: Theme.textSecondary
                                Layout.alignment: Qt.AlignHCenter
                            }

                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                width: 150
                                height: 40
                                color: Theme.bgPrimary
                                border.color: Theme.warning
                                border.width: 1
                                radius: Theme.radiusSmall

                                Text {
                                    anchors.centerIn: parent
                                    text: "Fumée détectée"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.warning
                                }
                            }

                            Item { Layout.fillHeight: true }
                        }
                    }
                }
            }
        }
    }
}
