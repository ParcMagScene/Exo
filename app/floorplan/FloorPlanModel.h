#ifndef FLOORPLANMODEL_H
#define FLOORPLANMODEL_H

#include "FloorPlanItem.h"
#include "FloorPlanSerializer.h"

#include <QAbstractListModel>
#include <QList>
#include <QPointF>
#include <QSizeF>
#include <QRectF>
#include <QVariantMap>
#include <QHash>
#include <QtQml/qqml.h>

// ─────────────────────────────────────────────────────
//  FloorPlanModel — QAbstractListModel for 2D floor plan
//
//  Provides a complete list model of FloorPlanItem objects
//  for QML Canvas-based floor plan editing.
//
//  Features:
//   • CRUD with full model reset signals
//   • Move / rotate / select
//   • Snap-to-grid and snap-to-object magnetism
//   • JSON save/load (multi-dwelling support)
//   • Linked device binding (for home automation)
//
//  Thread: main thread only (QML-bound).
// ─────────────────────────────────────────────────────
class FloorPlanModel : public QAbstractListModel
{
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(int    count       READ count        NOTIFY countChanged)
    Q_PROPERTY(bool   snapEnabled READ snapEnabled  WRITE setSnapEnabled NOTIFY snapEnabledChanged)
    Q_PROPERTY(qreal  gridSize    READ gridSize     WRITE setGridSize    NOTIFY gridSizeChanged)
    Q_PROPERTY(QString planName   READ planName     WRITE setPlanName    NOTIFY planNameChanged)

public:
    enum Roles {
        IdRole = Qt::UserRole + 1,
        TypeRole,
        PositionRole,
        SizeRole,
        RotationRole,
        PropertiesRole,
        LinkedDeviceRole,
    };
    Q_ENUM(Roles)

    explicit FloorPlanModel(QObject *parent = nullptr);
    ~FloorPlanModel() override = default;

    // ── QAbstractListModel interface ──
    int      rowCount(const QModelIndex &parent = {}) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    bool     setData(const QModelIndex &index, const QVariant &value, int role) override;
    Qt::ItemFlags flags(const QModelIndex &index) const override;
    QHash<int, QByteArray> roleNames() const override;

    // ── properties ──
    int     count() const { return m_items.size(); }
    bool    snapEnabled() const { return m_snapEnabled; }
    void    setSnapEnabled(bool on);
    qreal   gridSize() const { return m_gridSize; }
    void    setGridSize(qreal gs);
    QString planName() const { return m_planName; }
    void    setPlanName(const QString &name);

    // ── Q_INVOKABLE — QML API ──
    Q_INVOKABLE QList<QString> getItemIds() const;
    Q_INVOKABLE QVariantMap    getItemData(const QString &id) const;
    Q_INVOKABLE void           setItemData(const QString &id, const QVariantMap &data);
    Q_INVOKABLE QString        createItem(const QString &type, const QVariantMap &data);
    Q_INVOKABLE void           deleteItem(const QString &id);
    Q_INVOKABLE void           moveItem(const QString &id, qreal x, qreal y);
    Q_INVOKABLE void           rotateItem(const QString &id, qreal angle);
    Q_INVOKABLE void           clear();

    // ── device linking ──
    Q_INVOKABLE void linkDevice(const QString &itemId, const QString &deviceId);
    Q_INVOKABLE void unlinkDevice(const QString &itemId);

    // ── spatial queries ──
    Q_INVOKABLE QList<QString> itemsInRect(qreal x, qreal y, qreal w, qreal h) const;

    // ── magnetism ──
    Q_INVOKABLE QPointF snapToGrid(QPointF p) const;
    Q_INVOKABLE QPointF snapToObjects(QPointF p) const;
    Q_INVOKABLE QPointF snapToObjectAxis(QPointF p, QSizeF itemSize,
                                         const QString &excludeId = {}) const;
    Q_INVOKABLE QVariantMap findGuides(QPointF p, QSizeF itemSize,
                                       const QString &excludeId = {}) const;

    // ── persistence ──
    Q_INVOKABLE void save(const QString &path);
    Q_INVOKABLE void load(const QString &path);
    Q_INVOKABLE QJsonObject exportJson() const;
    Q_INVOKABLE void importJson(const QJsonObject &root);

signals:
    void countChanged();
    void snapEnabledChanged();
    void gridSizeChanged();
    void planNameChanged();
    void itemAdded(const QString &id);
    void itemRemoved(const QString &id);
    void itemUpdated(const QString &id);

private:
    int indexOfId(const QString &id) const;
    void emitItemChanged(int row);

    QList<FloorPlanItem>     m_items;
    QHash<QString, int>      m_idIndex;   // id → row (kept in sync)
    bool   m_snapEnabled = true;
    qreal  m_gridSize    = 10.0;
    QString m_planName   = QStringLiteral("Sans nom");

    void rebuildIndex();
};

#endif // FLOORPLANMODEL_H
