import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"
import "../core"

// ═══════════════════════════════════════════════════════════════
//  SecurityPageExpert — Sécurité Spatiale Complète
//  MODE EXPERT uniquement
// ═══════════════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ExoPanelHeader {
            title: SettingsLabels.t("security.title")
            subtitle: SettingsLabels.t("security.subtitle")
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
                text: SettingsLabels.t("security.tabOverview")
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
                text: SettingsLabels.t("security.tabRisks")
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
                text: SettingsLabels.t("security.tabCausality")
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
                text: SettingsLabels.t("security.tabDecisions")
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

            // Vue globale
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing12

                    Text {
                        text: SettingsLabels.t("security.summary")
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSmall
                        color: Theme.accent
                        font.bold: true
                    }

                    GridLayout {
                        columns: 2
                        columnSpacing: Theme.spacing12
                        rowSpacing: Theme.spacing12
                        Layout.fillWidth: true

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.error
                            border.width: 2
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: "🚨 CRITIQUE"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.error
                                    font.bold: true
                                }

                                Text {
                                    text: "3 risques détectés"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.error
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.warning
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: "⚠️ ALERTE"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.warning
                                }

                                Text {
                                    text: "5 anomalies"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.warning
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.info
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: "ℹ️ INFO"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.info
                                }

                                Text {
                                    text: "12 événements"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.info
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.success
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: "✓ NORMAL"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.success
                                }

                                Text {
                                    text: "3 zones"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.success
                                }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            // Risques
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("security.riskCategories")
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
                            contentHeight: risksCol.height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            ColumnLayout {
                                id: risksCol
                                width: parent.width
                                spacing: Theme.spacing6

                                Repeater {
                                    model: [
                                        {name: "Incendie", risk: "Faible", color: "success"},
                                        {name: "Intrusion", risk: "Critique", color: "error"},
                                        {name: "Électrique", risk: "Moyen", color: "warning"},
                                        {name: "Réseau", risk: "Moyen", color: "warning"},
                                        {name: "Domotique", risk: "Faible", color: "success"}
                                    ]

                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 40
                                        color: Theme.bgPrimary
                                        border.color: modelData.color === "error" ? Theme.error :
                                                      modelData.color === "warning" ? Theme.warning : Theme.success
                                        border.width: 1
                                        radius: Theme.radiusSmall

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: Theme.spacing6
                                            spacing: Theme.spacing8

                                            Text {
                                                text: modelData.name
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontSmall
                                                color: Theme.textPrimary
                                            }

                                            Item { Layout.fillWidth: true }

                                            Text {
                                                text: modelData.risk
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontSmall
                                                color: modelData.color === "error" ? Theme.error :
                                                        modelData.color === "warning" ? Theme.warning : Theme.success
                                                font.bold: true
                                            }
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
                        text: SettingsLabels.t("security.causalGraph")
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
                                text: "Cause primaire: Porte déverrouillée"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSmall
                                color: Theme.error
                                font.bold: true
                            }

                            Column {
                                spacing: Theme.spacing4
                                Layout.fillWidth: true

                                Text {
                                    text: "↓"
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.textSecondary
                                }

                                Text {
                                    text: "Signature thermique détectée"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.warning
                                }

                                Text {
                                    text: "↓"
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.textSecondary
                                }

                                Text {
                                    text: "Possible intrusion"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.error
                                    font.bold: true
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
                        text: SettingsLabels.t("security.recommendations")
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
                            contentHeight: actionsCol.height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            ColumnLayout {
                                id: actionsCol
                                width: parent.width
                                spacing: Theme.spacing6

                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 50
                                    color: Theme.bgPrimary
                                    border.color: Theme.error
                                    border.width: 1
                                    radius: Theme.radiusSmall

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: Theme.spacing6
                                        spacing: Theme.spacing8

                                        ColumnLayout {
                                            spacing: 2

                                            Text {
                                                text: "🚨 Alerter les services de sécurité"
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontSmall
                                                color: Theme.error
                                                font.bold: true
                                            }

                                            Text {
                                                text: SettingsLabels.t("security.priorityCritical")
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontMicro
                                                color: Theme.textSecondary
                                            }
                                        }

                                        Item { Layout.fillWidth: true }

                                        ExoButton {
                                            text: SettingsLabels.t("common.execute")
                                            onClicked: console.log("Execute critical action")
                                        }
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 50
                                    color: Theme.bgPrimary
                                    border.color: Theme.warning
                                    border.width: 1
                                    radius: Theme.radiusSmall

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: Theme.spacing6
                                        spacing: Theme.spacing8

                                        ColumnLayout {
                                            spacing: 2

                                            Text {
                                                text: "⚠️ Fermer accès réseau"
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontSmall
                                                color: Theme.warning
                                            }

                                            Text {
                                                text: "Mitigation réseau"
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontMicro
                                                color: Theme.textSecondary
                                            }
                                        }

                                        Item { Layout.fillWidth: true }

                                        ExoButton {
                                            text: SettingsLabels.t("common.confirm")
                                            onClicked: console.log("Execute mitigation")
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
