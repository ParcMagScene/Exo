import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"
import "../core"
import "../navigation"

// ═══════════════════════════════════════════════════════
//  HeaderBar — Barre d'en-tête EXO Design System
//  Affiche le titre de la page active + état pipeline
// ═══════════════════════════════════════════════════════

Rectangle {
    id: headerBar
    color: Theme.bgSecondary
    implicitHeight: Theme.headerHeight

    property string currentPage: "chat"
    property string pipelineState: "Idle"

    readonly property var pageTitles: ({
        "chat":           "Chat",
           "home":           "Accueil",
        "settings":       "Paramètres",
        "history":        "Historique",
        "logs":           "Logs système",
        "pipeline":       "Pipeline Monitor",
        "maison":         "Maison",
        "reseau":         "Réseau",
        "cognitive":      "Cognitive Timeline",
        "heatmap":        "Engine Heatmap",
           "voicePipeline":  "Voice Pipeline",
        "memory":         "Memory Inspector",
        "governance":     "Gouvernance",
           "observability":  "Observabilité",
           "vision":         "Vision",
           "simulation":     "Simulation",
           "spatialCognition": "Cognition Spatiale",
           "security":       "Sécurité",
           "development":    "Développement",
           "safeboot":       "Démarrage sûr",
           "debug":          "Logs système"
    })

    // Bordure inférieure
    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: Theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing16
        anchors.rightMargin: Theme.spacing16
        spacing: Theme.spacing12

        // Breadcrumb : EXO > Page
        Row {
            spacing: Theme.spacing6

            Text {
                text: "EXO"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontMicro
                font.bold: true
                color: Theme.textMuted
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                text: "›"
                font.pixelSize: Theme.fontSmall
                color: Theme.textMuted
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                text: headerBar.pageTitles[headerBar.currentPage] || headerBar.currentPage
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSmall
                font.weight: Font.Medium
                color: Theme.textPrimary
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        Item { Layout.fillWidth: true }

        // Mode switch Expert/Simple
        ModeSwitch {
            id: modeSwitch
            expertMode: typeof UIState !== 'undefined' ? UIState.expertMode : false
            onModeChanged: function(isExpert) {
                if (typeof UIState !== 'undefined') UIState.setExpertMode(isExpert)
                if (typeof MenuStructure !== 'undefined') MenuStructure.refreshMenu()
            }
            Connections {
                target: typeof UIState !== 'undefined' ? UIState : null
                function onExpertModeChanged() {
                    modeSwitch.expertMode = UIState.expertMode
                }
            }
        }

        // Pipeline state pill
        ExoPipelineStatus {
            state: headerBar.pipelineState
        }
    }
}
