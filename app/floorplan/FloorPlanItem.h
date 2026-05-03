#ifndef FLOORPLANITEM_H
#define FLOORPLANITEM_H

#include "FloorPlanEnums.h"

#include <QObject>
#include <QPointF>
#include <QSizeF>
#include <QRectF>
#include <QString>
#include <QVariantMap>
#include <QJsonObject>
#include <QJsonArray>
#include <QUuid>

// ─────────────────────────────────────────────────────
//  FloorPlanItem — single element on the 2D floor plan
//
//  Represents walls, doors, windows, rooms, furniture,
//  devices, cameras, sensors.  Serializable to/from JSON.
//  Not a QObject — lightweight value-like class stored
//  inside FloorPlanModel.
// ─────────────────────────────────────────────────────
class FloorPlanItem
{
public:
    FloorPlanItem();
    explicit FloorPlanItem(const QString &type);

    // ── identity ──
    QString id() const { return m_id; }
    void    setId(const QString &id) { m_id = id; }

    // ── type ──
    QString type() const { return m_type; }
    void    setType(const QString &type) { m_type = type; }
    FloorPlan::ItemType typeEnum() const;

    // ── geometry ──
    QPointF position() const { return m_position; }
    void    setPosition(const QPointF &pos) { m_position = pos; }

    QSizeF  size() const { return m_size; }
    void    setSize(const QSizeF &sz) { m_size = sz; }

    qreal   rotation() const { return m_rotation; }
    void    setRotation(qreal angle) { m_rotation = angle; }

    QRectF  boundingRect() const;

    // ── properties (extensible key/value) ──
    QVariantMap properties() const { return m_properties; }
    void        setProperties(const QVariantMap &props) { m_properties = props; }
    QVariant    property(const QString &key) const { return m_properties.value(key); }
    void        setProperty(const QString &key, const QVariant &val) { m_properties.insert(key, val); }

    // ── linked device ──
    QString linkedDeviceId() const { return m_linkedDeviceId; }
    void    setLinkedDeviceId(const QString &id) { m_linkedDeviceId = id; }

    // ── serialization ──
    QJsonObject toJson() const;
    static FloorPlanItem fromJson(const QJsonObject &obj);

    // ── QVariantMap conversion for QML ──
    QVariantMap toVariantMap() const;
    void        applyVariantMap(const QVariantMap &data);

private:
    QString     m_id;
    QString     m_type;
    QPointF     m_position;
    QSizeF      m_size{10.0, 10.0};
    qreal       m_rotation = 0.0;
    QVariantMap m_properties;
    QString     m_linkedDeviceId;
};

#endif // FLOORPLANITEM_H
