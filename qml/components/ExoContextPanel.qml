import QtQuick
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  ExoContextPanel — v8 Contextual Awareness Widget
//
//  Shows the current context engine state: topic,
//  detected preferences, energy level, location.
//  Appears as a floating info strip on the HomePage.
// ═══════════════════════════════════════════════════════

Rectangle {
    id: root

    property string topic: ""
    property real topicConfidence: 0.0
    property string energyLevel: "normal"    // low, normal, high
    property string location: ""
    property var preferences: []             // [{category, value}]

    readonly property bool hasData: topic.length > 0 || location.length > 0

    color: Theme.bgElevated
    radius: Theme.radiusMedium
    border.color: Theme.border
    implicitHeight: root.hasData ? innerRow.implicitHeight + Theme.spacing12 : 0
    visible: root.hasData
    clip: true
    opacity: root.hasData ? 1.0 : 0.0

    Behavior on implicitHeight { NumberAnimation { duration: Theme.animNormal; easing.type: Easing.OutCubic } }
    Behavior on opacity { NumberAnimation { duration: Theme.animNormal } }

    RowLayout {
        id: innerRow
        anchors.fill: parent
        anchors.margins: Theme.spacing6
        spacing: Theme.spacing12

        // ── Topic chip ──
        Rectangle {
            visible: root.topic.length > 0
            color: Theme.accentActive
            radius: Theme.radiusSmall
            implicitWidth: topicText.implicitWidth + Theme.spacing12
            implicitHeight: 22

            Text {
                id: topicText
                anchors.centerIn: parent
                text: root.topic
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontCaption
                font.weight: Theme.weightMedium
                color: Theme.textPrimary
            }
        }

        // ── Confidence ──
        Text {
            visible: root.topic.length > 0
            text: Math.round(root.topicConfidence * 100) + "%"
            font.family: Theme.fontMono
            font.pixelSize: Theme.fontTiny
            color: Theme.textMuted
        }

        // ── Energy indicator ──
        Rectangle {
            visible: root.energyLevel !== "normal"
            width: 8; height: 8
            radius: 4
            color: root.energyLevel === "high" ? Theme.success
                 : root.energyLevel === "low"  ? Theme.warning
                 : "transparent"
        }

        // ── Location ──
        Text {
            visible: root.location.length > 0
            text: "📍 " + root.location
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontCaption
            color: Theme.textSecondary
        }

        Item { Layout.fillWidth: true }

        // ── Dismiss ──
        Text {
            text: "✕"
            font.pixelSize: Theme.fontCaption
            color: Theme.textMuted
            opacity: dismissArea.containsMouse ? 1.0 : 0.5

            MouseArea {
                id: dismissArea
                anchors.fill: parent
                anchors.margins: -4
                cursorShape: Qt.PointingHandCursor
                hoverEnabled: true
                onClicked: root.visible = false
            }
        }
    }
}
