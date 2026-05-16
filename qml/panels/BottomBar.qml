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
        // v9.1 — Sync GUI : on n'affiche QUE les services qui ont une source d'état
        //  réelle (registry Supervisor OU probe HealthCheck). Les 9 services
        //  phantoms (files/calendar/homegraph/domotic/camera/samsung/voltalis/
        //  echo/networkmap) ne sont pas dans services.json ni dans HealthCheck,
        //  ils restaient donc forcément en "disabled" (gris). Cohérence avec
        //  AssistantToolDispatcher (abandon après 5 tentatives, patch C).
        //  Pour les réactiver : déclarer le service dans config/services.json
        //  ET ajouter setupService(...) dans HealthCheck::configure().
        var keys = ["stt","tts","vad","wakeword","memory","nlu","context","planner",
                    "executor","verifier","system",
                    "websearch","news","knowledge","tools"]
        var s = {}
        var hasSup = (typeof serviceSupervisor !== 'undefined')
        var hasHealth = (typeof healthCheck !== 'undefined')
        for (var i = 0; i < keys.length; ++i) {
            var k = keys[i]
            // Priorité au statut runtime ping/pong (HealthCheck), sinon état boot Supervisor.
            // Toute valeur brute (healthy/degraded/down/ready/starting/failed/unknown/…)
            // est ensuite normalisée en 4 états canoniques : ready/starting/error/disabled.
            // Service absent du registry ET non probé par HealthCheck → "disabled" (gris).
            var raw = ""
            if (hasHealth) {
                var h = healthCheck.serviceStatus(k)
                if (h && h !== "unknown") raw = h
            }
            if (!raw && hasSup) {
                var sup = serviceSupervisor.serviceState(k)
                if (sup && sup !== "unknown") raw = sup
            }
            s[k] = Theme.normalizeServiceState(raw)
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
                // v9.1 — Sync stricte : 15 dots = 11 services réels du Supervisor
                //  (services.json) + 4 microservices outils probés par HealthCheck
                //  (websearch/news/knowledge/tools). Garantie : si splash vert,
                //  alors tous les dots verts.
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
                    { label: "SYS", key: "system" },
                    { label: "WEB", key: "websearch" },
                    { label: "NWS", key: "news" },
                    { label: "KNW", key: "knowledge" },
                    { label: "TLS", key: "tools" }
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
