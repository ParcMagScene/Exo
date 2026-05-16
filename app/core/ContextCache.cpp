#include "ContextCache.h"
#include "LogManager.h"

static constexpr int EVICTION_INTERVAL_MS = 10000;  // 10s

// ═══════════════════════════════════════════════════════
//  Construction
// ═══════════════════════════════════════════════════════

ContextCache::ContextCache(QObject *parent)
    : QObject(parent)
    , m_evictionTimer(new QTimer(this))
    , m_refreshTimer(new QTimer(this))
{
    m_clock.start();

    // Eviction toutes les 10 secondes
    m_evictionTimer->setInterval(EVICTION_INTERVAL_MS);
    connect(m_evictionTimer, &QTimer::timeout, this, &ContextCache::evictExpired);
    m_evictionTimer->start();

    hAssistant() << "ContextCache initialisé";
}

// ═══════════════════════════════════════════════════════
//  Core API
// ═══════════════════════════════════════════════════════

bool ContextCache::has(const QString &key) const
{
    QMutexLocker lock(&m_mutex);
    auto it = m_entries.constFind(key);
    if (it == m_entries.constEnd())
        return false;
    return !isExpired(it.value());
}

QJsonObject ContextCache::get(const QString &key)
{
    QMutexLocker lock(&m_mutex);
    auto it = m_entries.find(key);
    if (it == m_entries.end() || isExpired(it.value())) {
        ++m_totalMisses;
        lock.unlock();
        emit cacheMiss(key);
        return {};
    }
    it->hitCount++;
    ++m_totalHits;
    QJsonObject val = it->value;
    lock.unlock();
    emit cacheHit(key);
    return val;
}

void ContextCache::set(const QString &key, const QJsonObject &value,
                       qint64 ttlMs)
{
    QMutexLocker lock(&m_mutex);
    CacheEntry entry;
    entry.value      = value;
    entry.ttlMs      = ttlMs;
    entry.insertedAt = m_clock.elapsed();
    entry.hitCount   = 0;
    m_entries.insert(key, entry);
}

void ContextCache::invalidate(const QString &key)
{
    QMutexLocker lock(&m_mutex);
    m_entries.remove(key);
}

void ContextCache::invalidateAll()
{
    QMutexLocker lock(&m_mutex);
    m_entries.clear();
    m_totalHits = 0;
    m_totalMisses = 0;
}

// ═══════════════════════════════════════════════════════
//  Batch
// ═══════════════════════════════════════════════════════

void ContextCache::setMultiple(const QHash<QString, QJsonObject> &entries,
                               qint64 ttlMs)
{
    QMutexLocker lock(&m_mutex);
    qint64 now = m_clock.elapsed();
    for (auto it = entries.cbegin(); it != entries.cend(); ++it) {
        CacheEntry entry;
        entry.value      = it.value();
        entry.ttlMs      = ttlMs;
        entry.insertedAt = now;
        entry.hitCount   = 0;
        m_entries.insert(it.key(), entry);
    }
}

// ═══════════════════════════════════════════════════════
//  Stats
// ═══════════════════════════════════════════════════════

int ContextCache::size() const
{
    QMutexLocker lock(&m_mutex);
    return m_entries.size();
}

double ContextCache::hitRate() const
{
    QMutexLocker lock(&m_mutex);
    return hitRate_locked();
}

double ContextCache::hitRate_locked() const
{
    int total = m_totalHits + m_totalMisses;
    return (total > 0) ? static_cast<double>(m_totalHits) / total : 0.0;
}

QJsonObject ContextCache::stats() const
{
    QMutexLocker lock(&m_mutex);
    QJsonObject s;
    s[QStringLiteral("size")]       = m_entries.size();
    s[QStringLiteral("hits")]       = m_totalHits;
    s[QStringLiteral("misses")]     = m_totalMisses;
    s[QStringLiteral("hit_rate")]   = hitRate_locked();
    return s;
}

// ═══════════════════════════════════════════════════════
//  Background refresh
// ═══════════════════════════════════════════════════════

void ContextCache::addRefreshRule(const QString &key, qint64 intervalMs)
{
    m_refreshRules.append({key, intervalMs});
}

void ContextCache::startBackgroundRefresh()
{
    if (m_refreshRules.isEmpty()) return;

    // Find the shortest interval for the timer tick
    qint64 minInterval = std::numeric_limits<qint64>::max();
    for (const auto &rule : m_refreshRules)
        minInterval = qMin(minInterval, rule.intervalMs);

    m_refreshTimer->setInterval(static_cast<int>(minInterval));
    connect(m_refreshTimer, &QTimer::timeout, this, &ContextCache::onRefreshTimer);
    m_refreshTimer->start();

    hAssistant() << "Rafraîchissement ContextCache en arrière-plan démarré — intervalle :"
                 << minInterval << "ms," << m_refreshRules.size() << "rules";
}

void ContextCache::stopBackgroundRefresh()
{
    m_refreshTimer->stop();
}

void ContextCache::onRefreshTimer()
{
    qint64 now = m_clock.elapsed();
    QMutexLocker lock(&m_mutex);

    for (const auto &rule : m_refreshRules) {
        auto it = m_entries.constFind(rule.key);
        if (it == m_entries.constEnd()) {
            // Key not in cache, needs refresh
            lock.unlock();
            emit refreshNeeded(rule.key);
            lock.relock();
            continue;
        }
        qint64 age = now - it->insertedAt;
        if (age >= rule.intervalMs) {
            lock.unlock();
            emit refreshNeeded(rule.key);
            lock.relock();
        }
    }
}

// ═══════════════════════════════════════════════════════
//  Eviction
// ═══════════════════════════════════════════════════════

void ContextCache::evictExpired()
{
    QMutexLocker lock(&m_mutex);
    QStringList expired;
    for (auto it = m_entries.begin(); it != m_entries.end(); ) {
        if (isExpired(it.value())) {
            expired.append(it.key());
            it = m_entries.erase(it);
        } else {
            ++it;
        }
    }
    lock.unlock();

    for (const auto &key : expired)
        emit entryExpired(key);
}

bool ContextCache::isExpired(const CacheEntry &entry) const
{
    return (m_clock.elapsed() - entry.insertedAt) > entry.ttlMs;
}
