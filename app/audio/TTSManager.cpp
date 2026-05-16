#include "TTSManager.h"
#ifdef ENABLE_RTAUDIO
#include "TTSAudioSinkRtAudio.h"
#endif
#include "TTSBackend.h"
#include "TTSBackendQt.h"
#ifdef ENABLE_XTTS
#include "TTSBackendXTTS.h"
#endif
#include "core/LogManager.h"
#include "core/PipelineEvent.h"
#include "core/LatencyMetrics.h"
#include "core/MetricsManager.h"
#include "core/TraceManager.h"

#include <QCoreApplication>
#include <QJsonObject>
#include <QJsonDocument>
#include <QFile>
#include <QSet>
#include <QtEndian>
#include <algorithm>
#include <cstring>
#include <cmath>
#include <chrono>

// ═══════════════════════════════════════════════════════
//  RingPullDevice — QIODevice qui sert le PCM en mode PULL
//  Qt appelle readData() quand IL le decide, basculement
//  push -> pull elimine les craquements WASAPI lies au timer
//  Windows imprecis (CoarseTimer, scheduling 15-40 ms).
// ═══════════════════════════════════════════════════════
class RingPullDevice : public QIODevice
{
public:
    explicit RingPullDevice(PCMRingBuffer *ring, QObject *parent = nullptr)
        : QIODevice(parent), m_ring(ring) {}

    bool isSequential() const override { return true; }
    qint64 bytesAvailable() const override
    {
        // Toujours dispo : si le ring est vide on remplit de silence.
        // 1 MB virtuel suffit a satisfaire Qt sans declencher EOF.
        return 1 << 20;
    }

protected:
    qint64 readData(char *data, qint64 maxSize) override
    {
        if (!m_ring || maxSize <= 0) return 0;
        const int got = m_ring->read(data, static_cast<int>(maxSize));
        if (got < static_cast<int>(maxSize)) {
            // Silence-fill -> Qt ne stoppe jamais le sink, zero glitch.
            std::memset(data + got, 0, static_cast<size_t>(maxSize - got));
        }
        return maxSize;
    }
    qint64 writeData(const char *, qint64 len) override { return len; }

private:
    PCMRingBuffer *m_ring = nullptr;
};

// ═══════════════════════════════════════════════════════
//  TTSEqualizer — 2nd-order peaking EQ (presence band)
// ═══════════════════════════════════════════════════════

void TTSEqualizer::configure(int sampleRate, float centerHz,
                              float gainDb, float q)
{
    // Peaking EQ via Audio-EQ-Cookbook (Robert Bristow-Johnson)
    const double pi = 3.14159265358979323846;
    double w0 = 2.0 * pi * centerHz / sampleRate;
    double A  = std::pow(10.0, gainDb / 40.0);
    double alpha = std::sin(w0) / (2.0 * q);

    double b0 =  1.0 + alpha * A;
    double b1 = -2.0 * std::cos(w0);
    double b2 =  1.0 - alpha * A;
    double a0 =  1.0 + alpha / A;
    double a1 = -2.0 * std::cos(w0);
    double a2 =  1.0 - alpha / A;

    // Normalise so a0 == 1
    m_b0 = b0 / a0;
    m_b1 = b1 / a0;
    m_b2 = b2 / a0;
    m_a1 = a1 / a0;
    m_a2 = a2 / a0;

    reset();
}

void TTSEqualizer::process(float *samples, int count)
{
    for (int i = 0; i < count; ++i) {
        double x0 = samples[i];
        double y0 = m_b0 * x0 + m_b1 * m_x1 + m_b2 * m_x2
                   - m_a1 * m_y1 - m_a2 * m_y2;
        m_x2 = m_x1; m_x1 = x0;
        m_y2 = m_y1; m_y1 = y0;
        samples[i] = static_cast<float>(y0);
    }
}

void TTSEqualizer::reset()
{
    m_x1 = m_x2 = m_y1 = m_y2 = 0.0;
}

// ═══════════════════════════════════════════════════════
//  TTSCompressor — soft-knee downward compressor
// ═══════════════════════════════════════════════════════

void TTSCompressor::configure(int sampleRate, float thresholdDb,
                               float ratio, float attackMs,
                               float releaseMs)
{
    m_threshold = thresholdDb;
    m_ratio     = ratio;
    // Attack / release as one-pole coefficients
    m_attack  = 1.0f - std::exp(-1.0f / (sampleRate * attackMs / 1000.0f));
    m_release = 1.0f - std::exp(-1.0f / (sampleRate * releaseMs / 1000.0f));
    reset();
}

void TTSCompressor::process(float *samples, int count)
{
    float threshLin = std::pow(10.0f, m_threshold / 20.0f);

    for (int i = 0; i < count; ++i) {
        float absVal = std::fabs(samples[i]);

        // Smooth envelope follower
        float coeff = (absVal > m_envelope) ? m_attack : m_release;
        m_envelope += coeff * (absVal - m_envelope);

        if (m_envelope > threshLin) {
            float envDb   = 20.0f * std::log10(m_envelope + 1e-12f);
            float overDb  = envDb - m_threshold;
            float gainDb  = overDb - overDb / m_ratio;
            float gainLin = std::pow(10.0f, -gainDb / 20.0f);
            samples[i] *= gainLin;
        }
    }
}

void TTSCompressor::reset()
{
    m_envelope = 0.0f;
}

// ═══════════════════════════════════════════════════════
//  TTSNormalizer — peak normalization to target dBFS
// ═══════════════════════════════════════════════════════

void TTSNormalizer::process(float *samples, int count)
{
    if (count <= 0) return;

    // Find peak
    float peak = 0.0f;
    for (int i = 0; i < count; ++i)
        peak = std::max(peak, std::fabs(samples[i]));

    if (peak < 1e-6f) return; // silence

    float targetLin = std::pow(10.0f, m_targetDb / 20.0f);
    float desiredGain = targetLin / peak;
    // Don't amplify more than 20 dB
    desiredGain = std::min(desiredGain, 10.0f);

    // Smooth gain across chunks — slow convergence to prevent pumping
    if (m_currentGain < 0.0f) {
        m_currentGain = desiredGain;       // first chunk: apply directly
    } else {
        constexpr float kSmooth = 0.05f;   // very slow convergence to avoid volume trembling
        m_currentGain += kSmooth * (desiredGain - m_currentGain);
    }

    for (int i = 0; i < count; ++i)
        samples[i] *= m_currentGain;
}

// ═══════════════════════════════════════════════════════
//  TTSFade — anti-click fade-in / fade-out
// ═══════════════════════════════════════════════════════

void TTSFade::configure(int sampleRate, float fadeInMs, float fadeOutMs)
{
    m_fadeInSamples  = static_cast<int>(sampleRate * fadeInMs / 1000.0f);
    m_fadeOutSamples = static_cast<int>(sampleRate * fadeOutMs / 1000.0f);
    if (m_fadeInSamples  < 1) m_fadeInSamples  = 1;
    if (m_fadeOutSamples < 1) m_fadeOutSamples = 1;
}

void TTSFade::applyFadeIn(float *samples, int count)
{
    int n = std::min(count, m_fadeInSamples);
    for (int i = 0; i < n; ++i) {
        float t = static_cast<float>(i) / static_cast<float>(m_fadeInSamples);
        // Raised-cosine fade (smoother than linear)
        float gain = 0.5f * (1.0f - std::cos(3.14159265f * t));
        samples[i] *= gain;
    }
}

void TTSFade::applyFadeOut(float *samples, int count)
{
    int n = std::min(count, m_fadeOutSamples);
    int offset = count - n;
    for (int i = 0; i < n; ++i) {
        float t = static_cast<float>(i) / static_cast<float>(m_fadeOutSamples);
        float gain = 0.5f * (1.0f + std::cos(3.14159265f * t));
        samples[offset + i] *= gain;
    }
}

// ═══════════════════════════════════════════════════════
//  TTSDSPProcessor — modular DSP pipeline
//  EQ → Compressor → Normalizer → Fade → Anti-clip
// ═══════════════════════════════════════════════════════

void TTSDSPProcessor::configure(int sampleRate)
{
    m_sampleRate = sampleRate;
    // XTTS v2 produces well-normalized audio — very light DSP
    m_eq.configure(sampleRate, 3000.0f, 0.5f, 1.0f);  // subtle presence boost
    m_comp.configure(sampleRate, -20.0f, 1.4f, 15.0f, 100.0f); // gentle compression
    m_norm.setTargetDb(-16.0f);
    m_fade.configure(sampleRate, 15.0f, 20.0f); // longer fades for neural TTS
    m_firstChunk = true;
}

void TTSDSPProcessor::process(int16_t *pcm, int count, bool isFinalChunk)
{
    if (!m_enabled || count <= 0) return;

    // Reuse float buffer to avoid per-chunk heap allocation
    if (static_cast<int>(m_fbuf.size()) < count)
        m_fbuf.resize(count);

    // Convert int16 → float [-1, +1]
    for (int i = 0; i < count; ++i)
        m_fbuf[i] = pcm[i] / 32768.0f;

    // 1. Presence EQ (2-4 kHz boost)
    m_eq.process(m_fbuf.data(), count);

    // 2. Compressor — sole gain stage (normalizer disabled: causes volume jumps)
    m_comp.process(m_fbuf.data(), count);

    // 4. Fade
    if (m_firstChunk) {
        m_fade.applyFadeIn(m_fbuf.data(), count);
        m_firstChunk = false;
    }
    if (isFinalChunk)
        m_fade.applyFadeOut(m_fbuf.data(), count);

    // 5. Anti-clipping (hard limiter at ±1.0)
    for (int i = 0; i < count; ++i)
        m_fbuf[i] = std::clamp(m_fbuf[i], -1.0f, 1.0f);

    // Convert float → int16
    for (int i = 0; i < count; ++i)
        pcm[i] = static_cast<int16_t>(m_fbuf[i] * 32767.0f);
}

void TTSDSPProcessor::reset()
{
    m_eq.reset();
    m_comp.reset();
    m_norm.reset();
    m_firstChunk = true;
}

void TTSDSPProcessor::setEQGainDb(float db)
{
    m_eq.configure(m_sampleRate, 3000.0f, db, 1.0f);
}

void TTSDSPProcessor::setCompressorThreshold(float db)
{
    m_comp.configure(m_sampleRate, db, 2.0f, 5.0f, 50.0f);
}

