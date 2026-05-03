#pragma once

#include <QObject>
#include <QElapsedTimer>
#include <QJsonObject>
#include <QJsonArray>
#include <QMutex>
#include <QVector>

// ─────────────────────────────────────────────────────
//  LatencySnapshot — single interaction timing
// ─────────────────────────────────────────────────────
struct LatencySnapshot
{
    qint64 tSttStart       = 0;   // user starts speaking → STT begins
    qint64 tSttPartialFirst= 0;   // first partial transcript
    qint64 tSttFinal       = 0;   // final transcript ready
    qint64 tLlmRequest     = 0;   // request sent to Claude
    qint64 tLlmFirstToken  = 0;   // first token received
    qint64 tLlmComplete    = 0;   // full response complete
    qint64 tTtsFirstChunk  = 0;   // first TTS audio chunk
    qint64 tTtsFirstAudio  = 0;   // audio playback started
    qint64 tResponseDone   = 0;   // full response played

    // Derived metrics (computed)
    qint64 sttLatency() const {
        return (tSttStart > 0 && tSttFinal >= tSttStart) ? (tSttFinal - tSttStart) : 0;
    }
    qint64 llmFirstTokenLatency() const {
        return (tLlmRequest > 0 && tLlmFirstToken >= tLlmRequest) ? (tLlmFirstToken - tLlmRequest) : 0;
    }
    qint64 llmTotalLatency() const {
        return (tLlmRequest > 0 && tLlmComplete >= tLlmRequest) ? (tLlmComplete - tLlmRequest) : 0;
    }
    qint64 ttsLatency() const {
        return (tLlmFirstToken > 0 && tTtsFirstAudio >= tLlmFirstToken) ? (tTtsFirstAudio - tLlmFirstToken) : 0;
    }
    qint64 perceivedLatency() const {
        return (tSttFinal > 0 && tTtsFirstAudio >= tSttFinal) ? (tTtsFirstAudio - tSttFinal) : 0;
    }
    qint64 endToEnd() const {
        return (tSttStart > 0 && tResponseDone >= tSttStart) ? (tResponseDone - tSttStart) : 0;
    }

    QJsonObject toJson() const;
};

// ─────────────────────────────────────────────────────
//  LatencyMetrics — pipeline latency instrumentation
//
//  Tracks timing milestones across the voice pipeline
//  (STT → LLM → TTS) for each interaction. Provides
//  rolling averages and per-interaction snapshots.
// ─────────────────────────────────────────────────────
class LatencyMetrics : public QObject
{
    Q_OBJECT

public:
    static LatencyMetrics* instance();

    // ── Milestone recording ──────────────────────────
    void markSttStart();
    void markSttPartialFirst();
    void markSttFinal();
    void markLlmRequest();
    void markLlmFirstToken();
    void markLlmComplete();
    void markTtsFirstChunk();
    void markTtsFirstAudio();
    void markResponseDone();

    // ── Finalize current interaction ─────────────────
    void finalize();

    // ── Query ────────────────────────────────────────
    LatencySnapshot current() const;
    LatencySnapshot lastCompleted() const;
    QJsonObject     averages(int lastN = 20) const;
    QJsonArray      recentSnapshots(int maxCount = 10) const;

    // ── QML ──────────────────────────────────────────
    Q_INVOKABLE QJsonObject getLatencyReport() const;

signals:
    void interactionFinalized(const QJsonObject &snapshot);

private:
    explicit LatencyMetrics(QObject *parent = nullptr);

    mutable QMutex m_mutex;
    QElapsedTimer  m_clock;
    LatencySnapshot m_current;
    QVector<LatencySnapshot> m_history;

    static LatencyMetrics *s_instance;
    static constexpr int MAX_HISTORY = 100;
};
