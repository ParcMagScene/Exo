import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════════════
//  LogsPage — Visualiseur complet des logs runtime EXO
//  - Source : LogManager (contextProperty `logManager`)
//  - Tri par timestamp / niveau / catégorie / message
//  - Filtre texte + filtre par niveau
//  - Copie ligne unique / copie sélection / copie tout
//  - Auto-scroll, pause, vidage, rafraîchissement
// ═══════════════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    // Modèle interne — chaque entrée : {raw, ts, level, category, message}
    ListModel { id: logModel }

    // État
    property bool autoScroll: true
    property bool paused: false
    property string filterText: ""
    property string filterLevel: "ALL"   // ALL/DEBUG/INFO/WARN/ERROR
    property string sortColumn: "ts"     // ts/level/category/message
    property bool sortDescending: false
    property int maxRows: 5000           // garde-fou mémoire

    // ── Parser : "[2026-05-14 09:37:52.154] INFO  [VOICE] message…" ──
    function parseLine(raw) {
        var s = String(raw)
        var entry = { raw: s, ts: "", level: "INFO", category: "", message: s }
        // timestamp : entre crochets
        var m = s.match(/^\[([^\]]+)\]\s+(\S+)\s*(?:\[([^\]]+)\])?\s*(.*)$/)
        if (m) {
            entry.ts = m[1]
            entry.level = (m[2] || "INFO").toUpperCase()
            entry.category = m[3] || ""
            entry.message = m[4] || ""
        }
        return entry
    }

    function levelMatches(lvl) {
        if (root.filterLevel === "ALL") return true
        if (root.filterLevel === "WARN") return lvl === "WARN" || lvl === "WARNING"
        if (root.filterLevel === "ERROR") return lvl === "ERROR" || lvl === "CRITICAL" || lvl === "FATAL"
        return lvl === root.filterLevel
    }

    function lineMatches(entry) {
        if (!levelMatches(entry.level)) return false
        if (!root.filterText) return true
        var f = root.filterText.toLowerCase()
        return entry.raw.toLowerCase().indexOf(f) !== -1
    }

    function compareEntries(a, b) {
        var k = root.sortColumn
        var av = String(a[k] || "")
        var bv = String(b[k] || "")
        if (k === "level") {
            var rank = { "DEBUG":0, "INFO":1, "WARN":2, "WARNING":2, "ERROR":3, "CRITICAL":4, "FATAL":5 }
            av = rank[av] !== undefined ? rank[av] : -1
            bv = rank[bv] !== undefined ? rank[bv] : -1
        }
        if (av < bv) return root.sortDescending ? 1 : -1
        if (av > bv) return root.sortDescending ? -1 : 1
        return 0
    }

    // ── Reload complet depuis LogManager ──
    function reload() {
        if (typeof logManager === 'undefined') return
        var raw = logManager.getRecentLogs() || []
        var parsed = []
        for (var i = 0; i < raw.length; i++) {
            var e = parseLine(raw[i])
            if (lineMatches(e)) parsed.push(e)
        }
        parsed.sort(compareEntries)
        logModel.clear()
        for (var j = 0; j < parsed.length; j++) logModel.append(parsed[j])
        if (autoScroll) logView.positionViewAtEnd()
        countLabel.text = parsed.length + " / " + raw.length
    }

    // ── Append incrémental (signal newLogEntry) ──
    function appendLine(raw) {
        if (root.paused) return
        var e = parseLine(raw)
        if (!lineMatches(e)) return
        // Ajout en queue (les nouveaux logs arrivent par ordre chrono → cohérent avec tri ts asc).
        // Si tri custom différent → on déclenche un reload léger.
        if (sortColumn !== "ts" || sortDescending) {
            reloadDebounce.restart()
            return
        }
        logModel.append(e)
        if (logModel.count > maxRows) logModel.remove(0, logModel.count - maxRows)
        if (autoScroll) logView.positionViewAtEnd()
        countLabel.text = logModel.count + " entries"
    }

    Timer {
        id: reloadDebounce
        interval: 200; repeat: false
        onTriggered: root.reload()
    }

    Connections {
        target: typeof logManager !== 'undefined' ? logManager : null
        function onNewLogEntry(entry) { root.appendLine(entry) }
    }

    Component.onCompleted: reload()
    onVisibleChanged: if (visible) reload()

    // ────────────────────────────────────────────────────────────
    //  Layout principal
    // ────────────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing12
        spacing: Theme.spacing8

        // ── Barre titre + compteur ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing12
            Text {
                text: "Logs runtime"
                color: Theme.textPrimary
                font.family: Theme.fontMono
                font.pixelSize: 18
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            Text {
                id: countLabel
                text: "0"
                color: Theme.textSecondary
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontSmall
            }
        }

        // ── Toolbar : filtre, niveau, actions ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing8

            // Filtre texte
            Rectangle {
                Layout.preferredWidth: 280
                Layout.preferredHeight: 30
                color: Theme.bgSecondary
                radius: Theme.radiusSmall
                border.color: filterField.activeFocus ? Theme.accent : Theme.border
                TextInput {
                    id: filterField
                    anchors.fill: parent
                    anchors.leftMargin: 8; anchors.rightMargin: 8
                    verticalAlignment: TextInput.AlignVCenter
                    color: Theme.textPrimary
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSmall
                    onTextChanged: { root.filterText = text; reloadDebounce.restart() }
                    Text {
                        anchors.fill: parent
                        verticalAlignment: Text.AlignVCenter
                        text: "Filtrer (texte, catégorie, message)…"
                        color: Theme.textMuted
                        font: parent.font
                        visible: !filterField.text && !filterField.activeFocus
                    }
                }
            }

            // Niveau
            ComboBox {
                id: levelCombo
                Layout.preferredWidth: 120
                Layout.preferredHeight: 30
                model: ["ALL", "DEBUG", "INFO", "WARN", "ERROR"]
                currentIndex: 0
                onActivated: { root.filterLevel = currentText; root.reload() }
            }

            // Tri
            ComboBox {
                id: sortCombo
                Layout.preferredWidth: 160
                Layout.preferredHeight: 30
                model: ["Tri: timestamp", "Tri: niveau", "Tri: catégorie", "Tri: message"]
                currentIndex: 0
                onActivated: {
                    root.sortColumn = ["ts", "level", "category", "message"][currentIndex]
                    root.reload()
                }
            }

            Button {
                text: root.sortDescending ? "↓" : "↑"
                Layout.preferredWidth: 36
                Layout.preferredHeight: 30
                ToolTip.visible: hovered
                ToolTip.text: root.sortDescending ? "Décroissant" : "Croissant"
                onClicked: { root.sortDescending = !root.sortDescending; root.reload() }
            }

            Item { Layout.fillWidth: true }

            CheckBox {
                text: "Auto-scroll"
                checked: root.autoScroll
                onToggled: root.autoScroll = checked
                contentItem: Text {
                    text: parent.text
                    color: Theme.textPrimary
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSmall
                    leftPadding: parent.indicator.width + 6
                    verticalAlignment: Text.AlignVCenter
                }
            }

            Button {
                text: root.paused ? "Reprendre" : "Pause"
                Layout.preferredHeight: 30
                onClicked: root.paused = !root.paused
            }

            Button {
                text: "Copier tout"
                Layout.preferredHeight: 30
                onClicked: {
                    var lines = []
                    for (var i = 0; i < logModel.count; i++)
                        lines.push(logModel.get(i).raw)
                    var blob = lines.join("\n")
                    if (typeof logManager !== 'undefined') logManager.copyToClipboard(blob)
                }
            }

            Button {
                text: "Vider"
                Layout.preferredHeight: 30
                onClicked: {
                    if (typeof logManager !== 'undefined') logManager.clearLogs()
                    logModel.clear()
                    countLabel.text = "0"
                }
            }

            Button {
                text: "Rafraîchir"
                Layout.preferredHeight: 30
                onClicked: root.reload()
            }
        }

        // ── En-tête colonnes ──
        Rectangle {
            Layout.fillWidth: true
            height: 28
            color: Theme.bgSecondary
            radius: Theme.radiusSmall
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8; anchors.rightMargin: 8
                spacing: 0
                Text {
                    text: "TIMESTAMP"; Layout.preferredWidth: 180
                    color: Theme.textSecondary; font.family: Theme.fontMono
                    font.pixelSize: Theme.fontMicro; font.bold: true
                    MouseArea {
                        anchors.fill: parent
                        onClicked: { root.sortColumn = "ts"; root.reload() }
                    }
                }
                Text {
                    text: "NIVEAU"; Layout.preferredWidth: 70
                    color: Theme.textSecondary; font.family: Theme.fontMono
                    font.pixelSize: Theme.fontMicro; font.bold: true
                    MouseArea {
                        anchors.fill: parent
                        onClicked: { root.sortColumn = "level"; root.reload() }
                    }
                }
                Text {
                    text: "CATÉGORIE"; Layout.preferredWidth: 110
                    color: Theme.textSecondary; font.family: Theme.fontMono
                    font.pixelSize: Theme.fontMicro; font.bold: true
                    MouseArea {
                        anchors.fill: parent
                        onClicked: { root.sortColumn = "category"; root.reload() }
                    }
                }
                Text {
                    text: "MESSAGE"; Layout.fillWidth: true
                    color: Theme.textSecondary; font.family: Theme.fontMono
                    font.pixelSize: Theme.fontMicro; font.bold: true
                    MouseArea {
                        anchors.fill: parent
                        onClicked: { root.sortColumn = "message"; root.reload() }
                    }
                }
            }
        }

        // ── Liste ──
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.bgSecondary
            radius: Theme.radiusSmall
            border.color: Theme.border

            ListView {
                id: logView
                anchors.fill: parent
                anchors.margins: 4
                model: logModel
                clip: true
                cacheBuffer: 200
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                boundsBehavior: Flickable.StopAtBounds

                delegate: Rectangle {
                    width: ListView.view.width
                    height: 22
                    color: index % 2 === 0 ? "transparent" : Qt.rgba(1,1,1,0.02)

                    function levelColor(l) {
                        switch (l) {
                            case "DEBUG":    return Theme.textMuted
                            case "INFO":     return Theme.textPrimary
                            case "WARN":
                            case "WARNING":  return Theme.warning
                            case "ERROR":
                            case "CRITICAL":
                            case "FATAL":    return Theme.error
                            default:         return Theme.textSecondary
                        }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 4; anchors.rightMargin: 4
                        spacing: 0
                        Text {
                            text: model.ts
                            Layout.preferredWidth: 180
                            color: Theme.textSecondary
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontMicro
                            elide: Text.ElideRight
                        }
                        Text {
                            text: model.level
                            Layout.preferredWidth: 70
                            color: levelColor(model.level)
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontMicro
                            font.bold: true
                        }
                        Text {
                            text: model.category
                            Layout.preferredWidth: 110
                            color: Theme.accentLight
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontMicro
                            elide: Text.ElideRight
                        }
                        Text {
                            text: model.message
                            Layout.fillWidth: true
                            color: levelColor(model.level)
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontMicro
                            elide: Text.ElideRight
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        onClicked: function(mouse) {
                            if (mouse.button === Qt.RightButton) {
                                rowMenu.rawText = model.raw
                                rowMenu.popup()
                            }
                        }
                        onDoubleClicked: {
                            if (typeof logManager !== 'undefined')
                                logManager.copyToClipboard(model.raw)
                        }
                    }
                }
            }

            // Menu contextuel ligne
            Menu {
                id: rowMenu
                property string rawText: ""
                MenuItem {
                    text: "Copier la ligne"
                    onTriggered: {
                        if (typeof logManager !== 'undefined')
                            logManager.copyToClipboard(rowMenu.rawText)
                    }
                }
                MenuItem {
                    text: "Filtrer sur cette catégorie"
                    onTriggered: {
                        var m = rowMenu.rawText.match(/\[[^\]]+\]\s+\S+\s+\[([^\]]+)\]/)
                        if (m && m[1]) { filterField.text = m[1]; }
                    }
                }
            }
        }

        // ── Footer hint ──
        Text {
            text: "Double-clic = copier la ligne · Clic droit = menu · Clic en-tête = trier"
            color: Theme.textMuted
            font.family: Theme.fontMono
            font.pixelSize: Theme.fontMicro
        }
    }
}
