#pragma once

#include <QObject>
#include <QTimer>
#include <QMap>
#include <QElapsedTimer>
#include <QJsonObject>
#include <QJsonDocument>
#include "WebSocketClient.h"

// ═══════════════════════════════════════════════════════
//  HealthCheck — Surveillance automatique des microservices
//
//  Envoie un ping périodique à chaque serveur Python et
//  expose l'état individuel + global à la GUI via Q_PROPERTY.
//
//  États par service :
//    Healthy   — pong reçu dans le délai
//    Degraded  — pong reçu mais latence > seuil
//    Down      — pong non reçu (timeout)
//    Unknown   — pas encore vérifié
//
//  État global :
//    AllHealthy — tous les services sont Healthy
//    Degraded   — au moins un service Degraded, aucun Down
//    Critical   — au moins un service Down
// ═══════════════════════════════════════════════════════

class ConfigManager;

class HealthCheck : public QObject
{
    Q_OBJECT

    Q_PROPERTY(QString sttStatus   READ sttStatus   NOTIFY healthChanged)
    Q_PROPERTY(QString ttsStatus   READ ttsStatus   NOTIFY healthChanged)
    Q_PROPERTY(QString vadStatus   READ vadStatus   NOTIFY healthChanged)
    Q_PROPERTY(QString wakewordStatus READ wakewordStatus NOTIFY healthChanged)
    Q_PROPERTY(QString memoryStatus READ memoryStatus NOTIFY healthChanged)
    Q_PROPERTY(QString nluStatus   READ nluStatus   NOTIFY healthChanged)
    Q_PROPERTY(QString contextStatus READ contextStatus NOTIFY healthChanged)
    Q_PROPERTY(QString plannerStatus READ plannerStatus NOTIFY healthChanged)
    Q_PROPERTY(QString overallStatus READ overallStatus NOTIFY healthChanged)
    Q_PROPERTY(bool allHealthy READ allHealthy NOTIFY healthChanged)

public:
    enum class ServiceHealth { Unknown, Healthy, Degraded, Down };
    Q_ENUM(ServiceHealth)

    enum class OverallHealth { Unknown, AllHealthy, Degraded, Critical };
    Q_ENUM(OverallHealth)

    explicit HealthCheck(QObject *parent = nullptr);
    ~HealthCheck() override = default;

    void configure(ConfigManager *config);
    Q_INVOKABLE void start(int intervalMs = 10000);
    Q_INVOKABLE void stop();
    Q_INVOKABLE void checkNow();

    // Accesseurs pour Q_PROPERTY (retournent "healthy"/"degraded"/"down"/"unknown")
    QString sttStatus() const;
    QString ttsStatus() const;
    QString vadStatus() const;
    QString wakewordStatus() const;
    QString memoryStatus() const;
    QString nluStatus() const;
    QString contextStatus() const;
    QString plannerStatus() const;
    QString overallStatus() const;
    bool allHealthy() const;

    // Accès programmatique
    Q_INVOKABLE QString serviceStatus(const QString &name) const;
    ServiceHealth serviceHealth(const QString &name) const;
    OverallHealth overall() const;
    int latencyMs(const QString &name) const;

signals:
    void healthChanged();
    void serviceDown(const QString &serviceName);
    void serviceRecovered(const QString &serviceName);

private slots:
    void onPingTimer();

private:
    struct ServiceState {
        WebSocketClient *client = nullptr;
        ServiceHealth    health = ServiceHealth::Unknown;
        QElapsedTimer    pingTimer;
        bool             pingPending = false;
        int              latencyMs   = -1;
        qint64           lastPongMs  = 0;
        QUrl             url;
    };

    void setupService(const QString &name, const QUrl &url);
    void sendPing(const QString &name);
    void onServiceConnected(const QString &name);
    void onServiceDisconnected(const QString &name);
    void onServiceMessage(const QString &name, const QString &message);
    void checkTimeouts();
    void updateHealth(const QString &name, ServiceHealth newHealth, int latency = -1);
    static QString healthToString(ServiceHealth h);

    QMap<QString, ServiceState> m_services;
    QTimer m_timer;
    int m_pingIntervalMs = 10000;
    // IMPORTANT : m_timeoutMs DOIT rester strictement inférieur à m_pingIntervalMs.
    // Si timeout == intervalle, la callback checkTimeouts() du tick N s'exécute
    // au moment précis où onPingTimer() du tick N+1 vient de remettre pingPending
    // à true, ce qui fait osciller artificiellement tous les services
    // healthy → down → healthy à chaque cycle (visible dans les logs comme
    // "down → healthy (1-100ms)"). 3s laisse une marge confortable pour le pong.
    int m_timeoutMs = 3000;
    int m_degradedThresholdMs = 2000;
};
