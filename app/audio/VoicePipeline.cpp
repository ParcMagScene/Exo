#include "VoicePipeline.h"
#include "core/LogManager.h"
#include "core/LatencyMetrics.h"
#include "core/MetricsManager.h"
#include "core/TraceManager.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QRegularExpression>
#include <QStandardPaths>
#include <QDataStream>
#include <QLocale>
#include <cstring>
#include <algorithm>
#include <numeric>

// ═══════════════════════════════════════════════════════
//  CircularAudioBuffer
// ═══════════════════════════════════════════════════════

CircularAudioBuffer::CircularAudioBuffer(size_t cap)
    : m_buf(cap, 0)
{}

void CircularAudioBuffer::write(const int16_t *data, size_t count)
{
    QMutexLocker lk(&m_mutex);
    for (size_t i = 0; i < count; ++i) {
        m_buf[m_head] = data[i];
        m_head = (m_head + 1) % m_buf.size();
        if (m_count < m_buf.size())
            ++m_count;
        else
            m_tail = (m_tail + 1) % m_buf.size(); // overwrite oldest
    }
}

size_t CircularAudioBuffer::read(int16_t *dest, size_t count)
{
    QMutexLocker lk(&m_mutex);
    size_t n = std::min(count, m_count);
    for (size_t i = 0; i < n; ++i) {
        dest[i] = m_buf[m_tail];
        m_tail = (m_tail + 1) % m_buf.size();
    }
    m_count -= n;
    return n;
}

size_t CircularAudioBuffer::peek(int16_t *dest, size_t count) const
{
    QMutexLocker lk(&m_mutex);
    size_t n = std::min(count, m_count);
    size_t idx = m_tail;
    for (size_t i = 0; i < n; ++i) {
        dest[i] = m_buf[idx];
        idx = (idx + 1) % m_buf.size();
    }
    return n;
}

size_t CircularAudioBuffer::available() const
{
    QMutexLocker lk(&m_mutex);
    return m_count;
}

void CircularAudioBuffer::clear()
{
    QMutexLocker lk(&m_mutex);
    m_head = m_tail = m_count = 0;
}

// ═══════════════════════════════════════════════════════
//  AudioPreprocessor
// ═══════════════════════════════════════════════════════

AudioPreprocessor::AudioPreprocessor()
{
    recomputeHP();
}

void AudioPreprocessor::setSampleRate(int sr)
{
    m_sampleRate = sr;
    recomputeHP();
}

void AudioPreprocessor::setHighPassCutoff(float hz)
{
    m_hpCutoff = hz;
    recomputeHP();
}

void AudioPreprocessor::setNoiseGateThreshold(float rms)
{
    m_gateThreshold = rms;
}

void AudioPreprocessor::setAGCEnabled(bool on)
{
    m_agcEnabled = on;
    m_agcGain = 1.0f;
}

void AudioPreprocessor::setNormalizationTarget(float rms)
{
    m_normTarget = rms;
}

void AudioPreprocessor::recomputeHP()
{
    // Butterworth 2nd-order high-pass via bilinear transform
    const double pi = 3.14159265358979323846;
    double wc = 2.0 * pi * m_hpCutoff / m_sampleRate;
    double k  = std::tan(wc / 2.0);
    double k2 = k * k;
    double sq2 = std::sqrt(2.0);
    double norm = 1.0 / (1.0 + sq2 * k + k2);

    m_b0 =  1.0 * norm;
    m_b1 = -2.0 * norm;
    m_b2 =  1.0 * norm;
    m_a1 =  2.0 * (k2 - 1.0) * norm;
    m_a2 = (1.0 - sq2 * k + k2) * norm;

    // reset state
    m_x1 = m_x2 = m_y1 = m_y2 = 0.0;
}

void AudioPreprocessor::process(int16_t *samples, int count)
{
    if (count <= 0) return;

    // ---- 1. High-pass filter (in-place) ----
    for (int i = 0; i < count; ++i) {
        double x0 = static_cast<double>(samples[i]);
        double y0 = m_b0 * x0 + m_b1 * m_x1 + m_b2 * m_x2
                   - m_a1 * m_y1 - m_a2 * m_y2;
        m_x2 = m_x1; m_x1 = x0;
        m_y2 = m_y1; m_y1 = y0;
        // clamp
        y0 = std::clamp(y0, -32768.0, 32767.0);
        samples[i] = static_cast<int16_t>(y0);
    }

    // ---- 2. Compute RMS of this chunk ----
    double sumSq = 0.0;
    for (int i = 0; i < count; ++i) {
        double s = samples[i] / 32768.0;
        sumSq += s * s;
    }
    float rms = static_cast<float>(std::sqrt(sumSq / count));

    // ---- 3. AGC (envelope follower) — BEFORE noise gate ----
    // Must amplify first, otherwise quiet mic signals are gated out
    if (m_agcEnabled && rms > 1e-6f) {
        constexpr float TARGET = 0.15f;  // target RMS ~ -16 dBFS
        float desired = TARGET / rms;
        // faster convergence for quiet signals
        float alpha = (desired > m_agcGain) ? 0.15f : 0.05f;
        m_agcGain += alpha * (desired - m_agcGain);
        m_agcGain = std::clamp(m_agcGain, 0.1f, 10.0f);  // cap at 20 dB to limit noise amplification
        for (int i = 0; i < count; ++i) {
            float v = samples[i] * m_agcGain;
            samples[i] = static_cast<int16_t>(std::clamp(v, -32768.0f, 32767.0f));
        }
        // Recompute RMS after AGC for accurate noise gate
        sumSq = 0.0;
        for (int i = 0; i < count; ++i) {
            double s = samples[i] / 32768.0;
            sumSq += s * s;
        }
        rms = static_cast<float>(std::sqrt(sumSq / count));
    }

    // ---- 4. Noise gate (on AGC-amplified signal) ----
    if (rms < m_gateThreshold) {
        if (!m_gateOpen) {
            std::memset(samples, 0, count * sizeof(int16_t));
            return;
        }
        // hysteresis: gate opened, keep open until well below threshold
        if (rms < m_gateThreshold * 0.6f) {
            m_gateOpen = false;
            std::memset(samples, 0, count * sizeof(int16_t));
            return;
        }
    } else {
        m_gateOpen = true;
    }

    // ---- 5. RMS normalization (optional) ----
    if (m_normTarget > 0.0f && rms > 1e-6f) {
        float gain = m_normTarget / rms;
        gain = std::min(gain, 10.0f);  // cap at 20 dB boost
        for (int i = 0; i < count; ++i) {
            float v = samples[i] * gain;
            samples[i] = static_cast<int16_t>(std::clamp(v, -32768.0f, 32767.0f));
        }
    }
}

// ═══════════════════════════════════════════════════════
//  VADEngine
// ═══════════════════════════════════════════════════════

VADEngine::VADEngine(QObject *parent)
    : QObject(parent)
{}

VADEngine::~VADEngine()
{
    if (m_sileroWs) {
        m_sileroWs->close();
    }
}

bool VADEngine::initialize(Backend preferred, const QString &sileroUrl)
{
    m_sileroUrl = sileroUrl;
    m_sileroFlapCount = 0;
    m_sileroReconnectDisabled = false;
    m_sileroConnectedClock.invalidate();
    m_sileroFlapWindow.restart();

    if (preferred == Backend::SileroONNX || preferred == Backend::Hybrid) {
        // Connect to Silero VAD server via WebSocketClient
        m_sileroWs = new WebSocketClient("VAD", this);
        m_sileroWs->setReconnectParams(3000, 0, false);  // 3s fixed, infinite
        connect(m_sileroWs, &WebSocketClient::connected,
                this, &VADEngine::onSileroConnected);
        connect(m_sileroWs, &WebSocketClient::disconnected,
                this, &VADEngine::onSileroDisconnected);
        connect(m_sileroWs, &WebSocketClient::textReceived,
                this, &VADEngine::onSileroMessage);
        m_sileroWs->open(QUrl(sileroUrl));

        m_backend = preferred;
        hVoice() << "VAD initialisé (backend:"
                 << (preferred == Backend::SileroONNX ? "Silero" : "Hybrid")
                 << "url:" << sileroUrl << ")";
    } else {
        m_backend = Backend::Builtin;
        hVoice() << "VAD initialisé (backend: Builtin energy+ZCR)";
    }

    resetNoiseEstimate();
    return true;
}

void VADEngine::setThreshold(float t)
{
    m_threshold = t;
    // Forward to Silero server if connected
    if (m_sileroWs && m_sileroWs->isConnected()) {
        QJsonObject cfg;
        cfg["type"] = "config";
        cfg["threshold"] = static_cast<double>(t);
        m_sileroWs->sendJson(cfg);
    }
}

void VADEngine::onSileroConnected()
{
    m_sileroConnectedClock.restart();
    if (!m_sileroFlapWindow.isValid() || m_sileroFlapWindow.elapsed() > SILERO_FLAP_WINDOW_MS) {
        m_sileroFlapWindow.restart();
        m_sileroFlapCount = 0;
    }
    hVoice() << "Silero VAD serveur connecté";
}

