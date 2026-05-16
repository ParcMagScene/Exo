#include "TTSBackendXTTS.h"
#include "TTSManager.h"
#include "utils/SafeIO.h"

#include <QWebSocket>
#include <QEventLoop>
#include <QElapsedTimer>
#include <QJsonObject>
#include <QJsonDocument>
#include <QTimer>

TTSBackendXTTS::TTSBackendXTTS(QObject *parent)
    : TTSBackend(parent)
{
    qInfo() << "[TTS] Backend: CUDA (RTX 3070)";
}

TTSBackendXTTS::~TTSBackendXTTS()
{
    // v5.2 memory audit : m_keepaliveTimer est un QObject child de `this`
    // (cf. setupKeepalive : `new QTimer(this)`). Qt le détruira via la chaîne
    // parent—enfant. On stoppe juste pour éviter un dernier tick en vol.
    if (m_keepaliveTimer)
        m_keepaliveTimer->stop();
    if (m_ws) {
        // QWebSocket sans parent : utiliser deleteLater pour éviter de courir
        // avec un signal en vol (textMessageReceived/binaryMessageReceived).
        m_ws->close();
        m_ws->deleteLater();
        m_ws = nullptr;
    }
}

bool TTSBackendXTTS::isAvailable() const
{
    return !m_url.isEmpty();
}

void TTSBackendXTTS::setUrl(const QString &url)
{
    m_url = url;
    qInfo() << "[TTS] XTTS URL set:" << m_url;
}

void TTSBackendXTTS::setVoice(const QString &voice)
{
    m_voice = voice;
    qInfo() << "[TTS] XTTS voice set to:" << voice;
}

void TTSBackendXTTS::setLang(const QString &lang)
{
    m_lang = lang;
    qInfo() << "[TTS] XTTS language set to:" << lang;
}

void TTSBackendXTTS::resetConnection()
{
    if (m_keepaliveTimer)
        m_keepaliveTimer->stop();
    if (m_ws) {
        m_ws->close();
        m_ws->deleteLater();
        m_ws = nullptr;
    }
    m_connected = false;
    m_readyReceived = false;
    qInfo() << "[TTS] Connexion Python réinitialisée";
}

void TTSBackendXTTS::warmConnect()
{
    if (m_url.isEmpty()) return;
    if (m_ws && m_connected) {
        qInfo() << "[TTS] warmConnect: already connected";
        return;
    }
    qInfo() << "[TTS] warmConnect: early connection to" << m_url;
    ensureConnected();
    if (m_connected)
        setupKeepalive();
}

void TTSBackendXTTS::setupKeepalive()
{
    if (m_keepaliveTimer)
        return;
    m_keepaliveTimer = new QTimer(this);
    m_keepaliveTimer->setInterval(15000);  // ping every 15s
    connect(m_keepaliveTimer, &QTimer::timeout, this, [this]() {
        if (m_ws && m_connected) {
            exo::safeio::wsSafeSend(m_ws,
                QStringLiteral(R"({"type":"ping"})"),
                "TTSBackendXTTS::keepalive");
        } else {
            qInfo() << "[TTS] keepalive: connection lost, reconnecting...";
            ensureConnected();
        }
    });
    m_keepaliveTimer->start();
    qInfo() << "[TTS] WebSocket keepalive started (15s interval)";
}

void TTSBackendXTTS::cancel()
{
    if (m_ws && m_connected)
        exo::safeio::wsSafeSend(m_ws,
            QStringLiteral(R"({"type":"cancel"})"),
            "TTSBackendXTTS::cancel");
}

