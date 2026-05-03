import QtQuick
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  ExoStatusIndicator — Indicateur d'état pipeline
// ═══════════════════════════════════════════════════════

Item {
    id: root

    property string currentStatus: "Idle"

    readonly property color statusColor: Theme.stateColor(currentStatus)

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing16
        anchors.rightMargin: Theme.spacing16
        anchors.topMargin: Theme.spacing12
        anchors.bottomMargin: Theme.spacing12
        spacing: Theme.spacing6

        Text {
            text: "ÉTAT"
            font.family: Theme.fontMono
            font.pixelSize: Theme.fontTiny
            font.bold: true
            color: Theme.textMuted
            font.letterSpacing: 2
        }

        RowLayout {
            spacing: Theme.spacing10

            Rectangle {
                width: 10
                height: 10
                radius: 5
                color: root.statusColor

                Behavior on color { ColorAnimation { duration: Theme.animNormal } }

                SequentialAnimation on opacity {
                    running: root.currentStatus === "Listening" ||
                             root.currentStatus === "Thinking"
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.3; duration: 600; easing.type: Easing.InOutQuad }
                    NumberAnimation { to: 1.0; duration: 600; easing.type: Easing.InOutQuad }
                }
            }

            Text {
                text: root.currentStatus
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontBody
                color: root.statusColor
            }
        }
    }
}
