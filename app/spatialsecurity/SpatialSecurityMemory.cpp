#include "SpatialSecurityMemory.h"

#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QFile>
#include <QUuid>
#include <algorithm>

// ─────────────────────────────────────────────────────
//  SecurityIncident
// ─────────────────────────────────────────────────────

QVariantMap SecurityIncident::toVariantMap() const
{
    QVariantList tagList;
    for (const auto &t : tags) tagList.append(t);

    return {
        {"id",          id},
        {"type",        static_cast<int>(type)},
        {"severity",    static_cast<int>(severity)},
        {"roomId",      roomId},
        {"description", description},
        {"confidence",  confidence},
        {"data",        data},
        {"tags",        tagList},
        {"timestamp",   timestamp.toString(Qt::ISODate)},
        {"resolved",    resolved}
    };
}

SecurityIncident SecurityIncident::fromVariantMap(const QVariantMap &map)
{
    SecurityIncident inc;
    inc.id          = map.value("id").toString();
    inc.type        = static_cast<SpatialSecurity::RiskType>(map.value("type").toInt());
    inc.severity    = static_cast<SpatialSecurity::SecuritySeverity>(map.value("severity").toInt());
    inc.roomId      = map.value("roomId").toString();
    inc.description = map.value("description").toString();
    inc.confidence  = map.value("confidence").toDouble();
    inc.data        = map.value("data").toMap();
    inc.timestamp   = QDateTime::fromString(map.value("timestamp").toString(), Qt::ISODate);
    inc.resolved    = map.value("resolved").toBool();

    const auto tagList = map.value("tags").toList();
    for (const auto &t : tagList)
        inc.tags.append(t.toString());

    return inc;
}

// ─────────────────────────────────────────────────────
//  SpatialSecurityMemory
// ─────────────────────────────────────────────────────

SpatialSecurityMemory::SpatialSecurityMemory(QObject *parent)
    : QObject(parent)
{
}

SpatialSecurityMemory::~SpatialSecurityMemory() = default;

// ── Stockage ──

void SpatialSecurityMemory::storeIncident(const SecurityIncident &incident)
{
    evictIfNeeded();
    m_incidents.append(incident);
    emit incidentStored(incident.toVariantMap());
}

void SpatialSecurityMemory::storeRisk(SpatialSecurity::RiskType type, const QString &roomId,
                                       const QString &description, double severity)
{
    SecurityIncident inc;
    inc.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
    inc.type        = type;
    inc.roomId      = roomId;
    inc.description = description;
    inc.confidence  = severity;
    inc.timestamp   = QDateTime::currentDateTime();
    inc.tags.append(roomId);

    if (severity >= 0.8)      inc.severity = SpatialSecurity::SecuritySeverity::Critical;
    else if (severity >= 0.6) inc.severity = SpatialSecurity::SecuritySeverity::High;
    else if (severity >= 0.4) inc.severity = SpatialSecurity::SecuritySeverity::Medium;
    else if (severity >= 0.2) inc.severity = SpatialSecurity::SecuritySeverity::Low;
    else                      inc.severity = SpatialSecurity::SecuritySeverity::Info;

    storeIncident(inc);
}

void SpatialSecurityMemory::resolveIncident(const QString &incidentId)
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

QVector<SecurityIncident> SpatialSecurityMemory::queryByType(SpatialSecurity::RiskType type, int maxCount) const
{
    QVector<SecurityIncident> result;
    for (int i = m_incidents.size() - 1; i >= 0 && result.size() < maxCount; --i) {
        if (m_incidents[i].type == type)
            result.append(m_incidents[i]);
    }
    return result;
}

QVector<SecurityIncident> SpatialSecurityMemory::queryByRoom(const QString &roomId, int maxCount) const
{
    QVector<SecurityIncident> result;
    for (int i = m_incidents.size() - 1; i >= 0 && result.size() < maxCount; --i) {
        if (m_incidents[i].roomId == roomId)
            result.append(m_incidents[i]);
    }
    return result;
}

QVector<SecurityIncident> SpatialSecurityMemory::queryByTimeRange(const QDateTime &from, const QDateTime &to) const
{
    QVector<SecurityIncident> result;
    for (const auto &inc : m_incidents) {
        if (inc.timestamp >= from && inc.timestamp <= to)
            result.append(inc);
    }
    return result;
}

QVector<SecurityIncident> SpatialSecurityMemory::queryBySeverity(SpatialSecurity::SecuritySeverity minSeverity, int maxCount) const
{
    QVector<SecurityIncident> result;
    for (int i = m_incidents.size() - 1; i >= 0 && result.size() < maxCount; --i) {
        if (static_cast<int>(m_incidents[i].severity) >= static_cast<int>(minSeverity))
            result.append(m_incidents[i]);
    }
    return result;
}

