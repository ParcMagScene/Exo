#ifndef TTSMANAGER_H
#define TTSMANAGER_H

#include <QObject>
#include <QAudioSink>
#include <QAudioFormat>
#include <QAudioDevice>
#include <QMediaDevices>
#include <QWebSocket>
#include <QThread>
#include <QMutex>
#include <QQueue>
#include <QTimer>
#include <QElapsedTimer>
#include <QBuffer>
#include <QJsonObject>
#include <QJsonDocument>
#include <memory>
#include <vector>
#include <cstdint>
#include <cmath>
#include <atomic>

#include "AudioProfiler.h"
#include "AudioAnomalyDetector.h"
#include "AudioAutoCorrector.h"

// ─────────────────────────────────────────────────────
//  ProsodyProfile — pitch / rate / volume per utterance
// ─────────────────────────────────────────────────────
struct ProsodyProfile
{
    float pitch  = 0.0f;   // -1.0 … +1.0
    float rate   = 0.0f;   // -1.0 … +1.0
    float volume = 0.8f;   //  0.0 … 1.0
};

// ─────────────────────────────────────────────────────
//  TTSEqualizer — 2nd-order peak EQ (presence band)
// ─────────────────────────────────────────────────────
class TTSEqualizer
{
public:
    void configure(int sampleRate, float centerHz = 3000.0f,
                   float gainDb = 3.0f, float q = 1.0f);
    void process(float *samples, int count);
    void reset();

private:
    double m_b0=1, m_b1=0, m_b2=0, m_a1=0, m_a2=0;
    double m_x1=0, m_x2=0, m_y1=0, m_y2=0;
};

// ─────────────────────────────────────────────────────
//  TTSCompressor — soft-knee downward compressor
// ─────────────────────────────────────────────────────
class TTSCompressor
{
public:
    void configure(int sampleRate, float thresholdDb = -18.0f,
                   float ratio = 2.0f, float attackMs = 5.0f,
                   float releaseMs = 50.0f);
    void process(float *samples, int count);
    void reset();

private:
    float m_threshold = -18.0f;
    float m_ratio     = 2.0f;
    float m_attack    = 0.0f;   // coefficient
    float m_release   = 0.0f;   // coefficient
    float m_envelope  = 0.0f;
};

// ─────────────────────────────────────────────────────
//  TTSNormalizer — peak / RMS normalization
// ─────────────────────────────────────────────────────
class TTSNormalizer
{
public:
    void setTargetDb(float dBFS) { m_targetDb = dBFS; }
    void process(float *samples, int count);
    void reset() { m_currentGain = -1.0f; }

private:
    float m_targetDb = -14.0f;
    float m_currentGain = -1.0f;  // <0 means uninitialised
};

// ─────────────────────────────────────────────────────
//  TTSFade — fade-in / fade-out anti-click
// ─────────────────────────────────────────────────────
class TTSFade
{
public:
    void configure(int sampleRate, float fadeInMs = 5.0f,
                   float fadeOutMs = 10.0f);
    void applyFadeIn(float *samples, int count);
    void applyFadeOut(float *samples, int count);

private:
    int m_fadeInSamples  = 80;
    int m_fadeOutSamples = 160;
};

// ─────────────────────────────────────────────────────
//  TTSDSPProcessor — modular DSP chain
//
//  Pipeline : EQ → Compressor → Normalizer → Fade
//  Operates on float buffer (normalized -1..+1)
// ─────────────────────────────────────────────────────
class TTSDSPProcessor
{
public:
    void configure(int sampleRate);
    void process(int16_t *pcm, int count, bool isFinalChunk = false);
    void reset();
    void resetNorm() { m_norm.reset(); }

    void setEnabled(bool on)       { m_enabled = on; }
    bool isEnabled() const         { return m_enabled; }
    void setEQGainDb(float db);
    void setCompressorThreshold(float db);
    void setNormTarget(float dBFS);

    // v26.1 Latency: pre-allocate float buffer to avoid first-chunk heap alloc
    void preAllocate(int samples) { if (static_cast<int>(m_fbuf.size()) < samples) m_fbuf.resize(samples); }

private:
    bool m_enabled = true;
    int  m_sampleRate = 16000;

    TTSEqualizer   m_eq;
    TTSCompressor  m_comp;
    TTSNormalizer  m_norm;
    TTSFade        m_fade;
    bool m_firstChunk = true;
    std::vector<float> m_fbuf;  // reusable float buffer to avoid per-chunk allocation
};

