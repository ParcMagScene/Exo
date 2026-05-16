import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"
import "../core"

// ═══════════════════════════════════════════════════════════════════
//  EXO — Page Paramètres
//  Sections organisées selon le pipeline d'exécution :
//   1. Entrée audio (Microphone & VAD)
//   2. Reconnaissance vocale (STT)
//   3. Orchestrateur & Mémoire
//   4. Modèle LLM
//   5. Synthèse vocale (TTS)
//   6. Interface & Affichage
//   7. Services externes (Météo, API)
//   8. Diagnostics & Tests
// ═══════════════════════════════════════════════════════════════════
Rectangle {
    id: root
    color: Theme.bgPrimary

    Connections {
        target: typeof configManager !== 'undefined' ? configManager : null

        function onLocationDetected(city, country) {
            if (city && city.length > 0) {
                cityInput.text = city
                if (typeof configManager !== 'undefined')
                    configManager.setWeatherCity(city)
                if (typeof weatherManager !== 'undefined')
                    weatherManager.setCity(city)
            }
            console.log("[Settings] Localisation détectée:", city, country)
        }

        function onLocationDetectionError(error) {
            console.warn("[Settings] Erreur détection localisation:", error)
        }
    }

    Connections {
        target: typeof UIState !== 'undefined' ? UIState : null
        function onExpertModeChanged() {
            console.log("[Settings] Mode expert changé:", UIState.expertMode)
            expertModeToggle.checked = UIState.expertMode
        }
    }

    // ── Composant utilitaire : séparateur visuel entre sections ──
    component SectionSeparator : Rectangle {
        Layout.fillWidth: true
        height: 1
        color: Theme.border
        opacity: 0.4
    }

    // ── Composant utilitaire : titre de section ──
    component SectionTitle : Text {
        font.family: Theme.fontMono
        font.pixelSize: Theme.fontSmall
        font.bold: true
        color: Theme.textPrimary
    }

    // ── Composant utilitaire : libellé de champ ──
    component FieldLabel : Text {
        font.family: Theme.fontMono
        font.pixelSize: Theme.fontCaption
        color: Theme.textSecondary
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ExoPanelHeader {
            title: SettingsLabels.t("app.settingsTitle")
        }

        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: settingsCol.height + Theme.spacing32
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            ColumnLayout {
                id: settingsCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: Theme.marginH
                anchors.rightMargin: Theme.marginH
                y: Theme.spacing16
                spacing: Theme.spacing20

                // ═══════════════════════════════════════════════════
                //  1 ── ENTRÉE AUDIO (Microphone & VAD)
                // ═══════════════════════════════════════════════════
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8

                    SectionTitle { text: "1. Entrée audio (Microphone & VAD)" }

                    // ── Périphérique d'entrée audio ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4

                        FieldLabel { text: SettingsLabels.t("audio.inputDevice") }

                        ComboBox {
                            id: micDeviceCombo
                            Layout.fillWidth: true
                            Layout.preferredHeight: 30
                            model: typeof audioDeviceManager !== 'undefined'
                                   ? audioDeviceManager.inputDevices : []
                            currentIndex: typeof audioDeviceManager !== 'undefined'
                                          ? audioDeviceManager.selectedDeviceIndex : -1

                            onActivated: function(index) {
                                if (typeof audioDeviceManager !== 'undefined')
                                    audioDeviceManager.setInputDevice(index)
                            }

                            Connections {
                                target: typeof audioDeviceManager !== 'undefined' ? audioDeviceManager : null
                                function onDevicesChanged() {
                                    micDeviceCombo.currentIndex = audioDeviceManager.selectedDeviceIndex
                                }
                            }

                            background: Rectangle {
                                color: Theme.bgElevated
                                border.color: micDeviceCombo.hovered ? Theme.borderFocus : Theme.border
                                radius: Theme.radiusSmall
                            }
                            contentItem: Text {
                                leftPadding: Theme.spacing8
                                text: micDeviceCombo.displayText
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontCaption
                                color: Theme.textPrimary
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                            }
                        }
                    }

                    // ── Message d'erreur si aucun micro ──
                    Text {
                        visible: typeof audioDeviceManager !== 'undefined'
                                 && !audioDeviceManager.hasValidInputDevice
                        text: "⚠ Aucun microphone détecté — mode clavier activé"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontMicro
                        color: Theme.error
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    // ── Indicateur état audio ──
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing8

                        Rectangle {
                            width: 10; height: 10; radius: 5
                            color: {
                                if (typeof audioDeviceManager === 'undefined') return Theme.textMuted
                                switch (audioDeviceManager.audioStatus) {
                                    case "healthy": return Theme.success
                                    case "down":    return Theme.error
                                    default:        return Theme.textMuted
                                }
                            }
                        }
                        Text {
                            text: {
                                if (typeof audioDeviceManager === 'undefined') return "Inconnu"
                                switch (audioDeviceManager.audioStatus) {
                                    case "healthy": return "Microphone opérationnel"
                                    case "down":    return "Microphone indisponible"
                                    default:        return "En attente…"
                                }
                            }
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontMicro
                            color: Theme.textSecondary
                        }
                    }

                    // ── VU-mètre niveau micro ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing2

                        FieldLabel { text: SettingsLabels.t("audio.level") }

                        Rectangle {
                            Layout.fillWidth: true
                            height: 8
                            radius: Theme.radiusSmall
                            color: Theme.bgElevated

                            Rectangle {
                                width: {
                                    var rms = typeof audioDeviceManager !== 'undefined'
                                              ? audioDeviceManager.currentRmsLevel : 0
                                    return Math.min(1.0, rms * 3.0) * parent.width
                                }
                                height: parent.height
                                radius: Theme.radiusSmall
                                color: {
                                    var rms = typeof audioDeviceManager !== 'undefined'
                                              ? audioDeviceManager.currentRmsLevel : 0
                                    if (rms > 0.6) return Theme.error
                                    if (rms > 0.3) return Theme.warning
                                    return Theme.success
                                }
                                Behavior on width { NumberAnimation { duration: 60 } }
                            }
                        }
                    }

                    // ── Boutons : Tester le microphone + Source audio Windows ──
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing8

                        Button {
                            text: typeof audioDeviceManager !== 'undefined'
                                  && audioDeviceManager.audioTestRunning
                                  ? "Arrêter le test" : "🎙 Tester le microphone"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 28

                            onClicked: {
                                if (typeof audioDeviceManager === 'undefined') return
                                if (audioDeviceManager.audioTestRunning)
                                    audioDeviceManager.stopAudioTest()
                                else
                                    audioDeviceManager.startAudioTest()
                            }

                            background: Rectangle {
                                color: parent.hovered ? Theme.bgInput : Theme.bgElevated
                                border.color: Theme.accent
                                border.width: 1
                                radius: Theme.radiusSmall
                            }
                            contentItem: Text {
                                text: parent.text
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontMicro
                                color: Theme.textPrimary
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Button {
                            text: "⚙ Source audio Windows"
                            Layout.preferredHeight: 28
                            Layout.preferredWidth: 160

                            onClicked: {
                                if (typeof audioDeviceManager !== 'undefined')
                                    audioDeviceManager.openWindowsSoundSettings()
                            }

                            background: Rectangle {
                                color: parent.hovered ? Theme.bgInput : Theme.bgElevated
                                border.color: Theme.border
                                border.width: 1
                                radius: Theme.radiusSmall
                            }
                            contentItem: Text {
                                text: parent.text
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontMicro
                                color: Theme.textPrimary
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: Theme.border
                        Layout.topMargin: Theme.spacing4
                        Layout.bottomMargin: Theme.spacing4
                    }

                    // ── Système audio (backend Qt / RtAudio) ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4

                        FieldLabel { text: SettingsLabels.t("audio.backend") }

                        ComboBox {
                            id: audioBackendCombo
                            Layout.fillWidth: true
                            Layout.preferredHeight: 30
                            model: ListModel {
                                ListElement { text: "Qt Multimedia"; value: "qt" }
                                ListElement { text: "RtAudio (WASAPI)"; value: "rtaudio" }
                            }
                            textRole: "text"
                            valueRole: "value"

                            Component.onCompleted: {
                                var backend = typeof configManager !== 'undefined'
                                              ? configManager.getString("Audio", "backend", "qt") : "qt"
                                for (var i = 0; i < model.count; i++) {
                                    if (model.get(i).value === backend) {
                                        currentIndex = i
                                        break
                                    }
                                }
                            }

                            onActivated: {
                                var val = model.get(currentIndex).value
                                if (typeof configManager !== 'undefined')
                                    configManager.setUserValue("Audio", "backend", val)
                            }

                            background: Rectangle {
                                color: Theme.bgInput
                                border.color: audioBackendCombo.activeFocus ? Theme.borderFocus : "transparent"
                                radius: Theme.radiusSmall
                            }
                            contentItem: Text {
                                text: audioBackendCombo.displayText
                                color: Theme.textPrimary
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSmall
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: Theme.spacing8
                            }
                        }
                    }

                    // ── Moteur de détection vocale (VAD backend) ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4

                        FieldLabel { text: SettingsLabels.t("vad.engine") }

                        ComboBox {
                            id: vadBackendCombo
                            Layout.fillWidth: true
                            Layout.preferredHeight: 30
                            model: ["builtin", "silero", "hybrid"]

                            Component.onCompleted: {
                                var val = typeof configManager !== 'undefined'
                                          ? configManager.getVADBackend() : "builtin"
                                currentIndex = model.indexOf(val)
                                if (currentIndex < 0) currentIndex = 0
                            }

                            onActivated: {
                                if (typeof configManager !== 'undefined')
                                    configManager.setUserValue("VAD", "backend", currentText)
                            }

                            background: Rectangle {
                                radius: Theme.radiusSmall
                                color: Theme.bgInput
                                border.color: vadBackendCombo.activeFocus ? Theme.borderFocus : "transparent"
                            }
                            contentItem: Text {
                                leftPadding: Theme.spacing8
                                text: vadBackendCombo.displayText
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSmall
                                color: Theme.textPrimary
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    // ── Seuil VAD ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4

                        RowLayout {
                            Layout.fillWidth: true
                            FieldLabel { text: SettingsLabels.t("vad.threshold") }
                            Item { Layout.fillWidth: true }
                            Text {
                                text: vadSlider.value.toFixed(2)
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontCaption
                                color: Theme.warning
                            }
                        }

                        Slider {
                            id: vadSlider
                            Layout.fillWidth: true
                            from: 0.1
                            to: 0.9
                            stepSize: 0.05
                            value: typeof configManager !== 'undefined'
                                   ? configManager.getVADThreshold() : 0.45

                            onMoved: {
                                if (typeof configManager !== 'undefined')
                                    configManager.setUserValue("VAD", "threshold", value.toFixed(2))
                                if (typeof voiceManager !== 'undefined')
                                    voiceManager.setVADThreshold(value)
                            }

                            background: Rectangle {
                                x: vadSlider.leftPadding
                                y: vadSlider.topPadding + vadSlider.availableHeight / 2 - height / 2
                                implicitWidth: 200
                                implicitHeight: 4
                                width: vadSlider.availableWidth
                                height: implicitHeight
                                radius: Theme.radiusSmall
                                color: Theme.bgInput

                                Rectangle {
                                    width: vadSlider.visualPosition * parent.width
                                    height: parent.height
                                    radius: Theme.radiusSmall
                                    color: Theme.accent
                                }
                            }

                            handle: Rectangle {
                                x: vadSlider.leftPadding + vadSlider.visualPosition * (vadSlider.availableWidth - width)
                                y: vadSlider.topPadding + vadSlider.availableHeight / 2 - height / 2
                                implicitWidth: 14
                                implicitHeight: 14
                                radius: 7
                                color: vadSlider.pressed ? "#FFFFFF" : Theme.textSecondary

                                Behavior on color { ColorAnimation { duration: Theme.animFast } }
                            }
                        }
                    }

                    // ── Porte de bruit (noise gate) ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4

                        RowLayout {
                            Layout.fillWidth: true
                            FieldLabel { text: SettingsLabels.t("noise.gate") }
                            Item { Layout.fillWidth: true }
                            Text {
                                text: noiseSlider.value.toFixed(3)
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontCaption
                                color: Theme.warning
                            }
                        }

                        Slider {
                            id: noiseSlider
                            Layout.fillWidth: true
                            from: 0.0
                            to: 0.05
                            stepSize: 0.001
                            value: 0.001

                            Component.onCompleted: {
                                if (typeof configManager !== 'undefined') {
                                    var v = parseFloat(configManager.getString("Audio", "noise_gate", "0.001"))
                                    if (!isNaN(v)) value = v
                                }
                            }
                            onMoved: {
                                if (typeof configManager !== 'undefined')
                                    configManager.setUserValue("Audio", "noise_gate", value.toFixed(3))
                                if (typeof voiceManager !== 'undefined')
                                    voiceManager.setNoiseGate(value)
                            }

                            background: Rectangle {
                                x: noiseSlider.leftPadding
                                y: noiseSlider.topPadding + noiseSlider.availableHeight / 2 - height / 2
                                implicitWidth: 200
                                implicitHeight: 4
                                width: noiseSlider.availableWidth
                                height: implicitHeight
                                radius: Theme.radiusSmall
                                color: Theme.bgInput

                                Rectangle {
                                    width: noiseSlider.visualPosition * parent.width
                                    height: parent.height
                                    radius: Theme.radiusSmall
                                    color: Theme.accent
                                }
                            }

                            handle: Rectangle {
                                x: noiseSlider.leftPadding + noiseSlider.visualPosition * (noiseSlider.availableWidth - width)
                                y: noiseSlider.topPadding + noiseSlider.availableHeight / 2 - height / 2
                                implicitWidth: 14
                                implicitHeight: 14
                                radius: 7
                                color: noiseSlider.pressed ? "#FFFFFF" : Theme.textSecondary

                                Behavior on color { ColorAnimation { duration: Theme.animFast } }
                            }
                        }
                    }

                    // ── Contrôle automatique du gain (AGC) ──
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing8

                        FieldLabel { text: SettingsLabels.t("agc.enabled") }
                        Item { Layout.fillWidth: true }

                        Switch {
                            id: agcSwitch
                            checked: typeof configManager !== 'undefined' ? configManager.getBool("Audio", "agc_enabled", true) : true

                            onToggled: {
                                if (typeof configManager !== 'undefined')
                                    configManager.setUserValue("Audio", "agc_enabled", checked ? "true" : "false")
                                if (typeof voiceManager !== 'undefined')
                                    voiceManager.setAGC(checked)
                            }

                            indicator: Rectangle {
                                implicitWidth: 40
                                implicitHeight: 20
                                x: agcSwitch.leftPadding
                                y: parent.height / 2 - height / 2
                                radius: 10
                                color: agcSwitch.checked ? Theme.accent : Theme.bgInput

                                Behavior on color { ColorAnimation { duration: Theme.animNormal } }

                                Rectangle {
                                    x: agcSwitch.checked ? parent.width - width - 2 : 2
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 16
                                    height: 16
                                    radius: 8
                                    color: "#FFFFFF"

                                    Behavior on x {
                                        NumberAnimation { duration: Theme.animNormal }
                                    }
                                }
                            }
                        }
                    }

                    // ── Réduction de bruit (DSP) ──
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing8

                        FieldLabel { text: SettingsLabels.t("dsp.noiseReduction") }
                        Item { Layout.fillWidth: true }

                        Switch {
                            id: noiseReductionToggle
                            checked: typeof configManager !== 'undefined' ? configManager.getBool("DSP", "noise_reduction_enabled", true) : true
                            onToggled: {
                                if (typeof configManager !== 'undefined')
                                    configManager.setUserValue("DSP", "noise_reduction_enabled",
                                                               checked ? "true" : "false")
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4
                        visible: noiseReductionToggle.checked

                        FieldLabel {
                            text: "Intensité de réduction de bruit : " + dspNoiseSlider.value.toFixed(2)
                        }

                        Slider {
                            id: dspNoiseSlider
                            Layout.fillWidth: true
                            from: 0.0
                            to: 1.0
                            value: 0.7
                            stepSize: 0.05
                            Component.onCompleted: {
                                if (typeof configManager !== 'undefined') {
                                    var v = parseFloat(configManager.getString("DSP", "noise_reduction_strength", "0.70"))
                                    if (!isNaN(v)) value = v
                                }
                            }
                            onMoved: {
                                if (typeof configManager !== 'undefined')
                                    configManager.setUserValue("DSP", "noise_reduction_strength",
                                                               value.toFixed(2))
                            }
                        }
                    }
                }

                SectionSeparator {}

                // ═══════════════════════════════════════════════════
                //  2 ── RECONNAISSANCE VOCALE (STT)
                // ═══════════════════════════════════════════════════
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8

                    SectionTitle { text: "2. Reconnaissance vocale (STT)" }

                    // ── Langue de reconnaissance vocale ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4

                        FieldLabel { text: SettingsLabels.t("stt.language") }

                        ComboBox {
                            id: langCombo
                            Layout.fillWidth: true
                            Layout.preferredHeight: 30
                            model: ListModel {
                                ListElement { text: "Français"; value: "fr" }
                                ListElement { text: "English"; value: "en" }
                                ListElement { text: "Español"; value: "es" }
                                ListElement { text: "Deutsch"; value: "de" }
                                ListElement { text: "Italiano"; value: "it" }
                                ListElement { text: "Português"; value: "pt" }
                                ListElement { text: "日本語"; value: "ja" }
                                ListElement { text: "中文"; value: "zh" }
                            }
                            textRole: "text"
                            valueRole: "value"

                            Component.onCompleted: {
                                var lang = typeof configManager !== 'undefined'
                                           ? configManager.getSTTLanguage() : "fr"
                                for (var i = 0; i < model.count; i++) {
                                    if (model.get(i).value === lang) {
                                        currentIndex = i
                                        break
                                    }
                                }
                            }

                            onActivated: {
                                var val = model.get(currentIndex).value
                                if (typeof configManager !== 'undefined')
                                    configManager.setUserValue("STT", "language", val)
                                if (typeof voiceManager !== 'undefined')
                                    voiceManager.setSTTLanguage(val)
                            }

                            background: Rectangle {
                                radius: Theme.radiusSmall
                                color: Theme.bgInput
                                border.color: langCombo.activeFocus ? Theme.borderFocus : "transparent"
                            }

                            contentItem: Text {
                                leftPadding: Theme.spacing8
                                text: langCombo.displayText
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSmall
                                color: Theme.textPrimary
                                verticalAlignment: Text.AlignVCenter
                            }

                            delegate: ItemDelegate {
                                width: langCombo.width
                                contentItem: Text {
                                    text: model.text
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.textPrimary
                                }
                                background: Rectangle {
                                    color: highlighted ? Theme.accentActive : Theme.bgSecondary
                                }
                            }

                            popup: Popup {
                                y: langCombo.height
                                width: langCombo.width
                                implicitHeight: contentItem.implicitHeight
                                padding: 1

                                contentItem: ListView {
                                    clip: true
                                    implicitHeight: contentHeight
                                    model: langCombo.popup.visible ? langCombo.delegateModel : null
                                    currentIndex: langCombo.highlightedIndex
                                }

                                background: Rectangle {
                                    color: Theme.bgSecondary
                                    border.color: Theme.border
                                    radius: Theme.radiusSmall
                                }
                            }
                        }
                    }

                    // ── Mot-clé d'activation (wake word texte) ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4

                        FieldLabel { text: SettingsLabels.t("assistant.wakeWord") }

                        Rectangle {
                            Layout.fillWidth: true
                            height: 30
                            radius: Theme.radiusSmall
                            color: Theme.bgInput
                            border.color: wakeInput.activeFocus ? Theme.borderFocus : "transparent"

                            Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

                            TextInput {
                                id: wakeInput
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacing8
                                anchors.rightMargin: Theme.spacing8
                                verticalAlignment: TextInput.AlignVCenter
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSmall
                                color: Theme.textPrimary
                                selectByMouse: true
                                selectionColor: Theme.accentActive
                                text: typeof configManager !== 'undefined'
                                      ? configManager.getWakeWord() : "EXO"

                                onAccepted: {
                                    if (typeof configManager !== 'undefined')
                                        configManager.setWakeWord(text)
                                    if (typeof voiceManager !== 'undefined')
                                        voiceManager.setWakeWord(text)
                                }
                                onActiveFocusChanged: {
                                    if (!activeFocus && typeof configManager !== 'undefined') {
                                        configManager.setWakeWord(text)
                                        if (typeof voiceManager !== 'undefined')
                                            voiceManager.setWakeWord(text)
                                    }
                                }
                            }
                        }
                    }

                    // ── Détection neuronale du mot-clé ──
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing8

                        FieldLabel { text: SettingsLabels.t("wakeword.neural") }
                        Item { Layout.fillWidth: true }

                        Switch {
                            id: neuralWakewordToggle
                            checked: typeof configManager !== 'undefined'
                                     ? configManager.getBool("WakeWord", "neural_enabled", false) : false
                            onToggled: {
                                if (typeof configManager !== 'undefined')
                                    configManager.setUserValue("WakeWord", "neural_enabled",
                                                               checked ? "true" : "false")
                            }
                        }
                    }
                }

                SectionSeparator {}

                // ═══════════════════════════════════════════════════
                //  3 ── ORCHESTRATEUR & MÉMOIRE
                // ═══════════════════════════════════════════════════
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8

                    SectionTitle { text: "3. Orchestrateur & Mémoire" }

                    Row {
                        spacing: Theme.spacing16

                        Text {
                            text: typeof memoryManager !== 'undefined'
                                  ? "Conversations enregistrées : " + memoryManager.conversationCount
                                  : "Conversations enregistrées : 0"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontCaption
                            color: Theme.textSecondary
                        }

                        Text {
                            text: typeof memoryManager !== 'undefined'
                                  ? "Souvenirs persistants : " + memoryManager.memoryCount
                                  : "Souvenirs persistants : 0"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontCaption
                            color: Theme.textSecondary
                        }
                    }

                    // ── Mémoire sémantique (FAISS) ──
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing8

                        FieldLabel { text: SettingsLabels.t("memory.semantic") }
                        Item { Layout.fillWidth: true }

                        Switch {
                            id: semanticToggle
                            checked: typeof configManager !== 'undefined'
                                     ? configManager.getBool("Memory", "semantic_enabled", true) : true
                            onToggled: {
                                if (typeof configManager !== 'undefined')
                                    configManager.setUserValue("Memory", "semantic_enabled",
                                                               checked ? "true" : "false")
                            }
                        }
                    }
                }

                SectionSeparator {}

                // ═══════════════════════════════════════════════════
                //  4 ── MODÈLE LLM
                // ═══════════════════════════════════════════════════
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8

                    SectionTitle { text: "4. Modèle LLM (Claude)" }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4

                        FieldLabel { text: SettingsLabels.t("claude.model") }

                        Rectangle {
                            Layout.fillWidth: true
                            height: 30
                            radius: Theme.radiusSmall
                            color: Theme.bgInput

                            Text {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacing8
                                verticalAlignment: Text.AlignVCenter
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSmall
                                color: Theme.warning
                                text: typeof configManager !== 'undefined'
                                      ? configManager.getClaudeModel() : "claude-3-haiku"
                            }
                        }
                    }
                }

                SectionSeparator {}

                // ═══════════════════════════════════════════════════
                //  5 ── SYNTHÈSE VOCALE (TTS)
                // ═══════════════════════════════════════════════════
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8

                    SectionTitle { text: "5. Synthèse vocale (TTS)" }

                    // ── Moteur de synthèse vocale ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4

                        FieldLabel { text: SettingsLabels.t("tts.engine") }

                        ComboBox {
                            id: engineCombo
                            Layout.fillWidth: true
                            Layout.preferredHeight: 30
                            model: ListModel {
                                ListElement { text: "Orpheus 3B FR (CUDA)"; value: "orpheus_cuda" }
                                ListElement { text: "Qt TTS (secours)";    value: "qt_fallback" }
                            }
                            textRole: "text"
                            valueRole: "value"

                            // Synchronise le combo avec le moteur réellement actif côté serveur
                            // via /health (engine = "orpheus-gguf").
                            // Lancé au démarrage et après chaque changement.
                            function syncFromServer() {
                                var xhr = new XMLHttpRequest()
                                xhr.timeout = 1500
                                xhr.onreadystatechange = function() {
                                    if (xhr.readyState !== XMLHttpRequest.DONE) return
                                    if (xhr.status !== 200) return
                                    try {
                                        var h = JSON.parse(xhr.responseText)
                                        var eng = (h.engine || "").toLowerCase()
                                        var target = ""
                                        if (eng.indexOf("orpheus") === 0) target = "orpheus_cuda"
                                        if (!target) return
                                        for (var i = 0; i < engineCombo.model.count; i++) {
                                            if (engineCombo.model.get(i).value === target) {
                                                if (engineCombo.currentIndex !== i)
                                                    engineCombo.currentIndex = i
                                                break
                                            }
                                        }
                                    } catch (e) { /* silencieux */ }
                                }
                                xhr.open("GET", "http://127.0.0.1:8767/health", true)
                                xhr.send()
                            }

                            Component.onCompleted: {
                                var engine = typeof configManager !== 'undefined'
                                             ? configManager.getTTSEngine() : "orpheus_cuda"
                                // Migration auto : valeurs héritées -> Orpheus
                                if (engine.indexOf("cosy") === 0) {
                                    engine = "orpheus_cuda"
                                    if (typeof configManager !== 'undefined')
                                        configManager.setTTSEngine(engine)
                                }
                                for (var i = 0; i < model.count; i++) {
                                    if (model.get(i).value === engine) {
                                        currentIndex = i
                                        break
                                    }
                                }
                                syncFromServer()
                            }

                            onActivated: {
                                var val = model.get(currentIndex).value
                                if (typeof configManager !== 'undefined')
                                    configManager.setTTSEngine(val)
                                if (typeof voiceManager !== 'undefined')
                                    voiceManager.setTTSEngine(val)
                            }

                            background: Rectangle {
                                radius: Theme.radiusSmall
                                color: Theme.bgInput
                                border.color: engineCombo.activeFocus ? Theme.borderFocus : "transparent"
                            }

                            contentItem: Text {
                                leftPadding: Theme.spacing8
                                text: engineCombo.displayText
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontCaption
                                color: Theme.textPrimary
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                            }

                            delegate: ItemDelegate {
                                width: engineCombo.width
                                contentItem: Text {
                                    text: model.text
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontCaption
                                    color: highlighted ? "#FFFFFF" : Theme.textPrimary
                                    verticalAlignment: Text.AlignVCenter
                                }
                                highlighted: engineCombo.highlightedIndex === index
                                background: Rectangle {
                                    color: highlighted ? Theme.accentActive : Theme.bgElevated
                                }
                            }

                            popup: Popup {
                                y: engineCombo.height
                                width: engineCombo.width
                                implicitHeight: contentItem.implicitHeight + 2
                                padding: 1
                                contentItem: ListView {
                                    clip: true
                                    implicitHeight: contentHeight
                                    model: engineCombo.popup.visible ? engineCombo.delegateModel : null
                                    ScrollIndicator.vertical: ScrollIndicator {}
                                }
                                background: Rectangle {
                                    color: Theme.bgElevated
                                    border.color: Theme.borderFocus
                                    radius: Theme.radiusSmall
                                }
                            }
                        }
                    }

                    // ── Voix ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4

                        FieldLabel { text: SettingsLabels.t("tts.voice") }

                        ComboBox {
                            id: voiceCombo
                            Layout.fillWidth: true
                            Layout.preferredHeight: 30
                            model: {
                                if (typeof voiceManager !== 'undefined'
                                    && voiceManager.ttsVoices
                                    && voiceManager.ttsVoices.length > 0)
                                    return voiceManager.ttsVoices
                                return ["fr_denise"]
                            }

                            Component.onCompleted: {
                                if (typeof voiceManager !== 'undefined')
                                    voiceManager.fetchTTSVoices()
                                var voice = typeof configManager !== 'undefined'
                                            ? configManager.getTTSVoice() : "fr_denise"
                                var idx = voiceCombo.model.indexOf(voice)
                                if (idx >= 0) currentIndex = idx
                            }

                            Connections {
                                target: typeof voiceManager !== 'undefined' ? voiceManager : null
                                function onTtsVoicesChanged() {
                                    var voice = typeof configManager !== 'undefined'
                                                ? configManager.getTTSVoice() : "fr_denise"
                                    var idx = voiceCombo.model.indexOf(voice)
                                    if (idx >= 0) voiceCombo.currentIndex = idx
                                }
                            }

                            onActivated: {
                                var val = voiceCombo.model[currentIndex]
                                if (typeof configManager !== 'undefined')
                                    configManager.setUserValue("TTS", "voice", val)
                                if (typeof voiceManager !== 'undefined')
                                    voiceManager.setTTSVoice(val)
                            }

                            background: Rectangle {
                                radius: Theme.radiusSmall
                                color: Theme.bgInput
                                border.color: voiceCombo.activeFocus ? Theme.borderFocus : "transparent"
                            }

                            contentItem: Text {
                                leftPadding: Theme.spacing8
                                text: voiceCombo.displayText
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSmall
                                color: Theme.textPrimary
                                verticalAlignment: Text.AlignVCenter
                            }

                            delegate: ItemDelegate {
                                width: voiceCombo.width
                                contentItem: Text {
                                    text: modelData
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.textPrimary
                                }
                                background: Rectangle {
                                    color: highlighted ? Theme.accentActive : Theme.bgSecondary
                                }
                            }

                            popup: Popup {
                                y: voiceCombo.height
                                width: voiceCombo.width
                                implicitHeight: contentItem.implicitHeight
                                padding: 1

                                contentItem: ListView {
                                    clip: true
                                    implicitHeight: contentHeight
                                    model: voiceCombo.popup.visible ? voiceCombo.delegateModel : null
                                    currentIndex: voiceCombo.highlightedIndex
                                }

                                background: Rectangle {
                                    color: Theme.bgSecondary
                                    border.color: Theme.border
                                    radius: Theme.radiusSmall
                                }
                            }
                        }
                    }

                    // ── Tonalité + Vitesse de parole (côte à côte) ──
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing8

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing4

                            RowLayout {
                                Layout.fillWidth: true
                                FieldLabel { text: SettingsLabels.t("tts.pitch") }
                                Item { Layout.fillWidth: true }
                                Text {
                                    id: pitchValueText
                                    text: pitchSlider.value.toFixed(2)
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontCaption
                                    color: Theme.textPrimary
                                }
                            }

                            Slider {
                                id: pitchSlider
                                Layout.fillWidth: true
                                from: 0.8
                                to: 1.2
                                value: 1.0
                                stepSize: 0.05

                                Component.onCompleted: {
                                    if (typeof configManager !== 'undefined') {
                                        var v = parseFloat(configManager.getString("TTS", "pitch", "1.0"))
                                        if (!isNaN(v)) value = v
                                    }
                                }
                                onMoved: {
                                    if (typeof configManager !== 'undefined')
                                        configManager.setUserValue("TTS", "pitch", value.toFixed(2))
                                    if (typeof voiceManager !== 'undefined')
                                        voiceManager.setTTSPitch(value)
                                }

                                background: Rectangle {
                                    x: pitchSlider.leftPadding
                                    y: pitchSlider.topPadding + pitchSlider.availableHeight / 2 - height / 2
                                    implicitWidth: 200
                                    implicitHeight: 4
                                    width: pitchSlider.availableWidth
                                    height: implicitHeight
                                    radius: Theme.radiusSmall
                                    color: Theme.bgInput
                                    Rectangle {
                                        width: pitchSlider.visualPosition * parent.width
                                        height: parent.height
                                        color: Theme.accent
                                        radius: Theme.radiusSmall
                                    }
                                }

                                handle: Rectangle {
                                    x: pitchSlider.leftPadding + pitchSlider.visualPosition * (pitchSlider.availableWidth - width)
                                    y: pitchSlider.topPadding + pitchSlider.availableHeight / 2 - height / 2
                                    implicitWidth: 14
                                    implicitHeight: 14
                                    radius: 7
                                    color: pitchSlider.pressed ? Theme.accentLight : Theme.accent
                                }
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing4

                            RowLayout {
                                Layout.fillWidth: true
                                FieldLabel { text: SettingsLabels.t("tts.rate") }
                                Item { Layout.fillWidth: true }
                                Text {
                                    id: rateValueText
                                    text: rateSlider.value.toFixed(2)
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontCaption
                                    color: Theme.textPrimary
                                }
                            }

                            Slider {
                                id: rateSlider
                                Layout.fillWidth: true
                                from: 0.8
                                to: 1.2
                                value: 1.0
                                stepSize: 0.05

                                Component.onCompleted: {
                                    if (typeof configManager !== 'undefined') {
                                        var v = parseFloat(configManager.getString("TTS", "rate", "1.0"))
                                        if (!isNaN(v)) value = v
                                    }
                                }
                                onMoved: {
                                    if (typeof configManager !== 'undefined')
                                        configManager.setUserValue("TTS", "rate", value.toFixed(2))
                                    if (typeof voiceManager !== 'undefined')
                                        voiceManager.setTTSRate(value)
                                }

                                background: Rectangle {
                                    x: rateSlider.leftPadding
                                    y: rateSlider.topPadding + rateSlider.availableHeight / 2 - height / 2
                                    implicitWidth: 200
                                    implicitHeight: 4
                                    width: rateSlider.availableWidth
                                    height: implicitHeight
                                    radius: Theme.radiusSmall
                                    color: Theme.bgInput
                                    Rectangle {
                                        width: rateSlider.visualPosition * parent.width
                                        height: parent.height
                                        color: Theme.accent
                                        radius: Theme.radiusSmall
                                    }
                                }

                                handle: Rectangle {
                                    x: rateSlider.leftPadding + rateSlider.visualPosition * (rateSlider.availableWidth - width)
                                    y: rateSlider.topPadding + rateSlider.availableHeight / 2 - height / 2
                                    implicitWidth: 14
                                    implicitHeight: 14
                                    radius: 7
                                    color: rateSlider.pressed ? Theme.accentLight : Theme.accent
                                }
                            }
                        }
                    }

                    // ── Style vocal + Langue de synthèse (côte à côte) ──
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing8

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing4

                            FieldLabel { text: SettingsLabels.t("tts.style") }

                            ComboBox {
                                id: styleCombo
                                Layout.fillWidth: true
                                Layout.preferredHeight: 30
                                model: ["neutral", "conversational"]
                                currentIndex: 0

                                Component.onCompleted: {
                                    if (typeof configManager !== 'undefined') {
                                        var saved = configManager.getString("TTS", "style", "neutral")
                                        var idx = model.indexOf(saved)
                                        if (idx >= 0) currentIndex = idx
                                    }
                                }
                                onActivated: {
                                    var val = model[currentIndex]
                                    if (typeof configManager !== 'undefined')
                                        configManager.setUserValue("TTS", "style", val)
                                    if (typeof voiceManager !== 'undefined')
                                        voiceManager.setTTSStyle(val)
                                }

                                background: Rectangle {
                                    radius: Theme.radiusSmall
                                    color: Theme.bgInput
                                    border.color: styleCombo.activeFocus ? Theme.borderFocus : "transparent"
                                }

                                contentItem: Text {
                                    leftPadding: Theme.spacing8
                                    text: styleCombo.displayText
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.textPrimary
                                    verticalAlignment: Text.AlignVCenter
                                }

                                delegate: ItemDelegate {
                                    width: styleCombo.width
                                    contentItem: Text {
                                        text: modelData
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontSmall
                                        color: Theme.textPrimary
                                    }
                                    background: Rectangle {
                                        color: highlighted ? Theme.accentActive : Theme.bgSecondary
                                    }
                                }

                                popup: Popup {
                                    y: styleCombo.height
                                    width: styleCombo.width
                                    implicitHeight: contentItem.implicitHeight
                                    padding: 1

                                    contentItem: ListView {
                                        clip: true
                                        implicitHeight: contentHeight
                                        model: styleCombo.popup.visible ? styleCombo.delegateModel : null
                                        currentIndex: styleCombo.highlightedIndex
                                    }

                                    background: Rectangle {
                                        color: Theme.bgSecondary
                                        border.color: Theme.border
                                        radius: Theme.radiusSmall
                                    }
                                }
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing4

                            FieldLabel { text: SettingsLabels.t("tts.language") }

                            ComboBox {
                                id: ttsLangCombo
                                Layout.fillWidth: true
                                Layout.preferredHeight: 30
                                model: ListModel {
                                    ListElement { text: "Français";    value: "fr" }
                                    ListElement { text: "English";     value: "en" }
                                    ListElement { text: "Español";     value: "es" }
                                    ListElement { text: "Deutsch";     value: "de" }
                                    ListElement { text: "Italiano";    value: "it" }
                                    ListElement { text: "Português";   value: "pt" }
                                    ListElement { text: "Polski";      value: "pl" }
                                    ListElement { text: "Türkçe";      value: "tr" }
                                    ListElement { text: "Русский";     value: "ru" }
                                    ListElement { text: "Nederlands";  value: "nl" }
                                    ListElement { text: "Čeština";     value: "cs" }
                                    ListElement { text: "العربية";     value: "ar" }
                                    ListElement { text: "中文";         value: "zh-cn" }
                                    ListElement { text: "日本語";       value: "ja" }
                                    ListElement { text: "한국어";       value: "ko" }
                                    ListElement { text: "Magyar";      value: "hu" }
                                    ListElement { text: "हिन्दी";       value: "hi" }
                                }
                                textRole: "text"
                                valueRole: "value"

                                Component.onCompleted: {
                                    var lang = typeof configManager !== 'undefined'
                                               ? configManager.getTTSLanguage() : "fr"
                                    for (var i = 0; i < model.count; i++) {
                                        if (model.get(i).value === lang) {
                                            currentIndex = i
                                            break
                                        }
                                    }
                                }

                                onActivated: {
                                    var val = model.get(currentIndex).value
                                    if (typeof configManager !== 'undefined')
                                        configManager.setUserValue("TTS", "language", val)
                                    if (typeof voiceManager !== 'undefined')
                                        voiceManager.setTTSLanguage(val)
                                }

                                background: Rectangle {
                                    radius: Theme.radiusSmall
                                    color: Theme.bgInput
                                    border.color: ttsLangCombo.activeFocus ? Theme.borderFocus : "transparent"
                                }

                                contentItem: Text {
                                    leftPadding: Theme.spacing8
                                    text: ttsLangCombo.displayText
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.textPrimary
                                    verticalAlignment: Text.AlignVCenter
                                }

                                delegate: ItemDelegate {
                                    width: ttsLangCombo.width
                                    contentItem: Text {
                                        text: model.text
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontSmall
                                        color: Theme.textPrimary
                                    }
                                    background: Rectangle {
                                        color: highlighted ? Theme.accentActive : Theme.bgSecondary
                                    }
                                }

                                popup: Popup {
                                    y: ttsLangCombo.height
                                    width: ttsLangCombo.width
                                    implicitHeight: contentItem.implicitHeight
                                    padding: 1

                                    contentItem: ListView {
                                        clip: true
                                        implicitHeight: contentHeight
                                        model: ttsLangCombo.popup.visible ? ttsLangCombo.delegateModel : null
                                        currentIndex: ttsLangCombo.highlightedIndex
                                    }

                                    background: Rectangle {
                                        color: Theme.bgSecondary
                                        border.color: Theme.border
                                        radius: Theme.radiusSmall
                                    }
                                }
                            }
                        }
                    }

                    // ── Phrase de test + bouton Parler ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4

                        FieldLabel { text: SettingsLabels.t("tts.testPhrase") }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing8

                            TextField {
                                id: testPhraseField
                                Layout.fillWidth: true
                                Layout.preferredHeight: 30
                                text: typeof configManager !== 'undefined'
                                      ? configManager.getString("TTS", "testPhrase",
                                            "Bonjour, je suis EXO, votre assistant vocal.")
                                      : "Bonjour, je suis EXO, votre assistant vocal."
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSmall
                                color: Theme.textPrimary
                                placeholderText: SettingsLabels.t("tts.testPlaceholder")
                                placeholderTextColor: Theme.textMuted
                                background: Rectangle {
                                    radius: Theme.radiusSmall
                                    color: Theme.bgInput
                                    border.color: testPhraseField.activeFocus ? Theme.borderFocus : "transparent"
                                }
                                onEditingFinished: {
                                    if (typeof configManager !== 'undefined')
                                        configManager.setUserValue("TTS", "testPhrase", text)
                                }
                            }

                            Rectangle {
                                Layout.preferredWidth: 90
                                Layout.preferredHeight: 30
                                radius: Theme.radiusSmall
                                color: testAudioMouse.pressed ? Theme.accentDark
                                     : testAudioMouse.containsMouse ? Theme.accentHover
                                     : Theme.accent

                                Behavior on color { ColorAnimation { duration: Theme.animFast } }

                                Row {
                                    anchors.centerIn: parent
                                    spacing: Theme.spacing6
                                    Text {
                                        text: "🔊"
                                        font.pixelSize: Theme.fontBody
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    Text {
                                        text: SettingsLabels.t("tts.speak")
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontCaption
                                        font.bold: true
                                        color: "#FFFFFF"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }

                                MouseArea {
                                    id: testAudioMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        var phrase = testPhraseField.text.trim()
                                        if (phrase.length === 0) phrase = "Bonjour, je suis EXO."
                                        if (typeof assistantManager !== 'undefined') {
                                            assistantManager.testTTS(phrase)
                                        } else if (typeof voiceManager !== 'undefined') {
                                            voiceManager.speak(phrase)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                SectionSeparator {}

                // ═══════════════════════════════════════════════════
                //  6 ── INTERFACE & AFFICHAGE
                // ═══════════════════════════════════════════════════
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing12

                    SectionTitle { text: "6. Interface & Affichage" }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 50
                        color: Theme.bgSecondary
                        border.color: Theme.border
                        border.width: 1
                        radius: Theme.radiusSmall

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacing12
                            anchors.rightMargin: Theme.spacing12
                            spacing: Theme.spacing12

                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true

                                Text {
                                    text: SettingsLabels.t("dev.expertMode")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.textPrimary
                                    font.bold: true
                                }

                                Text {
                                    text: SettingsLabels.t("dev.expertModeDescription")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontCaption
                                    color: Theme.textSecondary
                                }
                            }

                            Switch {
                                id: expertModeToggle
                                checked: typeof UIState !== 'undefined' ? UIState.expertMode : false
                                onCheckedChanged: {
                                    if (typeof UIState !== 'undefined') {
                                        UIState.setExpertMode(checked)
                                        if (typeof MenuStructure !== 'undefined') {
                                            MenuStructure.refreshMenu()
                                        }
                                        console.log("[Settings] Mode Expert basculé à:", checked)
                                    }
                                }
                            }
                        }
                    }
                }

                SectionSeparator {}

                // ═══════════════════════════════════════════════════
                //  7 ── SERVICES EXTERNES (Météo, API)
                // ═══════════════════════════════════════════════════
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8

                    SectionTitle { text: "7. Services externes (Météo, API)" }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4

                        FieldLabel { text: SettingsLabels.t("weather.city") }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing8

                            Rectangle {
                                Layout.fillWidth: true
                                height: 30
                                radius: Theme.radiusSmall
                                color: Theme.bgInput
                                border.color: cityInput.activeFocus ? Theme.borderFocus : "transparent"

                                Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

                                TextInput {
                                    id: cityInput
                                    anchors.fill: parent
                                    anchors.leftMargin: Theme.spacing8
                                    anchors.rightMargin: Theme.spacing8
                                    verticalAlignment: TextInput.AlignVCenter
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.textPrimary
                                    selectByMouse: true
                                    selectionColor: Theme.accentActive
                                    text: typeof configManager !== 'undefined'
                                          ? configManager.getWeatherCity() : "Paris"

                                    Keys.onReturnPressed: {
                                        if (typeof configManager !== 'undefined')
                                            configManager.setWeatherCity(cityInput.text)
                                        if (typeof weatherManager !== 'undefined')
                                            weatherManager.setCity(cityInput.text)
                                    }
                                    onActiveFocusChanged: {
                                        if (!activeFocus && typeof configManager !== 'undefined') {
                                            configManager.setWeatherCity(cityInput.text)
                                            if (typeof weatherManager !== 'undefined')
                                                weatherManager.setCity(cityInput.text)
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                width: 90
                                height: 30
                                radius: Theme.radiusSmall
                                color: detectArea.containsMouse ? Theme.accentHover : Theme.accent

                                Behavior on color { ColorAnimation { duration: Theme.animFast } }

                                Text {
                                    anchors.centerIn: parent
                                    text: SettingsLabels.t("common.detect")
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontMicro
                                    color: "#FFFFFF"
                                }

                                MouseArea {
                                    id: detectArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof configManager !== 'undefined')
                                            configManager.detectLocation()
                                    }
                                }
                            }
                        }
                    }
                }

                SectionSeparator {}

                // ═══════════════════════════════════════════════════
                //  8 ── DIAGNOSTICS & TESTS
                // ═══════════════════════════════════════════════════
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing8

                    SectionTitle { text: "8. Diagnostics & Tests" }

                    // ── Accès aux tests de stabilité ──
                    Rectangle {
                        Layout.fillWidth: true
                        height: Theme.buttonHeight
                        radius: Theme.radiusSmall
                        color: stabilityMa.containsPress ? Theme.accentDark
                             : stabilityMa.containsMouse ? Theme.accentHover
                             : Theme.accent

                        Behavior on color { ColorAnimation { duration: Theme.animFast } }

                        Text {
                            anchors.centerIn: parent
                            text: SettingsLabels.t("diag.stability")
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSmall
                            font.weight: Font.Medium
                            color: "#FFFFFF"
                        }

                        MouseArea {
                            id: stabilityMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                // Index 17 = DevelopmentPageExpert
                                var mw = root
                                while (mw && !mw.hasOwnProperty("navigateTo"))
                                    mw = mw.parent
                                // Repli : positionner directement le centralStack
                                if (typeof centralStack !== 'undefined')
                                    centralStack.currentIndex = 17
                            }
                        }
                    }

                    // ── Test conversationnel rapide ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacing4

                        FieldLabel { text: "Test conversationnel (envoyer un message à EXO)" }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spacing8

                            Rectangle {
                                Layout.fillWidth: true
                                height: Theme.buttonHeight
                                radius: Theme.radiusSmall
                                color: Theme.bgInput
                                border.color: chatInput.activeFocus ? Theme.borderFocus : "transparent"

                                Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

                                TextInput {
                                    id: chatInput
                                    anchors.fill: parent
                                    anchors.leftMargin: Theme.spacing8
                                    anchors.rightMargin: Theme.spacing8
                                    verticalAlignment: TextInput.AlignVCenter
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.textPrimary
                                    clip: true
                                    selectByMouse: true
                                    selectionColor: Theme.accentActive

                                    property string placeholderText: "Tapez un message…"
                                    Text {
                                        anchors.fill: parent
                                        verticalAlignment: Text.AlignVCenter
                                        font: chatInput.font
                                        color: Theme.textMuted
                                        text: chatInput.placeholderText
                                        visible: !chatInput.text && !chatInput.activeFocus
                                    }

                                    Keys.onReturnPressed: sendChatBtn.clicked()
                                    Keys.onEnterPressed: sendChatBtn.clicked()
                                }
                            }

                            Rectangle {
                                id: sendChatBtn
                                Layout.preferredWidth: Theme.buttonHeight
                                Layout.preferredHeight: Theme.buttonHeight
                                radius: Theme.radiusSmall
                                color: sendChatMa.containsPress ? Theme.accentDark : Theme.accent

                                Behavior on color { ColorAnimation { duration: Theme.animFast } }

                                signal clicked()

                                Text {
                                    anchors.centerIn: parent
                                    text: "▶"
                                    font.pixelSize: Theme.fontBody
                                    color: "#FFFFFF"
                                }

                                MouseArea {
                                    id: sendChatMa
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        parent.clicked()
                                        var msg = chatInput.text.trim()
                                        if (msg.length > 0 && typeof assistantManager !== 'undefined') {
                                            assistantManager.sendMessage(msg)
                                            chatInput.text = ""
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Item { Layout.preferredHeight: Theme.spacing20 }
            }
        }
    }
}
