#include "TraceManager.h"
#include <QLoggingCategory>
#include <mutex>

Q_LOGGING_CATEGORY(exoTrace, "exo.trace")

TraceManager *TraceManager::s_instance = nullptr;
static std::once_flag s_traceManagerOnce;

TraceManager::TraceManager(QObject *parent)
    : QObject(parent)
{
    m_clock.start();
}

TraceManager* TraceManager::instance()
{
    std::call_once(s_traceManagerOnce, []() {
        s_instance = new TraceManager();
    });
    return s_instance;
}

// ── Span lifecycle ───────────────────────────────────

QString TraceManager::startTrace(const QString &name)
{
    QMutexLocker lock(&m_mutex);
    QString traceId = QUuid::createUuid().toString(QUuid::WithoutBraces).left(16);
    m_currentTraceId = traceId;

    TraceSpan root;
    root.spanId   = QUuid::createUuid().toString(QUuid::WithoutBraces).left(16);
    root.traceId  = traceId;
    root.name     = name;
    root.startMs  = m_clock.elapsed();
    m_activeSpans.insert(root.spanId, root);

    qCInfo(exoTrace) << "Trace démarrée :" << traceId << name;
    emit traceStarted(traceId);
    return traceId;
}

QString TraceManager::startSpan(const QString &traceId, const QString &name,
                                const QString &parentSpanId)
{
    QMutexLocker lock(&m_mutex);
    TraceSpan span;
    span.spanId   = QUuid::createUuid().toString(QUuid::WithoutBraces).left(16);
    span.traceId  = traceId;
    span.parentId = parentSpanId;
    span.name     = name;
    span.startMs  = m_clock.elapsed();
    m_activeSpans.insert(span.spanId, span);
    return span.spanId;
}

void TraceManager::endSpan(const QString &spanId)
{
    QMutexLocker lock(&m_mutex);
    auto it = m_activeSpans.find(spanId);
    if (it == m_activeSpans.end())
        return;

    it->endMs = m_clock.elapsed();
    TraceSpan completed = *it;
    m_activeSpans.erase(it);

    if (m_completedSpans.size() >= MAX_COMPLETED_SPANS)
        m_completedSpans.removeFirst();
    m_completedSpans.append(completed);

    qCDebug(exoTrace) << "Span terminé :" << completed.name
                      << completed.durationMs() << "ms";

    lock.unlock();
    emit spanEnded(completed.toJson());
}

void TraceManager::addAttribute(const QString &spanId, const QString &key,
                                const QJsonValue &value)
{
    QMutexLocker lock(&m_mutex);
    auto it = m_activeSpans.find(spanId);
    if (it != m_activeSpans.end())
        it->attributes.insert(key, value);
}

// ── Query ────────────────────────────────────────────

QVector<TraceSpan> TraceManager::spansForTrace(const QString &traceId) const
{
    QMutexLocker lock(&m_mutex);
    QVector<TraceSpan> result;
    for (const auto &span : m_completedSpans) {
        if (span.traceId == traceId)
            result.append(span);
    }
    return result;
}

QJsonArray TraceManager::recentTraces(int maxCount) const
{
    QMutexLocker lock(&m_mutex);
    QJsonArray arr;
    // Collect unique trace IDs from most recent
    QStringList seen;
    for (int i = m_completedSpans.size() - 1; i >= 0 && seen.size() < maxCount; --i) {
        const auto &span = m_completedSpans[i];
        if (!seen.contains(span.traceId)) {
            seen.append(span.traceId);
            arr.append(span.toJson());
        }
    }
    return arr;
}

// ── QML API ──────────────────────────────────────────

QJsonObject TraceManager::getActiveTrace() const
{
    QMutexLocker lock(&m_mutex);
    QJsonObject obj;
    obj["trace_id"] = m_currentTraceId;
    obj["active_spans"] = m_activeSpans.size();
    QJsonArray spans;
    for (const auto &span : m_activeSpans)
        spans.append(span.toJson());
    obj["spans"] = spans;
    return obj;
}

QJsonArray TraceManager::getTraceHistory(int maxCount) const
{
    return recentTraces(maxCount);
}
