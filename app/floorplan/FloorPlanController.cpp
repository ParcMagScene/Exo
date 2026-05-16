#include "FloorPlanController.h"

#include <QDir>
#include <QFileInfo>
#include <cmath>
#include <algorithm>
#include <limits>

// ═══════════════════════════════════════════════════════
//  FloorPlanController — bridge between QML and Model
// ═══════════════════════════════════════════════════════

FloorPlanController::FloorPlanController(QObject *parent)
    : QObject(parent)
{}

// ── model binding ────────────────────────────────────

void FloorPlanController::setModel(FloorPlanModel *m)
{
    if (m_model == m) return;
    m_model = m;
    emit modelChanged();
}

// ── tool ─────────────────────────────────────────────

void FloorPlanController::setTool(const QString &tool)
{
    if (m_currentTool == tool) return;
    if (m_actionInProgress)
        cancelAction();
    m_currentTool = tool;
    emit toolChanged();
}

// ══════════════════════════════════════════════════════
//  ACTION PROTOCOL — begin/update/end for drawing
// ══════════════════════════════════════════════════════

void FloorPlanController::beginAction(qreal x, qreal y)
{
    if (m_actionInProgress || !m_model) return;

    m_actionInProgress = true;
    m_actionOrigin = QPointF(x, y);
    m_actionPreviewId.clear();

    emit actionInProgressChanged();
    emit actionStarted(m_currentTool, x, y);
}

void FloorPlanController::updateAction(qreal x, qreal y)
{
    if (!m_actionInProgress) return;
    emit actionUpdated(x, y);
}

QString FloorPlanController::endAction(qreal x, qreal y)
{
    if (!m_actionInProgress || !m_model) {
        cancelAction();
        return {};
    }

    m_actionInProgress = false;
    emit actionInProgressChanged();

    const qreal dx = x - m_actionOrigin.x();
    const qreal dy = y - m_actionOrigin.y();

    // Minimum size threshold
    const bool isDraw = (m_currentTool == QStringLiteral("wall") ||
                         m_currentTool == QStringLiteral("room"));

    if (isDraw) {
        qreal rx = std::min(m_actionOrigin.x(), x);
        qreal ry = std::min(m_actionOrigin.y(), y);
        qreal rw = std::abs(dx);
        qreal rh = std::abs(dy);

        if (rw < 3 && rh < 3) {
            emit actionCancelled();
            return {};
        }

        // For walls: ensure minimum thickness
        if (m_currentTool == QStringLiteral("wall")) {
            if (rw > rh) rh = std::max(rh, 6.0);
            else         rw = std::max(rw, 6.0);
        }

        QPointF snapped = applySnap(QPointF(rx, ry));
        QVariantMap data;
        data[QStringLiteral("x")]        = snapped.x();
        data[QStringLiteral("y")]        = snapped.y();
        data[QStringLiteral("width")]    = rw;
        data[QStringLiteral("height")]   = rh;
        data[QStringLiteral("rotation")] = 0.0;

        QString id = createItemWithUndo(m_currentTool, data);
        m_selectedIds = {id};
        emit selectionChanged();
        emit actionFinished(id);
        return id;
    }

    // Point-place tools (furniture, camera, sensor, device, door, window)
    if (m_currentTool != QStringLiteral("select") &&
        m_currentTool != QStringLiteral("eraser")) {

        QPointF snapped = applySnap(QPointF(x, y));
        QVariantMap data = defaultDataForTool(m_currentTool);
        data[QStringLiteral("x")] = snapped.x();
        data[QStringLiteral("y")] = snapped.y();

        QString id = createItemWithUndo(m_currentTool, data);
        m_selectedIds = {id};
        emit selectionChanged();
        emit actionFinished(id);
        return id;
    }

    emit actionFinished({});
    return {};
}

void FloorPlanController::cancelAction()
{
    if (!m_actionInProgress) return;
    m_actionInProgress = false;
    m_actionPreviewId.clear();
    emit actionInProgressChanged();
    emit actionCancelled();
}

// ══════════════════════════════════════════════════════
//  UNDO / REDO
// ══════════════════════════════════════════════════════

void FloorPlanController::pushUndo(UndoAction::Type type,
                                   const QString &itemId,
                                   const QVariantMap &before,
                                   const QVariantMap &after)
{
    m_undoStack.append({type, itemId, before, after});
    if (m_undoStack.size() > MAX_UNDO_DEPTH)
        m_undoStack.removeFirst();
    m_redoStack.clear();
    emit undoStateChanged();
}

