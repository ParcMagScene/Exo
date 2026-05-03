import QtQuick
import "../theme"

// ═══════════════════════════════════════════════════════
//  ExoOrbVisualizer — v8 Premium Ambient Orb
//
//  Animated radial orb that reacts to EXO state:
//    Idle       →  dim breathing pulse
//    Listening  →  blue expanding rings
//    Thinking   →  purple rotating arcs
//    Speaking   →  green pulsing glow
//
//  Multi-layer Canvas rendering with GPU composition.
// ═══════════════════════════════════════════════════════

Item {
    id: root

    property string state: "Idle"     // Idle, Listening, Transcribing, Thinking, Speaking
    property real audioLevel: 0.0     // 0.0–1.0
    property real orbSize: 120

    property color orbColor: Theme.stateColor(root.state)

    implicitWidth: orbSize
    implicitHeight: orbSize

    // ── Internal animation state ──
    property real phase: 0.0
    property real smoothLevel: 0.0
    property real glowIntensity: root.state === "Idle" ? 0.3 : 0.8

    onAudioLevelChanged: {
        smoothLevel = smoothLevel * 0.65 + audioLevel * 0.35
    }

    Behavior on orbColor { ColorAnimation { duration: Theme.animSlow } }
    Behavior on glowIntensity { NumberAnimation { duration: Theme.animSlow } }

    layer.enabled: true
    layer.smooth: true

    // ── Outer glow ──
    Canvas {
        id: glowLayer
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        opacity: 0.4 * root.glowIntensity

        onPaint: {
            var ctx = getContext("2d")
            var w = width, h = height
            var cx = w / 2, cy = h / 2
            var r = Math.min(w, h) / 2

            ctx.clearRect(0, 0, w, h)

            var pulse = 0.85 + 0.15 * Math.sin(root.phase * 1.8)
            var outerR = r * (0.9 + root.smoothLevel * 0.1) * pulse
            var grad = ctx.createRadialGradient(cx, cy, outerR * 0.3, cx, cy, outerR)
            grad.addColorStop(0, Qt.rgba(root.orbColor.r, root.orbColor.g,
                                         root.orbColor.b, 0.6 * pulse))
            grad.addColorStop(0.6, Qt.rgba(root.orbColor.r, root.orbColor.g,
                                           root.orbColor.b, 0.15 * pulse))
            grad.addColorStop(1, "transparent")

            ctx.fillStyle = grad
            ctx.beginPath()
            ctx.arc(cx, cy, outerR, 0, 2 * Math.PI)
            ctx.fill()
        }
    }

    // ── Core orb ──
    Canvas {
        id: coreLayer
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative

        onPaint: {
            var ctx = getContext("2d")
            var w = width, h = height
            var cx = w / 2, cy = h / 2
            var baseR = Math.min(w, h) / 2 * 0.45

            ctx.clearRect(0, 0, w, h)

            var breathe = 0.92 + 0.08 * Math.sin(root.phase * 2.0)
            var levelR = baseR * (1.0 + root.smoothLevel * 0.25) * breathe

            // Orb gradient
            var grad = ctx.createRadialGradient(cx - levelR * 0.2, cy - levelR * 0.2,
                                                levelR * 0.1, cx, cy, levelR)
            var c = root.orbColor
            grad.addColorStop(0, Qt.rgba(Math.min(c.r + 0.3, 1), Math.min(c.g + 0.3, 1),
                                         Math.min(c.b + 0.3, 1), 0.95))
            grad.addColorStop(0.5, Qt.rgba(c.r, c.g, c.b, 0.85))
            grad.addColorStop(1, Qt.rgba(c.r * 0.6, c.g * 0.6, c.b * 0.6, 0.7))

            ctx.fillStyle = grad
            ctx.beginPath()
            ctx.arc(cx, cy, levelR, 0, 2 * Math.PI)
            ctx.fill()
        }
    }

    // ── Animated rings (Listening / Speaking) ──
    Canvas {
        id: ringsLayer
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        visible: root.state === "Listening" || root.state === "Speaking"

        onPaint: {
            var ctx = getContext("2d")
            var w = width, h = height
            var cx = w / 2, cy = h / 2
            var maxR = Math.min(w, h) / 2

            ctx.clearRect(0, 0, w, h)

            var numRings = 3
            for (var i = 0; i < numRings; i++) {
                var ringPhase = (root.phase * 0.8 + i * (2 * Math.PI / numRings)) % (2 * Math.PI)
                var progress = ringPhase / (2 * Math.PI)
                var ringR = maxR * (0.35 + progress * 0.6)
                var alpha = (1.0 - progress) * 0.35 * root.glowIntensity

                ctx.strokeStyle = Qt.rgba(root.orbColor.r, root.orbColor.g,
                                          root.orbColor.b, alpha)
                ctx.lineWidth = 1.5
                ctx.beginPath()
                ctx.arc(cx, cy, ringR, 0, 2 * Math.PI)
                ctx.stroke()
            }
        }
    }

    // ── Rotating arcs (Thinking) ──
    Canvas {
        id: arcsLayer
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        visible: root.state === "Thinking" || root.state === "Transcribing"

        onPaint: {
            var ctx = getContext("2d")
            var w = width, h = height
            var cx = w / 2, cy = h / 2
            var r = Math.min(w, h) / 2 * 0.55

            ctx.clearRect(0, 0, w, h)

            var numArcs = 3
            for (var i = 0; i < numArcs; i++) {
                var angle = root.phase * (1.2 + i * 0.3) + i * (2 * Math.PI / numArcs)
                var arcLen = Math.PI * 0.4

                ctx.strokeStyle = Qt.rgba(root.orbColor.r, root.orbColor.g,
                                          root.orbColor.b, 0.5 - i * 0.1)
                ctx.lineWidth = 2 - i * 0.3
                ctx.lineCap = "round"
                ctx.beginPath()
                ctx.arc(cx, cy, r + i * 5, angle, angle + arcLen)
                ctx.stroke()
            }
        }
    }

    // ── 30 FPS animation ──
    // ── 30 FPS actif / 10 FPS idle  (réduit charge GPU en état Idle) ──
    Timer {
        interval: root.active ? 33 : 100
        running: root.visible
        repeat: true
        onTriggered: {
            root.phase += interval / 1000.0
            if (!root.active && root.smoothLevel > 0.001)
                root.smoothLevel *= 0.92
            glowLayer.requestPaint()
            coreLayer.requestPaint()
            if (ringsLayer.visible) ringsLayer.requestPaint()
            if (arcsLayer.visible) arcsLayer.requestPaint()
        }
    }

    // ── Convenience ──
    readonly property bool active: root.state !== "Idle"
}
