import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ─── Section de réglages (carte repliable) ───────────────

Rectangle {
    id: section

    property string title: ""
    default property alias content: contentColumn.data

    Layout.fillWidth: true
    implicitHeight: col.implicitHeight + 32
    radius: Theme.radiusLarge
    color: Theme.card

    ColumnLayout {
        id: col
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16

        Text {
            text: section.title
            font.pixelSize: 16
            font.bold: true
            color: Theme.textPrimary
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.surfaceVariant
        }

        ColumnLayout {
            id: contentColumn
            Layout.fillWidth: true
            spacing: 16
        }
    }
}