void TTSDSPProcessor::setNormTarget(float dBFS)
{
    m_norm.setTargetDb(dBFS);
}

// ═══════════════════════════════════════════════════════
//  PCMRingBuffer — SPSC lock-free PCM16 ring buffer
//
//  Indices monotoniques en bytes : head (producer) / tail (consumer),
//  acquire/release pour la visibilite memoire. Capacite POT, mask
//  remplace le modulo. availableRead = head - tail (jamais negatif
//  dans un usage SPSC). availableWrite = capacity - (head - tail).
// ═══════════════════════════════════════════════════════

int PCMRingBuffer::roundUpPow2(int v)
{
    if (v < 2) return 2;
    int p = 1;
    while (p < v) p <<= 1;
    return p;
}

PCMRingBuffer::PCMRingBuffer(int capacityBytes)
{
    m_capacity = roundUpPow2(std::max(2, capacityBytes));
    m_mask     = m_capacity - 1;
    m_buf.assign(m_capacity, 0);
    m_head.store(0, std::memory_order_relaxed);
    m_tail.store(0, std::memory_order_relaxed);
}

int PCMRingBuffer::availableRead() const
{
    const int head = m_head.load(std::memory_order_acquire);
    const int tail = m_tail.load(std::memory_order_acquire);
    return head - tail;
}

int PCMRingBuffer::availableWrite() const
{
    return m_capacity - availableRead();
}

int PCMRingBuffer::write(const char *data, int size)
{
    if (size <= 0) return 0;
    const int head = m_head.load(std::memory_order_relaxed);
    const int tail = m_tail.load(std::memory_order_acquire);
    const int free = m_capacity - (head - tail);
    const int toWrite = std::min(size, free);
    if (toWrite <= 0) {
        // Overflow : log throttle (1 toutes les 50 occurrences) pour
        // ne pas spammer la console quand le sink est sature.
        static thread_local int g_overflowCount = 0;
        if ((g_overflowCount++ % 50) == 0)
            hWarning(exoVoice) << "ringbuffer overflow -- tried" << size
                               << "B, free=" << free << "B (drop)";
        return 0;
    }

    const int wpos = head & m_mask;
    const int firstPart = std::min(toWrite, m_capacity - wpos);
    std::memcpy(&m_buf[wpos], data, firstPart);
    if (toWrite > firstPart)
        std::memcpy(&m_buf[0], data + firstPart, toWrite - firstPart);

    // release : rend les ecritures memoire visibles AVANT la maj de head
    m_head.store(head + toWrite, std::memory_order_release);
    return toWrite;
}

int PCMRingBuffer::read(char *data, int maxSize)
{
    if (maxSize <= 0) return 0;
    const int tail = m_tail.load(std::memory_order_relaxed);
    const int head = m_head.load(std::memory_order_acquire);
    const int avail = head - tail;
    const int toRead = std::min(maxSize, avail);
    if (toRead <= 0) return 0;

    const int rpos = tail & m_mask;
    const int firstPart = std::min(toRead, m_capacity - rpos);
    std::memcpy(data, &m_buf[rpos], firstPart);
    if (toRead > firstPart)
        std::memcpy(data + firstPart, &m_buf[0], toRead - firstPart);

    m_tail.store(tail + toRead, std::memory_order_release);
    return toRead;
}

void PCMRingBuffer::clear()
{
    // SPSC : un seul thread peut clear (main). On synchronise les indices.
    const int head = m_head.load(std::memory_order_acquire);
    m_tail.store(head, std::memory_order_release);
}

int PCMRingBuffer::pushSamples(const int16_t *samples, int count)
{
    if (count <= 0) return 0;
    const int written = write(reinterpret_cast<const char *>(samples),
                               count * static_cast<int>(sizeof(int16_t)));
    return written / static_cast<int>(sizeof(int16_t));
}

int PCMRingBuffer::popBlock(int16_t *out, int count)
{
    if (count <= 0) return 0;
    const int needBytes = count * static_cast<int>(sizeof(int16_t));
    const int got = read(reinterpret_cast<char *>(out), needBytes);
    const int gotSamples = got / static_cast<int>(sizeof(int16_t));
    if (gotSamples < count) {
        // Underflow : silence-fill (zero), garantit un bloc complet
        // -> jamais de craquement par lecture partielle.
        std::memset(out + gotSamples, 0,
                    (count - gotSamples) * sizeof(int16_t));
        static thread_local int g_underflowCount = 0;
        if ((g_underflowCount++ % 50) == 0)
            hWarning(exoVoice) << "ringbuffer underflow -- got" << gotSamples
                               << "/" << count << "samples (silence-fill)";
    }
    return count;
}

void PCMRingBuffer::dropSamples(int count)
{
    if (count <= 0) return;
    const int dropBytes = count * static_cast<int>(sizeof(int16_t));
    const int tail = m_tail.load(std::memory_order_relaxed);
    const int head = m_head.load(std::memory_order_acquire);
    const int avail = head - tail;
    const int actual = std::min(dropBytes, avail);
    if (actual <= 0) return;
    m_tail.store(tail + actual, std::memory_order_release);
}

void PCMRingBuffer::fadeOutTail(int fadeBytes)
{
    if (fadeBytes <= 0) return;
    const int head = m_head.load(std::memory_order_acquire);
    const int tail = m_tail.load(std::memory_order_acquire);
    const int avail = head - tail;
    if (avail == 0) return;

    int actual = std::min(fadeBytes, avail);
    actual &= ~1;  // align to int16 sample boundary
    const int fadeSamples = actual / 2;
    if (fadeSamples == 0) return;

    // Audit fix: race vs consumer (callback RtAudio).
    // On modifie [head-actual, head) ; si tail est "proche" de cette zone,
    // la callback peut lire pendant qu'on ecrit -> click final intermittent.
    // On exige une marge de securite >= 2 callbacks WASAPI typiques (4096 B
    // ~= 2x bufferFrames=960 stereo Int16) entre tail et le debut du fade.
    constexpr int kFadeSafetyMarginBytes = 4096;
    if (avail - actual < kFadeSafetyMarginBytes) {
        // Le consumer va atteindre la zone du fade dans <2 callbacks ->
        // skip le fade pour eviter la race. Le silence-fill du callback
        // remplacera proprement la queue.
        return;
    }

    // Extract tail data into a linear temporary buffer
    std::vector<char> tmp(actual);
    const int tailStart = (head - actual) & m_mask;
    const int firstPart = std::min(actual, m_capacity - tailStart);
    std::memcpy(tmp.data(), &m_buf[tailStart], firstPart);
    if (actual > firstPart)
        std::memcpy(tmp.data() + firstPart, &m_buf[0], actual - firstPart);

    // Apply raised-cosine fade-out
    auto *samples = reinterpret_cast<int16_t *>(tmp.data());
    for (int i = 0; i < fadeSamples; ++i) {
        float t = static_cast<float>(i) / static_cast<float>(fadeSamples);
        float gain = 0.5f * (1.0f + std::cos(3.14159265f * t));
        samples[i] = static_cast<int16_t>(samples[i] * gain);
    }

    // Write back into ring buffer
    std::memcpy(&m_buf[tailStart], tmp.data(), firstPart);
    if (actual > firstPart)
        std::memcpy(&m_buf[0], tmp.data() + firstPart, actual - firstPart);
}

// ═══════════════════════════════════════════════════════
//  TTSWorker — backend-based synthesis dispatcher
// ═══════════════════════════════════════════════════════

TTSWorker::TTSWorker(QObject *parent)
    : QObject(parent)
{}

TTSWorker::~TTSWorker()
{
    qInfo() << "[TTS] TTSWorker détruit";
}

void TTSWorker::resetPythonConnection()
{
#ifdef ENABLE_XTTS
    if (m_xttsBackend)
        m_xttsBackend->resetConnection();
#endif
}

void TTSWorker::init(const QString &pythonWsUrl)
{
#ifdef ENABLE_XTTS
    // Create XTTS backend (Python) — priority 1
    m_xttsBackend = new TTSBackendXTTS(this);
    m_xttsBackend->setCancelled(&m_cancelled);
    if (!pythonWsUrl.isEmpty())
        m_xttsBackend->setUrl(pythonWsUrl);
    connect(m_xttsBackend, &TTSBackend::started,  this, &TTSWorker::started);
    connect(m_xttsBackend, &TTSBackend::chunk,    this, &TTSWorker::chunk);
    connect(m_xttsBackend, &TTSBackend::finished, this, &TTSWorker::finished);
    connect(m_xttsBackend, &TTSBackend::error,    this, &TTSWorker::error);
    m_backends.append(m_xttsBackend);
#else
    Q_UNUSED(pythonWsUrl)
    qWarning() << "[TTS] XTTS non compilé (ENABLE_XTTS=OFF) — mode Qt-only";
#endif

    // Create Qt TTS backend — DESACTIVE (patch anti-XTTS) : on n'enregistre
    // plus le backend Qt SAPI dans la chaine. Orpheus est le seul backend
    // autorise ; en cas d'echec, on log ERROR et on s'arrete (pas de
    // bascule vers une voix Windows degradee).
    m_qtBackend = new TTSBackendQt(this);
    m_qtBackend->setCancelled(&m_cancelled);
    m_qtBackend->init();
    connect(m_qtBackend, &TTSBackendQt::voiceInfo, this, &TTSWorker::voiceInfo);
    // INTENTIONNEL : pas de m_backends.append(m_qtBackend)
    // INTENTIONNEL : pas de connect started/chunk/finished/error

    qInfo() << "[TTS] Worker init:" << m_backends.size() << "backend(s) Orpheus actif(s) ; Qt SAPI desactive";
    qInfo() << "[TTS] Backends actifs: Orpheus uniquement (XTTS desactive au niveau code)";
}

// Patch anti-XTTS : toute voix XTTS heritee (pierre/amelie/marie) est
// remappee silencieusement vers la voix logique unique "orpheus". Le
// serveur Python (services/orpheus/server_ws.py) se charge ensuite de
// resoudre "orpheus" vers le token GGUF reel.
static QString remapLegacyVoice(const QString &name)
{
    static const QSet<QString> kLegacy = { QStringLiteral("pierre"),
                                           QStringLiteral("amelie"),
                                           QStringLiteral("marie") };
    const QString trimmed = name.trimmed().toLower();
    if (kLegacy.contains(trimmed)) {
        qInfo() << "[TTS] Voix legacy XTTS" << name << "-> remappee vers 'orpheus'";
        return QStringLiteral("orpheus");
    }
    return name;
}

