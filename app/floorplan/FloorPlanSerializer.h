#ifndef FLOORPLANSERIALIZER_H
#define FLOORPLANSERIALIZER_H

#include "FloorPlanItem.h"

#include <QJsonObject>
#include <QJsonArray>
#include <QJsonDocument>
#include <QString>
#include <QList>

// ─────────────────────────────────────────────────────
//  FloorPlanSerializer — JSON persistence for floor plans
//
//  Format:
//  {
//    "version": 1,
//    "name": "Appartement",
//    "items": [ { ... }, ... ]
//  }
// ─────────────────────────────────────────────────────
class FloorPlanSerializer
{
public:
    // ── file I/O ──
    static bool saveToFile(const QString &path,
                           const QString &planName,
                           const QList<FloorPlanItem> &items);

    static bool loadFromFile(const QString &path,
                             QString &planName,
                             QList<FloorPlanItem> &items);

    // ── in-memory JSON ──
    static QJsonObject exportJson(const QString &planName,
                                  const QList<FloorPlanItem> &items);

    static bool importJson(const QJsonObject &root,
                           QString &planName,
                           QList<FloorPlanItem> &items);

    static constexpr int FORMAT_VERSION = 1;
};

#endif // FLOORPLANSERIALIZER_H
