// ============================================================================
//  AudioAnomalyDetector.h
//  Detection temps reel d'anomalies du pipeline audio PCM16 mono 24 kHz EXO.
//
//  Cible : chunks de 960 samples (40 ms) provenant d'Orpheus, ring buffer
//  alimentant un QAudioSink en push mode (cf. TTSManager).
//
//  Anomalies detectees :
//    - underflow (pop sur buffer vide)
//    - overflow  (push tronque par le ring buffer)
//    - jitter excessif (ecart-type glissant des delta-pop)
//    - drift (cumule entre temps theorique et temps reel)
//    - block size != 960 samples
//    - silence anormal (>80% de samples = 0)
//    - burst push (plusieurs push espaces de < 10 ms)
//    - trou (>60 ms sans push pendant que le ring n'est pas vide)
//    - saturation amplitude (samples = +/- 32767)
//    - latence d'ecriture sink anormale (> 5 ms)
//
//  Concu pour le hot path audio :
//    - 100% atomique, zero mutex
//    - aucune allocation
//    - aucune dependance externe
//    - cout negligeable quand desactive (early return atomique)
// ============================================================================
#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>

class AudioAnomalyDetector {
public:
    // Format pipeline EXO / Orpheus
    static constexpr int   SAMPLE_RATE_HZ        = 24000;
    static constexpr int   EXPECTED_BLOCK_SAMPLES = 960;       // 40 ms
    static constexpr double EXPECTED_DT_MS        = 40.0;
    // Seuils anomalies
    static constexpr double JITTER_THRESHOLD_MS   = 4.0;       // > -> spike
    static constexpr double DRIFT_THRESHOLD_MS    = 40.0;      // 1 block
    static constexpr double GAP_THRESHOLD_MS      = 60.0;      // trou pop
    static constexpr double BURST_THRESHOLD_MS    = 10.0;      // burst push
    static constexpr double SILENCE_RATIO_LIMIT   = 0.80;      // 80% zeros
    static constexpr int    SAT_SAMPLE            = 32767;
    static constexpr int    WRITE_LATENCY_LIMIT_US = 5000;     // 5 ms

    AudioAnomalyDetector();

    void setEnabled(bool on)            { m_enabled.store(on, std::memory_order_relaxed); }
    bool isEnabled() const              { return m_enabled.load(std::memory_order_relaxed); }
    void setLogIntervalMs(int ms)       { m_logIntervalMs.store(ms > 0 ? ms : 2000, std::memory_order_relaxed); }

    // Hooks hot path - thread safe (SPSC + multi reader counters atomiques).
    // samples = nombre de samples Int16 mono.
    void onPush(int samples, const int16_t *pcm = nullptr);
    void onPop (int samples, int ringFreeBytes);
    void onBlockWritten(int64_t writeMicros);

    // Signalements externes (le ring buffer connait deja sa propre verite).
    void noteUnderflow()  { m_underflowCount.fetch_add(1, std::memory_order_relaxed); flag(Anomaly::Underflow); }
    void noteOverflow()   { m_overflowCount.fetch_add(1, std::memory_order_relaxed);  flag(Anomaly::Overflow);  }

    // Cycle de log (a appeler depuis la boucle pump).
    void maybeFlush(bool force = false);
    void reset();

private:
    enum class Anomaly : uint32_t {
        Underflow      = 1u << 0,
        Overflow       = 1u << 1,
        JitterSpike    = 1u << 2,
        DriftExcess    = 1u << 3,
        BlockMismatch  = 1u << 4,
        SilenceBurst   = 1u << 5,
        PushBurst      = 1u << 6,
        PushGap        = 1u << 7,
        Saturation     = 1u << 8,
        WriteSlow      = 1u << 9,
        TimestampSkew  = 1u << 10,
    };

    using clock = std::chrono::steady_clock;

    void flag(Anomaly a) { m_anomalyMask.fetch_or(static_cast<uint32_t>(a), std::memory_order_relaxed); }
    static int64_t microsSince(clock::time_point start);
    static int64_t atomicMinI64(std::atomic<int64_t> &dst, int64_t v);
    static int64_t atomicMaxI64(std::atomic<int64_t> &dst, int64_t v);
    void doFlush(bool force);

    // Configuration
    std::atomic<bool>    m_enabled{false};
    std::atomic<int>     m_logIntervalMs{2000};

    // Compteurs cumules
    std::atomic<uint64_t> m_pushCount{0};
    std::atomic<uint64_t> m_popCount{0};
    std::atomic<uint64_t> m_pushSamples{0};
    std::atomic<uint64_t> m_popSamples{0};
    std::atomic<uint64_t> m_underflowCount{0};
    std::atomic<uint64_t> m_overflowCount{0};
    std::atomic<uint64_t> m_blockMismatchCount{0};
    std::atomic<uint64_t> m_silenceCount{0};
    std::atomic<uint64_t> m_burstCount{0};
    std::atomic<uint64_t> m_gapCount{0};
    std::atomic<uint64_t> m_satCount{0};
    std::atomic<uint64_t> m_jitterSpikeCount{0};
    std::atomic<uint64_t> m_writeSlowCount{0};

    // Timing
    std::atomic<int64_t> m_lastPushUs{0};
    std::atomic<int64_t> m_lastPopUs{0};
    std::atomic<int64_t> m_dtPopSumUs{0};
    std::atomic<int64_t> m_dtPopSqSumUs2{0};   // somme des carres (jitter / std)
    std::atomic<int64_t> m_dtPopMinUs{INT64_MAX};
    std::atomic<int64_t> m_dtPopMaxUs{0};
    std::atomic<uint64_t> m_dtPopSamples{0};
    std::atomic<int64_t> m_driftUs{0};         // cumul (real - expected) entre pops
    std::atomic<int64_t> m_writeMaxUs{0};
    std::atomic<int64_t> m_writeSumUs{0};
    std::atomic<uint64_t> m_writeSamples{0};
    std::atomic<int>     m_lastBlockSamples{0};
    std::atomic<int>     m_ringFreeBytes{0};

    // Bitmask anomalies depuis dernier flush
    std::atomic<uint32_t> m_anomalyMask{0};

    clock::time_point m_startTp;
    std::atomic<int64_t> m_lastFlushUs{0};
};
