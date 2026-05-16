#include "AudioDeviceManager.h"
#include <QDebug>
#include <QtMath>
#include <QMetaObject>
#include <QDesktopServices>
#include <QUrl>

// ═══════════════════════════════════════════════════════
//  AudioDeviceManager — implémentation
// ═══════════════════════════════════════════════════════

AudioDeviceManager::AudioDeviceManager(QObject *parent)
    : QObject(parent)
{
    connect(&m_healthTimer, &QTimer::timeout,
            this, &AudioDeviceManager::onHealthCheckTimer);

#ifdef ENABLE_RTAUDIO
    ensureRtAudio();
#endif

    // Scan initial
    scanDevices();
}

AudioDeviceManager::~AudioDeviceManager()
{
    stopAudioTest();
    stopHealthCheck();
}

#ifdef ENABLE_RTAUDIO
void AudioDeviceManager::ensureRtAudio() const
{
    if (!m_rtAudio) {
        m_rtAudio = std::make_unique<RtAudio>(
#ifdef _WIN32
            RtAudio::WINDOWS_WASAPI,
#else
            RtAudio::Api::UNSPECIFIED,
#endif
            [](RtAudioErrorType /*type*/, const std::string &msg) {
                qWarning() << "AudioDeviceManager [RtAudio]:" << QString::fromStdString(msg);
            });
    }
}
#endif

// ─────────────────────────────────────────────────────
//  Enumération des devices d'entrée
// ─────────────────────────────────────────────────────

void AudioDeviceManager::scanDevices()
{
    m_devices.clear();

#ifdef ENABLE_RTAUDIO
    ensureRtAudio();

    auto ids = m_rtAudio->getDeviceIds();
    for (unsigned int id : ids) {
        auto info = m_rtAudio->getDeviceInfo(id);
        if (info.inputChannels > 0) {
            DeviceInfo di;
            di.rtId = id;
            di.name = QString::fromStdString(info.name);
            di.inputChannels = static_cast<int>(info.inputChannels);
            m_devices.push_back(di);
        }
    }

    // Auto-sélection : chercher le device par défaut, sinon le premier
    if (m_selectedIndex < 0 || m_selectedIndex >= static_cast<int>(m_devices.size())) {
        unsigned int defaultId = m_rtAudio->getDefaultInputDevice();
        m_selectedIndex = -1;
        for (int i = 0; i < static_cast<int>(m_devices.size()); ++i) {
            if (m_devices[i].rtId == defaultId) {
                m_selectedIndex = i;
                break;
            }
        }
        if (m_selectedIndex < 0 && !m_devices.empty())
            m_selectedIndex = 0;
    }
#endif

    qDebug() << "AudioDeviceManager: scan terminé —"
             << m_devices.size() << "device(s) d'entrée trouvé(s)";
    for (size_t i = 0; i < m_devices.size(); ++i) {
        qDebug() << "  [" << i << "]" << m_devices[i].name
                 << "(rtId:" << m_devices[i].rtId
                 << ", ch:" << m_devices[i].inputChannels << ")";
    }

    emit devicesChanged();

    if (m_devices.empty()) {
        setLastError("Aucun microphone détecté");
        setAudioStatus("down");
        emit audioUnavailable();
    } else {
        emit audioReady();
    }
}

QStringList AudioDeviceManager::inputDevices() const
{
    QStringList list;
    for (const auto &d : m_devices)
        list.append(d.name);
    return list;
}

int AudioDeviceManager::defaultInputDevice() const
{
#ifdef ENABLE_RTAUDIO
    ensureRtAudio();

    unsigned int defaultId = m_rtAudio->getDefaultInputDevice();
    for (int i = 0; i < static_cast<int>(m_devices.size()); ++i) {
        if (m_devices[i].rtId == defaultId)
            return i;
    }
#endif
    return m_devices.empty() ? -1 : 0;
}

bool AudioDeviceManager::hasValidInputDevice() const
{
    return m_selectedIndex >= 0
        && m_selectedIndex < static_cast<int>(m_devices.size());
}

