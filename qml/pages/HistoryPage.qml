import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"
import "../core"

Rectangle {
    id: root
    color: Theme.bgPrimary

    // Recharger quand la page redevient visible (couvre les cas où l'historique
    // est rempli APRÈS la première création de la page).
    onVisibleChanged: if (visible) loadHistory()

    // Mise à jour temps-réel : nouvel échange ajouté à AIMemoryManager.
    Connections {
        target: typeof memoryManager !== 'undefined' ? memoryManager : null
        function onConversationCountChanged() { root.loadHistory() }
        function onConversationAdded(userMessage, assistantResponse) {
            // Ajout incrémental rapide (évite un full reload) si le format match.
            historyModel.append({
                "userMessage": String(userMessage),
                "assistantResponse": String(assistantResponse)
            })
            historyList.positionViewAtEnd()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Header ──
        ExoPanelHeader {
            title: SettingsLabels.t("history.title")
            rightContent: [
                Text {
                    text: SettingsLabels.t("common.clear")
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontMicro
                    color: clearMouseArea.containsMouse ? Theme.error : Theme.textMuted

                    Behavior on color { ColorAnimation { duration: Theme.animFast } }

                    MouseArea {
                        id: clearMouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (typeof memoryManager !== 'undefined') {
                                memoryManager.clearConversationHistory()
                                historyModel.clear()
                            }
                        }
                    }
                }
            ]
        }

        // ── Liste des conversations récentes ──
        ListView {
            id: historyList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 0
            model: ListModel { id: historyModel }

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
                width: historyList.width
                height: histCol.height + Theme.spacing16
                color: histMouseArea.containsMouse ? Theme.bgHover : "transparent"

                Behavior on color { ColorAnimation { duration: Theme.animFast } }

                Rectangle {
                    anchors.left: parent.left
                    width: 3
                    height: parent.height
                    color: Theme.textAccent
                    opacity: 0.5
                }

                Column {
                    id: histCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Theme.spacing16
                    anchors.rightMargin: Theme.spacing16
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Theme.spacing4

                    Text {
                        text: model.userMessage
                        width: parent.width
                        elide: Text.ElideRight
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontCaption
                        color: Theme.textAccent
                    }

                    Text {
                        text: model.assistantResponse
                        width: parent.width
                        elide: Text.ElideRight
                        maximumLineCount: 2
                        wrapMode: Text.WordWrap
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontCaption
                        color: Theme.textSecondary
                    }
                }

                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: Theme.bgElevated
                }

                MouseArea {
                    id: histMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                }
            }

            // Charger l'historique au démarrage
            Component.onCompleted: loadHistory()
        }
    }

    function loadHistory() {
        if (typeof memoryManager === 'undefined') {
            historyModel.clear()
            return
        }
        var conversations = memoryManager.getRecentConversations(50) || []
        // Format renvoyé par AIMemoryManager::getRecentConversations : une entrée
        // formatée par échange « [hh:mm] user → assistant ». On tente d'abord
        // ce format-là (nouveau), avec fallback sur l'ancien format paire user/assistant.
        historyModel.clear()
        if (conversations.length > 0 && conversations[0].indexOf(" → ") !== -1) {
            for (var k = 0; k < conversations.length; ++k) {
                var line = String(conversations[k])
                var arrow = line.indexOf(" → ")
                var head  = line.substring(0, arrow)
                var resp  = line.substring(arrow + 3)
                historyModel.append({
                    "userMessage": head,
                    "assistantResponse": resp
                })
            }
            return
        }
        // Fallback ancien format paire user / assistant
        for (var i = 0; i < conversations.length; i += 2) {
            if (i + 1 < conversations.length) {
                historyModel.append({
                    "userMessage": conversations[i],
                    "assistantResponse": conversations[i + 1]
                })
            }
        }
    }

    function loadHistory_legacy() {
        // Conserv\u00e9 pour r\u00e9f\u00e9rence — non appel\u00e9.
    }
}