void TTSWorker::setVoice(const QString &name)
{
    const QString safe = remapLegacyVoice(name);
    if (m_qtBackend)
        m_qtBackend->setVoice(safe);
#ifdef ENABLE_XTTS
    if (m_xttsBackend)
        m_xttsBackend->setVoice(safe);
#endif
}

void TTSWorker::setPythonWsUrl(const QString &url)
{
#ifdef ENABLE_XTTS
    if (m_xttsBackend)
        m_xttsBackend->setUrl(url);
#else
    Q_UNUSED(url)
#endif
}

#ifdef ENABLE_XTTS
void TTSWorker::setXTTSVoice(const QString &name)
{
    if (m_xttsBackend)
        m_xttsBackend->setVoice(name);
}

void TTSWorker::setXTTSLang(const QString &lang)
{
    if (m_xttsBackend)
        m_xttsBackend->setLang(lang);
}
#endif

void TTSWorker::warmConnect()
{
#ifdef ENABLE_XTTS
    if (m_xttsBackend)
        m_xttsBackend->warmConnect();
#endif
}

void TTSWorker::processRequest(const TTSRequest &req)
{
    m_cancelled = false;

    // Iterate backends in priority order
    // Patch anti-XTTS : on remappe le nom de classe historique TTSBackendXTTS -> TTSBackendOrpheus
    // dans les logs (la classe C++ est conservée pour compatibilité ABI mais elle EST le client Orpheus).
    for (TTSBackend *backend : m_backends) {
        QString backendName = QString::fromLatin1(backend->metaObject()->className());
        if (backendName == QLatin1String("TTSBackendXTTS"))
            backendName = QStringLiteral("TTSBackendOrpheus");
        if (!backend->isAvailable()) {
            qWarning() << "[TTS] Backend indisponible:" << backendName;
            continue;
        }

        qInfo() << "[TTS] Tentative backend:" << backendName;
        if (backend->synthesize(req)) {
            qInfo() << "[TTS] Backend sélectionné:" << backendName;
            return;
        }
        qWarning() << "[TTS] Backend échoué:" << backendName;
    }

    // All engines failed
    emit error("Tous les moteurs TTS ont échoué pour: " + req.text.left(40));
}

void TTSWorker::cancelCurrent()
{
    m_cancelled = true;
    for (TTSBackend *backend : m_backends)
        backend->cancel();
}

// ═══════════════════════════════════════════════════════
//  TTSManager — main-thread orchestrator
// ═══════════════════════════════════════════════════════

TTSManager::TTSManager(QObject *parent)
    : QObject(parent)
{
    m_lastSpeechEnd.start();

    // Audio profiling : ON par defaut pour diagnostiquer les craquements,
    // log toutes les 2 secondes + immediatement sur anomalie. Desactivable
    // via setAudioProfilingEnabled(false) depuis QML.
    m_audioProfiler.setEnabled(true);
    m_audioProfiler.setLogIntervalMs(2000);

    // Detection automatique des anomalies audio (Phase 9). Mode debug ON par
    // defaut : log immediat sur underflow/overflow/jitter/burst/gap/silence/
    // saturation/block-mismatch + resume periodique toutes les 2s.
    m_audioAnomalies.setEnabled(m_enableAudioAnomalyDetection);
    m_audioAnomalies.setLogIntervalMs(2000);

    // Auto-correction (Phase 10) : ON par defaut, depend du detector + ring.
    m_audioAutoCorrector.attach(&m_ringBuffer, &m_audioAnomalies);
    m_audioAutoCorrector.setEnabled(m_enableAudioAutoCorrection);
    m_audioAutoCorrector.setVerbose(true);

    // Keep TTS voice list fresh across backend restarts without requiring
    // a Settings page reopen.
    m_voiceRefreshTimer = new QTimer(this);
    m_voiceRefreshTimer->setInterval(10000);
    connect(m_voiceRefreshTimer, &QTimer::timeout, this, [this]() {
        if (m_ttsServerUrl.isEmpty() || m_voiceFetchInFlight)
            return;
        fetchAvailableVoices();
    });
}

TTSManager::~TTSManager()
{
    hVoice() << "TTSManager destruction — arrêt thread TTS";
    // Destroy persistent sink before worker thread
    destroySink();
    // Signal worker to exit blocking loops (atomic flag — thread-safe)
    if (m_worker)
        m_worker->requestStop();

    // R2 audit threads : avant quit(), forcer la fermeture du WebSocket Python
    // depuis le thread du worker (sans cela, une lecture WS pendante peut
    // bloquer 5s puis déclencher terminate() — qui peut corrompre Qt).
    if (m_worker) {
        QMetaObject::invokeMethod(m_worker, [w = m_worker]() {
            w->resetPythonConnection();
        }, Qt::QueuedConnection);
    }

    m_workerThread.quit();
    if (!m_workerThread.wait(5000)) {
        hWarning(exoVoice) << "Thread TTS ne répond pas — terminate forcé";
        m_workerThread.terminate();
        m_workerThread.wait(2000);
    }
}

// ── initialisation ───────────────────────────────────

void TTSManager::initTTS(const QString &pythonWsUrl)
{
    m_ttsServerUrl = pythonWsUrl;
    // Create worker and move to thread
    m_worker = new TTSWorker();
    m_worker->moveToThread(&m_workerThread);

    // Wire signals: worker → manager (queued across threads)
    // Pass pythonWsUrl directly to init() so it's set BEFORE any TTS request
    connect(&m_workerThread, &QThread::started,
            m_worker, [this, pythonWsUrl]() { m_worker->init(pythonWsUrl); });
    connect(&m_workerThread, &QThread::finished,
            m_worker, &QObject::deleteLater);

    connect(m_worker, &TTSWorker::started,
            this, &TTSManager::onWorkerStarted, Qt::QueuedConnection);
    connect(m_worker, &TTSWorker::chunk,
            this, &TTSManager::onWorkerChunk, Qt::QueuedConnection);
    connect(m_worker, &TTSWorker::finished,
            this, &TTSManager::onWorkerFinished, Qt::QueuedConnection);
    connect(m_worker, &TTSWorker::error,
            this, &TTSManager::onWorkerError, Qt::QueuedConnection);
    connect(m_worker, &TTSWorker::voiceInfo,
            this, [](const QString &name, int count) {
                hVoice() << "TTS worker voix:" << name
                         << "(" << count << "voix disponibles)";
            }, Qt::QueuedConnection);

    // Manager → worker (queued)
    connect(this, &TTSManager::_doRequest,
            m_worker, &TTSWorker::processRequest, Qt::QueuedConnection);
    connect(this, &TTSManager::_doCancelWorker,
            m_worker, &TTSWorker::cancelCurrent, Qt::QueuedConnection);

    m_workerThread.setObjectName("EXO-TTS");
    m_workerThread.start(QThread::HighPriority);

    m_cascadeEnabled = !pythonWsUrl.isEmpty();
    hVoice() << "TTSManager initialisé — thread TTS démarré";
    if (m_cascadeEnabled) {
        hVoice() << "Cascade TTS activée — CUDA backend:" << pythonWsUrl;
        // Eager WebSocket connection: connect now so first TTS request has zero connect latency
        QTimer::singleShot(500, this, [this]() {
            if (m_worker) {
                QMetaObject::invokeMethod(m_worker, [this]() {
                    m_worker->warmConnect();
                }, Qt::QueuedConnection);
            }
        });

        // Start periodic voice refresh and trigger an immediate fetch.
        if (m_voiceRefreshTimer && !m_voiceRefreshTimer->isActive())
            m_voiceRefreshTimer->start();
        QTimer::singleShot(100, this, [this]() {
            if (!m_voiceFetchInFlight)
                fetchAvailableVoices();
        });
    } else if (m_voiceRefreshTimer) {
        m_voiceRefreshTimer->stop();
    }
}

void TTSManager::initDSP()
{
    m_sinkFormat.setSampleRate(SAMPLE_RATE);
    m_sinkFormat.setChannelCount(CHANNELS);
    m_sinkFormat.setSampleFormat(QAudioFormat::Int16);
    m_deviceFormat = m_sinkFormat;

    m_dsp.configure(SAMPLE_RATE);
    hVoice() << "DSP pipeline configuré — EQ 3kHz +0.5dB, compresseur -20dB 1.4:1, normalizer OFF (XTTS v2 light)";

    // v26.1 Latency: pre-allocate DSP float buffer (avoids first-chunk heap alloc)
    m_dsp.preAllocate(4096);

    // v27 Latency: pre-allocate pump staging buffer + anti-jitter clock
    m_pumpBuf.resize(PUMP_BUF_SIZE);
    m_pumpClock.start();
    m_pumpEpochNs = 0;
    m_pumpBytesSent = 0;
    m_ringBuffer.clear();

    // === Persistent sink — created once, never destroyed between phrases ===
    // v26.1 Latency: open sink at init, not on first speech request
    ensureSinkReady();
    // Start pump timer immediately so it's ready when first audio arrives
    if (m_pumpTimer && !m_pumpTimer->isActive())
        m_pumpTimer->start();
    hVoice() << "[Latency] Audio sink pré-ouvert — pump" << PUMP_INTERVAL_MS << "ms, anti-jitter actif";
}

// ── v26.2 Latency: pre-warm TTS pipeline during Claude thinking ──

void TTSManager::prepareNext()
{
    if (m_speaking) return;  // don't interfere with active speech

    m_dsp.preAllocate(4096);
    m_ringBuffer.clear();
    ensureSinkReady();
    if (m_pumpTimer && !m_pumpTimer->isActive())
        m_pumpTimer->start();

    hVoice() << "[Latency] prepareNext: TTS pipeline pré-chauffé pour prochain speech";
}

// ── prosody analysis ─────────────────────────────────

