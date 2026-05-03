#ifndef SPATIALMEMORY_H
#define SPATIALMEMORY_H

#include "SpatialEnums.h"
#include "SpatialContext.h"

#include <QObject>
#include <QString>
#include <QVector>
#include <QVariantMap>
#include <QVariantList>
#include <QDateTime>

// ─────────────────────────────────────────────────────
//  SpatialMemoryEntry — Entrée en mémoire spatiale
// ─────────────────────────────────────────────────────
struct SpatialMemoryEntry
{
    QString     id;
    QString     category;  // "state", "risk", "anomaly", "decision", "event"
    QVariantMap data;
    QDateTime   timestamp;
    double      relevance = 1.0;
    QStringList tags;

    QVariantMap toVariantMap() const;
};

// ─────────────────────────────────────────────────────
//  SpatialMemory — Mémoire spatiale persistante
//
//  Stocke et interroge :
//   • Historique des états spatiaux
//   • Historique des risques détectés
//   • Historique des anomalies
//   • Historique des décisions prises
//   • Recherche par similarité (vecteurs futurs via FAISS)
//
//  Capacité limitée avec éviction LRU sur la relevance.
// ─────────────────────────────────────────────────────
class SpatialMemory : public QObject
{
    Q_OBJECT

public:
    explicit SpatialMemory(QObject *parent = nullptr);
    ~SpatialMemory() override;

    // ── Stockage ──
    void storeState(const QVariantMap &snapshot);
    void storeRisk(const QVariantMap &risk);
    void storeAnomaly(const QVariantMap &anomaly);
    void storeDecision(const QVariantMap &decision);
    void storeEvent(const QString &category, const QVariantMap &data,
                    const QStringList &tags = {});

    // ── Requêtes ──
    QVector<SpatialMemoryEntry> querySimilarSituations(const QVariantMap &currentState,
                                                 int maxResults = 5) const;
    QVector<SpatialMemoryEntry> retrievePastRisks(const QString &roomId = {},
                                            int maxResults = 10) const;
    QVector<SpatialMemoryEntry> retrievePastAnomalies(const QString &roomId = {},
                                                int maxResults = 10) const;
    QVector<SpatialMemoryEntry> retrievePastDecisions(int maxResults = 10) const;
    QVector<SpatialMemoryEntry> queryByCategory(const QString &category,
                                          int maxResults = 20) const;
    QVector<SpatialMemoryEntry> queryByTags(const QStringList &tags,
                                      int maxResults = 10) const;
    QVector<SpatialMemoryEntry> queryByTimeRange(const QDateTime &from,
                                           const QDateTime &to) const;

    // ── Stats ──
    int entryCount() const { return m_entries.size(); }
    int maxCapacity() const { return m_maxCapacity; }
    void setMaxCapacity(int capacity);

    // ── Export QML ──
    QVariantList toVariantList(int maxEntries = 50) const;
    QVariantMap  statsToVariantMap() const;

    // ── Persistence ──
    void saveToFile(const QString &path) const;
    void loadFromFile(const QString &path);

    // ── Clear ──
    void clear();

signals:
    void entryStored(const QString &id, const QString &category);
    void memoryCleared();

private:
    void addEntry(const SpatialMemoryEntry &entry);
    void evictIfNeeded();
    double computeSimilarity(const QVariantMap &a, const QVariantMap &b) const;

    QVector<SpatialMemoryEntry> m_entries;
    int m_maxCapacity = 5000;
};

#endif // SPATIALMEMORY_H
