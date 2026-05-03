#ifndef VOICEPIPELINE_H
#define VOICEPIPELINE_H

#include <QObject>
#include <QAudioFormat>
#include <QAudioDevice>
#include <QMediaDevices>
#include "AudioInput.h"
#include "AudioInputQt.h"
#ifdef ENABLE_RTAUDIO
#include "AudioInputRtAudio.h"
#endif
#include "AudioDeviceManager.h"
#include "TTSManager.h"
#include <QThread>
#include <QMutex>
#include <QElapsedTimer>
#include <QTimer>
#include <QJsonObject>
#include <QJsonDocument>
#include "core/WebSocketClient.h"
#include <memory>
#include <vector>
#include <atomic>
#include <cstdint>
#include <cmath>
#include <QVariantList>
#include "core/PipelineEvent.h"

// ─────────────────────────────────────────────────────
//  CircularAudioBuffer — lock-free-ish ring buffer
// ─────────────────────────────────────────────────────
class CircularAudioBuffer
{
public:
    explicit CircularAudioBuffer(size_t capacitySamples = 16000 * 30);

    void     write(const int16_t *data, size_t count);
    size_t   read(int16_t *dest, size_t count);
    size_t   peek(int16_t *dest, size_t count) const;
    size_t   available() const;
    void     clear();
    size_t   capacity() const { return m_buf.size(); }

private:
    std::vector<int16_t> m_buf;
    size_t m_head = 0;
    size_t m_tail = 0;
    size_t m_count = 0;
    mutable QMutex m_mutex;
};

// ─────────────────────────────────────────────────────
//  AudioPreprocessor — DSP chain on int16 chunks
// ─────────────────────────────────────────────────────
class AudioPreprocessor
{
public:
    AudioPreprocessor();

    void process(int16_t *samples, int count);

    // Butterworth high-pass (2nd order) cutoff Hz
    void setHighPassCutoff(float hz);
    void setNoiseGateThreshold(float rms);
    void setAGCEnabled(bool on);
    void setNormalizationTarget(float rms);
    void setSampleRate(int sr);

private:
    // High-pass Butterworth 2nd-order state
    void recomputeHP();
    float m_hpCutoff   = 80.0f;   // 80 Hz: preserves male fundamental (was 150 Hz)
    int   m_sampleRate = 16000;
    // biquad coefficients  a0 is normalized to 1
    double m_b0=1, m_b1=0, m_b2=0, m_a1=0, m_a2=0;
    double m_x1=0, m_x2=0, m_y1=0, m_y2=0;

    // Noise gate
    float m_gateThreshold = 0.001f;   // RMS below this → zero (lowered for quiet mics)
    bool  m_gateOpen = false;

    // AGC
    bool  m_agcEnabled = true;
    float m_agcGain    = 1.0f;

    // RMS normalization target (0 = disabled)
    float m_normTarget = 0.0f;
};

// ─────────────────────────────────────────────────────
//  VADEngine — Voice Activity Detection
//  Builtin  : energy + ZCR heuristic (always available)
//  Silero   : Silero VAD via WebSocket → vad_server.py
//  Hybrid   : Builtin + Silero combined
// ─────────────────────────────────────────────────────
class VADEngine : public QObject
{
    Q_OBJECT
public:
    enum class Backend { Builtin, SileroONNX, Hybrid };
    Q_ENUM(Backend)

    explicit VADEngine(QObject *parent = nullptr);
    ~VADEngine();

    bool     initialize(Backend preferred = Backend::Builtin,
                        const QString &sileroUrl = "ws://localhost:8768");
    float    processChunk(const int16_t *samples, int count);
    bool     isSpeech() const { return m_isSpeech; }
    Backend  activeBackend() const { return m_backend; }

    void setThreshold(float t);
    float threshold() const { return m_threshold; }

    // Adaptive noise floor
    void resetNoiseEstimate();

signals:
    void speechStarted();
    void speechEnded();

private slots:
    void onSileroConnected();
    void onSileroDisconnected();
    void onSileroMessage(const QString &msg);

private:
    float builtinScore(const int16_t *s, int n);
    void  updateSpeechState(float score);
    void  sendSileroAudio(const int16_t *s, int n);

    Backend m_backend = Backend::Builtin;
    float  m_threshold = 0.45f;
    bool   m_isSpeech  = false;
    int    m_speechFrames  = 0;
    int    m_silenceFrames = 0;

