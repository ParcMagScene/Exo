#include "WebSocketClient.h"
#include "core/LogManager.h"
#include "MetricsManager.h"
#include "TraceManager.h"
#include <algorithm>

// ═══════════════════════════════════════════════════════
//  WebSocketClient — implementation
// ═══════════════════════════════════════════════════════

WebSocketClient::WebSocketClient(const QString &name, QObject *parent)
    : QObject(parent)
    , m_name(name)
{
}

WebSocketClient::~WebSocketClient()
{
    m_reconnectEnabled = false;
    if (m_ws) {
        disconnectSocket();
        m_ws->abort();
        m_ws->deleteLater();
        m_ws = nullptr;
    }
}

// ── Connection lifecycle ─────────────────────────────

void WebSocketClient::open(const QUrl &url)
{
    m_url = url;
    m_reconnectAttempts = 0;
    m_closing = false;
    MetricsManager::instance()->increment(QStringLiteral("ws.connect_attempts"));

    destroySocket();
    createSocket();

    setState(State::Connecting);
    hDebug(exoMain) << "[WS:" << m_name << "] connecting to" << url.toString();
    m_ws->open(url);
}

void WebSocketClient::close()
{
    m_closing = true;
    m_reconnectEnabled = false;
    if (m_ws && m_ws->state() != QAbstractSocket::UnconnectedState) {
        m_ws->close();
    }
    setState(State::Disconnected);
}

// ── Reconnection policy ──────────────────────────────

void WebSocketClient::setReconnectEnabled(bool enabled)
{
    m_reconnectEnabled = enabled;
}

void WebSocketClient::setReconnectParams(int baseMs, int maxAttempts, bool exponential)
{
    m_reconnectBaseMs       = baseMs;
    m_reconnectMaxAttempts  = maxAttempts;
    m_reconnectExponential  = exponential;
}

// ── Sending ──────────────────────────────────────────

void WebSocketClient::sendText(const QString &msg)
{
    if (m_state != State::Connected || !m_ws) return;
    m_ws->sendTextMessage(msg);
}

void WebSocketClient::sendJson(const QJsonObject &obj)
{
    if (m_state != State::Connected || !m_ws) return;
    m_ws->sendTextMessage(QString::fromUtf8(
        QJsonDocument(obj).toJson(QJsonDocument::Compact)));
}

void WebSocketClient::sendBinary(const QByteArray &data)
{
    if (m_state != State::Connected || !m_ws) return;
    MetricsManager::instance()->increment(QStringLiteral("ws.binary_sent"));
    MetricsManager::instance()->recordValue(QStringLiteral("ws.binary_size_bytes"), data.size());
    m_ws->sendBinaryMessage(data);
}

// ── Private slots ────────────────────────────────────

void WebSocketClient::onConnected()
{
    m_reconnectAttempts = 0;
    setState(State::Connected);
    MetricsManager::instance()->increment(QStringLiteral("ws.connections_established"));
    hDebug(exoMain) << "[WS:" << m_name << "] connected";

    // Audit P2.4 : armer ping 30s pour détecter zombies (TCP keepalive OS = 2h)
    if (!m_pingTimer) {
        m_pingTimer = new QTimer(this);
        connect(m_pingTimer, &QTimer::timeout, this, [this]() {
            if (m_ws && m_state == State::Connected) {
                m_ws->ping();
            }
        });
    }
    m_pingTimer->start(PING_INTERVAL_MS);

    emit connected();
}

void WebSocketClient::onDisconnected()
{
    setState(State::Disconnected);
    if (m_pingTimer) m_pingTimer->stop(); // Audit P2.4
    hDebug(exoMain) << "[WS:" << m_name << "] disconnected";
    if (!m_closing)
        emit disconnected();
    if (!m_closing)
        scheduleReconnect();
}

void WebSocketClient::onError(QAbstractSocket::SocketError err)
{
    Q_UNUSED(err)
    if (m_closing) return;
    MetricsManager::instance()->increment(QStringLiteral("ws.errors"));
    QString desc = m_ws ? m_ws->errorString() : QStringLiteral("unknown");
    hWarning(exoMain) << "[WS:" << m_name << "] error:" << desc;
    emit errorOccurred(desc);

    // If we were connecting and got an error, schedule reconnect
    if (m_state == State::Connecting) {
        setState(State::Disconnected);
        scheduleReconnect();
    }
}

// ── Reconnection logic ──────────────────────────────

void WebSocketClient::scheduleReconnect()
{
    if (!m_reconnectEnabled || m_closing) return;
    if (m_reconnectMaxAttempts > 0 && m_reconnectAttempts >= m_reconnectMaxAttempts) {
        hWarning(exoMain) << "[WS:" << m_name << "] max reconnect attempts reached ("
                             << m_reconnectMaxAttempts << ")";
        emit errorOccurred(m_name + " server unreachable");
        return;
    }

    int delay = m_reconnectBaseMs;
    if (m_reconnectExponential) {
        delay = m_reconnectBaseMs * (1 << std::min(m_reconnectAttempts, 5));
    }
    ++m_reconnectAttempts;

    setState(State::Reconnecting);
    hDebug(exoMain) << "[WS:" << m_name << "] reconnecting in" << delay
             << "ms (attempt" << m_reconnectAttempts << ")";

    QTimer::singleShot(delay, this, [this]() {
        if (m_closing) return;
        if (m_state == State::Reconnecting) {
            // v5.1: créer un socket frais pour éviter QNativeSocketEngine warnings
            destroySocket();
            createSocket();
            setState(State::Connecting);
            m_ws->open(m_url);
        }
    });
}

// ── Socket lifecycle helpers ─────────────────────────

void WebSocketClient::createSocket()
{
    m_ws = new QWebSocket(QString(), QWebSocketProtocol::VersionLatest, this);
    connect(m_ws, &QWebSocket::connected,
            this, &WebSocketClient::onConnected);
    connect(m_ws, &QWebSocket::disconnected,
            this, &WebSocketClient::onDisconnected);
    connect(m_ws, &QWebSocket::textMessageReceived,
            this, &WebSocketClient::textReceived);
    connect(m_ws, &QWebSocket::binaryMessageReceived,
            this, &WebSocketClient::binaryReceived);
    connect(m_ws, &QWebSocket::errorOccurred,
            this, &WebSocketClient::onError);
}

void WebSocketClient::destroySocket()
{
    if (!m_ws) return;
    disconnectSocket();
    m_ws->abort();
    // deleteLater au lieu de delete : le destructeur de QWebSocket appelle
    // m_pSocket->disconnect() (wildcard) sur un QTcpSocket potentiellement
    // détruit — en différant, le cleanup Qt interne se fait proprement.
    m_ws->deleteLater();
    m_ws = nullptr;
}

void WebSocketClient::disconnectSocket()
{
    if (!m_ws) return;
    QObject::disconnect(m_ws, &QWebSocket::connected,
                        this, &WebSocketClient::onConnected);
    QObject::disconnect(m_ws, &QWebSocket::disconnected,
                        this, &WebSocketClient::onDisconnected);
    QObject::disconnect(m_ws, &QWebSocket::textMessageReceived,
                        this, &WebSocketClient::textReceived);
    QObject::disconnect(m_ws, &QWebSocket::binaryMessageReceived,
                        this, &WebSocketClient::binaryReceived);
    QObject::disconnect(m_ws, &QWebSocket::errorOccurred,
                        this, &WebSocketClient::onError);
}

// ── State management ─────────────────────────────────

void WebSocketClient::setState(State s)
{
    if (m_state != s) {
        m_state = s;
        emit stateChanged(s);
    }
}
