import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  FloorPlanProperties — panneau de propriétés dynamique
//
//  Affiche/édite les propriétés de l'item sélectionné :
//   type, position, taille, rotation,
//   propriétés dynamiques (QVariantMap),
//   linkedDeviceId.
// ═══════════════════════════════════════════════════════

Rectangle {
    id: propPanel
    color: Theme.bgSecondary
    border.color: Theme.border
    border.width: 1
    clip: true

    // ── Injections ──
    property var controller: null     // FloorPlanController
    property var floorModel: null     // FloorPlanModel
    property var networkIntegration: null  // SpatialNetworkIntegration

    // ── Selected data (refreshed on selectionChanged) ──
    property var selectedData: null
    property string selectedId: ""

    // ── Computed ──
    property int selCount: controller ? controller.selectedIds.length : 0

    Connections {
        target: controller
        function onSelectionChanged() { refreshData() }
    }

    Connections {
        target: floorModel
        function onItemUpdated(id) {
            if (id === selectedId) refreshData()
        }
    }

    function refreshData() {
        if (!controller || !floorModel) { selectedData = null; return }
        var ids = controller.selectedIds
        if (ids.length === 1) {
            selectedId = ids[0]
            selectedData = floorModel.getItemData(ids[0])
            loadFields()
        } else {
            selectedId = ""
            selectedData = null
        }
    }

    function loadFields() {
        if (!selectedData) return
        fieldType.text    = selectedData.type || ""
        fieldX.text       = String(Math.round((selectedData.x || 0) * 100) / 100)
        fieldY.text       = String(Math.round((selectedData.y || 0) * 100) / 100)
        fieldW.text       = String(Math.round((selectedData.width || 0) * 100) / 100)
        fieldH.text       = String(Math.round((selectedData.height || 0) * 100) / 100)
        fieldRot.text     = String(Math.round((selectedData.rotation || 0) * 10) / 10)
        fieldDevice.text  = selectedData.linkedDeviceId || ""
        fieldName.text    = (selectedData.properties && selectedData.properties.name)
                            ? selectedData.properties.name : ""
    }

    function commitChanges() {
        if (!controller || !selectedId) return
        var data = {
            x: parseFloat(fieldX.text) || 0,
            y: parseFloat(fieldY.text) || 0,
            width:  parseFloat(fieldW.text)  || 10,
            height: parseFloat(fieldH.text)  || 10,
            rotation: parseFloat(fieldRot.text) || 0
        }
        controller.updateItemWithUndo(selectedId, data)
    }

    function commitName() {
        if (!floorModel || !selectedId) return
        var d = floorModel.getItemData(selectedId)
        if (!d) return
        var props = d.properties || {}
        props.name = fieldName.text
        floorModel.setItemData(selectedId, {properties: props})
    }

    function commitDevice() {
        if (!floorModel || !selectedId) return
        if (fieldDevice.text.length > 0)
            floorModel.linkDevice(selectedId, fieldDevice.text)
        else
            floorModel.unlinkDevice(selectedId)
    }

    // ══════════════════════════════════════════════
    //  LAYOUT
    // ══════════════════════════════════════════════

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacing8
        spacing: Theme.spacing8

        // ── Header ──
        Text {
            text: selCount === 0 ? "Propriétés"
                : selCount === 1 ? "Propriétés"
                : (selCount + " éléments")
            font.pixelSize: Theme.fontH3
            font.weight: Font.SemiBold
            color: Theme.textPrimary
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

        // ══════ No selection ══════
        Text {
            visible: selCount === 0
            text: "Sélectionnez un élément\npour voir ses propriétés."
            font.pixelSize: Theme.fontSmall
            color: Theme.textMuted
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        // ══════ Single selection ══════
        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: singleCol.height
            clip: true
            visible: selCount === 1

            ColumnLayout {
                id: singleCol
                width: parent.width
                spacing: Theme.spacing6

                // Type
                PropLabel { text: "Type" }
                Text {
                    id: fieldType
                    font.pixelSize: Theme.fontBody
                    font.weight: Font.Medium
                    color: Theme.accent
                }

                // Name (for rooms, furniture, etc.)
                PropLabel { text: "Nom" }
                PropInput {
                    id: fieldName
                    onEditingFinished: commitName()
                }

                // Position
                PropLabel { text: "Position" }
                RowLayout {
                    spacing: Theme.spacing4
                    Text { text: "X"; font.pixelSize: Theme.fontTiny; color: Theme.textMuted }
                    PropInput { id: fieldX; Layout.preferredWidth: 70; onEditingFinished: commitChanges() }
                    Text { text: "Y"; font.pixelSize: Theme.fontTiny; color: Theme.textMuted }
                    PropInput { id: fieldY; Layout.preferredWidth: 70; onEditingFinished: commitChanges() }
                }

                // Size
                PropLabel { text: "Taille" }
                RowLayout {
                    spacing: Theme.spacing4
                    Text { text: "L"; font.pixelSize: Theme.fontTiny; color: Theme.textMuted }
                    PropInput { id: fieldW; Layout.preferredWidth: 70; onEditingFinished: commitChanges() }
                    Text { text: "H"; font.pixelSize: Theme.fontTiny; color: Theme.textMuted }
                    PropInput { id: fieldH; Layout.preferredWidth: 70; onEditingFinished: commitChanges() }
                }

                // Rotation
                PropLabel { text: "Rotation (°)" }
                RowLayout {
                    spacing: Theme.spacing4
                    PropInput {
                        id: fieldRot
                        Layout.preferredWidth: 80
                        onEditingFinished: commitChanges()
                    }
                    // Quick rotation buttons
                    Repeater {
                        model: [{angle: -90, label: "−90°"}, {angle: -45, label: "−45°"},
                                {angle:  45, label: "+45°"}, {angle:  90, label: "+90°"}]
                        Rectangle {
                            required property var modelData
                            Layout.preferredWidth: 36
                            Layout.preferredHeight: 24
                            radius: Theme.radiusSmall
                            color: rotBtnMa.containsMouse ? Theme.bgHover : Theme.bgInput
                            Text {
                                anchors.centerIn: parent
                                text: modelData.label
                                font.pixelSize: Theme.fontMicro
                                color: Theme.textSecondary
                            }
                            MouseArea {
                                id: rotBtnMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var cur = parseFloat(fieldRot.text) || 0
                                    var newAngle = cur + modelData.angle
                                    if (controller && selectedId)
                                        controller.applyRotation(selectedId, newAngle)
                                }
                            }
                        }
                    }
                }

                // Separator
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border; Layout.topMargin: Theme.spacing8 }

                // Dynamic properties display
                PropLabel { text: "Propriétés" }
                Repeater {
                    model: {
                        if (!selectedData || !selectedData.properties) return []
                        var keys = Object.keys(selectedData.properties)
                        var result = []
                        for (var i = 0; i < keys.length; ++i) {
                            if (keys[i] !== "name")
                                result.push({key: keys[i], value: String(selectedData.properties[keys[i]])})
                        }
                        return result
                    }

                    RowLayout {
                        required property var modelData
                        spacing: Theme.spacing4
                        Text {
                            text: modelData.key + ":"
                            font.pixelSize: Theme.fontTiny
                            font.family: Theme.fontMono
                            color: Theme.textMuted
                            Layout.preferredWidth: 80
                        }
                        Text {
                            text: modelData.value
                            font.pixelSize: Theme.fontTiny
                            font.family: Theme.fontMono
                            color: Theme.textSecondary
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }
                    }
                }

                // Separator
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border; Layout.topMargin: Theme.spacing8 }

                // Linked device
                PropLabel { text: "Appareil lié" }
                RowLayout {
                    spacing: Theme.spacing4
                    PropInput {
                        id: fieldDevice
                        Layout.fillWidth: true
                        placeholderText: "device-id"
                        onEditingFinished: commitDevice()
                    }
                }

                // Link indicator
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 28
                    radius: Theme.radiusSmall
                    visible: fieldDevice.text.length > 0
                    color: Theme.successDim
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacing8
                        spacing: Theme.spacing4
                        Text { text: "🔗"; font.pixelSize: 12 }
                        Text {
                            text: "Lié à " + fieldDevice.text
                            font.pixelSize: Theme.fontMicro
                            color: Theme.success
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                }

                // ── Device info (from networkIntegration provider) ──
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    visible: fieldDevice.text.length > 0 && propPanel.networkIntegration !== null

                    property var devInfo: {
                        if (!propPanel.networkIntegration || fieldDevice.text.length === 0) return null
                        return propPanel.networkIntegration.getDeviceById(fieldDevice.text)
                    }

                    Repeater {
                        model: {
                            var info = parent.devInfo
                            if (!info) return []
                            var rows = []
                            if (info.vendor)   rows.push({ k: "Vendor",   v: info.vendor })
                            if (info.protocol) rows.push({ k: "Protocol", v: info.protocol })
                            if (info.ip)       rows.push({ k: "IP",       v: info.ip })
                            if (info.rssi !== undefined) rows.push({ k: "RSSI", v: info.rssi + " dBm" })
                            if (info.latency !== undefined) rows.push({ k: "Latence", v: info.latency + " ms" })
                            if (info.online !== undefined)  rows.push({ k: "État", v: info.online ? "en ligne" : "hors ligne" })
                            return rows
                        }
                        RowLayout {
                            required property var modelData
                            spacing: Theme.spacing4
                            Text {
                                text: modelData.k + ":"
                                font.pixelSize: Theme.fontTiny
                                font.family: Theme.fontMono
                                color: Theme.textMuted
                                Layout.preferredWidth: 60
                            }
                            Text {
                                text: modelData.v
                                font.pixelSize: Theme.fontTiny
                                font.family: Theme.fontMono
                                color: Theme.textSecondary
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }
                    }
                }

                // ── Device picker button ──
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 28
                    radius: Theme.radiusSmall
                    visible: propPanel.networkIntegration !== null
                    color: devPickMa.containsMouse ? Theme.bgHover : "transparent"
                    border.color: Theme.accent
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "📡 Choisir un appareil…"
                        font.pixelSize: Theme.fontMicro
                        color: Theme.accent
                    }

                    MouseArea {
                        id: devPickMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: devicePickerPopup.open()
                    }
                }

                // Unlink button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 28
                    radius: Theme.radiusSmall
                    visible: fieldDevice.text.length > 0
                    color: unlinkMa.containsMouse ? Theme.bgHover : "transparent"
                    border.color: Theme.border
                    Text {
                        anchors.centerIn: parent
                        text: "Délier l'appareil"
                        font.pixelSize: Theme.fontMicro
                        color: Theme.textSecondary
                    }
                    MouseArea {
                        id: unlinkMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { fieldDevice.text = ""; commitDevice() }
                    }
                }

                // Separator
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border; Layout.topMargin: Theme.spacing8 }

                // Delete
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 32
                    radius: Theme.radiusMedium
                    color: delMa.containsMouse ? Theme.errorDim : "transparent"
                    border.color: Theme.error
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "⊘ Supprimer"
                        font.pixelSize: Theme.fontSmall
                        color: Theme.error
                    }
                    MouseArea {
                        id: delMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { if (controller) controller.deleteSelected() }
                    }
                }
            }
        }

        // ══════ Multi selection ══════
        ColumnLayout {
            Layout.fillWidth: true
            visible: selCount > 1
            spacing: Theme.spacing8

            Text {
                text: selCount + " éléments sélectionnés"
                font.pixelSize: Theme.fontBody
                color: Theme.textSecondary
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 32
                radius: Theme.radiusMedium
                color: delMultiMa.containsMouse ? Theme.errorDim : "transparent"
                border.color: Theme.error; border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: "⊘ Supprimer la sélection"
                    font.pixelSize: Theme.fontSmall
                    color: Theme.error
                }
                MouseArea {
                    id: delMultiMa
                    anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { if (controller) controller.deleteSelected() }
                }
            }
        }

        Item { Layout.fillHeight: true }
    }

    // ═══════════════════════════════════════════════════
    //  Composants internes
    // ═══════════════════════════════════════════════════

    // ── Device Picker Popup ──
    Popup {
        id: devicePickerPopup
        anchors.centerIn: Overlay.overlay
        width: 320
        height: 360
        modal: true
        clip: true

        background: Rectangle {
            color: Theme.bgSecondary
            border.color: Theme.border
            radius: Theme.radiusMedium
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Theme.spacing8
            spacing: Theme.spacing8

            Text {
                text: "Sélectionner un appareil"
                font.pixelSize: Theme.fontH3
                font.weight: Font.SemiBold
                color: Theme.textPrimary
            }

            TextField {
                id: deviceSearchField
                Layout.fillWidth: true
                placeholderText: "Rechercher…"
                font.pixelSize: Theme.fontSmall
                color: Theme.textPrimary
                background: Rectangle {
                    color: Theme.bgInput; radius: Theme.radiusSmall
                    border.color: deviceSearchField.activeFocus ? Theme.borderFocus : Theme.border
                }
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: {
                    if (!propPanel.networkIntegration) return []
                    var devs = propPanel.networkIntegration.networkDevices
                    var q = deviceSearchField.text.toLowerCase()
                    if (q.length === 0) return devs
                    var filtered = []
                    for (var i = 0; i < devs.length; i++) {
                        var d = devs[i]
                        var str = ((d.name || "") + " " + (d.ip || "") + " " + (d.vendor || "")).toLowerCase()
                        if (str.indexOf(q) >= 0) filtered.push(d)
                    }
                    return filtered
                }

                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: ListView.view.width
                    height: 42
                    color: devItemMa.containsMouse ? Theme.bgHover : "transparent"
                    radius: Theme.radiusSmall

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacing4
                        spacing: Theme.spacing8

                        Rectangle {
                            width: 8; height: 8; radius: 4
                            color: modelData.online ? Theme.success : Theme.textMuted
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            Text {
                                text: modelData.name || modelData.ip || modelData.id
                                font.pixelSize: Theme.fontSmall
                                color: Theme.textPrimary
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Text {
                                text: (modelData.vendor || "") + " • " + (modelData.protocol || "")
                                font.pixelSize: Theme.fontTiny
                                color: Theme.textMuted
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                    }

                    MouseArea {
                        id: devItemMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            fieldDevice.text = modelData.id
                            commitDevice()
                            devicePickerPopup.close()
                        }
                    }
                }
            }
        }
    }

    component PropLabel: Text {
        font.pixelSize: Theme.fontLabel
        color: Theme.textSecondary
    }

    component PropInput: TextInput {
        property string placeholderText: ""
        font.pixelSize: Theme.fontSmall
        font.family: Theme.fontMono
        color: Theme.textPrimary
        selectionColor: Theme.accent

        Text {
            visible: parent.text.length === 0 && !parent.activeFocus
            text: parent.placeholderText
            font: parent.font
            color: Theme.textMuted
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            color: "transparent"
            border.color: parent.activeFocus ? Theme.borderFocus : Theme.border
            border.width: 1
            radius: 3
            z: -1
        }
    }
}
