import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  SafeBootPanel — Panneau Safe Boot EXO v30.2
//
//  Affiché quand le mode dégradé est actif.
//  Liste les services KO/dégradés, timeline du boot,
//  boutons Réessayer et Redémarrer.
// ═══════════════════════════════════════════════════════

Rectangle {
    id: panel
    color: Theme.bgSecondary
    radius: 0  // Fullscreen, pas de radius

    // ── Données ──
    property bool safeBootEnabled: false
    property int failedCount: 0
    property int degradedCount: 0
    property int readyCount: 0
    property int totalCount: 0
    property var failedServices: []
    property var degradedServices: []
    property var startupTimeline: []

    // ── Signaux vers C++ ──
    signal retryRequested()
    signal restartRequested()

    // La visibilité est contrôlée par MainWindow.qml (z: 999, anchors.fill)

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Math.max(Theme.spacing16, parent.width * 0.15)
        anchors.topMargin: Theme.spacing32
        anchors.bottomMargin: Theme.spacing32
        spacing: Theme.spacing12

        // ─── En-tête ───────────────────────────
        RowLayout {
            spacing: Theme.spacing8
            Layout.fillWidth: true

            Rectangle {
                width: 12; height: 12; radius: 6
                color: panel.safeBootEnabled ? Theme.error : Theme.warning

                SequentialAnimation on opacity {
                    running: panel.safeBootEnabled
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.3; duration: 600 }
                    NumberAnimation { to: 1.0; duration: 600 }
                }
            }

            Text {
                text: panel.safeBootEnabled ? "⚠  SAFE BOOT — Mode dégradé" : "Services dégradés"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontH2
                font.weight: Font.Bold
                color: panel.safeBootEnabled ? Theme.error : Theme.warning
            }

            Item { Layout.fillWidth: true }

            Text {
                text: panel.readyCount + "/" + panel.totalCount + " prêts"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontSmall
                color: Theme.textSecondary
            }
        }

        // Message explicatif
        Text {
            Layout.fillWidth: true
            text: panel.safeBootEnabled
                  ? "EXO a démarré en mode dégradé car certains services n'ont pas répondu dans les 2 secondes. "
                    + "Les services non critiques sont en cours de chargement en arrière-plan."
                  : "Certains services sont dégradés mais EXO fonctionne normalement."
            font.family: Theme.fontMono
            font.pixelSize: Theme.fontCaption
            color: Theme.textSecondary
            wrapMode: Text.WordWrap
        }

        // ─── Services en échec (critiques) ─────
        Column {
            Layout.fillWidth: true
            spacing: Theme.spacing8
            visible: panel.failedCount > 0

            Text {
                text: "✗  Services en échec (" + panel.failedCount + ")"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontBody
                font.weight: Font.Bold
                color: Theme.error
            }

            Repeater {
                model: panel.failedServices
                delegate: Rectangle {
                    width: parent.width
                    height: 36
                    radius: Theme.radiusSmall
                    color: Qt.rgba(Theme.error.r, Theme.error.g, Theme.error.b, 0.08)
                    border.color: Qt.rgba(Theme.error.r, Theme.error.g, Theme.error.b, 0.2)
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacing12
                        anchors.rightMargin: Theme.spacing12
                        spacing: Theme.spacing8

                        Rectangle {
                            width: 8; height: 8; radius: 4
                            color: Theme.error
                        }

                        Text {
                            text: modelData.name
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSmall
                            font.weight: Font.Bold
                            color: Theme.textPrimary
                        }

                        Text {
                            text: modelData.criticality === "critical" ? "[CRITIQUE]" : "[NON-CRITIQUE]"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontCaption
                            color: modelData.criticality === "critical" ? Theme.error : Theme.warning
                        }

                        Item { Layout.fillWidth: true }

                        Text {
                            text: modelData.error || ""
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontCaption
                            color: Theme.textSecondary
                            elide: Text.ElideRight
                            Layout.maximumWidth: 200
                        }
                    }
                }
            }
        }

        // ─── Services dégradés (non critiques) ─
        Column {
            Layout.fillWidth: true
            spacing: Theme.spacing8
            visible: panel.degradedCount > 0

            Text {
                text: "◉  Services dégradés (" + panel.degradedCount + ")"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontBody
                font.weight: Font.Bold
                color: Theme.warning
            }

            Repeater {
                model: panel.degradedServices
                delegate: Rectangle {
                    width: parent.width
                    height: 36
                    radius: Theme.radiusSmall
                    color: Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.06)
                    border.color: Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.15)
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacing12
                        anchors.rightMargin: Theme.spacing12
                        spacing: Theme.spacing8

                        Rectangle {
                            width: 8; height: 8; radius: 4
                            color: Theme.warning
                        }

                        Text {
                            text: modelData.name
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSmall
                            font.weight: Font.Bold
                            color: Theme.textPrimary
                        }

                        Item { Layout.fillWidth: true }

                        Text {
                            text: modelData.error || ""
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontCaption
                            color: Theme.textSecondary
                            elide: Text.ElideRight
                            Layout.maximumWidth: 200
                        }
                    }
                }
            }
        }

        // ─── Chronologie du démarrage ─────────────
        Column {
            Layout.fillWidth: true
            spacing: Theme.spacing8

            Text {
                text: "⏱  Chronologie du démarrage"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontBody
                font.weight: Font.Bold
                color: Theme.textPrimary
            }

            ScrollView {
                Layout.fillWidth: true
                implicitHeight: Math.min(timelineCol.implicitHeight, 200)
                width: parent.width
                clip: true

                Column {
                    id: timelineCol
                    width: parent.width
                    spacing: 2

                    Repeater {
                        model: panel.startupTimeline

                        Rectangle {
                            width: parent.width
                            height: 26
                            radius: 2
                            color: index % 2 === 0 ? "transparent" : Qt.rgba(1,1,1,0.02)

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacing8
                                anchors.rightMargin: Theme.spacing8
                                spacing: Theme.spacing8

                                Text {
                                    text: {
                                        var d = new Date(modelData.timestamp)
                                        return d.toLocaleTimeString(Qt.locale(), "HH:mm:ss.zzz")
                                    }
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontCaption - 1
                                    color: Theme.textMuted
                                    Layout.preferredWidth: 85
                                }

                                Text {
                                    text: modelData.serviceName || "—"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontCaption
                                    font.weight: Font.Bold
                                    color: Theme.textSecondary
                                    Layout.preferredWidth: 100
                                }

                                Text {
                                    text: modelData.detail || modelData.event
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontCaption
                                    color: {
                                        var e = modelData.event
                                        if (e.indexOf("fail") >= 0 || e.indexOf("timeout_critical") >= 0)
                                            return Theme.error
                                        if (e.indexOf("degrad") >= 0 || e.indexOf("timeout") >= 0)
                                            return Theme.warning
                                        if (e.indexOf("ready") >= 0 || e.indexOf("recovered") >= 0)
                                            return Theme.success
                                        return Theme.textSecondary
                                    }
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }
            }
        }

        // ─── Boutons d'action ──────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing12

            Item { Layout.fillWidth: true }

            Button {
                text: "↻  Réessayer"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontSmall

                contentItem: Text {
                    text: parent.text
                    font: parent.font
                    color: Theme.textPrimary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                background: Rectangle {
                    implicitWidth: 140
                    implicitHeight: 32
                    radius: Theme.radiusSmall
                    color: parent.hovered ? Theme.bgHover : Theme.bgInput
                    border.color: Theme.warning
                    border.width: 1
                }

                onClicked: panel.retryRequested()
            }

            Button {
                text: "⟳  Redémarrer normal"
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontSmall

                contentItem: Text {
                    text: parent.text
                    font: parent.font
                    color: Theme.textPrimary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                background: Rectangle {
                    implicitWidth: 180
                    implicitHeight: 32
                    radius: Theme.radiusSmall
                    color: parent.hovered ? Theme.accentHover : Theme.accent
                    border.color: Theme.accentLight
                    border.width: 1
                }

                onClicked: panel.restartRequested()
            }
        }
    }
}
