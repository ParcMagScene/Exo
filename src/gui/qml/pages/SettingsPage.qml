import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

// ─── Page Réglages ───────────────────────────────────────

Item {
    id: settingsPage

    opacity: 0
    Component.onCompleted: {
        fadeIn.start()
        loadSettings()
    }
    NumberAnimation { id: fadeIn; target: settingsPage; property: "opacity"; to: 1; duration: 400; easing.type: Easing.OutCubic }

    property var settings: ({})

    function loadSettings() {
        try {
            settings = JSON.parse(Bridge.getSettings())
        } catch(e) {
            settings = {}
        }
    }

    ScrollView {
        anchors.fill: parent
        clip: true

        ColumnLayout {
            width: parent.width
            anchors.margins: 24

            // ─── En-tête ─────────────────────────────────

            Item { Layout.preferredHeight: 24 }

            Text {
                text: "⚙️ Réglages"
                font.pixelSize: 22
                font.bold: true
                color: Theme.textPrimary
                Layout.leftMargin: 24
            }

            Item { Layout.preferredHeight: 16 }

            // ─── Section Audio / STT ─────────────────────

            SettingsSection {
                title: "🎤 Audio & Reconnaissance vocale"
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 16

                    SettingsRow {
                        label: "Modèle Whisper"
                        description: "Plus gros = plus précis mais plus lent"
                        Layout.fillWidth: true

                        ComboBox {
                            id: whisperCombo
                            model: ["tiny", "base", "small", "medium", "large-v3"]
                            currentIndex: model.indexOf(settings.whisper_model || "base")
                            width: 160
                            onActivated: Bridge.setSetting("whisper_model", currentText)
                        }
                    }

                    SettingsRow {
                        label: "Sensibilité VAD"
                        description: "Plus bas = plus sensible au bruit"
                        Layout.fillWidth: true

                        RowLayout {
                            spacing: 12
                            Slider {
                                id: vadSlider
                                from: 1.0
                                to: 5.0
                                stepSize: 0.5
                                value: settings.vad_multiplier || 2.5
                                onMoved: Bridge.setSetting("vad_multiplier", value.toFixed(1))

                                background: Rectangle {
                                    x: vadSlider.leftPadding
                                    y: vadSlider.topPadding + vadSlider.availableHeight / 2 - height / 2
                                    width: vadSlider.availableWidth
                                    height: 4
                                    radius: 2
                                    color: Theme.surfaceVariant

                                    Rectangle {
                                        width: vadSlider.visualPosition * parent.width
                                        height: parent.height
                                        radius: 2
                                        color: Theme.primary
                                    }
                                }

                                handle: Rectangle {
                                    x: vadSlider.leftPadding + vadSlider.visualPosition * (vadSlider.availableWidth - width)
                                    y: vadSlider.topPadding + vadSlider.availableHeight / 2 - height / 2
                                    width: 20; height: 20; radius: 10
                                    color: Theme.primary
                                }
                            }

                            Text {
                                text: "×" + vadSlider.value.toFixed(1)
                                font.pixelSize: 13
                                color: Theme.textSecondary
                                Layout.preferredWidth: 40
                            }
                        }
                    }
                }
            }

            Item { Layout.preferredHeight: 16 }

            // ─── Section TTS ─────────────────────────────

            SettingsSection {
                title: "🔊 Synthèse vocale"
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 16

                    SettingsRow {
                        label: "Moteur TTS"
                        description: "Kokoro = meilleure qualité locale"
                        Layout.fillWidth: true

                        ComboBox {
                            model: ["kokoro", "piper", "openai"]
                            currentIndex: model.indexOf(settings.tts_engine || "kokoro")
                            width: 160
                            onActivated: Bridge.setSetting("tts_engine", currentText)
                        }
                    }
                }
            }

            Item { Layout.preferredHeight: 16 }

            // ─── Section Home Assistant ──────────────────

            SettingsSection {
                title: "🏠 Home Assistant"
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 16

                    SettingsRow {
                        label: "URL"
                        description: "Adresse de votre instance HA"
                        Layout.fillWidth: true

                        TextField {
                            text: settings.ha_url || ""
                            placeholderText: "http://homeassistant.local:8123"
                            width: 280
                            color: Theme.textPrimary
                            onEditingFinished: Bridge.setSetting("ha_url", text)
                            background: Rectangle {
                                color: Theme.card
                                radius: Theme.radiusSmall
                                border.color: Theme.surfaceVariant
                            }
                        }
                    }

                    SettingsRow {
                        label: "Connexion"
                        description: settings.ha_connected ? "Connecté à HA" : "Non connecté"
                        Layout.fillWidth: true

                        Rectangle {
                            width: statusLabel.implicitWidth + 24
                            height: 32
                            radius: 16
                            color: settings.ha_connected ? Theme.success : Theme.error
                            opacity: 0.2

                            Text {
                                id: statusLabel
                                anchors.centerIn: parent
                                text: settings.ha_connected ? "✅ Connecté" : "❌ Déconnecté"
                                font.pixelSize: 12
                                color: settings.ha_connected ? Theme.success : Theme.error
                            }
                        }
                    }
                }
            }

            Item { Layout.preferredHeight: 16 }

            // ─── Section À propos ────────────────────────

            SettingsSection {
                title: "ℹ️ À propos"
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: "EXO — Assistant vocal intelligent"
                        font.pixelSize: 14
                        color: Theme.textPrimary
                    }
                    Text {
                        text: "Version 2.0 — Interface PySide6/QML"
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }
                    Text {
                        text: "Pipeline : Whisper STT → GPT-4o-mini → Kokoro TTS"
                        font.pixelSize: 12
                        color: Theme.textMuted
                    }
                }
            }

            Item { Layout.preferredHeight: 32 }
        }
    }
}