ProsodyProfile TTSManager::analyzeProsody(const QString &text) const
{
    ProsodyProfile p;
    p.pitch  = m_basePitch;
    p.rate   = m_baseRate;
    p.volume = m_baseEnergy;

    if (text.isEmpty()) return p;

    // Detect sentence type
    bool isQuestion    = text.endsWith('?');
    bool isExclamation = text.endsWith('!');
    // Perf: regex pré-compilée une seule fois (évite re-compile à chaque
    // synthèse — analyzeProsody est appelée par TTSWorker pour chaque request).
    static const QRegularExpression RX_WHITESPACE(QStringLiteral("\\s+"));
    int  wordCount     = text.split(RX_WHITESPACE, Qt::SkipEmptyParts).count();
    bool isShort       = (wordCount <= 5);
    bool isLong        = (wordCount > 30);

    // Detect context keywords (case-insensitive)
    QString low = text.toLower();
    bool isDomotic  = low.contains("lumière") || low.contains("lampe")
                   || low.contains("volet")   || low.contains("chauffage")
                   || low.contains("allume")  || low.contains("éteins");
    bool isWeather  = low.contains("météo")   || low.contains("temps")
                   || low.contains("pluie")   || low.contains("soleil")
                   || low.contains("température");
    bool isReminder = low.contains("rappel")  || low.contains("alarme")
                   || low.contains("timer")   || low.contains("minuteur");
    bool isGreeting = low.contains("bonjour") || low.contains("bonsoir")
                   || low.contains("salut")   || low.contains("bienvenue");

    // Adjust pitch
    if (isQuestion)
        p.pitch += 0.12f;   // rising intonation
    if (isExclamation)
        p.pitch += 0.06f;
    if (isGreeting)
        p.pitch += 0.04f;

    // Adjust rate — conservative to avoid accelerated speech on Qt TTS
    if (isShort)
        p.rate -= 0.03f;    // slightly slower for short confirmations
    if (isLong)
        p.rate += 0.03f;    // gentle speedup for long texts
    if (isDomotic)
        p.rate += 0.02f;    // crisp for home commands
    if (isReminder)
        p.rate -= 0.04f;    // slower for important reminders

    // Adjust volume / energy
    if (isExclamation)
        p.volume = std::min(p.volume + 0.08f, 1.0f);
    if (isReminder)
        p.volume = std::min(p.volume + 0.05f, 1.0f);
    if (isWeather)
        p.rate += 0.01f;    // conversational flow for weather

    // Clamp — cap rate to ±0.05 to keep speech natural
    p.pitch  = std::clamp(p.pitch,  -1.0f, 1.0f);
    p.rate   = std::clamp(p.rate,   -0.05f, 0.05f);
    p.volume = std::clamp(p.volume,  0.0f, 1.0f);

    return p;
}

QString TTSManager::preprocessText(const QString &raw) const
{
    QString t = raw;
    // Remove emojis and pictographic symbols (PCRE2 Unicode escapes)
    t.remove(QRegularExpression(
        "[\\x{1F000}-\\x{1FFFF}"
        "\\x{2600}-\\x{27BF}"
        "\\x{2300}-\\x{23FF}"
        "\\x{200D}\\x{FE0F}\\x{FE0E}"
        "\\x{20E3}"
        "\\x{25A0}-\\x{25FF}"
        "\\x{2B05}-\\x{2B55}]+"
    ));
    // Remove bullet markers at start of lines
    t.replace(QRegularExpression("^\\s*[-\\x{2022}\\x{2013}\\x{2014}]\\s*",
                                 QRegularExpression::MultilineOption), QStringLiteral(""));
    // Collapse multiple newlines to spaces
    t.replace(QRegularExpression("\\n+"), " ");
    // Remove markdown-like formatting
    t.remove(QRegularExpression("[*_`#]"));
    // Collapse multiple spaces
    t.replace(QRegularExpression("\\s{2,}"), " ");
    return t.trimmed();
}

// ── main API ─────────────────────────────────────────

void TTSManager::speakText(const QString &text)
{
    if (text.isEmpty()) return;
    MetricsManager::instance()->increment(QStringLiteral("tts.requests"));

    m_speakRequestTime.restart();
    QString clean = preprocessText(text);
    if (clean.isEmpty()) return;

    ProsodyProfile prosody = analyzeProsody(clean);

    TTSRequest req;
    req.text    = clean;
    req.prosody = prosody;

    PIPELINE_EVENT(PipelineModule::TTS, EventType::SynthesisRequested,
                   {{"text_length", clean.length()},
                    {"pitch", prosody.pitch},
                    {"rate", prosody.rate},
                    {"volume", prosody.volume}});
    PIPELINE_STATE(PipelineModule::TTS, ModuleState::Processing);

    hVoice() << "TTS demande — pitch:" << prosody.pitch
             << "rate:" << prosody.rate
             << "vol:" << prosody.volume
             << "texte:" << clean.left(60) << "...";

    // If already speaking, cancel current and enqueue
    if (m_speaking) {
        emit _doCancelWorker();
        // Clear queue (newest wins)
        QMutexLocker lk(&m_queueMutex);
        m_queue.clear();
        m_queue.enqueue(req);
        return;
    }

    // Start immediately
    {
        QMutexLocker lk(&m_queueMutex);
        m_queue.enqueue(req);
    }
    processQueue();
}

void TTSManager::enqueueSentence(const QString &text)
{
    if (text.isEmpty()) return;

    QString clean = preprocessText(text);
    if (clean.isEmpty()) return;

    ProsodyProfile prosody = analyzeProsody(clean);

    TTSRequest req;
    req.text    = clean;
    req.prosody = prosody;

    hVoice() << "TTS sentence enqueued:" << clean.left(60) << "...";

    {
        QMutexLocker lk(&m_queueMutex);
        m_queue.enqueue(req);
    }

    PIPELINE_EVENT(PipelineModule::TTS, EventType::SentenceQueued,
                   {{"text_length", clean.length()},
                    {"preview", clean.left(60)}});

    // If not currently speaking, start immediately
    if (!m_speaking)
        processQueue();
}

void TTSManager::cancelSpeech()
{
    PIPELINE_EVENT(PipelineModule::TTS, EventType::SpeechCancelled);
    {
        QMutexLocker lk(&m_queueMutex);
        m_queue.clear();
    }
    emit _doCancelWorker();

    // Clear ring buffer but keep persistent sink alive
    m_ringBuffer.clear();
    m_synthesizing = false;
    m_turnActive = false;
    if (m_pumpTimer) m_pumpTimer->stop();

    if (m_speaking) {
        m_speaking = false;
        m_lastSpeechEnd.restart();
        emit speakingChanged();
        emit ttsFinished();
        broadcastState("idle");
    }
}

void TTSManager::processQueue()
{
    // Guard against re-entrant calls (finalizeSpeech → processQueue while still inside)
    bool expected = false;
    if (!m_processingGuard.compare_exchange_strong(expected, true))
        return;

    QMutexLocker lk(&m_queueMutex);
    if (m_queue.isEmpty() || m_speaking) {
        m_processingGuard = false;
        return;
    }

    TTSRequest req = m_queue.dequeue();
    lk.unlock();

    // Mark speaking IMMEDIATELY to prevent re-entrant dispatch.
    m_speaking = true;
    m_synthesizing = true;

    m_totalPcmBytes = 0;
    // First phrase of turn → full DSP reset with fade-in.
    // Chained phrases → DSP stays fully continuous (no reset).
    if (!m_turnActive) {
        m_dsp.reset();
        m_turnActive = true;
        // v27: reset anti-jitter counters for new audio stream
        m_pumpEpochNs = m_pumpClock.nsecsElapsed();
        m_pumpBytesSent = 0;
        // Reset etat du resampler streaming pour repartir propre.
        resetResamplerState();
    }
    // Chained phrases: no reset at all — EQ/compressor envelope stays continuous

    m_processingGuard = false;
    m_speakRequestTime.restart();

    // Ensure persistent sink is alive and pump is running
    ensureSinkReady();
    if (m_pumpTimer && !m_pumpTimer->isActive())
        m_pumpTimer->start();

    hVoice() << "processQueue — dispatching phrase, ringbuffer:" << m_ringBuffer.availableRead() << "bytes";
    emit _doRequest(req);
}

// ── worker callbacks (main thread) ───────────────────

void TTSManager::onWorkerStarted(const QString &text)
{
    m_speaking = true;
    m_firstChunkReceived = false;
    m_firstAudioPumped = false;
    PIPELINE_EVENT(PipelineModule::TTS, EventType::WorkerStarted,
                   {{"text_preview", text.left(50)}});
    emit ttsStarted();
    emit speakingChanged();
    emit statusChanged("Parle...");
    broadcastState("speaking");
    hVoice() << "TTS démarré:" << text.left(50);
}

