import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ─── Barre de navigation latérale tactile ────────────────

Rectangle {
    id: navRail
    color: Theme.surface
    width: Theme.navRailWidth

    property string currentPage: "home"
    signal pageSelected(string page)

    // Bordure droite subtile
    Rectangle {
        anchors.right: parent.right
        width: 1
        height: parent.height
        color: Theme.surfaceVariant
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 16
        anchors.bottomMargin: 16
        spacing: 4

        // Logo EXO en haut
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 48
            Layout.preferredHeight: 48
            radius: 12
            color: Theme.primary
            opacity: 0.9

            Text {
                anchors.centerIn: parent
                text: "E"
                font.pixelSize: 22
                font.bold: true
                color: "#ffffff"
            }
        }

        Item { Layout.preferredHeight: 20 }

        // Boutons de navigation
        Repeater {
            model: [
                { icon: "🏠", page: "home",       label: "Accueil" },
                { icon: "🗺️", page: "floorplan",  label: "Plans" },
                { icon: "📹", page: "cameras",    label: "Caméras" },
                { icon: "💡", page: "automation", label: "Domoti." },
                { icon: "⚙️", page: "settings",   label: "Réglages" }
            ]

            delegate: NavButton {
                Layout.alignment: Qt.AlignHCenter
                icon: modelData.icon
                label: modelData.label
                active: navRail.currentPage === modelData.page
                onClicked: navRail.pageSelected(modelData.page)
            }
        }

        Item { Layout.fillHeight: true }

        // Bouton thème en bas
        NavButton {
            Layout.alignment: Qt.AlignHCenter
            icon: Theme.isDark ? "🌙" : "☀️"
            label: "Thème"
            active: false
            onClicked: Theme.toggleTheme()
        }
    }
}
