import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"
import "../core"

// ═══════════════════════════════════════════════════════
//  HomePage — Page principale chat (Transcript + Réponse)
// ═══════════════════════════════════════════════════════

Item {
    id: root

    property string partialTranscript: ""
    property string currentResponse: ""
    property bool isStreaming: false
    property var floorModel: null

    // v8: Plan & Context properties
    property var currentPlan: null       // {id, goal, steps, progress, strategy}
    property string contextTopic: ""
    property real contextConfidence: 0.0
    property string contextEnergy: "normal"
    property string contextLocation: ""

    // Expose les vues pour le wiring externe
    property alias transcriptView: transcript
    property alias responseView: response
    property alias planProgress: planWidget
    property alias contextPanel: ctxPanel
    property alias maisonPanel: maisonTab
    property alias reseauPanel: reseauTab
    property alias floorPlanPanel: floorPlanTab

    property int selectedSection: 0
    property bool expertMode: typeof UIState !== 'undefined' ? UIState.expertMode : false

    signal deviceCommand(string deviceId, string command, var params)
    signal homeRefreshRequested()
    signal scenarioRequested(string name)
    signal networkScanRequested()
    signal networkScanFastRequested()

    function showSection(panelName) {
        switch (panelName) {
        case "maison":
            selectedSection = 1
            break
        case "reseau":
            selectedSection = 2
            break
        case "floorplan":
            selectedSection = 3
            break
        default:
            selectedSection = 0
            break
        }
    }

    Connections {
        target: typeof UIState !== 'undefined' ? UIState : null

        function onExpertModeChanged() {
            root.expertMode = UIState.expertMode
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.selectedSection

            Item {
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    PipelineView {
                        Layout.fillWidth: true
                        Layout.leftMargin: Theme.spacing8
                        Layout.rightMargin: Theme.spacing8
                        Layout.topMargin: Theme.spacing4
                        Layout.preferredHeight: root.expertMode ? 140 : 0
                        visible: root.expertMode
                        collapsed: !root.expertMode
                        clip: true

                        Behavior on Layout.preferredHeight { NumberAnimation { duration: Theme.animNormal; easing.type: Easing.InOutQuad } }
                    }

                    ExoContextPanel {
                        id: ctxPanel
                        Layout.fillWidth: true
                        Layout.leftMargin: Theme.spacing8
                        Layout.rightMargin: Theme.spacing8
                        Layout.topMargin: Theme.spacing4
                        topic: root.contextTopic
                        topicConfidence: root.contextConfidence
                        energyLevel: root.contextEnergy
                        location: root.contextLocation
                    }

                    ExoPlanProgress {
                        id: planWidget
                        Layout.fillWidth: true
                        Layout.leftMargin: Theme.spacing8
                        Layout.rightMargin: Theme.spacing8
                        Layout.topMargin: root.currentPlan ? Theme.spacing4 : 0
                        plan: root.currentPlan
                    }

                    SplitView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        orientation: Qt.Vertical

                        // PERF FIX: Loader évite que le Timer de CognitiveTimeline
                        // tourne en permanence même quand expertMode est désactivé.
                        Loader {
                            id: cognitiveTimelineLoader
                            SplitView.fillWidth: true
                            SplitView.preferredHeight: root.expertMode ? 200 : 0
                            SplitView.minimumHeight: 0
                            active: root.expertMode
                            clip: true
                            sourceComponent: Component {
                                CognitiveTimeline { compact: true }
                            }
                            onStatusChanged: if (status === Loader.Error) console.error("[QML] cognitiveTimelineLoader failed:", sourceComponent ? sourceComponent.errorString() : "unknown")
                            Behavior on SplitView.preferredHeight { NumberAnimation { duration: Theme.animNormal; easing.type: Easing.InOutQuad } }
                        }

                        ExoTranscriptView {
                            id: transcript
                            SplitView.fillWidth: true
                            SplitView.preferredHeight: parent.height * 0.55
                            SplitView.minimumHeight: 100
                            partialTranscript: root.partialTranscript
                        }

                        ExoResponseView {
                            id: response
                            SplitView.fillWidth: true
                            SplitView.fillHeight: true
                            SplitView.minimumHeight: 80
                            responseText: root.currentResponse
                            isStreaming: root.isStreaming
                        }

                        handle: Rectangle {
                            implicitHeight: 4
                            color: SplitHandle.hovered || SplitHandle.pressed
                                   ? Theme.borderFocus : Theme.border
                            Behavior on color { ColorAnimation { duration: Theme.animFast } }
                        }
                    }
                }
            }

            MaisonPage {
                id: maisonTab
                onDeviceCommand: function(deviceId, command, params) {
                    root.deviceCommand(deviceId, command, params || {})
                }
                onRefreshRequested: root.homeRefreshRequested()
                onScenarioRequested: function(name) {
                    root.scenarioRequested(name)
                }
            }

            ReseauPage {
                id: reseauTab
                onScanRequested: root.networkScanRequested()
                onScanFastRequested: root.networkScanFastRequested()
            }

            FloorPlanPage {
                id: floorPlanTab
                floorModel: root.floorModel
            }
        }
    }

    Component.onCompleted: {
        root.expertMode = typeof UIState !== 'undefined' ? UIState.expertMode : false
    }
}
