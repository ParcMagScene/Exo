#ifdef ENABLE_RTAUDIO

#include "TTSAudioSinkRtAudio.h"
#include "TTSManager.h"   // pour PCMRingBuffer
#include <QDebug>
#include <cstring>

TTSAudioSinkRtAudio::TTSAudioSinkRtAudio() = default;

TTSAudioSinkRtAudio::~TTSAudioSinkRtAudio()
{
    close();
}

bool TTSAudioSinkRtAudio::open(int sampleRate, int channels, PCMRingBuffer *ringBuffer,
                               unsigned int bufferFrames,
                               const std::string &deviceNameSubstr)
{
    if (!ringBuffer) {
        qWarning() << "TTSAudioSinkRtAudio: ringBuffer nullptr";
        return false;
    }
    m_ring        = ringBuffer;
    m_sampleRate  = sampleRate;
    m_channels    = channels;
    m_bufferFrames = bufferFrames;

#ifdef _WIN32
    m_rt = std::make_unique<RtAudio>(RtAudio::WINDOWS_WASAPI,
        [](RtAudioErrorType type, const std::string &msg) {
            qWarning() << "TTSAudioSinkRtAudio [RtAudio]:" << type
                       << QString::fromStdString(msg);
        });
#else
    m_rt = std::make_unique<RtAudio>(RtAudio::Api::UNSPECIFIED,
        [](RtAudioErrorType type, const std::string &msg) {
            qWarning() << "TTSAudioSinkRtAudio [RtAudio]:" << type
                       << QString::fromStdString(msg);
        });
#endif

    if (m_rt->getDeviceCount() == 0) {
        qWarning() << "TTSAudioSinkRtAudio: aucun device";
        return false;
    }

    unsigned int devId = m_rt->getDefaultOutputDevice();
    if (!deviceNameSubstr.empty()) {
        auto ids = m_rt->getDeviceIds();
        for (unsigned int id : ids) {
            auto di = m_rt->getDeviceInfo(id);
            if (di.outputChannels >= (unsigned)channels &&
                di.name.find(deviceNameSubstr) != std::string::npos) {
                devId = id;
                break;
            }
        }
    }

    auto info = m_rt->getDeviceInfo(devId);
    if (info.outputChannels == 0) {
        qWarning() << "TTSAudioSinkRtAudio: device" << devId << "n'a pas de canaux out";
        return false;
    }

    qDebug() << "TTSAudioSinkRtAudio: device" << QString::fromStdString(info.name)
             << "rate:" << m_sampleRate << "ch:" << m_channels
             << "bufferFrames:" << m_bufferFrames;

    RtAudio::StreamParameters params;
    params.deviceId     = devId;
    params.nChannels    = static_cast<unsigned int>(m_channels);
    params.firstChannel = 0;

    RtAudio::StreamOptions opts;
    opts.flags = RTAUDIO_SCHEDULE_REALTIME;
    opts.priority = 1;

    RtAudioErrorType err = m_rt->openStream(
        &params, nullptr,
        RTAUDIO_SINT16,
        static_cast<unsigned int>(m_sampleRate),
        &m_bufferFrames,
        &TTSAudioSinkRtAudio::rtCallback,
        this,
        &opts);
    if (err != RTAUDIO_NO_ERROR) {
        qWarning() << "TTSAudioSinkRtAudio: openStream FAIL" << (int)err;
        return false;
    }

    qDebug() << "TTSAudioSinkRtAudio: stream OUVERT (pas encore demarre), bufferFrames negociees:"
             << m_bufferFrames;
    return true;
}

bool TTSAudioSinkRtAudio::start()
{
    if (!m_rt || !m_rt->isStreamOpen()) {
        qWarning() << "TTSAudioSinkRtAudio::start() sans openStream prealable";
        return false;
    }
    if (m_rt->isStreamRunning()) {
        m_running = true;
        return true;
    }
    RtAudioErrorType err = m_rt->startStream();
    if (err != RTAUDIO_NO_ERROR) {
        qWarning() << "TTSAudioSinkRtAudio: startStream FAIL" << (int)err;
        return false;
    }
    m_running = true;
    qDebug() << "TTSAudioSinkRtAudio: stream DEMARRE";
    return true;
}

void TTSAudioSinkRtAudio::stop()
{
    // ATTENTION : ne ferme PAS le stream, juste pause.
    // closeStream() laisse le sink dans un etat inutilisable jusqu'au prochain
    // open() complet, ce qui casse le pipeline TTS multi-phrases.
    // Le destructeur ~TTSAudioSinkRtAudio appelle close() qui fait closeStream.
    if (!m_running) return;
    m_running = false;
    if (m_rt && m_rt->isStreamOpen() && m_rt->isStreamRunning()) {
        m_rt->stopStream();
    }
}

void TTSAudioSinkRtAudio::close()
{
    m_running = false;
    if (m_rt && m_rt->isStreamOpen()) {
        if (m_rt->isStreamRunning())
            m_rt->stopStream();
        m_rt->closeStream();
    }
}

int TTSAudioSinkRtAudio::rtCallback(void *outputBuffer, void * /*inputBuffer*/,
                                    unsigned int nFrames,
                                    double /*streamTime*/,
                                    RtAudioStreamStatus status,
                                    void *userData)
{
    auto *self = static_cast<TTSAudioSinkRtAudio *>(userData);
    if (!self || !outputBuffer) return 0;

    const int frameBytes = self->m_channels * static_cast<int>(sizeof(int16_t));
    const int wantBytes  = static_cast<int>(nFrames) * frameBytes;
    char *out = static_cast<char *>(outputBuffer);

    if (!self->m_ring) {
        std::memset(out, 0, wantBytes);
        return 0;
    }

    const int got = self->m_ring->read(out, wantBytes);
    if (got < wantBytes) {
        // Underflow : silence-fill le reste. Ne jamais retourner moins de
        // donnees que ce que WASAPI demande -> sinon click immediat.
        std::memset(out + got, 0, wantBytes - got);
        if (got < wantBytes && self->m_running.load())
            self->m_underflowCount.fetch_add(1, std::memory_order_relaxed);
    }
    self->m_framesWritten.fetch_add(nFrames, std::memory_order_relaxed);
    (void)status;
    return 0;
}

#endif // ENABLE_RTAUDIO
