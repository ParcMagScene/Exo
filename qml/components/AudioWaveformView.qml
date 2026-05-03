import QtQuick

// ═══════════════════════════════════════════════════════
//  AudioWaveformView — Premium Waveform Visualizer
//
//  GPU-composited waveform with glow, breathing, cubic
//  interpolation, and 60 FPS refresh. Uses multi-pass
//  Canvas rendering with layer composition for premium
//  visual quality.
//
//  Usage:
//    AudioWaveformView {
//        color: "#00FF88"
//        amplitude: 0.4
//        function feedSamples(arr) { updateSamples(arr) }
//    }
// ═══════════════════════════════════════════════════════

Item {
    id: root

    // ── Public API ──
    property color waveColor: "#00AEEF"
    property real amplitude: 0.4
    property real thickness: 2.0
    property real glowAmount: 0.015
    property bool active: false

    // ── Internal ──
    property int sampleCount: 256
    property var currentSamples: []
    property var targetSamples: []
    property real breathPhase: 0.0
    property real smoothFactor: 0.35   // interpolation between frames

    implicitHeight: 120

    // ── GPU layer composition for smooth rendering ──
    layer.enabled: true
    layer.smooth: true

    // ── Update samples from C++ signal ──
    function updateSamples(arr) {
        if (!arr || arr.length === 0) return
        // Copy to target array for smooth interpolation
        var newTarget = []
        var n = Math.min(arr.length, sampleCount)
        for (var i = 0; i < n; ++i)
            newTarget.push(arr[i])
        for (var j = n; j < sampleCount; ++j)
            newTarget.push(0.0)
        targetSamples = newTarget
    }

    // ── Glow layer (wide, blurred) ──
    Canvas {
        id: glowCanvas
        anchors.fill: parent
        visible: root.active
        renderStrategy: Canvas.Cooperative
        opacity: 0.45

        onPaint: {
            var ctx = getContext("2d")
            drawWaveform(ctx, width, height, root.currentSamples,
                         root.amplitude, root.thickness * 5.0,
                         root.waveColor, root.breathPhase, 0.3)
        }
    }

    // ── Medium glow layer ──
    Canvas {
        id: midGlowCanvas
        anchors.fill: parent
        visible: root.active
        renderStrategy: Canvas.Cooperative
        opacity: 0.7

        onPaint: {
            var ctx = getContext("2d")
            drawWaveform(ctx, width, height, root.currentSamples,
                         root.amplitude, root.thickness * 2.5,
                         root.waveColor, root.breathPhase, 0.6)
        }
    }

    // ── Sharp core waveform ──
    Canvas {
        id: coreCanvas
        anchors.fill: parent
        visible: root.active
        renderStrategy: Canvas.Cooperative

        onPaint: {
            var ctx = getContext("2d")
            drawWaveform(ctx, width, height, root.currentSamples,
                         root.amplitude, root.thickness,
                         root.waveColor, root.breathPhase, 1.0)
        }
    }

    // ── Idle flat line ──
    Canvas {
        id: idleCanvas
        anchors.fill: parent
        visible: !root.active
        renderStrategy: Canvas.Cooperative

        onPaint: {
            var ctx = getContext("2d")
            var w = width, h = height, midY = h / 2
            ctx.clearRect(0, 0, w, h)

            var breathe = 0.4 + 0.15 * Math.sin(root.breathPhase * 1.5)

            ctx.strokeStyle = Qt.rgba(root.waveColor.r, root.waveColor.g,
                                      root.waveColor.b, breathe)
            ctx.lineWidth = 1.0
            ctx.beginPath()
            ctx.moveTo(0, midY)
            ctx.lineTo(w, midY)
            ctx.stroke()
        }
    }

    // ── Shared drawing function with cubic interpolation ──
    function drawWaveform(ctx, w, h, samples, amp, lineW, color, breath, alphaFactor) {
        var midY = h / 2
        ctx.clearRect(0, 0, w, h)

        if (!samples || samples.length < 2) return

        var breathe = 0.85 + 0.15 * Math.sin(breath * 2.0)
        var r = color.r, g = color.g, b = color.b
        ctx.strokeStyle = Qt.rgba(r * breathe, g * breathe, b * breathe, alphaFactor * breathe)
        ctx.lineWidth = lineW
        ctx.lineJoin = "round"
        ctx.lineCap = "round"
        ctx.beginPath()

        var n = samples.length
        var stepX = w / (n - 1)

        // First point
        var y0 = midY - samples[0] * amp * (h * 0.45)
        ctx.moveTo(0, y0)

        // Cubic Bézier interpolation between sample points
        for (var i = 1; i < n; ++i) {
            var x = i * stepX
            var y = midY - samples[i] * amp * (h * 0.45)
            var xPrev = (i - 1) * stepX
            var yPrev = midY - samples[i - 1] * amp * (h * 0.45)

            // Control points for smooth cubic curve
            var cpx1 = xPrev + stepX * 0.5
            var cpy1 = yPrev
            var cpx2 = x - stepX * 0.5
            var cpy2 = y
            ctx.bezierCurveTo(cpx1, cpy1, cpx2, cpy2, x, y)
        }

        ctx.stroke()
    }

    // ── 60 FPS animation timer ──
    // ── Tampon pré-alloué (évite new Array() à chaque frame, réduit GC) ──
    property var _scratch: {
        var a = []
        for (var i = 0; i < sampleCount; ++i) a.push(0.0)
        return a
    }

    // ── Timer adaptatif : 60 FPS actif / 12 FPS idle ──
    Timer {
        id: animTimer
        interval: root.active ? 16 : 83   // 60 FPS actif, 12 FPS idle
        running: root.visible
        repeat: true
        onTriggered: {
            root.breathPhase += interval / 1000.0

            // Interpolation in-place (réutilise root._scratch, pas de new Array)
            if (root.active && root.targetSamples.length > 0) {
                var curr = root.currentSamples
                var tgt  = root.targetSamples
                var n    = root.sampleCount
                var lerp = root.smoothFactor
                var buf  = root._scratch

                if (curr.length !== n) {
                    for (var k = 0; k < n; ++k) buf[k] = 0.0
                } else {
                    for (var i = 0; i < n; ++i) {
                        var c = curr[i] !== undefined ? curr[i] : 0.0
                        var t = i < tgt.length ? tgt[i] : 0.0
                        buf[i] = c + (t - c) * lerp
                    }
                }
                root.currentSamples = buf.slice()   // slice une seule fois
            }

            // Decay en idle (seulement si énergie résiduelle)
            if (!root.active && root.currentSamples.length > 0) {
                var decay = root.currentSamples
                var hasEnergy = false
                for (var d = 0; d < decay.length; ++d) {
                    decay[d] *= 0.92
                    if (Math.abs(decay[d]) > 0.001) hasEnergy = true
                }
                if (!hasEnergy) {
                    root.currentSamples = []
                    return   // rien à dessiner
                }
                root.currentSamples = decay
            }

            if (root.active) {
                glowCanvas.requestPaint()
                midGlowCanvas.requestPaint()
                coreCanvas.requestPaint()
            } else {
                idleCanvas.requestPaint()
            }
        }
    }
}