void VADEngine::onSileroDisconnected()
{
    if (m_sileroConnectedClock.isValid()
        && m_sileroConnectedClock.elapsed() < SILERO_MIN_UPTIME_MS) {
        if (!m_sileroFlapWindow.isValid() || m_sileroFlapWindow.elapsed() > SILERO_FLAP_WINDOW_MS) {
            m_sileroFlapWindow.restart();
            m_sileroFlapCount = 0;
        }
        ++m_sileroFlapCount;
    } else {
        m_sileroFlapCount = 0;
    }

    if (!m_sileroReconnectDisabled && m_sileroFlapCount >= SILERO_MAX_FLAPS && m_sileroWs) {
        m_sileroWs->setReconnectEnabled(false);
        m_sileroReconnectDisabled = true;
        hWarning(exoVoice) << "Silero VAD instable (flapping) — reconnection désactivée, fallback Builtin";
        return;
    }

    hVoice() << "Silero VAD serveur déconnecté — fallback Builtin";
    // Reconnection automatique gérée par WebSocketClient
}

void VADEngine::onSileroMessage(const QString &msg)
{
    QJsonDocument doc = QJsonDocument::fromJson(msg.toUtf8());
    if (!doc.isObject()) return;
    QJsonObject obj = doc.object();
    QString type = obj["type"].toString();

    if (type == "vad") {
        m_sileroScore = static_cast<float>(obj["score"].toDouble());
    } else if (type == "ready") {
        hVoice() << "Silero VAD prêt — modèle:" << obj["model"].toString();
    }
}

void VADEngine::sendSileroAudio(const int16_t *s, int n)
{
    if (!m_sileroWs || !m_sileroWs->isConnected()) return;
    QByteArray data(reinterpret_cast<const char *>(s), n * sizeof(int16_t));
    m_sileroWs->sendBinary(data);
}

void VADEngine::resetNoiseEstimate()
{
    m_noiseFloor = 0.0f;
    m_noiseCalibrated = false;
    m_calibrationFrames = 0;
    m_speechFrames = 0;
    m_silenceFrames = 0;
    m_isSpeech = false;
}

float VADEngine::builtinScore(const int16_t *s, int n)
{
    if (n <= 0) return 0.0f;

    // RMS energy (normalized 0..1)
    double sumSq = 0.0;
    for (int i = 0; i < n; ++i) {
        double v = s[i] / 32768.0;
        sumSq += v * v;
    }
    float rms = static_cast<float>(std::sqrt(sumSq / n));

    // Zero-crossing rate (normalized 0..1, speech ~0.05-0.15)
    int zc = 0;
    for (int i = 1; i < n; ++i) {
        if ((s[i] >= 0) != (s[i - 1] >= 0)) ++zc;
    }
    float zcr = static_cast<float>(zc) / static_cast<float>(n);

    // Adaptive noise floor (updated only during non-speech)
    if (!m_noiseCalibrated) {
        m_noiseFloor += rms;
        ++m_calibrationFrames;
        if (m_calibrationFrames >= CALIBRATION_WINDOW) {
            m_noiseFloor /= CALIBRATION_WINDOW;
            m_noiseCalibrated = true;
            hVoice() << "VAD noise floor calibré:" << m_noiseFloor;
        }
        return 0.0f; // no detection during calibration
    }

    // Update noise floor slowly when NOT in speech
    if (!m_isSpeech) {
        m_noiseFloor = 0.95f * m_noiseFloor + 0.05f * rms;
    }

    // Signal-to-noise ratio score
    float snr = (m_noiseFloor > 1e-6f) ? (rms / m_noiseFloor) : rms * 100.0f;

    // Composite score: weigh energy heavily, penalize very high ZCR (noise)
    // Speech typically has moderate ZCR (0.02-0.2) and high energy above noise
    float zcrPenalty = (zcr > 0.35f) ? 0.5f : 1.0f;
    float score = std::min(1.0f, (snr - 1.0f) / 5.0f) * zcrPenalty;
    score = std::clamp(score, 0.0f, 1.0f);

    return score;
}

float VADEngine::processChunk(const int16_t *samples, int count)
{
    float builtinS = builtinScore(samples, count);
    float score = builtinS;

    bool sileroUp = m_sileroWs && m_sileroWs->isConnected();

    // Send audio to Silero if backend requires it
    if ((m_backend == Backend::SileroONNX || m_backend == Backend::Hybrid)
        && sileroUp) {
        sendSileroAudio(samples, count);
    }

    switch (m_backend) {
    case Backend::Builtin:
        score = builtinS;
        break;
    case Backend::SileroONNX:
        // Use Silero score if connected, else fallback to builtin
        score = sileroUp ? m_sileroScore : builtinS;
        break;
    case Backend::Hybrid:
        // Weighted combination: Silero is more accurate, builtin is low-latency
        if (sileroUp)
            score = 0.3f * builtinS + 0.7f * m_sileroScore;
        else
            score = builtinS;
        break;
    }

    updateSpeechState(score);
    return score;
}

void VADEngine::updateSpeechState(float score)
{
    bool frameIsSpeech = score >= m_threshold;

    if (frameIsSpeech) {
        ++m_speechFrames;
        m_silenceFrames = 0;
    } else {
        ++m_silenceFrames;
        // don't reset m_speechFrames immediately — hang period
    }

    if (!m_isSpeech) {
        // transition to speech
        if (m_speechFrames >= SPEECH_START_FRAMES) {
            m_isSpeech = true;
            emit speechStarted();
        }
    } else {
        // transition to silence
        if (m_silenceFrames >= SPEECH_HANG_FRAMES) {
            m_isSpeech = false;
            m_speechFrames = 0;
            emit speechEnded();
        }
    }
}

// ═══════════════════════════════════════════════════════
//  StreamingSTT — WebSocket client for stt_server.py
// ═══════════════════════════════════════════════════════

StreamingSTT::StreamingSTT(QObject *parent)
    : QObject(parent)
{}

StreamingSTT::~StreamingSTT()
{
    if (m_ws) {
        m_ws->close();
    }
}

bool StreamingSTT::initialize(const QString &serverUrl)
{
    if (m_ws) {
        m_ws->close();
        m_ws->deleteLater();
    }

    m_ws = new WebSocketClient("STT", this);
    m_ws->setReconnectParams(1000, 10, true);  // exponential backoff, max 10
    connect(m_ws, &WebSocketClient::connected,
            this, &StreamingSTT::onWsConnected);
    connect(m_ws, &WebSocketClient::disconnected,
            this, &StreamingSTT::onWsDisconnected);
    connect(m_ws, &WebSocketClient::textReceived,
            this, &StreamingSTT::onWsTextMessage);

    hVoice() << "StreamingSTT: connexion à" << serverUrl;
    m_ws->open(QUrl(serverUrl));
    return true;  // async — actual availability set on connect
}

void StreamingSTT::onWsConnected()
{
    m_connected = true;
    hVoice() << "StreamingSTT: connecté au serveur STT";
    emit connected();

    // Send initial config
    QJsonObject cfg;
    cfg["type"] = "config";
    cfg["language"] = m_language;
    cfg["beam_size"] = m_beamSize;
    m_ws->sendJson(cfg);
}

void StreamingSTT::onWsDisconnected()
{
    m_connected = false;
    m_recording = false;
    QWebSocket *raw = m_ws->socket();
    hWarning(exoVoice) << "StreamingSTT: DÉCONNECTÉ du serveur STT"
                        << "— closeCode:" << (raw ? raw->closeCode() : 0)
                        << "closeReason:" << (raw ? raw->closeReason() : QString())
                        << "errorString:" << (raw ? raw->errorString() : QString());
    emit disconnected();
    // Reconnection automatique gérée par WebSocketClient
}

void StreamingSTT::onWsTextMessage(const QString &msg)
{
    QJsonDocument doc = QJsonDocument::fromJson(msg.toUtf8());
    if (!doc.isObject()) return;
    QJsonObject obj = doc.object();
    QString type = obj["type"].toString();

    if (type == "partial") {
        QString text = obj["text"].toString();
        if (!text.isEmpty()) {
            emit partialTranscript(text);
        }
    } else if (type == "final") {
        QString text = obj["text"].toString();
        hVoice() << "STT final:" << text;
        emit finalTranscript(text);
    } else if (type == "ready") {
        hVoice() << "STT server prêt — modèle:" << obj["model"].toString()
                 << "device:" << obj["device"].toString();
    } else if (type == "error") {
        emit error(obj["message"].toString());
    }
}

void StreamingSTT::startUtterance()
{
    if (!m_connected) {
        emit error("STT server non connecté");
        return;
    }
    m_recording = true;
    QJsonObject msg;
    msg["type"] = "start";
    m_ws->sendJson(msg);
}

void StreamingSTT::feedAudio(const int16_t *samples, int count)
{
    if (!m_connected || !m_recording || count <= 0) return;

    // Send raw PCM16 as binary WebSocket frame
    QByteArray data(reinterpret_cast<const char *>(samples),
                    count * static_cast<int>(sizeof(int16_t)));
    m_ws->sendBinary(data);
}

void StreamingSTT::endUtterance()
{
    hVoice() << "endUtterance: connected=" << m_connected
             << "recording=" << m_recording
             << "wsState=" << (m_ws && m_ws->socket() ? static_cast<int>(m_ws->socket()->state()) : -1);
    if (!m_connected) {
        hWarning(exoVoice) << "endUtterance: STT non connecté — abandon";
        return;
    }
    m_recording = false;
    QJsonObject msg;
    msg["type"] = "end";
    m_ws->sendJson(msg);
    hVoice() << "endUtterance: message 'end' envoyé au STT";
}

void StreamingSTT::cancelUtterance()
{
    if (!m_connected) return;
    m_recording = false;
    QJsonObject msg;
    msg["type"] = "cancel";
    m_ws->sendJson(msg);
}

void StreamingSTT::transcribeBuffer(const std::vector<int16_t> &pcm)
{
    // Non-streaming fallback: send entire buffer at once
    if (!m_connected || pcm.empty()) {
        emit error("STT non disponible ou audio vide");
        return;
    }

    startUtterance();
    feedAudio(pcm.data(), static_cast<int>(pcm.size()));
    endUtterance();
}