// ─────────────────────────────────────────────────────
//  PCMRingBuffer — SPSC lock-free PCM16 ring buffer
//
//  - capacite arrondie a la puissance de 2 superieure (mask au lieu de modulo)
//  - indices atomiques (single-producer / single-consumer safe)
//  - API legacy byte-based (write / read / availableRead) preservee
//  - API native PCM16 (pushSamples / popBlock) :
//      * push : drop controle si overflow + log
//      * popBlock : retourne TOUJOURS un bloc complet,
//                   silence-fill si underflow (zero craquement)
// ─────────────────────────────────────────────────────
class PCMRingBuffer
{
public:
    explicit PCMRingBuffer(int capacityBytes = 1048576); // ~5.4s @ 48kHz stereo 16bit (POT)

    // ── Legacy byte-based API (utilisee par feedRingBuffer / pumpBuffer) ──
    int  write(const char *data, int size);          // bytes ; renvoie ce qui a ete ecrit
    int  read(char *data, int maxSize);              // bytes ; renvoie ce qui a ete lu
    int  availableRead()  const;                     // bytes
    int  availableWrite() const;                     // bytes
    bool isEmpty()        const { return availableRead() == 0; }
    void clear();

    // ── PCM16 native API (anti-craquements) ──
    /// Push N samples int16. Renvoie le nombre reellement ecrit.
    /// N'ecrase JAMAIS la zone non lue ; surplus = drop + log.
    int  pushSamples(const int16_t *samples, int count);
    /// Pop EXACTEMENT count samples. Si underflow : silence-fill + log.
    /// Renvoie toujours count.
    int  popBlock(int16_t *out, int count);
    /// Avance le readPos sans copier (drain controle).
    void dropSamples(int count);

    /// Apply cosine fade-out to the last fadeBytes of buffered data
    void fadeOutTail(int fadeBytes);

    int  capacityBytes() const { return m_capacity; }

private:
    static int roundUpPow2(int v);

    std::vector<char> m_buf;
    int m_capacity = 0;   // power of 2, bytes
    int m_mask     = 0;   // m_capacity - 1
    // SPSC : indices monotoniques en bytes. Producer ecrit head, consumer ecrit tail.
    alignas(64) std::atomic<int> m_head{0};
    alignas(64) std::atomic<int> m_tail{0};
};

// ─────────────────────────────────────────────────────
//  TTSRequest — queued item
// ─────────────────────────────────────────────────────
struct TTSRequest
{
    QString text;
    ProsodyProfile prosody;
    int retries = 0;
};

class TTSBackend;
#ifdef ENABLE_RTAUDIO
class TTSAudioSinkRtAudio;
#endif
class TTSBackendQt;
#ifdef ENABLE_XTTS
class TTSBackendXTTS;
#endif

// ─────────────────────────────────────────────────────
//  TTSWorker — runs on dedicated QThread
//
//  Iterates registered TTSBackend instances in priority
//  order (XTTS first, Qt TTS fallback).
//  Emits chunks of PCM16 data for streaming playback.
// ─────────────────────────────────────────────────────
class TTSWorker : public QObject
{
    Q_OBJECT
public:
    explicit TTSWorker(QObject *parent = nullptr);
    ~TTSWorker();

public slots:
    void init(const QString &pythonWsUrl = {});
    void processRequest(const TTSRequest &req);
    void cancelCurrent();
    void setVoice(const QString &name);
    void setPythonWsUrl(const QString &url);
#ifdef ENABLE_XTTS
    void setXTTSVoice(const QString &name);
    void setXTTSLang(const QString &lang);
#endif
    void warmConnect();

signals:
    void started(const QString &text);
    void chunk(const QByteArray &pcm);
    void finished();
    void error(const QString &msg);
    void voiceInfo(const QString &name, int voiceCount);

public:
    void requestStop() { m_cancelled = true; }
    void resetPythonConnection();

private:
    QList<TTSBackend *> m_backends;
    TTSBackendQt   *m_qtBackend   = nullptr;
#ifdef ENABLE_XTTS
    TTSBackendXTTS *m_xttsBackend = nullptr;
#endif
    alignas(64) std::atomic<bool> m_cancelled{false};

    static constexpr int MAX_RETRIES = 2;
};

