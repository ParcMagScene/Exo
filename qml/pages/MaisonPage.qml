import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../core"

// ═══════════════════════════════════════════════════════
//  MaisonPage — Vue Maison Connectée (Domotique v2)
//  Affiche les pièces, appareils, commandes rapides et scénarios
// ═══════════════════════════════════════════════════════

Item {
    id: root

    // ── Données injectées depuis MainWindow ──
    property var rooms: []          // [{id, name, device_ids}]
    property var devices: []        // [{id_exo, name, type, room_id, state, online, source}]
    property var scenarios: []      // [{name, description, builtin}]
    property string selectedRoom: "" // filtre pièce active ("" = toutes)

    signal deviceCommand(string deviceId, string command, var params)
    signal refreshRequested()
    signal scenarioRequested(string name)

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing12
        spacing: Theme.spacing12

        // ── En-tête ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing8

            Text {
                text: "🏠  Maison"
                font.pixelSize: Theme.fontXL
                font.weight: Font.Bold
                color: Theme.textPrimary
            }

            Item { Layout.fillWidth: true }

            // Bouton refresh
            Rectangle {
                width: 36; height: 36
                radius: Theme.radius8
                color: refreshMa.containsMouse ? Theme.bgHover : "transparent"
                border.color: Theme.border
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: "⟳"
                    font.pixelSize: 18
                    color: Theme.textSecondary
                }
                MouseArea {
                    id: refreshMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.refreshRequested()
                }
            }
        }

        // ── Barre de pièces (filtre) ──
        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            ScrollBar.horizontal.policy: ScrollBar.AsNeeded
            ScrollBar.vertical.policy: ScrollBar.AlwaysOff

            Row {
                spacing: Theme.spacing8

                // "Tout"
                Rectangle {
                    width: labelAll.implicitWidth + 24
                    height: 32
                    radius: Theme.radius8
                    color: root.selectedRoom === "" ? Theme.accent : Theme.bgElevated
                    border.color: Theme.border

                    Text {
                        id: labelAll
                        anchors.centerIn: parent
                        text: SettingsLabels.t("common.all")
                        font.pixelSize: Theme.fontSM
                        color: root.selectedRoom === "" ? "#FFF" : Theme.textSecondary
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.selectedRoom = ""
                    }
                }

                Repeater {
                    model: root.rooms
                    delegate: Rectangle {
                        required property var modelData
                        width: labelRoom.implicitWidth + 24
                        height: 32
                        radius: Theme.radius8
                        color: root.selectedRoom === modelData.id ? Theme.accent : Theme.bgElevated
                        border.color: Theme.border

                        Text {
                            id: labelRoom
                            anchors.centerIn: parent
                            text: modelData.name
                            font.pixelSize: Theme.fontSM
                            color: root.selectedRoom === modelData.id ? "#FFF" : Theme.textSecondary
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.selectedRoom = modelData.id
                        }
                    }
                }
            }
        }

        // ── Grille d'appareils ──
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            GridLayout {
                width: parent.width
                columns: Math.max(1, Math.floor(parent.width / 220))
                columnSpacing: Theme.spacing12
                rowSpacing: Theme.spacing12

                Repeater {
                    model: root.devices.filter(function(d) {
                        return root.selectedRoom === "" || d.room_id === root.selectedRoom;
                    })

                    delegate: Rectangle {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: 140
                        radius: Theme.radius12
                        color: Theme.bgElevated
                        border.color: modelData.online ? Theme.border : Theme.errorDim
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing12
                            spacing: Theme.spacing4

                            // Icône + nom
                            RowLayout {
                                spacing: Theme.spacing8
                                Text {
                                    text: {
                                        var icons = {
                                            "light": "💡", "plug": "🔌", "camera": "📷",
                                            "tv": "📺", "soundbar": "🔊", "speaker": "🔈",
                                            "heater": "🌡️", "sensor": "📡", "router": "📶",
                                            "pc": "💻", "phone": "📱", "nas": "💾"
                                        };
                                        return icons[modelData.type] || "❓";
                                    }
                                    font.pixelSize: 24
                                }
                                ColumnLayout {
                                    spacing: 0
                                    Text {
                                        text: modelData.name
                                        font.pixelSize: Theme.fontMD
                                        font.weight: Font.DemiBold
                                        color: Theme.textPrimary
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        text: modelData.source
                                        font.pixelSize: Theme.fontXS
                                        color: Theme.textMuted
                                    }
                                }
                            }

                            // État
                            Text {
                                text: {
                                    var s = modelData.state || {};
                                    var parts = [];
                                    if (s.on !== undefined) parts.push(s.on ? "Allumé" : "Éteint");
                                    if (s.brightness !== undefined) parts.push(s.brightness + "%");
                                    if (s.temperature !== undefined) parts.push(s.temperature + "°C");
                                    if (s.volume !== undefined) parts.push("Vol " + s.volume);
                                    if (s.mode !== undefined) parts.push(s.mode);
                                    return parts.join(" · ") || "—";
                                }
                                font.pixelSize: Theme.fontSM
                                color: Theme.textSecondary
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            Item { Layout.fillHeight: true }

                            // Boutons rapides
                            RowLayout {
                                spacing: Theme.spacing4
                                Layout.fillWidth: true

                                // Toggle ON/OFF
                                Rectangle {
                                    visible: (modelData.capabilities || []).indexOf("on_off") !== -1
                                    width: 60; height: 28
                                    radius: Theme.radius8
                                    color: (modelData.state && modelData.state.on)
                                           ? Theme.success : Theme.bgActive
                                    Text {
                                        anchors.centerIn: parent
                                        text: (modelData.state && modelData.state.on) ? "ON" : "OFF"
                                        font.pixelSize: Theme.fontXS
                                        font.weight: Font.Bold
                                        color: "#FFF"
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            var isOn = modelData.state && modelData.state.on;
                                            root.deviceCommand(
                                                modelData.id_exo,
                                                isOn ? "turn_off" : "turn_on",
                                                {}
                                            );
                                        }
                                    }
                                }

                                // Online indicator
                                Rectangle {
                                    width: 8; height: 8
                                    radius: 4
                                    color: modelData.online ? Theme.success : Theme.error
                                    Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                                }
                            }
                        }
                    }
                }
            }
        }

        // ── Pied de page : statistiques ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacing16

            Text {
                text: root.devices.length + " appareils"
                font.pixelSize: Theme.fontSM
                color: Theme.textMuted
            }
            Text {
                text: root.devices.filter(function(d) { return d.online; }).length + " en ligne"
                font.pixelSize: Theme.fontSM
                color: Theme.success
            }
            Text {
                text: root.rooms.length + " pièces"
                font.pixelSize: Theme.fontSM
                color: Theme.textMuted
            }
        }

        // ── v2: Scénarios rapides ──
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: scenariosCol.implicitHeight + Theme.spacing12 * 2
            radius: Theme.radius12
            color: Theme.bgElevated
            border.color: Theme.border
            visible: root.scenarios.length > 0

            ColumnLayout {
                id: scenariosCol
                anchors.fill: parent
                anchors.margins: Theme.spacing12
                spacing: Theme.spacing8

                Text {
                    text: "🎬  Scénarios"
                    font.pixelSize: Theme.fontMD
                    font.weight: Font.DemiBold
                    color: Theme.textPrimary
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8

                    Repeater {
                        model: root.scenarios
                        delegate: Rectangle {
                            required property var modelData
                            width: scenarioLabel.implicitWidth + 24
                            height: 34
                            radius: Theme.radius8
                            color: scenarioMa.containsMouse ? Theme.accent : Theme.bgActive
                            border.color: Theme.border

                            Text {
                                id: scenarioLabel
                                anchors.centerIn: parent
                                text: {
                                    var icons = {
                                        "cinema": "🎬", "nuit": "🌙", "absence": "🔒",
                                        "reveil": "☀️", "securite": "🛡️", "eco": "🌿"
                                    };
                                    return (icons[modelData.name] || "▶") + "  " + modelData.name;
                                }
                                font.pixelSize: Theme.fontSM
                                color: scenarioMa.containsMouse ? "#FFF" : Theme.textSecondary
                            }
                            MouseArea {
                                id: scenarioMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.scenarioRequested(modelData.name)
                            }

                            ToolTip.visible: scenarioMa.containsMouse
                            ToolTip.text: modelData.description || modelData.name
                        }
                    }
                }
            }
        }
    }
}
