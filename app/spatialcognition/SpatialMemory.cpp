#include "SpatialMemory.h"

#include <QUuid>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QFile>
#include <algorithm>

// ─────────────────────────────────────────────────────
//  SpatialMemoryEntry
// ─────────────────────────────────────────────────────

QVariantMap SpatialMemoryEntry::toVariantMap() const
{
    return {
        {"id",        id},
        {"category",  category},
        {"data",      data},
        {"timestamp", timestamp.toString(Qt::ISODate)},
        {"relevance", relevance},
        {"tags",      QVariant::fromValue(tags)}
    };
}

// ─────────────────────────────────────────────────────
//  SpatialMemory
// ─────────────────────────────────────────────────────

SpatialMemory::SpatialMemory(QObject *parent)
    : QObject(parent)
{
}

SpatialMemory::~SpatialMemory() = default;

// ── Stockage ──

void SpatialMemory::storeState(const QVariantMap &snapshot)
{
    SpatialMemoryEntry entry;
    entry.category  = QStringLiteral("state");
    entry.data      = snapshot;
    entry.tags      = {"state", "snapshot"};
    addEntry(entry);
}

void SpatialMemory::storeRisk(const QVariantMap &risk)
{
    SpatialMemoryEntry entry;
    entry.category  = QStringLiteral("risk");
    entry.data      = risk;
    entry.relevance = risk.value("score", 0.5).toDouble();
    entry.tags      = {"risk"};

    const QString room = risk.value("roomId").toString();
    if (!room.isEmpty())
        entry.tags.append(room);
    const QString severity = risk.value("severity").toString();
    if (!severity.isEmpty())
        entry.tags.append(severity);

    addEntry(entry);
}

void SpatialMemory::storeAnomaly(const QVariantMap &anomaly)
{
    SpatialMemoryEntry entry;
    entry.category  = QStringLiteral("anomaly");
    entry.data      = anomaly;
    entry.relevance = anomaly.value("confidence", 0.5).toDouble();
    entry.tags      = {"anomaly"};

    const QString room = anomaly.value("roomId").toString();
    if (!room.isEmpty())
        entry.tags.append(room);

    addEntry(entry);
}

void SpatialMemory::storeDecision(const QVariantMap &decision)
{
    SpatialMemoryEntry entry;
    entry.category  = QStringLiteral("decision");
    entry.data      = decision;
    entry.tags      = {"decision"};
    addEntry(entry);
}

void SpatialMemory::storeEvent(const QString &category, const QVariantMap &data,
                                const QStringList &tags)
{
    SpatialMemoryEntry entry;
    entry.category = category;
    entry.data     = data;
    entry.tags     = tags;
    addEntry(entry);
}

// ── Requêtes ──

QVector<SpatialMemoryEntry>
SpatialMemory::querySimilarSituations(const QVariantMap &currentState, int maxResults) const
{
    // Classement par similarité Jaccard-like sur les clés/valeurs
    QVector<std::pair<double, int>> scored;
    scored.reserve(m_entries.size());

    for (int i = 0; i < m_entries.size(); ++i) {
        if (m_entries[i].category != "state")
            continue;
        double sim = computeSimilarity(currentState, m_entries[i].data);
        scored.append({sim, i});
    }

    std::sort(scored.begin(), scored.end(), [](const auto &a, const auto &b) {
        return a.first > b.first;
    });

    QVector<SpatialMemoryEntry> result;
    const int limit = qMin(maxResults, scored.size());
    for (int i = 0; i < limit; ++i)
        result.append(m_entries[scored[i].second]);
    return result;
}

QVector<SpatialMemoryEntry>
SpatialMemory::retrievePastRisks(const QString &roomId, int maxResults) const
{
    QVector<SpatialMemoryEntry> result;
    for (int i = m_entries.size() - 1; i >= 0 && result.size() < maxResults; --i) {
        const auto &e = m_entries[i];
        if (e.category != "risk")
            continue;
        if (!roomId.isEmpty() && !e.tags.contains(roomId))
            continue;
        result.append(e);
    }
    return result;
}

QVector<SpatialMemoryEntry>
SpatialMemory::retrievePastAnomalies(const QString &roomId, int maxResults) const
{
    QVector<SpatialMemoryEntry> result;
    for (int i = m_entries.size() - 1; i >= 0 && result.size() < maxResults; --i) {
        const auto &e = m_entries[i];
        if (e.category != "anomaly")
            continue;
        if (!roomId.isEmpty() && !e.tags.contains(roomId))
            continue;
        result.append(e);
    }
    return result;
}

QVector<SpatialMemoryEntry>
SpatialMemory::retrievePastDecisions(int maxResults) const
{
    return queryByCategory("decision", maxResults);
}

QVector<SpatialMemoryEntry>
SpatialMemory::queryByCategory(const QString &category, int maxResults) const
{
    QVector<SpatialMemoryEntry> result;
    for (int i = m_entries.size() - 1; i >= 0 && result.size() < maxResults; --i) {
        if (m_entries[i].category == category)
            result.append(m_entries[i]);
    }
    return result;
}

