#ifndef AUDIOINPUT_RTAUDIO_H
#define AUDIOINPUT_RTAUDIO_H

#include "AudioInput.h"

#ifdef ENABLE_RTAUDIO

#include <RtAudio.h>
#include <memory>
#include <vector>
#include <atomic>

// ─────────────────────────────────────────────────────
//  AudioInputRtAudio — RtAudio/WASAPI backend
//
//  Uses RtAudio for low-latency audio capture.
//  On Windows, defaults to WASAPI shared mode.
//  The RtAudio callback runs on an internal thread;
//  we dispatch data to the pipeline callback from there.
// ─────────────────────────────────────────────────────
class AudioInputRtAudio : public AudioInput
{
    Q_OBJECT
public:
    explicit AudioInputRtAudio(QObject *parent = nullptr);
    ~AudioInputRtAudio() override;

    bool open(int sampleRate, int channels) override;
    bool start() override;
    void stop()  override;
    void suspend() override;
    void resume()  override;
    bool isRunning() const override;
    QString backendName() const override { return QStringLiteral("rtaudio"); }

private:
    static int rtCallback(void *outputBuffer, void *inputBuffer,
                          unsigned int nFrames,
                          double streamTime,
                          RtAudioStreamStatus status,
                          void *userData);

    std::unique_ptr<RtAudio> m_rt;
    int m_sampleRate = 16000;
    int m_channels   = 1;
    unsigned int m_bufferFrames = 512;
    std::atomic<bool> m_running{false};
    std::atomic<bool> m_suspended{false};
};

#endif // ENABLE_RTAUDIO
#endif // AUDIOINPUT_RTAUDIO_H
