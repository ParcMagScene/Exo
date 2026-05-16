import QtQuick
import QtQuick.Layouts
import "../theme"

// ═══════════════════════════════════════════════════════════════════════════
//  SafeButton — Variante durcie d'ExoButton (Hardening 2026)
//
//  Apports :
//    - Anti-clic-multiple : intervalle minimum entre deux émissions du signal
//      `safeClicked` (défaut 350 ms). Le signal natif `clicked` est conservé
//      pour compatibilité mais NON débouncé.
//    - Verrou `busy` : si vrai, le bouton refuse les clics et affiche une
//      opacité réduite + curseur d'attente.
//    - Vérification d'état préalable via `precondition` (fonction QML qui
//      retourne true/false). Si false → toast d'erreur via `errorMessage`.
//    - Timeout UI optionnel (`autoReleaseMs`) : libère automatiquement `busy`
//      après N ms pour éviter les états bloqués si le backend ne répond pas.
//
//  Usage type :
//    SafeButton {
//        text: "Valider"
//        primary: true
//        debounceMs: 500
//        autoReleaseMs: 5000
//        onSafeClicked: backend.submit()
//    }
//
//  ID / bindings / imports : compatible avec le pattern ExoButton existant.
// ═══════════════════════════════════════════════════════════════════════════

Rectangle {
    id: safeRoot

    // -- API publique --------------------------------------------------------
    property string text: ""
    property string iconText: ""
    property bool primary: false
    property bool destructive: false
    property bool enabled: true
    property bool flat: false

    property int debounceMs: 350
    property int autoReleaseMs: 0
    property bool busy: false
    property var precondition: null   // function returning bool
    property string errorMessage: ""

    signal safeClicked()
    signal clicked()               // compat — non débouncé
    signal blocked(string reason)  // diagnostic

    // -- État interne --------------------------------------------------------
    QtObject {
        id: priv
        property double lastClickTs: 0
    }

    Timer {
        id: autoReleaseTimer
        interval: safeRoot.autoReleaseMs
        repeat: false
        onTriggered: {
            if (safeRoot.busy) {
                console.warn("[SafeButton] Auto-release après", safeRoot.autoReleaseMs, "ms — backend silencieux ?")
                safeRoot.busy = false
            }
        }
    }

    // -- Apparence (reprend ExoButton, ajoute curseur d'attente) -------------
    implicitWidth: contentRow.implicitWidth + Theme.paddingBtn * 2
    implicitHeight: Theme.buttonHeight
    radius: Theme.radiusMedium
    opacity: (safeRoot.enabled && !safeRoot.busy) ? 1.0 : 0.45

    color: {
        if (!safeRoot.enabled || safeRoot.busy) return Theme.bgInput
        if (safeRoot.destructive)
            return mouseArea.pressed ? Theme.errorDim
                 : mouseArea.containsMouse ? Theme.errorHover : Theme.error
        if (safeRoot.primary)
            return mouseArea.pressed ? Theme.accentDark
                 : mouseArea.containsMouse ? Theme.accentHover : Theme.accent
        if (safeRoot.flat)
            return mouseArea.pressed ? Theme.bgActive
                 : mouseArea.containsMouse ? Theme.bgHover : "transparent"
        return mouseArea.pressed ? Theme.bgActive
             : mouseArea.containsMouse ? Theme.bgHover : Theme.bgElevated
    }

    RowLayout {
        id: contentRow
        anchors.centerIn: parent
        spacing: 6

        Text {
            visible: safeRoot.iconText.length > 0
            text: safeRoot.iconText
            color: Theme.fgPrimary
            font.pixelSize: 16
        }
        Text {
            text: safeRoot.busy ? "…" : safeRoot.text
            color: Theme.fgPrimary
            font.pixelSize: Theme.fontMedium
            font.weight: Font.Medium
        }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: (safeRoot.enabled && !safeRoot.busy)
                     ? Qt.PointingHandCursor : Qt.WaitCursor
        onClicked: {
            // Signal natif (toujours émis pour compat).
            safeRoot.clicked()

            if (!safeRoot.enabled) {
                safeRoot.blocked("disabled")
                return
            }
            if (safeRoot.busy) {
                safeRoot.blocked("busy")
                return
            }

            var now = Date.now()
            if (now - priv.lastClickTs < safeRoot.debounceMs) {
                safeRoot.blocked("debounce")
                return
            }
            priv.lastClickTs = now

            if (safeRoot.precondition !== null
                && typeof safeRoot.precondition === "function") {
                try {
                    if (!safeRoot.precondition()) {
                        safeRoot.blocked("precondition")
                        if (safeRoot.errorMessage.length > 0) {
                            console.warn("[SafeButton]", safeRoot.errorMessage)
                        }
                        return
                    }
                } catch (e) {
                    console.warn("[SafeButton] precondition a levé :", e)
                    safeRoot.blocked("precondition_error")
                    return
                }
            }

            safeRoot.busy = true
            if (safeRoot.autoReleaseMs > 0) {
                autoReleaseTimer.restart()
            }
            safeRoot.safeClicked()
        }
    }

    // Permet au consommateur de libérer `busy` manuellement quand le backend
    // a répondu (ex: onBackendDone: safeButton.releaseBusy()).
    function releaseBusy() {
        busy = false
        autoReleaseTimer.stop()
    }
}
