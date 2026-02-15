import QtQuick
import QtQuick.Controls

// ─── Marqueur d'appareil sur plan ────────────────────────

Item {
    id: marker
    width: 36; height: 36

    property string entityId: ""
    property string planId: ""
    property string deviceType: "light"
    property bool isOn: false

    signal moved(real newX, real newY)

    // Halo
    Rectangle {
        anchors.centerIn: parent
        width: 36; height: 36; radius: 18
        color: marker.isOn ? Theme.primary : Theme.surfaceVariant
        opacity: marker.isOn ? 0.35 : 0.2

        Behavior on color { ColorAnimation { duration: 300 } }
        Behavior on opacity { NumberAnimation { duration: 300 } }
    }

    // Cercle principal
    Rectangle {
        anchors.centerIn: parent
        width: 26; height: 26; radius: 13
        color: marker.isOn ? Theme.primary : Theme.card
        border.color: marker.isOn ? Theme.primary : Theme.surfaceVariant
        border.width: 2

        Behavior on color { ColorAnimation { duration: 300 } }

        Text {
            anchors.centerIn: parent
            text: {
                if (marker.deviceType === "light") return "💡"
                if (marker.deviceType === "camera") return "📹"
                if (marker.deviceType === "sensor") return "🌡️"
                if (marker.deviceType === "switch") return "🔌"
                return "📍"
            }
            font.pixelSize: 12
        }
    }

    // Tooltip au survol
    ToolTip {
        parent: marker
        visible: dragArea.containsMouse && !dragArea.drag.active
        text: marker.entityId
        delay: 500
    }

    // Drag & drop
    MouseArea {
        id: dragArea
        anchors.fill: parent
        hoverEnabled: true
        drag.target: marker
        drag.axis: Drag.XAndYAxis
        cursorShape: drag.active ? Qt.ClosedHandCursor : Qt.OpenHandCursor

        onReleased: {
            marker.moved(marker.x, marker.y)
        }
    }

    // Animation d'apparition
    scale: 0.0
    Component.onCompleted: scaleIn.start()
    NumberAnimation { id: scaleIn; target: marker; property: "scale"; to: 1.0; duration: 300; easing.type: Easing.OutBack }
}
