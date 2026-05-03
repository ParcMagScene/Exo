#include "FloorPlanModel.h"

#include <QJsonDocument>
#include <cmath>
#include <algorithm>
#include <limits>

// ═══════════════════════════════════════════════════════
//  FloorPlanModel — QAbstractListModel for 2D floor plan
// ═══════════════════════════════════════════════════════

FloorPlanModel::FloorPlanModel(QObject *parent)
    : QAbstractListModel(parent)
{}

// ── QAbstractListModel interface ─────────────────────

int FloorPlanModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : m_items.size();
}

QVariant FloorPlanModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() < 0 || index.row() >= m_items.size())
        return {};

    const FloorPlanItem &item = m_items[index.row()];

    switch (role) {
    case IdRole:           return item.id();
    case TypeRole:         return item.type();
    case PositionRole:     return item.position();
    case SizeRole:         return item.size();
    case RotationRole:     return item.rotation();
    case PropertiesRole:   return item.properties();
    case LinkedDeviceRole: return item.linkedDeviceId();
    default:               return {};
    }
}

bool FloorPlanModel::setData(const QModelIndex &index, const QVariant &value, int role)
{
    if (!index.isValid() || index.row() < 0 || index.row() >= m_items.size())
        return false;

    FloorPlanItem &item = m_items[index.row()];
    bool changed = false;

    switch (role) {
    case TypeRole:
        item.setType(value.toString());
        changed = true;
        break;
    case PositionRole:
        item.setPosition(value.toPointF());
        changed = true;
        break;
    case SizeRole:
        item.setSize(value.toSizeF());
        changed = true;
        break;
    case RotationRole:
        item.setRotation(value.toReal());
        changed = true;
        break;
    case PropertiesRole:
        item.setProperties(value.toMap());
        changed = true;
        break;
    case LinkedDeviceRole:
        item.setLinkedDeviceId(value.toString());
        changed = true;
        break;
    default:
        break;
    }

    if (changed) {
        emit dataChanged(index, index, {role});
        emit itemUpdated(item.id());
    }
    return changed;
}

Qt::ItemFlags FloorPlanModel::flags(const QModelIndex &index) const
{
    if (!index.isValid())
        return Qt::NoItemFlags;
    return Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsEditable;
}

QHash<int, QByteArray> FloorPlanModel::roleNames() const
{
    return {
        {IdRole,           "itemId"},
        {TypeRole,         "itemType"},
        {PositionRole,     "position"},
        {SizeRole,         "size"},
        {RotationRole,     "rotation"},
        {PropertiesRole,   "properties"},
        {LinkedDeviceRole, "linkedDeviceId"},
    };
}

// ── properties ───────────────────────────────────────

void FloorPlanModel::setSnapEnabled(bool on)
{
    if (m_snapEnabled == on) return;
    m_snapEnabled = on;
    emit snapEnabledChanged();
}

void FloorPlanModel::setGridSize(qreal gs)
{
    if (qFuzzyCompare(m_gridSize, gs)) return;
    m_gridSize = gs;
    emit gridSizeChanged();
}

void FloorPlanModel::setPlanName(const QString &name)
{
    if (m_planName == name) return;
    m_planName = name;
    emit planNameChanged();
}

// ── index helpers ────────────────────────────────────

int FloorPlanModel::indexOfId(const QString &id) const
{
    auto it = m_idIndex.constFind(id);
    return (it != m_idIndex.constEnd()) ? it.value() : -1;
}

void FloorPlanModel::rebuildIndex()
{
    m_idIndex.clear();
    m_idIndex.reserve(m_items.size());
    for (int i = 0; i < m_items.size(); ++i)
        m_idIndex.insert(m_items[i].id(), i);
}

void FloorPlanModel::emitItemChanged(int row)
{
    const QModelIndex idx = index(row);
    emit dataChanged(idx, idx);
}

// ── Q_INVOKABLE — QML CRUD API ──────────────────────

QList<QString> FloorPlanModel::getItemIds() const
{
    QList<QString> ids;
    ids.reserve(m_items.size());
    for (const auto &item : m_items)
        ids.append(item.id());
    return ids;
}

QVariantMap FloorPlanModel::getItemData(const QString &id) const
{
    const int row = indexOfId(id);
    if (row < 0) return {};
    return m_items[row].toVariantMap();
}