void TTSManager::onWorkerChunk(const QByteArray &pcm)
{
    if (pcm.isEmpty()) {
        hWarning(exoVoice) << "TTS chunk 0 bytes — synthèse possiblement échouée";
        return;
    }

    if (!m_firstChunkReceived) {
        m_firstChunkReceived = true;
        LatencyMetrics::instance()->markTtsFirstChunk();
        // v27: mark ttsFirstAudio dès le premier chunk (not at pump delay)
        if (!m_firstAudioPumped) {
            LatencyMetrics::instance()->markTtsFirstAudio();
            m_firstAudioPumped = true;
            // Reset anti-jitter epoch — audio data starts flowing
            m_pumpEpochNs = m_pumpClock.nsecsElapsed();
            m_pumpBytesSent = 0;
        }
        hVoice() << "[Latency] TTS first-chunk C++:" << m_speakRequestTime.elapsed() << "ms (ttsFirstAudio marqué)";
        PIPELINE_EVENT(PipelineModule::AudioOutput, EventType::PcmChunk,
                       {{"bytes", pcm.size()}, {"first", true}});
    }

    // Apply DSP to chunk (EQ → compressor → normalizer → fade-in on first chunk)
    QByteArray processed = pcm;
    m_dsp.process(reinterpret_cast<int16_t *>(processed.data()),
                  processed.size() / static_cast<int>(sizeof(int16_t)),
                  false);

    QByteArray outputPcm = adaptForOutputFormat(processed);
    m_totalPcmBytes += outputPcm.size();

    // DEBUG CRAQUEMENTS : dump du PCM apres resample/upmix EXO, juste avant
    // d'etre injecte dans le ring -> active uniquement si EXO_TTS_DUMP=1.
    // Audit: laisser actif en permanence faisait des I/O sync sur chaque
    // chunk WS (40 ms) -> micro-jitter sur le slot principal.
    {
        static const bool s_dumpEnabled = qEnvironmentVariableIntValue("EXO_TTS_DUMP") == 1;
        if (s_dumpEnabled) {
            static QFile dbg("D:/EXO/logs/tts_post_adapt.pcm");
            if (!dbg.isOpen()) dbg.open(QIODevice::WriteOnly | QIODevice::Truncate);
            if (dbg.isOpen()) { dbg.write(outputPcm); dbg.flush(); }
        }
    }

    // Write to ring buffer — persistent sink reads from it continuously
    feedRingBuffer(outputPcm);

    // FIX CRAQUEMENTS : pre-buffer 200 ms avant de demarrer le pump.
    // Sans pre-buffer, le ring se vide entre chaque chunk WS (40 ms +
    // jitter reseau) -> sink en famine continue -> glitch audio. Avec
    // 200 ms d'avance le ring absorbe la jitter du producer et le sink
    // a toujours de quoi jouer.
    if (m_sink && m_pumpTimer && !m_pumpTimer->isActive() && !m_useRtAudioSink) {
        const int bps = outputBytesPerSecond();
        const int prebufBytes = bps * 400 / 1000;
        if (m_ringBuffer.availableRead() >= prebufBytes) {
            m_pumpTimer->start();
            // Reset epoch pour eviter une bouffee de rattrapage massive
            // au demarrage (idealPos calcule a partir d'un nowNs faux).
            m_pumpEpochNs = m_pumpClock.nsecsElapsed();
            m_pumpBytesSent = 0;
            hVoice() << "[Audio] pump start apres prebuffer"
                     << m_ringBuffer.availableRead() << "bytes ("
                     << (m_ringBuffer.availableRead() * 1000 / bps) << "ms)";
        }
    }
#ifdef ENABLE_RTAUDIO
    // Demarrage differe du stream RtAudio APRES prebuffer 400 ms.
    // (Backup au cas où le staging serait court-circuité.)
    if (m_useRtAudioSink && m_rtSink && !m_rtSink->isRunning() && !m_rtNeedsPrebuf) {
        m_rtSink->start();
    }
#endif

    broadcastWaveform(processed);
    emit ttsChunk(outputPcm);

    // ── Emit downsampled PCM for QML waveform visualization ──
    {
        const int sampleCount = processed.size() / static_cast<int>(sizeof(int16_t));
        const auto *pcmSamples = reinterpret_cast<const int16_t *>(processed.constData());
        constexpr int TARGET = 256;
        QVariantList vizSamples;
        vizSamples.reserve(TARGET);
        if (sampleCount > 0) {
            const float step = static_cast<float>(sampleCount) / TARGET;
            for (int i = 0; i < TARGET; ++i) {
                const int start = static_cast<int>(i * step);
                const int end   = std::min(static_cast<int>((i + 1) * step), sampleCount);
                float sum = 0.0f;
                for (int j = start; j < end; ++j)
                    sum += pcmSamples[j] / 32768.0f;
                vizSamples.append(sum / std::max(1, end - start));
            }
        } else {
            for (int i = 0; i < TARGET; ++i)
                vizSamples.append(0.0f);
        }
        emit ttsPcmForVisualization(vizSamples);
    }
}

void TTSManager::onWorkerFinished()
{
    m_synthesizing = false;
    MetricsManager::instance()->increment(QStringLiteral("tts.synthesis_completed"));
    hVoice() << "onWorkerFinished — ringbuffer:" << m_ringBuffer.availableRead()
             << "bytes, totalPcm:" << m_totalPcmBytes;

#ifdef ENABLE_RTAUDIO
    // Synthese terminee : si on est encore en mode prebuffer (phrase courte
    // < seuil), flush immediatement pour eviter de bloquer la lecture.
    if (m_useRtAudioSink && m_rtNeedsPrebuf) {
        flushRtPrebuffer("worker finished");
    }
#endif

    // Check if more sentences are queued → chain seamlessly
    bool hasMore = false;
    {
        QMutexLocker lk(&m_queueMutex);
        hasMore = !m_queue.isEmpty();
    }

    // AUDIT AUDIO 2026-05-04 : ne PAS appliquer fadeOutTail entre 2 phrases
    // chainees -- ca fade les 10 derniers ms d'audio deja pousse dans le ring,
    // puis on enchaine direct avec la phrase suivante = dip de volume audible
    // a la jonction. On ne fade QUE sur la derniere phrase de la sequence.
    if (!hasMore) {
        const int fadeBytes = SAMPLE_RATE * 10 / 1000 * static_cast<int>(sizeof(int16_t)); // 10ms
        m_ringBuffer.fadeOutTail(fadeBytes);
        hVoice() << "fade_out_applied — 10ms tail (last sentence)";
    }

    if (hasMore) {
        // Seamless chaining — sink stays alive, ring buffer may still have data
        m_speaking = false;
        hVoice() << "TTS phrase terminée — enchaînement suivante (sink persistant)";
        processQueue();
    } else {
        // No more phrases — pumpBuffer will detect empty ring buffer and finalize
        hVoice() << "TTS dernière phrase — attente vidage ring buffer";
#ifdef ENABLE_RTAUDIO
        // En mode RtAudio, pumpBuffer ne tourne pas : on poll manuellement
        // le vidage du ring buffer pour declencher finalizeSpeech.
        if (m_useRtAudioSink) {
            QTimer *drainTimer = new QTimer(this);
            drainTimer->setInterval(50);
            connect(drainTimer, &QTimer::timeout, this, [this, drainTimer]() {
                if (!m_speaking) { drainTimer->stop(); drainTimer->deleteLater(); return; }
                if (m_synthesizing) return; // chunks encore en route
                if (m_ringBuffer.availableRead() > 0) return; // pas encore vide
                drainTimer->stop();
                drainTimer->deleteLater();
                finalizeSpeech();
            });
            drainTimer->start();
        }
#endif
    }
}

void TTSManager::onWorkerError(const QString &msg)
{
    PIPELINE_EVENT(PipelineModule::TTS, EventType::WorkerError, {{"message", msg}});
    PipelineEventBus::instance()->setModuleError(PipelineModule::TTS, msg);
    MetricsManager::instance()->increment(QStringLiteral("tts.errors"));
    hVoice() << "TTS erreur:" << msg;
    emit ttsError(msg);

    // Try next in queue — keep sink alive
    m_synthesizing = false;
    m_speaking = false;
    m_lastSpeechEnd.restart();
    emit speakingChanged();
    broadcastState("idle");
    QTimer::singleShot(200, this, &TTSManager::processQueue);
}

// ── persistent audio output ──────────────────────────

