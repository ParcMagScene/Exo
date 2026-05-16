#include "TestController.h"
#include "ConfigManager.h"
#include <QDateTime>
#include <QDebug>

// ═══════════════════════════════════════════════════════
//  TestController — implémentation
// ═══════════════════════════════════════════════════════

TestController::TestController(QObject *parent)
    : QObject(parent)
{
    m_timeoutTimer.setSingleShot(true);
    connect(&m_timeoutTimer, &QTimer::timeout, this, &TestController::checkTimeouts);
    connect(&m_autoTimer,    &QTimer::timeout, this, &TestController::onAutoLoopTick);
}

TestController::~TestController()
{
    stopAutoTestLoop();
}

// ── Configuration (called once from main.cpp) ───────────────────

void TestController::configure(ConfigManager *config)
{
    if (!config) return;

    // Core voice services
    setupService("stt",       QUrl(config->getSTTServerUrl()));
    setupService("tts",       QUrl(config->getTTSServerUrl()));
    setupService("vad",       QUrl(config->getString("VAD",      "server_url",          "ws://localhost:8768")));
    setupService("wakeword",  QUrl(config->getString("WakeWord", "server_url",          "ws://localhost:8770")));
    setupService("memory",    QUrl(config->getString("Memory",   "semantic_server_url", "ws://localhost:8771")));
    setupService("nlu",       QUrl(config->getString("NLU",      "server_url",          "ws://localhost:8772")));
    setupService("context",   QUrl(config->getString("Tools",    "context_url",         "ws://localhost:8777")));
    setupService("planner",   QUrl(config->getString("Tools",    "planner_url",         "ws://localhost:8778")));

    // Extended services
    setupService("network",   QUrl(QStringLiteral("ws://localhost:8790")));
    setupService("domotic",   QUrl(QStringLiteral("ws://localhost:8785")));
    setupService("homegraph", QUrl(QStringLiteral("ws://localhost:8784")));
}

// ── QML API ─────────────────────────────────────────────────────

QVariantMap TestController::runPing(const QString &target)
{
    QVariantMap result;
    auto it = m_services.find(target);
    if (it == m_services.end()) {
        result["status"]  = "error";
        result["error"]   = QStringLiteral("Unknown service: ") + target;
        return result;
    }

    result["status"]  = it->status;
    result["latency"] = it->latencyMs;
    if (!it->error.isEmpty())
        result["error"] = it->error;
    return result;
}

void TestController::runAllPings()
{
    if (m_pendingCount > 0) return;  // already running

    m_loopCount++;
    m_pendingCount = 0;
    m_errorLog.clear();

    qInfo() << "[TestController] === Loop" << m_loopCount << "===";

    for (auto it = m_services.begin(); it != m_services.end(); ++it) {
        it->status      = "unknown";
        it->latencyMs   = -1;
        it->error.clear();
        it->pingPending = false;

        // (Re)connect if needed
        if (!it->client->isConnected()) {
            it->client->open(it->url);
        }
    }

    // Small delay to let connections establish, then send pings
    QTimer::singleShot(1500, this, [this]() {
        for (auto it = m_services.begin(); it != m_services.end(); ++it) {
            sendTestPing(it.key());
        }
        m_timeoutTimer.start(m_timeoutMs);
    });
}

QVariantMap TestController::getPipelineState()
{
    QVariantMap state;
    for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it) {
        QVariantMap svc;
        svc["status"]  = it->status;
        svc["latency"] = it->latencyMs;
        if (!it->error.isEmpty())
            svc["error"] = it->error;
        state[it.key()] = svc;
    }
    return state;
}

QVariantList TestController::getErrors()
{
    QVariantList list;
    for (const auto &err : m_errorLog)
        list.append(err);
    return list;
}

void TestController::startAutoTestLoop()
{
    if (m_running) return;
    m_running   = true;
    m_loopCount = 0;
    emit runningChanged();

    qInfo() << "[TestController] Boucle d'auto-test démarrée";
    onAutoLoopTick();  // first run immediately
}

void TestController::stopAutoTestLoop()
{
    if (!m_running) return;
    m_running = false;
    m_autoTimer.stop();
    m_timeoutTimer.stop();

    // Close all test connections
    for (auto it = m_services.begin(); it != m_services.end(); ++it) {
        if (it->client) {
            it->client->setReconnectEnabled(false);
            it->client->close();
        }
    }

    emit runningChanged();
    qInfo() << "[TestController] Boucle d'auto-test arrêtée";
}

// ── Property accessors ──────────────────────────────────────────

QVariantList TestController::serviceResults() const
{
    QVariantList list;
    for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it) {
        QVariantMap entry;
        entry["name"]    = it.key();
        entry["status"]  = it->status;
        entry["latency"] = it->latencyMs;
        if (!it->error.isEmpty())
            entry["error"] = it->error;
        list.append(entry);
    }
    return list;
}

QString TestController::overallStatus() const
{
    if (m_services.isEmpty()) return QStringLiteral("unknown");

    bool allOk = true;
    for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it) {
        if (it->status != "ok") {
            allOk = false;
            break;
        }
    }
    return allOk ? QStringLiteral("stable") : QStringLiteral("unstable");
}

bool TestController::running() const { return m_running; }
int  TestController::loopCount() const { return m_loopCount; }