bool AudioDeviceManager::setInputDevice(int index)
{
    if (index < 0 || index >= static_cast<int>(m_devices.size())) {
        setLastError(QString("Index de device invalide : %1").arg(index));
        return false;
    }

    if (index == m_selectedIndex)
        return true;

    m_selectedIndex = index;
    qDebug() << "AudioDeviceManager: device sélectionné —"
             << m_devices[index].name << "(rtId:" << m_devices[index].rtId << ")";

    emit inputDeviceChanged();
    emit deviceSwitchRequested(static_cast<int>(m_devices[index].rtId));
    return true;
}

int AudioDeviceManager::selectedRtAudioDeviceId() const
{
    if (!hasValidInputDevice())
        return -1;
    return static_cast<int>(m_devices[m_selectedIndex].rtId);
}

// ─────────────────────────────────────────────────────
//  Health check
// ─────────────────────────────────────────────────────

void AudioDeviceManager::startHealthCheck(int intervalMs)
{
    m_healthTimer.start(intervalMs);
    qDebug() << "AudioDeviceManager: health check démarré (interval:" << intervalMs << "ms)";
}

void AudioDeviceManager::stopHealthCheck()
{
    m_healthTimer.stop();
}

void AudioDeviceManager::notifyStreamOpened()
{
    m_streamOpen = true;
    setAudioStatus("healthy");
}

void AudioDeviceManager::notifyStreamClosed()
{
    m_streamOpen = false;
    setAudioStatus("down");
}

void AudioDeviceManager::onHealthCheckTimer()
{
    // Re-scan pour détecter branchement/débranchement
    auto previousCount = m_devices.size();
    bool hadDevice = hasValidInputDevice();

#ifdef ENABLE_RTAUDIO
    ensureRtAudio();

    // Perf P0-2: fast-path. getDeviceInfo() par device est coûteux sur WASAPI
    // (10–50 ms cumulés). On compare d'abord la liste d'IDs; si identique au
    // dernier scan, on ne refait PAS getDeviceInfo() et on sort tôt.
    auto ids = m_rtAudio->getDeviceIds();
    if (ids == m_lastDeviceIds && !m_devices.empty()) {
        // Aucune modification matérielle — sortie rapide, on saute aux checks stream.
    } else {
    m_lastDeviceIds = ids;

    std::vector<DeviceInfo> newDevices;
    for (unsigned int id : ids) {
        auto info = m_rtAudio->getDeviceInfo(id);
        if (info.inputChannels > 0) {
            DeviceInfo di;
            di.rtId = id;
            di.name = QString::fromStdString(info.name);
            di.inputChannels = static_cast<int>(info.inputChannels);
            newDevices.push_back(di);
        }
    }

    if (newDevices.size() != previousCount) {
        m_devices = newDevices;

        // Essayer de garder la sélection actuelle
        if (m_selectedIndex >= static_cast<int>(m_devices.size()))
            m_selectedIndex = m_devices.empty() ? -1 : 0;

        emit devicesChanged();

        if (m_devices.empty() && hadDevice) {
            setLastError("Microphone déconnecté");
            setAudioStatus("down");
            emit audioUnavailable();
        } else if (!m_devices.empty() && !hadDevice) {
            setLastError("");
            setAudioStatus(m_streamOpen ? "healthy" : "unknown");
            emit audioReady();
        }
    }
    }
#endif

    // Vérifier l'état du stream
    if (m_streamOpen && hasValidInputDevice()) {
        if (m_audioStatus != "healthy")
            setAudioStatus("healthy");
    } else if (!hasValidInputDevice()) {
        if (m_audioStatus != "down")
            setAudioStatus("down");
    }
}

// ─────────────────────────────────────────────────────
//  VU-mètre RMS (thread-safe)
// ─────────────────────────────────────────────────────

void AudioDeviceManager::feedRmsSamples(const int16_t *samples, int count)
{
    float rms = computeRms(samples, count);
    m_currentRms.store(rms, std::memory_order_relaxed);
    // Émettre depuis le thread Qt
    QMetaObject::invokeMethod(this, [this, rms]() {
        Q_UNUSED(rms);
        emit rmsLevelChanged();
    }, Qt::QueuedConnection);
}

float AudioDeviceManager::computeRms(const int16_t *samples, int count) const
{
    if (count <= 0) return 0.0f;
    double sum = 0.0;
    for (int i = 0; i < count; ++i) {
        double s = samples[i] / 32768.0;
        sum += s * s;
    }
    return static_cast<float>(std::sqrt(sum / count));
}