// ─────────────────────────────────────────────────────
//  TTSManager — public-facing TTS orchestrator
//
//  • Prosody analysis (question / exclamation / context)
//  • Queue management  (cancel-on-new, drain)
//  • DSP post-processing
//  • Streaming playback via QAudioSink
//  • WebSocket broadcast (waveform + state) to React GUI
//
//  Thread layout :
//    main thread  → TTSManager (queue, prosody, DSP, sink)
//        ↓ signal
//    worker thread → TTSWorker  (Qt TTS + Python backend)
// ─────────────────────────────────────────────────────
class TTSManager : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool isSpeaking READ isSpeaking NOTIFY speakingChanged)
    Q_PROPERTY(QStringList ttsVoices READ ttsVoices NOTIFY ttsVoicesChanged)

public:
    explicit TTSManager(QObject *parent = nullptr);
    ~TTSManager();

    // ── lifecycle ──
    void initTTS(const QString &pythonWsUrl = {});
    void initDSP();

    // ── main API ──
    Q_INVOKABLE void speakText(const QString &text);
    Q_INVOKABLE void enqueueSentence(const QString &text);
    Q_INVOKABLE void cancelSpeech();
    void prepareNext();

    // ── state ──
    bool isSpeaking() const { return m_speaking; }

    // ── tuning ──
    Q_INVOKABLE void setVoice(const QString &name);
    Q_INVOKABLE void setRate(float r);
    Q_INVOKABLE void setPitch(float p);
    Q_INVOKABLE void setEnergy(float e);
    Q_INVOKABLE void setStyle(const QString &s);
    Q_INVOKABLE void setLanguage(const QString &lang);
    Q_INVOKABLE void setDSPEnabled(bool on);
    Q_INVOKABLE void setAudioProfilingEnabled(bool on) { m_audioProfiler.setEnabled(on); }
    Q_INVOKABLE void setAudioProfilingIntervalMs(int ms) { m_audioProfiler.setLogIntervalMs(ms); }
    Q_INVOKABLE void setAudioAnomalyDetectionEnabled(bool on) { m_audioAnomalies.setEnabled(on); m_enableAudioAnomalyDetection = on; }
    Q_INVOKABLE void setAudioAnomalyDetectionIntervalMs(int ms) { m_audioAnomalies.setLogIntervalMs(ms); }
    Q_INVOKABLE void setAudioAutoCorrectionEnabled(bool on) { m_audioAutoCorrector.setEnabled(on); m_enableAudioAutoCorrection = on; }
    Q_INVOKABLE void setAudioAutoCorrectionVerbose(bool on) { m_audioAutoCorrector.setVerbose(on); }
    Q_INVOKABLE void setCascadeEnabled(bool on);
    Q_INVOKABLE void setPythonUrl(const QString &url);
    Q_INVOKABLE void setOutputDevicePreference(const QString &deviceName);
    Q_INVOKABLE void fetchAvailableVoices();
    QStringList ttsVoices() const { return m_ttsVoices; }

    // ── WebSocket bridge (for React GUI) ──
    void setWebSocket(QWebSocket *ws);

    // ── elapsed since last speech ended (for guard timing) ──
    qint64 msSinceLastSpeech() const;

signals:
    void ttsStarted();
    void ttsChunk(const QByteArray &pcm);
    void ttsPcmForVisualization(const QVariantList &samples);
    void ttsFinished();
    void speakingChanged();
    void ttsError(const QString &msg);
    void statusChanged(const QString &status);
    void ttsVoicesChanged();

    // internal → worker thread
    void _doRequest(const TTSRequest &req);
    void _doCancelWorker();

private slots:
    void onWorkerStarted(const QString &text);
    void onWorkerChunk(const QByteArray &pcm);
    void onWorkerFinished();
    void onWorkerError(const QString &msg);
    void processQueue();

private:
    // ── prosody ──
    ProsodyProfile analyzeProsody(const QString &text) const;
    QString preprocessText(const QString &raw) const;

    // ── streaming playback — persistent sink + ring buffer ──
    void ensureSinkReady();
    void feedRingBuffer(const QByteArray &pcm);
    void pumpBuffer();
    void destroySink();
    void finalizeSpeech();
    void onSinkStateChanged(QAudio::State state);
#ifdef ENABLE_RTAUDIO
    // Flush du staging RtAudio + start du stream. Appele soit quand le
    // seuil prebuffer est atteint, soit quand worker termine.
    void flushRtPrebuffer(const char *reason);
