import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

import "components"
import "pages"
import "floorplan"

ApplicationWindow {
    id: root
    visible: true
    width: 1280
    height: 800
    minimumWidth: 800
    minimumHeight: 600
    title: "EXO"
    color: Theme.background

    // ─── État global ─────────────────────────────────────
    property string currentPage: "home"
    property string pipelineState: "idle"
    property string lastTranscript: ""
    property string lastResponse: ""
    property string currentTime: ""

    // ─── Connexions au Bridge Python ─────────────────────
    Connections {
        target: Bridge
        function onStateChanged(state) { root.pipelineState = state }
        function onTranscriptChanged(text) { root.lastTranscript = text }
        function onResponseChanged(text) { root.lastResponse = text }
        function onTimeChanged(time) { root.currentTime = time }
    }

    // ─── Layout principal ────────────────────────────────
    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Navigation latérale
        NavRail {
            id: navRail
            Layout.fillHeight: true
            Layout.preferredWidth: Theme.navRailWidth
            currentPage: root.currentPage
            onPageSelected: function(page) { root.currentPage = page }
        }

        // Contenu principal
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Barre de titre
            TopBar {
                Layout.fillWidth: true
                Layout.preferredHeight: Theme.topBarHeight
                currentTime: root.currentTime
                pipelineState: root.pipelineState
            }

            // Pages (StackLayout)
            StackLayout {
                id: pageStack
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: {
                    switch(root.currentPage) {
                        case "home": return 0
                        case "floorplan": return 1
                        case "cameras": return 2
                        case "automation": return 3
                        case "settings": return 4
                        default: return 0
                    }
                }

                // Page 0: Accueil
                HomePage {
                    pipelineState: root.pipelineState
                    lastTranscript: root.lastTranscript
                    lastResponse: root.lastResponse
                }

                // Page 1: Plans
                FloorPlanPage {}

                // Page 2: Caméras
                CamerasPage {}

                // Page 3: Domotique
                AutomationPage {}

                // Page 4: Réglages
                SettingsPage {}
            }
        }
    }
}
