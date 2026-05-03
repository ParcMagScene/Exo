#pragma once

#include <QObject>
#include <QTimer>
#include <QMap>
#include <QVariantList>
#include <QProcess>

class ServiceRegistry;
class SafeBootController;

// ═══════════════════════════════════════════════════════
//  SafeBootAutoRepair — Réparation automatique EXO v30.3
//
//  Tente de réparer automatiquement les services KO :
//    1. Vérifier si le port est libre (tuer zombie)
//    2. Relancer le microservice Python
//    3. Attendre le handshake READY via WebSocket
//    4. Si OK → serviceRecovered
//    5. Si KO → retry (max 3 tentatives)
//
//  Intégré dans SafeBootController::enableSafeBoot().
// ═══════════════════════════════════════════════════════

class SafeBootAutoRepair : public QObject
{
    Q_OBJECT

    Q_PROPERTY(bool running READ isRunning NOTIFY runningChanged)
    Q_PROPERTY(QVariantList repairTimeline READ repairTimeline NOTIFY repairTimelineChanged)

public:
    explicit SafeBootAutoRepair(QObject *parent = nullptr);

    // ── Configuration ──
    void setRegistry(ServiceRegistry *registry);
    void setController(SafeBootController *controller);

    // ── Contrôle ──
    Q_INVOKABLE void attemptRepair(const QString &serviceName);
    Q_INVOKABLE void autoRepairAll();
    Q_INVOKABLE void autoRepairLoop();
    Q_INVOKABLE void stop();

    // ── Accesseurs ──
    bool isRunning() const { return m_running; }
    QVariantList repairTimeline() const { return m_repairTimeline; }

signals:
    void repairAttempted(const QString &service, bool success);
    void repairCompleted();
    void runningChanged();
    void repairTimelineChanged();

private:
    // ── Réparation individuelle ──
    bool restartService(const QString &serviceName);
    bool clearServiceCache(const QString &serviceName);
    bool checkPortAvailable(int port);
    bool killProcessOnPort(int port);
    bool waitForReady(const QString &serviceName, int timeoutMs);

    // ── Utilitaires ──
    QString pythonExeForVenv(const QString &venv) const;
    QString projectDir() const;
    void addRepairEvent(const QString &event, const QString &service,
                        const QString &detail = {});
    void processRepairQueue();

    // ── Données ──
    ServiceRegistry    *m_registry   = nullptr;
    SafeBootController *m_controller = nullptr;
    bool m_running = false;

    QStringList m_repairQueue;
    QMap<QString, int> m_attemptCount;
    QVariantList m_repairTimeline;

    static constexpr int kMaxRepairAttempts  = 3;
    static constexpr int kReadyTimeoutMs     = 1500;
    static constexpr int kRepairBaseDelayMs  = 500;   // backoff: base * 2^(attempt-1)
    static constexpr int kRepairMaxDelayMs   = 8000;
};
