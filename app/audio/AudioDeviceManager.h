#pragma once

#include <QObject>
#include <QStringList>
#include <QTimer>
#include <memory>
#include <vector>
#include <atomic>
#include <cstdint>

#ifdef ENABLE_RTAUDIO
#include <RtAudio.h>
#endif

// ═══════════════════════════════════════════════════════
//  AudioDeviceManager — gestion complète des microphones
//
//  Fonctionnalités :
//   - Scanner tous les devices d'entrée RtAudio
//   - Sélection manuelle ou automatique du micro
//   - Health check du stream audio (healthy/down)
//   - Test audio intégré : vumètre RMS + enregistrement
//     + lecture (1 seconde)
//   - Signaux vers QML pour UI réactive
//
//  Exposé dans QML via setContextProperty.
// ═══════════════════════════════════════════════════════
class AudioDeviceManager : public QObject
{
    Q_OBJECT

    // ── Propriétés exposées au QML ──
    Q_PROPERTY(QStringList inputDevices   READ inputDevices   NOTIFY devicesChanged)
    Q_PROPERTY(int  selectedDeviceIndex   READ selectedDeviceIndex NOTIFY inputDeviceChanged)
    Q_PROPERTY(int  defaultInputDevice    READ defaultInputDevice  NOTIFY devicesChanged)
    Q_PROPERTY(bool hasValidInputDevice   READ hasValidInputDevice NOTIFY devicesChanged)
    Q_PROPERTY(QString lastError          READ lastError          NOTIFY audioError)
    Q_PROPERTY(QString audioStatus        READ audioStatus        NOTIFY audioStatusChanged)
    Q_PROPERTY(float currentRmsLevel      READ currentRmsLevel    NOTIFY rmsLevelChanged)
    Q_PROPERTY(bool  audioTestRunning     READ audioTestRunning   NOTIFY audioTestRunningChanged)

public:
    explicit AudioDeviceManager(QObject *parent = nullptr);
    ~AudioDeviceManager() override;

    // ── Enumération des devices ──
    QStringList inputDevices() const;
    int defaultInputDevice() const;
    int selectedDeviceIndex() const { return m_selectedIndex; }
    bool hasValidInputDevice() const;
    QString lastError() const { return m_lastError; }

    // ── Health check ──
    QString audioStatus() const { return m_audioStatus; }

    // ── VU-mètre ──
    float currentRmsLevel() const { return m_currentRms; }

    // ── Test audio ──
    bool audioTestRunning() const { return m_testRunning; }

    // ── API publique (appelé par VoicePipeline) ──
    Q_INVOKABLE void scanDevices();
    Q_INVOKABLE bool setInputDevice(int index);
    Q_INVOKABLE void startAudioTest();
    Q_INVOKABLE void stopAudioTest();
    Q_INVOKABLE void openWindowsSoundSettings();

    // Accès interne pour VoicePipeline
    int selectedRtAudioDeviceId() const;
    void startHealthCheck(int intervalMs = 5000);
    void stopHealthCheck();

    // Mettre à jour le RMS depuis le callback audio (thread-safe)
    void feedRmsSamples(const int16_t *samples, int count);

    // Notifier le manager que le stream principal est ouvert/fermé
    void notifyStreamOpened();
    void notifyStreamClosed();

signals:
    void devicesChanged();
    void inputDeviceChanged();
    void audioError(const QString &error);
    void audioStatusChanged();
    void rmsLevelChanged();
    void audioTestRunningChanged();
    void audioTestFinished(bool success);

    // Signaux pour VoicePipeline
    void audioUnavailable();
    void audioReady();
    void deviceSwitchRequested(int rtAudioDeviceId);

private slots:
    void onHealthCheckTimer();

private:
    struct DeviceInfo {
        unsigned int rtId = 0;
        QString name;
        int inputChannels = 0;
    };

    void setLastError(const QString &err);
    void setAudioStatus(const QString &status);
    float computeRms(const int16_t *samples, int count) const;
    void playbackRecordedBuffer();

    // ── Devices ──
    std::vector<DeviceInfo> m_devices;
    int m_selectedIndex = -1;          // index dans m_devices
    QString m_lastError;

    // ── Health check ──
    QTimer m_healthTimer;
    QString m_audioStatus = "unknown"; // "healthy" | "down" | "unknown"
    bool m_streamOpen = false;

#ifdef ENABLE_RTAUDIO
    // Persistent RtAudio instance for enumeration / health checks
    mutable std::unique_ptr<RtAudio> m_rtAudio;
    void ensureRtAudio() const;
#endif

    // ── VU-mètre RMS (mis à jour depuis le callback audio) ──
    std::atomic<float> m_currentRms{0.0f};

    // ── Test audio ──
    bool m_testRunning = false;
    std::vector<int16_t> m_testBuffer;
    int m_testSampleRate = 16000;
    int m_testRecordMs = 1000;

#ifdef ENABLE_RTAUDIO
    std::unique_ptr<RtAudio> m_testRt;
    static int testInputCallback(void *outputBuffer, void *inputBuffer,
                                  unsigned int nFrames, double streamTime,
                                  RtAudioStreamStatus status, void *userData);
    static int testOutputCallback(void *outputBuffer, void *inputBuffer,
                                   unsigned int nFrames, double streamTime,
                                   RtAudioStreamStatus status, void *userData);
    size_t m_playbackPos = 0;
#endif
};
