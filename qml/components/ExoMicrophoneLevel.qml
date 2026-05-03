import QtQuick
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  ExoMicrophoneLevel — VU mètre micro simplifié
// ═══════════════════════════════════════════════════════

Item {
    id: root

    property real level: 0.0

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing16
        anchors.rightMargin: Theme.spacing16
        spacing: Theme.spacing10

        Text {
            text: "MICRO"
            font.family: Theme.fontMono
            font.pixelSize: Theme.fontTiny
            font.bold: true
            color: Theme.textMuted
            font.letterSpacing: 2
        }

        Rectangle {
            Layout.fillWidth: true
            height: 6
            radius: 3
            color: Theme.bgInput

            Rectangle {
                width: Math.min(1.0, root.level) * parent.width
                height: parent.height
                radius: parent.radius
                color: root.level > 0.8 ? Theme.error
                     : root.level > 0.5 ? Theme.warning
                     : Theme.accent

                Behavior on width { NumberAnimation { duration: 50 } }
                Behavior on color { ColorAnimation { duration: 200 } }
            }
        }
    }
}
