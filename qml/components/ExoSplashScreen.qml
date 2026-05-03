import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  ExoSplashScreen — Écran de démarrage EXO
// ═══════════════════════════════════════════════════════

Rectangle {
    id: splash
    color: Theme.splashBg

    property bool allReady: false
    property int readyCount: 0
    property int totalServices: 0
    property string currentAction: "Initialisation…"
    property var serviceStatuses: []

    // Safe Boot properties
    property bool safeBootActive: false
    property bool criticalReady: false
    property int criticalReadyCount: 0
    property int criticalTotal: 0
    property int lazyReadyCount: 0
    property int lazyTotal: 0
    property int failedCount: 0
    property var failedServices: []

    // AutoRepair properties
    property bool autoRepairActive: false
    property var autoRepairTimeline: []

    signal dismissed()

    onAllReadyChanged: {
        if (allReady)
            dismissTimer.start()
    }

    Timer {
        id: dismissTimer
        interval: 600
        onTriggered: splash.dismissed()
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacing32
        width: Math.min(parent.width * 0.7, 500)

        // Logo / Titre
        Column {
            Layout.alignment: Qt.AlignHCenter
            spacing: Theme.spacing8

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "⬡"
                font.pixelSize: 64
                color: Theme.splashAccent
                visible: false  // Remplacé par l'icône SVG
            }

            Image {
                anchors.horizontalCenter: parent.horizontalCenter
                source: "qrc:/assets/icons/app/exo.svg"
                sourceSize.width: 72
                sourceSize.height: 72
                width: 72
                height: 72
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "EXO Assistant"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontH1 + 4
                font.weight: Font.Bold
                color: Theme.textPrimary
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "v30.3"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontBody
                color: Theme.textSecondary
            }
        }

        // Barre de progression
        Column {
            Layout.fillWidth: true
            spacing: Theme.spacing8

            ProgressBar {
                id: progressBar
                width: parent.width
                from: 0
                to: splash.totalServices > 0 ? splash.totalServices : 1
                value: splash.readyCount

                background: Rectangle {
                    implicitHeight: 6
                    radius: 3
                    color: Theme.splashPanel
                }

                contentItem: Item {
                    Rectangle {
                        width: progressBar.visualPosition * parent.width
                        height: parent.height
                        radius: 3

                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: Theme.splashAccent }
                            GradientStop { position: 1.0; color: Theme.accentDark }
                        }

                        Behavior on width {
                            NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                        }
                    }
                }
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: splash.allReady
                      ? "✓ Tous les services sont prêts"
                      : splash.currentAction
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontSmall
                color: splash.allReady ? Theme.success : Theme.textPrimary
            }
        }

        // Liste des services
        Column {
            Layout.fillWidth: true
            spacing: Theme.spacing4

            Repeater {
                model: splash.serviceStatuses

                Rectangle {
                    width: parent.width
                    height: 32
                    radius: Theme.radiusSmall
                    color: Theme.splashPanel

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacing12
                        anchors.rightMargin: Theme.spacing12
                        spacing: Theme.spacing8

                        Rectangle {
                            width: 8; height: 8; radius: 4
                            color: {
                                var s = modelData.status
                                if (s === "ready")     return Theme.success
                                if (s === "failed" || s === "crashed") return Theme.error
                                if (s === "repairing") return Theme.info
                                if (s === "starting" || s === "waiting_ready"
                                    || s === "restarting"
                                    || s === "launching" || s === "running" || s === "checking")
                                    return Theme.warning
                                return Theme.textMuted
                            }

                            SequentialAnimation on opacity {
                                running: modelData.status !== "ready"
                                         && modelData.status !== "failed"
                                         && modelData.status !== "crashed"
                                         && modelData.status !== "stopped"
                                         && modelData.status !== "repairing"
                                loops: Animation.Infinite
                                NumberAnimation { to: 0.3; duration: 500 }
                                NumberAnimation { to: 1.0; duration: 500 }
                            }
                        }

                        Text {
                            text: modelData.name
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontCaption
                            font.weight: Font.Bold
                            color: Theme.textPrimary
                        }

                        // v5.1: phase detail for TTS
                        Text {
                            visible: modelData.phase !== undefined
                                     && modelData.phase !== "none"
                                     && modelData.phase !== "ready_online"
                            text: {
                                var p = modelData.phase
                                if (p === "ready_init")    return "Initialisation…"
                                if (p === "ready_loading") return "Chargement modèle…"
                                if (p === "ready_warmup")  return "Préchauffage GPU…"
                                return ""
                            }
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontMicro
                            font.italic: true
                            color: Theme.splashAccent
                            Layout.fillWidth: true
                        }

                        // Filler when no phase
                        Item {
                            visible: modelData.phase === undefined
                                     || modelData.phase === "none"
                                     || modelData.phase === "ready_online"
                            Layout.fillWidth: true
                        }

                        Text {
                            text: ":" + modelData.port
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontMicro
                            color: Theme.textSecondary
                        }

                        Text {
                            text: {
                                var s = modelData.status
                                if (s === "ready")         return "✓"
                                if (s === "failed")        return "✗"
                                if (s === "crashed")       return "⚠"
                                if (s === "starting")      return "…"
                                if (s === "waiting_ready") return "◉"
                                if (s === "restarting")    return "↻"
                                if (s === "repairing")     return "🔧"
                                if (s === "launching")     return "…"
                                if (s === "checking")      return "?"
                                if (s === "running")       return "↻"
                                return ""
                            }
                            font.pixelSize: Theme.fontBody
                            color: {
                                var s = modelData.status
                                if (s === "ready")  return Theme.success
                                if (s === "failed" || s === "crashed") return Theme.error
                                if (s === "repairing") return Theme.info
                                return Theme.warning
                            }
                        }
                    }
                }
            }
        }

        // ── Safe Boot Status (inline) ──
        Column {
            Layout.fillWidth: true
            spacing: Theme.spacing4
            visible: splash.safeBootActive

            Rectangle {
                width: parent.width
                height: safeBootCol.implicitHeight + Theme.spacing16
                radius: Theme.radiusSmall
                color: Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.1)
                border.color: Theme.warning
                border.width: 1

                Column {
                    id: safeBootCol
                    anchors.centerIn: parent
                    spacing: Theme.spacing4

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "⚠ Mode Safe Boot actif"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSmall
                        font.weight: Font.Bold
                        color: Theme.warning
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: splash.failedCount > 0
                              ? splash.failedCount + " service(s) en échec"
                              : "Services critiques prêts — démarrage dégradé"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontCaption
                        color: splash.failedCount > 0 ? Theme.error : Theme.textSecondary
                    }
                }
            }
        }

        // ── AutoRepair Status (inline) ──
        Column {
            Layout.fillWidth: true
            spacing: Theme.spacing4
            visible: splash.autoRepairActive

            Rectangle {
                width: parent.width
                height: autoRepairCol.implicitHeight + Theme.spacing16
                radius: Theme.radiusSmall
                color: Qt.rgba(Theme.info.r, Theme.info.g, Theme.info.b, 0.1)
                border.color: Theme.info
                border.width: 1

                Column {
                    id: autoRepairCol
                    anchors.centerIn: parent
                    spacing: Theme.spacing4

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "🔧 Réparation automatique en cours…"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSmall
                        font.weight: Font.Bold
                        color: Theme.info
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: {
                            var tl = splash.autoRepairTimeline
                            if (!tl || tl.length === 0)
                                return "Analyse des services KO…"
                            var last = tl[tl.length - 1]
                            if (last.event === "repair_success")
                                return "✓ " + last.service + " réparé"
                            if (last.event === "repair_failed")
                                return "✗ " + last.service + " — échec"
                            if (last.event === "repair_attempt")
                                return "↻ Réparation de " + last.service + "…"
                            return last.detail || ""
                        }
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontCaption
                        color: Theme.textSecondary
                    }
                }
            }
        }

        // Spinner animé
        Item {
            Layout.alignment: Qt.AlignHCenter
            width: 24; height: 24
            visible: !splash.allReady

            Rectangle {
                id: spinner
                anchors.centerIn: parent
                width: 24; height: 24
                radius: 12
                color: "transparent"
                border.width: 3
                border.color: Theme.splashAccent

                Rectangle {
                    width: 12; height: 12
                    color: Theme.splashBg
                    anchors.right: parent.right
                    anchors.top: parent.top
                }

                RotationAnimation on rotation {
                    from: 0; to: 360
                    duration: 1000
                    loops: Animation.Infinite
                }
            }
        }
    }

    // Fond animé subtil
    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 2
        color: Theme.splashAccent
        opacity: splash.allReady ? 0 : 0.6

        Behavior on opacity { NumberAnimation { duration: 400 } }

        SequentialAnimation on x {
            running: !splash.allReady
            loops: Animation.Infinite
            NumberAnimation { from: -splash.width; to: splash.width; duration: 2000 }
        }
    }
}
