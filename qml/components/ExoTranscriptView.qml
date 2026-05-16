import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../core"

// ═══════════════════════════════════════════════════════
//  ExoTranscriptView — Vue de transcription avec messages
// ═══════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    property string partialTranscript: ""
    ListModel {
        id: messageListModel
    }

    function addMessage(text, isUser, isPartial) {
        messageListModel.append({
            "message": text,
            "isUser": isUser,
            "isPartial": isPartial || false,
            "timestamp": Qt.formatTime(new Date(), "hh:mm")
        })
        // Purge: garder les 200 derniers messages (fix audit M1)
        while (messageListModel.count > 200)
            messageListModel.remove(0)
        messageListView.positionViewAtEnd()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Header ──
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.headerHeight
            color: Theme.bgSecondary

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacing16
                anchors.rightMargin: Theme.spacing16

                Text {
                    text: SettingsLabels.t("comp.transcript")
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontMicro
                    font.bold: true
                    color: Theme.textAccent
                    font.letterSpacing: 1.5
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: messageListModel.count + " messages"
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontMicro
                    color: Theme.textMuted
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Theme.border
            }
        }

        // ── Message list ──
        ListView {
            id: messageListView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 0
            model: messageListModel

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                contentItem: Rectangle {
                    implicitWidth: 6
                    radius: 3
                    color: Theme.textMuted
                    opacity: 0.5
                }
            }

            delegate: Rectangle {
                width: messageListView.width
                height: msgColumn.height + 16
                color: index % 2 === 0 ? Theme.bgPrimary : "#1F1F1F"

                Rectangle {
                    anchors.left: parent.left
                    width: 3
                    height: parent.height
                    color: model.isUser ? Theme.accent : Theme.success
                    opacity: model.isPartial ? 0.4 : 1.0
                }

                Column {
                    id: msgColumn
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Theme.spacing16
                    anchors.rightMargin: Theme.spacing16
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Theme.spacing2

                    Row {
                        spacing: Theme.spacing10

                        Text {
                            text: model.isUser ? "user" : "exo"
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontMicro
                            font.bold: true
                            color: model.isUser ? Theme.accent : Theme.success
                        }

                        Text {
                            text: model.timestamp
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontMicro
                            color: Theme.textMuted
                        }
                    }

                    Text {
                        text: model.message
                        width: parent.width
                        wrapMode: Text.WordWrap
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fontSmall
                        color: model.isPartial ? Theme.textSecondary : Theme.textPrimary
                        font.italic: model.isPartial
                        lineHeight: 1.4
                    }
                }

                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: "#2A2A2A"
                }
            }
        }

        // ── Partial transcript en cours ──
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.partialTranscript.length > 0 ? partialText.height + 16 : 0
            color: Theme.bgSecondary
            visible: root.partialTranscript.length > 0
            clip: true

            Behavior on Layout.preferredHeight {
                NumberAnimation { duration: 100; easing.type: Easing.OutQuad }
            }

            Rectangle {
                anchors.top: parent.top
                width: parent.width
                height: 1
                color: Theme.border
            }

            Text {
                id: partialText
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: Theme.spacing16
                anchors.rightMargin: Theme.spacing16
                anchors.verticalCenter: parent.verticalCenter
                text: "▸ " + root.partialTranscript
                wrapMode: Text.WordWrap
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontSmall
                font.italic: true
                color: Theme.textSecondary
            }
        }

        // ── Champ d'entrée manuelle ──
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            color: Theme.bgSecondary

            Rectangle {
                anchors.top: parent.top
                width: parent.width
                height: 1
                color: Theme.border
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacing12
                anchors.rightMargin: Theme.spacing12
                anchors.topMargin: Theme.spacing4
                anchors.bottomMargin: Theme.spacing4
                spacing: Theme.spacing8

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: Theme.radiusSmall
                    color: Theme.bgInput
                    border.color: manualInput.activeFocus ? Theme.borderFocus : "transparent"

                    Behavior on border.color {
                        ColorAnimation { duration: Theme.animFast }
                    }

                    TextInput {
                        id: manualInput
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacing10
                        anchors.rightMargin: Theme.spacing10
                        verticalAlignment: TextInput.AlignVCenter
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSmall
                        color: Theme.textPrimary
                        clip: true

                        property string placeholderText: "Poser une question à EXO..."
                        Text {
                            anchors.fill: parent
                            verticalAlignment: Text.AlignVCenter
                            font: manualInput.font
                            color: Theme.textMuted
                            text: manualInput.placeholderText
                            visible: !manualInput.text && !manualInput.activeFocus
                        }

                        Keys.onReturnPressed: sendManualInput()
                        Keys.onEnterPressed: sendManualInput()

                        function sendManualInput() {
                            var txt = manualInput.text.trim()
                            if (txt.length === 0) return
                            root.addMessage(txt, true, false)
                            if (typeof assistantManager !== 'undefined') {
                                assistantManager.sendManualQuery(txt)
                            }
                            manualInput.text = ""
                        }
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 32
                    Layout.fillHeight: true
                    radius: Theme.radiusSmall
                    color: sendArea.containsMouse ? Theme.accentActive : Theme.accent

                    Behavior on color {
                        ColorAnimation { duration: Theme.animFast }
                    }

                    Image {
                        anchors.centerIn: parent
                        source: "../icons/send.svg"
                        sourceSize.width: Theme.iconSize
                        sourceSize.height: Theme.iconSize
                        width: Theme.iconSize
                        height: Theme.iconSize
                    }

                    MouseArea {
                        id: sendArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: manualInput.sendManualInput()
                    }
                }
            }
        }
    }
}