bool TTSBackendXTTS::tryConnect()
{
    if (m_ws)
        resetConnection();

    // v5.2 memory audit : QWebSocket parenté sur `this` → cleanup automatique
    // par Qt si le backend est détruit avant resetConnection.
    m_ws = new QWebSocket(QString(), QWebSocketProtocol::VersionLatest, this);

    // v5.2 FSM/WS audit : suivre les déconnexions réelles pour invalider
    // m_connected. Avant : si TCP drop (firewall, kill serveur), m_connected
    // restait true et la prochaine synthèse envoyait sur socket mort.
    connect(m_ws, &QWebSocket::disconnected, this, [this]() {
        if (m_connected) {
            qWarning() << "[TTS] WebSocket disconnected — invalidating connection";
            m_connected = false;
            m_readyReceived = false;
        }
    });

    bool gotReady = false;

    // Ready handler connected BEFORE opening — prevents race condition
    QMetaObject::Connection readyConn = connect(m_ws, &QWebSocket::textMessageReceived,
        this, [&gotReady](const QString &txt) {
            QJsonDocument d = QJsonDocument::fromJson(txt.toUtf8());
            if (d.isObject() && d.object()["type"].toString() == "ready")
                gotReady = true;
        });

    // --- Wait for connection via QEventLoop (no busy-wait) ---
    QEventLoop connectLoop;
    QTimer::singleShot(3000, &connectLoop, &QEventLoop::quit);
    auto connOk  = connect(m_ws, &QWebSocket::connected,  &connectLoop, &QEventLoop::quit);
    auto connErr = connect(m_ws, &QWebSocket::errorOccurred, &connectLoop, [&connectLoop](auto) { connectLoop.quit(); });

    QElapsedTimer elapsed;
    elapsed.start();
    m_ws->open(QUrl(m_url));
    connectLoop.exec();

    disconnect(connOk);
    disconnect(connErr);

    m_connected = (m_ws->state() == QAbstractSocket::ConnectedState);
    qWarning() << "[TTS] tryConnect: connected =" << m_connected
               << "state:" << m_ws->state()
               << "après" << elapsed.elapsed() << "ms";

    // --- Wait for "ready" message via QEventLoop ---
    if (m_connected && !m_readyReceived && !gotReady) {
        QEventLoop readyLoop;
        QTimer::singleShot(3000, &readyLoop, &QEventLoop::quit);
        auto readyTxt = connect(m_ws, &QWebSocket::textMessageReceived,
            &readyLoop, [&gotReady, &readyLoop](const QString &) {
                if (gotReady) readyLoop.quit();
            });
        readyLoop.exec();
        disconnect(readyTxt);
    }

    disconnect(readyConn);
    m_readyReceived = gotReady || m_readyReceived;
    qWarning() << "[TTS] XTTS v2 ready message:" << (m_readyReceived ? "OK" : "timeout");

    return m_connected;
}

bool TTSBackendXTTS::ensureConnected()
{
    if (m_ws && m_connected)
        return true;

    qWarning() << "[TTS] tryPythonTTS: connexion à" << m_url;
    qInfo().noquote() << "[TTSManager] Connecting to" << m_url;
    if (tryConnect()) {
        qWarning() << "[TTS] Connected to XTTS CUDA GPU server";
        return true;
    }

    // Retry once
    qWarning() << "[TTS] tryPythonTTS: non connecté — retry connexion...";
    if (tryConnect())
        return true;

    qWarning() << "[TTS] Python TTS unavailable — fallback Qt TTS";
    return false;
}

