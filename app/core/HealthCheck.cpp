#include "HealthCheck.h"
#include "ConfigManager.h"
#include <QJsonObject>
#include <QJsonDocument>
#include <QDebug>

// ═══════════════════════════════════════════════════════
//  HealthCheck — implémentation
// ═══════════════════════════════════════════════════════

HealthCheck::HealthCheck(QObject *parent)
    : QObject(parent)
{
    connect(&m_timer, &QTimer::timeout, this, &HealthCheck::onPingTimer);
}

void HealthCheck::configure(ConfigManager *config)
{
    if (!config) return;

    // Services — toutes les URL proviennent de ConfigManager
    setupService("stt",      QUrl(config->getSTTServerUrl()));
    setupService("tts",      QUrl(config->getTTSServerUrl()));
    setupService("memory",   QUrl(config->getString("Memory",   "semantic_server_url", "ws://localhost:8771")));
    // Audit P2.1 : NLU 8772 retiré du probe — service mort-vivant, jamais appelé
    // par AssistantManager (fast-path bypass + Claude direct). nluStatus() reste
    // exposé en Q_PROPERTY pour compat QML (renvoie "unknown").

    // Les serveurs wakeword et vad sont mono-client (asyncio.Lock côté Python) :
    // une connexion HealthCheck persistante leur vole la session active du
    // VoicePipeline et fait osciller leur statut connected/disconnected toutes
    // les ~10s. On les exclut donc du ping périodique pour préserver la capture
    // vocale ; leur readiness est déjà vérifiée par le ServiceSupervisor au boot.

    // Microservices outils
    setupService("websearch", QUrl(config->getString("Tools",    "websearch_url",       "ws://localhost:8773")));
    setupService("news",      QUrl(config->getString("Tools",    "news_url",            "ws://localhost:8774")));
    setupService("knowledge", QUrl(config->getString("Tools",    "knowledge_url",       "ws://localhost:8775")));
    setupService("tools",     QUrl(config->getString("Tools",    "tools_url",           "ws://localhost:8776")));

    // Microservices v7
    setupService("context",   QUrl(config->getString("Tools",    "context_url",         "ws://localhost:8777")));
    setupService("planner",   QUrl(config->getString("Tools",    "planner_url",         "ws://localhost:8778")));
}

void HealthCheck::start(int intervalMs)
{
    if (m_services.isEmpty()) {
        qWarning() << "[HealthCheck] No services configured — call configure() first";
        return;
    }

    m_pingIntervalMs = intervalMs;

    // Connecter chaque WebSocketClient
    for (auto it = m_services.begin(); it != m_services.end(); ++it) {
        it->client->open(it->url);
    }

    m_timer.start(intervalMs);

    // Premier check immédiat après un court délai (laisser le temps de se connecter)
    QTimer::singleShot(2000, this, &HealthCheck::checkNow);
}

void HealthCheck::stop()
{
    m_timer.stop();
    for (auto it = m_services.begin(); it != m_services.end(); ++it) {
        it->client->close();
        it->health = ServiceHealth::Unknown;
        it->pingPending = false;
    }
    emit healthChanged();
}

void HealthCheck::checkNow()
{
    for (auto it = m_services.begin(); it != m_services.end(); ++it) {
        sendPing(it.key());
    }

    // Vérifier les timeouts après le délai
    QTimer::singleShot(m_timeoutMs, this, &HealthCheck::checkTimeouts);
}

// ── Accesseurs Q_PROPERTY ──

QString HealthCheck::sttStatus() const      { return healthToString(m_services.value("stt").health); }
QString HealthCheck::ttsStatus() const      { return healthToString(m_services.value("tts").health); }
QString HealthCheck::vadStatus() const      { return healthToString(m_services.value("vad").health); }
QString HealthCheck::wakewordStatus() const { return healthToString(m_services.value("wakeword").health); }
QString HealthCheck::memoryStatus() const   { return healthToString(m_services.value("memory").health); }
QString HealthCheck::nluStatus() const      { return healthToString(m_services.value("nlu").health); }
QString HealthCheck::contextStatus() const  { return healthToString(m_services.value("context").health); }
QString HealthCheck::plannerStatus() const  { return healthToString(m_services.value("planner").health); }

QString HealthCheck::serviceStatus(const QString &name) const
{
    return healthToString(m_services.value(name).health);
}

QString HealthCheck::overallStatus() const
{
    switch (overall()) {
    case OverallHealth::AllHealthy: return QStringLiteral("healthy");
    case OverallHealth::Degraded:   return QStringLiteral("degraded");
    case OverallHealth::Critical:   return QStringLiteral("critical");
    default:                        return QStringLiteral("unknown");
    }
}

bool HealthCheck::allHealthy() const
{
    return overall() == OverallHealth::AllHealthy;
}

HealthCheck::ServiceHealth HealthCheck::serviceHealth(const QString &name) const
{
    return m_services.value(name).health;
}

HealthCheck::OverallHealth HealthCheck::overall() const
{
    if (m_services.isEmpty()) return OverallHealth::Unknown;

    bool hasDown = false;
    bool hasDegraded = false;
    bool allHealthyFlag = true;

    for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it) {
        switch (it->health) {
        case ServiceHealth::Down:
            hasDown = true;
            allHealthyFlag = false;
            break;
        case ServiceHealth::Degraded:
            hasDegraded = true;
            allHealthyFlag = false;
            break;
        case ServiceHealth::Unknown:
            allHealthyFlag = false;
            break;
        case ServiceHealth::Healthy:
            break;
        }
    }

    if (hasDown) return OverallHealth::Critical;
    if (hasDegraded) return OverallHealth::Degraded;
    if (allHealthyFlag) return OverallHealth::AllHealthy;
    return OverallHealth::Unknown;
}

