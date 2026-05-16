import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"
import "../core"

// ═══════════════════════════════════════════════════════════════
//  DevelopmentPageExpert — Services, Stability & Debug
//  MODE EXPERT uniquement
// ═══════════════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    property int readyCount: 14
    property int failedCount: 1
    property int degradedCount: 2
    property int totalCount: 17

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ExoPanelHeader {
            title: SettingsLabels.t("dev.title")
            subtitle: SettingsLabels.t("dev.subtitle")
        }

        TabBar {
            id: tabBar
            Layout.fillWidth: true
            background: Rectangle {
                color: Theme.bgSecondary
                border.color: Theme.border
                border.width: 1
            }

            TabButton {
                text: SettingsLabels.t("dev.tabServices")
                contentItem: Text {
                    text: parent.text
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSmall
                    color: parent.checked ? Theme.accent : Theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
            TabButton {
                text: SettingsLabels.t("dev.tabStability")
                contentItem: Text {
                    text: parent.text
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSmall
                    color: parent.checked ? Theme.accent : Theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
            TabButton {
                text: SettingsLabels.t("dev.tabConfig")
                contentItem: Text {
                    text: parent.text
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSmall
                    color: parent.checked ? Theme.accent : Theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
            TabButton {
                text: SettingsLabels.t("dev.tabDebug")
                contentItem: Text {
                    text: parent.text
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSmall
                    color: parent.checked ? Theme.accent : Theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabBar.currentIndex

            // Services
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing12

                    // Status summary
                    GridLayout {
                        columns: 2
                        columnSpacing: Theme.spacing12
                        rowSpacing: Theme.spacing12
                        Layout.fillWidth: true

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.success
                            border.width: 2
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: SettingsLabels.t("dev.ready")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.success
                                    font.bold: true
                                }

                                Text {
                                    text: root.readyCount + "/" + root.totalCount
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.success
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.error
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: SettingsLabels.t("dev.failed")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.error
                                }

                                Text {
                                    text: root.failedCount
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.error
                                    font.bold: true
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.warning
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: SettingsLabels.t("dev.degraded")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.warning
                                }

                                Text {
                                    text: root.degradedCount
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.warning
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            color: Theme.bgSecondary
                            border.color: Theme.border
                            border.width: 1
                            radius: Theme.radiusSmall

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacing8
                                spacing: Theme.spacing4

                                Text {
                                    text: SettingsLabels.t("common.total")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.accent
                                    font.bold: true
                                }

                                Text {
                                    text: root.totalCount
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontLarge
                                    color: Theme.textPrimary
                                }
                            }
                        }
                    }

                    // Services list
                    Text {
                        text: SettingsLabels.t("dev.detailedState")
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSmall
                        color: Theme.accent
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: Theme.bgSecondary
                        border.color: Theme.border
                        border.width: 1
                        radius: Theme.radiusSmall

                        Flickable {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing8
                            contentWidth: width
                            contentHeight: servicesCol.height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            ColumnLayout {
                                id: servicesCol
                                width: parent.width
                                spacing: Theme.spacing6

                                Repeater {
                                    model: [
                                        {name: "STT Server", port: "8766", status: "ready"},
                                        {name: "TTS Server", port: "8767", status: "ready"},
                                        {name: "VAD Server", port: "8768", status: "ready"},
                                        {name: "Wakeword Server", port: "8770", status: "failed"},
                                        {name: "Memory Service", port: "8771", status: "degraded"}
                                    ]

                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 36
                                        color: Theme.bgPrimary
                                        border.color: modelData.status === "ready" ? Theme.success :
                                                      modelData.status === "failed" ? Theme.error : Theme.warning
                                        border.width: 1
                                        radius: Theme.radiusSmall

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: Theme.spacing6
                                            spacing: Theme.spacing8

                                            Rectangle {
                                                width: 8
                                                height: 8
                                                radius: 4
                                                color: modelData.status === "ready" ? Theme.success :
                                                        modelData.status === "failed" ? Theme.error : Theme.warning
                                            }

                                            Text {
                                                text: modelData.name
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontSmall
                                                color: Theme.textPrimary
                                            }

                                            Item { Layout.fillWidth: true }

                                            Text {
                                                text: modelData.port
                                                font.family: Theme.fontMono
                                                font.pixelSize: Theme.fontMicro
                                                color: Theme.textSecondary
                                            }
                                        }
                                    }
                                }

                                Item { Layout.fillHeight: true }
                            }

                            ScrollBar.vertical: ScrollBar {
                                policy: ScrollBar.AsNeeded
                            }
                        }
                    }
                }
            }

            // Stabilité
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("dev.stabilityTests")
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSmall
                        color: Theme.accent
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: Theme.bgSecondary
                        border.color: Theme.border
                        border.width: 1
                        radius: Theme.radiusSmall

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing12
                            spacing: Theme.spacing8

                            ExoButton {
                                Layout.fillWidth: true
                                text: "▶ Stress Test (100 requêtes)"
                                onClicked: console.log("Starting stress test")
                            }

                            ExoButton {
                                Layout.fillWidth: true
                                text: "▶ Memory Leak Check"
                                onClicked: console.log("Starting memory check")
                            }

                            ExoButton {
                                Layout.fillWidth: true
                                text: "▶ Reconnection Test"
                                onClicked: console.log("Starting reconnection test")
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 100
                                color: Theme.bgPrimary
                                border.color: Theme.border
                                border.width: 1
                                radius: Theme.radiusSmall

                                Text {
                                    anchors.centerIn: parent
                                    text: SettingsLabels.t("dev.lastTestPassed")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.success
                                    textFormat: Text.PlainText
                                    horizontalAlignment: Text.AlignHCenter
                                }
                            }

                            Item { Layout.fillHeight: true }
                        }
                    }
                }
            }

            // Configuration
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("dev.configFile")
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSmall
                        color: Theme.accent
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: Theme.bgSecondary
                        border.color: Theme.border
                        border.width: 1
                        radius: Theme.radiusSmall

                        Flickable {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing8
                            contentWidth: width
                            contentHeight: configCol.height
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds

                            ColumnLayout {
                                id: configCol
                                width: parent.width
                                spacing: Theme.spacing4

                                Text {
                                    text: "[Audio]"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.accent
                                }

                                Text {
                                    text: SettingsLabels.t("dev.cfgAudioBackend")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.textSecondary
                                }

                                Text {
                                    text: SettingsLabels.t("dev.cfgAgcEnabled")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.textSecondary
                                }

                                Text {
                                    text: ""
                                    font.pixelSize: Theme.fontMicro
                                }

                                Text {
                                    text: "[UI]"
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.accent
                                }

                                Text {
                                    text: SettingsLabels.t("dev.cfgExpertMode")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: Theme.success
                                }

                                Item { Layout.fillHeight: true }
                            }

                            ScrollBar.vertical: ScrollBar {
                                policy: ScrollBar.AsNeeded
                            }
                        }
                    }
                }
            }

            // Debug
            Rectangle {
                color: Theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacing12
                    spacing: Theme.spacing8

                    Text {
                        text: SettingsLabels.t("dev.debugTools")
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSmall
                        color: Theme.accent
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: Theme.bgSecondary
                        border.color: Theme.border
                        border.width: 1
                        radius: Theme.radiusSmall

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacing12
                            spacing: Theme.spacing8

                            ExoButton {
                                Layout.fillWidth: true
                                text: "📋 Dump Memory Profile"
                                onClicked: memoryDumpPopup.open()
                            }

                            ExoButton {
                                Layout.fillWidth: true
                                text: "🧹 Forcer GC (collecte manuelle)"
                                onClicked: {
                                    if (typeof gc === 'function') {
                                        gc();
                                        memoryDumpPopup.open();
                                    } else {
                                        Qt.callLater(function() {
                                            memoryDumpPopup.open();
                                        });
                                    }
                                }
                            }

                            Popup {
                                id: memoryDumpPopup
                                modal: true
                                focus: true
                                width: 600
                                height: 400
                                background: Rectangle {
                                    color: Theme.bgElevated
                                    radius: Theme.radiusSmall
                                    border.color: Theme.accent
                                    border.width: 2
                                }
                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: Theme.spacing12
                                    spacing: Theme.spacing8
                                    Text {
                                        text: SettingsLabels.t("dev.qmlMemoryState")
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontLarge
                                        color: Theme.accent
                                    }
                                    TextArea {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        readOnly: true
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontTiny
                                        text: memoryDump()
                                    }
                                    ExoButton {
                                        Layout.alignment: Qt.AlignHCenter
                                        text: SettingsLabels.t("common.close")
                                        onClicked: memoryDumpPopup.close()
                                    }
                                }
                            }

                            function memoryDump() {
                                var out = [];
                                out.push("Objets QML vivants (synthétique):");
                                out.push("- root: " + root);
                                if (typeof Qt !== 'undefined' && Qt.binding) {
                                    out.push("- Qt.binding présent (Qt version: " + Qt.version + ")");
                                }
                                out.push("- Timers actifs: (non exhaustif)");
                                if (typeof animTimer !== 'undefined') out.push("  - animTimer running=" + animTimer.running);
                                if (typeof saveGeometryTimer !== 'undefined') out.push("  - saveGeometryTimer running=" + saveGeometryTimer.running);
                                out.push("- Loaders dynamiques:");
                                if (typeof loader11 !== 'undefined') out.push("  - loader11 active=" + loader11.active);
                                if (typeof loader12 !== 'undefined') out.push("  - loader12 active=" + loader12.active);
                                if (typeof loader13 !== 'undefined') out.push("  - loader13 active=" + loader13.active);
                                if (typeof loader14 !== 'undefined') out.push("  - loader14 active=" + loader14.active);
                                if (typeof loader15 !== 'undefined') out.push("  - loader15 active=" + loader15.active);
                                if (typeof loader16 !== 'undefined') out.push("  - loader16 active=" + loader16.active);
                                out.push("- (Pour un dump complet, utiliser l'inspecteur QML natif)");
                                return out.join("\n");
                            }

                            ExoButton {
                                Layout.fillWidth: true
                                text: "📊 Exporter les Métriques"
                                onClicked: console.log("Exporting metrics")
                            }

                            ExoButton {
                                Layout.fillWidth: true
                                text: "🔧 Réinitialiser le Cache"
                                onClicked: console.log("Resetting cache")
                            }

                            ExoButton {
                                Layout.fillWidth: true
                                text: "🔄 Redémarrer tous les services"
                                onClicked: console.log("Restarting services")
                            }

                            Item { Layout.fillHeight: true }
                        }
                    }
                }
            }
        }
    }
}
