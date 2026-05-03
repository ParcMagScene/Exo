#include "FloorPlanItem.h"

#include <QJsonValue>
#include <cmath>

// ═══════════════════════════════════════════════════════
//  FloorPlanItem — lightweight 2D plan element
// ═══════════════════════════════════════════════════════

FloorPlanItem::FloorPlanItem()
    : m_id(QUuid::createUuid().toString(QUuid::WithoutBraces))
{}

FloorPlanItem::FloorPlanItem(const QString &type)
    : m_id(QUuid::createUuid().toString(QUuid::WithoutBraces))
    , m_type(type)
{}

FloorPlan::ItemType FloorPlanItem::typeEnum() const
{
    static const QHash<QString, FloorPlan::ItemType> map = {
        {"wall",      FloorPlan::ItemType::Wall},
        {"door",      FloorPlan::ItemType::Door},
        {"window",    FloorPlan::ItemType::Window},
        {"room",      FloorPlan::ItemType::Room},
        {"furniture", FloorPlan::ItemType::Furniture},
        {"device",    FloorPlan::ItemType::Device},
        {"camera",    FloorPlan::ItemType::Camera},
        {"sensor",    FloorPlan::ItemType::Sensor},
    };
    return map.value(m_type.toLower(), FloorPlan::ItemType::Furniture);
}

QRectF FloorPlanItem::boundingRect() const
{
    return QRectF(m_position, m_size);
}

// ── JSON serialization ──────────────────────────────

QJsonObject FloorPlanItem::toJson() const
{
    QJsonObject obj;
    obj["id"]       = m_id;
    obj["type"]     = m_type;
    obj["position"] = QJsonArray{m_position.x(), m_position.y()};
    obj["size"]     = QJsonArray{m_size.width(), m_size.height()};
    obj["rotation"] = m_rotation;

    if (!m_properties.isEmpty())
        obj["properties"] = QJsonObject::fromVariantMap(m_properties);

    if (!m_linkedDeviceId.isEmpty())
        obj["linkedDeviceId"] = m_linkedDeviceId;

    return obj;
}

FloorPlanItem FloorPlanItem::fromJson(const QJsonObject &obj)
{
    FloorPlanItem item;
    item.m_id   = obj["id"].toString(QUuid::createUuid().toString(QUuid::WithoutBraces));
    item.m_type = obj["type"].toString("furniture");

    const QJsonArray pos = obj["position"].toArray();
    if (pos.size() >= 2)
        item.m_position = QPointF(pos[0].toDouble(), pos[1].toDouble());

    const QJsonArray sz = obj["size"].toArray();
    if (sz.size() >= 2)
        item.m_size = QSizeF(sz[0].toDouble(), sz[1].toDouble());

    item.m_rotation = obj["rotation"].toDouble(0.0);

    if (obj.contains("properties"))
        item.m_properties = obj["properties"].toObject().toVariantMap();

    item.m_linkedDeviceId = obj.value("linkedDeviceId").toString();

    return item;
}

// ── QVariantMap conversion (QML bridge) ─────────────

QVariantMap FloorPlanItem::toVariantMap() const
{
    QVariantMap m;
    m["id"]             = m_id;
    m["type"]           = m_type;
    m["x"]              = m_position.x();
    m["y"]              = m_position.y();
    m["width"]          = m_size.width();
    m["height"]         = m_size.height();
    m["rotation"]       = m_rotation;
    m["properties"]     = m_properties;
    m["linkedDeviceId"] = m_linkedDeviceId;
    return m;
}

void FloorPlanItem::applyVariantMap(const QVariantMap &data)
{
    if (data.contains("type"))
        m_type = data["type"].toString();
    if (data.contains("x") || data.contains("y"))
        m_position = QPointF(data.value("x", m_position.x()).toReal(),
                             data.value("y", m_position.y()).toReal());
    if (data.contains("width") || data.contains("height"))
        m_size = QSizeF(data.value("width", m_size.width()).toReal(),
                        data.value("height", m_size.height()).toReal());
    if (data.contains("rotation"))
        m_rotation = data["rotation"].toReal();
    if (data.contains("properties"))
        m_properties = data["properties"].toMap();
    if (data.contains("linkedDeviceId"))
        m_linkedDeviceId = data["linkedDeviceId"].toString();
}