void FloorPlanController::undo()
{
    if (m_undoStack.isEmpty() || !m_model) return;
    UndoAction action = m_undoStack.takeLast();
    m_redoStack.append(action);
    applyAction(action, true);
    emit undoStateChanged();
}

void FloorPlanController::redo()
{
    if (m_redoStack.isEmpty() || !m_model) return;
    UndoAction action = m_redoStack.takeLast();
    m_undoStack.append(action);
    applyAction(action, false);
    emit undoStateChanged();
}

void FloorPlanController::clearUndoHistory()
{
    m_undoStack.clear();
    m_redoStack.clear();
    emit undoStateChanged();
}

void FloorPlanController::applyAction(const UndoAction &action, bool isUndo)
{
    const QVariantMap &data = isUndo ? action.before : action.after;

    switch (action.type) {
    case UndoAction::Add:
        if (isUndo)
            m_model->deleteItem(action.itemId);
        else
            m_model->createItem(data.value(QStringLiteral("type")).toString(), data);
        break;

    case UndoAction::Remove:
        if (isUndo)
            m_model->createItem(data.value(QStringLiteral("type")).toString(), data);
        else
            m_model->deleteItem(action.itemId);
        break;

    case UndoAction::Move:
        m_model->moveItem(action.itemId,
                          data.value(QStringLiteral("x")).toReal(),
                          data.value(QStringLiteral("y")).toReal());
        break;

    case UndoAction::Rotate:
        m_model->rotateItem(action.itemId,
                            data.value(QStringLiteral("rotation")).toReal());
        break;

    case UndoAction::Update:
        m_model->setItemData(action.itemId, data);
        break;
    }
}

// ══════════════════════════════════════════════════════
//  SELECTION
// ══════════════════════════════════════════════════════

void FloorPlanController::setSelectedIds(const QStringList &ids)
{
    if (m_selectedIds == ids) return;
    m_selectedIds = ids;
    emit selectionChanged();
}

void FloorPlanController::selectItem(const QString &id, bool addToSelection)
{
    if (addToSelection) {
        if (!m_selectedIds.contains(id)) {
            m_selectedIds.append(id);
            emit selectionChanged();
        }
    } else {
        m_selectedIds = {id};
        emit selectionChanged();
    }
}

void FloorPlanController::deselectItem(const QString &id)
{
    if (m_selectedIds.removeAll(id) > 0)
        emit selectionChanged();
}

void FloorPlanController::selectRect(qreal x, qreal y, qreal w, qreal h, bool addToSelection)
{
    if (!m_model) return;
    QStringList inRect = m_model->itemsInRect(x, y, w, h);

    if (addToSelection) {
        for (const auto &id : inRect) {
            if (!m_selectedIds.contains(id))
                m_selectedIds.append(id);
        }
    } else {
        m_selectedIds = inRect;
    }
    emit selectionChanged();
}

void FloorPlanController::selectAll()
{
    if (!m_model) return;
    m_selectedIds = m_model->getItemIds();
    emit selectionChanged();
}

void FloorPlanController::deselectAll()
{
    if (m_selectedIds.isEmpty()) return;
    m_selectedIds.clear();
    emit selectionChanged();
}

void FloorPlanController::deleteSelected()
{
    if (!m_model || m_selectedIds.isEmpty()) return;

    for (const auto &id : std::as_const(m_selectedIds)) {
        QVariantMap before = m_model->getItemData(id);
        if (!before.isEmpty()) {
            pushUndo(UndoAction::Remove, id, before, {});
            m_model->deleteItem(id);
        }
    }
    m_selectedIds.clear();
    emit selectionChanged();
}

// ══════════════════════════════════════════════════════
//  ITEM OPS WITH UNDO
// ══════════════════════════════════════════════════════

QString FloorPlanController::createItemWithUndo(const QString &type,
                                                const QVariantMap &data)
{
    if (!m_model) return {};
    QString id = m_model->createItem(type, data);
    QVariantMap after = m_model->getItemData(id);
    pushUndo(UndoAction::Add, id, {}, after);
    return id;
}

void FloorPlanController::deleteItemWithUndo(const QString &id)
{
    if (!m_model) return;
    QVariantMap before = m_model->getItemData(id);
    if (before.isEmpty()) return;
    pushUndo(UndoAction::Remove, id, before, {});
    m_model->deleteItem(id);
}

void FloorPlanController::moveItemWithUndo(const QString &id, qreal x, qreal y)
{
    if (!m_model) return;
    QVariantMap before = m_model->getItemData(id);
    if (before.isEmpty()) return;

    m_model->moveItem(id, x, y);

    QVariantMap after = m_model->getItemData(id);
    if (before.value(QStringLiteral("x")) != after.value(QStringLiteral("x")) ||
        before.value(QStringLiteral("y")) != after.value(QStringLiteral("y"))) {
        pushUndo(UndoAction::Move, id, before, after);
    }
}