#endif
    void broadcastWaveform(const QByteArray &pcm);
    void broadcastState(const QString &state);
    QByteArray adaptForOutputFormat(const QByteArray &pcm);
    int outputBytesPerSecond() const;
    void resetResamplerState();

    // ── streaming linear resampler state (24 kHz mono -> device format) ──
    // Persistant entre chunks pour eviter une discontinuite a chaque
    // frontiere de 40 ms (cause de craquements periodiques ~25 Hz).
    double  m_resampleSrcPos    = 0.0;   // position fractionnaire dans le flux source
    int16_t m_resampleLastSample = 0;    // dernier sample du chunk source precedent
    bool    m_resampleHasHistory = false;

    // ── state ──
    // alignas(64): evite false-sharing avec PCMRingBuffer indices (callback RtAudio temps-reel)
    alignas(64) std::atomic<bool> m_speaking{false};
    alignas(64) std::atomic<bool> m_processingGuard{false}; // prevents re-entrant processQueue
    bool m_synthesizing = false;  // true while worker is producing chunks for current phrase
    bool m_turnActive   = false;  // true while a speech turn is ongoing (spans chained phrases)
    bool m_cascadeEnabled = true;
    float m_baseRate   = 0.0f;
    float m_basePitch  = 0.0f;
    float m_baseEnergy = 0.8f;
    QString m_baseStyle = "neutral";
    QString m_voiceName = "exo_default";
    QString m_language  = "fr";

    // ── queue ──
    QMutex m_queueMutex;
    QQueue<TTSRequest> m_queue;

    // ── DSP ──
    TTSDSPProcessor m_dsp;

    // ── audio output — persistent sink + ring buffer ──
    QAudioFormat m_sinkFormat;
    QAudioFormat m_deviceFormat;
    std::unique_ptr<QAudioSink> m_sink;
    QIODevice *m_sinkIO = nullptr;
    QIODevice *m_pullDevice = nullptr; // RingPullDevice (mode PULL anti-craquements)
    PCMRingBuffer m_ringBuffer;       // circular PCM buffer between TTS and sink
    QTimer    *m_pumpTimer = nullptr; // feeds sink from ring buffer
    bool       m_useRtAudioSink = false; // true si TTSAudioSinkRtAudio actif (bypasse pump+QAudioSink)
#ifdef ENABLE_RTAUDIO
    std::unique_ptr<TTSAudioSinkRtAudio> m_rtSink;
    QByteArray m_rtPrebufStage;          // accumulateur pre-flush vers ring (anti-click debut de phrase)
    bool       m_rtNeedsPrebuf = true;   // true entre 2 phrases : mode staging actif
    bool       m_sinkWarmedUp = false;   // false jusqu'au 1er flush de la session : injecte 200 ms de silence
                                         // pour absorber le warmup WASAPI (sinon 1re syllabe coupee)
#endif
    qint64     m_totalPcmBytes = 0;   // diagnostic counter
    AudioProfiler m_audioProfiler;    // real-time audio profiling (opt-in)
    AudioAnomalyDetector m_audioAnomalies; // detection automatique d'anomalies audio
    bool          m_enableAudioAnomalyDetection = true; // mode debug par defaut
    AudioAutoCorrector m_audioAutoCorrector;       // auto-correction temps reel (Phase 10)
    bool          m_enableAudioAutoCorrection = false; // OFF: silence-fill cause des clics audio

    // ── worker thread ──
    QThread      m_workerThread;
    TTSWorker   *m_worker = nullptr;

    // ── timers ──
    QElapsedTimer m_lastSpeechEnd;
    QElapsedTimer m_speakRequestTime;
    bool m_firstChunkReceived = false;
    bool m_firstAudioPumped = false;  // v8.1: first audio written to sink

    // ── anti-jitter (v27) ──
    std::vector<char> m_pumpBuf;       // pre-allocated pump staging buffer
    QElapsedTimer m_pumpClock;         // monotonic clock for timestamp correction
    qint64 m_pumpEpochNs = 0;         // audio stream start timestamp (ns)
    qint64 m_pumpBytesSent = 0;       // cumulative bytes pumped since epoch

    // ── WebSocket ──
    QWebSocket *m_ws = nullptr;
    QStringList m_ttsVoices;
    QString m_ttsServerUrl;
    QTimer *m_voiceRefreshTimer = nullptr;
    bool m_voiceFetchInFlight = false;
    QString m_outputDevicePreference;

    // ── constants ──
    static constexpr int SAMPLE_RATE     = 24000; // Orpheus native rate (24 kHz)
    static constexpr int CHANNELS        = 1;
    static constexpr int BITS_PER_SAMPLE = 16;
    static constexpr int PUMP_INTERVAL_MS = 5;    // v27: reduced from 10ms
    static constexpr int PUMP_BUF_SIZE   = 4096;  // pre-allocated pump staging buffer
    static constexpr int SINK_BUFFER_SIZE = 8192; // ~170ms @ 24kHz mono16
};

#endif // TTSMANAGER_H
