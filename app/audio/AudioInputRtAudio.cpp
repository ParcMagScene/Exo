#ifdef ENABLE_RTAUDIO

#include "AudioInputRtAudio.h"
#include <QDebug>

AudioInputRtAudio::AudioInputRtAudio(QObject *parent)
    : AudioInput(parent)
{}

AudioInputRtAudio::~AudioInputRtAudio()
{
    stop();
}

bool AudioInputRtAudio::open(int sampleRate, int channels)
{
    m_sampleRate = sampleRate;
    m_channels   = channels;

    // RtAudio 6.x: constructor doesn't throw — use error callback for diagnostics
#ifdef _WIN32
    m_rt = std::make_unique<RtAudio>(RtAudio::WINDOWS_WASAPI,
        [](RtAudioErrorType type, const std::string &msg) {
            qWarning() << "AudioInputRtAudio [RtAudio]:" << type
                       << QString::fromStdString(msg);
        });
#else
    m_rt = std::make_unique<RtAudio>(RtAudio::Api::UNSPECIFIED,
        [](RtAudioErrorType type, const std::string &msg) {
            qWarning() << "AudioInputRtAudio [RtAudio]:" << type
                       << QString::fromStdString(msg);
        });
#endif

    if (m_rt->getDeviceCount() == 0) {
        emit error(QStringLiteral("AudioInputRtAudio: aucun périphérique audio détecté"));
        return false;
    }

    unsigned int defaultDev = m_rt->getDefaultInputDevice();
    RtAudio::DeviceInfo info = m_rt->getDeviceInfo(defaultDev);

    // Validate that the default input device is usable
    if (info.inputChannels == 0) {
        qWarning() << "AudioInputRtAudio: device" << defaultDev
                   << "n'a pas de canaux d'entrée — liste des devices:";
        auto ids = m_rt->getDeviceIds();
        for (unsigned int id : ids) {
            auto di = m_rt->getDeviceInfo(id);
            qWarning() << "  device" << id << ":" << QString::fromStdString(di.name)
                       << "in:" << di.inputChannels << "out:" << di.outputChannels;
        }
        emit error(QStringLiteral("AudioInputRtAudio: périphérique d'entrée par défaut invalide (0 canaux d'entrée)"));
        return false;
    }

    qDebug() << "AudioInputRtAudio: ouvert —" << QString::fromStdString(info.name)
             << "rate:" << m_sampleRate << "ch:" << m_channels
             << "inputChannels:" << info.inputChannels;
    return true;
}

bool AudioInputRtAudio::start()
{
    if (m_running) return true;
    if (!m_rt) {
        emit error(QStringLiteral("AudioInputRtAudio: open() non appelé"));
        return false;
    }

    RtAudio::StreamParameters params;
    params.deviceId    = m_rt->getDefaultInputDevice();
    params.nChannels   = static_cast<unsigned int>(m_channels);
    params.firstChannel = 0;

    m_bufferFrames = 512;

    // RtAudio 6.x: openStream/startStream return error codes (no exceptions)
    RtAudioErrorType err = m_rt->openStream(
        nullptr, &params,
        RTAUDIO_SINT16,
        static_cast<unsigned int>(m_sampleRate),
        &m_bufferFrames,
        &AudioInputRtAudio::rtCallback,
        this);

    if (err != RTAUDIO_NO_ERROR) {
        emit error(QStringLiteral("AudioInputRtAudio: openStream a échoué (code %1)")
                       .arg(static_cast<int>(err)));
        return false;
    }

    err = m_rt->startStream();
    if (err != RTAUDIO_NO_ERROR) {
        emit error(QStringLiteral("AudioInputRtAudio: startStream a échoué (code %1)")
                       .arg(static_cast<int>(err)));
        m_rt->closeStream();
        return false;
    }

    m_running = true;
    m_suspended = false;
    qDebug() << "AudioInputRtAudio: stream démarré — bufferFrames:" << m_bufferFrames;
    return true;
}

void AudioInputRtAudio::stop()
{
    if (!m_running) return;
    m_running = false;
    m_suspended = false;

    if (m_rt && m_rt->isStreamOpen()) {
        if (m_rt->isStreamRunning())
            m_rt->stopStream();
        m_rt->closeStream();
    }
    qDebug() << "AudioInputRtAudio: stream arrêté";
}

void AudioInputRtAudio::suspend()
{
    m_suspended = true;
}

void AudioInputRtAudio::resume()
{
    m_suspended = false;
}

bool AudioInputRtAudio::isRunning() const
{
    return m_running;
}

int AudioInputRtAudio::rtCallback(void * /*outputBuffer*/, void *inputBuffer,
                                   unsigned int nFrames,
                                   double /*streamTime*/,
                                   RtAudioStreamStatus status,
                                   void *userData)
{
    auto *self = static_cast<AudioInputRtAudio *>(userData);
    if (status)
        qWarning() << "AudioInputRtAudio: stream overflow/underflow";

    if (self->m_suspended || !self->m_callback)
        return 0;

    auto *samples = static_cast<const int16_t *>(inputBuffer);
    self->m_callback(samples, static_cast<int>(nFrames));
    return 0;
}

#endif // ENABLE_RTAUDIO
