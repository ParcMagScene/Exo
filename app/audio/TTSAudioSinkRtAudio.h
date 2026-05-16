#ifndef TTS_AUDIO_SINK_RTAUDIO_H
#define TTS_AUDIO_SINK_RTAUDIO_H

#ifdef ENABLE_RTAUDIO

#include <RtAudio.h>
#include <atomic>
#include <memory>
#include <string>

class PCMRingBuffer;

// ─────────────────────────────────────────────────────
//  TTSAudioSinkRtAudio — sortie audio RtAudio/WASAPI
//
//  Bypasse QAudioSink (Qt6 cause craquements en mode SHARED). Le
//  callback RtAudio s'execute sur un thread audio dedie -> immune
//  au jitter de la Qt event loop. Lit directement le PCMRingBuffer
//  (SPSC safe). Si underflow : silence-fill (ne laisse JAMAIS le
//  buffer WASAPI vide -> evite les glitches).
// ─────────────────────────────────────────────────────
class TTSAudioSinkRtAudio
{
public:
    TTSAudioSinkRtAudio();
    ~TTSAudioSinkRtAudio();

    // Ouvre le stream WASAPI mais NE LE DEMARRE PAS (utiliser start()).
    // bufferFrames typique : 480 (10 ms @ 48kHz).
    // Si deviceNameSubstr non vide, cherche un device dont le nom contient cette sous-chaine.
    bool open(int sampleRate, int channels, PCMRingBuffer *ringBuffer,
              unsigned int bufferFrames = 480,
              const std::string &deviceNameSubstr = std::string());

    // Demarre la lecture. A appeler APRES qu'au moins ~bufferFrames*N
    // soient deja dans le ring (anti-click au demarrage).
    bool start();

    // Pause le stream (peut etre redemarre par start() sans reouvrir).
    void stop();
    // Ferme completement le stream (a appeler uniquement avant destruction).
    void close();
    bool isOpen()    const { return m_rt && m_rt->isStreamOpen(); }
    bool isRunning() const { return m_running.load(); }

    // Statistiques (optionnel pour logs)
    uint64_t underflowCount() const { return m_underflowCount.load(); }
    uint64_t framesWritten()  const { return m_framesWritten.load(); }

    int sampleRate() const { return m_sampleRate; }
    int channels()   const { return m_channels; }

private:
    static int rtCallback(void *outputBuffer, void *inputBuffer,
                          unsigned int nFrames,
                          double streamTime,
                          RtAudioStreamStatus status,
                          void *userData);

    std::unique_ptr<RtAudio> m_rt;
    PCMRingBuffer           *m_ring = nullptr;
    int m_sampleRate = 48000;
    int m_channels   = 2;
    unsigned int m_bufferFrames = 480;
    std::atomic<bool>     m_running{false};
    std::atomic<uint64_t> m_underflowCount{0};
    std::atomic<uint64_t> m_framesWritten{0};
};

#endif // ENABLE_RTAUDIO
#endif // TTS_AUDIO_SINK_RTAUDIO_H