void StreamingSTT::setLanguage(const QString &lang)
{
    m_language = lang;
    if (m_connected) {
        QJsonObject cfg;
        cfg["type"] = "config";
        cfg["language"] = lang;
        m_ws->sendJson(cfg);
    }
}

void StreamingSTT::setBeamSize(int beam)
{
    m_beamSize = beam;
    if (m_connected) {
        QJsonObject cfg;
        cfg["type"] = "config";
        cfg["beam_size"] = beam;
        m_ws->sendJson(cfg);
    }
}

// ═══════════════════════════════════════════════════════
//  VoicePipeline — main orchestrator
// ═══════════════════════════════════════════════════════

VoicePipeline::VoicePipeline(QObject *parent)
    : QObject(parent)
    , m_ringBuf(SAMPLE_RATE * 10) // 10 s ring buffer
{
    m_ttsEndClock.start();
    m_lastWakeWordClock.start();
    m_interactionClock.start();

    // Initialize default wake-word variants (accept both Jarvis and EXO)
    m_wakeVariants << "jarvis" << "jarvice" << "jarvi" << "jarviss" << "garvis"
                   << "exo" << "egzo" << "ekso" << "exho" << "exau"
                   << "eczau" << "egzau" << "ekzo";

    m_utteranceTimer = new QTimer(this);
    m_utteranceTimer->setSingleShot(true);
    connect(m_utteranceTimer, &QTimer::timeout,
            this, &VoicePipeline::onUtteranceTimeout);

    m_conversationTimer = new QTimer(this);
    m_conversationTimer->setSingleShot(true);
    connect(m_conversationTimer, &QTimer::timeout, this, [this]() {
        m_conversationActive = false;
        hVoice() << "Mode conversation expiré";
    });

    m_transcribeTimer = new QTimer(this);
    m_transcribeTimer->setSingleShot(true);
    connect(m_transcribeTimer, &QTimer::timeout,
            this, &VoicePipeline::onTranscribeTimeout);
}

VoicePipeline::~VoicePipeline()
{
    stopListening();
}

// ── initialisation ───────────────────────────────────

bool VoicePipeline::initAudio()
{
    m_format.setSampleRate(SAMPLE_RATE);
    m_format.setChannelCount(1);
    m_format.setSampleFormat(QAudioFormat::Int16);

    // ── AudioDeviceManager ──
    if (!m_audioDeviceManager) {
        m_audioDeviceManager = new AudioDeviceManager(this);
        connect(m_audioDeviceManager, &AudioDeviceManager::deviceSwitchRequested,
                this, &VoicePipeline::onDeviceSwitchRequested);
        connect(m_audioDeviceManager, &AudioDeviceManager::audioUnavailable,
                this, [this]() {
                    emit voiceError("Aucun microphone détecté");
                    emit audioUnavailable();
                });
        connect(m_audioDeviceManager, &AudioDeviceManager::audioReady,
                this, [this]() { emit audioReady(); });
    }

    // Vérifier qu'un micro est disponible
    if (!m_audioDeviceManager->hasValidInputDevice()) {
        hVoice() << "Aucun microphone détecté — mode clavier activé";
        emit voiceError("Aucun microphone détecté");
        emit audioUnavailable();
        return false;
    }

    // Create backend based on config
    m_audioInput.reset();
#ifdef ENABLE_RTAUDIO
    if (m_audioBackend == "rtaudio") {
        m_audioInput = std::make_unique<AudioInputRtAudio>(this);
    } else
#endif
    {
        m_audioInput = std::make_unique<AudioInputQt>(this);
    }

    connect(m_audioInput.get(), &AudioInput::error,
            this, [this](const QString &msg) {
                hVoice() << "Audio backend erreur:" << msg;
                emit voiceError(msg);
            });

    // Set callback: preprocess + feed pipeline + feed device manager RMS
    m_audioInput->setCallback([this](const int16_t *samples, int count) {
        auto copy = std::make_shared<std::vector<int16_t>>(samples, samples + count);
        QMetaObject::invokeMethod(this, [this, copy]() {
            onAudioSamples(copy->data(), static_cast<int>(copy->size()));
        }, Qt::QueuedConnection);
        // Feed RMS to device manager (thread-safe)
        if (m_audioDeviceManager)
            m_audioDeviceManager->feedRmsSamples(samples, count);
    });

    if (!m_audioInput->open(SAMPLE_RATE, 1)) {
        emit voiceError("Impossible d'ouvrir le backend audio");
        return false;
    }

    // Notifier le device manager que le stream est prêt
    m_audioDeviceManager->notifyStreamOpened();
    m_audioDeviceManager->startHealthCheck(5000);

    hVoice() << "Audio initialisé — backend:" << m_audioInput->backendName()
             << "rate:" << m_format.sampleRate();
    return true;
}

bool VoicePipeline::initVAD(VADEngine::Backend preferred, const QString &sileroUrl)
{
    m_vad = std::make_unique<VADEngine>(this);
    connect(m_vad.get(), &VADEngine::speechStarted,
            this, &VoicePipeline::onVADSpeechStarted);
    connect(m_vad.get(), &VADEngine::speechEnded,
            this, &VoicePipeline::onVADSpeechEnded);
    return m_vad->initialize(preferred, sileroUrl);
}

bool VoicePipeline::initSTT(const QString &serverUrl)
{
    m_stt = std::make_unique<StreamingSTT>(this);
    connect(m_stt.get(), &StreamingSTT::partialTranscript,
            this, &VoicePipeline::onSTTPartial);
    connect(m_stt.get(), &StreamingSTT::finalTranscript,
            this, &VoicePipeline::onSTTFinal);
    connect(m_stt.get(), &StreamingSTT::error,
            this, [this](const QString &e) {
                hVoice() << "STT erreur:" << e;
                onSTTError(e);
            });
    connect(m_stt.get(), &StreamingSTT::connected,
            this, [this]() {
                hVoice() << "STT server connecté — streaming STT actif";
            });
    return m_stt->initialize(serverUrl);
}

void VoicePipeline::initTTS(const QString &ttsServerUrl)
{
    m_ttsServerUrl = ttsServerUrl;
    m_ttsManager = new TTSManager(this);
    m_ttsManager->initTTS(ttsServerUrl);
    m_ttsManager->initDSP();

    // Pass WebSocket for GUI broadcast
    if (m_ws)
        m_ttsManager->setWebSocket(m_ws);

    connect(m_ttsManager, &TTSManager::ttsStarted,
            this, &VoicePipeline::onTtsStarted);
    connect(m_ttsManager, &TTSManager::ttsFinished,
            this, &VoicePipeline::onTtsFinished);
    connect(m_ttsManager, &TTSManager::ttsError,
            this, &VoicePipeline::onTtsError);
    connect(m_ttsManager, &TTSManager::ttsPcmForVisualization,
            this, &VoicePipeline::ttsPcmForVisualization);
        connect(m_ttsManager, &TTSManager::ttsVoicesChanged,
            this, &VoicePipeline::ttsVoicesChanged, Qt::UniqueConnection);

        // Prime the voices list once TTS server/model reach ready_online.
        QTimer::singleShot(250, this, [this]() {
        if (m_ttsManager)
            m_ttsManager->fetchAvailableVoices();
        });

    hVoice() << "TTSManager initialisé avec DSP pipeline";
    hVoice() << "[Pipeline] GPU STT/TTS: RTX 3070";
    hVoice() << "[Pipeline] GPU GUI: AMD";
    hVoice() << "[Latency] Targets: STT < 300 ms | TTS < 800 ms | Pipeline < 1500 ms";
    hVoice() << "[Latency] TTS guard:" << TTS_GUARD_MS << "ms | Wake cooldown:" << WAKE_COOLDOWN_MS << "ms"
             << "| Min utterance:" << MIN_UTTERANCE_MS << "ms";
}

// ── OpenWakeWord server integration ──────────────────

void VoicePipeline::initWakeWordServer(const QString &url)
{
    if (m_wakewordWs) {
        m_wakewordWs->close();
        m_wakewordWs->deleteLater();
    }
    m_wakewordWs = new WebSocketClient("WakeWord", this);
    m_wakewordWs->setReconnectParams(5000, 0, false);  // 5s fixed, infinite
    connect(m_wakewordWs, &WebSocketClient::connected,
            this, &VoicePipeline::onWakeWordWsConnected);
    connect(m_wakewordWs, &WebSocketClient::disconnected,
            this, &VoicePipeline::onWakeWordWsDisconnected);
    connect(m_wakewordWs, &WebSocketClient::textReceived,
            this, &VoicePipeline::onWakeWordWsMessage);
    m_wakewordWs->open(QUrl(url));
    hVoice() << "Connecting to OpenWakeWord server:" << url;
}

void VoicePipeline::onWakeWordWsConnected()
{
    hVoice() << "OpenWakeWord server connected";
}

void VoicePipeline::onWakeWordWsDisconnected()
{
    hWarning(exoVoice) << "OpenWakeWord server disconnected — fallback transcript detection";
    // Reconnection automatique gérée par WebSocketClient
}

