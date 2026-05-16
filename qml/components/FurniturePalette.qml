import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  FurniturePalette — palette de mobilier catégorisée
//
//  Modal / popup affichant des catégories de meubles.
//  Click = crée un item Furniture via controller.
// ═══════════════════════════════════════════════════════

Rectangle {
    id: palette
    color: Theme.bgElevated
    border.color: Theme.borderLight
    border.width: 1
    radius: Theme.radiusMedium

    // ── Injections ──
    property var controller: null

    // ── Signal pour fermer ──
    signal closed()

    // ── Catalogue ──
    readonly property var categories: [
        {
            name: "Salon",
            items: [
                { label: "Canapé",       icon: "🛋️", w: 180, h: 80 },
                { label: "Fauteuil",     icon: "🪑", w: 70,  h: 70 },
                { label: "Table basse",  icon: "🟫", w: 100, h: 60 },
                { label: "Meuble TV",    icon: "📺", w: 150, h: 40 },
                { label: "Bibliothèque", icon: "📚", w: 120, h: 30 },
                { label: "Lampe",        icon: "💡", w: 30,  h: 30 }
            ]
        },
        {
            name: "Chambre",
            items: [
                { label: "Lit double",   icon: "🛏️", w: 160, h: 200 },
                { label: "Lit simple",   icon: "🛏️", w: 100, h: 200 },
                { label: "Armoire",      icon: "🚪", w: 120, h: 60 },
                { label: "Commode",      icon: "🗄️", w: 80,  h: 45 },
                { label: "Table de nuit",icon: "🔲", w: 45,  h: 45 },
                { label: "Bureau",       icon: "🖥️", w: 120, h: 60 }
            ]
        },
        {
            name: "Cuisine",
            items: [
                { label: "Plan de travail", icon: "🔲", w: 200, h: 60 },
                { label: "Table",           icon: "🟫", w: 120, h: 80 },
                { label: "Chaise",          icon: "🪑", w: 40,  h: 40 },
                { label: "Réfrigérateur",   icon: "🧊", w: 60,  h: 60 },
                { label: "Four/Cuisinière",  icon: "🔥", w: 60,  h: 60 },
                { label: "Évier",           icon: "🚰", w: 80,  h: 60 }
            ]
        },
        {
            name: "Bureau",
            items: [
                { label: "Bureau",       icon: "🖥️", w: 140, h: 70 },
                { label: "Chaise bureau",icon: "💺", w: 50,  h: 50 },
                { label: "Étagère",      icon: "📚", w: 100, h: 30 },
                { label: "Imprimante",   icon: "🖨️", w: 45,  h: 40 },
                { label: "Classeur",     icon: "🗄️", w: 45,  h: 60 }
            ]
        },
        {
            name: "Salle de bain",
            items: [
                { label: "Baignoire",    icon: "🛁", w: 170, h: 75 },
                { label: "Douche",       icon: "🚿", w: 90,  h: 90 },
                { label: "Lavabo",       icon: "🚰", w: 60,  h: 45 },
                { label: "WC",           icon: "🚽", w: 40,  h: 60 },
                { label: "Meuble vasque",icon: "🔲", w: 100, h: 50 }
            ]
        },
        {
            name: "Divers",
            items: [
                { label: "Plante",       icon: "🪴", w: 40,  h: 40 },
                { label: "Tapis",        icon: "🟫", w: 150, h: 100 },
                { label: "Escalier",     icon: "🪜", w: 100, h: 30 },
                { label: "Radiateur",    icon: "♨️", w: 80,  h: 15 },
                { label: "Cheminée",     icon: "🔥", w: 100, h: 25 }
            ]
        }
    ]

    property int currentCategory: 0

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing8
        spacing: Theme.spacing8

        // ── Header ──
        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "Mobilier"
                font.pixelSize: Theme.fontH3
                font.weight: Font.SemiBold
                color: Theme.textPrimary
                Layout.fillWidth: true
            }
            Rectangle {
                width: 24; height: 24; radius: 12
                color: closeMa.containsMouse ? Theme.bgHover : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    font.pixelSize: Theme.fontSmall
                    color: Theme.textSecondary
                }
                MouseArea {
                    id: closeMa
                    anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: palette.closed()
                }
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

        // ── Category tabs ──
        Row {
            Layout.fillWidth: true
            spacing: Theme.spacing2

            Repeater {
                model: palette.categories
                Rectangle {
                    required property int index
                    required property var modelData
                    width: catText.width + Theme.spacing16
                    height: 28
                    radius: Theme.radiusSmall
                    color: palette.currentCategory === index
                           ? Theme.accentActive : catMa.containsMouse
                           ? Theme.bgHover : "transparent"
                    Text {
                        id: catText
                        anchors.centerIn: parent
                        text: modelData.name
                        font.pixelSize: Theme.fontMicro
                        font.weight: palette.currentCategory === index ? Font.SemiBold : Font.Normal
                        color: palette.currentCategory === index ? Theme.accent : Theme.textSecondary
                    }
                    MouseArea {
                        id: catMa
                        anchors.fill: parent; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: palette.currentCategory = index
                    }
                }
            }
        }

        // ── Items grid ──
        GridView {
            id: itemsGrid
            Layout.fillWidth: true
            Layout.fillHeight: true
            cellWidth: 90
            cellHeight: 76
            clip: true

            model: (palette.categories[palette.currentCategory] || { items: [] }).items

            delegate: Rectangle {
                required property var modelData
                required property int index
                width: 84; height: 70
                radius: Theme.radiusSmall
                color: itemMa.containsMouse ? Theme.bgHover : Theme.bgSecondary
                border.color: itemMa.containsMouse ? Theme.accent : Theme.border
                border.width: itemMa.containsMouse ? 1 : 0

                Column {
                    anchors.centerIn: parent
                    spacing: Theme.spacing4
                    Text {
                        text: modelData.icon
                        font.pixelSize: 22
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Text {
                        text: modelData.label
                        font.pixelSize: Theme.fontMicro
                        color: Theme.textSecondary
                        width: 78
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                    }
                }
                MouseArea {
                    id: itemMa
                    anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (!palette.controller) return
                        var data = {
                            type: "Furniture",
                            x: 200, y: 200,
                            width: modelData.w,
                            height: modelData.h,
                            rotation: 0,
                            properties: { name: modelData.label, icon: modelData.icon }
                        }
                        palette.controller.createItemWithUndo(data)
                        palette.closed()
                    }
                }
            }
        }
    }
}
