import QtQuick
import QtQuick.Controls

// ─── Bouton de navigation (dans le NavRail) ──────────────

Rectangle {
    id: navBtn
    width: 56
    height: 56
    radius: Theme.radiusMedium
    color: active ? Theme.primary : (hoverArea.containsMouse ? Theme.cardHover : "transparent")

    property string icon: ""
    property string label: ""
    property bool active: false
    signal clicked()

    Behavior on color {
        ColorAnimation { duration: 200; easing.type: Easing.OutCubic }
    }

    Column {
        anchors.centerIn: parent
        spacing: 2

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: navBtn.icon
            font.pixelSize: 20
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: navBtn.label
            font.pixelSize: 9
            color: navBtn.active ? "#ffffff" : Theme.textSecondary
            font.weight: navBtn.active ? Font.Bold : Font.Normal
        }
    }

    MouseArea {
        id: hoverArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: navBtn.clicked()
    }

    // Animation d'entrée
    scale: hoverArea.pressed ? 0.92 : 1.0
    Behavior on scale {
        NumberAnimation { duration: 100; easing.type: Easing.OutCubic }
    }
}