void VoicePipeline::onWakeWordWsMessage(const QString &msg)
{
    QJsonDocument doc = QJsonDocument::fromJson(msg.toUtf8());
    if (!doc.isObject()) return;
    QJsonObject obj = doc.object();
    if (obj["type"].toString() == "wakeword") {
        float score = static_cast<float>(obj["score"].toDouble());
        QString word = obj["word"].toString();
        // Only arm capture from Idle state, require score > 0.7, and enforce cooldown
        if (score > 0.7f && m_state == PipelineState::Idle
            && m_lastWakeWordClock.elapsed() > WAKE_COOLDOWN_MS
            && m_ttsEndClock.elapsed() > TTS_GUARD_MS) {
            hVoice() << "OpenWakeWord detected:" << word << "score:" << score;
            // Démarrer l'interaction dès le wake-word pour corréler VAD/STT
            PipelineEventBus::instance()->beginInteraction();
            PIPELINE_EVENT(PipelineModule::WakeWord, EventType::WakeWordDetected,
                           {{"word", word}, {"score", score}, {"source", "neural"}});
            m_wakeWordTriggered = true;
            m_lastWakeWordClock.restart();
            emit wakeWordDetected();
            emit statusChanged("EXO écoute...");
        }
    }
}

// ── start / stop ─────────────────────────────────────

void VoicePipeline::startListening()
{
    if (m_audioRunning) return;

    if (!m_audioInput) {
        emit voiceError("Backend audio non initialisé");
        return;
    }

    if (!m_audioInput->start()) {
        emit voiceError("Impossible de démarrer la capture audio");
        return;
    }

    m_audioRunning = true;
    setState(PipelineState::Idle);
    emit listeningChanged();
    MetricsManager::instance()->increment(QStringLiteral("voice.pipeline.starts"));

    if (m_vad)
        m_vad->resetNoiseEstimate();

    hVoice() << "Pipeline démarré — wake-word logiciel '" << m_wakeKeyword << "' (détection dans transcript)";
}

void VoicePipeline::stopListening()
{
    if (!m_audioRunning) return;

    if (m_audioInput) {
        m_audioInput->stop();
    }
    if (m_audioDeviceManager)
        m_audioDeviceManager->notifyStreamClosed();

    m_audioRunning = false;
    m_utteranceTimer->stop();
    setState(PipelineState::Idle);
    emit listeningChanged();
    hVoice() << "Pipeline arrêté";
}

void VoicePipeline::speak(const QString &text)
{
    if (text.isEmpty() || !m_ttsManager) return;
    MetricsManager::instance()->increment(QStringLiteral("tts.speak_requests"));

    if (m_vadInteraction)
        hVoice() << "[Latency] speak() called (" << m_interactionClock.elapsed() << "ms since VAD)";
    else
        hVoice() << "[Latency] speak() called (manual request — no VAD)";
    PIPELINE_EVENT(PipelineModule::TTS, EventType::SpeakRequested,
                   {{"text_length", text.length()},
                    {"preview", text.left(80)}});

    // Stop capture while speaking to avoid self-triggering
    if (m_audioInput)
        m_audioInput->suspend();

    hVoice() << "TTS:" << text.left(80) << "...";
    m_ttsManager->speakText(text);
}

void VoicePipeline::speakSentence(const QString &text)
{
    if (text.isEmpty() || !m_ttsManager) return;

    PIPELINE_EVENT(PipelineModule::TTS, EventType::SentenceEnqueued,
                   {{"text_length", text.length()},
                    {"preview", text.left(80)}});

    // Suspend capture to avoid self-triggering
    if (m_audioInput)
        m_audioInput->suspend();

    hVoice() << "TTS sentence:" << text.left(80) << "...";
    m_ttsManager->enqueueSentence(text);
}

void VoicePipeline::resetBuffers()
{
    m_utteranceBuf.clear();
    m_ringBuf.clear();
    m_wakeWordTriggered = false;
    if (m_vad)
        m_vad->resetNoiseEstimate();
    hVoice() << "Buffers réinitialisés";
}

// ── tuning ───────────────────────────────────────────

void VoicePipeline::setWakeWordSensitivity(float s)
{
    Q_UNUSED(s) // wake-word sensitivity not used with software detection
    hVoice() << "Wake word sensitivity:" << s;
}

void VoicePipeline::setVADThreshold(float t)
{
    if (m_vad) m_vad->setThreshold(t);
    hVoice() << "VAD threshold:" << t;
}

void VoicePipeline::setNoiseGate(float rms)
{
    m_preproc.setNoiseGateThreshold(rms);
}

void VoicePipeline::setAGC(bool on)
{
    m_preproc.setAGCEnabled(on);
}

void VoicePipeline::setSTTServerUrl(const QString &url)
{
    if (m_stt) m_stt->initialize(url);
    hVoice() << "STT server URL:" << url;
}

void VoicePipeline::setSTTLanguage(const QString &lang)
{
    if (m_stt) m_stt->setLanguage(lang);
    hVoice() << "STT language:" << lang;
}

void VoicePipeline::setTTSVoice(const QString &name)
{
    QString selected = name.trimmed();
    // Only substitute when name is empty — all declared voices (incl. exo_default,
    // fr_vivienne, etc.) are valid and must be forwarded to the Python TTS engine.
    if (selected.isEmpty()) {
        selected = QStringLiteral("fr_denise");
    }
    if (m_ttsManager) m_ttsManager->setVoice(selected);
    hVoice() << "TTS voice:" << selected;
}

void VoicePipeline::setTTSLanguage(const QString &lang)
{
    if (m_ttsManager) m_ttsManager->setLanguage(lang);
    hVoice() << "TTS language:" << lang;
}

void VoicePipeline::setTTSStyle(const QString &style)
{
    if (m_ttsManager) m_ttsManager->setStyle(style);
    hVoice() << "TTS style:" << style;
}

void VoicePipeline::setTTSEngine(const QString &engine)
{
    QString url;
    if (engine == "cosyvoice2" || engine == "cosyvoice2_cuda" || engine == "cosyvoice2_cpu" || engine == "cosyvoice2_auto"
        || engine == "xtts_directml" || engine == "xtts_cuda" || engine == "xtts_auto"
        || engine == "orpheus" || engine == "orpheus_cuda" || engine == "orpheus_gguf")
        url = m_ttsServerUrl.isEmpty() ? QStringLiteral("ws://localhost:8767") : m_ttsServerUrl;
    else // qt_fallback or unknown
        url = QString();

    if (m_ttsManager) m_ttsManager->setPythonUrl(url);
    hVoice() << "TTS engine:" << engine << "-> URL:" << url;
}

void VoicePipeline::setTTSOutputDevice(const QString &deviceName)
{
    if (m_ttsManager) m_ttsManager->setOutputDevicePreference(deviceName);
    hVoice() << "TTS output device:" << deviceName;
}

void VoicePipeline::setTTSPitch(float p)
{
    // Backward compatibility: configs often store pitch as multiplier (1.0 = neutral).
    // Internal pipeline expects centered value (-1..1, 0 = neutral).
    float normalized = p;
    if (p >= 0.0f && p <= 2.0f) {
        normalized = p - 1.0f;
    }
    normalized = std::clamp(normalized, -0.3f, 0.3f);

    if (m_ttsManager) m_ttsManager->setPitch(normalized);
    hVoice() << "TTS pitch:" << p << "-> normalized:" << normalized;
}

void VoicePipeline::setTTSRate(float r)
{
    // Backward compatibility: configs often store rate as multiplier (1.0 = neutral).
    // Internal pipeline expects centered value (-1..1, 0 = neutral).
    float normalized = r;
    if (r >= 0.0f && r <= 2.0f) {
        normalized = r - 1.0f;
    }
    normalized = std::clamp(normalized, -0.35f, 0.25f);

    if (m_ttsManager) m_ttsManager->setRate(normalized);
    hVoice() << "TTS rate:" << r << "-> normalized:" << normalized;
}

void VoicePipeline::fetchTTSVoices()
{
    if (m_ttsManager) {
        connect(m_ttsManager, &TTSManager::ttsVoicesChanged,
                this, &VoicePipeline::ttsVoicesChanged, Qt::UniqueConnection);
        m_ttsManager->fetchAvailableVoices();
    }
}

QStringList VoicePipeline::ttsVoices() const
{
    return m_ttsManager ? m_ttsManager->ttsVoices() : QStringList();
}

void VoicePipeline::setAudioBackend(const QString &backend)
{
    QString b = backend.toLower().trimmed();
#ifndef ENABLE_RTAUDIO
    if (b == "rtaudio") {
        hVoice() << "RtAudio non disponible dans cette build, fallback Qt";
        b = "qt";
    }
#endif
    if (b != "qt" && b != "rtaudio") b = "qt";
    m_audioBackend = b;
    hVoice() << "Audio backend sélectionné:" << m_audioBackend;
}

void VoicePipeline::onDeviceSwitchRequested(int /*rtAudioDeviceId*/)
{
    hVoice() << "Changement de micro demandé — redémarrage du stream audio";

    bool wasRunning = m_audioRunning.load();

    // Fermer le stream actuel
    if (m_audioInput) {
        m_audioInput->stop();
        if (m_audioDeviceManager)
            m_audioDeviceManager->notifyStreamClosed();
    }
    m_audioInput.reset();

    // Recréer le backend audio
    if (initAudio() && wasRunning) {
        startListening();
        emit audioReady();
    }
}

void VoicePipeline::setWakeWord(const QString &word)
{
    m_wakeKeyword = word.toLower().trimmed();
    // Rebuild variants: primary keyword + common phonetic variants for "exo"
    m_wakeVariants.clear();
    m_wakeVariants << m_wakeKeyword;
    // Always accept both Jarvis and EXO as wake words
    m_wakeVariants << "jarvis" << "jarvice" << "jarvi" << "jarviss" << "garvis"
                   << "exo" << "egzo" << "ekso" << "exho" << "exau"
                   << "eczau" << "egzau" << "ekzo";
    m_wakeVariants.removeDuplicates();
    hVoice() << "Wake-word:" << m_wakeKeyword << "variants:" << m_wakeVariants;
}