void FloorPlanModel::setItemData(const QString &id, const QVariantMap &data)
{
    const int row = indexOfId(id);
    if (row < 0) return;

    m_items[row].applyVariantMap(data);
    emitItemChanged(row);
    emit itemUpdated(id);
}

QString FloorPlanModel::createItem(const QString &type, const QVariantMap &data)
{
    FloorPlanItem item(type);
    item.applyVariantMap(data);

    const int row = m_items.size();
    beginInsertRows({}, row, row);
    m_items.append(item);
    m_idIndex.insert(item.id(), row);
    endInsertRows();

    emit countChanged();
    emit itemAdded(item.id());
    return item.id();
}

void FloorPlanModel::deleteItem(const QString &id)
{
    const int row = indexOfId(id);
    if (row < 0) return;

    beginRemoveRows({}, row, row);
    m_items.removeAt(row);
    rebuildIndex();
    endRemoveRows();

    emit countChanged();
    emit itemRemoved(id);
}

void FloorPlanModel::moveItem(const QString &id, qreal x, qreal y)
{
    const int row = indexOfId(id);
    if (row < 0) return;

    QPointF pos(x, y);
    if (m_snapEnabled)
        pos = snapToGrid(pos);

    m_items[row].setPosition(pos);
    emitItemChanged(row);
    emit itemUpdated(id);
}

void FloorPlanModel::rotateItem(const QString &id, qreal angle)
{
    const int row = indexOfId(id);
    if (row < 0) return;

    m_items[row].setRotation(angle);
    emitItemChanged(row);
    emit itemUpdated(id);
}

void FloorPlanModel::clear()
{
    if (m_items.isEmpty()) return;

    beginResetModel();
    m_items.clear();
    m_idIndex.clear();
    endResetModel();

    emit countChanged();
}

// ── device linking ───────────────────────────────────

void FloorPlanModel::linkDevice(const QString &itemId, const QString &deviceId)
{
    const int row = indexOfId(itemId);
    if (row < 0) return;

    m_items[row].setLinkedDeviceId(deviceId);
    emitItemChanged(row);
    emit itemUpdated(itemId);
}

void FloorPlanModel::unlinkDevice(const QString &itemId)
{
    linkDevice(itemId, QString());
}

// ── spatial queries ──────────────────────────────────

QList<QString> FloorPlanModel::itemsInRect(qreal x, qreal y, qreal w, qreal h) const
{
    const QRectF rect(x, y, w, h);
    QList<QString> result;
    for (const auto &item : m_items) {
        if (rect.intersects(item.boundingRect()))
            result.append(item.id());
    }
    return result;
}

// ── magnetism ────────────────────────────────────────

QPointF FloorPlanModel::snapToGrid(QPointF p) const
{
    if (m_gridSize <= 0.0) return p;
    const qreal gx = std::round(p.x() / m_gridSize) * m_gridSize;
    const qreal gy = std::round(p.y() / m_gridSize) * m_gridSize;
    return {gx, gy};
}

QPointF FloorPlanModel::snapToObjects(QPointF p) const
{
    constexpr qreal SNAP_THRESHOLD = 5.0; // pixels

    qreal bestDist = std::numeric_limits<qreal>::max();
    QPointF bestSnap = p;

    for (const auto &item : m_items) {
        const QRectF r = item.boundingRect();

        // Test snap to each edge/corner of existing items
        const QPointF candidates[] = {
            r.topLeft(),
            r.topRight(),
            r.bottomLeft(),
            r.bottomRight(),
            QPointF(r.center().x(), r.top()),
            QPointF(r.center().x(), r.bottom()),
            QPointF(r.left(),  r.center().y()),
            QPointF(r.right(), r.center().y()),
        };

        for (const auto &c : candidates) {
            const qreal dx = p.x() - c.x();
            const qreal dy = p.y() - c.y();
            const qreal dist = std::sqrt(dx * dx + dy * dy);
            if (dist < SNAP_THRESHOLD && dist < bestDist) {
                bestDist = dist;
                bestSnap = c;
            }
        }
    }

    return bestSnap;
}