// ─────────────────────────────────────────────────────
//  Test audio (enregistrement 1s + playback)
// ─────────────────────────────────────────────────────

void AudioDeviceManager::startAudioTest()
{
#ifdef ENABLE_RTAUDIO
    if (m_testRunning) return;
    if (!hasValidInputDevice()) {
        setLastError("Aucun microphone disponible pour le test");
        emit audioTestFinished(false);
        return;
    }

    m_testBuffer.clear();
    m_testBuffer.reserve(m_testSampleRate * m_testRecordMs / 1000);
    m_testRunning = true;
    emit audioTestRunningChanged();

    m_testRt = std::make_unique<RtAudio>(
#ifdef _WIN32
        RtAudio::WINDOWS_WASAPI,
#else
        RtAudio::Api::UNSPECIFIED,
#endif
        [](RtAudioErrorType, const std::string &msg) {
            qWarning() << "AudioDeviceManager [test]:" << QString::fromStdString(msg);
        });

    RtAudio::StreamParameters params;
    params.deviceId = m_devices[m_selectedIndex].rtId;
    params.nChannels = 1;
    params.firstChannel = 0;

    unsigned int bufferFrames = 512;
    RtAudioErrorType err = m_testRt->openStream(
        nullptr, &params, RTAUDIO_SINT16,
        static_cast<unsigned int>(m_testSampleRate),
        &bufferFrames, &AudioDeviceManager::testInputCallback, this);

    if (err != RTAUDIO_NO_ERROR) {
        setLastError("Échec de l'ouverture du stream test");
        m_testRunning = false;
        emit audioTestRunningChanged();
        emit audioTestFinished(false);
        return;
    }

    err = m_testRt->startStream();
    if (err != RTAUDIO_NO_ERROR) {
        setLastError("Échec du démarrage du stream test");
        m_testRt->closeStream();
        m_testRunning = false;
        emit audioTestRunningChanged();
        emit audioTestFinished(false);
        return;
    }

    // Arrêter l'enregistrement après m_testRecordMs ms
    QTimer::singleShot(m_testRecordMs, this, [this]() {
        if (!m_testRunning) return;

        if (m_testRt && m_testRt->isStreamRunning())
            m_testRt->stopStream();
        if (m_testRt && m_testRt->isStreamOpen())
            m_testRt->closeStream();

        qDebug() << "AudioDeviceManager: test enregistrement terminé —"
                 << m_testBuffer.size() << "samples";

        // Jouer le buffer enregistré
        playbackRecordedBuffer();
    });

#else
    setLastError("RtAudio non disponible");
    emit audioTestFinished(false);
#endif
}

void AudioDeviceManager::stopAudioTest()
{
#ifdef ENABLE_RTAUDIO
    if (!m_testRunning) return;

    if (m_testRt) {
        if (m_testRt->isStreamRunning())
            m_testRt->stopStream();
        if (m_testRt->isStreamOpen())
            m_testRt->closeStream();
    }
    m_testRunning = false;
    m_testBuffer.clear();
    emit audioTestRunningChanged();
#endif
}

#ifdef ENABLE_RTAUDIO
int AudioDeviceManager::testInputCallback(void * /*outputBuffer*/, void *inputBuffer,
                                           unsigned int nFrames, double /*streamTime*/,
                                           RtAudioStreamStatus /*status*/, void *userData)
{
    auto *self = static_cast<AudioDeviceManager *>(userData);
    auto *samples = static_cast<const int16_t *>(inputBuffer);

    size_t maxSamples = static_cast<size_t>(self->m_testSampleRate * self->m_testRecordMs / 1000);
    size_t remaining = maxSamples - self->m_testBuffer.size();
    size_t toCopy = std::min(static_cast<size_t>(nFrames), remaining);

    self->m_testBuffer.insert(self->m_testBuffer.end(), samples, samples + toCopy);

    // Mettre à jour le RMS pour le vumètre
    float rms = self->computeRms(samples, static_cast<int>(nFrames));
    self->m_currentRms.store(rms, std::memory_order_relaxed);
    QMetaObject::invokeMethod(self, [self]() {
        emit self->rmsLevelChanged();
    }, Qt::QueuedConnection);

    return 0;
}