void VoicePipeline::setWakeWords(const QStringList &words)
{
    m_wakeVariants.clear();
    for (const QString &w : words) {
        QString clean = w.toLower().trimmed();
        clean.remove(QRegularExpression("[!?.,;]"));
        if (!clean.isEmpty() && !m_wakeVariants.contains(clean))
            m_wakeVariants << clean;
    }
    if (!m_wakeVariants.isEmpty())
        m_wakeKeyword = m_wakeVariants.first();
    hVoice() << "Wake-words:" << m_wakeVariants;
}

// ── WebSocket bridge ─────────────────────────────────

void VoicePipeline::connectToServer(const QString &url)
{
    if (m_ws) {
        m_ws->close();
        m_ws->deleteLater();
    }
    m_ws = new QWebSocket(QString(), QWebSocketProtocol::VersionLatest, this);
    connect(m_ws, &QWebSocket::textMessageReceived,
            this, &VoicePipeline::onWsTextMessage);
    connect(m_ws, &QWebSocket::binaryMessageReceived,
            this, &VoicePipeline::onWsBinaryMessage);
    connect(m_ws, &QWebSocket::connected, this, [this]() {
        hVoice() << "WebSocket connecté";
        broadcastState();
    });
    connect(m_ws, &QWebSocket::disconnected, this, [this, url]() {
        hVoice() << "WebSocket déconnecté — reconnexion dans 5s";
        QTimer::singleShot(5000, this, [this, url]() { connectToServer(url); });
    });
    m_ws->open(QUrl(url));
}

void VoicePipeline::sendWebSocketMessage(const QString &message)
{
    if (m_ws && m_ws->isValid()) {
        m_ws->sendTextMessage(message);
    } else {
        hWarning(exoVoice) << "WebSocket non connecté — message perdu";
    }
}

void VoicePipeline::onWsTextMessage(const QString &msg)
{
    // Messages from exo_server.py (e.g. TTS response)
    QJsonDocument doc = QJsonDocument::fromJson(msg.toUtf8());
    if (!doc.isObject()) return;
    QJsonObject obj = doc.object();
    QString type = obj["type"].toString();

    if (type == "tts") {
        speak(obj["text"].toString());
    }
}

void VoicePipeline::onWsBinaryMessage(const QByteArray &msg)
{
    Q_UNUSED(msg)
}

// ── audio callback (from AudioInput backend) ─────────

void VoicePipeline::onAudioSamples(const int16_t *samples, int count)
{
    if (count <= 0) return;

    // Work on a mutable copy for preprocessing
    std::vector<int16_t> chunk(samples, samples + count);

    // P1.1: Protect preprocessor state from RtAudio thread race condition
    {
        QMutexLocker lk(&m_preprocMutex);
        m_preproc.process(chunk.data(), count);
    }

    // Write to ring buffer
    m_ringBuf.write(chunk.data(), count);

    // Process in CHUNK_SAMPLES-sized blocks
    processAudioChunk(chunk.data(), count);
}

// ── core pipeline ────────────────────────────────────

void VoicePipeline::processAudioChunk(const int16_t *samples, int count)
{
    if (m_state == PipelineState::Speaking) return;

    // Guard against self-triggering right after TTS
    if (m_ttsEndClock.elapsed() < TTS_GUARD_MS) return;

    // ── VAD scoring ──
    float vadScore = 0.0f;
    if (m_vad) {
        vadScore = m_vad->processChunk(samples, count);
    } else {
        hWarning(exoVoice) << "processAudioChunk: m_vad est nullptr — VAD désactivé";
        return;
    }

    // ── Compute RMS for UI ──
    double sumSq = 0.0;
    for (int i = 0; i < count; ++i) {
        double v = samples[i] / 32768.0;
        sumSq += v * v;
    }
    float rms = static_cast<float>(std::sqrt(sumSq / count));
    broadcastAudioLevel(rms, vadScore);
    emit audioLevel(rms, vadScore);

    // ── Emit downsampled PCM for QML waveform visualization ──
    emit micPcmForVisualization(downsampleForVisualization(samples, count));

    switch (m_state) {
    case PipelineState::Idle: {
        // Send audio to OpenWakeWord server for neural wake word detection
        if (m_wakewordWs && m_wakewordWs->isConnected()) {
            QByteArray pcmData(reinterpret_cast<const char*>(samples),
                               count * sizeof(int16_t));
            m_wakewordWs->sendBinary(pcmData);
        }
        // Wakeword-first gating:
        // - si le serveur wakeword est connecté, on n'ouvre STT en Idle qu'après wakeword neural
        // - sinon fallback legacy (VAD-only) pour conserver un mode dégradé fonctionnel
        const bool wakewordOnline = (m_wakewordWs && m_wakewordWs->isConnected());
        const bool allowIdleCapture = (!wakewordOnline) || m_wakeWordTriggered;

        // VAD déclenche le passage en DetectingSpeech uniquement après confirmation
        // (évite les faux positifs sur pics isolés de score).
        if (allowIdleCapture && m_vad && m_vad->isSpeech() && vadScore >= m_vad->threshold()) {
            handleVAD(samples, count, vadScore);
        }
        break;
    }

    case PipelineState::DetectingSpeech:
        // Accumule audio + stream vers STT pendant le grace period
        handleRecording(samples, count);
        if (m_stt && m_stt->isConnected() && m_sttStreaming) {
            m_stt->feedAudio(samples, count);
        }
        break;

    case PipelineState::Listening:
        handleRecording(samples, count);
        // Stream audio to STT server in real-time
        if (m_stt && m_stt->isConnected() && m_sttStreaming) {
            m_stt->feedAudio(samples, count);
        }
        // End-of-speech detection via VAD (min 800ms pour éviter clips trop courts)
        if (m_vad && !m_vad->isSpeech()
            && m_utteranceBuf.size() > static_cast<size_t>(SAMPLE_RATE * MIN_UTTERANCE_MS / 1000)) {
            finishUtterance();
        }
        break;

    case PipelineState::Transcribing:
    case PipelineState::Thinking:
    case PipelineState::Speaking:
        break;
    }
}

void VoicePipeline::handleVAD(const int16_t *samples, int count, float vadScore)
{
    // VAD a détecté de la parole → commencer capture + streaming STT
    // Note: le cooldown wake-word ne doit PAS bloquer la détection de parole VAD

    if (m_lastIgnoredNoiseClock.isValid() && m_lastIgnoredNoiseClock.elapsed() < NOISE_REARM_MS) {
        return;
    }

    if (vadScore >= m_vad->threshold()) {
        hVoice() << "VAD: parole détectée (score:" << vadScore << ") → streaming STT";
        hVoice() << "[Latency] VAD → STT start";
        m_interactionClock.restart();  // v5.2: start end-to-end measurement
        m_vadInteraction = true;       // mark as VAD-triggered interaction
        m_utteranceBuf.clear();
        m_wakeWordTriggered = false;  // reset wake-word flag pour cette utterance
        setState(PipelineState::DetectingSpeech);
        emit speechStarted();
        emit statusChanged("Détection parole...");
        m_utteranceTimer->start(UTTERANCE_TIMEOUT_MS);

        // Start streaming STT immediately
        LatencyMetrics::instance()->markSttStart();
        if (m_stt && m_stt->isConnected()) {
            m_stt->startUtterance();
            m_sttStreaming = true;
            PIPELINE_EVENT(PipelineModule::STT, EventType::StreamStarted);
            PIPELINE_STATE(PipelineModule::STT, ModuleState::Active);
        }

        // Feed the triggering chunk so beginning of speech isn't lost
        handleRecording(samples, count);
        if (m_stt && m_stt->isConnected() && m_sttStreaming) {
            m_stt->feedAudio(samples, count);
        }

        // Grace period → passer en Listening
        QTimer::singleShot(POST_WAKE_GRACE_MS, this, [this]() {
            if (m_state == PipelineState::DetectingSpeech)
                setState(PipelineState::Listening);
        });
    }
}

// ── Wake-word logiciel : détection fuzzy + phonétique de "EXO" ──

int VoicePipeline::levenshteinDistance(const QString &a, const QString &b)
{
    const int m = a.length(), n = b.length();
    if (m == 0) return n;
    if (n == 0) return m;
    std::vector<int> prev(n + 1), curr(n + 1);
    for (int j = 0; j <= n; ++j) prev[j] = j;
    for (int i = 1; i <= m; ++i) {
        curr[0] = i;
        for (int j = 1; j <= n; ++j) {
            int cost = (a[i-1] == b[j-1]) ? 0 : 1;
            curr[j] = std::min({prev[j] + 1, curr[j-1] + 1, prev[j-1] + cost});
        }
        std::swap(prev, curr);
    }
    return prev[n];
}

bool VoicePipeline::checkWakeWord(const QString &text)
{
    QString lower = text.toLower();

    // Direct contains check for primary keyword
    if (lower.contains(m_wakeKeyword))
        return true;

    // Check all variants with fuzzy matching (Levenshtein ≤ 1)
    QStringList words = lower.split(QRegularExpression("[\\s,;.!?]+"), Qt::SkipEmptyParts);
    for (const QString &word : words) {
        for (const QString &variant : m_wakeVariants) {
            if (word == variant)
                return true;
            if (std::abs(word.length() - variant.length()) <= 1
                && levenshteinDistance(word, variant) <= 1)
                return true;
        }
    }
    return false;
}

