// ============================================================================
//  AudioAutoCorrector.h
//  Auto-correction temps reel des anomalies du pipeline audio PCM16 mono
//  24 kHz d'EXO (Orpheus -> ring buffer -> QAudioSink push mode).
//
//  Cooperateur direct de AudioAnomalyDetector et de PCMRingBuffer :
//    - normalise les blocs entrants (taille multiple de 960 samples)
//    - applique un soft-clip sur la saturation (+/- 32767)
//    - corrige l'overflow en draine controle d'un bloc (drop oldest)
//    - corrige l'underflow par injection d'un bloc de silence (960 samples)
//    - injecte un silence proactif sur trou push > 60 ms
//    - tracke la derive cumulative et propose un ajustement de pacing
//
//  Hot path safe :
//    - 100% atomique, zero mutex
//    - aucune allocation dynamique
//    - aucune dependance externe (Qt + STL)
//    - desactivable a chaud (early return)
// ============================================================================
#pragma once

#include <QByteArray>
#include <atomic>
#include <chrono>
#include <cstdint>

class PCMRingBuffer;
class AudioAnomalyDetector;

class AudioAutoCorrector {
public:
    // Constantes pipeline EXO / Orpheus
    static constexpr int   SAMPLE_RATE_HZ      = 24000;
    static constexpr int   EXPECTED_SAMPLES    = 960;          // 40 ms
    static constexpr int   EXPECTED_BYTES      = EXPECTED_SAMPLES * 2;
    static constexpr double EXPECTED_DT_MS     = 40.0;
    static constexpr int   GAP_THRESHOLD_MS    = 60;           // trou push
    static constexpr int   BURST_THRESHOLD_MS  = 10;           // burst push
    static constexpr int   SOFTCLIP_THRESHOLD  = 32500;        // pre-clip
    static constexpr int   SOFTCLIP_LIMIT      = 32700;        // hard cap
    static constexpr double DRIFT_LIMIT_US     = 4000.0;       // +/- 4 ms

    AudioAutoCorrector();
    ~AudioAutoCorrector() = default;

    // Cablage (appele une fois apres construction TTSManager).
    void attach(PCMRingBuffer *ring, AudioAnomalyDetector *detector);

    // Activation
    void setEnabled(bool on)    { m_enabled.store(on, std::memory_order_relaxed); }
    bool isEnabled() const      { return m_enabled.load(std::memory_order_relaxed); }
    void setVerbose(bool on)    { m_verbose.store(on, std::memory_order_relaxed); }

    // ========================================================================
    //  Hooks producteur (thread WS / TTS)
    // ========================================================================

    /// Pre-traite un chunk PCM16 AVANT ecriture dans le ring :
    ///   - aligne la taille sur 2 octets (drop d'un octet residuel)
    ///   - normalise sur multiple de 960 samples (drop du mini-bloc terminal)
    ///   - applique un soft-clip sur la saturation +/- 32767
    ///   - injecte un silence proactif si trou > 60 ms depuis le dernier push
    /// Modifie pcm en place. Retourne le nombre de samples corriges (clipped).
    int onPush(QByteArray &pcm);

    /// Appele APRES m_ringBuffer.write(). Si requested > written :
    ///   - drop un bloc de tete pour faire de la place
    ///   - log [AUTOFIX] overflow -> dropped N samples
    void afterRingWrite(int requestedBytes, int writtenBytes);

    // ========================================================================
    //  Hooks consommateur (thread pump audio QTimer)
    // ========================================================================

    /// Appele AVANT m_sinkIO->write(). Si actualBytes < wantedBytes (underflow),
    /// remplit la queue de buffer avec un silence propre (zero absolu) pour
    /// preserver la cadence 40 ms vers QAudioSink. Retourne le nb d'octets
    /// effectivement disponibles a ecrire (toujours pair, multiple de 2).
    int onPop(char *buffer, int actualBytes, int wantedBytes, int ringFreeBytes);

    /// Appele APRES m_sinkIO->write() avec la latence mesuree (us).
    /// Met a jour la derive cumulative et propose un ajustement de pacing.
    void onBlockWritten(int64_t writeMicros);

    /// Suggestion d'ajustement du deadline pump en microsecondes (-1000..+1000).
    /// 0 si pas de derive significative.
    int64_t suggestPacingAdjustmentUs();

    // ========================================================================
    //  Etat / reset
    // ========================================================================
    void reset();

    // Compteurs (lecture multi-thread safe)
    uint64_t silenceInjections() const   { return m_silenceInjections.load(std::memory_order_relaxed); }
    uint64_t overflowDrops()     const   { return m_overflowDrops.load(std::memory_order_relaxed); }
    uint64_t softClippedSamples() const  { return m_softClipped.load(std::memory_order_relaxed); }
    uint64_t blockNormalizations() const { return m_blockNormalized.load(std::memory_order_relaxed); }
    uint64_t gapInjections() const       { return m_gapInjections.load(std::memory_order_relaxed); }
    uint64_t pacingAdjustments() const   { return m_pacingAdjustments.load(std::memory_order_relaxed); }

private:
    using clock = std::chrono::steady_clock;

    // Cablage externe (non possede)
    PCMRingBuffer        *m_ring     = nullptr;
    AudioAnomalyDetector *m_detector = nullptr;

    // Activation
    std::atomic<bool>     m_enabled{true};
    std::atomic<bool>     m_verbose{true};

    // Tracking timing producteur / consommateur
    std::atomic<int64_t>  m_lastPushTickUs{0};
    std::atomic<int64_t>  m_lastPopTickUs{0};
    std::atomic<int64_t>  m_driftCumulUs{0};

    // Compteurs
    std::atomic<uint64_t> m_silenceInjections{0};
    std::atomic<uint64_t> m_overflowDrops{0};
    std::atomic<uint64_t> m_softClipped{0};
    std::atomic<uint64_t> m_blockNormalized{0};
    std::atomic<uint64_t> m_gapInjections{0};
    std::atomic<uint64_t> m_pacingAdjustments{0};

    // Helpers internes
    int64_t nowUs() const;
    int  applySoftClip(int16_t *samples, int count);
    void injectSilenceIntoRing(int samples, const char *reason);
};
