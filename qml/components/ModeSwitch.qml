import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  ModeSwitch — Toggle Expert / Simple
// ═══════════════════════════════════════════════════════

Rectangle {
    id: root
    width: 140
    height: 28
    radius: Theme.radiusMedium
    color: Theme.bgElevated

    property bool expertMode: false
    signal modeChanged(bool isExpert)

    RowLayout {
        anchors.fill: parent
        anchors.margins: 2
        spacing: 0

        // Simple button
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.radiusSmall
            color: !root.expertMode ? Theme.accent : "transparent"

            Behavior on color { ColorAnimation { duration: Theme.animFast } }

            Text {
                anchors.centerIn: parent
                text: "Simple"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontTiny
                font.weight: !root.expertMode ? Font.Bold : Font.Normal
                color: !root.expertMode ? "#FFFFFF" : Theme.textMuted
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.expertMode = false
                    root.modeChanged(false)
                }
            }
        }

        // Expert button
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.radiusSmall
            color: root.expertMode ? Theme.accent : "transparent"

            Behavior on color { ColorAnimation { duration: Theme.animFast } }

            Text {
                anchors.centerIn: parent
                text: "Expert"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontTiny
                font.weight: root.expertMode ? Font.Bold : Font.Normal
                color: root.expertMode ? "#FFFFFF" : Theme.textMuted
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.expertMode = true
                    root.modeChanged(true)
                }
            }
        }
    }
}
