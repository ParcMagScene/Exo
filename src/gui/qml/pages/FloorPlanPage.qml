import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

import "../components"
import "../floorplan"

// ─── Page Plans de maison ────────────────────────────────

Item {
    id: floorPlanPage

    opacity: 0
    Component.onCompleted: { fadeIn.start(); loadPlans() }
    NumberAnimation { id: fadeIn; target: floorPlanPage; property: "opacity"; to: 1; duration: 400; easing.type: Easing.OutCubic }

    property var plansData: []
    property int currentPlanIndex: 0

    function loadPlans() {
        try {
            var json = Bridge.getFloorPlans()
            var data = JSON.parse(json)
            plansData = data.plans || []
        } catch(e) {
            plansData = []
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        // ─── En-tête ─────────────────────────────────────

        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            Text {
                text: "🗺️ Plans de la maison"
                font.pixelSize: 22
                font.bold: true
                color: Theme.textPrimary
            }

            Item { Layout.fillWidth: true }

            AnimatedButton {
                label: "Ajouter un plan"
                icon: "➕"
                primary: true
                onClicked: addPlanDialog.open()
            }
        }

        // ─── Onglets des plans ───────────────────────────

        Row {
            Layout.fillWidth: true
            spacing: 8
            visible: plansData.length > 0

            Repeater {
                model: plansData

                Rectangle {
                    width: planLabel.implicitWidth + 32
                    height: 36
                    radius: 18
                    color: currentPlanIndex === index ? Theme.primary : Theme.card

                    Text {
                        id: planLabel
                        anchors.centerIn: parent
                        text: modelData.name || "Plan " + (index + 1)
                        font.pixelSize: 13
                        color: currentPlanIndex === index ? "#fff" : Theme.textSecondary
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: currentPlanIndex = index
                    }
                }
            }
        }

        // ─── Zone du plan (canvas) ───────────────────────

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.radiusLarge
            color: Theme.card
            clip: true

            // Message si pas de plan
            Column {
                anchors.centerIn: parent
                spacing: 16
                visible: plansData.length === 0

                Text {
                    text: "🏠"
                    font.pixelSize: 64
                    anchors.horizontalCenter: parent.horizontalCenter
                }
                Text {
                    text: "Aucun plan configuré"
                    font.pixelSize: 18
                    color: Theme.textSecondary
                    anchors.horizontalCenter: parent.horizontalCenter
                }
                Text {
                    text: "Cliquez sur « Ajouter un plan » pour commencer"
                    font.pixelSize: 13
                    color: Theme.textMuted
                    anchors.horizontalCenter: parent.horizontalCenter
                }
            }

            // Plan interactif (Flickable pour pan + zoom)
            Flickable {
                id: planView
                anchors.fill: parent
                anchors.margins: 8
                clip: true
                contentWidth: planImage.width * planScale
                contentHeight: planImage.height * planScale
                visible: plansData.length > 0 && currentPlanIndex < plansData.length

                property real planScale: 1.0

                Image {
                    id: planImage
                    source: {
                        if (plansData.length > 0 && currentPlanIndex < plansData.length) {
                            var img = plansData[currentPlanIndex].image || ""
                            return img ? "file:///" + img : ""
                        }
                        return ""
                    }
                    fillMode: Image.PreserveAspectFit
                    width: sourceSize.width > 0 ? sourceSize.width : planView.width
                    height: sourceSize.height > 0 ? sourceSize.height : planView.height
                    transform: Scale {
                        origin.x: 0; origin.y: 0
                        xScale: planView.planScale
                        yScale: planView.planScale
                    }

                    // Appareils positionnés sur le plan
                    Repeater {
                        model: {
                            if (plansData.length > 0 && currentPlanIndex < plansData.length) {
                                return plansData[currentPlanIndex].devices || []
                            }
                            return []
                        }

                        DeviceMarker {
                            x: modelData.x * planImage.width - 16
                            y: modelData.y * planImage.height - 16
                            entityId: modelData.entity_id || ""
                            planId: plansData[currentPlanIndex] ? plansData[currentPlanIndex].id : ""

                            onMoved: function(newX, newY) {
                                var relX = (newX + 16) / planImage.width
                                var relY = (newY + 16) / planImage.height
                                Bridge.moveDeviceOnPlan(planId, entityId, relX, relY)
                                loadPlans()
                            }
                        }
                    }
                }

                // Zoom avec molette / pinch
                MouseArea {
                    anchors.fill: parent
                    propagateComposedEvents: true
                    onWheel: function(wheel) {
                        var delta = wheel.angleDelta.y / 120
                        planView.planScale = Math.max(0.3, Math.min(5.0, planView.planScale + delta * 0.15))
                    }
                }
            }
        }
    }

    // ─── Dialog ajouter un plan ──────────────────────────

    Dialog {
        id: addPlanDialog
        title: "Nouveau plan"
        anchors.centerIn: parent
        width: 400
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel

        background: Rectangle {
            color: Theme.surface
            radius: Theme.radiusLarge
            border.color: Theme.surfaceVariant
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 16

            Text {
                text: "Nom du plan"
                font.pixelSize: 14
                color: Theme.textPrimary
            }

            TextField {
                id: planNameField
                Layout.fillWidth: true
                placeholderText: "Ex: Rez-de-chaussée"
                color: Theme.textPrimary
                background: Rectangle {
                    color: Theme.card
                    radius: Theme.radiusSmall
                    border.color: Theme.surfaceVariant
                }
            }

            Text {
                text: "Image du plan (chemin absolu)"
                font.pixelSize: 14
                color: Theme.textPrimary
            }

            TextField {
                id: planImageField
                Layout.fillWidth: true
                placeholderText: "C:/Plans/rdc.png"
                color: Theme.textPrimary
                background: Rectangle {
                    color: Theme.card
                    radius: Theme.radiusSmall
                    border.color: Theme.surfaceVariant
                }
            }
        }

        onAccepted: {
            if (planNameField.text) {
                Bridge.addFloorPlan(planNameField.text, planImageField.text)
                loadPlans()
                planNameField.text = ""
                planImageField.text = ""
            }
        }
    }
}