void TTSManager::ensureSinkReady()
{
    // Persistent sink — created once, never destroyed between phrases
    if (m_sink) {
        hVoice() << "sink_still_running — device active";
        return;
    }

    QAudioDevice dev = QMediaDevices::defaultAudioOutput();
    if (!m_outputDevicePreference.trimmed().isEmpty()) {
        const auto outputs = QMediaDevices::audioOutputs();
        for (const QAudioDevice &candidate : outputs) {
            if (candidate.description().contains(m_outputDevicePreference, Qt::CaseInsensitive)) {
                dev = candidate;
                break;
            }
        }
    }
    if (dev.isNull()) {
        hWarning(exoVoice) << "Pas de sortie audio disponible";
        return;
    }

    // ── FIX CRAQUEMENTS WASAPI ──
    // dev.isFormatSupported(24kHz mono) ment souvent en mode SHARED : Qt
    // accepte le format mais Windows applique un resample 24->48 +
    // mono->stereo dans le mixer partage avec un algo de tres mauvaise
    // qualite -> craquements audibles permanents.
    //
    // Solution : on vise EXPLICITEMENT le format reel du mixer Windows
    // (typiquement 48 kHz stereo Int16, ce que Realtek/HDMI/USB exposent
    // tous en partage). Notre resampler streaming + upmix mono->stereo
    // fait le boulot proprement avant que Qt ne touche au sink, donc
    // Windows ne resample plus rien.
    auto matchInt16 = [&](int rate, int ch) -> QAudioFormat {
        QAudioFormat f;
        f.setSampleRate(rate);
        f.setChannelCount(ch);
        f.setSampleFormat(QAudioFormat::Int16);
        return f;
    };
    QAudioFormat target;
    bool targetOk = false;
    for (int rate : {48000, 44100, 96000, 192000}) {
        for (int ch : {2, 1}) {
            QAudioFormat f = matchInt16(rate, ch);
            if (dev.isFormatSupported(f)) { target = f; targetOk = true; break; }
        }
        if (targetOk) break;
    }
    if (targetOk) {
        m_deviceFormat = target;
        if (m_deviceFormat.sampleRate()   != m_sinkFormat.sampleRate() ||
            m_deviceFormat.channelCount() != m_sinkFormat.channelCount()) {
            hVoice() << "Format mixer Windows force ->"
                     << m_deviceFormat.sampleRate() << "Hz"
                     << m_deviceFormat.channelCount() << "ch Int16"
                     << "(resample/upmix interne EXO, ZERO resample WASAPI)";
        } else {
            hVoice() << "Format mixer Windows == format TTS natif (24kHz mono Int16)"
                     << "-- ZERO resample necessaire";
        }
    } else {
        hWarning(exoVoice) << "Aucun format Int16 supporte trouve -- fallback format TTS natif";
    }

    hVoice() << "sink_started -- device:" << dev.description()
             << "format:" << m_deviceFormat.sampleRate() << "Hz"
             << m_deviceFormat.channelCount() << "ch Int16 (PERSISTENT)";

    m_sink = std::make_unique<QAudioSink>(dev, m_deviceFormat);
    m_sink->setVolume(1.0f);
    // Buffer sink dimensionne en bytes/sec REELS du device : ~160 ms
    // = 4 chunks WS de 40 ms. Marge confortable contre la jitter du pump
    // sans empiler de retard a la reprise.
    const int devBps = std::max(1, m_deviceFormat.sampleRate()
                                    * m_deviceFormat.channelCount()
                                    * std::max(1, m_deviceFormat.bytesPerSample()));
    // Buffer sink par DEFAUT Qt (pas de setBufferSize) -- Qt choisit la taille
    // adaptee au backend WASAPI (typiquement 50-100 ms). Forcer plus grand
    // peut causer des artefacts de segmentation cote backend.
    // const int sinkBufBytes = std::max(SINK_BUFFER_SIZE, devBps * 500 / 1000);
    // m_sink->setBufferSize(sinkBufBytes);
    (void)devBps;
    connect(m_sink.get(), &QAudioSink::stateChanged,
            this, &TTSManager::onSinkStateChanged);
    m_sinkIO = m_sink->start();

    if (!m_sinkIO) {
        hWarning(exoVoice) << "ERREUR: QAudioSink::start() a retourné nullptr!";
        m_sink->stop();
        m_sink.reset();
        return;
    }

    // Pump timer — feeds ring buffer → sink at steady pace
    if (!m_pumpTimer) {
        m_pumpTimer = new QTimer(this);
        m_pumpTimer->setInterval(PUMP_INTERVAL_MS); // v27: 5ms pump cycle (anti-jitter)
        // FIX CRAQUEMENTS : sans PreciseTimer, Qt utilise un CoarseTimer
        // (granularite 15-40 ms sur Windows) -> le pump est en realite
        // appele toutes les ~40 ms et n'arrive pas a alimenter le sink
        // assez vite -> famine continue cote WASAPI -> craquements.
        m_pumpTimer->setTimerType(Qt::PreciseTimer);
        connect(m_pumpTimer, &QTimer::timeout, this, &TTSManager::pumpBuffer);
    }

    // Pre-allocated pump staging buffer dimensionne sur le DEVICE (et non sur
    // le sink format) : a 48 kHz stereo Int16 le debit est 4x plus eleve qu'a
    // 24 kHz mono. On vise >= max budget du pump (60 ms) avec marge.
    const int wantBuf = std::max(PUMP_BUF_SIZE, devBps * 250 / 1000);
    if (static_cast<int>(m_pumpBuf.size()) < wantBuf)
        m_pumpBuf.resize(wantBuf);

    hVoice() << "QAudioSink persistant demarre -- bufferSize:" << m_sink->bufferSize()
             << "pumpBuf:" << m_pumpBuf.size() << "B"
             << "devBps:" << devBps;
    // Nouveau sink/format -> repart propre cote resampler.
    resetResamplerState();

#ifdef ENABLE_RTAUDIO
    // ── BYPASS QAudioSink : RtAudio/WASAPI direct ──
    // QAudioSink Qt6 + WASAPI shared cause des craquements meme avec un
    // PCM bit-perfect en entree. RtAudio ouvre WASAPI directement avec son
    // propre thread audio dedie -> immune au jitter de la Qt event loop.
    // Le callback RtAudio lit le ring SPSC ; le pump+QAudioSink
    // restent en place comme fallback mais le timer ne tourne pas.
    if (m_rtSink && m_rtSink->isOpen()) {
        // Sink RtAudio deja ouvert (sink persistant) -> ne pas re-ouvrir
        // un 2e stream (sinon conflit WASAPI = pitch instable + craquements).
        m_useRtAudioSink = true;
        if (m_sink) m_sink->suspend();
        return;
    }
    if (!m_rtSink) m_rtSink = std::make_unique<TTSAudioSinkRtAudio>();
    // 1920 frames @ 48 kHz = 40 ms par callback. WASAPI shared mode Realtek
    // tient mieux 40 ms que 20 ms : un wakeup OS rate (sched, GC, autre
    // process) ne provoque plus immediatement un underflow car on a 40 ms
    // de marge entre 2 callbacks au lieu de 20 ms. Trade-off : +20 ms de
    // latence audio device, negligeable face au prebuffer 1100 ms.
    const std::string devNameSubstr = m_outputDevicePreference.trimmed().isEmpty()
        ? std::string()
        : m_outputDevicePreference.trimmed().toStdString();
    if (m_rtSink->open(m_deviceFormat.sampleRate(),
                       m_deviceFormat.channelCount(),
                       &m_ringBuffer,
                       1920,
                       devNameSubstr)) {
        m_useRtAudioSink = true;
        // QAudioSink reste cree mais ne sera pas alimente. On le passe en
        // pause pour qu'il ne consomme pas de CPU (et n'emette pas de
        // requetes de donnees parasites).
        if (m_sink) m_sink->suspend();
        hVoice() << "[Audio] RtAudio sink OUVERT (start differe apres prebuffer) -- QAudioSink desactive";
    } else {
        hWarning(exoVoice) << "[Audio] RtAudio sink echec -> fallback QAudioSink+pump";
        m_rtSink.reset();
        m_useRtAudioSink = false;
    }
#endif
}

int TTSManager::outputBytesPerSecond() const
{
    const int rate = (m_deviceFormat.sampleRate() > 0) ? m_deviceFormat.sampleRate() : m_sinkFormat.sampleRate();
    const int channels = (m_deviceFormat.channelCount() > 0) ? m_deviceFormat.channelCount() : m_sinkFormat.channelCount();
    const int bytesPerSample = (m_deviceFormat.bytesPerSample() > 0) ? m_deviceFormat.bytesPerSample() : 2;
    return std::max(1, rate * channels * bytesPerSample);
}

QByteArray TTSManager::adaptForOutputFormat(const QByteArray &pcm)
{
    if (pcm.isEmpty())
        return pcm;

    const int inRate = m_sinkFormat.sampleRate();
    const int outRate = m_deviceFormat.sampleRate();
    const int inChannels = m_sinkFormat.channelCount();
    const int outChannels = m_deviceFormat.channelCount();

    if (inRate == outRate && inChannels == outChannels)
        return pcm;

    if (m_deviceFormat.sampleFormat() != QAudioFormat::Int16)
        return pcm;

    const int16_t *input = reinterpret_cast<const int16_t *>(pcm.constData());
    const int inputFrames = pcm.size() / static_cast<int>(sizeof(int16_t) * inChannels);
    if (inputFrames <= 0)
        return pcm;

    // Cas pas de resample (rates egaux) mais up/down-mix canaux : duplication simple
    if (inRate == outRate) {
        QByteArray converted(inputFrames * outChannels * static_cast<int>(sizeof(int16_t)),
                             Qt::Uninitialized);
        int16_t *output = reinterpret_cast<int16_t *>(converted.data());
        for (int f = 0; f < inputFrames; ++f) {
            const int16_t s = input[f * inChannels];
            for (int c = 0; c < outChannels; ++c)
                output[f * outChannels + c] = s;
        }
        return converted;
    }

    const double ratio = static_cast<double>(outRate) / static_cast<double>(inRate);

    // ── Linear interpolation resample STREAMING ──
    // Etat persistant entre chunks (m_resampleSrcPos, m_resampleLastSample) :
    // - srcPos accumule sa fraction d'un chunk au suivant -> pas de drift et
    //   pas de "reset" toutes les 40 ms.
    // - lastSample fournit l'echantillon "i = -1" au debut d'un chunk pour
    //   interpoler proprement entre la fin du chunk precedent et le debut du
    //   chunk courant -> elimine le clic periodique a la frontiere.
    // Sortie : nombre de frames produits tant que srcPos < inputFrames.
    // Premier chunk : on amorce lastSample avec input[0] pour eviter un saut
    // depuis 0 vers le premier sample.
    if (!m_resampleHasHistory) {
        m_resampleLastSample = input[0];
        m_resampleSrcPos = 0.0;
        m_resampleHasHistory = true;
    }

    // Reserve approximative ; on retaillera apres.
    const int approxOut = std::max(1, static_cast<int>(std::ceil(
        (static_cast<double>(inputFrames) - m_resampleSrcPos) * ratio)) + 2);
    QByteArray converted(approxOut * outChannels * static_cast<int>(sizeof(int16_t)),
                         Qt::Uninitialized);
    int16_t *output = reinterpret_cast<int16_t *>(converted.data());

    int outFrame = 0;
    double srcPos = m_resampleSrcPos;
    while (srcPos < static_cast<double>(inputFrames)) {
        const int i0 = static_cast<int>(std::floor(srcPos));
        const int i1 = i0 + 1;
        const double frac = srcPos - static_cast<double>(i0);
        // i0 == -1 : premier sample d'un chunk dont la position fractionnaire
        // pointe AVANT input[0]. On utilise le dernier sample du chunk precedent.
        const int s0 = (i0 < 0)
            ? static_cast<int>(m_resampleLastSample)
            : static_cast<int>(input[i0 * inChannels]);
        const int s1 = (i1 < inputFrames)
            ? static_cast<int>(input[i1 * inChannels])
            : static_cast<int>(input[(inputFrames - 1) * inChannels]);
        const int interp = static_cast<int>(s0 + (s1 - s0) * frac);
        const int16_t sample = static_cast<int16_t>(std::clamp(interp, -32768, 32767));
        for (int c = 0; c < outChannels; ++c)
            output[outFrame * outChannels + c] = sample;
        ++outFrame;
        srcPos += 1.0 / ratio;
        if (outFrame >= approxOut) break; // garde-fou ; ne doit pas arriver
    }

    // Maj etat : on retranche inputFrames pour repartir relatif au prochain chunk.
    m_resampleSrcPos = srcPos - static_cast<double>(inputFrames);
    m_resampleLastSample = input[(inputFrames - 1) * inChannels];

    // Truncate au nombre exact de frames produits.
    converted.resize(outFrame * outChannels * static_cast<int>(sizeof(int16_t)));
    return converted;
}

void TTSManager::resetResamplerState()
{
    m_resampleSrcPos = 0.0;
    m_resampleLastSample = 0;
    m_resampleHasHistory = false;
}

void TTSManager::setOutputDevicePreference(const QString &deviceName)
{
    m_outputDevicePreference = deviceName.trimmed();
    hVoice() << "TTS output device preference:" << m_outputDevicePreference;

    if (m_sink) {
        destroySink();
        ensureSinkReady();
        if (m_pumpTimer && !m_pumpTimer->isActive())
            m_pumpTimer->start();
    }
}

