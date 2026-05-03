#pragma once

#include "PipelineEvent.h"
#include <QObject>
#include <QJsonObject>
#include <QJsonArray>
#include <QTimer>
#include <QMap>

// ─────────────────────────────────────────────────────
//  TimelineSegment — durée d'un module dans une interaction
// ─────────────────────────────────────────────────────
struct TimelineSegment
{
    QString       moduleName;
    qint64        startMs = 0;    // elapsed ms depuis début interaction
    qint64        endMs   = 0;
    qint64        durationMs() const { return endMs - startMs; }
    QJsonObject toJson() const {
        return {{"module", moduleName},
                {"start_ms", startMs},
                {"end_ms", endMs},
                {"duration_ms", durationMs()}};
    }
};

// ─────────────────────────────────────────────────────
//  InteractionSummary — résumé structuré d'une interaction
// ─────────────────────────────────────────────────────
struct InteractionSummary
{
    QString correlationId;
    qint64  totalMs       = 0;
    qint64  vadMs         = 0;   // speech detection
    qint64  sttMs         = 0;   // transcription
    qint64  llmMs         = 0;   // Claude response
    qint64  llmFirstToken = 0;   // time to first token
    qint64  ttsMs         = 0;   // synthesis
    qint64  playbackMs    = 0;   // audio output
    int     sentenceCount = 0;
    int     eventCount    = 0;
    QStringList anomalies;

    QJsonObject toJson() const;
};

// ─────────────────────────────────────────────────────
//  AnomalyType — types d'anomalies détectées
// ─────────────────────────────────────────────────────
enum class AnomalyType {
    SlowSTT,           // STT > 5s
    SlowLLM,           // LLM > 15s
    SlowTTS,           // TTS synthesis > 10s
    NoResponse,        // Pas de réponse Claude
    DoubleTTS,         // TTS lancé 2x pour même interaction
    OverlapSpeaking,   // TTS playback pendant écoute
    OrphanInteraction, // Interaction sans endInteraction
    TotalTimeout       // Interaction totale > 30s
};

// ─────────────────────────────────────────────────────
//  PipelineTracer — analyse post-interaction
//
//  Se connecte à PipelineEventBus::interactionEnded
//  pour assembler la timeline, détecter les anomalies
//  et logger un résumé structuré.
// ─────────────────────────────────────────────────────
class PipelineTracer : public QObject
{
    Q_OBJECT

public:
    static PipelineTracer* instance();

    // Assemble la timeline à partir de la trace
    QVector<TimelineSegment> assembleTimeline(const InteractionTrace &trace) const;

    // Détecte les anomalies dans une trace
    QStringList detectAnomalies(const InteractionTrace &trace) const;

    // Génère le résumé complet d'une interaction
    InteractionSummary buildSummary(const InteractionTrace &trace) const;

    // QML API
    Q_INVOKABLE QJsonArray  getRecentSummaries(int maxCount = 10) const;
    Q_INVOKABLE QJsonObject getLastSummary() const;

    // Seuils configurables
    void setSTTThresholdMs(qint64 ms)  { m_sttThreshold = ms; }
    void setLLMThresholdMs(qint64 ms)  { m_llmThreshold = ms; }
    void setTTSThresholdMs(qint64 ms)  { m_ttsThreshold = ms; }
    void setTotalThresholdMs(qint64 ms) { m_totalThreshold = ms; }

signals:
    void summaryReady(const QJsonObject &summary);
    void anomalyDetected(const QString &anomaly, const QString &correlationId);

private slots:
    void onInteractionEnded(const QString &correlationId, qint64 durationMs);
    void onInteractionStarted(const QString &correlationId);
    void checkOrphanInteraction();

private:
    explicit PipelineTracer(QObject *parent = nullptr);
    static PipelineTracer *s_instance;

    // Finds first/last event of type in trace
    qint64 firstEventMs(const InteractionTrace &trace, const QString &module, EventType eventType) const;
    qint64 lastEventMs(const InteractionTrace &trace, const QString &module, EventType eventType) const;
    int countEvents(const InteractionTrace &trace, const QString &module, EventType eventType) const;

    // Historique des résumés
    QVector<InteractionSummary> m_summaries;
    static constexpr int MAX_SUMMARIES = 50;

    // Orphan interaction watchdog
    QTimer *m_orphanTimer = nullptr;
    QString m_activeCorrelationId;
    static constexpr int ORPHAN_TIMEOUT_MS = 60000;

    // Seuils d'anomalie (ms)
    qint64 m_sttThreshold   = 5000;
    qint64 m_llmThreshold   = 15000;
    qint64 m_ttsThreshold   = 10000;
    qint64 m_totalThreshold = 30000;
};