QString VoicePipeline::findAndRemoveWakeWord(const QString &text)
{
    QString result = text;
    // Remove primary keyword
    result.remove(QRegularExpression("\\b" + QRegularExpression::escape(m_wakeKeyword) + "\\b",
                                     QRegularExpression::CaseInsensitiveOption));
    // Remove known variants
    for (const QString &variant : m_wakeVariants) {
        result.remove(QRegularExpression("\\b" + QRegularExpression::escape(variant) + "\\b",
                                         QRegularExpression::CaseInsensitiveOption));
    }
    // Remove fuzzy-matched words
    QStringList words = result.split(QRegularExpression("[\\s]+"), Qt::SkipEmptyParts);
    QStringList kept;
    for (const QString &word : words) {
        QString clean = word.toLower();
        clean.remove(QRegularExpression("[,;.!?]"));
        bool isWake = false;
        for (const QString &variant : m_wakeVariants) {
            if (std::abs(clean.length() - variant.length()) <= 1
                && levenshteinDistance(clean, variant) <= 1) {
                isWake = true;
                break;
            }
        }
        if (!isWake) kept.append(word);
    }
    return kept.join(" ").trimmed();
}

void VoicePipeline::handleRecording(const int16_t *samples, int count)
{
    // Append to utterance buffer (capped)
    size_t space = MAX_UTTERANCE_SAMPLES - m_utteranceBuf.size();
    size_t toAdd = std::min(static_cast<size_t>(count), space);
    m_utteranceBuf.insert(m_utteranceBuf.end(), samples, samples + toAdd);

    if (m_utteranceBuf.size() >= MAX_UTTERANCE_SAMPLES) {
        hVoice() << "Utterance buffer plein — fin de capture";
        finishUtterance();
    }
}

void VoicePipeline::finishUtterance()
{
    m_utteranceTimer->stop();
    PIPELINE_EVENT(PipelineModule::STT, EventType::UtteranceFinished,
                   {{"samples", static_cast<qint64>(m_utteranceBuf.size())},
                    {"duration_ms", static_cast<qint64>(m_utteranceBuf.size() * 1000 / SAMPLE_RATE)}});

    if (m_utteranceBuf.empty()) {
        hVoice() << "Utterance vide — retour à Idle";
        if (m_sttStreaming) {
            m_stt->cancelUtterance();
            m_sttStreaming = false;
        }
        setState(PipelineState::Idle);
        return;
    }

    setState(PipelineState::Transcribing);
    m_transcribeTimer->start(TRANSCRIBE_TIMEOUT_MS);
    emit speechEnded();
    emit statusChanged("Transcription en cours...");

    const qint64 uttDurationMs = static_cast<qint64>(m_utteranceBuf.size() * 1000 / SAMPLE_RATE);
    hVoice() << "[Latency] Utterance captured:" << m_utteranceBuf.size() << "samples ("
             << uttDurationMs << "ms)";

    // End the streaming utterance if we were streaming
    if (m_stt && m_stt->isConnected()) {
        if (m_sttStreaming) {
            // We were already streaming audio — just signal end
            hVoice() << "finishUtterance: endUtterance() sur STT";
            m_stt->endUtterance();
            m_sttStreaming = false;
        } else {
            // Fallback: send entire buffer in one shot
            hVoice() << "finishUtterance: transcribeBuffer (" << m_utteranceBuf.size() << " samples)";
            m_stt->transcribeBuffer(m_utteranceBuf);
        }
    } else {
        hWarning(exoVoice) << "finishUtterance: STT non connecté — fallback interne";
        QString text = analyzeAudioFallback(m_utteranceBuf);
        if (!text.isEmpty()) {
            dispatchTranscript(text);
        } else {
            emit voiceError("STT non disponible — parlez plus fort ou plus près du micro");
            setState(PipelineState::Idle);
        }
    }
}

void VoicePipeline::dispatchTranscript(const QString &text)
{
    hVoice() << "=== dispatchTranscript ===" << text.left(80);
    hVoice() << "[Latency] STT → dispatch (" << m_interactionClock.elapsed() << "ms since VAD)";

    // Interaction déjà démarrée au wake-word ; sinon (mode conversation) la démarrer ici
    if (PipelineEventBus::instance()->currentCorrelationId().isEmpty())
        PipelineEventBus::instance()->beginInteraction();
    PIPELINE_EVENT(PipelineModule::Orchestrator, EventType::TranscriptDispatched,
                   {{"text", text}, {"length", text.length()}});

    m_lastCommand = text;
    hVoice() << "Transcript final:" << text;

    // v26.2 Latency: fast-path for simple intents (bypass Claude)
    if (handleFastPath(text)) {
        hVoice() << "[FastPath] Intent simple traité localement — Claude bypassed";
        emit finalTranscript(text);
        emit speechTranscribed(text);
        emit commandDetected(text);
        return;
    }

    emit finalTranscript(text);
    hVoice() << "dispatchTranscript: finalTranscript émis";
    emit speechTranscribed(text);
    hVoice() << "dispatchTranscript: speechTranscribed émis";
    emit commandDetected(text);
    hVoice() << "dispatchTranscript: commandDetected émis";

    // Send to Python backend via WebSocket (with correlationId for tracing)
    if (m_ws && m_ws->state() == QAbstractSocket::ConnectedState) {
        QJsonObject msg;
        msg["type"] = "transcript";
        msg["text"] = text;
        msg["timestamp"] = QDateTime::currentMSecsSinceEpoch();
        QString cid = PipelineEventBus::instance()->currentCorrelationId();
        if (!cid.isEmpty())
            msg["req_id"] = cid;
        m_ws->sendTextMessage(QString::fromUtf8(QJsonDocument(msg).toJson(QJsonDocument::Compact)));
        hVoice() << "dispatchTranscript: transcript envoyé via WS";
    } else {
        hWarning(exoVoice) << "dispatchTranscript: WebSocket backend non connecté!";
    }

    // v26.2 Latency: pre-warm TTS pipeline while Claude is thinking
    if (m_ttsManager)
        m_ttsManager->prepareNext();

    hVoice() << "dispatchTranscript: passage à Thinking";
    setState(PipelineState::Thinking);
    hVoice() << "dispatchTranscript: terminé";
}

// ── v26.2 Latency: fast-path for simple intents ─────

