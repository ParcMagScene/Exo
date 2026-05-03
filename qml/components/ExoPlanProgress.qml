import QtQuick
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  ExoPlanProgress — v8 Plan Execution Progress Widget
//
//  Shows the current multi-step plan execution status
//  with step indicators, progress bar, and step names.
// ═══════════════════════════════════════════════════════

Rectangle {
    id: root

    property var plan: null   // { id, goal, steps: [{name, tool, status}], progress, strategy }
    property bool active: plan !== null && plan.steps !== undefined

    color: Theme.bgElevated
    radius: Theme.radiusMedium
    border.color: root.active ? Theme.borderFocus : Theme.border
    border.width: 1
    implicitHeight: root.active ? contentCol.implicitHeight + Theme.spacing16 : 0
    visible: root.active
    clip: true

    Behavior on implicitHeight { NumberAnimation { duration: Theme.animNormal; easing.type: Easing.OutCubic } }
    Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

    ColumnLayout {
        id: contentCol
        anchors.fill: parent
        anchors.margins: Theme.spacing8
        spacing: Theme.spacing6

        // ── Header ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing8

            Text {
                text: "⚙"
                font.pixelSize: Theme.fontBody
            }

            Text {
                text: root.plan ? root.plan.goal || "Plan en cours" : ""
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSmall
                font.weight: Theme.weightSemiBold
                color: Theme.textPrimary
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            Text {
                text: root.plan ? (root.plan.strategy || "sequential").toUpperCase() : ""
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontTiny
                color: Theme.textMuted
            }
        }

        // ── Progress bar ──
        Rectangle {
            Layout.fillWidth: true
            height: Theme.progressHeight
            radius: Theme.progressHeight / 2
            color: Theme.bgInput

            Rectangle {
                width: parent.width * (root.plan ? root.plan.progress || 0 : 0)
                height: parent.height
                radius: parent.radius
                color: Theme.accent

                Behavior on width { NumberAnimation { duration: Theme.animNormal; easing.type: Easing.OutCubic } }
            }
        }

        // ── Step list ──
        Column {
            Layout.fillWidth: true
            spacing: Theme.spacing4
            visible: root.plan && root.plan.steps

            Repeater {
                model: root.plan ? root.plan.steps || [] : []

                RowLayout {
                    width: parent ? parent.width : 0
                    spacing: Theme.spacing6
                    height: 22

                    Rectangle {
                        width: 14
                        height: 14
                        radius: 7
                        color: {
                            switch (modelData.status) {
                            case "completed": return Theme.success
                            case "running":   return Theme.accent
                            case "failed":    return Theme.error
                            case "skipped":   return Theme.textMuted
                            default:          return Theme.bgInput
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            text: {
                                switch (modelData.status) {
                                case "completed": return "✓"
                                case "running":   return "►"
                                case "failed":    return "✗"
                                case "skipped":   return "–"
                                default:          return ""
                                }
                            }
                            font.pixelSize: 9
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                        }

                        Behavior on color { ColorAnimation { duration: Theme.animFast } }
                    }

                    Text {
                        text: modelData.name || modelData.tool || ("Étape " + (index + 1))
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontCaption
                        color: modelData.status === "completed" ? Theme.textSecondary
                             : modelData.status === "running"   ? Theme.textPrimary
                             : Theme.textMuted
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Text {
                        text: modelData.tool || ""
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontTiny
                        color: Theme.textMuted
                        visible: text.length > 0
                    }
                }
            }
        }
    }
}