#ifdef ENABLE_RTAUDIO
void TTSManager::flushRtPrebuffer(const char *reason)
{
    if (!m_useRtAudioSink || !m_rtNeedsPrebuf) return;
    const int bps = std::max(1, outputBytesPerSecond());

    // ── Warmup WASAPI : sur le tout 1er flush de la session, prepend
    // ~200 ms de silence dans le ring AVANT l'audio utile. En mode shared
    // mode WASAPI met 50-200 ms a acheminer les premieres frames au DAC,
    // ces frames seraient perdues -> 1re syllabe coupee. On encaisse le
    // warmup sur du silence inaudible. Une seule fois par session : entre
    // les phrases suivantes le sink reste warm (driver cache).
    if (!m_sinkWarmedUp) {
        constexpr int kWarmupMs = 200;
        const int warmupBytes = (bps * kWarmupMs) / 1000;
        // Aligne sur frame size (2 bytes/sample mono)
        const int alignedBytes = warmupBytes - (warmupBytes % 2);
        if (alignedBytes > 0) {
            const int written = m_ringBuffer.write(QByteArray(alignedBytes, 0).constData(), alignedBytes);
            hVoice() << "[Audio] RtAudio WASAPI warmup pad" << written
                     << "bytes (" << (written * 1000 / bps) << "ms) -- 1re session";
        }
        m_sinkWarmedUp = true;
    }

    const int stagedBytes = m_rtPrebufStage.size();
    if (stagedBytes > 0) {
        const int written = m_ringBuffer.write(m_rtPrebufStage.constData(), stagedBytes);
        if (written < stagedBytes) {
            hWarning(exoVoice) << "ringbuffer_write OVERFLOW (prebuf flush) -- lost"
                               << (stagedBytes - written) << "bytes";
        }
        // AUDIT LATENCE 2026-05-03 : log enrichi -- temps depuis speak() pour
        // mesurer la latence reelle premier-son (= cible utilisateur).
        const qint64 sinceSpeak = m_speakRequestTime.isValid() ? m_speakRequestTime.elapsed() : -1;
        hVoice() << "[Latency] RtAudio prebuf flush" << stagedBytes
                 << "bytes (" << (stagedBytes * 1000 / bps) << "ms staged) reason:" << reason
                 << "-- since speak():" << sinceSpeak << "ms";
    } else {
        hVoice() << "[Latency] RtAudio prebuf flush 0 bytes (empty) reason:" << reason;
    }
    m_rtPrebufStage.clear();
    m_rtNeedsPrebuf = false;
    if (m_rtSink && !m_rtSink->isRunning()) {
        m_rtSink->start();
    }
}
#endif

void TTSManager::feedRingBuffer(const QByteArray &pcm)
{
    if (pcm.isEmpty()) return;

#ifdef ENABLE_RTAUDIO
    // Staging anti-craquements pour RtAudio : accumuler ~1100 ms avant de
    // flush + demarrer. Orpheus a un RTF total ~1.23 mais une fois la
    // marge de demarrage consommee, le steady-state est ~1.13 par chunk
    // (pauses KV cache / GC llama.cpp). 1100 ms de coussin absorbe les
    // pics jusqu'a ~700 ms, ce qui couvre les phrases longues (>10 s) sans
    // craquements, au prix de +350 ms de latence vs 750 ms.
    if (m_useRtAudioSink && m_rtNeedsPrebuf) {
        m_rtPrebufStage.append(pcm);
        const int bps = outputBytesPerSecond();
        // Orpheus RTF mesure ~1.22 sur phrases >5s (genere a 0.82x realtime).
        // Le ring se vide donc ~180 ms par seconde de speech : un prebuf de
        // 1800 ms couvre ~10 s de phrase sans craquements (cas typique).
        // Au-dela, des micro-coupures resteront possibles sauf a accelerer
        // le moteur (rate plus eleve, GGUF Q4, n_threads++, draft model).
        // AUDIT AUDIO 2026-05-04 : prebuf reduit a 600 ms (defaut) pour gagner
        // ~1200 ms de latence percue tout en restant au-dessus du pire jitter
        // Orpheus observe (~400 ms). Le warmup pad WASAPI + le silence-fill
        // anti-click cote sink couvrent les micro-dips. Override possible via
        // EXO_TTS_PREBUF_MS (range 100..5000).
        static const int s_prebufMs = []() {
            const int v = qEnvironmentVariableIntValue("EXO_TTS_PREBUF_MS");
            return (v >= 100 && v <= 5000) ? v : 600;
        }();
        const int prebufBytes = bps * s_prebufMs / 1000;
        if (m_rtPrebufStage.size() >= prebufBytes) {
            flushRtPrebuffer("prebuf threshold");
        }
        return;
    }
#endif

    // AUDIT AUDIO 2026-05-04 : ecrire le ring par sous-blocs ~80 ms pour
    // matcher la cadence du callback RtAudio (40 ms) et eviter qu'un gros
    // chunk Orpheus (>200 ms) bloque le writer une fraction de seconde en
    // creant un vide cote reader -> jitter spike artificiel.
    const int bpsCap = std::max(1, outputBytesPerSecond());
    const int subBlockBytes = std::max(2, (bpsCap * 80) / 1000);
    int offset = 0;
    while (offset < pcm.size()) {
        const int chunk = std::min<int>(subBlockBytes, static_cast<int>(pcm.size()) - offset);
        const int written = m_ringBuffer.write(pcm.constData() + offset, chunk);
        if (written < chunk) {
            hWarning(exoVoice) << "ringbuffer_write OVERFLOW — lost"
                               << (chunk - written) << "bytes";
            break;
        }
        offset += written;
    }
}

void TTSManager::pumpBuffer()
{
    if (!m_sinkIO || !m_sink) return;

    const qint64 canWrite = m_sink->bytesFree();
    if (canWrite <= 0) return;

    if (!m_ringBuffer.isEmpty()) {
        // ── Anti-jitter: time-proportional writes (v27) ──
        const int bytesPerSec = outputBytesPerSecond();
        const int frameBytes = std::max(1,
            m_deviceFormat.channelCount() * static_cast<int>(sizeof(int16_t)));
        const qint64 nowNs = m_pumpClock.nsecsElapsed();
        const qint64 idealPos = (m_pumpEpochNs > 0)
            ? (nowNs - m_pumpEpochNs) * bytesPerSec / 1000000000LL
            : m_pumpBytesSent + static_cast<qint64>(m_pumpBuf.size());
        int budget = static_cast<int>(idealPos - m_pumpBytesSent);
        // Clamp: min 2ms, max 60ms. Le max 20ms historique etait trop bas
        // pour absorber un jitter de timer de 40 ms (granularite Coarse
        // Windows) -> on n'ecrivait que 50% du debit -> famine WASAPI ->
        // craquement. 60ms reste largement sous le bufferSize sink (160ms).
        budget = std::clamp(budget, bytesPerSec * 2 / 1000, bytesPerSec * 200 / 1000);
        // Aligne sur la FRAME (channels * Int16) et non sur 1 sample Int16.
        // Sinon, en stereo, ecrire un nombre impair de samples decale L/R
        // de facon permanente -> craquement continu audible.
        budget -= budget % frameBytes;

        int toRead = std::min({static_cast<int>(canWrite),
                                     m_ringBuffer.availableRead(),
                                     static_cast<int>(m_pumpBuf.size()),
                                     budget});
        // Garde-fou : alignement frame (channels*Int16). canWrite/availableRead
        // peuvent ne pas etre alignes selon le backend Qt.
        toRead -= toRead % frameBytes;
        if (toRead <= 0) return;
        const int actual = m_ringBuffer.read(m_pumpBuf.data(), toRead);
        // Phase 10 : silence-fill si underflow (preserve cadence 40 ms vers QAudioSink)
        const int writeBytes = m_audioAutoCorrector.onPop(
            m_pumpBuf.data(), actual, toRead, m_ringBuffer.availableWrite());
        if (writeBytes > 0) {
            const auto wt0 = std::chrono::steady_clock::now();
            m_sinkIO->write(m_pumpBuf.data(), writeBytes);
            const auto wt1 = std::chrono::steady_clock::now();
            m_pumpBytesSent += writeBytes;
            // Profiler hooks (no-op si disabled)
            const int popSamples = writeBytes / static_cast<int>(sizeof(int16_t));
            const int64_t writeUs =
                std::chrono::duration_cast<std::chrono::microseconds>(wt1 - wt0).count();
            m_audioProfiler.onPop(popSamples, writeBytes);
            m_audioProfiler.onAudioWrite(writeUs);
            m_audioProfiler.setRingFreeBytes(m_ringBuffer.availableWrite());
            m_audioProfiler.maybeFlush();
            // Anomaly detector hooks (rapporte le pop reel cote ring)
            m_audioAnomalies.onPop(actual / static_cast<int>(sizeof(int16_t)),
                                   m_ringBuffer.availableWrite());
            m_audioAnomalies.onBlockWritten(writeUs);
            m_audioAnomalies.maybeFlush();
            // Phase 10 : tracking derive + suggestion pacing
            m_audioAutoCorrector.onBlockWritten(writeUs);
            (void)m_audioAutoCorrector.suggestPacingAdjustmentUs();
        } else {
            // Pop sur ring vide alors que le pump avait du budget : underflow.
            m_audioAnomalies.onPop(0, m_ringBuffer.availableWrite());
            m_audioAnomalies.maybeFlush();
        }
        return;
    }

    // ── Ring buffer empty ──
    if (m_synthesizing) {
        // TTS still producing chunks — larger sink buffer handles the gap
        return;
    }

    // Fix audit T2: stop pump timer when idle (no data, not synthesizing)
    // Timer will be restarted by startSpeaking() / onWorkerChunk()
    if (m_pumpTimer && m_pumpTimer->isActive()) {
        m_pumpTimer->stop();
    }

    // Not synthesizing, ring buffer empty — check if speech turn is over
    bool hasMore = false;
    {
        QMutexLocker lk(&m_queueMutex);
        hasMore = !m_queue.isEmpty();
    }

    if (hasMore) {
        // Between phrases — start next phrase immediately
        // (sink stays alive, ring buffer is empty, ready for next audio)
        m_speaking = false;
        processQueue();
    } else if (m_speaking) {
        // Speech turn complete — all phrases done, ring buffer empty
        if (m_pumpTimer) m_pumpTimer->stop();
        finalizeSpeech();
    }
}

void TTSManager::destroySink()
{
    if (m_pumpTimer) m_pumpTimer->stop();
#ifdef ENABLE_RTAUDIO
    if (m_rtSink) {
        m_rtSink->stop();
        m_rtSink.reset();
    }
    m_useRtAudioSink = false;
#endif
    m_ringBuffer.clear();
    if (m_sink) {
        m_sink->stop();
        m_sink.reset();
    }
    m_sinkIO = nullptr;
}

