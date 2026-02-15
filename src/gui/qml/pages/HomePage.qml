import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

// ─── Page d'accueil : Orbe + Dashboard ───────────────────

Item {
    id: homePage

    property string pipelineState: "idle"
    property string lastTranscript: ""
    property string lastResponse: ""

    // Animation d'entrée
    opacity: 0
    Component.onCompleted: fadeIn.start()
    NumberAnimation { id: fadeIn; target: homePage; property: "opacity"; to: 1; duration: 400; easing.type: Easing.OutCubic }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 24

        // ─── Ligne supérieure : Orbe + Info ──────────────

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 240
            spacing: 32

            // Orbe d'état
            Item {
                Layout.preferredWidth: 240
                Layout.preferredHeight: 240

                StatusOrb {
                    anchors.centerIn: parent
                    state: homePage.pipelineState
                }
            }

            // Carte de transcription
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: Theme.radiusLarge
                color: Theme.card

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 12

                    Text {
                        text: "💬 Conversation"
                        font.pixelSize: 16
                        font.bold: true
                        color: Theme.textPrimary
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: Theme.surfaceVariant
                    }

                    // Dernier transcript
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            text: "Vous :"
                            font.pixelSize: 11
                            color: Theme.textMuted
                            visible: homePage.lastTranscript !== ""
                        }
                        Text {
                            text: homePage.lastTranscript || "Dites « Exo » pour commencer..."
                            font.pixelSize: 14
                            color: homePage.lastTranscript ? Theme.textPrimary : Theme.textMuted
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                            font.italic: homePage.lastTranscript === ""
                        }
                    }

                    // Dernière réponse
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        visible: homePage.lastResponse !== ""

                        Text {
                            text: "EXO :"
                            font.pixelSize: 11
                            color: Theme.primary
                        }
                        Text {
                            text: homePage.lastResponse
                            font.pixelSize: 14
                            color: Theme.textPrimary
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }
        }

        // ─── Widgets rapides ─────────────────────────────

        Text {
            text: "Raccourcis"
            font.pixelSize: 18
            font.bold: true
            color: Theme.textPrimary
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: Math.max(2, Math.floor(parent.width / 250))
            columnSpacing: 16
            rowSpacing: 16

            // Carte Lumières
            QuickCard {
                icon: "💡"
                title: "Lumières"
                subtitle: "Salon, Chambre, Cuisine"
                accentColor: Theme.warning
                onClicked: root.currentPage = "automation"
            }

            // Carte Caméras
            QuickCard {
                icon: "📹"
                title: "Caméras"
                subtitle: "3 caméras actives"
                accentColor: Theme.error
                onClicked: root.currentPage = "cameras"
            }

            // Carte Plans
            QuickCard {
                icon: "🗺️"
                title: "Plans"
                subtitle: "Voir les plans de la maison"
                accentColor: Theme.accent
                onClicked: root.currentPage = "floorplan"
            }

            // Carte Température
            QuickCard {
                icon: "🌡️"
                title: "Température"
                subtitle: "22°C — Salon"
                accentColor: Theme.success
            }
        }
    }
}
