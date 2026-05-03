import QtQuick
import "../theme"

// ═══════════════════════════════════════════════════════
//  ExoProgressBar — Barre de progression Fluent
// ═══════════════════════════════════════════════════════

Item {
    id: root

    property real value: 0.0          // 0.0–1.0
    property bool indeterminate: false
    property string level: "accent"   // accent, success, warning, error

    implicitWidth: 200
    implicitHeight: Theme.progressHeight

    readonly property color barColor: {
        switch (root.level) {
        case "success": return Theme.success
        case "warning": return Theme.warning
        case "error":   return Theme.error
        default:        return Theme.accent
        }
    }

    // Track
    Rectangle {
        id: track
        anchors.fill: parent
        radius: height / 2
        color: Theme.bgInput
        clip: true

        // Determinate fill
        Rectangle {
            visible: !root.indeterminate
            width: root.value * parent.width
            height: parent.height
            radius: parent.radius
            color: root.barColor

            Behavior on width { NumberAnimation { duration: Theme.animNormal; easing.type: Easing.OutCubic } }
        }

        // Indeterminate slider
        Rectangle {
            id: slider
            visible: root.indeterminate
            width: parent.width * 0.3
            height: parent.height
            radius: parent.radius
            color: root.barColor

            SequentialAnimation on x {
                running: root.indeterminate && root.visible
                loops: Animation.Infinite
                NumberAnimation { from: -slider.width; to: track.width; duration: 1200; easing.type: Easing.InOutQuad }
                PauseAnimation { duration: 200 }
            }
        }
    }
}
