import QtQuick

// ═══════════════════════════════════════════════════════
//  ExoVisualizer — Visualiseur d'onde audio Canvas
// ═══════════════════════════════════════════════════════

Item {
    id: root

    property real audioLevel: 0.0
    property bool active: false
    property color lineColor: "#007ACC"
    property real lineWidth: 1.5
    property real preferredHeight: 100

    property real iTime: 0.0
    property real smoothLevel: 0.0

    onAudioLevelChanged: {
        smoothLevel = smoothLevel * 0.7 + audioLevel * 0.3
    }

    implicitHeight: preferredHeight

    Canvas {
        id: waveCanvas
        anchors.fill: parent
        visible: true
        renderStrategy: Canvas.Cooperative

        onPaint: {
            var ctx = getContext("2d")
            var w = width
            var h = height
            var midY = h / 2

            ctx.clearRect(0, 0, w, h)

            if (!root.active) {
                ctx.strokeStyle = Qt.rgba(0, 0.478, 0.8, 0.2)
                ctx.lineWidth = root.lineWidth
                ctx.beginPath()
                ctx.moveTo(0, midY)
                ctx.lineTo(w, midY)
                ctx.stroke()
                return
            }

            ctx.strokeStyle = root.lineColor
            ctx.lineWidth = root.lineWidth
            ctx.lineJoin = "round"
            ctx.lineCap = "round"
            ctx.beginPath()

            var steps = Math.min(w, 200)
            for (var i = 0; i <= steps; i++) {
                var x = (i / steps) * w
                var nx = i / steps
                var amplitude = root.smoothLevel * (h * 0.38)
                var wave = Math.sin(nx * 25.0 + root.iTime * 3.0) * amplitude
                         + Math.sin(nx * 15.0 - root.iTime * 2.1 + 1.5) * amplitude * 0.6
                         + Math.sin(nx * 40.0 + root.iTime * 4.5 + 0.8) * amplitude * 0.3
                var y = midY + wave
                if (i === 0) ctx.moveTo(x, y)
                else ctx.lineTo(x, y)
            }
            ctx.stroke()
        }
    }

    Timer {
        interval: 50  // fix audit T11: 20 FPS suffisant pour une onde sinusoïdale
        running: root.active && root.visible
        repeat: true
        onTriggered: {
            root.iTime += interval / 1000.0
            waveCanvas.requestPaint()
        }
    }
}
