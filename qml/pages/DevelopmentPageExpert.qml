import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// ═══════════════════════════════════════════════════════════════
//  DevelopmentPageExpert — Services, Stability & Debug
//  MODE EXPERT uniquement
// ═══════════════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    property int readyCount: 14
    property int failedCount: 1
    property int degradedCount: 2
    property int totalCount: 17

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ExoPanelHeader {
            title: "DÉVELOPPEMENT"
            subtitle: "Services, Stabilité & Configuration"
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
                text: "Services"
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
                text: "Stabilité"
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
                text: "Config"
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
                text: "Debug"
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

            // Services
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing12

                    // Status summary
                    GridLayout {
                        columns: 2
                        columnSpacing: Theme.spacing12
                        rowSpacing: Theme.spacing12
                        Layout.fillWidth: true

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.success
                            border.width: 2
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: "PRÊTS"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.success
                                    font.bold: true
                                }

                                Text {
                                    text: root.readyCount + "/" + root.totalCount
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.success
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.error
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: "ÉCHOUÉS"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.error
                                }

                                Text {
                                    text: root.failedCount
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.error
                                    font.bold: true
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
                                    text: "DÉGRADÉS"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.warning
                                }

                                Text {
                                    text: root.degradedCount
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
                            border.color: Theme.border
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: "TOTAL"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.accent
                                    font.bold: true
                                }

                                Text {
                                    text: root.totalCount
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.textPrimary
                                }
                            }
                        }
                    }

                    // Services list
                    Text {
                        text: "État détaillé"
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
                                spacing: Theme.spacing6

                                Repeater {
                                    model: [
                                        {name: "STT Server", port: "8766", status: "ready"},
                                        {name: "TTS Server", port: "8767", status: "ready"},
                                        {name: "VAD Server", port: "8768", status: "ready"},
                                        {name: "Wakeword Server", port: "8770", status: "failed"},
                                        {name: "Memory Service", port: "8771", status: "degraded"}
                                    ]

                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 36
                                        color: Theme.bgPrimary
                                        border.color: modelData.status === "ready" ? Theme.success :
                                                      modelData.status === "failed" ? Theme.error : Theme.warning
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
                                                color: modelData.status === "ready" ? Theme.success :
                                                        modelData.status === "failed" ? Theme.error : Theme.warning
                                            }

                                            Text {
                                                text: modelData.name
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontSmall
                                                color: Theme.textPrimary
                                            }

                                            Item { Layout.fillWidth: true }

                                            Text {
                                                text: modelData.port
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontMicro
                                                color: Theme.textSecondary
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

            // Stabilité
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: "Tests de stabilité"
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

                            ExoButton {
                                Layout.fillWidth: true
                                text: "▶ Stress Test (100 requêtes)"
                                onClicked: console.log("Starting stress test")
                            }

                            ExoButton {
                                Layout.fillWidth: true
                                text: "▶ Memory Leak Check"
                                onClicked: console.log("Starting memory check")
                            }

                            ExoButton {
                                Layout.fillWidth: true
                                text: "▶ Reconnection Test"
                                onClicked: console.log("Starting reconnection test")
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 100
                                color: Theme.bgPrimary
                                border.color: Theme.border
                                border.width: 1
                                radius: Theme.radiusSmall

                                Text {
                                    anchors.centerIn: parent
                                    text: "Résultats du dernier test:\n✓ PASSED (12.3s)"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.success
                                    textFormat: Text.PlainText
                                    horizontalAlignment: Text.AlignHCenter
                                }
                            }

                            Item { Layout.fillHeight: true }
                        }
                    }
                }
            }

            // Configuration
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: "Fichier de configuration"
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
                            contentHeight: configCol.height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            ColumnLayout {
                                id: configCol
                                width: parent.width
                                spacing: Theme.spacing4

                                Text {
                                    text: "[Audio]"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.accent
                                }

                                Text {
                                    text: "backend=qt"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.textSecondary
                                }

                                Text {
                                    text: "agc_enabled=true"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.textSecondary
                                }

                                Text {
                                    text: ""
                                    font.pixelSize: Theme.fontMicro
                                }

                                Text {
                                    text: "[UI]"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.accent
                                }

                                Text {
                                    text: "expert_mode=true"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.success
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

            // Debug
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: "Outils de débogage"
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

                            ExoButton {
                                Layout.fillWidth: true
                                text: "📋 Dump Memory Profile"
                                onClicked: console.log("Dumping memory profile")
                            }

                            ExoButton {
                                Layout.fillWidth: true
                                text: "📊 Export Metrics"
                                onClicked: console.log("Exporting metrics")
                            }

                            ExoButton {
                                Layout.fillWidth: true
                                text: "🔧 Reset Cache"
                                onClicked: console.log("Resetting cache")
                            }

                            ExoButton {
                                Layout.fillWidth: true
                                text: "🔄 Restart All Services"
                                onClicked: console.log("Restarting services")
                            }

                            Item { Layout.fillHeight: true }
                        }
                    }
                }
            }
        }
    }
}
