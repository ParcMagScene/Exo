import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

// ─── Page Domotique ──────────────────────────────────────

Item {
    id: automationPage

    opacity: 0
    Component.onCompleted: fadeIn.start()
    NumberAnimation { id: fadeIn; target: automationPage; property: "opacity"; to: 1; duration: 400; easing.type: Easing.OutCubic }

    // Pièces et appareils (seront dynamiques via HA)
    property var rooms: [
        {
            name: "Salon", icon: "🛋️",
            devices: [
                { name: "Lumière Hue", entity_id: "light.salon_hue", type: "light", state: "on" },
                { name: "TV Samsung", entity_id: "media_player.samsung_tv", type: "media", state: "off" },
                { name: "Soundbar", entity_id: "media_player.samsung_soundbar", type: "media", state: "off" }
            ]
        },
        {
            name: "Chambre", icon: "🛏️",
            devices: [
                { name: "Lumière Hue", entity_id: "light.chambre_hue", type: "light", state: "off" },
                { name: "Veilleuse IKEA", entity_id: "light.chambre_ikea", type: "light", state: "off" }
            ]
        },
        {
            name: "Cuisine", icon: "🍳",
            devices: [
                { name: "Lumière IKEA", entity_id: "light.cuisine_ikea", type: "light", state: "on" }
            ]
        },
        {
            name: "Salle de bain", icon: "🚿",
            devices: [
                { name: "Lumière Hue", entity_id: "light.salle_bain_hue", type: "light", state: "off" }
            ]
        }
    ]

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        // En-tête
        Text {
            text: "💡 Domotique"
            font.pixelSize: 22
            font.bold: true
            color: Theme.textPrimary
        }

        // Scènes rapides
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Repeater {
                model: [
                    { label: "Tout éteindre", icon: "🌙", color: "#6366f1" },
                    { label: "Mode film", icon: "🎬", color: "#8b5cf6" },
                    { label: "Mode travail", icon: "💻", color: "#3b82f6" },
                    { label: "Mode nuit", icon: "😴", color: "#1e3a5f" }
                ]

                Rectangle {
                    Layout.fillWidth: true
                    height: 48
                    radius: Theme.radiusMedium
                    color: modelData.color
                    opacity: sceneArea.containsMouse ? 1.0 : 0.7

                    Behavior on opacity { NumberAnimation { duration: 150 } }

                    Row {
                        anchors.centerIn: parent
                        spacing: 8
                        Text { text: modelData.icon; font.pixelSize: 16 }
                        Text { text: modelData.label; font.pixelSize: 13; color: "#fff"; font.weight: Font.Medium }
                    }

                    MouseArea {
                        id: sceneArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: console.log("Scene:", modelData.label)
                    }

                    scale: sceneArea.pressed ? 0.95 : 1.0
                    Behavior on scale { NumberAnimation { duration: 100 } }
                }
            }
        }

        // Liste des pièces
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ColumnLayout {
                width: parent.width
                spacing: 16

                Repeater {
                    model: rooms

                    // Carte de pièce
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: roomContent.implicitHeight + 32
                        radius: Theme.radiusLarge
                        color: Theme.card

                        ColumnLayout {
                            id: roomContent
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 12

                            // En-tête pièce
                            RowLayout {
                                Layout.fillWidth: true

                                Text {
                                    text: modelData.icon + " " + modelData.name
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: Theme.textPrimary
                                }

                                Item { Layout.fillWidth: true }

                                Text {
                                    text: modelData.devices.length + " appareils"
                                    font.pixelSize: 12
                                    color: Theme.textMuted
                                }
                            }

                            // Appareils
                            Flow {
                                Layout.fillWidth: true
                                spacing: 8

                                Repeater {
                                    model: modelData.devices

                                    Rectangle {
                                        width: deviceRow.implicitWidth + 24
                                        height: 40
                                        radius: 20
                                        color: modelData.state === "on" ? Theme.primary : Theme.surfaceVariant
                                        opacity: modelData.state === "on" ? 1.0 : 0.6

                                        Behavior on color { ColorAnimation { duration: 200 } }
                                        Behavior on opacity { NumberAnimation { duration: 200 } }

                                        Row {
                                            id: deviceRow
                                            anchors.centerIn: parent
                                            spacing: 8

                                            Text {
                                                text: modelData.type === "light" ? "💡" : "📺"
                                                font.pixelSize: 14
                                                anchors.verticalCenter: parent.verticalCenter
                                            }

                                            Text {
                                                text: modelData.name
                                                font.pixelSize: 12
                                                color: modelData.state === "on" ? "#fff" : Theme.textSecondary
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                var newState = modelData.state === "on" ? "off" : "on"
                                                Bridge.callService(modelData.entity_id, newState)
                                            }
                                        }

                                        scale: deviceArea2.pressed ? 0.93 : 1.0
                                        Behavior on scale { NumberAnimation { duration: 100 } }
                                        MouseArea { id: deviceArea2; anchors.fill: parent; visible: false }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
