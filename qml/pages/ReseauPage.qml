import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  ReseauPage v2 — Carte réseau dynamique (NetworkMap v2)
//  Graph topologie, latence, classification, interactions
// ═══════════════════════════════════════════════════════

Item {
    id: root

    // ── Données injectées depuis MainWindow ──
    property var nodes: []       // [{mac, ip, vendor, name, type, online, latency_ms, is_gateway, is_exo}]
    property var links: []       // [{from_id, to_id, type, latency_ms}]
    property bool scanning: false
    property var selectedNode: null
    property string filterType: ""  // filtre par type

    signal scanRequested()
    signal scanFastRequested()
    signal nodeClicked(var node)

    // Types filtrables
    readonly property var deviceTypes: [
        "", "router", "pc", "phone", "tv", "camera",
        "speaker", "light", "plug", "nas", "printer", "iot", "unknown"
    ]

    // Nœuds filtrés
    property var filteredNodes: {
        if (!filterType) return root.nodes;
        var result = [];
        for (var i = 0; i < root.nodes.length; i++) {
            if (root.nodes[i].type === filterType) result.push(root.nodes[i]);
        }
        return result;
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing12
        spacing: Theme.spacing12

        // ── En-tête ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing8

            Text {
                text: "📶  Réseau"
                font.pixelSize: Theme.fontH1
                font.weight: Font.Bold
                color: Theme.textPrimary
            }

            Text {
                text: root.nodes.length + " appareils"
                font.pixelSize: Theme.fontSmall
                color: Theme.textMuted
                Layout.alignment: Qt.AlignBottom
            }

            Item { Layout.fillWidth: true }

            // Filtre par type
            ComboBox {
                id: typeFilter
                model: root.deviceTypes
                displayText: currentText || "Tous"
                implicitWidth: 120
                onCurrentTextChanged: root.filterType = currentText
            }

            // Scan rapide
            Rectangle {
                width: fastLabel.implicitWidth + 24
                height: 34
                radius: Theme.radiusLarge
                color: root.scanning ? Theme.bgActive : Theme.bgElevated
                border.color: Theme.border

                Text {
                    id: fastLabel
                    anchors.centerIn: parent
                    text: "⚡ Rapide"
                    font.pixelSize: Theme.fontSmall
                    color: Theme.textPrimary
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: root.scanning ? Qt.WaitCursor : Qt.PointingHandCursor
                    enabled: !root.scanning
                    onClicked: root.scanFastRequested()
                }
            }

            // Scan complet
            Rectangle {
                width: scanLabel.implicitWidth + 24
                height: 34
                radius: Theme.radiusLarge
                color: root.scanning ? Theme.bgActive : Theme.accent
                border.color: Theme.border

                Text {
                    id: scanLabel
                    anchors.centerIn: parent
                    text: root.scanning ? "Scan…" : "🔍 Scan complet"
                    font.pixelSize: Theme.fontSmall
                    color: "#FFF"
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: root.scanning ? Qt.WaitCursor : Qt.PointingHandCursor
                    enabled: !root.scanning
                    onClicked: root.scanRequested()
                }
            }
        }

        // ── Zone graphe réseau ──
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.radiusXL
            color: Theme.bgSecondary
            border.color: Theme.border
            clip: true

            Canvas {
                id: networkCanvas
                anchors.fill: parent
                anchors.margins: 20

                property var nodePositions: ({})

                onPaint: {
                    var ctx = getContext("2d");
                    ctx.reset();
                    var w = width;
                    var h = height;

                    var displayNodes = root.filteredNodes;

                    if (displayNodes.length === 0) {
                        ctx.fillStyle = Theme.textMuted.toString();
                        ctx.font = "14px sans-serif";
                        ctx.textAlign = "center";
                        ctx.fillText("Cliquer « Scan complet » pour détecter les appareils", w / 2, h / 2);
                        return;
                    }

                    // Compute positions (circular layout centré sur le routeur)
                    var positions = {};
                    var gatewayIdx = -1;
                    for (var i = 0; i < displayNodes.length; i++) {
                        if (displayNodes[i].type === "router" || displayNodes[i].is_gateway) {
                            gatewayIdx = i;
                            break;
                        }
                    }

                    var cx = w / 2;
                    var cy = h / 2;
                    var radius = Math.min(w, h) * 0.38;

                    // Place gateway at center
                    if (gatewayIdx >= 0) {
                        var gw = displayNodes[gatewayIdx];
                        positions[gw.mac || gw.ip] = { x: cx, y: cy };
                    }

                    // Place others in circle
                    var otherNodes = [];
                    for (var j = 0; j < displayNodes.length; j++) {
                        if (j !== gatewayIdx) otherNodes.push(displayNodes[j]);
                    }
                    for (var k = 0; k < otherNodes.length; k++) {
                        var angle = (2 * Math.PI * k) / otherNodes.length - Math.PI / 2;
                        var nx = cx + radius * Math.cos(angle);
                        var ny = cy + radius * Math.sin(angle);
                        positions[otherNodes[k].mac || otherNodes[k].ip] = { x: nx, y: ny };
                    }

                    nodePositions = positions;

                    // Draw links with latency
                    for (var li = 0; li < root.links.length; li++) {
                        var link = root.links[li];
                        var p1 = positions[link.from_id];
                        var p2 = positions[link.to_id];
                        if (!p1 || !p2) continue;

                        ctx.beginPath();
                        ctx.moveTo(p1.x, p1.y);
                        ctx.lineTo(p2.x, p2.y);

                        // Couleur selon type
                        if (link.type === "eth") {
                            ctx.strokeStyle = Theme.info.toString();
                            ctx.lineWidth = 2.5;
                            ctx.setLineDash([]);
                        } else if (link.type === "iot") {
                            ctx.strokeStyle = Theme.warning ? Theme.warning.toString() : "#FFA500";
                            ctx.lineWidth = 1;
                            ctx.setLineDash([2, 4]);
                        } else {
                            ctx.strokeStyle = Theme.textMuted.toString();
                            ctx.lineWidth = 1.5;
                            ctx.setLineDash([4, 4]);
                        }
                        ctx.stroke();
                        ctx.setLineDash([]);

                        // Afficher latence sur le lien
                        if (link.latency_ms !== undefined && link.latency_ms !== null) {
                            var mx = (p1.x + p2.x) / 2;
                            var my = (p1.y + p2.y) / 2;
                            ctx.fillStyle = Theme.textMuted.toString();
                            ctx.font = "9px sans-serif";
                            ctx.textAlign = "center";
                            ctx.fillText(link.latency_ms + "ms", mx, my - 4);
                        }
                    }

                    // Draw nodes
                    var nodeIcons = {
                        "router": "📶", "pc": "💻", "phone": "📱",
                        "tv": "📺", "speaker": "🔈", "camera": "📷",
                        "nas": "💾", "light": "💡", "plug": "🔌",
                        "printer": "🖨️", "iot": "📡", "unknown": "❓"
                    };

                    for (var ni = 0; ni < displayNodes.length; ni++) {
                        var node = displayNodes[ni];
                        var pos = positions[node.mac || node.ip];
                        if (!pos) continue;

                        var icon = nodeIcons[node.type] || "❓";
                        var isGateway = node.type === "router" || node.is_gateway;
                        var isExo = node.is_exo || false;
                        var isSelected = root.selectedNode &&
                            (root.selectedNode.ip === node.ip || root.selectedNode.mac === node.mac);

                        // Node circle
                        ctx.beginPath();
                        var nodeRadius = isGateway ? 28 : (isExo ? 24 : 20);
                        ctx.arc(pos.x, pos.y, nodeRadius, 0, 2 * Math.PI);

                        if (isSelected) {
                            ctx.fillStyle = Theme.accent.toString();
                        } else if (!node.online) {
                            ctx.fillStyle = Theme.errorDim ? Theme.errorDim.toString() : "#442222";
                        } else if (isGateway) {
                            ctx.fillStyle = Theme.accent.toString();
                        } else if (isExo) {
                            ctx.fillStyle = Theme.success ? Theme.success.toString() : "#22AA44";
                        } else {
                            ctx.fillStyle = Theme.bgElevated.toString();
                        }
                        ctx.fill();

                        ctx.strokeStyle = isSelected
                            ? "#FFFFFF"
                            : (node.online ? Theme.border.toString()
                               : (Theme.error ? Theme.error.toString() : "#FF4444"));
                        ctx.lineWidth = isSelected ? 2.5 : 1.5;
                        ctx.stroke();

                        // Icon
                        ctx.fillStyle = "#FFF";
                        ctx.font = (isGateway ? "18px" : "14px") + " sans-serif";
                        ctx.textAlign = "center";
                        ctx.textBaseline = "middle";
                        ctx.fillText(icon, pos.x, pos.y);

                        // Label below
                        var label = node.name || node.hostname || node.ip || node.mac;
                        if (label.length > 18) label = label.substring(0, 16) + "…";
                        ctx.fillStyle = Theme.textSecondary.toString();
                        ctx.font = "11px sans-serif";
                        ctx.fillText(label, pos.x, pos.y + nodeRadius + 14);

                        // Latence below label
                        if (node.latency_ms !== undefined && node.latency_ms !== null) {
                            var latColor = node.latency_ms < 5 ? "#44BB66"
                                         : node.latency_ms < 20 ? "#BBBB44"
                                         : "#BB4444";
                            ctx.fillStyle = latColor;
                            ctx.font = "9px sans-serif";
                            ctx.fillText(node.latency_ms + "ms", pos.x, pos.y + nodeRadius + 26);
                        }
                    }
                }

                // Click detection
                MouseArea {
                    anchors.fill: parent
                    onClicked: function(mouse) {
                        var positions = networkCanvas.nodePositions;
                        var displayNodes = root.filteredNodes;
                        for (var i = 0; i < displayNodes.length; i++) {
                            var node = displayNodes[i];
                            var pos = positions[node.mac || node.ip];
                            if (!pos) continue;
                            var dx = mouse.x - pos.x;
                            var dy = mouse.y - pos.y;
                            if (dx * dx + dy * dy < 25 * 25) {
                                root.selectedNode = node;
                                root.nodeClicked(node);
                                networkCanvas.requestPaint();
                                return;
                            }
                        }
                        // Click elsewhere: deselect
                        root.selectedNode = null;
                        networkCanvas.requestPaint();
                    }
                }
            }

            // Redraw when data changes
            Connections {
                target: root
                function onNodesChanged() { networkCanvas.requestPaint(); }
                function onLinksChanged() { networkCanvas.requestPaint(); }
                function onSelectedNodeChanged() { networkCanvas.requestPaint(); }
                function onFilterTypeChanged() { networkCanvas.requestPaint(); }
            }
        }

        // ── Panneau détails appareil sélectionné ──
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.selectedNode ? 80 : 0
            visible: root.selectedNode !== null
            radius: Theme.radiusLarge
            color: Theme.bgElevated
            border.color: Theme.accent

            RowLayout {
                anchors.fill: parent
                anchors.margins: Theme.spacing12
                spacing: Theme.spacing12
                visible: root.selectedNode !== null

                ColumnLayout {
                    spacing: 2
                    Text {
                        text: root.selectedNode ? (root.selectedNode.name || root.selectedNode.hostname || "Inconnu") : ""
                        font.pixelSize: Theme.fontBody
                        font.weight: Font.Bold
                        color: Theme.textPrimary
                    }
                    Text {
                        text: root.selectedNode ? ("IP: " + (root.selectedNode.ip || "—") + "  MAC: " + (root.selectedNode.mac || "—")) : ""
                        font.pixelSize: Theme.fontSmall
                        color: Theme.textSecondary
                    }
                }

                ColumnLayout {
                    spacing: 2
                    Text {
                        text: root.selectedNode ? ("Vendor: " + (root.selectedNode.vendor || "—")) : ""
                        font.pixelSize: Theme.fontSmall
                        color: Theme.textSecondary
                    }
                    Text {
                        text: root.selectedNode ? ("Type: " + (root.selectedNode.type || "—") + "  Latence: " + (root.selectedNode.latency_ms !== undefined && root.selectedNode.latency_ms !== null ? root.selectedNode.latency_ms + "ms" : "—")) : ""
                        font.pixelSize: Theme.fontSmall
                        color: Theme.textSecondary
                    }
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    width: 8; height: 8; radius: 4
                    color: root.selectedNode && root.selectedNode.online ? Theme.success : Theme.error
                    Layout.alignment: Qt.AlignVCenter
                }
            }
        }

        // ── Tableau récapitulatif ──
        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: 180
            clip: true

            ListView {
                model: root.filteredNodes
                spacing: 2

                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: ListView.view.width
                    height: 32
                    color: {
                        if (root.selectedNode && root.selectedNode.ip === modelData.ip)
                            return Theme.accent + "33";
                        return index % 2 === 0 ? Theme.bgSecondary : Theme.bgPrimary;
                    }
                    radius: 2

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.selectedNode = modelData;
                            root.nodeClicked(modelData);
                        }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacing8
                        anchors.rightMargin: Theme.spacing8
                        spacing: Theme.spacing12

                        // Online dot
                        Rectangle {
                            width: 8; height: 8; radius: 4
                            color: modelData.online ? Theme.success : Theme.error
                            Layout.alignment: Qt.AlignVCenter
                        }

                        Text {
                            text: modelData.name || modelData.hostname || "—"
                            font.pixelSize: Theme.fontSmall
                            color: Theme.textPrimary
                            Layout.preferredWidth: 140
                            elide: Text.ElideRight
                        }
                        Text {
                            text: modelData.ip || "—"
                            font.pixelSize: Theme.fontSmall
                            color: Theme.textSecondary
                            Layout.preferredWidth: 110
                        }
                        Text {
                            text: modelData.mac || "—"
                            font.pixelSize: Theme.fontCaption
                            color: Theme.textMuted
                            Layout.preferredWidth: 130
                        }
                        Text {
                            text: modelData.vendor || ""
                            font.pixelSize: Theme.fontCaption
                            color: Theme.textMuted
                            Layout.preferredWidth: 100
                            elide: Text.ElideRight
                        }
                        Text {
                            text: modelData.type || ""
                            font.pixelSize: Theme.fontCaption
                            color: Theme.accent
                            Layout.preferredWidth: 55
                        }
                        Text {
                            text: modelData.latency_ms !== undefined && modelData.latency_ms !== null
                                  ? modelData.latency_ms + "ms" : "—"
                            font.pixelSize: Theme.fontCaption
                            color: {
                                var lat = modelData.latency_ms;
                                if (lat === undefined || lat === null) return Theme.textMuted;
                                return lat < 5 ? "#44BB66" : lat < 20 ? "#BBBB44" : "#BB4444";
                            }
                            Layout.preferredWidth: 50
                        }
                    }
                }
            }
        }
    }
}