void FloorPlanController::rotateItemWithUndo(const QString &id, qreal angle)
{
    if (!m_model) return;
    QVariantMap before = m_model->getItemData(id);
    if (before.isEmpty()) return;

    m_model->rotateItem(id, angle);

    QVariantMap after = m_model->getItemData(id);
    pushUndo(UndoAction::Rotate, id, before, after);
}

void FloorPlanController::updateItemWithUndo(const QString &id, const QVariantMap &data)
{
    if (!m_model) return;
    QVariantMap before = m_model->getItemData(id);
    if (before.isEmpty()) return;

    m_model->setItemData(id, data);

    QVariantMap after = m_model->getItemData(id);
    pushUndo(UndoAction::Update, id, before, after);
}

// ══════════════════════════════════════════════════════
//  SNAPPING / ALIGNMENT
// ══════════════════════════════════════════════════════

QPointF FloorPlanController::applySnap(QPointF p) const
{
    if (!m_model) return p;
    QPointF snapped = m_model->snapToGrid(p);
    if (m_model->snapEnabled())
        snapped = m_model->snapToObjects(snapped);
    return snapped;
}

QVariantMap FloorPlanController::findAlignmentGuides(QPointF p, qreal w, qreal h) const
{
    // Returns alignment guide lines for the canvas to draw
    // { "hLines": [y1, y2, ...], "vLines": [x1, x2, ...] }
    QVariantMap result;
    QVariantList hLines, vLines;

    if (!m_model) {
        result[QStringLiteral("hLines")] = hLines;
        result[QStringLiteral("vLines")] = vLines;
        return result;
    }

    constexpr qreal ALIGN_THRESHOLD = 8.0;

    // Points to test from the dragged item
    const QPointF testPoints[] = {
        p,                                              // top-left
        QPointF(p.x() + w, p.y()),                      // top-right
        QPointF(p.x(), p.y() + h),                      // bottom-left
        QPointF(p.x() + w, p.y() + h),                  // bottom-right
        QPointF(p.x() + w / 2.0, p.y() + h / 2.0),     // center
    };

    const auto ids = m_model->getItemIds();
    for (const auto &id : ids) {
        // Skip items in current selection
        if (m_selectedIds.contains(id)) continue;

        QVariantMap d = m_model->getItemData(id);
        if (d.isEmpty()) continue;

        qreal ix = d.value(QStringLiteral("x")).toReal();
        qreal iy = d.value(QStringLiteral("y")).toReal();
        qreal iw = d.value(QStringLiteral("width")).toReal();
        qreal ih = d.value(QStringLiteral("height")).toReal();

        // Anchor points of existing item
        const qreal xAnchors[] = {ix, ix + iw / 2.0, ix + iw};
        const qreal yAnchors[] = {iy, iy + ih / 2.0, iy + ih};

        for (const auto &tp : testPoints) {
            for (qreal xa : xAnchors) {
                if (std::abs(tp.x() - xa) < ALIGN_THRESHOLD)
                    vLines.append(xa);
            }
            for (qreal ya : yAnchors) {
                if (std::abs(tp.y() - ya) < ALIGN_THRESHOLD)
                    hLines.append(ya);
            }
        }
    }

    result[QStringLiteral("hLines")] = hLines;
    result[QStringLiteral("vLines")] = vLines;
    return result;
}

// ══════════════════════════════════════════════════════
//  MULTI-DWELLING
// ══════════════════════════════════════════════════════

void FloorPlanController::newPlan(const QString &name)
{
    if (!m_model) return;
    m_model->clear();
    m_model->setPlanName(name.isEmpty() ? QStringLiteral("Sans nom") : name);
    clearUndoHistory();
    m_selectedIds.clear();
    emit selectionChanged();
    m_currentPlanPath.clear();
    emit currentPlanPathChanged();
}

void FloorPlanController::openPlan(const QString &path)
{
    if (!m_model) return;
    m_model->load(path);
    clearUndoHistory();
    m_selectedIds.clear();
    emit selectionChanged();
    m_currentPlanPath = path;
    emit currentPlanPathChanged();
}

void FloorPlanController::savePlan(const QString &path)
{
    if (!m_model) return;
    QString savePath = path.isEmpty() ? m_currentPlanPath : path;
    if (savePath.isEmpty())
        savePath = QStringLiteral("D:/EXO/config/floorplan.json");
    m_model->save(savePath);
    m_currentPlanPath = savePath;
    emit currentPlanPathChanged();
}

