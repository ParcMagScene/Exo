import QtQuick
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  ExoButton — Bouton moderne Fluent Design
// ═══════════════════════════════════════════════════════

Rectangle {
    id: root

    property string text: ""
    property string iconText: ""       // SVG/Unicode icon
    property bool primary: false
    property bool destructive: false
    property bool enabled: true
    property bool flat: false

    signal clicked()

    implicitWidth: contentRow.implicitWidth + Theme.paddingBtn * 2
    implicitHeight: Theme.buttonHeight
    radius: Theme.radiusMedium
    opacity: root.enabled ? 1.0 : 0.4

    color: {
        if (!root.enabled) return Theme.bgInput
        if (root.destructive)
            return mouseArea.pressed ? Theme.errorDim
                 : mouseArea.containsMouse ? Theme.errorHover : Theme.error
        if (root.primary)
            return mouseArea.pressed ? Theme.accentDark
                 : mouseArea.containsMouse ? Theme.accentHover : Theme.accent
        if (root.flat)
            return mouseArea.pressed ? Theme.bgActive
                 : mouseArea.containsMouse ? Theme.bgHover : "transparent"
        return mouseArea.pressed ? Theme.bgActive
             : mouseArea.containsMouse ? Theme.bgHover : Theme.bgElevated
    }

    border.width: root.flat ? 0 : 1
    border.color: {
        if (root.flat) return "transparent"
        if (root.primary || root.destructive) return "transparent"
        return mouseArea.containsMouse ? Theme.borderHover : Theme.border
    }

    scale: mouseArea.pressed ? 0.98 : 1.0
    Behavior on scale { NumberAnimation { duration: Theme.animFast; easing.type: Easing.OutQuad } }
    Behavior on color { ColorAnimation { duration: Theme.animNormal } }

    RowLayout {
        id: contentRow
        anchors.centerIn: parent
        spacing: root.iconText && root.text ? Theme.spacing6 : 0

        Text {
            visible: root.iconText.length > 0
            text: root.iconText
            font.pixelSize: Theme.iconSize
            font.family: Theme.fontFamily
            color: root.primary || root.destructive ? "#FFFFFF" : Theme.textPrimary
        }

        Text {
            visible: root.text.length > 0
            text: root.text
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSmall
            font.weight: Font.Medium
            color: root.primary || root.destructive ? "#FFFFFF" : Theme.textPrimary
        }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        enabled: root.enabled
        onClicked: root.clicked()
    }
}
