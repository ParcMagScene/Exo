#pragma once

#include <QObject>
#include <QHash>
#include <QJsonObject>
#include <QTimer>
#include <QElapsedTimer>
#include <QMutex>
#include <QStringList>

// ─────────────────────────────────────────────────────
//  CacheEntry — single cached value with TTL
// ─────────────────────────────────────────────────────
struct CacheEntry
{
    QJsonObject value;
    qint64      ttlMs      = 30000;   // time-to-live in ms
    qint64      insertedAt = 0;       // elapsed ms since cache start
    int         hitCount   = 0;
};

// ─────────────────────────────────────────────────────
//  ContextCache — in-process cache with TTL
//
//  Reduces latency by caching tool results (weather,
//  datetime, HA state, network, etc.) and serving them
//  instantly instead of dispatching to microservices.
//
//  Thread-safe via QMutex.
// ─────────────────────────────────────────────────────
class ContextCache : public QObject
{
    Q_OBJECT

public:
    explicit ContextCache(QObject *parent = nullptr);
    ~ContextCache() override = default;

    // ── Core API ─────────────────────────────────────
    bool        has(const QString &key) const;
    QJsonObject get(const QString &key);
    void        set(const QString &key, const QJsonObject &value,
                    qint64 ttlMs = 30000);
    void        invalidate(const QString &key);
    void        invalidateAll();

    // ── Batch operations ─────────────────────────────
    void        setMultiple(const QHash<QString, QJsonObject> &entries,
                            qint64 ttlMs = 30000);

    // ── Stats ────────────────────────────────────────
    int         size() const;
    int         totalHits() const { return m_totalHits; }
    int         totalMisses() const { return m_totalMisses; }
    double      hitRate() const;
    QJsonObject stats() const;

    // ── Background refresh ───────────────────────────
    struct RefreshRule {
        QString key;
        qint64  intervalMs;
    };
    void addRefreshRule(const QString &key, qint64 intervalMs);
    void startBackgroundRefresh();
    void stopBackgroundRefresh();

signals:
    void cacheHit(const QString &key);
    void cacheMiss(const QString &key);
    void refreshNeeded(const QString &key);
    void entryExpired(const QString &key);

private slots:
    void onRefreshTimer();
    void evictExpired();

private:
    bool isExpired(const CacheEntry &entry) const;
    double hitRate_locked() const;  // call with m_mutex already held

    mutable QMutex m_mutex;
    QHash<QString, CacheEntry> m_entries;
    QElapsedTimer m_clock;
    QTimer *m_evictionTimer  = nullptr;
    QTimer *m_refreshTimer   = nullptr;

    QVector<RefreshRule> m_refreshRules;

    int m_totalHits   = 0;
    int m_totalMisses = 0;
};
