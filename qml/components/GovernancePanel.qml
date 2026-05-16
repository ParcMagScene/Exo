import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../core"

// ═══════════════════════════════════════════════════════
//  GovernancePanel — Règles, validations, compliance, audit
// ═══════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    // ── Données governance ──
    property var rules: []            // { id, name, status, lastCheck, scope }
    // PERF FIX: ListModel à la place de property var [] — insert(0) O(1), pas de slice/unshift
    ListModel { id: validationsModel }
    ListModel { id: auditModel }
    property int passCount: 0
    property int failCount: 0
    property int warnCount: 0

    property int activeTab: 0  // 0=Règles, 1=Validations, 2=Audit

    // ── Connexions ──
    Connections {
        target: typeof pipelineEventBus !== 'undefined' ? pipelineEventBus : null

        function onEventEmitted(event) {
            if ((event.module || "") !== "governance") return

            if (event.event_type === "rule_check") {
                validationsModel.insert(0, {
                    timestamp: event.timestamp || Qt.formatTime(new Date(), "HH:mm:ss"),
                    rule: event.rule || "",
                    result: event.result || "pass",
                    detail: event.detail || ""
                })
                if (validationsModel.count > 200) validationsModel.remove(validationsModel.count - 1)

                if (event.result === "pass") root.passCount++
                else if (event.result === "fail") root.failCount++
                else root.warnCount++
            }

            if (event.event_type === "audit") {
                auditModel.insert(0, {
                    timestamp: event.timestamp || Qt.formatTime(new Date(), "HH:mm:ss"),
                    action: event.action || "",
                    actor: event.actor || "",
                    outcome: event.outcome || "ok"
                })
                if (auditModel.count > 500) auditModel.remove(auditModel.count - 1)
            }
        }
    }

    function resultColor(result) {
        switch (result) {
        case "pass": return Theme.success
        case "fail": return Theme.error
        case "warn": return Theme.warning
        default:     return Theme.textMuted
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing8
        spacing: Theme.spacing8

        // ── Header ──
        RowLayout {
            Layout.fillWidth: true

            Text {
                text: SettingsLabels.t("comp.governance")
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontMicro
                font.weight: Font.Bold
                color: Theme.textAccent
                font.letterSpacing: 1.5
            }

            Item { Layout.fillWidth: true }

            // Counters
            Row {
                spacing: Theme.spacing12

                Row {
                    spacing: 4
                    Rectangle { width: 8; height: 8; radius: 4; color: Theme.success; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: root.passCount.toString(); font.family: Theme.fontMono; font.pixelSize: Theme.fontTiny; color: Theme.success }
                }
                Row {
                    spacing: 4
                    Rectangle { width: 8; height: 8; radius: 4; color: Theme.warning; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: root.warnCount.toString(); font.family: Theme.fontMono; font.pixelSize: Theme.fontTiny; color: Theme.warning }
                }
                Row {
                    spacing: 4
                    Rectangle { width: 8; height: 8; radius: 4; color: Theme.error; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: root.failCount.toString(); font.family: Theme.fontMono; font.pixelSize: Theme.fontTiny; color: Theme.error }
                }
            }
        }

        // ── Tab Bar ──
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            Repeater {
                model: [
                    { label: "Règles",      idx: 0 },
                    { label: "Validations", idx: 1 },
                    { label: "Journal d'audit",   idx: 2 }
                ]

                Rectangle {
                    Layout.fillWidth: true
                    height: 32
                    color: root.activeTab === modelData.idx ? Theme.bgElevated : "transparent"

                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width; height: 2
                        color: root.activeTab === modelData.idx ? Theme.accent : Theme.border
                    }

                    Text {
                        anchors.centerIn: parent
                        text: modelData.label
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSmall
                        color: root.activeTab === modelData.idx ? Theme.textPrimary : Theme.textSecondary
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.activeTab = modelData.idx
                    }
                }
            }
        }

        // ── Contenu ──
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.activeTab

            // ── Tab 0: Règles ──
            ListView {
                id: rulesList
                clip: true
                spacing: Theme.spacing4
                boundsBehavior: Flickable.StopAtBounds
                model: root.rules.length

                delegate: Rectangle {
                    width: rulesList.width
                    height: 44
                    radius: Theme.radiusSmall
                    color: Theme.bgElevated

                    readonly property var rule: root.rules[index] || {}

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacing8
                        spacing: Theme.spacing8

                        Rectangle {
                            width: 8; height: 8; radius: 4
                            color: root.resultColor(rule.status || "pass")
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1

                            Text {
                                text: rule.name || "Unnamed rule"
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fontSmall
                                color: Theme.textPrimary
                            }
                            Text {
                                text: (rule.scope || "global") + " • " + (rule.lastCheck || "—")
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontTiny
                                color: Theme.textMuted
                            }
                        }

                        Text {
                            text: (rule.status || "pass").toUpperCase()
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontTiny
                            font.weight: Font.Bold
                            color: root.resultColor(rule.status || "pass")
                        }
                    }
                }

                // Default rules when empty
                Component.onCompleted: {
                    if (root.rules.length === 0) {
                        root.rules = [
                            { id: "R001", name: "Contenu sécurisé (OWASP)", status: "pass", lastCheck: "actif", scope: "llm" },
                            { id: "R002", name: "Limite tokens (max_tokens)", status: "pass", lastCheck: "actif", scope: "claude" },
                            { id: "R003", name: "Rate limiting API", status: "pass", lastCheck: "actif", scope: "network" },
                            { id: "R004", name: "Validation entrées utilisateur", status: "pass", lastCheck: "actif", scope: "pipeline" },
                            { id: "R005", name: "Timeout microservices (30s)", status: "pass", lastCheck: "actif", scope: "services" },
                            { id: "R006", name: "Audio format PCM16 24kHz", status: "pass", lastCheck: "actif", scope: "audio" },
                            { id: "R007", name: "Singleton guard services", status: "pass", lastCheck: "actif", scope: "infra" },
                            { id: "R008", name: "Historique max 10 tours", status: "pass", lastCheck: "actif", scope: "claude" }
                        ]
                    }
                }
            }

            // ── Tab 1: Validations ──
            ListView {
                id: validationsList
                clip: true
                spacing: 2
                boundsBehavior: Flickable.StopAtBounds
                model: validationsModel

                delegate: Rectangle {
                    width: validationsList.width
                    height: 28
                    color: index % 2 === 0 ? Theme.bgElevated : "transparent"

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacing8
                        anchors.rightMargin: Theme.spacing8
                        spacing: Theme.spacing8

                        Text {
                            text: model.timestamp || ""
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontTiny
                            color: Theme.textMuted
                            Layout.preferredWidth: 55
                        }

                        Rectangle {
                            width: 6; height: 6; radius: 3
                            color: root.resultColor(model.result || "pass")
                        }

                        Text {
                            text: model.rule || ""
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontTiny
                            color: Theme.textPrimary
                            Layout.preferredWidth: 150
                            elide: Text.ElideRight
                        }

                        Text {
                            text: model.detail || ""
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontTiny
                            color: Theme.textMuted
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    text: SettingsLabels.t("comp.governanceNoValidation")
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSmall
                    color: Theme.textMuted
                    visible: validationsModel.count === 0
                }
            }

            // ── Tab 2: Audit Log ──
            ListView {
                id: auditList
                clip: true
                spacing: 2
                boundsBehavior: Flickable.StopAtBounds
                model: auditModel

                delegate: Rectangle {
                    width: auditList.width
                    height: 28
                    color: index % 2 === 0 ? Theme.bgElevated : "transparent"

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacing8
                        anchors.rightMargin: Theme.spacing8
                        spacing: Theme.spacing8

                        Text {
                            text: model.timestamp || ""
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontTiny
                            color: Theme.textMuted
                            Layout.preferredWidth: 55
                        }

                        Text {
                            text: model.actor || "system"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontTiny
                            color: Theme.info
                            Layout.preferredWidth: 80
                        }

                        Text {
                            text: model.action || ""
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fontTiny
                            color: Theme.textPrimary
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }

                        Rectangle {
                            width: outcomeLabel.implicitWidth + 8
                            height: 16; radius: 3
                            color: model.outcome === "ok" ? Qt.rgba(Theme.success.r, Theme.success.g, Theme.success.b, 0.15)
                                 : model.outcome === "denied" ? Qt.rgba(Theme.error.r, Theme.error.g, Theme.error.b, 0.15)
                                 : Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.15)

                            Text {
                                id: outcomeLabel
                                anchors.centerIn: parent
                                  text: (model.outcome || "ok").toUpperCase()
                                  font.family: Theme.fontMono
                                  font.pixelSize: 9
                                  font.weight: Font.Bold
                                  color: model.outcome === "ok" ? Theme.success
                                      : model.outcome === "denied" ? Theme.error
                                      : Theme.warning
                            }
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    text: SettingsLabels.t("comp.governanceNoAudit")
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSmall
                    color: Theme.textMuted
                    visible: auditModel.count === 0
                }
            }
        }
    }
}
