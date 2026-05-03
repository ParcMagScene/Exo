#ifndef TTSBACKENDQT_H
#define TTSBACKENDQT_H

#include "TTSBackend.h"

class QTextToSpeech;

// ─────────────────────────────────────────────────────
//  TTSBackendQt — Windows SAPI / Qt TextToSpeech
//
//  Non-blocking synthesis via QEventLoop + stateChanged signal.
//  Used as fallback when XTTS v2 is unavailable.
// ─────────────────────────────────────────────────────
class TTSBackendQt : public TTSBackend
{
    Q_OBJECT
public:
    explicit TTSBackendQt(QObject *parent = nullptr);
    ~TTSBackendQt() override;

    QString name() const override { return QStringLiteral("QtTTS"); }
    bool isAvailable() const override;
    bool synthesize(const TTSRequest &req) override;
    void cancel() override;
    void init() override;

    void setVoice(const QString &name);

signals:
    void voiceInfo(const QString &name, int voiceCount);

private:
    QTextToSpeech *m_tts = nullptr;
    static constexpr int QT_TTS_TIMEOUT_MS = 30000;
};

#endif // TTSBACKENDQT_H
