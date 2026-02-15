import QtQuick

// ─── StatusOrb — Orbe lumineux animé selon l'état du pipeline ──

Item {
    id: orbRoot
    width: 200
    height: 200

    property string state: "idle"
    property color orbColor: {
        switch(state) {
            case "idle":        return Theme.orbIdle
            case "listening":   return Theme.orbListening
            case "processing":  return Theme.orbProcessing
            case "responding":  return Theme.orbResponding
            default:            return Theme.orbIdle
        }
    }

    // ─── Halo externe (glow) ─────────────────────────────

    Rectangle {
        id: halo
        anchors.centerIn: parent
        width: 180
        height: 180
        radius: 90
        color: "transparent"
        border.color: orbColor
        border.width: 2
        opacity: 0.3

        SequentialAnimation on opacity {
            loops: Animation.Infinite
            NumberAnimation { to: 0.6; duration: orbRoot.state === "listening" ? 600 : 2000; easing.type: Easing.InOutSine }
            NumberAnimation { to: 0.15; duration: orbRoot.state === "listening" ? 600 : 2000; easing.type: Easing.InOutSine }
        }

        SequentialAnimation on scale {
            loops: Animation.Infinite
            NumberAnimation { to: 1.15; duration: orbRoot.state === "listening" ? 600 : 2000; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1.0; duration: orbRoot.state === "listening" ? 600 : 2000; easing.type: Easing.InOutSine }
        }
    }

    // ─── Orbe principal ──────────────────────────────────

    Rectangle {
        id: orb
        anchors.centerIn: parent
        width: 140
        height: 140
        radius: 70

        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.lighter(orbColor, 1.4) }
            GradientStop { position: 0.5; color: orbColor }
            GradientStop { position: 1.0; color: Qt.darker(orbColor, 1.3) }
        }

        // Rotation pour le mode "processing"
        rotation: 0
        RotationAnimation on rotation {
            running: orbRoot.state === "processing"
            loops: Animation.Infinite
            from: 0; to: 360
            duration: 3000
        }

        Behavior on gradient {
            ColorAnimation { duration: 500; easing.type: Easing.OutCubic }
        }
    }

    // ─── Reflet interne ──────────────────────────────────

    Rectangle {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -25
        width: 60
        height: 30
        radius: 15
        color: "#ffffff"
        opacity: 0.08
        rotation: -15
    }

    // ─── Pulse du centre (responding) ────────────────────

    Rectangle {
        id: pulse
        anchors.centerIn: parent
        width: 60
        height: 60
        radius: 30
        color: Qt.lighter(orbColor, 1.6)
        opacity: 0
        visible: orbRoot.state === "responding"

        SequentialAnimation on opacity {
            running: orbRoot.state === "responding"
            loops: Animation.Infinite
            NumberAnimation { to: 0.5; duration: 300 }
            NumberAnimation { to: 0; duration: 300 }
        }

        SequentialAnimation on scale {
            running: orbRoot.state === "responding"
            loops: Animation.Infinite
            NumberAnimation { to: 2.0; duration: 600 }
            NumberAnimation { to: 1.0; duration: 0 }
        }
    }

    // ─── Label EXO au centre ─────────────────────────────

    Text {
        anchors.centerIn: parent
        text: "EXO"
        font.pixelSize: 28
        font.bold: true
        font.letterSpacing: 4
        color: "#ffffff"
        opacity: 0.9

        SequentialAnimation on opacity {
            loops: Animation.Infinite
            NumberAnimation { to: 0.5; duration: 2000; easing.type: Easing.InOutSine }
            NumberAnimation { to: 0.9; duration: 2000; easing.type: Easing.InOutSine }
        }
    }

    // ─── Transition fluide des couleurs ──────────────────

    Behavior on orbColor {
        ColorAnimation { duration: 600; easing.type: Easing.OutCubic }
    }
}
