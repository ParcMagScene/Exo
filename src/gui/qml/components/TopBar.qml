import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ─── Barre de titre avec horloge et état EXO ─────────────

Rectangle {
    id: topBar
    color: Theme.surface
    height: Theme.topBarHeight

    property string currentTime: ""
    property string pipelineState: "idle"

    // Bordure inférieure subtile
    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: Theme.surfaceVariant
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        spacing: 16

        // Titre
        Text {
            text: "EXO"
            font.pixelSize: 20
            font.bold: true
            font.letterSpacing: 3
            color: Theme.primary
        }

        // Sous-titre état
        Text {
            text: {
                switch(topBar.pipelineState) {
                    case "idle": return "En veille"
                    case "listening": return "🎤 Écoute..."
                    case "processing": return "⚡ Traitement..."
                    case "responding": return "🔊 Réponse..."
                    default: return ""
                }
            }
            font.pixelSize: 13
            color: Theme.textSecondary

            Behavior on text {
                // Fade effect on state change
                SequentialAnimation {
                    NumberAnimation { target: parent; property: "opacity"; to: 0; duration: 100 }
                    NumberAnimation { target: parent; property: "opacity"; to: 1; duration: 200 }
                }
            }
        }

        Item { Layout.fillWidth: true }

        // Indicateur de connexion HA
        Row {
            spacing: 6
            Rectangle {
                width: 8; height: 8; radius: 4
                color: Theme.success
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: "HA connecté"
                font.pixelSize: 12
                color: Theme.textMuted
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        // Horloge
        Text {
            text: topBar.currentTime
            font.pixelSize: 24
            font.weight: Font.Light
            color: Theme.textPrimary
        }
    }
}
