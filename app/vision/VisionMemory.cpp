#include "VisionMemory.h"

#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QFile>
#include <QUuid>
#include <QDebug>
#include <algorithm>

// ═══════════════════════════════════════════════════════
//  VisionIncident
// ═══════════════════════════════════════════════════════

QVariantMap VisionIncident::toVariant() const
{
    QVariantList tagList;
    for (const auto &t : tags) tagList.append(t);

    return {
        {"id",          id},
        {"cameraId",    cameraId},
        {"roomId",      roomId},
        {"type",        static_cast<int>(type)},
        {"severity",    static_cast<int>(severity)},
        {"description", description},
        {"confidence",  confidence},
        {"data",        data},
        {"tags",        tagList},
        {"timestamp",   timestamp.toString(Qt::ISODate)},
        {"resolved",    resolved}
    };
}

VisionIncident VisionIncident::fromVariant(const QVariantMap &map)
{
    VisionIncident inc;
    inc.id          = map.value("id").toString();
    inc.cameraId    = map.value("cameraId").toString();
    inc.roomId      = map.value("roomId").toString();
    inc.type        = static_cast<Vision::DetectionType>(map.value("type").toInt());
    inc.severity    = static_cast<Vision::VisionSeverity>(map.value("severity").toInt());
    inc.description = map.value("description").toString();
    inc.confidence  = map.value("confidence").toDouble();
    inc.data        = map.value("data").toMap();
    inc.timestamp   = QDateTime::fromString(map.value("timestamp").toString(), Qt::ISODate);
    inc.resolved    = map.value("resolved").toBool();

    for (const auto &t : map.value("tags").toList())
        inc.tags.append(t.toString());

    return inc;
}

// ═══════════════════════════════════════════════════════
//  VisionMemory
// ═══════════════════════════════════════════════════════

VisionMemory::VisionMemory(QObject *parent)
    : QObject(parent)
{
}

VisionMemory::~VisionMemory() = default;

// ── Stockage ──

void VisionMemory::storeIncident(const VisionIncident &incident)
{
    m_incidents.append(incident);
    evictIfNeeded();
    emit incidentStored(incident.toVariant());
}

void VisionMemory::storeFromEvent(const VisionEvent &event)
{
    VisionIncident inc;
    inc.id          = event.id;
    inc.cameraId    = event.cameraId;
    inc.roomId      = event.roomId;
    inc.type        = event.type;
    inc.severity    = event.severity;
    inc.description = event.description;
    inc.confidence  = event.confidence;
    inc.data        = event.details;
    inc.timestamp   = event.timestamp;
    inc.resolved    = false;

    // Tags automatiques
    inc.tags.append(QString::number(static_cast<int>(event.type)));
    if (!event.roomId.isEmpty()) inc.tags.append("room:" + event.roomId);
    if (!event.cameraId.isEmpty()) inc.tags.append("cam:" + event.cameraId);
    if (static_cast<int>(event.severity) >= static_cast<int>(Vision::VisionSeverity::High))
        inc.tags.append("high_severity");

    storeIncident(inc);
}

void VisionMemory::resolveIncident(const QString &incidentId)
{
    for (auto &inc : m_incidents) {
        if (inc.id == incidentId) {
            inc.resolved = true;
            emit incidentResolved(incidentId);
            return;
        }
    }
}

// ── Requêtes ──

QVector<VisionIncident> VisionMemory::queryByType(Vision::DetectionType type, int maxCount) const
{
    QVector<VisionIncident> result;
    for (int i = m_incidents.size() - 1; i >= 0 && result.size() < maxCount; --i) {
        if (m_incidents[i].type == type)
            result.append(m_incidents[i]);
    }
    return result;
}

QVector<VisionIncident> VisionMemory::queryByCamera(const QString &cameraId, int maxCount) const
{
    QVector<VisionIncident> result;
    for (int i = m_incidents.size() - 1; i >= 0 && result.size() < maxCount; --i) {
        if (m_incidents[i].cameraId == cameraId)
            result.append(m_incidents[i]);
    }
    return result;
}

QVector<VisionIncident> VisionMemory::queryByRoom(const QString &roomId, int maxCount) const
{
    QVector<VisionIncident> result;
    for (int i = m_incidents.size() - 1; i >= 0 && result.size() < maxCount; --i) {
        if (m_incidents[i].roomId == roomId)
            result.append(m_incidents[i]);
    }
    return result;
}

QVector<VisionIncident> VisionMemory::queryByTimeRange(const QDateTime &from, const QDateTime &to) const
{
    QVector<VisionIncident> result;
    for (const auto &inc : m_incidents) {
        if (inc.timestamp >= from && inc.timestamp <= to)
            result.append(inc);
    }
    return result;
}

QVector<VisionIncident> VisionMemory::queryBySeverity(Vision::VisionSeverity minSeverity, int maxCount) const
{
    QVector<VisionIncident> result;
    for (int i = m_incidents.size() - 1; i >= 0 && result.size() < maxCount; --i) {
        if (static_cast<int>(m_incidents[i].severity) >= static_cast<int>(minSeverity))
            result.append(m_incidents[i]);
    }
    return result;
}

