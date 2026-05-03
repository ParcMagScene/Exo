#ifndef AUDIOINPUT_H
#define AUDIOINPUT_H

#include <QObject>
#include <functional>
#include <cstdint>

// ─────────────────────────────────────────────────────
//  AudioInput — abstract audio capture interface
//
//  Allows swapping between Qt Multimedia and RtAudio
//  backends without changing the pipeline logic.
// ─────────────────────────────────────────────────────
class AudioInput : public QObject
{
    Q_OBJECT
public:
    using AudioCallback = std::function<void(const int16_t *samples, int count)>;

    explicit AudioInput(QObject *parent = nullptr) : QObject(parent) {}
    virtual ~AudioInput() = default;

    virtual bool open(int sampleRate, int channels) = 0;
    virtual bool start() = 0;
    virtual void stop()  = 0;
    virtual void suspend() = 0;
    virtual void resume()  = 0;
    virtual bool isRunning() const = 0;
    virtual QString backendName() const = 0;

    void setCallback(AudioCallback cb) { m_callback = std::move(cb); }

signals:
    void error(const QString &msg);

protected:
    AudioCallback m_callback;
};

#endif // AUDIOINPUT_H