    // Adaptive noise estimation (exponential moving average)
    float  m_noiseFloor = 0.0f;
    bool   m_noiseCalibrated = false;
    int    m_calibrationFrames = 0;
    static constexpr int CALIBRATION_WINDOW = 15;   // ~300 ms @ 20 ms chunks (v5.2: halved for faster startup)
    static constexpr int SPEECH_HANG_FRAMES = 30;   // ~600ms @ 20ms — réduit la latence de fin d'utterance
    static constexpr int SPEECH_START_FRAMES = 2;    // require N consecutive speech frames

    // Silero VAD via WebSocketClient
    WebSocketClient *m_sileroWs = nullptr;
    float m_sileroScore = 0.0f;
    QString m_sileroUrl;
    QElapsedTimer m_sileroConnectedClock;
    QElapsedTimer m_sileroFlapWindow;
    int m_sileroFlapCount = 0;
    bool m_sileroReconnectDisabled = false;
    static constexpr int SILERO_MIN_UPTIME_MS = 2000;
    static constexpr int SILERO_FLAP_WINDOW_MS = 30000;
    static constexpr int SILERO_MAX_FLAPS = 4;
};

// ─────────────────────────────────────────────────────
//  StreamingSTT — STT via WebSocket → stt_server.py
//
//  Protocol:
//   → JSON {"type":"start"}   begin utterance
//   → Binary PCM16 audio chunks (real-time streaming)
//   → JSON {"type":"end"}     finalize utterance
//   ← JSON {"type":"partial","text":"..."}
//   ← JSON {"type":"final","text":"...","segments":[...]}
// ─────────────────────────────────────────────────────
class StreamingSTT : public QObject
{
    Q_OBJECT
public:
    explicit StreamingSTT(QObject *parent = nullptr);
    ~StreamingSTT();

    bool initialize(const QString &serverUrl = "ws://localhost:8766");
    bool isAvailable() const { return m_connected; }
    bool isConnected() const { return m_connected; }

    // Start a new utterance (tells server to expect audio)
    void startUtterance();
    // Stream audio chunk in real-time
    void feedAudio(const int16_t *samples, int count);
    // End utterance and request final transcript
    void endUtterance();
    // Cancel current utterance
    void cancelUtterance();

    // Submit full buffer (non-streaming fallback)
    void transcribeBuffer(const std::vector<int16_t> &pcm);

    void setLanguage(const QString &lang);
    void setBeamSize(int beam);

signals:
    void partialTranscript(const QString &text);
    void finalTranscript(const QString &text);
    void error(const QString &msg);
    void connected();
    void disconnected();

private slots:
    void onWsConnected();
    void onWsDisconnected();
    void onWsTextMessage(const QString &msg);

private:
    WebSocketClient *m_ws = nullptr;
    bool m_connected = false;
    bool m_recording = false;
    QString m_language = "fr";
    int m_beamSize = 1;
};

// ─────────────────────────────────────────────────────
//  PipelineState — finite state machine (v4.1)
// ─────────────────────────────────────────────────────
enum class PipelineState {
    Idle,             // attente — VAD + STT passif
    DetectingSpeech,  // parole détectée par VAD, streaming STT actif
    Listening,        // capture utterance en cours
    Transcribing,     // STT en cours (streaming vers stt_server)
    Thinking,         // Claude / NLU processing
    Speaking          // TTS playing
};

// ─────────────────────────────────────────────────────
//  VoicePipeline — central orchestrator
//
//  Audio → Preprocess → VAD → STT → detect "EXO" → Claude
//                                                    → TTS
// ─────────────────────────────────────────────────────
class VoicePipeline : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool isListening    READ isListening    NOTIFY listeningChanged)
    Q_PROPERTY(bool isSpeaking     READ isSpeaking     NOTIFY speakingChanged)
    Q_PROPERTY(QString lastCommand READ lastCommand     NOTIFY commandDetected)
    Q_PROPERTY(int    pipelineState READ pipelineStateInt NOTIFY stateChanged)
    Q_PROPERTY(QStringList ttsVoices READ ttsVoices NOTIFY ttsVoicesChanged)

