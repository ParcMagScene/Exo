#ifndef AUDIOINPUT_QT_H
#define AUDIOINPUT_QT_H

#include "AudioInput.h"

#include <QAudioSource>
#include <QAudioFormat>
#include <QAudioDevice>
#include <QMediaDevices>
#include <QIODevice>
#include <memory>

// ─────────────────────────────────────────────────────
//  AudioInputQt — Qt Multimedia backend (QAudioSource)
// ─────────────────────────────────────────────────────
class AudioInputQt : public AudioInput
{
    Q_OBJECT
public:
    explicit AudioInputQt(QObject *parent = nullptr);
    ~AudioInputQt() override;

    bool open(int sampleRate, int channels) override;
    bool start() override;
    void stop()  override;
    void suspend() override;
    void resume()  override;
    bool isRunning() const override;
    QString backendName() const override { return QStringLiteral("qt"); }

private slots:
    void onReadyRead();

private:
    QAudioFormat m_format;
    std::unique_ptr<QAudioSource> m_source;
    QIODevice *m_io = nullptr;
    bool m_running = false;
};

#endif // AUDIOINPUT_QT_H