QVector<SpatialMemoryEntry>
SpatialMemory::queryByTags(const QStringList &tags, int maxResults) const
{
    QVector<SpatialMemoryEntry> result;
    for (int i = m_entries.size() - 1; i >= 0 && result.size() < maxResults; --i) {
        bool match = true;
        for (const auto &tag : tags) {
            if (!m_entries[i].tags.contains(tag)) {
                match = false;
                break;
            }
        }
        if (match)
            result.append(m_entries[i]);
    }
    return result;
}

QVector<SpatialMemoryEntry>
SpatialMemory::queryByTimeRange(const QDateTime &from, const QDateTime &to) const
{
    QVector<SpatialMemoryEntry> result;
    for (const auto &e : m_entries) {
        if (e.timestamp >= from && e.timestamp <= to)
            result.append(e);
    }
    return result;
}

// ── Stats ──

void SpatialMemory::setMaxCapacity(int capacity)
{
    m_maxCapacity = qMax(100, capacity);
    evictIfNeeded();
}

// ── Export QML ──

QVariantList SpatialMemory::toVariantList(int maxEntries) const
{
    QVariantList list;
    const int start = qMax(0, m_entries.size() - maxEntries);
    for (int i = start; i < m_entries.size(); ++i)
        list.append(m_entries[i].toVariantMap());
    return list;
}

QVariantMap SpatialMemory::statsToVariantMap() const
{
    int states = 0, risks = 0, anomalies = 0, decisions = 0;
    for (const auto &e : m_entries) {
        if (e.category == "state")         ++states;
        else if (e.category == "risk")     ++risks;
        else if (e.category == "anomaly")  ++anomalies;
        else if (e.category == "decision") ++decisions;
    }
    return {
        {"total",     m_entries.size()},
        {"capacity",  m_maxCapacity},
        {"states",    states},
        {"risks",     risks},
        {"anomalies", anomalies},
        {"decisions", decisions}
    };
}

// ── Persistence ──

void SpatialMemory::saveToFile(const QString &path) const
{
    QJsonArray arr;
    for (const auto &e : m_entries) {
        QJsonObject obj;
        obj["id"]        = e.id;
        obj["category"]  = e.category;
        obj["data"]      = QJsonObject::fromVariantMap(e.data);
        obj["timestamp"] = e.timestamp.toString(Qt::ISODate);
        obj["relevance"] = e.relevance;
        QJsonArray tags;
        for (const auto &t : e.tags)
            tags.append(t);
        obj["tags"] = tags;
        arr.append(obj);
    }

    QFile file(path);
    if (file.open(QIODevice::WriteOnly)) {
        file.write(QJsonDocument(arr).toJson(QJsonDocument::Compact));
    }
}

void SpatialMemory::loadFromFile(const QString &path)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly))
        return;

    const auto doc = QJsonDocument::fromJson(file.readAll());
    if (!doc.isArray())
        return;

    m_entries.clear();
    const auto arr = doc.array();
    for (const auto &val : arr) {
        const QJsonObject obj = val.toObject();
        SpatialMemoryEntry entry;
        entry.id        = obj.value("id").toString();
        entry.category  = obj.value("category").toString();
        entry.data      = obj.value("data").toObject().toVariantMap();
        entry.timestamp = QDateTime::fromString(obj.value("timestamp").toString(), Qt::ISODate);
        entry.relevance = obj.value("relevance").toDouble(1.0);
        const auto tags = obj.value("tags").toArray();
        for (const auto &t : tags)
            entry.tags.append(t.toString());
        m_entries.append(entry);
    }
}

// ── Clear ──

void SpatialMemory::clear()
{
    m_entries.clear();
    emit memoryCleared();
}

// ── Private ──

void SpatialMemory::addEntry(const SpatialMemoryEntry &entry)
{
    SpatialMemoryEntry e = entry;
    if (e.id.isEmpty())
        e.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
    if (!e.timestamp.isValid())
        e.timestamp = QDateTime::currentDateTime();

    m_entries.append(e);
    evictIfNeeded();
    emit entryStored(e.id, e.category);
}

void SpatialMemory::evictIfNeeded()
{
    while (m_entries.size() > m_maxCapacity) {
        // Retirer l'entrée la plus ancienne avec la plus faible relevance
        int minIdx = 0;
        double minScore = std::numeric_limits<double>::max();
        for (int i = 0; i < m_entries.size(); ++i) {
            // Score = relevance * recency
            const double age = m_entries[i].timestamp.secsTo(QDateTime::currentDateTime());
            const double score = m_entries[i].relevance / (1.0 + age / 86400.0);
            if (score < minScore) {
                minScore = score;
                minIdx = i;
            }
        }
        m_entries.removeAt(minIdx);
    }
}

double SpatialMemory::computeSimilarity(const QVariantMap &a, const QVariantMap &b) const
{
    // Jaccard-like sur les paires clé=valeur
    int matches = 0;
    int total = a.size() + b.size();
    if (total == 0)
        return 0.0;

    for (auto it = a.constBegin(); it != a.constEnd(); ++it) {
        if (b.contains(it.key()) && b.value(it.key()) == it.value())
            ++matches;
    }

    return static_cast<double>(2 * matches) / static_cast<double>(total);
}