public:
    explicit VoicePipeline(QObject *parent = nullptr);
    ~VoicePipeline();

    // ── lifecycle ──
    bool initAudio();
    bool initVAD(VADEngine::Backend preferred = VADEngine::Backend::Builtin,
                 const QString &sileroUrl = "ws://localhost:8768");
    bool initSTT(const QString &serverUrl = "ws://localhost:8766");
    void initTTS(const QString &ttsServerUrl = "ws://localhost:8767");
    void initWakeWordServer(const QString &url = "ws://localhost:8770");

    Q_INVOKABLE void startListening();
    Q_INVOKABLE void stopListening();
    Q_INVOKABLE void speak(const QString &text);
    Q_INVOKABLE void speakSentence(const QString &text);
    Q_INVOKABLE void resetBuffers();

    // ── state queries ──
    bool isListening() const { return m_audioRunning; }
    bool isSpeaking()  const { return m_isSpeaking; }
    QString lastCommand() const { return m_lastCommand; }
    PipelineState state() const { return m_state; }
    int pipelineStateInt() const { return static_cast<int>(m_state); }

    // ── tuning API ──
    Q_INVOKABLE void setWakeWordSensitivity(float s);
    Q_INVOKABLE void setVADThreshold(float t);
    Q_INVOKABLE void setNoiseGate(float rms);
    Q_INVOKABLE void setAGC(bool on);
    Q_INVOKABLE void setWakeWord(const QString &word);
    Q_INVOKABLE void setWakeWords(const QStringList &words);
    Q_INVOKABLE void setSTTServerUrl(const QString &url);
    Q_INVOKABLE void setSTTLanguage(const QString &lang);
    Q_INVOKABLE void setTTSVoice(const QString &name);
    Q_INVOKABLE void setTTSLanguage(const QString &lang);
    Q_INVOKABLE void setTTSStyle(const QString &style);
    Q_INVOKABLE void setTTSEngine(const QString &engine);
    Q_INVOKABLE void setTTSOutputDevice(const QString &deviceName);
    Q_INVOKABLE void setTTSPitch(float p);
    Q_INVOKABLE void setTTSRate(float r);
    Q_INVOKABLE void setAudioBackend(const QString &backend);
    Q_INVOKABLE void fetchTTSVoices();
    QStringList ttsVoices() const;

    // ── AudioDeviceManager (QML exposure via AssistantManager) ──
    AudioDeviceManager* audioDeviceManager() const { return m_audioDeviceManager; }

    // ── WebSocket bridge (for React GUI) ──
    void connectToServer(const QString &url);
    void sendWebSocketMessage(const QString &message);

signals:
    // ── Events exposed to QML / AssistantManager ──
    void listeningChanged();
    void speakingChanged();
    void stateChanged(int newState);
    void commandDetected(const QString &command);
    void wakeWordDetected();
    void speechStarted();
    void speechEnded();
    void partialTranscript(const QString &text);
    void finalTranscript(const QString &text);
    void speechTranscribed(const QString &transcription);
    void statusChanged(const QString &status);
    void voiceError(const QString &error);
    void audioLevel(float rms, float vadScore);
    void ttsVoicesChanged();
    void micPcmForVisualization(const QVariantList &samples);
    void ttsPcmForVisualization(const QVariantList &samples);
    void audioUnavailable();
    void audioReady();

private slots:
    void onVADSpeechStarted();
    void onVADSpeechEnded();
    void onSTTPartial(const QString &text);
    void onSTTFinal(const QString &text);
    void onSTTError(const QString &msg);
    void onTtsStarted();
    void onTtsFinished();
    void onTtsError(const QString &msg);
    void onUtteranceTimeout();
    void onTranscribeTimeout();
    void onWsBinaryMessage(const QByteArray &msg);
    void onWsTextMessage(const QString &msg);
    void onWakeWordWsConnected();
    void onWakeWordWsDisconnected();
    void onWakeWordWsMessage(const QString &msg);

