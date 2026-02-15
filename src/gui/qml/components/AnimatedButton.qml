import QtQuick

// ─── Bouton animé avec effet tactile ─────────────────────

Rectangle {
    id: btn
    width: 160
    height: 48
    radius: Theme.radiusMedium
    color: primary ? Theme.primary : Theme.card
    border.color: primary ? "transparent" : Theme.surfaceVariant
    border.width: primary ? 0 : 1

    property string label: "Button"
    property string icon: ""
    property bool primary: false
    signal clicked()

    Behavior on color {
        ColorAnimation { duration: 150; easing.type: Easing.OutCubic }
    }

    Row {
        anchors.centerIn: parent
        spacing: 8

        Text {
            text: btn.icon
            font.pixelSize: 16
            visible: btn.icon !== ""
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            text: btn.label
            font.pixelSize: 14
            font.weight: Font.Medium
            color: btn.primary ? "#ffffff" : Theme.textPrimary
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor

        onClicked: btn.clicked()
        onPressed: pressAnim.start()
    }

    // Effet press
    scale: mouseArea.pressed ? 0.95 : (mouseArea.containsMouse ? 1.02 : 1.0)
    Behavior on scale {
        NumberAnimation { duration: 100; easing.type: Easing.OutCubic }
    }

    // Hover glow
    opacity: mouseArea.containsMouse ? 1.0 : 0.9
    Behavior on opacity {
        NumberAnimation { duration: 200 }
    }

    NumberAnimation {
        id: pressAnim
        target: btn
        property: "scale"
        from: 0.95; to: 1.0
        duration: 200
        easing.type: Easing.OutBack
    }
}
