#include "AudioProfiler.h"
#include "core/LogManager.h"

#include <QDebug>
#include <algorithm>
#include <cstdio>
#include <cstdint>

namespace {
inline int64_t microsSince(AudioProfiler::clock::time_point start)
{
    return std::chrono::duration_cast<std::chrono::microseconds>(
               AudioProfiler::clock::now() - start).count();
}

// Atomic min / max helpers (relaxed CAS).
inline void atomicMinI64(std::atomic<int64_t> &dst, int64_t v)
{
    int64_t cur = dst.load(std::memory_order_relaxed);
    while (v < cur && !dst.compare_exchange_weak(cur, v, std::memory_order_relaxed)) { }
}
inline void atomicMaxI64(std::atomic<int64_t> &dst, int64_t v)
{
    int64_t cur = dst.load(std::memory_order_relaxed);
    while (v > cur && !dst.compare_exchange_weak(cur, v, std::memory_order_relaxed)) { }
}
} // namespace

AudioProfiler::AudioProfiler()
    : m_startTp(clock::now())
{
    m_lastFlushUs.store(0, std::memory_order_relaxed);
}

void AudioProfiler::reset()
{
    m_pushCount.store(0); m_popCount.store(0);
    m_pushSamples.store(0); m_popSamples.store(0);
    m_underflowCount.store(0); m_overflowCount.store(0); m_anomalyCount.store(0);
    m_lastPopUs.store(0); m_lastPushUs.store(0);
    m_dtSumUs.store(0); m_dtMinUs.store(INT64_MAX); m_dtMaxUs.store(0); m_dtSamples.store(0);
    m_jitterSumUs.store(0); m_jitterMaxUs.store(0); m_driftUs.store(0);
    m_pushDtSumUs.store(0); m_pushDtSamples.store(0);
    m_writeMaxUs.store(0); m_writeSumUs.store(0); m_writeSamples.store(0);
    m_lastBlockSamples.store(0);
    m_dirty.store(false);
    m_startTp = clock::now();
    m_lastFlushUs.store(0);
}

void AudioProfiler::onPush(int samples)
{
    if (!m_enabled.load(std::memory_order_relaxed)) return;
    if (samples <= 0) return;

    m_pushCount.fetch_add(1, std::memory_order_relaxed);
    m_pushSamples.fetch_add(static_cast<uint64_t>(samples), std::memory_order_relaxed);

    const int64_t nowUs = microsSince(m_startTp);
    const int64_t prev  = m_lastPushUs.exchange(nowUs, std::memory_order_relaxed);
    if (prev > 0) {
        m_pushDtSumUs.fetch_add(nowUs - prev, std::memory_order_relaxed);
        m_pushDtSamples.fetch_add(1, std::memory_order_relaxed);
    }
}

void AudioProfiler::onPop(int samples, int blockBytes)
{
    if (!m_enabled.load(std::memory_order_relaxed)) return;
    if (samples <= 0) return;

    m_popCount.fetch_add(1, std::memory_order_relaxed);
    m_popSamples.fetch_add(static_cast<uint64_t>(samples), std::memory_order_relaxed);
    m_lastBlockSamples.store(samples, std::memory_order_relaxed);

    // Anomalie : taille != EXPECTED_BLOCK_SAMPLES (sauf dernier bloc d'une phrase)
    if (samples != EXPECTED_BLOCK_SAMPLES) {
        m_anomalyCount.fetch_add(1, std::memory_order_relaxed);
        m_dirty.store(true, std::memory_order_relaxed);
    }

    const int64_t nowUs = microsSince(m_startTp);
    const int64_t prev  = m_lastPopUs.exchange(nowUs, std::memory_order_relaxed);
    if (prev > 0) {
        const int64_t dtUs       = nowUs - prev;
        const int64_t expectedUs = static_cast<int64_t>(samples) * 1000000LL / 24000LL;
        const int64_t jitterUs   = std::llabs(dtUs - expectedUs);

        m_dtSumUs.fetch_add(dtUs, std::memory_order_relaxed);
        atomicMinI64(m_dtMinUs, dtUs);
        atomicMaxI64(m_dtMaxUs, dtUs);
        m_dtSamples.fetch_add(1, std::memory_order_relaxed);

        m_jitterSumUs.fetch_add(jitterUs, std::memory_order_relaxed);
        atomicMaxI64(m_jitterMaxUs, jitterUs);
        m_driftUs.fetch_add(dtUs - expectedUs, std::memory_order_relaxed);

        if (jitterUs > 10000) { // > 10 ms -> anomalie
            m_anomalyCount.fetch_add(1, std::memory_order_relaxed);
            m_dirty.store(true, std::memory_order_relaxed);
        }
    }
    (void)blockBytes;
}

