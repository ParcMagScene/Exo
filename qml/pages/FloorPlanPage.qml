import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RaspberryAssistant
import "../theme"
import "../components"

// ═══════════════════════════════════════════════════════
//  FloorPlanPage — Éditeur 2D de plan de logement v27
//
//  Architecture MVC :
//   • FloorPlanModel   — données (C++)
//   • FloorPlanController — logique outil/undo/sélection (C++)
//   • FloorPlanTools/Properties/FurniturePalette — UI (QML)
//
//  Fonctionnalités :
//   • Canvas 2D (murs, portes, fenêtres, pièces, capteurs)
//   • Sélection simple/multiple (rubber band, Shift+click)
//   • Déplacement, rotation, suppression
//   • Dessin (wall/room rect-draw, point-place pour le reste)
//   • Zoom / Pan (molette, pinch, drag)
//   • Grille + magnétisme axial (snap-to-grid, snap-to-object-axis)
//   • Undo/Redo C++ (FloorPlanController, 200 niveaux)
//   • FloorPlanProperties (panneau dynamique)
//   • Sauvegarde / Chargement JSON multi-logements
//   • FurniturePalette (catalogue mobilier)
// ═══════════════════════════════════════════════════════

Rectangle {
    id: root
    color: Theme.bgPrimary

    // ── Modèle C++ injecté ──
    property var floorModel: null   // FloorPlanModel*

    // ── Contrôleur ──
    FloorPlanController {
        id: controller
        model: floorModel
    }

    // ── Viewport state ──
    property real zoom: 1.0
    property real panX: 0
    property real panY: 0

    // ── Convenience aliases ──
    property string currentTool: controller.currentTool
    property var selectedIds: controller.selectedIds

    // ── Rubber band ──
    property bool rubberBanding: false
    property real rubberX0: 0
    property real rubberY0: 0
    property real rubberX1: 0
    property real rubberY1: 0

    // ── Drawing state (wall/room rect-draw) ──
    property bool drawing: false
    property real drawX0: 0
    property real drawY0: 0

    // ── Drag state ──
    property bool draggingItems: false
    property real dragStartX: 0
    property real dragStartY: 0
    property var  dragStartPositions: ({})  // id → {x, y}

    // ── Pan state ──
    property bool panning: false
    property real panStartX: 0
    property real panStartY: 0
    property real panStartPanX: 0
    property real panStartPanY: 0

    // ── Rotation handle ──
    property string rotatingId: ""
    property real rotateStartAngle: 0

    // ── Alignment guides ──
    property var alignGuides: ({hLines: [], vLines: []})

    // ══════════════════════════════════════════════
    //  COORDINATE HELPERS
    // ══════════════════════════════════════════════

    function screenToWorld(sx, sy) {
        return Qt.point((sx - panX) / zoom, (sy - panY) / zoom)
    }

    function worldToScreen(wx, wy) {
        return Qt.point(wx * zoom + panX, wy * zoom + panY)
    }

    function snapPoint(p) {
        if (!floorModel) return p
        var snapped = floorModel.snapToGrid(p)
        if (floorModel.snapEnabled) {
            // Axis-independent snap
            snapped = floorModel.snapToObjectAxis(snapped, Qt.size(10, 10))
        }
        return snapped
    }

    function snapPointWithSize(p, w, h, excludeId) {
        if (!floorModel) return p
        var snapped = floorModel.snapToGrid(p)
        if (floorModel.snapEnabled)
            snapped = floorModel.snapToObjectAxis(snapped, Qt.size(w, h), excludeId || "")
        return snapped
    }

    function hitTest(wx, wy) {
        if (!floorModel) return ""
        var ids = floorModel.getItemIds()
        // Reverse order: top-most items first
        for (var i = ids.length - 1; i >= 0; --i) {
            var d = floorModel.getItemData(ids[i])
            if (!d || !d.id) continue
            var ix = d.x || 0, iy = d.y || 0
            var iw = d.width || 10, ih = d.height || 10
            if (wx >= ix && wx <= ix + iw && wy >= iy && wy <= iy + ih)
                return d.id
        }
        return ""
    }

    function selectAll() {
        controller.selectAll()
        canvas.requestPaint()
    }

    function deleteSelected() {
        controller.deleteSelected()
        canvas.requestPaint()
    }

    function centerView() {
        panX = canvas.width / 2
        panY = canvas.height / 2
        zoom = 1.0
        canvas.requestPaint()
    }

    // ══════════════════════════════════════════════
    //  MODEL CONNECTIONS
    // ══════════════════════════════════════════════

    Connections {
        target: floorModel
        function onItemAdded()   { canvas.requestPaint() }
        function onItemRemoved() { canvas.requestPaint() }
        function onItemUpdated() { canvas.requestPaint() }
        function onModelReset()  { selectedIds = []; canvas.requestPaint() }
    }

    // ══════════════════════════════════════════════
    //  KEYBOARD SHORTCUTS
    // ══════════════════════════════════════════════

    focus: true

    Keys.onPressed: function(event) {
        if (event.modifiers & Qt.ControlModifier) {
            if (event.key === Qt.Key_Z) { controller.undo(); canvas.requestPaint(); event.accepted = true }
            else if (event.key === Qt.Key_Y) { controller.redo(); canvas.requestPaint(); event.accepted = true }
            else if (event.key === Qt.Key_A) { selectAll(); event.accepted = true }
            else if (event.key === Qt.Key_D) { controller.deselectAll(); canvas.requestPaint(); event.accepted = true }
            else if (event.key === Qt.Key_S) {
                controller.savePlan("")
                event.accepted = true
            }
        }
        if (event.key === Qt.Key_Delete || event.key === Qt.Key_Backspace) {
            deleteSelected()
            event.accepted = true
        }
        if (event.key === Qt.Key_Escape) {
            controller.deselectAll()
            controller.setTool("select")
            drawing = false
            furniturePalettePopup.visible = false
            canvas.requestPaint()
            event.accepted = true
        }
    }

    // ══════════════════════════════════════════════
    //  LAYOUT: Toolbar | Canvas | PropertyPanel
    // ══════════════════════════════════════════════

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ────────────────────────────────────────
        //  LEFT TOOLBAR (composant externe)
        // ────────────────────────────────────────
        FloorPlanTools {
            id: toolBar
            Layout.preferredWidth: 48
            Layout.fillHeight: true
            controller: controller
            floorModel: root.floorModel

            onZoomIn:  { zoom = Math.min(4.0, zoom * 1.25); canvas.requestPaint() }
            onZoomOut: { zoom = Math.max(0.2, zoom / 1.25); canvas.requestPaint() }
            onCenterView: root.centerView()
            onFurnitureRequested: { furniturePalettePopup.visible = !furniturePalettePopup.visible }
        }

        // ────────────────────────────────────────
        //  CENTRAL CANVAS AREA
        // ────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.bgPrimary
            clip: true

            // Status bar (top)
            Rectangle {
                id: statusBar
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 28
                color: Theme.bgSecondary
                z: 10

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacing8
                    anchors.rightMargin: Theme.spacing8
                    spacing: Theme.spacing16

                    Text {
                        text: floorModel ? ("📐 " + floorModel.planName) : "Plan"
                        font.pixelSize: Theme.fontSmall
                        font.weight: Font.Medium
                        color: Theme.textPrimary
                    }

                    Text {
                        text: "Zoom: " + Math.round(zoom * 100) + "%"
                        font.pixelSize: Theme.fontTiny
                        font.family: Theme.fontMono
                        color: Theme.textSecondary
                    }

                    Text {
                        text: "Items: " + (floorModel ? floorModel.count : 0)
                        font.pixelSize: Theme.fontTiny
                        font.family: Theme.fontMono
                        color: Theme.textSecondary
                    }

                    Text {
                        text: "Sélection: " + selectedIds.length
                        font.pixelSize: Theme.fontTiny
                        font.family: Theme.fontMono
                        color: selectedIds.length > 0 ? Theme.accent : Theme.textMuted
                    }

                    Text {
                        text: "Outil: " + controller.currentTool
                        font.pixelSize: Theme.fontTiny
                        font.family: Theme.fontMono
                        color: Theme.info
                    }

                    Item { Layout.fillWidth: true }

                    // Save / Load
                    Text {
                        text: "💾 Sauver"
                        font.pixelSize: Theme.fontTiny
                        color: saveMa.containsMouse ? Theme.accent : Theme.textSecondary

                        MouseArea {
                            id: saveMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: controller.savePlan("")
                        }
                    }

                    Text {
                        text: "📂 Charger"
                        font.pixelSize: Theme.fontTiny
                        color: loadMa.containsMouse ? Theme.accent : Theme.textSecondary

                        MouseArea {
                            id: loadMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: controller.openPlan("config/floorplan.json")
                        }
                    }
                }
            }

            // ── CANVAS ──
            Canvas {
                id: canvas
                anchors.fill: parent
                anchors.topMargin: statusBar.height
                renderStrategy: Canvas.Threaded

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.reset()
                    ctx.clearRect(0, 0, width, height)

                    // ── Background ──
                    ctx.fillStyle = "#1A1A1A"
                    ctx.fillRect(0, 0, width, height)

                    ctx.save()
                    ctx.translate(panX, panY)
                    ctx.scale(zoom, zoom)

                    // ── Grid ──
                    if (floorModel && floorModel.snapEnabled) {
                        drawGrid(ctx)
                    }

                    // ── Items ──
                    if (floorModel) {
                        var ids = floorModel.getItemIds()
                        for (var i = 0; i < ids.length; ++i) {
                            var d = floorModel.getItemData(ids[i])
                            if (d && d.id)
                                drawItem(ctx, d, selectedIds.indexOf(d.id) >= 0)
                        }
                    }

                    // ── Drawing preview ──
                    if (drawing && (currentTool === "wall" || currentTool === "room")) {
                        var wp = screenToWorld(drawX0, drawY0)
                        var wm = screenToWorld(canvasMouseX, canvasMouseY)
                        ctx.strokeStyle = Theme.accent
                        ctx.lineWidth = currentTool === "wall" ? 4 : 1
                        ctx.setLineDash([6, 4])
                        ctx.strokeRect(Math.min(wp.x, wm.x), Math.min(wp.y, wm.y),
                                       Math.abs(wm.x - wp.x), Math.abs(wm.y - wp.y))
                        ctx.setLineDash([])
                    }

                    ctx.restore()

                    // ── Alignment guides (world→screen) ──
                    if (draggingItems && alignGuides) {
                        ctx.save()
                        ctx.setLineDash([4, 4])
                        ctx.lineWidth = 1

                        var guides = alignGuides
                        if (guides.vLines) {
                            ctx.strokeStyle = "#FF6B6B"
                            for (var vi = 0; vi < guides.vLines.length; ++vi) {
                                var vx = guides.vLines[vi] * zoom + panX
                                ctx.beginPath()
                                ctx.moveTo(vx, 0)
                                ctx.lineTo(vx, canvas.height)
                                ctx.stroke()
                            }
                        }
                        if (guides.hLines) {
                            ctx.strokeStyle = "#4EC9B0"
                            for (var hi = 0; hi < guides.hLines.length; ++hi) {
                                var hy = guides.hLines[hi] * zoom + panY
                                ctx.beginPath()
                                ctx.moveTo(0, hy)
                                ctx.lineTo(canvas.width, hy)
                                ctx.stroke()
                            }
                        }

                        ctx.setLineDash([])
                        ctx.restore()
                    }

                    // ── Rubber band (screen space) ──
                    if (rubberBanding) {
                        ctx.save()
                        ctx.strokeStyle = Theme.accent
                        ctx.lineWidth = 1
                        ctx.setLineDash([4, 3])
                        ctx.fillStyle = Qt.rgba(0, 0.47, 0.83, 0.08)
                        var rx = Math.min(rubberX0, rubberX1)
                        var ry = Math.min(rubberY0, rubberY1)
                        var rw = Math.abs(rubberX1 - rubberX0)
                        var rh = Math.abs(rubberY1 - rubberY0)
                        ctx.fillRect(rx, ry, rw, rh)
                        ctx.strokeRect(rx, ry, rw, rh)
                        ctx.setLineDash([])
                        ctx.restore()
                    }
                }

                property real canvasMouseX: 0
                property real canvasMouseY: 0

                // ── GRID ──
                function drawGrid(ctx) {
                    var gs = floorModel.gridSize
                    if (gs <= 0) return

                    // Determine visible world bounds
                    var tl = screenToWorld(0, 0)
                    var br = screenToWorld(canvas.width, canvas.height)
                    var startX = Math.floor(tl.x / gs) * gs
                    var startY = Math.floor(tl.y / gs) * gs

                    ctx.strokeStyle = "#2A2A2A"
                    ctx.lineWidth = 0.5

                    ctx.beginPath()
                    for (var x = startX; x <= br.x; x += gs) {
                        ctx.moveTo(x, tl.y)
                        ctx.lineTo(x, br.y)
                    }
                    for (var y = startY; y <= br.y; y += gs) {
                        ctx.moveTo(tl.x, y)
                        ctx.lineTo(br.x, y)
                    }
                    ctx.stroke()

                    // Major grid lines (every 100px)
                    var major = gs * 10
                    startX = Math.floor(tl.x / major) * major
                    startY = Math.floor(tl.y / major) * major
                    ctx.strokeStyle = "#333333"
                    ctx.lineWidth = 1

                    ctx.beginPath()
                    for (x = startX; x <= br.x; x += major) {
                        ctx.moveTo(x, tl.y)
                        ctx.lineTo(x, br.y)
                    }
                    for (y = startY; y <= br.y; y += major) {
                        ctx.moveTo(tl.x, y)
                        ctx.lineTo(br.x, y)
                    }
                    ctx.stroke()
                }

                // ── ITEM RENDERING ──
                function drawItem(ctx, d, isSelected) {
                    var x = d.x || 0, y = d.y || 0
                    var w = d.width || 10, h = d.height || 10
                    var rot = d.rotation || 0
                    var type = (d.type || "furniture").toLowerCase()

                    ctx.save()
                    if (rot !== 0) {
                        ctx.translate(x + w / 2, y + h / 2)
                        ctx.rotate(rot * Math.PI / 180)
                        ctx.translate(-(x + w / 2), -(y + h / 2))
                    }

                    switch (type) {
                    case "wall":
                        ctx.fillStyle = "#8B8B8B"
                        ctx.fillRect(x, y, w, h)
                        ctx.strokeStyle = "#606060"
                        ctx.lineWidth = 1
                        ctx.strokeRect(x, y, w, h)
                        break

                    case "door":
                        // Door: gap in wall with arc
                        ctx.fillStyle = "#1A1A1A"
                        ctx.fillRect(x, y, w, h)
                        ctx.strokeStyle = "#4EC9B0"
                        ctx.lineWidth = 2
                        ctx.beginPath()
                        ctx.arc(x, y + h, w, -Math.PI / 2, 0)
                        ctx.stroke()
                        // Swing line
                        ctx.setLineDash([3, 2])
                        ctx.beginPath()
                        ctx.moveTo(x, y + h)
                        ctx.lineTo(x + w, y + h)
                        ctx.stroke()
                        ctx.setLineDash([])
                        break

                    case "window":
                        ctx.fillStyle = "#2A4A6A"
                        ctx.fillRect(x, y, w, h)
                        ctx.strokeStyle = "#569CD6"
                        ctx.lineWidth = 2
                        ctx.strokeRect(x, y, w, h)
                        // Center line
                        ctx.beginPath()
                        ctx.moveTo(x + w / 2, y)
                        ctx.lineTo(x + w / 2, y + h)
                        ctx.stroke()
                        break

                    case "room":
                        ctx.fillStyle = "rgba(45, 82, 115, 0.15)"
                        ctx.fillRect(x, y, w, h)
                        ctx.strokeStyle = "#3A96DD"
                        ctx.lineWidth = 1
                        ctx.setLineDash([8, 4])
                        ctx.strokeRect(x, y, w, h)
                        ctx.setLineDash([])
                        // Room label
                        var label = (d.properties && d.properties.name) ? d.properties.name : "Pièce"
                        ctx.fillStyle = "#3A96DD"
                        ctx.font = "12px Inter, sans-serif"
                        ctx.textAlign = "center"
                        ctx.fillText(label, x + w / 2, y + h / 2 + 4)
                        break

                    case "furniture":
                        ctx.fillStyle = "#5A4A3A"
                        ctx.fillRect(x, y, w, h)
                        ctx.strokeStyle = "#8A7A6A"
                        ctx.lineWidth = 1
                        ctx.strokeRect(x, y, w, h)
                        break

                    case "device":
                        ctx.fillStyle = "#3A5A3A"
                        ctx.fillRect(x, y, w, h)
                        ctx.strokeStyle = "#4EC9B0"
                        ctx.lineWidth = 1.5
                        ctx.strokeRect(x, y, w, h)
                        // Bulb icon
                        ctx.fillStyle = "#DCDCAA"
                        ctx.font = "14px sans-serif"
                        ctx.textAlign = "center"
                        ctx.fillText("💡", x + w / 2, y + h / 2 + 5)
                        break

                    case "camera":
                        // Camera body
                        ctx.fillStyle = "#4A3A5A"
                        ctx.fillRect(x, y, w, h)
                        ctx.strokeStyle = "#C586C0"
                        ctx.lineWidth = 1.5
                        ctx.strokeRect(x, y, w, h)
                        // Vision cone
                        var cx = x + w / 2, cy = y + h / 2
                        var coneLen = Math.max(w, h) * 2.5
                        var coneAngle = Math.PI / 4 // 45° spread
                        var baseAngle = (rot || 0) * Math.PI / 180
                        ctx.fillStyle = "rgba(197, 134, 192, 0.10)"
                        ctx.strokeStyle = "rgba(197, 134, 192, 0.25)"
                        ctx.lineWidth = 1
                        ctx.beginPath()
                        ctx.moveTo(cx, cy)
                        ctx.lineTo(cx + coneLen * Math.cos(baseAngle - coneAngle / 2),
                                   cy + coneLen * Math.sin(baseAngle - coneAngle / 2))
                        ctx.arc(cx, cy, coneLen, baseAngle - coneAngle / 2, baseAngle + coneAngle / 2)
                        ctx.closePath()
                        ctx.fill()
                        ctx.stroke()
                        break

                    case "sensor":
                        // Sensor: circle with pulse rings
                        var scx = x + w / 2, scy = y + h / 2
                        var sr = Math.min(w, h) / 2
                        ctx.fillStyle = "#2D5273"
                        ctx.beginPath()
                        ctx.arc(scx, scy, sr, 0, 2 * Math.PI)
                        ctx.fill()
                        ctx.strokeStyle = "#569CD6"
                        ctx.lineWidth = 1.5
                        ctx.stroke()
                        // Pulse rings
                        for (var ring = 1; ring <= 2; ++ring) {
                            ctx.strokeStyle = Qt.rgba(0.34, 0.61, 0.84, 0.3 / ring)
                            ctx.lineWidth = 1
                            ctx.beginPath()
                            ctx.arc(scx, scy, sr + ring * 8, 0, 2 * Math.PI)
                            ctx.stroke()
                        }
                        break

                    default:
                        ctx.fillStyle = "#3C3C3C"
                        ctx.fillRect(x, y, w, h)
                        ctx.strokeStyle = "#505050"
                        ctx.lineWidth = 1
                        ctx.strokeRect(x, y, w, h)
                        break
                    }

                    // ── Selection highlight ──
                    if (isSelected) {
                        ctx.strokeStyle = Theme.accent
                        ctx.lineWidth = 2
                        ctx.setLineDash([])
                        ctx.strokeRect(x - 2, y - 2, w + 4, h + 4)

                        // Corner handles
                        var handleSize = 6
                        ctx.fillStyle = Theme.accent
                        var corners = [
                            [x - handleSize / 2, y - handleSize / 2],
                            [x + w - handleSize / 2, y - handleSize / 2],
                            [x - handleSize / 2, y + h - handleSize / 2],
                            [x + w - handleSize / 2, y + h - handleSize / 2],
                        ]
                        for (var ci = 0; ci < corners.length; ++ci)
                            ctx.fillRect(corners[ci][0], corners[ci][1], handleSize, handleSize)

                        // Rotation handle (top center)
                        ctx.beginPath()
                        ctx.arc(x + w / 2, y - 16, 5, 0, 2 * Math.PI)
                        ctx.fillStyle = "#C586C0"
                        ctx.fill()
                        ctx.strokeStyle = "#E0E0E0"
                        ctx.lineWidth = 1
                        ctx.stroke()
                        // Line to rotation handle
                        ctx.beginPath()
                        ctx.moveTo(x + w / 2, y)
                        ctx.lineTo(x + w / 2, y - 11)
                        ctx.strokeStyle = "#C586C0"
                        ctx.lineWidth = 1
                        ctx.stroke()
                    }

                    // ── Linked device indicator ──
                    if (d.linkedDeviceId && d.linkedDeviceId.length > 0) {
                        ctx.fillStyle = "#4EC9B0"
                        ctx.beginPath()
                        ctx.arc(x + w - 3, y + 3, 4, 0, 2 * Math.PI)
                        ctx.fill()
                    }

                    ctx.restore()
                }
            }

            // ── MOUSE INTERACTION LAYER ──
            MouseArea {
                id: interactionArea
                anchors.fill: canvas
                anchors.topMargin: statusBar.height
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton

                onPositionChanged: function(mouse) {
                    canvas.canvasMouseX = mouse.x
                    canvas.canvasMouseY = mouse.y

                    // ── Pan ──
                    if (panning) {
                        panX = panStartPanX + (mouse.x - panStartX)
                        panY = panStartPanY + (mouse.y - panStartY)
                        canvas.requestPaint()
                        return
                    }

                    // ── Rubber band ──
                    if (rubberBanding) {
                        rubberX1 = mouse.x
                        rubberY1 = mouse.y
                        canvas.requestPaint()
                        return
                    }

                    // ── Drag items ──
                    if (draggingItems && selectedIds.length > 0) {
                        var wNow = screenToWorld(mouse.x, mouse.y)
                        var wStart = screenToWorld(dragStartX, dragStartY)
                        var dx = wNow.x - wStart.x
                        var dy = wNow.y - wStart.y
                        for (var i = 0; i < selectedIds.length; ++i) {
                            var sid = selectedIds[i]
                            var sp = dragStartPositions[sid]
                            if (sp) {
                                var newPos = Qt.point(sp.x + dx, sp.y + dy)
                                var dd = floorModel ? floorModel.getItemData(sid) : null
                                var iw = dd ? (dd.width || 10) : 10
                                var ih = dd ? (dd.height || 10) : 10
                                if (floorModel && floorModel.snapEnabled) {
                                    newPos = floorModel.snapToGrid(newPos)
                                    newPos = floorModel.snapToObjectAxis(newPos, Qt.size(iw, ih), sid)
                                    alignGuides = floorModel.findGuides(newPos, Qt.size(iw, ih), sid)
                                } else {
                                    alignGuides = {hLines: [], vLines: []}
                                }
                                floorModel.moveItem(sid, newPos.x, newPos.y)
                            }
                        }
                        canvas.requestPaint()
                        return
                    }

                    // Drawing preview
                    if (drawing)
                        canvas.requestPaint()
                }

                onPressed: function(mouse) {
                    root.forceActiveFocus()

                    // ── Middle button → pan ──
                    if (mouse.button === Qt.MiddleButton) {
                        panning = true
                        panStartX = mouse.x
                        panStartY = mouse.y
                        panStartPanX = panX
                        panStartPanY = panY
                        return
                    }

                    // ── Right click → context ──
                    if (mouse.button === Qt.RightButton) {
                        // ignore for now
                        return
                    }

                    var wp = screenToWorld(mouse.x, mouse.y)

                    // ── Eraser tool ──
                    if (currentTool === "eraser") {
                        var erasedId = hitTest(wp.x, wp.y)
                        if (erasedId) {
                            controller.deleteItemWithUndo(erasedId)
                            canvas.requestPaint()
                        }
                        return
                    }

                    // ── Drawing tools ──
                    if (currentTool === "wall" || currentTool === "room") {
                        drawing = true
                        drawX0 = mouse.x
                        drawY0 = mouse.y
                        return
                    }

                    if (currentTool !== "select" && floorModel) {
                        var snapped = snapPoint(wp)
                        var defaults = _defaultSizeForType(currentTool)
                        var newData = {x: snapped.x, y: snapped.y,
                                       width: defaults.w, height: defaults.h,
                                       rotation: 0}
                        var newId = controller.createItemWithUndo(newData)
                        controller.selectItem(newId, false)
                        canvas.requestPaint()
                        return
                    }

                    // ── Select tool ──
                    var hitId = hitTest(wp.x, wp.y)

                    // Check rotation handle
                    if (selectedIds.length === 1 && hitId === "") {
                        var selD = floorModel ? floorModel.getItemData(selectedIds[0]) : null
                        if (selD) {
                            var handleWorldX = (selD.x || 0) + (selD.width || 10) / 2
                            var handleWorldY = (selD.y || 0) - 16
                            var hdist = Math.sqrt(Math.pow(wp.x - handleWorldX, 2) + Math.pow(wp.y - handleWorldY, 2))
                            if (hdist < 10 / zoom) {
                                rotatingId = selectedIds[0]
                                rotateStartAngle = selD.rotation || 0
                                return
                            }
                        }
                    }

                    if (hitId) {
                        var shiftHeld = (mouse.modifiers & Qt.ShiftModifier)
                        controller.selectItem(hitId, shiftHeld)

                        // Start drag
                        draggingItems = true
                        dragStartX = mouse.x
                        dragStartY = mouse.y
                        dragStartPositions = {}
                        var curSel = controller.selectedIds
                        for (var di = 0; di < curSel.length; ++di) {
                            var dd = floorModel ? floorModel.getItemData(curSel[di]) : null
                            if (dd)
                                dragStartPositions[curSel[di]] = {x: dd.x || 0, y: dd.y || 0}
                        }
                    } else {
                        // Start rubber band
                        if (!(mouse.modifiers & Qt.ShiftModifier))
                            controller.deselectAll()
                        rubberBanding = true
                        rubberX0 = mouse.x
                        rubberY0 = mouse.y
                        rubberX1 = mouse.x
                        rubberY1 = mouse.y
                    }

                    canvas.requestPaint()
                }

                onReleased: function(mouse) {
                    // ── Pan end ──
                    if (panning) {
                        panning = false
                        return
                    }

                    // ── Rotation end ──
                    if (rotatingId !== "") {
                        var wp2 = screenToWorld(mouse.x, mouse.y)
                        var rd = floorModel ? floorModel.getItemData(rotatingId) : null
                        if (rd && floorModel) {
                            var rcx = (rd.x || 0) + (rd.width || 10) / 2
                            var rcy = (rd.y || 0) + (rd.height || 10) / 2
                            var angle = Math.atan2(wp2.y - rcy, wp2.x - rcx) * 180 / Math.PI + 90
                            angle = Math.round(angle / 15) * 15 // snap to 15° increments
                            controller.rotateItemWithUndo(rotatingId, angle)
                        }
                        rotatingId = ""
                        canvas.requestPaint()
                        return
                    }

                    // ── Drag end ──
                    if (draggingItems) {
                        draggingItems = false
                        alignGuides = {hLines: [], vLines: []}
                        // Record undo for each moved item
                        var curIds = controller.selectedIds
                        for (var mi = 0; mi < curIds.length; ++mi) {
                            var mid = curIds[mi]
                            var sp2 = dragStartPositions[mid]
                            var md = floorModel ? floorModel.getItemData(mid) : null
                            if (sp2 && md && (sp2.x !== (md.x || 0) || sp2.y !== (md.y || 0))) {
                                controller.moveItemWithUndo(mid, md.x || 0, md.y || 0)
                            }
                        }
                        dragStartPositions = {}
                        canvas.requestPaint()
                        return
                    }

                    // ── Drawing end ──
                    if (drawing) {
                        drawing = false
                        if (floorModel) {
                            var wp0 = screenToWorld(drawX0, drawY0)
                            var wp1 = screenToWorld(mouse.x, mouse.y)
                            var rx = Math.min(wp0.x, wp1.x)
                            var ry = Math.min(wp0.y, wp1.y)
                            var rw = Math.abs(wp1.x - wp0.x)
                            var rh = Math.abs(wp1.y - wp0.y)
                            if (rw > 3 && rh > 3) {
                                if (currentTool === "wall") {
                                    // Construct wall as thin rect
                                    if (rw > rh) rh = Math.max(rh, 6)
                                    else rw = Math.max(rw, 6)
                                }
                                var snp = snapPoint(Qt.point(rx, ry))
                                var drawnData = {x: snp.x, y: snp.y, width: rw, height: rh, rotation: 0}
                                var drawnId = controller.createItemWithUndo(drawnData)
                                controller.selectItem(drawnId, false)
                            }
                        }
                        canvas.requestPaint()
                        return
                    }

                    // ── Rubber band end ──
                    if (rubberBanding) {
                        rubberBanding = false
                        // Select all items in rubber band
                        if (floorModel) {
                            var rbtl = screenToWorld(Math.min(rubberX0, rubberX1), Math.min(rubberY0, rubberY1))
                            var rbbr = screenToWorld(Math.max(rubberX0, rubberX1), Math.max(rubberY0, rubberY1))
                            var rubberW = rbbr.x - rbtl.x
                            var rubberH = rbbr.y - rbtl.y
                            if (rubberW > 2 && rubberH > 2) {
                                controller.selectRect(rbtl.x, rbtl.y, rubberW, rubberH)
                            }
                        }
                        canvas.requestPaint()
                    }
                }

                onWheel: function(wheel) {
                    var factor = wheel.angleDelta.y > 0 ? 1.1 : (1.0 / 1.1)
                    var newZoom = Math.max(0.2, Math.min(4.0, zoom * factor))

                    // Zoom toward cursor
                    var wx = (wheel.x - panX) / zoom
                    var wy = (wheel.y - panY) / zoom
                    zoom = newZoom
                    panX = wheel.x - wx * zoom
                    panY = wheel.y - wy * zoom

                    canvas.requestPaint()
                }
            }

            // ── Pinch/Multi-touch zoom ──
            PinchHandler {
                id: pinchHandler
                target: null
                minimumScale: 0.2
                maximumScale: 4.0

                onScaleChanged: {
                    zoom = Math.max(0.2, Math.min(4.0, zoom * (pinchHandler.activeScale / pinchHandler.oldScale)))
                    canvas.requestPaint()
                }
                property real oldScale: 1.0
                onActiveScaleChanged: oldScale = activeScale
            }
        }

        // ────────────────────────────────────────
        //  RIGHT PROPERTY PANEL (composant externe)
        // ────────────────────────────────────────
        FloorPlanProperties {
            id: propertyPanel
            Layout.preferredWidth: selectedIds.length > 0 ? 240 : 0
            Layout.fillHeight: true
            visible: selectedIds.length > 0
            controller: controller
            floorModel: root.floorModel

            Behavior on Layout.preferredWidth {
                NumberAnimation { duration: Theme.animNormal; easing.type: Easing.OutCubic }
            }
        }
    }

    // ── FurniturePalette popup ──
    FurniturePalette {
        id: furniturePalettePopup
        visible: false
        width: 420
        height: 380
        x: 60
        y: (root.height - height) / 2
        z: 100
        controller: controller

        onClosed: furniturePalettePopup.visible = false
    }

    // ══════════════════════════════════════════════
    //  HELPERS
    // ══════════════════════════════════════════════

    function _defaultSizeForType(type) {
        switch (type) {
        case "wall":      return {w: 100, h: 6}
        case "door":      return {w: 30,  h: 6}
        case "window":    return {w: 40,  h: 6}
        case "room":      return {w: 120, h: 100}
        case "furniture": return {w: 40,  h: 40}
        case "device":    return {w: 20,  h: 20}
        case "camera":    return {w: 16,  h: 16}
        case "sensor":    return {w: 14,  h: 14}
        default:          return {w: 30,  h: 30}
        }
    }

    function applyPropertyChange() {
        // Deprecated — handled by FloorPlanProperties component
    }

    // Initial center
    Component.onCompleted: {
        centerView()
        controller.openPlan("config/floorplan.json")
    }
}
