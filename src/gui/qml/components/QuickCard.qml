import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ─── Carte rapide (widget dashboard) ─────────────────────

Rectangle {
    id: card
    Layout.fillWidth: true
    Layout.preferredHeight: 100
    radius: Theme.radiusMedium
    color: Theme.card
    border.color: mouseArea.containsMouse ? accentColor : "transparent"
    border.width: mouseArea.containsMouse ? 1 : 0

    property string icon: ""
    property string title: ""
    property string subtitle: ""
    property color accentColor: Theme.primary
    signal clicked()

    Behavior on border.color {
        ColorAnimation { duration: 200 }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16

        // Icône avec fond coloré
        Rectangle {
            Layout.preferredWidth: 52
            Layout.preferredHeight: 52
            radius: Theme.radiusMedium
            color: card.accentColor
            opacity: 0.15

            Text {
                anchors.centerIn: parent
                text: card.icon
                font.pixelSize: 24
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Text {
                text: card.title
                font.pixelSize: 15
                font.bold: true
                color: Theme.textPrimary
            }
            Text {
                text: card.subtitle
                font.pixelSize: 12
                color: Theme.textSecondary
            }
        }

        // Chevron
        Text {
            text: "›"
            font.pixelSize: 24
            color: Theme.textMuted
        }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: card.clicked()
    }

    scale: mouseArea.pressed ? 0.97 : 1.0
    Behavior on scale {
        NumberAnimation { duration: 100; easing.type: Easing.OutCubic }
    }
}
