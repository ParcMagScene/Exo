// ============================================================================
//  AudioAnomalyDetector.cpp
//  Implementation - voir AudioAnomalyDetector.h pour la doc complete.
// ============================================================================
#include "AudioAnomalyDetector.h"
#include "core/LogManager.h"

#include <QDebug>
#include <algorithm>
#include <cmath>
#include <cstdio>

AudioAnomalyDetector::AudioAnomalyDetector()
    : m_startTp(clock::now())
{
}

int64_t AudioAnomalyDetector::microsSince(clock::time_point start)
{
    return std::chrono::duration_cast<std::chrono::microseconds>(
               clock::now() - start).count();
}

int64_t AudioAnomalyDetector::atomicMinI64(std::atomic<int64_t> &dst, int64_t v)
{
    int64_t cur = dst.load(std::memory_order_relaxed);
    while (v < cur && !dst.compare_exchange_weak(cur, v, std::memory_order_relaxed)) {}
    return cur;
}

int64_t AudioAnomalyDetector::atomicMaxI64(std::atomic<int64_t> &dst, int64_t v)
{
    int64_t cur = dst.load(std::memory_order_relaxed);
    while (v > cur && !dst.compare_exchange_weak(cur, v, std::memory_order_relaxed)) {}
    return cur;
}