bool VoicePipeline::handleFastPath(const QString &text)
{
    QString low = text.toLower().trimmed();

    // ── DateTime ──
    if (low.contains(QLatin1String("quelle heure")) || low.contains(QLatin1String("quel jour"))
        || low.contains(QLatin1String("quelle date")) || low.contains(QLatin1String("on est quel jour"))
        || low.contains(QLatin1String("quel mois")) || low.contains(QLatin1String("quelle année"))) {
        QDateTime now = QDateTime::currentDateTime();
        QLocale fr(QLocale::French);
        QString response = QStringLiteral("Il est %1, nous sommes le %2.")
            .arg(now.toString(QStringLiteral("HH'h'mm")))
            .arg(fr.toString(now.date(), QStringLiteral("dddd d MMMM yyyy")));
        hVoice() << "[FastPath] DateTime:" << response;
        PIPELINE_EVENT(PipelineModule::Orchestrator, EventType::TranscriptDispatched,
                       {{"text", text}, {"fast_path", "datetime"}});
        setState(PipelineState::Speaking);
        m_ttsManager->speakText(response);
        return true;
    }

    // ── Timer / Minuteur ──
    {
        static QRegularExpression timerRx(
            QStringLiteral("(?:minuteur|timer|chrono|compte à rebours|minuterie).*?(\\d+)\\s*"
                           "(minutes?|min|secondes?|sec|heures?|h)"),
            QRegularExpression::CaseInsensitiveOption);
        auto match = timerRx.match(low);
        if (match.hasMatch()) {
            int value = match.captured(1).toInt();
            QString unit = match.captured(2).toLower();
            int ms = 0;
            QString unitStr;
            if (unit.startsWith(QLatin1String("min")))      { ms = value * 60000;   unitStr = QStringLiteral("minutes"); }
            else if (unit.startsWith(QLatin1String("sec")))  { ms = value * 1000;    unitStr = QStringLiteral("secondes"); }
            else if (unit.startsWith(QLatin1String("h")))    { ms = value * 3600000; unitStr = QStringLiteral("heures"); }

            if (ms > 0 && ms <= 86400000) { // max 24h
                QTimer::singleShot(ms, this, [this]() {
                    if (m_ttsManager) {
                        setState(PipelineState::Speaking);
                        m_ttsManager->speakText(QStringLiteral("Votre minuteur est terminé."));
                    }
                });
                QString response = QStringLiteral("Minuteur de %1 %2 lancé.").arg(value).arg(unitStr);
                hVoice() << "[FastPath] Timer:" << response;
                PIPELINE_EVENT(PipelineModule::Orchestrator, EventType::TranscriptDispatched,
                               {{"text", text}, {"fast_path", "timer"}, {"duration_ms", ms}});
                setState(PipelineState::Speaking);
                m_ttsManager->speakText(response);
                return true;
            }
        }
    }

    // ── Weather (remote fast-path) ──
    if (low.contains(QLatin1String("météo")) || low.contains(QLatin1String("quel temps"))
        || low.contains(QLatin1String("température dehors")) || low.contains(QLatin1String("va pleuvoir"))
        || low.contains(QLatin1String("prévision")) || low.contains(QLatin1String("fait beau"))
        || low.contains(QLatin1String("fait froid")) || low.contains(QLatin1String("fait chaud"))) {
        if (m_ws && m_ws->state() == QAbstractSocket::ConnectedState) {
            QJsonObject msg;
            msg[QStringLiteral("type")]      = QStringLiteral("direct_tool_call");
            msg[QStringLiteral("tool")]      = QStringLiteral("get_weather");
            msg[QStringLiteral("text")]      = text;
            msg[QStringLiteral("timestamp")] = QDateTime::currentMSecsSinceEpoch();
            m_ws->sendTextMessage(QString::fromUtf8(QJsonDocument(msg).toJson(QJsonDocument::Compact)));
            hVoice() << "[FastPath] Weather: direct_tool_call envoyé";
            PIPELINE_EVENT(PipelineModule::Orchestrator, EventType::TranscriptDispatched,
                           {{"text", text}, {"fast_path", "weather"}});
            if (m_ttsManager) m_ttsManager->prepareNext();
            setState(PipelineState::Thinking);
            return true;
        }
    }

    // ── Simple domotique (remote fast-path) ──
    if ((low.contains(QLatin1String("allume")) || low.contains(QLatin1String("éteins"))
         || low.contains(QLatin1String("éteindre")) || low.contains(QLatin1String("allumer"))
         || low.contains(QLatin1String("baisse")) || low.contains(QLatin1String("monte")))
        && (low.contains(QLatin1String("lumière")) || low.contains(QLatin1String("lampe"))
            || low.contains(QLatin1String("salon")) || low.contains(QLatin1String("chambre"))
            || low.contains(QLatin1String("cuisine")) || low.contains(QLatin1String("volet"))
            || low.contains(QLatin1String("chauffage")))) {
        if (m_ws && m_ws->state() == QAbstractSocket::ConnectedState) {
            QJsonObject msg;
            msg[QStringLiteral("type")]      = QStringLiteral("direct_tool_call");
            msg[QStringLiteral("tool")]      = QStringLiteral("domotic_action");
            msg[QStringLiteral("text")]      = text;
            msg[QStringLiteral("timestamp")] = QDateTime::currentMSecsSinceEpoch();
            m_ws->sendTextMessage(QString::fromUtf8(QJsonDocument(msg).toJson(QJsonDocument::Compact)));
            hVoice() << "[FastPath] Domotique: direct_tool_call envoyé";
            PIPELINE_EVENT(PipelineModule::Orchestrator, EventType::TranscriptDispatched,
                           {{"text", text}, {"fast_path", "domotic"}});
            if (m_ttsManager) m_ttsManager->prepareNext();
            setState(PipelineState::Thinking);
            return true;
        }
    }

    // ── Rappel (remote fast-path) ──
    if (low.contains(QLatin1String("rappelle")) || low.contains(QLatin1String("rappel"))
        || low.contains(QLatin1String("n'oublie pas")) || low.contains(QLatin1String("souviens"))) {
        if (m_ws && m_ws->state() == QAbstractSocket::ConnectedState) {
            QJsonObject msg;
            msg[QStringLiteral("type")]      = QStringLiteral("direct_tool_call");
            msg[QStringLiteral("tool")]      = QStringLiteral("remember_info");
            msg[QStringLiteral("text")]      = text;
            msg[QStringLiteral("timestamp")] = QDateTime::currentMSecsSinceEpoch();
            m_ws->sendTextMessage(QString::fromUtf8(QJsonDocument(msg).toJson(QJsonDocument::Compact)));
            hVoice() << "[FastPath] Rappel: direct_tool_call envoyé";
            PIPELINE_EVENT(PipelineModule::Orchestrator, EventType::TranscriptDispatched,
                           {{"text", text}, {"fast_path", "reminder"}});
            if (m_ttsManager) m_ttsManager->prepareNext();
            setState(PipelineState::Thinking);
            return true;
        }
    }

    return false;
}

// ── utterance timeout ────────────────────────────────

void VoicePipeline::onUtteranceTimeout()
{
    hVoice() << "Utterance timeout (" << UTTERANCE_TIMEOUT_MS << "ms)";
    if (m_state == PipelineState::Listening || m_state == PipelineState::DetectingSpeech) {
        finishUtterance();
    }
}

void VoicePipeline::onTranscribeTimeout()
{
    hWarning(exoVoice) << "Transcription timeout (" << TRANSCRIBE_TIMEOUT_MS
                         << "ms) — pipeline bloqué en Transcribing, retour Idle";
    if (m_state == PipelineState::Transcribing) {
        if (m_stt && m_stt->isConnected()) {
            m_stt->cancelUtterance();
        }
        m_sttStreaming = false;
        m_wakeWordTriggered = false;
        m_utteranceBuf.clear();
        emit voiceError("Transcription trop longue — réessayez");
        setState(PipelineState::Idle);
    }
}

// ── VAD callbacks ────────────────────────────────────

void VoicePipeline::onVADSpeechStarted()
{
    if (m_state == PipelineState::DetectingSpeech || m_state == PipelineState::Listening) {
        PIPELINE_EVENT(PipelineModule::VAD, EventType::SpeechStarted);
        PIPELINE_STATE(PipelineModule::VAD, ModuleState::Active);
        emit speechStarted();
    }
}

void VoicePipeline::onVADSpeechEnded()
{
    PIPELINE_EVENT(PipelineModule::VAD, EventType::SpeechEnded);
    PIPELINE_STATE(PipelineModule::VAD, ModuleState::Idle);
    // Speech end is handled in processAudioChunk for tighter control
}

// ── STT callbacks ────────────────────────────────────

void VoicePipeline::onSTTPartial(const QString &text)
{
    LatencyMetrics::instance()->markSttPartialFirst();
    PIPELINE_EVENT(PipelineModule::STT, EventType::PartialTranscript,
                   {{"text", text.left(100)}});
    emit partialTranscript(text);
    emit statusChanged("\"" + text + "\"...");

    // Wake-word logiciel : détecter "EXO" dans le transcript partiel
    if (!m_wakeWordTriggered && checkWakeWord(text)) {
        m_wakeWordTriggered = true;
        hVoice() << "Wake-word logiciel détecté dans transcript:" << text;
        // Démarrer l'interaction dès le wake-word pour corréler VAD/STT
        PipelineEventBus::instance()->beginInteraction();
        PIPELINE_EVENT(PipelineModule::WakeWord, EventType::WakeWordDetected,
                       {{"text", text.left(60)}, {"source", "transcript_partial"}});
        emit wakeWordDetected();
        emit statusChanged("EXO écoute...");
    }

    if (m_ws && m_ws->state() == QAbstractSocket::ConnectedState) {
        QJsonObject msg;
        msg["type"] = "partial_transcript";
        msg["text"] = text;
        m_ws->sendTextMessage(QString::fromUtf8(QJsonDocument(msg).toJson(QJsonDocument::Compact)));
    }
}

void VoicePipeline::onSTTFinal(const QString &text)
{
    m_transcribeTimer->stop();
    LatencyMetrics::instance()->markSttFinal();
    MetricsManager::instance()->increment(QStringLiteral("stt.finals_received"));
    hVoice() << "[Latency] STT final received";
    hVoice() << "=== onSTTFinal ===" << text.left(80)
             << "state=" << static_cast<int>(m_state)
             << "wakeTriggered=" << m_wakeWordTriggered
             << "conversationActive=" << m_conversationActive;
    PIPELINE_EVENT(PipelineModule::STT, EventType::FinalTranscript,
                   {{"text", text}, {"length", text.length()}});
    PIPELINE_STATE(PipelineModule::STT, ModuleState::Idle);

    const QString trimmed = text.trimmed();
    QString semantic = trimmed;
    semantic.remove(QRegularExpression("[\\p{P}\\p{S}\\s]+"));
    const bool hasMeaningfulContent = (semantic.length() >= 2);

    // Vérifier wake-word dans le transcript final aussi
    if (!m_wakeWordTriggered && checkWakeWord(text)) {
        m_wakeWordTriggered = true;
        hVoice() << "Wake-word logiciel détecté dans transcript final:" << text;
        // Démarrer l'interaction dès le wake-word pour corréler VAD/STT
        PipelineEventBus::instance()->beginInteraction();
        PIPELINE_EVENT(PipelineModule::WakeWord, EventType::WakeWordDetected,
                       {{"text", text.left(60)}, {"source", "transcript_final"}});
        emit wakeWordDetected();
    }

    if (m_wakeWordTriggered) {
        // Wake-word détecté → dispatch vers Claude
        // Retirer le mot-clé et ses variantes du texte
        QString command = findAndRemoveWakeWord(text);
        QString commandSemantic = command;
        commandSemantic.remove(QRegularExpression("[\\p{P}\\p{S}\\s]+"));
        if (!commandSemantic.isEmpty()) {
            m_conversationTimer->start(CONVERSATION_TIMEOUT_MS);
            m_conversationActive = true;
            dispatchTranscript(command);
        } else {
            hVoice() << "Transcript ne contient que le wake-word — retour Idle";
            m_lastIgnoredNoiseClock.restart();
            setState(PipelineState::Idle);
        }
    } else if (m_conversationActive && hasMeaningfulContent) {
        // Mode conversation actif — pas besoin de wake-word
        hVoice() << "Mode conversation — dispatch sans wake-word:" << text;
        m_conversationTimer->start(CONVERSATION_TIMEOUT_MS);
        dispatchTranscript(text);
    } else {
        // Pas de wake-word → ignorer et retourner en Idle
        hVoice() << "Transcript sans wake-word ignoré (vide/bruit):" << text;
        m_lastIgnoredNoiseClock.restart();
        emit statusChanged("Dites \"" + m_wakeKeyword + "\" pour activer");
        setState(PipelineState::Idle);
    }
    m_wakeWordTriggered = false;
}