QVector<VisionIncident> VisionMemory::querySimilar(const VisionIncident &reference, int maxCount) const
{
    struct Scored { double score; int index; };
    QVector<Scored> scored;
    for (int i = 0; i < m_incidents.size(); ++i) {
        if (m_incidents[i].id == reference.id) continue;
        double sim = computeSimilarity(reference, m_incidents[i]);
        if (sim > 0.1) scored.append({sim, i});
    }

    std::sort(scored.begin(), scored.end(), [](const Scored &a, const Scored &b) {
        return a.score > b.score;
    });

    QVector<VisionIncident> result;
    for (int i = 0; i < std::min(static_cast<int>(scored.size()), maxCount); ++i)
        result.append(m_incidents[scored[i].index]);
    return result;
}

QVector<VisionIncident> VisionMemory::unresolvedIncidents() const
{
    QVector<VisionIncident> result;
    for (const auto &inc : m_incidents) {
        if (!inc.resolved) result.append(inc);
    }
    return result;
}

// ── Statistiques ──

int VisionMemory::totalIncidents() const { return m_incidents.size(); }

int VisionMemory::unresolvedCount() const
{
    int count = 0;
    for (const auto &inc : m_incidents)
        if (!inc.resolved) ++count;
    return count;
}

QVariantMap VisionMemory::statisticsByType() const
{
    QHash<int, int> counts;
    for (const auto &inc : m_incidents)
        counts[static_cast<int>(inc.type)]++;

    QVariantMap map;
    for (auto it = counts.cbegin(); it != counts.cend(); ++it)
        map[QString::number(it.key())] = it.value();
    return map;
}

QVariantMap VisionMemory::statisticsByCamera() const
{
    QHash<QString, int> counts;
    for (const auto &inc : m_incidents)
        counts[inc.cameraId]++;

    QVariantMap map;
    for (auto it = counts.cbegin(); it != counts.cend(); ++it)
        map[it.key()] = it.value();
    return map;
}

QVariantMap VisionMemory::statisticsByRoom() const
{
    QHash<QString, int> counts;
    for (const auto &inc : m_incidents)
        if (!inc.roomId.isEmpty()) counts[inc.roomId]++;

    QVariantMap map;
    for (auto it = counts.cbegin(); it != counts.cend(); ++it)
        map[it.key()] = it.value();
    return map;
}

// ── Persistance JSON ──

bool VisionMemory::saveToFile(const QString &path) const
{
    QJsonArray arr;
    for (const auto &inc : m_incidents)
        arr.append(QJsonObject::fromVariantMap(inc.toVariant()));

    QJsonDocument doc(arr);
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly)) {
        qWarning() << "[VisionMemory] Cannot write:" << path;
        return false;
    }
    file.write(doc.toJson(QJsonDocument::Compact));
    return true;
}

bool VisionMemory::loadFromFile(const QString &path)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        qWarning() << "[VisionMemory] Cannot read:" << path;
        return false;
    }

    QJsonParseError err;
    QJsonDocument doc = QJsonDocument::fromJson(file.readAll(), &err);
    if (err.error != QJsonParseError::NoError) {
        qWarning() << "[VisionMemory] Parse error:" << err.errorString();
        return false;
    }

    m_incidents.clear();
    for (const auto &val : doc.array()) {
        m_incidents.append(VisionIncident::fromVariant(val.toObject().toVariantMap()));
    }
    qDebug() << "[VisionMemory] Loaded" << m_incidents.size() << "incidents from" << path;
    return true;
}

// ── Capacité ──

void VisionMemory::setMaxCapacity(int max) { m_maxCapacity = max; }

void VisionMemory::clear()
{
    m_incidents.clear();
    emit memoryCleared();
}

QVariantList VisionMemory::incidentsToVariantList(int maxCount) const
{
    QVariantList list;
    int start = std::max(0, static_cast<int>(m_incidents.size()) - maxCount);
    for (int i = m_incidents.size() - 1; i >= start; --i)
        list.append(m_incidents[i].toVariant());
    return list;
}

// ── Helpers privés ──

void VisionMemory::evictIfNeeded()
{
    while (m_incidents.size() > m_maxCapacity) {
        // Supprime le plus ancien résolu, sinon le plus ancien tout court
        int removeIdx = -1;
        for (int i = 0; i < m_incidents.size(); ++i) {
            if (m_incidents[i].resolved) { removeIdx = i; break; }
        }
        if (removeIdx < 0) removeIdx = 0;
        m_incidents.removeAt(removeIdx);
    }
}

double VisionMemory::computeSimilarity(const VisionIncident &a, const VisionIncident &b) const
{
    // Jaccard sur tags + bonus type/room/camera
    double score = 0.0;

    if (a.type == b.type) score += 0.3;
    if (!a.roomId.isEmpty() && a.roomId == b.roomId) score += 0.2;
    if (!a.cameraId.isEmpty() && a.cameraId == b.cameraId) score += 0.1;

    // Jaccard sur tags
    if (!a.tags.isEmpty() || !b.tags.isEmpty()) {
        QSet<QString> setA(a.tags.begin(), a.tags.end());
        QSet<QString> setB(b.tags.begin(), b.tags.end());
        int intersection = (setA & setB).size();
        int unionSize    = (setA | setB).size();
        if (unionSize > 0)
            score += 0.4 * (static_cast<double>(intersection) / unionSize);
    }

    return score;
}
