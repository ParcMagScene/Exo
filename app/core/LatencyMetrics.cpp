#include "LatencyMetrics.h"
#include "LogManager.h"
#include <mutex>

LatencyMetrics *LatencyMetrics::s_instance = nullptr;
static std::once_flag s_latencyMetricsOnce;

LatencyMetrics *LatencyMetrics::instance()
{
    std::call_once(s_latencyMetricsOnce, []() {
        s_instance = new LatencyMetrics(nullptr);
    });
    return s_instance;
}

LatencyMetrics::LatencyMetrics(QObject *parent)
    : QObject(parent)
{
    m_clock.start();
    hAssistant() << "LatencyMetrics initialisé";
}

// ═══════════════════════════════════════════════════════
//  Milestone recording
// ═══════════════════════════════════════════════════════

void LatencyMetrics::markSttStart()
{
    QMutexLocker lock(&m_mutex);
    m_current = {};  // reset for new interaction
    m_current.tSttStart = m_clock.elapsed();
}

void LatencyMetrics::markSttPartialFirst()
{
    QMutexLocker lock(&m_mutex);
    if (m_current.tSttPartialFirst == 0)
        m_current.tSttPartialFirst = m_clock.elapsed();
}

void LatencyMetrics::markSttFinal()
{
    QMutexLocker lock(&m_mutex);
    m_current.tSttFinal = m_clock.elapsed();
}

void LatencyMetrics::markLlmRequest()
{
    QMutexLocker lock(&m_mutex);
    m_current.tLlmRequest = m_clock.elapsed();
}

void LatencyMetrics::markLlmFirstToken()
{
    QMutexLocker lock(&m_mutex);
    if (m_current.tLlmFirstToken == 0)
        m_current.tLlmFirstToken = m_clock.elapsed();
}

void LatencyMetrics::markLlmComplete()
{
    QMutexLocker lock(&m_mutex);
    m_current.tLlmComplete = m_clock.elapsed();
}

void LatencyMetrics::markTtsFirstChunk()
{
    QMutexLocker lock(&m_mutex);
    if (m_current.tTtsFirstChunk == 0)
        m_current.tTtsFirstChunk = m_clock.elapsed();
}

void LatencyMetrics::markTtsFirstAudio()
{
    QMutexLocker lock(&m_mutex);
    if (m_current.tTtsFirstAudio == 0)
        m_current.tTtsFirstAudio = m_clock.elapsed();
}

void LatencyMetrics::markResponseDone()
{
    QMutexLocker lock(&m_mutex);
    m_current.tResponseDone = m_clock.elapsed();
}

// ═══════════════════════════════════════════════════════
//  Finalize
// ═══════════════════════════════════════════════════════

void LatencyMetrics::finalize()
{
    QMutexLocker lock(&m_mutex);
    if (m_current.tSttStart == 0) return; // nothing to finalize

    if (m_current.tResponseDone == 0)
        m_current.tResponseDone = m_clock.elapsed();

    m_history.append(m_current);
    if (m_history.size() > MAX_HISTORY)
        m_history.removeFirst();

    LatencySnapshot snap = m_current;
    lock.unlock();

    QJsonObject json = snap.toJson();
    hAssistant() << "Latency:"
                 << "perceived=" << snap.perceivedLatency() << "ms"
                 << "stt=" << snap.sttLatency() << "ms"
                 << "llm_first=" << snap.llmFirstTokenLatency() << "ms"
                 << "tts=" << snap.ttsLatency() << "ms"
                 << "e2e=" << snap.endToEnd() << "ms";

    emit interactionFinalized(json);
}

// ═══════════════════════════════════════════════════════
//  Query
// ═══════════════════════════════════════════════════════

LatencySnapshot LatencyMetrics::current() const
{
    QMutexLocker lock(&m_mutex);
    return m_current;
}

LatencySnapshot LatencyMetrics::lastCompleted() const
{
    QMutexLocker lock(&m_mutex);
    return m_history.isEmpty() ? LatencySnapshot{} : m_history.last();
}

QJsonObject LatencyMetrics::averages(int lastN) const
{
    QMutexLocker lock(&m_mutex);
    if (m_history.isEmpty())
        return {};

    int count = qMin(lastN, m_history.size());
    int start = m_history.size() - count;

    double avgPerceived = 0, avgStt = 0, avgLlmFirst = 0, avgTts = 0, avgE2e = 0;
    int validCount = 0;

    for (int i = start; i < m_history.size(); ++i) {
        const auto &s = m_history[i];
        if (s.tSttFinal == 0 || s.tTtsFirstAudio == 0) continue;
        avgPerceived += s.perceivedLatency();
        avgStt       += s.sttLatency();
        avgLlmFirst  += s.llmFirstTokenLatency();
        avgTts       += s.ttsLatency();
        avgE2e       += s.endToEnd();
        ++validCount;
    }

    if (validCount == 0) return {};

    QJsonObject result;
    result[QStringLiteral("count")]             = validCount;
    result[QStringLiteral("avg_perceived_ms")]  = qRound(avgPerceived / validCount);
    result[QStringLiteral("avg_stt_ms")]        = qRound(avgStt / validCount);
    result[QStringLiteral("avg_llm_first_ms")]  = qRound(avgLlmFirst / validCount);
    result[QStringLiteral("avg_tts_ms")]        = qRound(avgTts / validCount);
    result[QStringLiteral("avg_e2e_ms")]        = qRound(avgE2e / validCount);
    return result;
}

QJsonArray LatencyMetrics::recentSnapshots(int maxCount) const
{
    QMutexLocker lock(&m_mutex);
    QJsonArray arr;
    int start = qMax(0, m_history.size() - maxCount);
    for (int i = start; i < m_history.size(); ++i)
        arr.append(m_history[i].toJson());
    return arr;
}

QJsonObject LatencyMetrics::getLatencyReport() const
{
    QJsonObject report;
    report[QStringLiteral("current")]  = current().toJson();
    report[QStringLiteral("averages")] = averages(20);
    report[QStringLiteral("recent")]   = recentSnapshots(5);
    return report;
}

// ═══════════════════════════════════════════════════════
//  LatencySnapshot JSON
// ═══════════════════════════════════════════════════════

QJsonObject LatencySnapshot::toJson() const
{
    QJsonObject o;
    o[QStringLiteral("t_stt_start")]        = tSttStart;
    o[QStringLiteral("t_stt_partial_first")]= tSttPartialFirst;
    o[QStringLiteral("t_stt_final")]        = tSttFinal;
    o[QStringLiteral("t_llm_request")]      = tLlmRequest;
    o[QStringLiteral("t_llm_first_token")]  = tLlmFirstToken;
    o[QStringLiteral("t_llm_complete")]     = tLlmComplete;
    o[QStringLiteral("t_tts_first_chunk")]  = tTtsFirstChunk;
    o[QStringLiteral("t_tts_first_audio")]  = tTtsFirstAudio;
    o[QStringLiteral("t_response_done")]    = tResponseDone;
    // Derived
    if (tSttFinal > 0 && tSttStart > 0)
        o[QStringLiteral("stt_latency_ms")]     = sttLatency();
    if (tLlmFirstToken > 0 && tLlmRequest > 0)
        o[QStringLiteral("llm_first_token_ms")] = llmFirstTokenLatency();
    if (tTtsFirstAudio > 0 && tSttFinal > 0)
        o[QStringLiteral("perceived_ms")]       = perceivedLatency();
    if (tResponseDone > 0 && tSttStart > 0)
        o[QStringLiteral("end_to_end_ms")]      = endToEnd();
    return o;
}