// Axis-independent snap: X and Y snap independently to the
// closest edge/center of other items. Allows snapping X to one
// edge and Y to a completely different one.
QPointF FloorPlanModel::snapToObjectAxis(QPointF p, QSizeF itemSize,
                                         const QString &excludeId) const
{
    constexpr qreal SNAP_THRESHOLD = 8.0;
    const qreal iw = itemSize.width();
    const qreal ih = itemSize.height();

    // Anchors of the dragged item
    const qreal xAnchors[] = { p.x(), p.x() + iw / 2, p.x() + iw };
    const qreal yAnchors[] = { p.y(), p.y() + ih / 2, p.y() + ih };

    qreal bestDx = SNAP_THRESHOLD;
    qreal snapX  = p.x();
    bool  foundX = false;

    qreal bestDy = SNAP_THRESHOLD;
    qreal snapY  = p.y();
    bool  foundY = false;

    for (const auto &item : m_items) {
        if (!excludeId.isEmpty() && item.id() == excludeId) continue;

        const QRectF r = item.boundingRect();
        const qreal targetX[] = { r.left(), r.center().x(), r.right() };
        const qreal targetY[] = { r.top(),  r.center().y(), r.bottom() };

        for (const auto &xa : xAnchors) {
            for (const auto &tx : targetX) {
                const qreal d = std::abs(xa - tx);
                if (d < bestDx) {
                    bestDx = d;
                    snapX  = p.x() + (tx - xa);
                    foundX = true;
                }
            }
        }

        for (const auto &ya : yAnchors) {
            for (const auto &ty : targetY) {
                const qreal d = std::abs(ya - ty);
                if (d < bestDy) {
                    bestDy = d;
                    snapY  = p.y() + (ty - ya);
                    foundY = true;
                }
            }
        }
    }

    return { foundX ? snapX : p.x(), foundY ? snapY : p.y() };
}

// Returns alignment guides { hLines: [...], vLines: [...] }
// for visual feedback while dragging.
QVariantMap FloorPlanModel::findGuides(QPointF p, QSizeF itemSize,
                                       const QString &excludeId) const
{
    constexpr qreal THRESHOLD = 8.0;
    const qreal iw = itemSize.width();
    const qreal ih = itemSize.height();

    const qreal xAnchors[] = { p.x(), p.x() + iw / 2, p.x() + iw };
    const qreal yAnchors[] = { p.y(), p.y() + ih / 2, p.y() + ih };

    QVariantList hLines, vLines;

    for (const auto &item : m_items) {
        if (!excludeId.isEmpty() && item.id() == excludeId) continue;

        const QRectF r = item.boundingRect();
        const qreal targetX[] = { r.left(), r.center().x(), r.right() };
        const qreal targetY[] = { r.top(),  r.center().y(), r.bottom() };

        for (const auto &xa : xAnchors) {
            for (const auto &tx : targetX) {
                if (std::abs(xa - tx) < THRESHOLD)
                    vLines.append(tx);
            }
        }
        for (const auto &ya : yAnchors) {
            for (const auto &ty : targetY) {
                if (std::abs(ya - ty) < THRESHOLD)
                    hLines.append(ty);
            }
        }
    }

    return { {"hLines", hLines}, {"vLines", vLines} };
}

// ── persistence ──────────────────────────────────────

void FloorPlanModel::save(const QString &path)
{
    if (!FloorPlanSerializer::saveToFile(path, m_planName, m_items))
        qWarning("[FloorPlan] Save failed: %s", qPrintable(path));
}

void FloorPlanModel::load(const QString &path)
{
    QString name;
    QList<FloorPlanItem> items;
    if (!FloorPlanSerializer::loadFromFile(path, name, items)) {
        qWarning("[FloorPlan] Load failed: %s", qPrintable(path));
        return;
    }

    beginResetModel();
    m_items = std::move(items);
    m_planName = name;
    rebuildIndex();
    endResetModel();

    emit countChanged();
    emit planNameChanged();
}

QJsonObject FloorPlanModel::exportJson() const
{
    return FloorPlanSerializer::exportJson(m_planName, m_items);
}

void FloorPlanModel::importJson(const QJsonObject &root)
{
    QString name;
    QList<FloorPlanItem> items;
    if (!FloorPlanSerializer::importJson(root, name, items))
        return;

    beginResetModel();
    m_items = std::move(items);
    m_planName = name;
    rebuildIndex();
    endResetModel();

    emit countChanged();
    emit planNameChanged();
}
