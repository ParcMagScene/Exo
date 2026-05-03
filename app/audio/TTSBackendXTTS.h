#ifndef TTSBACKENDXTTS_H
#define TTSBACKENDXTTS_H

#include "TTSBackend.h"

class QWebSocket;

// ─────────────────────────────────────────────────────
//  TTSBackendXTTS — CosyVoice2-0.5B Python backend (CUDA)
//
//  Non-blocking WebSocket synthesis via QEventLoop.
//  Protocol: JSON control + binary PCM16 chunks.
//  (class name kept as TTSBackendXTTS for ABI compat)
// ─────────────────────────────────────────────────────
class TTSBackendXTTS : public TTSBackend
{
    Q_OBJECT
public:
    explicit TTSBackendXTTS(QObject *parent = nullptr);
    ~TTSBackendXTTS() override;

    QString name() const override { return QStringLiteral("CosyVoice2"); }
    bool isAvailable() const override;
    bool synthesize(const TTSRequest &req) override;
    void cancel() override;
    void resetConnection() override;

    void setUrl(const QString &url);
    void setVoice(const QString &voice);
    void setLang(const QString &lang);
    void warmConnect();  // establish WebSocket eagerly at startup

private:
    bool ensureConnected();
    bool tryConnect();

    QWebSocket *m_ws = nullptr;
    QString m_url;
    QString m_voice = "fr_denise";
    QString m_lang  = "fr";
    bool m_connected = false;
    bool m_readyReceived = false;

    // P1.3: Increased from 12s to 30s for CosyVoice2 under GPU load
    // Typical: 1.0-1.2s first chunk, 2-5s full phrase, max ~20s under GPU contention
    static constexpr int PY_TTS_TIMEOUT_MS = 30000;  // 30s timeout (covers 99.9% cases)
    QTimer *m_keepaliveTimer = nullptr;
    void setupKeepalive();
};

#endif // TTSBACKENDXTTS_H
