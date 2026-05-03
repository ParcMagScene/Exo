import QtQuick
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  ExoPipelineStatus — Indicateur d'état pipeline EXO
//  États : Idle, Listening, Transcribing, Thinking, Speaking, Error
// ═══════════════════════════════════════════════════════

Rectangle {
    id: root

    property string state: "Idle"      // Idle, Listening, Transcribing, Thinking, Speaking, Error
    property real latencyMs: 0

    implicitWidth: row.implicitWidth + Theme.spacing16
    implicitHeight: 32
    radius: Theme.radiusMedium
    color: Theme.bgElevated
    border.width: 1
    border.color: Theme.stateColor(root.state)

    Behavior on border.color { ColorAnimation { duration: Theme.animNormal } }

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: Theme.spacing8

        // Dot animé
        Rectangle {
            id: dot
            width: 8; height: 8; radius: 4
            color: Theme.stateColor(root.state)

            Behavior on color { ColorAnimation { duration: Theme.animNormal } }

            // Pulse pour états actifs
            SequentialAnimation on opacity {
                running: root.state !== "Idle" && root.state !== "Error"
                loops: Animation.Infinite
                NumberAnimation { from: 1.0; to: 0.3; duration: 600; easing.type: Easing.InOutSine }
                NumberAnimation { from: 0.3; to: 1.0; duration: 600; easing.type: Easing.InOutSine }
            }
        }

        // Label état
        Text {
            text: root.state
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontTiny
            font.weight: Font.Medium
            color: Theme.stateColor(root.state)
        }

        // Latence (si > 0)
        Text {
            visible: root.latencyMs > 0
            text: root.latencyMs.toFixed(0) + " ms"
            font.family: Theme.fontMono
            font.pixelSize: Theme.fontTiny
            color: root.latencyMs > 500 ? Theme.warning
                 : root.latencyMs > 1000 ? Theme.error
                 : Theme.textMuted
        }
    }

    // Flash coloré lors du changement d'état
    Rectangle {
        anchors.fill: parent; radius: parent.radius
        color: Theme.stateColor(root.state); opacity: 0

        Behavior on opacity { NumberAnimation { duration: 300 } }

        // On flash via state change
        onColorChanged: { opacity = 0.15; flashTimer.restart() }
        Timer { id: flashTimer; interval: 300; onTriggered: parent.opacity = 0 }
    }
}
