import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ─── Ligne de réglage: label + description + contrôle ────

RowLayout {
    id: row
    spacing: 16

    property string label: ""
    property string description: ""

    default property alias control: controlSlot.data

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 2

        Text {
            text: row.label
            font.pixelSize: 14
            color: Theme.textPrimary
        }
        Text {
            text: row.description
            font.pixelSize: 11
            color: Theme.textMuted
            visible: text !== ""
        }
    }

    Item {
        id: controlSlot
        Layout.preferredWidth: childrenRect.width
        Layout.preferredHeight: childrenRect.height
    }
}
