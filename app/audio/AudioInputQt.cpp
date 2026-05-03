#include "AudioInputQt.h"

#include <QDebug>
#include <cstring>

AudioInputQt::AudioInputQt(QObject *parent)
    : AudioInput(parent)
{}

AudioInputQt::~AudioInputQt()
{
    stop();
}

bool AudioInputQt::open(int sampleRate, int channels)
{
    m_format.setSampleRate(sampleRate);
    m_format.setChannelCount(channels);
    m_format.setSampleFormat(QAudioFormat::Int16);

    const QAudioDevice &dev = QMediaDevices::defaultAudioInput();
    if (dev.isNull()) {
        emit error(QStringLiteral("AudioInputQt: aucun périphérique d'entrée"));
        return false;
    }

    if (!dev.isFormatSupported(m_format)) {
        qWarning() << "AudioInputQt: format non supporté, utilisation du format préféré";
        m_format = dev.preferredFormat();
    }

    qDebug() << "AudioInputQt: ouvert —" << dev.description()
             << "rate:" << m_format.sampleRate()
             << "ch:" << m_format.channelCount();
    return true;
}

bool AudioInputQt::start()
{
    if (m_running) return true;

    const QAudioDevice &dev = QMediaDevices::defaultAudioInput();
    if (dev.isNull()) {
        emit error(QStringLiteral("AudioInputQt: aucun micro disponible"));
        return false;
    }

    m_source = std::make_unique<QAudioSource>(dev, m_format);
    m_io = m_source->start();
    if (!m_io) {
        emit error(QStringLiteral("AudioInputQt: impossible de démarrer la capture"));
        return false;
    }

    connect(m_io, &QIODevice::readyRead, this, &AudioInputQt::onReadyRead);
    m_running = true;
    return true;
}

void AudioInputQt::stop()
{
    if (!m_running) return;
    if (m_source) {
        m_source->stop();
        m_source.reset();
    }
    m_io = nullptr;
    m_running = false;
}

void AudioInputQt::suspend()
{
    if (m_source) m_source->suspend();
}

void AudioInputQt::resume()
{
    if (m_source) m_source->resume();
}

bool AudioInputQt::isRunning() const
{
    return m_running;
}

void AudioInputQt::onReadyRead()
{
    if (!m_io || !m_callback) return;

    QByteArray raw = m_io->readAll();
    if (raw.isEmpty()) return;

    int sampleCount = raw.size() / static_cast<int>(sizeof(int16_t));
    if (sampleCount <= 0) return;

    m_callback(reinterpret_cast<const int16_t *>(raw.constData()), sampleCount);
}