void VoicePipeline::onSTTError(const QString &msg)
{
    PIPELINE_EVENT(PipelineModule::STT, EventType::STTError, {{"message", msg}});
    PipelineEventBus::instance()->setModuleError(PipelineModule::STT, msg);
    hVoice() << "STT erreur:" << msg;

    // Ignore stale STT errors while TTS is speaking to avoid re-entrant dispatches.
    if (m_state == PipelineState::Speaking || m_isSpeaking) {
        hWarning(exoVoice) << "STT erreur reçue pendant Speaking — ignorée";
        m_sttStreaming = false;
        m_utteranceBuf.clear();
        m_wakeWordTriggered = false;
        return;
    }

    // Fallback to internal analysis
    if (!m_utteranceBuf.empty()) {
        QString fallback = analyzeAudioFallback(m_utteranceBuf);
        if (!fallback.isEmpty()) {
            dispatchTranscript(fallback);
            return;
        }
    }
    emit voiceError("Erreur STT: " + msg);
    setState(PipelineState::Idle);
}

// ── TTS callbacks ────────────────────────────────────

void VoicePipeline::onTtsStarted()
{
    if (m_vadInteraction)
        hVoice() << "[Latency] TTS playback started (" << m_interactionClock.elapsed() << "ms end-to-end)";
    else
        hVoice() << "[Latency] TTS playback started (manual request)";
    PIPELINE_EVENT(PipelineModule::TTS, EventType::PlaybackStarted);
    PIPELINE_STATE(PipelineModule::TTS, ModuleState::Active);
    PIPELINE_STATE(PipelineModule::AudioOutput, ModuleState::Active);
    m_isSpeaking = true;
    m_ttsPlaybackStart.restart();
    setState(PipelineState::Speaking);
    emit speakingChanged();
}

void VoicePipeline::onTtsFinished()
{
    if (m_isSpeaking) {
        PIPELINE_EVENT(PipelineModule::TTS, EventType::PlaybackFinished);
        PIPELINE_STATE(PipelineModule::TTS, ModuleState::Idle);
        PIPELINE_STATE(PipelineModule::AudioOutput, ModuleState::Idle);

        // End l'interaction courante
        QString cid = PipelineEventBus::instance()->currentCorrelationId();
        if (!cid.isEmpty())
            PipelineEventBus::instance()->endInteraction(cid);

        m_isSpeaking = false;
        m_vadInteraction = false;  // reset for next interaction
        m_ttsEndClock.restart();
        emit speakingChanged();
        hVoice() << "[Latency] TTS playback finished (" << m_ttsPlaybackStart.elapsed() << "ms)";

        // Activer le mode conversation après une réponse TTS
        m_conversationActive = true;
        m_conversationTimer->start(CONVERSATION_TIMEOUT_MS);
        hVoice() << "Mode conversation activé pour" << CONVERSATION_TIMEOUT_MS << "ms";

        // v5.2: Resume pipeline immediately — processAudioChunk guards via
        // m_ttsEndClock < TTS_GUARD_MS, so no artificial delay needed.
        if (m_audioInput) {
            m_audioInput->resume();
        } else {
            hWarning(exoVoice) << "onTtsFinished: m_audioInput est nullptr";
        }
        resetBuffers();
        setState(PipelineState::Idle);
        hVoice() << "Pipeline prêt — anti-echo guard:" << TTS_GUARD_MS << "ms";
    }
}

void VoicePipeline::onTtsError(const QString &msg)
{
    PIPELINE_EVENT(PipelineModule::TTS, EventType::TTSError, {{"message", msg}});
    PipelineEventBus::instance()->setModuleError(PipelineModule::TTS, msg);
    hVoice() << "TTS erreur:" << msg;
    if (m_isSpeaking) {
        m_isSpeaking = false;
        m_ttsEndClock.restart();
        emit speakingChanged();
        if (m_audioInput) m_audioInput->resume();
        setState(PipelineState::Idle);
    }
}

// ── state machine ────────────────────────────────────

void VoicePipeline::setState(PipelineState s)
{
    if (m_state == s) return;

    // Guard: block invalid transitions while Speaking (only Idle is allowed after Speaking)
    if (m_state == PipelineState::Speaking && s != PipelineState::Idle) {
        hWarning(exoVoice) << "setState: transition bloquée pendant Speaking → "
                             << static_cast<int>(s);
        return;
    }
    // Guard: don't go backwards from Thinking/Transcribing to DetectingSpeech/Listening
    if ((m_state == PipelineState::Thinking || m_state == PipelineState::Transcribing)
        && (s == PipelineState::DetectingSpeech || s == PipelineState::Listening)) {
        hWarning(exoVoice) << "setState: transition arrière bloquée "
                             << static_cast<int>(m_state) << " → " << static_cast<int>(s);
        return;
    }

    hVoice() << "Pipeline state:" << static_cast<int>(m_state) << "→" << static_cast<int>(s);
    m_state = s;
    emit stateChanged(static_cast<int>(s));
    broadcastState();

    // ── Speaking watchdog: force Idle if TTS never triggers finished() ──
    if (s == PipelineState::Speaking) {
        if (!m_speakingWatchdog) {
            m_speakingWatchdog = new QTimer(this);
            m_speakingWatchdog->setSingleShot(true);
            connect(m_speakingWatchdog, &QTimer::timeout, this, [this]() {
                hWarning(exoVoice) << "WATCHDOG: Speaking bloqué >" << SPEAKING_WATCHDOG_MS / 1000 << "s → force Idle";
                setState(PipelineState::Idle);
            });
        }
        m_speakingWatchdog->start(SPEAKING_WATCHDOG_MS);
    } else if (m_speakingWatchdog && m_speakingWatchdog->isActive()) {
        m_speakingWatchdog->stop();
    }

    static const char *names[] = {"Idle", "DetectingSpeech", "Listening", "Transcribing", "Thinking", "Speaking"};
    hVoice() << "État:" << names[static_cast<int>(s)];

    // Update pipeline event bus orchestrator state
    ModuleState ms = ModuleState::Idle;
    switch (s) {
    case PipelineState::DetectingSpeech:
    case PipelineState::Listening:
        ms = ModuleState::Active; break;
    case PipelineState::Transcribing:
    case PipelineState::Thinking:
    case PipelineState::Speaking:
        ms = ModuleState::Processing; break;
    default:
        ms = ModuleState::Idle; break;
    }
    PIPELINE_STATE(PipelineModule::Orchestrator, ms);
    PIPELINE_EVENT(PipelineModule::Orchestrator, EventType::StateChanged,
                   {{"state", names[static_cast<int>(s)]}});
}

void VoicePipeline::broadcastState()
{
    if (!m_ws || m_ws->state() != QAbstractSocket::ConnectedState) return;

    static const QString stateNames[] = {"idle", "detecting_speech", "listening", "transcribing", "thinking", "speaking"};
    QJsonObject msg;
    msg["type"]  = "pipeline_state";
    msg["state"] = stateNames[static_cast<int>(m_state)];
    m_ws->sendTextMessage(QString::fromUtf8(QJsonDocument(msg).toJson(QJsonDocument::Compact)));
}

void VoicePipeline::broadcastAudioLevel(float rms, float vadScore)
{
    if (!m_ws || m_ws->state() != QAbstractSocket::ConnectedState) return;

    // Throttle: send at most ~10 Hz
    static QElapsedTimer throttle;
    if (!throttle.isValid()) throttle.start();
    if (throttle.elapsed() < 100) return;
    throttle.restart();

    QJsonObject msg;
    msg["type"]      = "audio_level";
    msg["rms"]       = static_cast<double>(rms);
    msg["vad_score"] = static_cast<double>(vadScore);
    msg["is_speech"] = m_vad ? m_vad->isSpeech() : false;
    m_ws->sendTextMessage(QString::fromUtf8(QJsonDocument(msg).toJson(QJsonDocument::Compact)));
}

// ── fallback STT (energy heuristic) ──────────────────

QString VoicePipeline::analyzeAudioFallback(const std::vector<int16_t> &pcm)
{
    // This is a placeholder that returns a generic "commande vocale"
    // when no real STT (Whisper) is available.
    // It signals the AssistantManager that speech was detected so it can
    // ask Claude to respond conversationally.
    if (pcm.size() < 4000) return QString(); // < 250ms → too short

    // Compute average energy
    long long total = 0;
    for (auto s : pcm) total += std::abs(static_cast<int>(s));
    int avg = static_cast<int>(total / static_cast<long long>(pcm.size()));

    int durationMs = static_cast<int>(pcm.size() * 1000 / SAMPLE_RATE);

    hVoice() << "Fallback analyse — énergie:" << avg << " durée:" << durationMs << "ms";

    if (avg < 200) return QString(); // too quiet

    // Return a generic marker that AssistantManager can handle
    // In production, this path should not be used — Whisper should be available
    return QStringLiteral("[commande_vocale:%1ms]").arg(durationMs);
}

// ── Downsample PCM for QML waveform visualization ────

QVariantList VoicePipeline::downsampleForVisualization(const int16_t *samples, int count, int targetCount)
{
    QVariantList result;
    result.reserve(targetCount);

    if (count <= 0) {
        for (int i = 0; i < targetCount; ++i)
            result.append(0.0f);
        return result;
    }

    const float step = static_cast<float>(count) / targetCount;
    for (int i = 0; i < targetCount; ++i) {
        // Average samples in this bin for anti-aliased downsampling
        const int start = static_cast<int>(i * step);
        const int end   = std::min(static_cast<int>((i + 1) * step), count);
        float sum = 0.0f;
        for (int j = start; j < end; ++j)
            sum += samples[j] / 32768.0f;
        result.append(sum / std::max(1, end - start));
    }
    return result;
}