private:
    // ── internal pipeline stages ──
    void onAudioSamples(const int16_t *samples, int count);
    void processAudioChunk(const int16_t *samples, int count);
    void handleVAD(const int16_t *samples, int count, float vadScore);
    void handleRecording(const int16_t *samples, int count);
    bool checkWakeWord(const QString &text);
    QString findAndRemoveWakeWord(const QString &text);
    int levenshteinDistance(const QString &a, const QString &b);
    void finishUtterance();
    void dispatchTranscript(const QString &text);
    bool handleFastPath(const QString &text);
    void setState(PipelineState s);
    void broadcastState();
    void broadcastAudioLevel(float rms, float vadScore);
    QString analyzeAudioFallback(const std::vector<int16_t> &pcm);
    static QVariantList downsampleForVisualization(const int16_t *samples, int count, int targetCount = 256);

    // ── state ──
    PipelineState m_state = PipelineState::Idle;
    std::atomic<bool> m_audioRunning{false};
    bool m_isSpeaking = false;
    QString m_lastCommand;
    QString m_wakeKeyword = "exo";
    QStringList m_wakeVariants;   // all wake-word variants (lowercase, no punctuation)
    bool m_wakeWordTriggered = false;  // wake-word détecté dans transcript courant

    // ── audio capture (abstracted backend) ──
    QAudioFormat m_format;
    std::unique_ptr<AudioInput> m_audioInput;
    QString m_audioBackend = "qt"; // "qt" or "rtaudio"

    // ── device manager ──
    AudioDeviceManager *m_audioDeviceManager = nullptr;
    void onDeviceSwitchRequested(int rtAudioDeviceId);

    // ── preprocessing ──
    AudioPreprocessor m_preproc;
    QMutex m_preprocMutex;  // P1.1: Protect preprocessor state from concurrent access

    // ── VAD ──
    std::unique_ptr<VADEngine> m_vad;

    // ── STT (streaming via WebSocket → stt_server.py) ──
    std::unique_ptr<StreamingSTT> m_stt;
    bool m_sttStreaming = false;  // are we streaming audio to STT?

    // ── Recording buffer (utterance being captured) ──
    std::vector<int16_t> m_utteranceBuf;
    CircularAudioBuffer m_ringBuf;
    static constexpr size_t MAX_UTTERANCE_SAMPLES = 16000 * 30; // 30 s

    // ── TTS ──
    TTSManager *m_ttsManager = nullptr;
    QString m_ttsServerUrl;  // saved at initTTS() for setTTSEngine()

    // ── Timers ──
    QTimer *m_utteranceTimer = nullptr;
    QTimer *m_conversationTimer = nullptr;
    QTimer *m_transcribeTimer = nullptr;
    QTimer *m_speakingWatchdog = nullptr;
    QElapsedTimer m_ttsEndClock;
    QElapsedTimer m_ttsPlaybackStart;
    QElapsedTimer m_lastWakeWordClock;
    QElapsedTimer m_lastIgnoredNoiseClock;
    QElapsedTimer m_interactionClock;  // v5.2: end-to-end latency measurement
    bool m_vadInteraction = false;       // true when current interaction was triggered by VAD
    static constexpr int TTS_GUARD_MS           = 400;   // v5.2: 400ms anti-echo guard (was 1000)
    static constexpr int WAKE_COOLDOWN_MS       = 800;   // v5.2: 800ms cooldown (was 2000)
    static constexpr int UTTERANCE_TIMEOUT_MS   = 5500;  // réduit les pics STT liés à l'auto-timeout
    static constexpr int POST_WAKE_GRACE_MS     = 150;   // v5.2: 150ms grace (was 400)
    static constexpr int CONVERSATION_TIMEOUT_MS = 10000; // v5.2: 10s conversation mode (was 15000)
    static constexpr int TRANSCRIBE_TIMEOUT_MS  = 20000; // v25.1: 20s STT timeout (beam-size latency)
    static constexpr int SPEAKING_WATCHDOG_MS    = 20000; // v5.2: 20s watchdog (was 30000)
    static constexpr int MIN_UTTERANCE_MS       = 500;   // permet de couper plus tôt après la fin de parole
    static constexpr int NOISE_REARM_MS         = 2200;  // anti-boucle: temporisation plus longue après final vide/bruité

    // ── Conversation mode (no wake-word needed after TTS response) ──
    bool m_conversationActive = false;

    // ── OpenWakeWord neural detection (via wakeword_server.py) ──
    WebSocketClient *m_wakewordWs = nullptr;

    // ── WebSocket (to exo_server.py / React GUI) ──
    QWebSocket *m_ws = nullptr;

    // ── Audio format constants ──
    static constexpr int SAMPLE_RATE = 16000;
    static constexpr int CHUNK_MS    = 20;
    static constexpr int CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_MS / 1000; // 320
};

#endif // VOICEPIPELINE_H
