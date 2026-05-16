#ifdef ENABLE_RTAUDIO

#include "TTSAudioSinkRtAudio.h"
#include "TTSManager.h"   // pour PCMRingBuffer
#include <QDebug>
#include <cstring>
#include <cstdlib>
#include <string>

TTSAudioSinkRtAudio::TTSAudioSinkRtAudio()
{
    // Hardening 2026-05-16 : init opt-in du watchdog audio.
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable: 4996) // std::getenv jugé "unsafe" par MSVC, lecture seule ici.
#endif
    const char *env = std::getenv("EXO_AUDIO_WATCHDOG_MS");
#ifdef _MSC_VER
#pragma warning(pop)
#endif
    if (env) {
        try {
            const int thresh = std::stoi(env);
            if (thresh > 0) {
                m_watchdog = std::make_unique<exo::hardening::LatencyWatchdog>(thresh);
                qDebug() << "TTSAudioSinkRtAudio : LatencyWatchdog activé seuil" << thresh << "ms";
            }
        } catch (...) { /* env invalide : watchdog désactivé */ }
    }
}

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
    // AUDIT AUDIO 2026-05-04 : SCHEDULE_REALTIME + priorite max plage RtAudio
    // (Windows : SetThreadPriority THREAD_PRIORITY_TIME_CRITICAL = 15). Reduit
    // drastiquement le risque de preemption du callback WASAPI -> elimine les
    // jitter spikes >100 ms causes par un wakeup OS tardif.
    opts.flags = RTAUDIO_SCHEDULE_REALTIME | RTAUDIO_MINIMIZE_LATENCY;
    opts.priority = 15;

    RtAudioErrorType err = m_rt->openStream(
        &params, nullptr,
        RTAUDIO_SINT16,
        static_cast<unsigned int>(m_sampleRate),
        &m_bufferFrames,
        &TTSAudioSinkRtAudio::rtCallback,
        this,
        &opts);
    if (err != RTAUDIO_NO_ERROR) {
        qWarning() << "TTSAudioSinkRtAudio : échec ouverture stream" << (int)err;
        return false;
    }

    qDebug() << "TTSAudioSinkRtAudio : stream ouvert (pas encore démarré), bufferFrames négociées :"
             << m_bufferFrames;
    return true;
}

bool TTSAudioSinkRtAudio::start()
{
    if (!m_rt || !m_rt->isStreamOpen()) {
        qWarning() << "TTSAudioSinkRtAudio::start() sans openStream préalable";
        return false;
    }
    if (m_rt->isStreamRunning()) {
        m_running = true;
        return true;
    }
    RtAudioErrorType err = m_rt->startStream();
    if (err != RTAUDIO_NO_ERROR) {
        qWarning() << "TTSAudioSinkRtAudio : échec démarrage stream" << (int)err;
        return false;
    }
    m_running = true;
    qDebug() << "TTSAudioSinkRtAudio : stream démarré";
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

    // Hardening 2026-05-16 : watchdog opt-in (log uniquement, no-op si désactivé).
    if (self->m_watchdog) self->m_watchdog->tick();
    (void)status;

    const int frameBytes = self->m_channels * static_cast<int>(sizeof(int16_t));
    const int wantBytes  = static_cast<int>(nFrames) * frameBytes;
    char *out = static_cast<char *>(outputBuffer);

    if (!self->m_ring) {
        std::memset(out, 0, wantBytes);
        return 0;
    }

    const int got = self->m_ring->read(out, wantBytes);
    if (got < wantBytes) {
        // AUDIT AUDIO 2026-05-04 : anti-click fin de phrase. Au lieu d'un
        // memset(0) brutal (cause un step DC -> craquement audible), on
        // applique un fade lineaire du dernier sample disponible vers 0 sur
        // les premiers ~5 ms de la zone manquante, puis silence pur.
        const int missing = wantBytes - got;
        char *fillStart = out + got;
        const int chBytes = self->m_channels * static_cast<int>(sizeof(int16_t));
        // Fade window : min(missing, 5 ms) frames.
        int fadeFrames = (missing / std::max(1, chBytes));
        const int fadeMaxFrames = (self->m_sampleRate * 5) / 1000;
        if (fadeFrames > fadeMaxFrames) fadeFrames = fadeMaxFrames;
        if (got >= chBytes && fadeFrames > 0) {
            const int16_t *lastFrame = reinterpret_cast<const int16_t *>(out + got - chBytes);
            int16_t *dst = reinterpret_cast<int16_t *>(fillStart);
            for (int f = 0; f < fadeFrames; ++f) {
                const float gain = 1.0f - (static_cast<float>(f + 1) / static_cast<float>(fadeFrames + 1));
                for (int c = 0; c < self->m_channels; ++c) {
                    const int v = static_cast<int>(static_cast<float>(lastFrame[c]) * gain);
                    dst[f * self->m_channels + c] =
                        static_cast<int16_t>(v < -32768 ? -32768 : (v > 32767 ? 32767 : v));
                }
            }
            const int fadedBytes = fadeFrames * chBytes;
            std::memset(fillStart + fadedBytes, 0, missing - fadedBytes);
        } else {
            std::memset(fillStart, 0, missing);
        }
        if (self->m_running.load())
            self->m_underflowCount.fetch_add(1, std::memory_order_relaxed);
    }
    self->m_framesWritten.fetch_add(nFrames, std::memory_order_relaxed);

    // Telemetrie underflow : log periodique (toutes les ~5 s) si des
    // underflows se sont produits depuis le dernier log. Permet de
    // diagnostiquer un crackling silencieux a partir des logs.
    if (self->m_running.load()) {
        static thread_local uint64_t s_lastLoggedUnderflows = 0;
        static thread_local uint64_t s_lastLoggedFrames     = 0;
        const uint64_t framesNow = self->m_framesWritten.load(std::memory_order_relaxed);
        const uint64_t framesSinceLog = framesNow - s_lastLoggedFrames;
        const uint64_t intervalFrames = static_cast<uint64_t>(self->m_sampleRate) * 5; // ~5 s
        if (framesSinceLog >= intervalFrames) {
            const uint64_t totalUf = self->m_underflowCount.load(std::memory_order_relaxed);
            const uint64_t deltaUf = totalUf - s_lastLoggedUnderflows;
            if (deltaUf > 0) {
                qWarning() << "[TTSAudioSink] underflows derniers 5s :" << deltaUf
                           << "(total :" << totalUf
                           << ", frames ecrites :" << framesNow << ")";
            }
            s_lastLoggedUnderflows = totalUf;
            s_lastLoggedFrames     = framesNow;
        }
    }
    (void)status;
    return 0;
}

#endif // ENABLE_RTAUDIO