// ─────────────────────────────────────────────────────────────────────────────
//  PUSH : analyse burst / gap / silence / saturation / block size
// ─────────────────────────────────────────────────────────────────────────────
void AudioAnomalyDetector::onPush(int samples, const int16_t *pcm)
{
    if (!m_enabled.load(std::memory_order_relaxed)) return;

    const int64_t nowUs = microsSince(m_startTp);
    const int64_t prev  = m_lastPushUs.exchange(nowUs, std::memory_order_relaxed);

    m_pushCount.fetch_add(1, std::memory_order_relaxed);
    m_pushSamples.fetch_add(static_cast<uint64_t>(samples), std::memory_order_relaxed);

    // Block size mismatch ?
    if (samples != EXPECTED_BLOCK_SAMPLES) {
        m_blockMismatchCount.fetch_add(1, std::memory_order_relaxed);
        flag(Anomaly::BlockMismatch);
        char buf[160];
        std::snprintf(buf, sizeof(buf),
            "[ANOMALY] block size mismatch | expected=%d | got=%d",
            EXPECTED_BLOCK_SAMPLES, samples);
        hWarning(exoVoice) << buf;
    }

    // Burst / gap (uniquement si on a un push precedent)
    if (prev > 0) {
        const double dtMs = static_cast<double>(nowUs - prev) / 1000.0;
        if (dtMs < BURST_THRESHOLD_MS) {
            m_burstCount.fetch_add(1, std::memory_order_relaxed);
            flag(Anomaly::PushBurst);
            char buf[160];
            std::snprintf(buf, sizeof(buf),
                "[ANOMALY] push burst | dt=%.2f ms (< %.1f ms)",
                dtMs, BURST_THRESHOLD_MS);
            hWarning(exoVoice) << buf;
        } else if (dtMs > GAP_THRESHOLD_MS) {
            m_gapCount.fetch_add(1, std::memory_order_relaxed);
            flag(Anomaly::PushGap);
            char buf[160];
            std::snprintf(buf, sizeof(buf),
                "[ANOMALY] push gap | dt=%.2f ms (> %.1f ms)",
                dtMs, GAP_THRESHOLD_MS);
            hWarning(exoVoice) << buf;
        }
    }

    // Analyse PCM optionnelle (silence + saturation). Echantillonnage stride
    // pour rester O(samples/stride) et negligeable a 24 kHz.
    if (pcm && samples > 0) {
        const int stride = std::max(1, samples / 256);
        int zeros = 0, sats = 0, scanned = 0;
        for (int i = 0; i < samples; i += stride) {
            const int16_t s = pcm[i];
            if (s == 0) ++zeros;
            if (s == SAT_SAMPLE || s == -SAT_SAMPLE - 1) ++sats;
            ++scanned;
        }
        if (scanned > 0) {
            const double zeroRatio = static_cast<double>(zeros) / scanned;
            if (zeroRatio >= SILENCE_RATIO_LIMIT) {
                m_silenceCount.fetch_add(1, std::memory_order_relaxed);
                flag(Anomaly::SilenceBurst);
                char buf[160];
                std::snprintf(buf, sizeof(buf),
                    "[ANOMALY] silence anomaly | %.0f%% zeros",
                    zeroRatio * 100.0);
                hWarning(exoVoice) << buf;
            }
            if (sats > 0) {
                m_satCount.fetch_add(static_cast<uint64_t>(sats), std::memory_order_relaxed);
                flag(Anomaly::Saturation);
                char buf[160];
                std::snprintf(buf, sizeof(buf),
                    "[ANOMALY] amplitude saturation | sample=%d | hits=%d/%d",
                    SAT_SAMPLE, sats, scanned);
                hWarning(exoVoice) << buf;
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  POP : analyse jitter / drift / block size / underflow implicite
// ─────────────────────────────────────────────────────────────────────────────
void AudioAnomalyDetector::onPop(int samples, int ringFreeBytes)
{
    if (!m_enabled.load(std::memory_order_relaxed)) return;

    const int64_t nowUs = microsSince(m_startTp);
    const int64_t prev  = m_lastPopUs.exchange(nowUs, std::memory_order_relaxed);

    m_popCount.fetch_add(1, std::memory_order_relaxed);
    m_popSamples.fetch_add(static_cast<uint64_t>(samples), std::memory_order_relaxed);
    m_lastBlockSamples.store(samples, std::memory_order_relaxed);
    m_ringFreeBytes.store(ringFreeBytes, std::memory_order_relaxed);

    // Underflow implicite : pop a 0 sample (le ring n'a rien donne).
    if (samples <= 0) {
        m_underflowCount.fetch_add(1, std::memory_order_relaxed);
        flag(Anomaly::Underflow);
        char buf[160];
        std::snprintf(buf, sizeof(buf),
            "[ANOMALY] underflow detected | free=%d | dt=%.1f ms",
            ringFreeBytes,
            (prev > 0) ? static_cast<double>(nowUs - prev) / 1000.0 : 0.0);
        hWarning(exoVoice) << buf;
        return;
    }

    if (prev > 0) {
        const int64_t dtUs = nowUs - prev;
        m_dtPopSumUs.fetch_add(dtUs, std::memory_order_relaxed);
        m_dtPopSqSumUs2.fetch_add(dtUs * dtUs, std::memory_order_relaxed);
        m_dtPopSamples.fetch_add(1, std::memory_order_relaxed);
        atomicMinI64(m_dtPopMinUs, dtUs);
        atomicMaxI64(m_dtPopMaxUs, dtUs);

        // Drift = cumul (real - expected) sur la duree consommee.
        // expected_us = samples * 1e6 / sampleRate
        const int64_t expectedUs = static_cast<int64_t>(samples) * 1000000 / SAMPLE_RATE_HZ;
        const int64_t deltaUs    = dtUs - expectedUs;
        m_driftUs.fetch_add(deltaUs, std::memory_order_relaxed);

        const double dtMs     = dtUs / 1000.0;
        const double driftAbs = std::fabs(deltaUs / 1000.0);

        // Jitter spike (ecart pop-to-pop par rapport a l'attendu)
        if (driftAbs > JITTER_THRESHOLD_MS) {
            m_jitterSpikeCount.fetch_add(1, std::memory_order_relaxed);
            flag(Anomaly::JitterSpike);
            char buf[160];
            std::snprintf(buf, sizeof(buf),
                "[ANOMALY] jitter spike | jitter=%.2f ms | dt=%.2f ms",
                driftAbs, dtMs);
            hWarning(exoVoice) << buf;
        }

        const double absDriftCumMs =
            std::fabs(static_cast<double>(m_driftUs.load(std::memory_order_relaxed)) / 1000.0);
        if (absDriftCumMs > DRIFT_THRESHOLD_MS) {
            flag(Anomaly::DriftExcess);
            // log throttled : seul flush periodique le rapporte pour eviter le spam.
        }
    }

    // Block size pop differente du natif (peut etre legitime sur la queue de
    // phrase). On ne flag que si > 1 sample et != bloc attendu, et seulement
    // sous forme de compteur (le mismatch principal vient du push).
    if (samples != EXPECTED_BLOCK_SAMPLES && samples > 1) {
        m_blockMismatchCount.fetch_add(1, std::memory_order_relaxed);
        // pas de flag immediat : la taille pop varie selon le budget pump.
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  WRITE LATENCY (QAudioSink::write)
// ─────────────────────────────────────────────────────────────────────────────
void AudioAnomalyDetector::onBlockWritten(int64_t writeMicros)
{
    if (!m_enabled.load(std::memory_order_relaxed)) return;

    m_writeSumUs.fetch_add(writeMicros, std::memory_order_relaxed);
    m_writeSamples.fetch_add(1, std::memory_order_relaxed);
    atomicMaxI64(m_writeMaxUs, writeMicros);

    if (writeMicros > WRITE_LATENCY_LIMIT_US) {
        m_writeSlowCount.fetch_add(1, std::memory_order_relaxed);
        flag(Anomaly::WriteSlow);
        char buf[160];
        std::snprintf(buf, sizeof(buf),
            "[ANOMALY] sink write slow | %.2f ms (> %.1f ms)",
            writeMicros / 1000.0, WRITE_LATENCY_LIMIT_US / 1000.0);
        hWarning(exoVoice) << buf;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  FLUSH PERIODIQUE (toutes les 2 secondes par defaut)
// ─────────────────────────────────────────────────────────────────────────────
void AudioAnomalyDetector::maybeFlush(bool force)
{
    if (!force && !m_enabled.load(std::memory_order_relaxed)) return;

    const int64_t nowUs = microsSince(m_startTp);
    const int64_t last  = m_lastFlushUs.load(std::memory_order_relaxed);
    const int64_t intervalUs = static_cast<int64_t>(m_logIntervalMs.load(std::memory_order_relaxed)) * 1000;

    if (!force && nowUs - last < intervalUs) return;
    m_lastFlushUs.store(nowUs, std::memory_order_relaxed);
    doFlush(force);
}

void AudioAnomalyDetector::doFlush(bool /*force*/)
{
    const uint64_t pushCount = m_pushCount.load(std::memory_order_relaxed);
    const uint64_t popCount  = m_popCount.load(std::memory_order_relaxed);
    const uint64_t dtN       = m_dtPopSamples.load(std::memory_order_relaxed);
    const int64_t  dtSum     = m_dtPopSumUs.load(std::memory_order_relaxed);
    const int64_t  dtSq      = m_dtPopSqSumUs2.load(std::memory_order_relaxed);
    const int64_t  dtMin     = m_dtPopMinUs.load(std::memory_order_relaxed);
    const int64_t  dtMax     = m_dtPopMaxUs.load(std::memory_order_relaxed);
    const int64_t  drift     = m_driftUs.load(std::memory_order_relaxed);
    const uint64_t writeN    = m_writeSamples.load(std::memory_order_relaxed);
    const int64_t  writeSum  = m_writeSumUs.load(std::memory_order_relaxed);
    const int64_t  writeMax  = m_writeMaxUs.load(std::memory_order_relaxed);
    const uint32_t mask      = m_anomalyMask.exchange(0, std::memory_order_relaxed);

    const double dtAvgMs = dtN ? (static_cast<double>(dtSum) / dtN) / 1000.0 : 0.0;
    double jitterStdMs = 0.0;
    if (dtN > 1) {
        const double mean = static_cast<double>(dtSum) / dtN;
        const double var  = (static_cast<double>(dtSq) / dtN) - (mean * mean);
        jitterStdMs = (var > 0.0) ? std::sqrt(var) / 1000.0 : 0.0;
    }
    const double dtMinMs = (dtMin == INT64_MAX) ? 0.0 : dtMin / 1000.0;
    const double dtMaxMs = dtMax / 1000.0;
    const double driftMs = drift / 1000.0;
    const double wAvgMs  = writeN ? (static_cast<double>(writeSum) / writeN) / 1000.0 : 0.0;
    const double wMaxMs  = writeMax / 1000.0;

    char buf[512];
    std::snprintf(buf, sizeof(buf),
        "[AUDIO] block=%d | push=%llu pop=%llu | dt=%.1f ms (min %.1f / max %.1f) "
        "| jitter=%.2f ms | drift=%+.1f ms | free=%d B "
        "| under=%llu over=%llu burst=%llu gap=%llu sil=%llu sat=%llu jspike=%llu wslow=%llu mism=%llu "
        "| write=%.2f/%.2f ms",
        m_lastBlockSamples.load(std::memory_order_relaxed),
        static_cast<unsigned long long>(pushCount),
        static_cast<unsigned long long>(popCount),
        dtAvgMs, dtMinMs, dtMaxMs,
        jitterStdMs,
        driftMs,
        m_ringFreeBytes.load(std::memory_order_relaxed),
        static_cast<unsigned long long>(m_underflowCount.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(m_overflowCount.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(m_burstCount.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(m_gapCount.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(m_silenceCount.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(m_satCount.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(m_jitterSpikeCount.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(m_writeSlowCount.load(std::memory_order_relaxed)),
        static_cast<unsigned long long>(m_blockMismatchCount.load(std::memory_order_relaxed)),
        wAvgMs, wMaxMs);

    if (mask != 0) {
        hWarning(exoVoice) << buf << "| anomMask=0x" << QString::number(mask, 16);
    } else {
        hVoice() << buf;
    }

    // Reset des fenetres glissantes (les compteurs cumules persistent).
    m_dtPopSumUs.store(0, std::memory_order_relaxed);
    m_dtPopSqSumUs2.store(0, std::memory_order_relaxed);
    m_dtPopMinUs.store(INT64_MAX, std::memory_order_relaxed);
    m_dtPopMaxUs.store(0, std::memory_order_relaxed);
    m_dtPopSamples.store(0, std::memory_order_relaxed);
    m_writeSumUs.store(0, std::memory_order_relaxed);
    m_writeMaxUs.store(0, std::memory_order_relaxed);
    m_writeSamples.store(0, std::memory_order_relaxed);
}

void AudioAnomalyDetector::reset()
{
    m_pushCount.store(0, std::memory_order_relaxed);
    m_popCount.store(0, std::memory_order_relaxed);
    m_pushSamples.store(0, std::memory_order_relaxed);
    m_popSamples.store(0, std::memory_order_relaxed);
    m_underflowCount.store(0, std::memory_order_relaxed);
    m_overflowCount.store(0, std::memory_order_relaxed);
    m_blockMismatchCount.store(0, std::memory_order_relaxed);
    m_silenceCount.store(0, std::memory_order_relaxed);
    m_burstCount.store(0, std::memory_order_relaxed);
    m_gapCount.store(0, std::memory_order_relaxed);
    m_satCount.store(0, std::memory_order_relaxed);
    m_jitterSpikeCount.store(0, std::memory_order_relaxed);
    m_writeSlowCount.store(0, std::memory_order_relaxed);
    m_lastPushUs.store(0, std::memory_order_relaxed);
    m_lastPopUs.store(0, std::memory_order_relaxed);
    m_dtPopSumUs.store(0, std::memory_order_relaxed);
    m_dtPopSqSumUs2.store(0, std::memory_order_relaxed);
    m_dtPopMinUs.store(INT64_MAX, std::memory_order_relaxed);
    m_dtPopMaxUs.store(0, std::memory_order_relaxed);
    m_dtPopSamples.store(0, std::memory_order_relaxed);
    m_driftUs.store(0, std::memory_order_relaxed);
    m_writeSumUs.store(0, std::memory_order_relaxed);
    m_writeMaxUs.store(0, std::memory_order_relaxed);
    m_writeSamples.store(0, std::memory_order_relaxed);
    m_anomalyMask.store(0, std::memory_order_relaxed);
    m_lastFlushUs.store(microsSince(m_startTp), std::memory_order_relaxed);
}
