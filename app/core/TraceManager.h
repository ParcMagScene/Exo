#pragma once

#include "PipelineTracer.h"
#include <QObject>
#include <QJsonObject>
#include <QJsonArray>
#include <QMutex>
#include <QMap>
#include <QElapsedTimer>
#include <QUuid>

// ─────────────────────────────────────────────────────
//  TraceSpan — un span individuel dans une trace
// ─────────────────────────────────────────────────────
struct TraceSpan
{
    QString spanId;
    QString parentId;
    QString traceId;
    QString name;
    qint64  startMs = 0;
    qint64  endMs   = 0;
    QJsonObject attributes;

    qint64 durationMs() const { return endMs - startMs; }
    QJsonObject toJson() const {
        return {
            {"span_id", spanId}, {"parent_id", parentId},
            {"trace_id", traceId}, {"name", name},
            {"start_ms", startMs}, {"end_ms", endMs},
            {"duration_ms", durationMs()}, {"attributes", attributes},
        };
    }
};

// ─────────────────────────────────────────────────────
//  TraceManager — tracing distribué unifié (v26)
//
//  Fournit un système de spans hiérarchiques (trace_id →
//  span_id → parent_id) pour le suivi distribué des
//  interactions. Délègue l'analyse post-interaction
//  à PipelineTracer.
// ─────────────────────────────────────────────────────
class TraceManager : public QObject
{
    Q_OBJECT

public:
    static TraceManager* instance();

    // ── Span lifecycle ───────────────────────────────
    QString startTrace(const QString &name);
    QString startSpan(const QString &traceId, const QString &name,
                      const QString &parentSpanId = {});
    void endSpan(const QString &spanId);
    void addAttribute(const QString &spanId, const QString &key, const QJsonValue &value);

    // ── Query ────────────────────────────────────────
    QVector<TraceSpan> spansForTrace(const QString &traceId) const;
    QJsonArray recentTraces(int maxCount = 20) const;

    // ── Pipeline tracer (délègue) ────────────────────
    PipelineTracer* pipelineTracer() const { return PipelineTracer::instance(); }

    // ── QML API ──────────────────────────────────────
    Q_INVOKABLE QJsonObject getActiveTrace() const;
    Q_INVOKABLE QJsonArray  getTraceHistory(int maxCount = 10) const;

signals:
    void traceStarted(const QString &traceId);
    void spanEnded(const QJsonObject &span);

private:
    explicit TraceManager(QObject *parent = nullptr);

    mutable QMutex m_mutex;
    QElapsedTimer  m_clock;
    QMap<QString, TraceSpan> m_activeSpans;
    QVector<TraceSpan>       m_completedSpans;
    QString                  m_currentTraceId;

    static TraceManager *s_instance;
    static constexpr int MAX_COMPLETED_SPANS = 2000;
};