void FloorPlanController::scanPlanFiles(const QString &directory)
{
    QDir dir(directory);
    if (!dir.exists()) return;

    QStringList filters;
    filters << QStringLiteral("floorplan*.json") << QStringLiteral("plan_*.json");
    QStringList entries = dir.entryList(filters, QDir::Files, QDir::Name);

    m_planFiles.clear();
    for (const auto &entry : entries)
        m_planFiles.append(dir.absoluteFilePath(entry));

    emit planFilesChanged();
}

// ── rotation convenience ─────────────────────────────

void FloorPlanController::applyRotation(const QString &id, qreal angle)
{
    // Snap to 15° increments
    qreal snapped = std::round(angle / 15.0) * 15.0;
    rotateItemWithUndo(id, snapped);
}

// ── default sizes ────────────────────────────────────

QVariantMap FloorPlanController::defaultDataForTool(const QString &tool) const
{
    QVariantMap data;
    data[QStringLiteral("rotation")] = 0.0;

    if (tool == QStringLiteral("wall")) {
        data[QStringLiteral("width")]  = 100.0;
        data[QStringLiteral("height")] = 6.0;
    } else if (tool == QStringLiteral("door")) {
        data[QStringLiteral("width")]  = 30.0;
        data[QStringLiteral("height")] = 6.0;
    } else if (tool == QStringLiteral("window")) {
        data[QStringLiteral("width")]  = 40.0;
        data[QStringLiteral("height")] = 6.0;
    } else if (tool == QStringLiteral("room")) {
        data[QStringLiteral("width")]  = 120.0;
        data[QStringLiteral("height")] = 100.0;
    } else if (tool == QStringLiteral("furniture")) {
        data[QStringLiteral("width")]  = 40.0;
        data[QStringLiteral("height")] = 40.0;
    } else if (tool == QStringLiteral("device")) {
        data[QStringLiteral("width")]  = 20.0;
        data[QStringLiteral("height")] = 20.0;
    } else if (tool == QStringLiteral("camera")) {
        data[QStringLiteral("width")]  = 16.0;
        data[QStringLiteral("height")] = 16.0;
    } else if (tool == QStringLiteral("sensor")) {
        data[QStringLiteral("width")]  = 14.0;
        data[QStringLiteral("height")] = 14.0;
    } else {
        data[QStringLiteral("width")]  = 30.0;
        data[QStringLiteral("height")] = 30.0;
    }

    return data;
}

// ══════════════════════════════════════════════════════
//  DEVICE LINKING
// ══════════════════════════════════════════════════════

void FloorPlanController::linkDevice(const QString &itemId,
                                     const QString &deviceId)
{
    if (itemId.isEmpty() || deviceId.isEmpty()) return;
    m_deviceLinks[itemId] = deviceId;

    // Propagate to model if available
    if (m_model) {
        QVariantMap data = m_model->getItemData(itemId);
        if (!data.isEmpty()) {
            data[QStringLiteral("linkedDeviceId")] = deviceId;
            m_model->setItemData(itemId, data);
        }
    }

    emit deviceLinked(itemId, deviceId);
}

void FloorPlanController::unlinkDevice(const QString &itemId)
{
    if (itemId.isEmpty()) return;
    m_deviceLinks.remove(itemId);

    if (m_model) {
        QVariantMap data = m_model->getItemData(itemId);
        if (!data.isEmpty()) {
            data.remove(QStringLiteral("linkedDeviceId"));
            m_model->setItemData(itemId, data);
        }
    }

    emit deviceUnlinked(itemId);
}

QString FloorPlanController::linkedDeviceForItem(const QString &itemId) const
{
    return m_deviceLinks.value(itemId);
}

QVariantMap FloorPlanController::deviceInfoForItem(const QString &itemId) const
{
    QVariantMap info;
    const QString deviceId = m_deviceLinks.value(itemId);
    if (deviceId.isEmpty()) return info;

    info[QStringLiteral("deviceId")] = deviceId;
    info[QStringLiteral("linked")]   = true;

    // Enrich from model if available
    if (m_model) {
        QVariantMap itemData = m_model->getItemData(itemId);
        if (!itemData.isEmpty()) {
            info[QStringLiteral("itemType")] = itemData.value(QStringLiteral("type"));
            QVariantMap props = itemData.value(QStringLiteral("properties")).toMap();
            if (props.contains(QStringLiteral("name")))
                info[QStringLiteral("itemName")] = props.value(QStringLiteral("name"));
        }
    }

    return info;
}
