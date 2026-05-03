import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════
//  ExoResponseView — Vue de réponse avec streaming
// ═══════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    property string responseText: ""
    property bool isStreaming: false

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
                    text: "RÉPONSE"
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontMicro
                    font.bold: true
                    color: Theme.textAccent
                    font.letterSpacing: 1.5
                }

                Item { Layout.fillWidth: true }

                // Indicateur streaming
                Row {
                    visible: root.isStreaming
                    spacing: Theme.spacing6

                    Rectangle {
                        width: 6; height: 6; radius: 3
                        anchors.verticalCenter: parent.verticalCenter
                        color: Theme.success

                        SequentialAnimation on opacity {
                            running: root.isStreaming
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.2; duration: 500 }
                            NumberAnimation { to: 1.0; duration: 500 }
                        }
                    }

                    Text {
                        text: "streaming"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontMicro
                        color: Theme.success
                    }
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Theme.border
            }
        }

        // ── Response content ──
        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: responseContent.height + Theme.spacing32
            clip: true
            flickableDirection: Flickable.VerticalFlick

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                contentItem: Rectangle {
                    implicitWidth: 6
                    radius: 3
                    color: Theme.textMuted
                    opacity: 0.5
                }
            }

            Text {
                id: responseContent
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: Theme.spacing16
                anchors.rightMargin: Theme.spacing16
                anchors.topMargin: Theme.spacing16
                y: Theme.spacing16
                wrapMode: Text.WordWrap
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontBody
                color: Theme.textPrimary
                lineHeight: 1.6
                text: root.responseText.length > 0
                      ? root.responseText + (root.isStreaming ? cursorText.text : "")
                      : "En attente d'une commande vocale..."
                opacity: root.responseText.length > 0 ? 1.0 : 0.4
            }
        }
    }

    // Curseur clignotant
    Text {
        id: cursorText
        visible: false
        text: " ▌"
        SequentialAnimation on text {
            running: root.isStreaming
            loops: Animation.Infinite
            PropertyAnimation { to: " ▌"; duration: 500 }
            PropertyAnimation { to: "  "; duration: 500 }
        }
    }
}