QVector<SecurityIncident> SpatialSecurityMemory::querySimilarIncidents(const SecurityIncident &reference, int maxCount) const
{
    struct Scored {
        int index;
        double score;
    };
    QVector<Scored> scored;
    for (int i = 0; i < m_incidents.size(); ++i) {
        if (m_incidents[i].id == reference.id) continue;
        double sim = computeSimilarity(reference, m_incidents[i]);
        if (sim > 0.3)
            scored.append({i, sim});
    }

    std::sort(scored.begin(), scored.end(), [](const Scored &a, const Scored &b) {
        return a.score > b.score;
    });

    QVector<SecurityIncident> result;
    for (int i = 0; i < qMin(scored.size(), maxCount); ++i)
        result.append(m_incidents[scored[i].index]);
    return result;
}

QVector<SecurityIncident> SpatialSecurityMemory::retrievePastIntrusions(int maxCount) const
{
    return queryByType(SpatialSecurity::RiskType::Intrusion, maxCount);
}

QVector<SecurityIncident> SpatialSecurityMemory::retrievePastFires(int maxCount) const
{
    return queryByType(SpatialSecurity::RiskType::Fire, maxCount);
}

QVector<SecurityIncident> SpatialSecurityMemory::unresolvedIncidents() const
{
    QVector<SecurityIncident> result;
    for (const auto &inc : m_incidents) {
        if (!inc.resolved)
            result.append(inc);
    }
    return result;
}

// ── Statistiques ──

int SpatialSecurityMemory::totalIncidents() const { return m_incidents.size(); }

int SpatialSecurityMemory::unresolvedCount() const
{
    int count = 0;
    for (const auto &inc : m_incidents)
        if (!inc.resolved) ++count;
    return count;
}

QVariantMap SpatialSecurityMemory::statisticsByType() const
{
    QHash<int, int> counts;
    for (const auto &inc : m_incidents)
        counts[static_cast<int>(inc.type)]++;

    QVariantMap result;
    for (auto it = counts.constBegin(); it != counts.constEnd(); ++it)
        result.insert(QString::number(it.key()), it.value());
    return result;
}

QVariantMap SpatialSecurityMemory::statisticsByRoom() const
{
    QHash<QString, int> counts;
    for (const auto &inc : m_incidents)
        if (!inc.roomId.isEmpty()) counts[inc.roomId]++;

    QVariantMap result;
    for (auto it = counts.constBegin(); it != counts.constEnd(); ++it)
        result.insert(it.key(), it.value());
    return result;
}

// ── Persistance ──

bool SpatialSecurityMemory::saveToFile(const QString &path) const
{
    QJsonArray arr;
    for (const auto &inc : m_incidents)
        arr.append(QJsonObject::fromVariantMap(inc.toVariantMap()));

    QFile file(path);
    if (!file.open(QIODevice::WriteOnly))
        return false;

    file.write(QJsonDocument(arr).toJson(QJsonDocument::Compact));
    return true;
}

bool SpatialSecurityMemory::loadFromFile(const QString &path)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly))
        return false;

    const auto doc = QJsonDocument::fromJson(file.readAll());
    if (!doc.isArray())
        return false;

    m_incidents.clear();
    const auto arr = doc.array();
    for (const auto &val : arr)
        m_incidents.append(SecurityIncident::fromVariantMap(val.toObject().toVariantMap()));

    return true;
}

// ── Capacité ──

void SpatialSecurityMemory::setMaxCapacity(int max) { m_maxCapacity = max; }

void SpatialSecurityMemory::clear()
{
    m_incidents.clear();
    emit memoryCleared();
}

QVariantList SpatialSecurityMemory::incidentsToVariantList(int maxCount) const
{
    QVariantList list;
    int start = qMax(0, m_incidents.size() - maxCount);
    for (int i = m_incidents.size() - 1; i >= start; --i)
        list.append(m_incidents[i].toVariantMap());
    return list;
}

// ── Interne ──

void SpatialSecurityMemory::evictIfNeeded()
{
    while (m_incidents.size() >= m_maxCapacity) {
        // Supprimer le plus ancien incident résolu, sinon le plus ancien
        int toRemove = -1;
        for (int i = 0; i < m_incidents.size(); ++i) {
            if (m_incidents[i].resolved) { toRemove = i; break; }
        }
        if (toRemove < 0) toRemove = 0;
        m_incidents.removeAt(toRemove);
    }
}

double SpatialSecurityMemory::computeSimilarity(const SecurityIncident &a, const SecurityIncident &b) const
{
    double score = 0.0;
    if (a.type == b.type) score += 0.4;
    if (a.roomId == b.roomId && !a.roomId.isEmpty()) score += 0.3;
    if (a.severity == b.severity) score += 0.1;

    // Tags en commun (Jaccard)
    QSet<QString> setA(a.tags.begin(), a.tags.end());
    QSet<QString> setB(b.tags.begin(), b.tags.end());
    if (!setA.isEmpty() || !setB.isEmpty()) {
        int intersection = (setA & setB).size();
        int unionSize = (setA | setB).size();
        if (unionSize > 0)
            score += 0.2 * (static_cast<double>(intersection) / unionSize);
    }

    return qBound(0.0, score, 1.0);
}
