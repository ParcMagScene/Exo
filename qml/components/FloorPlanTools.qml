import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  FloorPlanTools — barre d'outils verticale
//
//  Appelle controller.setTool() pour chaque outil.
//  Affiche les contrôles zoom, grille, snap, undo/redo.
// ═══════════════════════════════════════════════════════

Rectangle {
    id: toolBar
    color: Theme.bgSecondary
    border.color: Theme.border
    border.width: 1

    // ── Injections ──
    property var controller: null    // FloorPlanController
    property var floorModel: null    // FloorPlanModel

    // ── Signals vers la page ──
    signal zoomIn()
    signal zoomOut()
    signal centerView()
    signal furnitureRequested()       // ouvrir la palette

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing4
        spacing: Theme.spacing2

        // ═══════ DRAWING TOOLS ═══════
        Repeater {
            model: [
                {tool: "select",    icon: "⊹",  tip: "Sélection (V)"},
                {tool: "wall",      icon: "▬",  tip: "Mur (W)"},
                {tool: "door",      icon: "🚪", tip: "Porte (D)"},
                {tool: "window",    icon: "⊞",  tip: "Fenêtre (N)"},
                {tool: "room",      icon: "⬜", tip: "Pièce (R)"},
                {tool: "furniture", icon: "🪑", tip: "Meuble (F)"},
                {tool: "device",    icon: "💡", tip: "Équipement (E)"},
                {tool: "camera",    icon: "📷", tip: "Caméra (C)"},
                {tool: "sensor",    icon: "📡", tip: "Capteur (S)"},
                {tool: "eraser",    icon: "✕",  tip: "Supprimer (X)"},
            ]

            ToolBtn {
                required property var modelData
                required property int index
                iconText:  modelData.icon
                tipText:   modelData.tip
                isActive:  controller ? controller.currentTool === modelData.tool : false
                onClicked: {
                    if (controller) controller.setTool(modelData.tool)
                    if (modelData.tool === "furniture") furnitureRequested()
                }
            }
        }

        // Separator
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 1
            Layout.topMargin: Theme.spacing4; Layout.bottomMargin: Theme.spacing4
            color: Theme.border
        }

        // ═══════ ZOOM ═══════
        ToolBtn { iconText: "+"; tipText: "Zoom + (Ctrl+=)"; onClicked: zoomIn() }
        ToolBtn { iconText: "−"; tipText: "Zoom − (Ctrl+-)"; onClicked: zoomOut() }
        ToolBtn { iconText: "⊙"; tipText: "Centrer (Home)"; onClicked: centerView() }

        // Separator
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 1
            Layout.topMargin: Theme.spacing4; Layout.bottomMargin: Theme.spacing4
            color: Theme.border
        }

        // ═══════ TOGGLES ═══════

        // Grid toggle
        ToolBtn {
            iconText: "#"
            tipText:  "Grille (G)"
            isActive: floorModel ? floorModel.snapEnabled : false
            onClicked: { if (floorModel) floorModel.snapEnabled = !floorModel.snapEnabled }
        }

        Item { Layout.fillHeight: true }

        // ═══════ UNDO / REDO ═══════
        ToolBtn {
            iconText: "↺"
            tipText:  "Annuler (Ctrl+Z)"
            enabled:  controller ? controller.canUndo : false
            opacity:  enabled ? 1.0 : 0.35
            onClicked: { if (controller) controller.undo() }
        }
        ToolBtn {
            iconText: "↻"
            tipText:  "Rétablir (Ctrl+Y)"
            enabled:  controller ? controller.canRedo : false
            opacity:  enabled ? 1.0 : 0.35
            onClicked: { if (controller) controller.redo() }
        }
    }

    // ═══════════════════════════════════════════════════
    //  ToolBtn — bouton d'outil interne
    // ═══════════════════════════════════════════════════
    component ToolBtn: Rectangle {
        id: btn

        property string iconText: ""
        property string tipText: ""
        property bool   isActive: false

        signal clicked()

        Layout.preferredWidth: 40
        Layout.preferredHeight: 40
        Layout.alignment: Qt.AlignHCenter
        radius: Theme.radiusMedium
        color: isActive ? Theme.accentActive
             : btnMa.containsMouse ? Theme.bgHover
             : "transparent"
        border.color: isActive ? Theme.accent : "transparent"
        border.width: 1

        Text {
            anchors.centerIn: parent
            text: iconText
            font.pixelSize: 16
            color: isActive ? Theme.accent : Theme.textSecondary
        }

        MouseArea {
            id: btnMa
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: btn.clicked()
        }

        ToolTip.visible: btnMa.containsMouse
        ToolTip.text: tipText
        ToolTip.delay: 350
    }
}