void TTSManager::onSinkStateChanged(QAudio::State state)
{
    // Persistent sink — log state changes but don't trigger finalization
    if (state == QAudio::StoppedState && m_sink && m_sink->error() != QAudio::NoError) {
        hWarning(exoVoice) << "Erreur sink :" << m_sink->error() << "— tentative recréation";
        m_sink.reset();
        m_sinkIO = nullptr;
        // Recreate on next speech
    }
}

void TTSManager::finalizeSpeech()
{
    hVoice() << "finalizeSpeech — ringbuffer:" << m_ringBuffer.availableRead() << "bytes";
    PIPELINE_EVENT(PipelineModule::TTS, EventType::SpeechFinalized,
                   {{"total_pcm_bytes", m_totalPcmBytes}});

    // Sink stays alive (persistent) — only update state
    m_speaking = false;
    m_synthesizing = false;
    m_turnActive = false;
    // v27: reset anti-jitter state
    m_pumpEpochNs = 0;
    m_pumpBytesSent = 0;
    m_lastSpeechEnd.restart();
    PIPELINE_STATE(PipelineModule::TTS, ModuleState::Idle);
    PIPELINE_STATE(PipelineModule::AudioOutput, ModuleState::Idle);
    emit ttsFinished();
    emit speakingChanged();
    emit statusChanged("Prêt");
    broadcastState("idle");
    hVoice() << "[Latency] TTS total speech:" << m_speakRequestTime.elapsed() << "ms";
    LatencyMetrics::instance()->markResponseDone();
    LatencyMetrics::instance()->finalize();
#ifdef ENABLE_RTAUDIO
    // Reset le mode staging pour la prochaine phrase + log underflows.
    if (m_useRtAudioSink && m_rtSink) {
        hVoice() << "[Audio] RtAudio stats -- underflows:" << m_rtSink->underflowCount()
                 << "frames:" << m_rtSink->framesWritten();
        // Stop le sink entre phrases : evite ~1700 underflows de silence-fill
        // pendant les 30s du mode conversation. Le prochain flushRtPrebuffer
        // redemarre via "if (m_rtSink && !m_rtSink->isRunning()) m_rtSink->start()".
        // m_sinkWarmedUp reste true : pas de pad warmup au redemarrage (driver chaud).
        //
        // IMPORTANT : RETARDER le stop. Quand le ring devient vide, WASAPI a
        // encore bufferFrames (40 ms) + latence shared mode (~30 ms) dans
        // son tampon device qui n'ont pas encore ete envoyes au DAC. Si on
        // appelle stopStream() immediatement, ces ~70-100 ms sont jetes :
        // derniere syllabe coupee. On pousse 200 ms de silence dans le ring
        // (synchrone) PUIS on stoppe : le DAC a le temps de drainer le tail.
        if (m_rtSink->isRunning()) {
            constexpr int kTailMs = 200;
            const int bps = outputBytesPerSecond();
            const int tailBytes = (bps * kTailMs) / 1000;
            const int alignedTail = tailBytes - (tailBytes % 2);
            if (alignedTail > 0) {
                QByteArray silence(alignedTail, '\0');
                m_ringBuffer.write(silence.constData(), alignedTail);
            }
            m_rtSink->stop();
        }
    }
    m_rtPrebufStage.clear();
    m_rtNeedsPrebuf = true;
#endif
    hVoice() << "TTS termin\u00e9 \u2014 sink stopp\u00e9 jusqu'\u00e0 prochaine phrase";
}

// ── tuning ───────────────────────────────────────────

void TTSManager::setVoice(const QString &name)
{
    m_voiceName = name;
    if (m_worker)
        QMetaObject::invokeMethod(m_worker, [this, name]() {
            m_worker->setVoice(name);
        }, Qt::QueuedConnection);
}

void TTSManager::setRate(float r)   { m_baseRate   = std::clamp(r, -1.0f, 1.0f); }
void TTSManager::setPitch(float p)  { m_basePitch  = std::clamp(p, -1.0f, 1.0f); }
void TTSManager::setEnergy(float e) { m_baseEnergy = std::clamp(e, 0.0f, 1.0f); }
void TTSManager::setStyle(const QString &s) { m_baseStyle = s; }
void TTSManager::setLanguage(const QString &lang)
{
    m_language = lang;
#ifdef ENABLE_XTTS
    if (m_worker)
        QMetaObject::invokeMethod(m_worker, [this, lang]() {
            m_worker->setXTTSLang(lang);
        }, Qt::QueuedConnection);
#endif
}
void TTSManager::setDSPEnabled(bool on) { m_dsp.setEnabled(on); }
void TTSManager::setCascadeEnabled(bool on) { m_cascadeEnabled = on; }

void TTSManager::setPythonUrl(const QString &url)
{
    m_ttsServerUrl = url;
    hVoice() << "TTS setPythonUrl:" << url;
    if (m_worker) {
        QMetaObject::invokeMethod(m_worker, [this, url]() {
            m_worker->resetPythonConnection();
            m_worker->setPythonWsUrl(url);
        }, Qt::QueuedConnection);
    }
    m_cascadeEnabled = !url.isEmpty();

    if (m_voiceRefreshTimer) {
        if (m_cascadeEnabled) {
            if (!m_voiceRefreshTimer->isActive())
                m_voiceRefreshTimer->start();
            QTimer::singleShot(100, this, [this]() {
                if (!m_voiceFetchInFlight)
                    fetchAvailableVoices();
            });
        } else {
            m_voiceRefreshTimer->stop();
        }
    }
}

void TTSManager::fetchAvailableVoices()
{
    if (m_ttsServerUrl.isEmpty()) {
        qWarning() << "[TTS] fetchAvailableVoices : aucune URL serveur";
        return;
    }
    if (m_voiceFetchInFlight) {
        return;
    }

    m_voiceFetchInFlight = true;

    auto *ws = new QWebSocket(QString(), QWebSocketProtocol::VersionLatest, this);

    connect(ws, &QWebSocket::textMessageReceived, this, [this, ws](const QString &msg) {
        QJsonDocument doc = QJsonDocument::fromJson(msg.toUtf8());
        if (!doc.isObject()) return;
        QJsonObject obj = doc.object();
        QString type = obj["type"].toString();

        if (type == "ready") {
            // Only request voice list once the model is fully loaded (ready_online).
            // The server starts accepting connections BEFORE loading the model and
            // broadcasts a "ready" message on each phase change. If we request
            // list_voices too early (ready_init / ready_loading / ready_warmup) the
            // engine returns an empty speaker list. Keeping the connection open lets
            // us receive the ready_online broadcast and fetch the complete list.
            QString phase = obj["phase"].toString();
            if (phase == QStringLiteral("ready_online") || phase.isEmpty()) {
                ws->sendTextMessage(QStringLiteral(R"({"type":"list_voices"})"));
            }
            // else: model still loading — keep the connection alive and wait
        } else if (type == "voices") {
            QStringList voices;
            for (const auto &v : obj["available"].toArray()) {
                QString id;
                if (v.isString()) {
                    id = v.toString();
                } else if (v.isObject()) {
                    id = v.toObject().value("id").toString();
                }
                id = id.trimmed();
                if (!id.isEmpty() && !voices.contains(id))
                    voices << id;
            }
            // Patch anti-XTTS : on ne laisse passer que la voix logique
            // "orpheus". Toute autre voix (pierre/amelie/marie, restes de
            // XTTS) est filtree pour ne jamais apparaitre dans la GUI.
            QStringList filtered;
            for (const QString &v : voices) {
                if (v.compare(QStringLiteral("orpheus"), Qt::CaseInsensitive) == 0)
                    filtered << QStringLiteral("orpheus");
            }
            if (filtered.isEmpty())
                filtered << QStringLiteral("orpheus");
            voices = filtered;
            if (voices != m_ttsVoices) {
                m_ttsVoices = voices;
                emit ttsVoicesChanged();
            }
            hVoice() << "TTS available voices:" << m_ttsVoices;
            m_voiceFetchInFlight = false;
            ws->close();
            ws->deleteLater();
        }
    });

    connect(ws, &QWebSocket::errorOccurred, this, [this, ws](QAbstractSocket::SocketError err) {
        Q_UNUSED(err)
        qWarning() << "[TTS] Erreur fetchAvailableVoices :" << ws->errorString();
        m_voiceFetchInFlight = false;
        ws->deleteLater();
    });

    // Timeout: keep the connection open long enough to survive model loading
    // (Orpheus 3B FR GGUF can take up to ~3 min on first cold start).
    QTimer::singleShot(300000, ws, [this, ws]() {
        if (ws->state() == QAbstractSocket::ConnectedState)
            ws->close();
        m_voiceFetchInFlight = false;
        ws->deleteLater();
    });

    ws->open(QUrl(m_ttsServerUrl));
}

// ── WebSocket ────────────────────────────────────────

void TTSManager::setWebSocket(QWebSocket *ws)
{
    m_ws = ws;
}

qint64 TTSManager::msSinceLastSpeech() const
{
    return m_lastSpeechEnd.elapsed();
}

void TTSManager::broadcastWaveform(const QByteArray &pcm)
{
    if (!m_ws || m_ws->state() != QAbstractSocket::ConnectedState)
        return;

    // Downsample waveform for GUI: send RMS of every 320 samples (~20ms)
    const int16_t *samples = reinterpret_cast<const int16_t *>(pcm.constData());
    int count = pcm.size() / static_cast<int>(sizeof(int16_t));

    QJsonArray waveform;
    constexpr int BLOCK = 320;
    for (int offset = 0; offset < count; offset += BLOCK) {
        int end = std::min(offset + BLOCK, count);
        double sumSq = 0;
        for (int i = offset; i < end; ++i) {
            double v = samples[i] / 32768.0;
            sumSq += v * v;
        }
        double rms = std::sqrt(sumSq / (end - offset));
        waveform.append(QJsonValue(rms));
    }

    QJsonObject msg;
    msg["type"]     = "tts_waveform";
    msg["waveform"] = waveform;
    m_ws->sendTextMessage(
        QString::fromUtf8(QJsonDocument(msg).toJson(QJsonDocument::Compact)));
}

void TTSManager::broadcastState(const QString &state)
{
    if (!m_ws || m_ws->state() != QAbstractSocket::ConnectedState)
        return;

    QJsonObject msg;
    msg["type"]  = "tts_state";
    msg["state"] = state;
    m_ws->sendTextMessage(
        QString::fromUtf8(QJsonDocument(msg).toJson(QJsonDocument::Compact)));
}
