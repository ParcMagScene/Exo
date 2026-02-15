import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ─── Page Caméras ────────────────────────────────────────

Item {
    id: camerasPage

    opacity: 0
    Component.onCompleted: fadeIn.start()
    NumberAnimation { id: fadeIn; target: camerasPage; property: "opacity"; to: 1; duration: 400; easing.type: Easing.OutCubic }

    // Caméras par défaut (seront dynamiques via HA)
    property var cameras: [
        { name: "Entrée", entity_id: "camera.ezwiz_entree", color: "#ef4444" },
        { name: "Jardin", entity_id: "camera.ezwiz_jardin", color: "#f59e0b" },
        { name: "Garage", entity_id: "camera.ezwiz_garage", color: "#22c55e" }
    ]

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        // En-tête
        RowLayout {
            Layout.fillWidth: true

            Text {
                text: "📹 Caméras"
                font.pixelSize: 22
                font.bold: true
                color: Theme.textPrimary
            }

            Item { Layout.fillWidth: true }

            Text {
                text: cameras.length + " caméras"
                font.pixelSize: 13
                color: Theme.textSecondary
            }
        }

        // Grille de caméras
        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: Math.max(1, Math.min(3, Math.floor(parent.width / 400)))
            columnSpacing: 16
            rowSpacing: 16

            Repeater {
                model: cameras

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 280
                    radius: Theme.radiusLarge
                    color: Theme.card
                    clip: true

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 0

                        // Zone vidéo (placeholder)
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            color: "#0d1117"
                            radius: Theme.radiusLarge

                            // Placeholder caméra
                            Column {
                                anchors.centerIn: parent
                                spacing: 8

                                Text {
                                    text: "📹"
                                    font.pixelSize: 48
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    opacity: 0.3
                                }

                                Text {
                                    text: "Flux non disponible"
                                    font.pixelSize: 12
                                    color: Theme.textMuted
                                    anchors.horizontalCenter: parent.horizontalCenter
                                }

                                Text {
                                    text: "Connecter via Home Assistant"
                                    font.pixelSize: 10
                                    color: Theme.textMuted
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    opacity: 0.6
                                }
                            }

                            // Pastille d'état
                            Rectangle {
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.margins: 12
                                width: 10; height: 10; radius: 5
                                color: modelData.color
                            }
                        }

                        // Label de la caméra
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 44
                            color: Theme.card

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 16
                                anchors.rightMargin: 16

                                Text {
                                    text: modelData.name
                                    font.pixelSize: 14
                                    font.bold: true
                                    color: Theme.textPrimary
                                }

                                Item { Layout.fillWidth: true }

                                Text {
                                    text: "En direct"
                                    font.pixelSize: 11
                                    color: Theme.success
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