int HealthCheck::latencyMs(const QString &name) const
{
    return m_services.value(name).latencyMs;
}

// ── Internals ──

void HealthCheck::setupService(const QString &name, const QUrl &url)
{
    ServiceState state;
    state.url = url;
    state.client = new WebSocketClient(QStringLiteral("HC-") + name, this);
    // VAD ferme volontairement la connexion de healthcheck sur certaines versions.
    // Éviter le cycle reconnect toutes les 5s (connected/disconnected en boucle).
    if (name == QLatin1String("vad")) {
        state.client->setReconnectEnabled(false);
    } else {
        state.client->setReconnectEnabled(true);
        state.client->setReconnectParams(5000, 0, false);  // retry toutes les 5s, illimité
    }

    connect(state.client, &WebSocketClient::connected, this,
            [this, name]() { onServiceConnected(name); });
    connect(state.client, &WebSocketClient::disconnected, this,
            [this, name]() { onServiceDisconnected(name); });
    connect(state.client, &WebSocketClient::textReceived, this,
            [this, name](const QString &msg) { onServiceMessage(name, msg); });

    m_services.insert(name, state);
}

void HealthCheck::sendPing(const QString &name)
{
    auto it = m_services.find(name);
    if (it == m_services.end()) return;

    if (!it->client->isConnected()) {
        // Cas spécial VAD: ouvrir à la demande pour éviter le flapping permanent.
        if (name == QLatin1String("vad")) {
            it->client->open(it->url);
            return;
        }
        updateHealth(name, ServiceHealth::Down);
        return;
    }

    // Perf: payloads pré-alloués (évite QJsonObject + QJsonDocument à chaque tick,
    // ~10 services × 6 ticks/min = 60 allocs/min épargnées sur le main thread Qt).
    static const QString PING_TYPE   = QStringLiteral("{\"type\":\"ping\"}");
    static const QString PING_ACTION = QStringLiteral("{\"action\":\"ping\"}");

    it->pingPending = true;
    it->pingTimer.start();
    it->client->sendText(name == QLatin1String("nlu") ? PING_ACTION : PING_TYPE);
}

void HealthCheck::onServiceConnected(const QString &name)
{
    qDebug() << "[HealthCheck]" << name << "connected";

    // VAD est pingé immédiatement après connexion à la demande.
    if (name == QLatin1String("vad")) {
        sendPing(name);
    }
}

void HealthCheck::onServiceDisconnected(const QString &name)
{
    qDebug() << "[HealthCheck]" << name << "disconnected";

    // Éviter les transitions down parasites pour VAD quand il ferme sa socket healthcheck.
    if (name == QLatin1String("vad")) {
        return;
    }

    updateHealth(name, ServiceHealth::Down);
}

void HealthCheck::onServiceMessage(const QString &name, const QString &message)
{
    QJsonDocument doc = QJsonDocument::fromJson(message.toUtf8());
    if (!doc.isObject()) return;

    QJsonObject obj = doc.object();
    QString type = obj.value(QStringLiteral("type")).toString();

    if (type == QLatin1String("pong")) {
        auto it = m_services.find(name);
        if (it == m_services.end() || !it->pingPending) return;

        int latency = static_cast<int>(it->pingTimer.elapsed());
        it->pingPending = false;
        it->lastPongMs = QDateTime::currentMSecsSinceEpoch();

        ServiceHealth h = (latency > m_degradedThresholdMs)
                              ? ServiceHealth::Degraded
                              : ServiceHealth::Healthy;
        updateHealth(name, h, latency);
    }
    // Ignorer les autres messages (ready, config, etc.)
}

void HealthCheck::onPingTimer()
{
    checkNow();
}

void HealthCheck::checkTimeouts()
{
    for (auto it = m_services.begin(); it != m_services.end(); ++it) {
        if (it->pingPending) {
            it->pingPending = false;
            updateHealth(it.key(), ServiceHealth::Down);
        }
    }
}

void HealthCheck::updateHealth(const QString &name, ServiceHealth newHealth, int latency)
{
    auto it = m_services.find(name);
    if (it == m_services.end()) return;

    ServiceHealth oldHealth = it->health;
    it->health = newHealth;
    if (latency >= 0) it->latencyMs = latency;

    if (oldHealth != newHealth) {
        qDebug() << "[HealthCheck]" << name << ":" << healthToString(oldHealth)
                 << "->" << healthToString(newHealth)
                 << (latency >= 0 ? QStringLiteral(" (%1 ms)").arg(latency) : QString());

        if (newHealth == ServiceHealth::Down && oldHealth != ServiceHealth::Down) {
            emit serviceDown(name);
        } else if (oldHealth == ServiceHealth::Down && newHealth != ServiceHealth::Down) {
            emit serviceRecovered(name);
        }
        emit healthChanged();
    }
}

QString HealthCheck::healthToString(ServiceHealth h)
{
    switch (h) {
    case ServiceHealth::Healthy:  return QStringLiteral("healthy");
    case ServiceHealth::Degraded: return QStringLiteral("degraded");
    case ServiceHealth::Down:     return QStringLiteral("down");
    default:                      return QStringLiteral("unknown");
    }
}
