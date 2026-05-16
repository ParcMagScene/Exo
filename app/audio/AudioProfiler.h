#ifndef EXO_AUDIO_PROFILER_H
#define EXO_AUDIO_PROFILER_H

#include <atomic>
#include <chrono>
#include <cstdint>

// ─────────────────────────────────────────────────────
//  AudioProfiler — real-time PCM16 24 kHz mono profiling
//
//  Lock-free instrumentation (atomics only, pas de mutex).
//  Hooks :
//    - onPush(samples)    : a chaque chunk recu du WS / ecrit dans le ring
//    - onPop(samples)     : a chaque bloc consomme par le pump vers le sink
//    - onAudioWrite(usec) : duree reelle d'ecriture vers QAudioSink
//    - setRingFree(b)     : taille libre courante du ring (bytes)
//    - noteUnderflow / noteOverflow / noteAnomaly
//
//  Cadence des stats : log toutes les `intervalMs` ms (defaut 2000),
//  + log immediat si une anomalie est notee depuis le dernier flush.
// ─────────────────────────────────────────────────────
class AudioProfiler
{
public:
    using clock = std::chrono::steady_clock;

    static constexpr int    EXPECTED_BLOCK_SAMPLES = 960;     // 40 ms @ 24kHz
    static constexpr double EXPECTED_DT_MS         = 40.0;

    AudioProfiler();

    void setEnabled(bool on)            { m_enabled.store(on, std::memory_order_relaxed); }
    bool isEnabled() const              { return m_enabled.load(std::memory_order_relaxed); }
    void setLogIntervalMs(int ms)       { m_logIntervalMs.store(ms <= 0 ? 2000 : ms, std::memory_order_relaxed); }

    // Hooks (lock-free, hot path)
    void onPush(int samples);
    void onPop(int samples, int blockBytes /*reellement consomme*/);
    void onAudioWrite(int64_t writeMicros);
    void setRingFreeBytes(int bytes)    { m_ringFreeBytes.store(bytes, std::memory_order_relaxed); }
    void noteUnderflow()                { m_underflowCount.fetch_add(1, std::memory_order_relaxed); m_dirty.store(true); }
    void noteOverflow()                 { m_overflowCount.fetch_add(1, std::memory_order_relaxed); m_dirty.store(true); }
    void noteAnomaly()                  { m_anomalyCount.fetch_add(1, std::memory_order_relaxed); m_dirty.store(true); }

    // Periodic flush (call from a QTimer ou depuis pumpBuffer ; thread-safe).
    // Force=true pour forcer un dump (anomalie).
    void maybeFlush(bool force = false);

    void reset();

private:
    void doFlush(bool anomaly);

    std::atomic<bool>    m_enabled{false};
    std::atomic<int>     m_logIntervalMs{2000};

    // Counters
    std::atomic<uint64_t> m_pushCount{0};
    std::atomic<uint64_t> m_popCount{0};
    std::atomic<uint64_t> m_pushSamples{0};
    std::atomic<uint64_t> m_popSamples{0};
    std::atomic<uint64_t> m_underflowCount{0};
    std::atomic<uint64_t> m_overflowCount{0};
    std::atomic<uint64_t> m_anomalyCount{0};
    std::atomic<int>      m_ringFreeBytes{0};

    // Pop dt / jitter (en us)
    std::atomic<int64_t>  m_lastPopUs{0};       // timestamp dernier pop (us depuis start)
    std::atomic<int64_t>  m_dtSumUs{0};
    std::atomic<int64_t>  m_dtMinUs{INT64_MAX};
    std::atomic<int64_t>  m_dtMaxUs{0};
    std::atomic<uint64_t> m_dtSamples{0};
    std::atomic<int64_t>  m_jitterSumUs{0};     // sum |dt - expected|
    std::atomic<int64_t>  m_jitterMaxUs{0};
    std::atomic<int64_t>  m_driftUs{0};         // somme cumulee (dt - expected)

    // Push dt
    std::atomic<int64_t>  m_lastPushUs{0};
    std::atomic<int64_t>  m_pushDtSumUs{0};
    std::atomic<uint64_t> m_pushDtSamples{0};

    // Sink write
    std::atomic<int64_t>  m_writeMaxUs{0};
    std::atomic<int64_t>  m_writeSumUs{0};
    std::atomic<uint64_t> m_writeSamples{0};

    // Bloc anormal (taille != EXPECTED_BLOCK_SAMPLES)
    std::atomic<int>      m_lastBlockSamples{0};

    // Flush bookkeeping
    clock::time_point     m_startTp;
    std::atomic<int64_t>  m_lastFlushUs{0};
    std::atomic<bool>     m_dirty{false};       // anomalie depuis dernier flush
};

#endif // EXO_AUDIO_PROFILER_H