QVariantList TestController::errorLog() const
{
    QVariantList list;
    for (const auto &e : m_errorLog)
        list.append(e);
    return list;
}

// ── Auto-loop ───────────────────────────────────────────────────

void TestController::onAutoLoopTick()
{
    if (!m_running) return;
    runAllPings();
}

// ── Internals ───────────────────────────────────────────────────

void TestController::setupService(const QString &name, const QUrl &url)
{
    ServiceTest svc;
    svc.name   = name;
    svc.url    = url;
    svc.status = QStringLiteral("unknown");
    svc.client = new WebSocketClient(QStringLiteral("Test-") + name, this);
    svc.client->setReconnectEnabled(true);
    svc.client->setReconnectParams(3000, 2, false);

    connect(svc.client, &WebSocketClient::connected, this,
            [this, name]() { onConnected(name); });
    connect(svc.client, &WebSocketClient::disconnected, this,
            [this, name]() { onDisconnected(name); });
    connect(svc.client, &WebSocketClient::textReceived, this,
            [this, name](const QString &msg) { onMessage(name, msg); });

    m_services.insert(name, svc);
}

void TestController::sendTestPing(const QString &name)
{
    auto it = m_services.find(name);
    if (it == m_services.end()) return;

    if (!it->client->isConnected()) {
        it->status = QStringLiteral("down");
        it->error  = QStringLiteral("not connected");
        return;
    }

    QJsonObject ping;
    if (name == QLatin1String("nlu"))
        ping[QStringLiteral("action")] = QStringLiteral("ping");
    else
        ping[QStringLiteral("type")]   = QStringLiteral("ping");

    it->pingPending = true;
    it->timer.start();
    it->client->sendJson(ping);
    m_pendingCount++;
}

void TestController::onConnected(const QString &name)
{
    qDebug() << "[TestController]" << name << "connecté";
}

void TestController::onDisconnected(const QString &name)
{
    auto it = m_services.find(name);
    if (it == m_services.end()) return;

    if (it->pingPending) {
        it->pingPending = false;
        it->status = QStringLiteral("down");
        it->error  = QStringLiteral("déconnecté pendant attente du pong");
        m_pendingCount = qMax(0, m_pendingCount - 1);

        QString err = QStringLiteral("[%1] disconnected during ping").arg(name);
        m_errorLog.append(err);
        qWarning() << "[TestController]" << err;

        if (m_pendingCount == 0)
            evaluateResults();
    }
}

void TestController::onMessage(const QString &name, const QString &msg)
{
    auto it = m_services.find(name);
    if (it == m_services.end() || !it->pingPending) return;

    QJsonDocument doc = QJsonDocument::fromJson(msg.toUtf8());
    if (!doc.isObject()) return;

    QJsonObject obj = doc.object();
    QString type = obj.value(QStringLiteral("type")).toString();
    if (type != QLatin1String("pong")) return;

    int latency = static_cast<int>(it->timer.elapsed());
    it->pingPending = false;
    it->latencyMs   = latency;
    it->status      = QStringLiteral("ok");
    m_pendingCount  = qMax(0, m_pendingCount - 1);

    qDebug() << "[TestController]" << name << "pong" << latency << "ms";

    if (m_pendingCount == 0) {
        m_timeoutTimer.stop();
        evaluateResults();
    }
}

void TestController::checkTimeouts()
{
    for (auto it = m_services.begin(); it != m_services.end(); ++it) {
        if (it->pingPending) {
            it->pingPending = false;
            it->status = QStringLiteral("timeout");
            it->error  = QStringLiteral("no pong within %1 ms").arg(m_timeoutMs);
            m_pendingCount = qMax(0, m_pendingCount - 1);

            QString err = QStringLiteral("[%1] timeout").arg(it.key());
            m_errorLog.append(err);
        }
    }

    evaluateResults();
}

void TestController::evaluateResults()
{
    // Flap detection
    for (auto it = m_services.begin(); it != m_services.end(); ++it) {
        if (isFlapping(*it) && it->status != QStringLiteral("down")) {
            it->status = QStringLiteral("flapping");
        }
    }

    bool allGreen = (overallStatus() == QStringLiteral("stable"));

    qInfo() << "[TestController] Loop" << m_loopCount
            << (allGreen ? "— STABLE ✔" : "— UNSTABLE ✘");

    emit resultsChanged();
    emit loopFinished(m_loopCount, allGreen);

    if (allGreen) {
        emit testComplete(true);
        if (m_running) {
            stopAutoTestLoop();
        }
    } else if (m_running) {
        // Schedule next loop
        m_autoTimer.start(AUTO_LOOP_MS);
    }
}

bool TestController::isFlapping(ServiceTest &svc) const
{
    qint64 now = QDateTime::currentMSecsSinceEpoch();
    svc.history.append({now, svc.status});

    // Trim old entries
    qint64 cutoff = now - (FLAP_WINDOW_S * 1000);
    while (!svc.history.isEmpty() && svc.history.first().first < cutoff)
        svc.history.removeFirst();

    // Count transitions
    int transitions = 0;
    for (int i = 1; i < svc.history.size(); ++i) {
        if (svc.history[i].second != svc.history[i - 1].second)
            transitions++;
    }

    return transitions >= FLAP_THRESHOLD;
}