void AudioDeviceManager::playbackRecordedBuffer()
{
    if (m_testBuffer.empty()) {
        setLastError("Buffer d'enregistrement vide");
        m_testRunning = false;
        emit audioTestRunningChanged();
        emit audioTestFinished(false);
        return;
    }

    m_playbackPos = 0;

    // Trouver un device de sortie
    auto ids = m_testRt ? m_testRt->getDeviceIds() : std::vector<unsigned int>();
    if (ids.empty()) {
        // Créer une nouvelle instance RtAudio
        m_testRt = std::make_unique<RtAudio>(
#ifdef _WIN32
            RtAudio::WINDOWS_WASAPI,
#else
            RtAudio::Api::UNSPECIFIED,
#endif
            [](RtAudioErrorType, const std::string &) {});
        ids = m_testRt->getDeviceIds();
    }

    unsigned int outDevice = m_testRt->getDefaultOutputDevice();

    RtAudio::StreamParameters outParams;
    outParams.deviceId = outDevice;
    outParams.nChannels = 1;
    outParams.firstChannel = 0;

    unsigned int bufferFrames = 512;
    RtAudioErrorType err = m_testRt->openStream(
        &outParams, nullptr, RTAUDIO_SINT16,
        static_cast<unsigned int>(m_testSampleRate),
        &bufferFrames, &AudioDeviceManager::testOutputCallback, this);

    if (err != RTAUDIO_NO_ERROR) {
        setLastError("Échec de l'ouverture du stream de lecture");
        m_testRunning = false;
        emit audioTestRunningChanged();
        emit audioTestFinished(false);
        return;
    }

    err = m_testRt->startStream();
    if (err != RTAUDIO_NO_ERROR) {
        setLastError("Échec du démarrage de la lecture");
        m_testRt->closeStream();
        m_testRunning = false;
        emit audioTestRunningChanged();
        emit audioTestFinished(false);
        return;
    }

    // Arrêter après la durée du buffer + marge
    int playMs = static_cast<int>(m_testBuffer.size() * 1000 / m_testSampleRate) + 200;
    QTimer::singleShot(playMs, this, [this]() {
        if (m_testRt) {
            if (m_testRt->isStreamRunning())
                m_testRt->stopStream();
            if (m_testRt->isStreamOpen())
                m_testRt->closeStream();
        }
        m_testRunning = false;
        emit audioTestRunningChanged();
        emit audioTestFinished(true);
        qDebug() << "AudioDeviceManager: test audio terminé avec succès";
    });
}

int AudioDeviceManager::testOutputCallback(void *outputBuffer, void * /*inputBuffer*/,
                                            unsigned int nFrames, double /*streamTime*/,
                                            RtAudioStreamStatus /*status*/, void *userData)
{
    auto *self = static_cast<AudioDeviceManager *>(userData);
    auto *out = static_cast<int16_t *>(outputBuffer);

    for (unsigned int i = 0; i < nFrames; ++i) {
        if (self->m_playbackPos < self->m_testBuffer.size()) {
            out[i] = self->m_testBuffer[self->m_playbackPos++];
        } else {
            out[i] = 0;
        }
    }
    return 0;
}
#endif // ENABLE_RTAUDIO

// ─────────────────────────────────────────────────────
//  Ouvrir paramètres Windows
// ─────────────────────────────────────────────────────

void AudioDeviceManager::openWindowsSoundSettings()
{
#ifdef _WIN32
    QMetaObject::invokeMethod(this, []() {
        // Ouvrir via Qt pour rester cross-platform compatible
        QDesktopServices::openUrl(QUrl("ms-settings:sound"));
    }, Qt::QueuedConnection);
#endif
}

// ─────────────────────────────────────────────────────
//  Helpers internes
// ─────────────────────────────────────────────────────

void AudioDeviceManager::setLastError(const QString &err)
{
    if (m_lastError == err) return;
    m_lastError = err;
    if (!err.isEmpty())
        qWarning() << "AudioDeviceManager:" << err;
    emit audioError(err);
}

void AudioDeviceManager::setAudioStatus(const QString &status)
{
    if (m_audioStatus == status) return;
    m_audioStatus = status;
    qDebug() << "AudioDeviceManager: audioStatus ->" << status;
    emit audioStatusChanged();
}
