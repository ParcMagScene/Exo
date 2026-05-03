import QtQuick
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  ExoPanelHeader — En-tête standard pour panneaux
// ═══════════════════════════════════════════════════════

Rectangle {
    id: root

    property string title: ""
    property string subtitle: ""
    property color titleColor: Theme.textAccent
    property alias rightContent: rightSlot.children

    Layout.fillWidth: true
    implicitHeight: subtitle.length > 0 ? Theme.headerHeight + 18 : Theme.headerHeight
    color: Theme.bgSecondary

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.marginH
        anchors.rightMargin: Theme.marginH
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true

        Text {
            text: root.title.toUpperCase()
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontMicro
            font.weight: Font.Bold
            color: root.titleColor
            font.letterSpacing: 1.5
        }

        Item { Layout.fillWidth: true }

        Row {
            id: rightSlot
            spacing: Theme.spacing12
        }
        } // end RowLayout

        Text {
            visible: root.subtitle.length > 0
            text: root.subtitle
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontMicro - 1
            color: Theme.textMuted
            Layout.fillWidth: true
            Layout.bottomMargin: 3
        }
    } // end ColumnLayout

    // Séparateur bas
    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: Theme.border
    }
}
