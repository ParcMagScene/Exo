import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"
import "../navigation"
import "../core"

// ═══════════════════════════════════════════════════════
//  Sidebar — Navigation latérale EXO v30.3
//  Menu catégorisé avec sections collapsibles
//  Source de vérité : MenuStructure singleton (Normal/Expert)
// ═══════════════════════════════════════════════════════

Rectangle {
    id: sidebar
    width: Theme.sidebarWidth
    color: Theme.bgElevated

    // ── Safe Boot: désactiver la navigation ──
    enabled: typeof assistantManager !== 'undefined' ? !assistantManager.safeBootEnabled : true
    opacity: (typeof assistantManager !== 'undefined' && assistantManager.safeBootEnabled) ? 0.3 : 1.0
    Behavior on opacity { NumberAnimation { duration: 300 } }

    property string currentStatus: "Idle"
    property real micLevel: 0.0
    property string activePanel: "home"

    signal panelSelected(string panelName)

    // ── État des catégories ouvertes / fermées ──
    property var collapsedCategories: ({})

    function isCategoryCollapsed(catId) {
        return collapsedCategories[catId] === true
    }

    function toggleCategory(catId) {
        var copy = Object.assign({}, collapsedCategories)
        copy[catId] = !copy[catId]
        collapsedCategories = copy
    }

    // ── Rafraîchir le menu lors du changement de mode ──
    Connections {
        target: typeof UIState !== 'undefined' ? UIState : null
        function onExpertModeChanged() {
            // Force le Repeater à se rafraîchir
            navRepeater.model = null
            navRepeater.model = MenuStructure.getCategories()
            console.log("[Sidebar] Menu adapté au mode:", UIState.expertMode ? "EXPERT" : "NORMAL")
        }
    }

    Connections {
        target: typeof MenuStructure !== 'undefined' ? MenuStructure : null
        function onForceRefreshChanged() {
            // Force le Repeater à se rafraîchir quand MenuStructure.refreshMenu() est appelée
            navRepeater.model = null
            navRepeater.model = MenuStructure.getCategories()
            console.log("[Sidebar] Menu rafraîchi (forceRefresh signal)")
        }
    }

    // Bordure droite
    Rectangle {
        anchors.right: parent.right
        width: 1
        height: parent.height
        color: Theme.border
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 0
        spacing: 0

        // ── Logo EXO ──
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 60
            color: "transparent"

            RowLayout {
                anchors.centerIn: parent
                spacing: Theme.spacing10

                Image {
                    source: "../../assets/icons/app/exo.svg"
                    sourceSize.width: 28
                    sourceSize.height: 28
                    width: 28
                    height: 28
                }
                Text {
                    text: "EXO"
                    font.family: Theme.fontMono
                    font.pixelSize: 18
                    font.bold: true
                    color: Theme.textPrimary
                    font.letterSpacing: 4
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Theme.border
            }
        }

        // ── Status Indicator ──
        ExoStatusIndicator {
            Layout.fillWidth: true
            Layout.preferredHeight: 80
            currentStatus: sidebar.currentStatus
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.border
        }

        // ── Microphone Level ──
        ExoMicrophoneLevel {
            Layout.fillWidth: true
            Layout.preferredHeight: 50
            level: sidebar.micLevel
        }

        // ── Audio Visualizer (déplacé depuis BottomBar) ──
        ExoVisualizer {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacing8
            Layout.rightMargin: Theme.spacing8
            Layout.preferredHeight: 36
            audioLevel: sidebar.micLevel
            active: sidebar.micLevel > 0.01
            lineColor: Theme.accent
            lineWidth: 1.0
        }

        // ── Orb Visualizer ──
        ExoOrbVisualizer {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 80
            Layout.preferredHeight: 80
            orbSize: 80
            state: sidebar.currentStatus
            audioLevel: sidebar.micLevel
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.border
        }

        // ══════════════════════════════════════════
        //  Navigation catégorisée — dynamique Normal/Expert
        // ══════════════════════════════════════════
        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: navColumn.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                width: 4
            }

            ColumnLayout {
                id: navColumn
                width: parent.width
                spacing: 0

                // Petit padding haut
                Item { Layout.preferredHeight: Theme.spacing8 }

                Repeater {
                    id: navRepeater
                    model: typeof MenuStructure !== 'undefined' ? MenuStructure.getCategories() : []

                    delegate: ColumnLayout {
                        id: categoryDelegate
                        Layout.fillWidth: true
                        spacing: 0

                        required property var modelData
                        required property int index

                        property string catId: modelData.id
                        property bool collapsed: sidebar.isCategoryCollapsed(catId)
                        property bool hasActiveItem: {
                            var items = modelData.items
                            for (var i = 0; i < items.length; i++) {
                                if (items[i].name === sidebar.activePanel) return true
                            }
                            return false
                        }

                        // ── En-tête de catégorie ──
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 28
                            Layout.leftMargin: Theme.spacing8
                            Layout.rightMargin: Theme.spacing8
                            Layout.topMargin: index > 0 ? Theme.spacing4 : 0
                            radius: Theme.radiusSmall
                            color: catHeaderMouse.containsMouse ? Theme.bgHover : "transparent"

                            Behavior on color {
                                ColorAnimation { duration: Theme.animFast }
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: Theme.spacing6

                                // Chevron
                                Text {
                                    text: categoryDelegate.collapsed ? "›" : "⌄"
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: categoryDelegate.hasActiveItem ? Theme.accent : Theme.textMuted
                                    Layout.preferredWidth: 12
                                    horizontalAlignment: Text.AlignHCenter
                                }

                                Text {
                                    text: categoryDelegate.modelData.label
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    font.bold: true
                                    font.letterSpacing: 1.5
                                    color: categoryDelegate.hasActiveItem ? Theme.accent : Theme.textMuted
                                    Layout.fillWidth: true
                                }

                                // Badge compteur d'items
                                Rectangle {
                                    visible: categoryDelegate.collapsed && categoryDelegate.hasActiveItem
                                    width: 6; height: 6; radius: 3
                                    color: Theme.accent
                                }
                            }

                            MouseArea {
                                id: catHeaderMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: sidebar.toggleCategory(categoryDelegate.catId)
                            }
                        }

                        // ── Items de la catégorie ──
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing2
                            visible: !categoryDelegate.collapsed

                            Repeater {
                                model: categoryDelegate.modelData.items

                                delegate: Rectangle {
                                    id: navItem
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: Theme.navItemHeight
                                    Layout.leftMargin: Theme.spacing8
                                    Layout.rightMargin: Theme.spacing8
                                    radius: Theme.radiusSmall

                                    required property var modelData

                                    property bool isActive: sidebar.activePanel === modelData.name

                                    color: isActive ? Theme.accentActive
                                         : navItemMouse.containsMouse ? Theme.bgHover
                                         : "transparent"

                                    Behavior on color {
                                        ColorAnimation { duration: Theme.animFast }
                                    }

                                    // Barre accent gauche
                                    Rectangle {
                                        visible: navItem.isActive
                                        anchors.left: parent.left
                                        width: 3
                                        height: parent.height
                                        radius: 1
                                        color: Theme.accent
                                    }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 20
                                        spacing: Theme.spacing10

                                        Image {
                                            source: "../" + navItem.modelData.icon
                                            sourceSize.width: Theme.iconSize
                                            sourceSize.height: Theme.iconSize
                                            width: Theme.iconSize
                                            height: Theme.iconSize
                                            opacity: navItem.isActive ? 1.0 : 0.6
                                        }
                                        Text {
                                            text: navItem.modelData.label
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.fontSmall
                                            color: navItem.isActive ? "#FFFFFF" : Theme.textSecondary
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }
                                    }

                                    MouseArea {
                                        id: navItemMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            sidebar.activePanel = navItem.modelData.name
                                            sidebar.panelSelected(navItem.modelData.name)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Item { Layout.fillHeight: true }
            }
        }
    }
}
