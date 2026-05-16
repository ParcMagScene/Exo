#include "FloorPlanSerializer.h"
#include "utils/SafeIO.h"

#include <QFile>
#include <QFileInfo>
#include <QDir>

// ═══════════════════════════════════════════════════════
//  FloorPlanSerializer — JSON persistence
// ═══════════════════════════════════════════════════════

QJsonObject FloorPlanSerializer::exportJson(const QString &planName,
                                            const QList<FloorPlanItem> &items)
{
    QJsonArray arr;
    for (const auto &item : items)
        arr.append(item.toJson());

    QJsonObject root;
    root["version"] = FORMAT_VERSION;
    root["name"]    = planName;
    root["items"]   = arr;
    return root;
}

bool FloorPlanSerializer::importJson(const QJsonObject &root,
                                     QString &planName,
                                     QList<FloorPlanItem> &items)
{
    const int version = root["version"].toInt(0);
    if (version < 1 || version > FORMAT_VERSION) {
        qWarning("[FloorPlan] Unsupported format version: %d", version);
        return false;
    }

    planName = root["name"].toString("Sans nom");

    items.clear();
    const QJsonArray arr = root["items"].toArray();
    items.reserve(arr.size());
    for (const QJsonValue &v : arr) {
        if (v.isObject())
            items.append(FloorPlanItem::fromJson(v.toObject()));
    }

    return true;
}

bool FloorPlanSerializer::saveToFile(const QString &path,
                                     const QString &planName,
                                     const QList<FloorPlanItem> &items)
{
    // Ensure parent directory exists
    const QFileInfo fi(path);
    if (!exo::safeio::ensureDir(fi.absolutePath(), "FloorPlanSerializer::saveToFile")) {
        qWarning("[FloorPlan] Cannot create directory: %s", qPrintable(fi.absolutePath()));
        return false;
    }

    QFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Text)) {
        qWarning("[FloorPlan] Cannot write file: %s", qPrintable(path));
        return false;
    }

    const QJsonObject root = exportJson(planName, items);
    file.write(QJsonDocument(root).toJson(QJsonDocument::Indented));
    file.close();
    return true;
}

bool FloorPlanSerializer::loadFromFile(const QString &path,
                                       QString &planName,
                                       QList<FloorPlanItem> &items)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        qWarning("[FloorPlan] Cannot read file: %s", qPrintable(path));
        return false;
    }

    const QByteArray data = file.readAll();
    file.close();

    QJsonParseError err;
    const QJsonDocument doc = QJsonDocument::fromJson(data, &err);
    if (err.error != QJsonParseError::NoError) {
        qWarning("[FloorPlan] Erreur de parsing JSON : %s", qPrintable(err.errorString()));
        return false;
    }

    if (!doc.isObject()) {
        qWarning("[FloorPlan] Root is not a JSON object");
        return false;
    }

    return importJson(doc.object(), planName, items);
}
