#ifndef WEBSOCKETCLIENT_H
#define WEBSOCKETCLIENT_H

#include <QObject>
#include <QWebSocket>
#include <QJsonObject>
#include <QJsonDocument>
#include <QTimer>
#include <QUrl>
#include <QString>

// ─────────────────────────────────────────────────────
//  WebSocketClient — reusable WS client with auto-reconnect
//
//  Wraps QWebSocket with:
//   • connection state machine (Disconnected → Connecting → Connected → Reconnecting)
//   • configurable reconnection (fixed delay or exponential backoff)
//   • typed signals for text, binary, JSON
//   • convenience sendJson() helper
//
//  Each microservice (TTS, STT, VAD, WakeWord, Memory) uses
//  one instance instead of duplicating QWebSocket boilerplate.
// ─────────────────────────────────────────────────────

class WebSocketClient : public QObject
{
    Q_OBJECT

public:
    enum class State { Disconnected, Connecting, Connected, Reconnecting };
    Q_ENUM(State)

    explicit WebSocketClient(const QString &name, QObject *parent = nullptr);
    ~WebSocketClient() override;

    // ── Connection lifecycle ──
    void open(const QUrl &url);
    void close();

    // ── Reconnection policy ──
    void setReconnectEnabled(bool enabled);
    void setReconnectParams(int baseMs, int maxAttempts, bool exponential = false);

    // ── Sending ──
    void sendText(const QString &msg);
    void sendJson(const QJsonObject &obj);
    void sendBinary(const QByteArray &data);

    // ── Accessors ──
    bool isConnected() const { return m_state == State::Connected; }
    State state() const { return m_state; }
    QString name() const { return m_name; }
    QUrl url() const { return m_url; }

    // Direct access to underlying socket (for edge-case signal wiring)
    QWebSocket *socket() const { return m_ws; }

signals:
    void connected();
    void disconnected();
    void textReceived(const QString &message);
    void binaryReceived(const QByteArray &data);
    void stateChanged(WebSocketClient::State newState);
    void errorOccurred(const QString &description);

private slots:
    void onConnected();
    void onDisconnected();
    void onError(QAbstractSocket::SocketError err);

private:
    void scheduleReconnect();
    void setState(State s);
    void createSocket();
    void destroySocket();
    void disconnectSocket();

    QString     m_name;       // for log prefix, e.g. "STT", "VAD"
    QWebSocket *m_ws = nullptr;
    QUrl        m_url;
    State       m_state = State::Disconnected;
    bool        m_closing = false;

    // reconnection
    bool m_reconnectEnabled   = true;
    int  m_reconnectBaseMs    = 3000;
    int  m_reconnectMaxAttempts = 0;  // 0 = unlimited
    bool m_reconnectExponential = false;
    int  m_reconnectAttempts  = 0;

    // Audit P2.4 : heartbeat ping applicatif 30s (évite zombies WS)
    QTimer *m_pingTimer = nullptr;
    static constexpr int PING_INTERVAL_MS = 30000;
};

#endif // WEBSOCKETCLIENT_H
