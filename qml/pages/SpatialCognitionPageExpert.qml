import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"
import "../core"

// ═══════════════════════════════════════════════════════════════
//  SpatialCognitionPageExpert — Cognition Spatiale complète
//  MODE EXPERT uniquement
// ═══════════════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ExoPanelHeader {
            title: SettingsLabels.t("cognition.title")
            subtitle: SettingsLabels.t("cognition.subtitle")
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
                text: SettingsLabels.t("cognition.tabSpatial")
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
                text: SettingsLabels.t("cognition.tabDecisions")
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
                text: SettingsLabels.t("cognition.tabExplanations")
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
                text: SettingsLabels.t("cognition.tabPredictions")
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

            // Spatial
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("cognition.spaceRepresentation")
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
                            spacing: Theme.spacing8

                            GridLayout {
                                columns: 2
                                columnSpacing: Theme.spacing8
                                rowSpacing: Theme.spacing8
                                Layout.fillWidth: true

                                Repeater {
                                    model: [
                                        {room: "Salon", entities: 3, risks: 1},
                                        {room: "Cuisine", entities: 5, risks: 2},
                                        {room: "Chambre", entities: 1, risks: 0},
                                        {room: "Entrée", entities: 2, risks: 0}
                                    ]

                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 60
                                        color: Theme.bgPrimary
                                        border.color: modelData.risks > 0 ? Theme.error : Theme.border
                                        border.width: 1
                                        radius: Theme.radiusSmall

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: Theme.spacing6
                                            spacing: 2

                                            Text {
                                                text: modelData.room
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontSmall
                                                color: Theme.textPrimary
                                                font.bold: true
                                            }

                                            Text {
                                                text: modelData.entities + " entités | " + modelData.risks + " risques"
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontMicro
                                                color: Theme.textSecondary
                                            }
                                        }
                                    }
                                }
                            }

                            Item { Layout.fillHeight: true }
                        }
                    }
                }
            }

            // Décisions
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("cognition.decisionTree")
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
                            contentHeight: decisionsCol.height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            ColumnLayout {
                                id: decisionsCol
                                width: parent.width
                                spacing: Theme.spacing6

                                Text {
                                    text: "Détection anomalie"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.accent
                                    font.bold: true
                                }

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

                                        Text {
                                            text: "→ Alerter utilisateur"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSmall
                                            color: Theme.textPrimary
                                        }

                                        Item { Layout.fillWidth: true }

                                        ExoButton {
                                            text: "✓"
                                        }
                                    }
                                }

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

                                        Text {
                                            text: "→ Enregistrer événement"
                                            font.family: Theme.fontMono
                                            font.pixelSize: Theme.fontSmall
                                            color: Theme.textPrimary
                                        }

                                        Item { Layout.fillWidth: true }

                                        ExoButton {
                                            text: "✓"
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

            // Explications
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("cognition.explanations")
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
                            contentHeight: explainCol.height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            ColumnLayout {
                                id: explainCol
                                width: parent.width
                                spacing: Theme.spacing6

                                Text {
                                    text: "La personne dans le salon est immobile depuis > 5 minutes\n→ Probable sommeil ou repos\n→ Pas d'action requise"
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

            // Prédictions
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("cognition.predictions")
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
                            spacing: Theme.spacing12

                            Text {
                                text: "Si la température monte à 28°C dans 10 min:"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSmall
                                color: Theme.accent
                                font.bold: true
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

                                    Text {
                                        text: "→ Augmenter probabilité incendie à 60%"
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontSmall
                                        color: Theme.warning
                                    }

                                    Item { Layout.fillWidth: true }
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