void AudioProfiler::onAudioWrite(int64_t writeMicros)
{
    if (!m_enabled.load(std::memory_order_relaxed)) return;
    if (writeMicros < 0) return;
    m_writeSumUs.fetch_add(writeMicros, std::memory_order_relaxed);
    m_writeSamples.fetch_add(1, std::memory_order_relaxed);
    atomicMaxI64(m_writeMaxUs, writeMicros);
}

void AudioProfiler::maybeFlush(bool force)
{
    if (!m_enabled.load(std::memory_order_relaxed)) return;
    const int64_t nowUs    = microsSince(m_startTp);
    const int64_t lastUs   = m_lastFlushUs.load(std::memory_order_relaxed);
    const int64_t intervUs = static_cast<int64_t>(m_logIntervalMs.load(std::memory_order_relaxed)) * 1000LL;
    const bool anomaly     = m_dirty.exchange(false, std::memory_order_relaxed);

    if (!force && !anomaly && (nowUs - lastUs) < intervUs)
        return;

    m_lastFlushUs.store(nowUs, std::memory_order_relaxed);
    doFlush(anomaly || force);
}

void AudioProfiler::doFlush(bool anomaly)
{
    const uint64_t pop      = m_popCount.load(std::memory_order_relaxed);
    const uint64_t push     = m_pushCount.load(std::memory_order_relaxed);
    const uint64_t dtN      = m_dtSamples.load(std::memory_order_relaxed);
    const int64_t  dtSum    = m_dtSumUs.load(std::memory_order_relaxed);
    const int64_t  dtMin    = m_dtMinUs.load(std::memory_order_relaxed);
    const int64_t  dtMax    = m_dtMaxUs.load(std::memory_order_relaxed);
    const int64_t  jitSum   = m_jitterSumUs.load(std::memory_order_relaxed);
    const int64_t  jitMax   = m_jitterMaxUs.load(std::memory_order_relaxed);
    const int64_t  drift    = m_driftUs.load(std::memory_order_relaxed);
    const uint64_t under    = m_underflowCount.load(std::memory_order_relaxed);
    const uint64_t over     = m_overflowCount.load(std::memory_order_relaxed);
    const uint64_t anomN    = m_anomalyCount.load(std::memory_order_relaxed);
    const int      block    = m_lastBlockSamples.load(std::memory_order_relaxed);
    const int      ringFree = m_ringFreeBytes.load(std::memory_order_relaxed);
    const int64_t  wMax     = m_writeMaxUs.load(std::memory_order_relaxed);
    const uint64_t wN       = m_writeSamples.load(std::memory_order_relaxed);
    const int64_t  wSum     = m_writeSumUs.load(std::memory_order_relaxed);

    const double dtAvgMs   = dtN ? (static_cast<double>(dtSum) / dtN) / 1000.0 : 0.0;
    const double dtMinMs   = (dtN && dtMin != INT64_MAX) ? dtMin / 1000.0 : 0.0;
    const double dtMaxMs   = dtN ? dtMax / 1000.0 : 0.0;
    const double jitAvgMs  = dtN ? (static_cast<double>(jitSum) / dtN) / 1000.0 : 0.0;
    const double jitMaxMs  = jitMax / 1000.0;
    const double driftMs   = drift / 1000.0;
    const double wAvgMs    = wN ? (static_cast<double>(wSum) / wN) / 1000.0 : 0.0;
    const double wMaxMs    = wMax / 1000.0;

    char buf[512];
    std::snprintf(buf, sizeof(buf),
        "[AUDIO] block=%d samples | pop=%llu push=%llu | dt=%.1f ms (min %.1f / max %.1f) "
        "| jitter=%.2f ms (max %.2f) | drift=%+.1f ms | free=%d B | under=%llu over=%llu anom=%llu | write=%.2f/%.2f ms",
        block,
        static_cast<unsigned long long>(pop),
        static_cast<unsigned long long>(push),
        dtAvgMs, dtMinMs, dtMaxMs,
        jitAvgMs, jitMaxMs,
        driftMs,
        ringFree,
        static_cast<unsigned long long>(under),
        static_cast<unsigned long long>(over),
        static_cast<unsigned long long>(anomN),
        wAvgMs, wMaxMs);

    if (anomaly)
        hWarning(exoVoice) << buf;
    else
        hVoice() << buf;

    // Reset des fenetres glissantes (counters cumulatifs gardes pour le total)
    m_dtSumUs.store(0); m_dtMinUs.store(INT64_MAX); m_dtMaxUs.store(0); m_dtSamples.store(0);
    m_jitterSumUs.store(0); m_jitterMaxUs.store(0);
    m_writeMaxUs.store(0); m_writeSumUs.store(0); m_writeSamples.store(0);
}