bool TTSBackendXTTS::synthesize(const TTSRequest &req)
{
    if (m_url.isEmpty()) {
        qWarning() << "[TTS] tryPythonTTS: URL vide — skip XTTS";
        return false;
    }

    if (!ensureConnected())
        return false;

    // Start keepalive if not yet running (first successful connection)
    setupKeepalive();

    emit started(req.text);

    // Send synthesis request (XTTS v2 tts_server.py protocol)
    QElapsedTimer synthLatency;
    synthLatency.start();
    QJsonObject msg;
    msg["type"]  = "synthesize";
    msg["text"]  = req.text;
    msg["voice"] = m_voice;
    msg["lang"]  = m_lang;
    msg["rate"]  = static_cast<double>(1.0 + req.prosody.rate * 0.5);   // [-1,1] → [0.5, 1.5]
    msg["pitch"] = static_cast<double>(1.0 + req.prosody.pitch * 0.3);  // [-1,1] → [0.7, 1.3]
    if (exo::safeio::wsSafeSend(m_ws,
            QString::fromUtf8(QJsonDocument(msg).toJson(QJsonDocument::Compact)),
            "TTSBackendXTTS::synthesize") < 0) {
        qWarning() << "[TTS] synthesize: envoi WS échoué — abort";
        resetConnection();
        return false;
    }

    // Wait for: JSON "start" → binary PCM chunks → JSON "end"
    // Using QEventLoop instead of processEvents busy-wait
    QEventLoop synthLoop;
    bool done = false;
    bool gotStart = false;
    bool gotAudio = false;

    QTimer synthTimeout;
    synthTimeout.setSingleShot(true);
    synthTimeout.setInterval(PY_TTS_TIMEOUT_MS);
    connect(&synthTimeout, &QTimer::timeout, &synthLoop, &QEventLoop::quit);

    QMetaObject::Connection binConn = connect(m_ws, &QWebSocket::binaryMessageReceived,
        this, [this, &synthTimeout, &synthLatency, &gotAudio](const QByteArray &data) {
            if (data.isEmpty())
                return;
            // v5.2 FSM/WS audit : drop chunks orphelins arrivés après un cancel
            // (le serveur a peut-être encore des chunks en vol au moment du cancel).
            if (isCancelled()) {
                synthTimeout.start();  // reset timeout pour ne pas bloquer la sortie sur 'end'
                return;
            }
            gotAudio = true;
            if (synthLatency.isValid()) {
                const qint64 firstMs = synthLatency.elapsed();
                qWarning() << "[Latency] TTS backend first-chunk:" << firstMs << "ms";
                qInfo().noquote() << "[TTSManager] First chunk received in" << firstMs << "ms";
                synthLatency.invalidate();
            }
            synthTimeout.start();  // restart timeout on each chunk
            emit chunk(data);
        });
    QMetaObject::Connection txtConn = connect(m_ws, &QWebSocket::textMessageReceived,
        this, [&done, &gotStart, &synthTimeout, &synthLoop](const QString &txtMsg) {
            QJsonDocument d = QJsonDocument::fromJson(txtMsg.toUtf8());
            if (!d.isObject()) return;
            const QJsonObject obj = d.object();
            const QString type = obj["type"].toString();
            if (type == "start") {
                gotStart = true;
                synthTimeout.start();  // restart timeout
            }
            else if (type == "end" || type == "error") {
                if (type == "end") {
                    // Server reports duration in seconds + total_ms wall-clock.
                    const double durationSec = obj.value("duration").toDouble(-1.0);
                    const int    totalMs     = obj.value("total_ms").toInt(-1);
                    if (durationSec >= 0.0 || totalMs >= 0) {
                        qInfo().noquote()
                            << "[TTSManager] Total audio duration:"
                            << static_cast<int>(durationSec * 1000.0) << "ms"
                            << "(server total_ms=" << totalMs << ")";
                    }
                }
                done = true;
                synthLoop.quit();
            }
        });

    synthTimeout.start();
    synthLoop.exec();

    disconnect(binConn);
    disconnect(txtConn);

    if (isCancelled()) {
        emit finished();
        return true;
    }

    if (done) {
        if (gotAudio) {
            emit finished();
            return true;
        }

        qWarning() << "[TTS] XTTS terminé sans audio — fallback Qt TTS";
        resetConnection();
        return false;
    }

    // Timeout — reset connection so next call starts fresh
    qWarning() << "[TTS] XTTS timeout après" << PY_TTS_TIMEOUT_MS << "ms — reset connexion";
    resetConnection();
    return false;
}
