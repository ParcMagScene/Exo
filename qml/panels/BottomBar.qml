import QtQuick
import QtQuick.Layouts
import "../theme"

// -------------------------------------------------------
//  BottomBar � Barre inf�rieure EXO Design System
//
//  PERF FIX: serviceStates cache centralis� � �vite 20 appels
//  C++ serviceState() en bindings directs (d�clench� une seule
//  fois sur signal serviceSupervisor, pas � chaque repaint).
// -------------------------------------------------------

Rectangle {
    id: bottomBar
    color: Theme.bgSecondary
    implicitHeight: Theme.bottomBarHeight

    property real audioLevel: 0.0

    // -- Cache centralis� des �tats services --
    property var serviceStates: ({})

    function refreshServiceStates() {
        // Clés en minuscules : ServiceDescriptor::fromJson force toLower()
        // sur les noms chargés depuis services.json (registry indexe en lowercase).
        var keys = ["stt","tts","vad","wakeword","memory","nlu","context","planner",
                    "executor","verifier","fileservice","calendar","system","homegraph",
                    "domotic","camera","samsung","voltalis","echo","networkmap"]
        var s = {}
        var hasSup = (typeof serviceSupervisor !== 'undefined')
        var hasHealth = (typeof healthCheck !== 'undefined')
        for (var i = 0; i < keys.length; ++i) {
            var k = keys[i]
            // Priorité au statut runtime ping/pong (HealthCheck), sinon état boot Supervisor
            var v = ""
            if (hasHealth) {
                var h = healthCheck.serviceStatus(k)
                if (h && h !== "unknown") v = h
            }
            if (!v && hasSup) v = serviceSupervisor.serviceState(k)
            s[k] = v || ""
        }
        bottomBar.serviceStates = s
    }

    // Signaux réels du Supervisor : progressChanged (chaque transition d'état),
    // serviceReady (par service), allServicesReady (fin du boot).
    Connections {
        target: typeof serviceSupervisor !== 'undefined' ? serviceSupervisor : null
        function onProgressChanged()       { bottomBar.refreshServiceStates() }
        function onServiceReady(name)      { bottomBar.refreshServiceStates() }
        function onAllServicesReady()      { bottomBar.refreshServiceStates() }
        function onCurrentActionChanged()  { bottomBar.refreshServiceStates() }
    }

    // HealthCheck émet healthChanged à chaque ping/pong (down/healthy/degraded).
    Connections {
        target: typeof healthCheck !== 'undefined' ? healthCheck : null
        function onHealthChanged() { bottomBar.refreshServiceStates() }
    }

    Component.onCompleted: Qt.callLater(refreshServiceStates)

    // Bordure supérieure
    Rectangle {
        anchors.top: parent.top
        width: parent.width
        height: 1
        color: Theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacing12
        anchors.rightMargin: Theme.spacing12
        spacing: Theme.spacing12

        // -- Health dots (cache serviceStates) --
        Row {
            spacing: Theme.spacing6

            Repeater {
                model: [
                    { label: "STT", key: "stt" },
                    { label: "TTS", key: "tts" },
                    { label: "VAD", key: "vad" },
                    { label: "WW",  key: "wakeword" },
                    { label: "MEM", key: "memory" },
                    { label: "NLU", key: "nlu" },
                    { label: "CTX", key: "context" },
                    { label: "PLN", key: "planner" },
                    { label: "EXE", key: "executor" },
                    { label: "VER", key: "verifier" },
                    { label: "FIL", key: "fileservice" },
                    { label: "CAL", key: "calendar" },
                    { label: "SYS", key: "system" },
                    { label: "HG",  key: "homegraph" },
                    { label: "DOM", key: "domotic" },
                    { label: "CAM", key: "camera" },
                    { label: "SAM", key: "samsung" },
                    { label: "VOL", key: "voltalis" },
                    { label: "ECH", key: "echo" },
                    { label: "NET", key: "networkmap" }
                ]

                Row {
                    spacing: 3

                    Rectangle {
                        width: Theme.dotSize
                        height: Theme.dotSize
                        radius: Theme.dotSize / 2
                        anchors.verticalCenter: parent.verticalCenter
                        color: Theme.healthColor(bottomBar.serviceStates[modelData.key] || "")
                        Behavior on color { ColorAnimation { duration: Theme.animNormal } }
                    }

                    Text {
                        text: modelData.label
                        font.family: Theme.fontMono
                        font.pixelSize: 9
                        color: Theme.textMuted
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }

        // Spacer - pousse l'horloge à droite
        Item { Layout.fillWidth: true }

        // Séparateur
        Rectangle {
            Layout.fillHeight: true
            Layout.topMargin: Theme.spacing6
            Layout.bottomMargin: Theme.spacing6
            width: 1
            color: Theme.border
        }

        // -- Horloge --
        Text {
            id: clockText
            font.family: Theme.fontMono
            font.pixelSize: Theme.fontMicro
            color: Theme.textSecondary

            Timer {
                interval: 30000
                running: true
                repeat: true
                triggeredOnStart: true
                onTriggered: clockText.text = Qt.formatTime(new Date(), "HH:mm")
            }
        }
    }
}
