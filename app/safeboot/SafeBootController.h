#pragma once

#include <QObject>
#include <QMap>
#include <QTimer>
#include <QElapsedTimer>
#include <QVariantList>
#include <QSet>
#include <QtQml/qqmlregistration.h>
#include "SafeBootEnums.h"
#include "SafeBootState.h"
#include "SafeBootTimeline.h"

class ServiceRegistry;
class SafeBootAutoRepair;

// ═══════════════════════════════════════════════════════
//  SafeBootController — Contrôleur Safe Boot EXO v30.2
//
//  Surveille le démarrage des services, applique un
//  timeout de 2 s par service, classe les services en
//  Critical / NonCritical, et démarre EXO même si les
//  NonCritical sont KO.
//
//  Lazy-load : les NonCritical sont relancés après l'UI
//  avec 3 tentatives.  Si toujours KO → Degraded.
// ═══════════════════════════════════════════════════════

class SafeBootController : public QObject
{
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(bool   safeBootEnabled  READ isSafeBootEnabled  NOTIFY safeBootEnabledChanged)
    Q_PROPERTY(int    failedCount      READ failedCount       NOTIFY timelineUpdated)
    Q_PROPERTY(int    degradedCount    READ degradedCount     NOTIFY timelineUpdated)
    Q_PROPERTY(int    readyCount       READ readyCount        NOTIFY timelineUpdated)
    Q_PROPERTY(int    totalCount       READ totalCount        CONSTANT)
    Q_PROPERTY(QVariantList failedServices   READ getFailedServices   NOTIFY timelineUpdated)
    Q_PROPERTY(QVariantList degradedServices READ getDegradedServices NOTIFY timelineUpdated)
    Q_PROPERTY(QVariantList startupTimeline  READ getStartupTimeline  NOTIFY timelineUpdated)
    Q_PROPERTY(bool autoRepairRunning READ autoRepairRunning NOTIFY autoRepairChanged)

public:
    explicit SafeBootController(QObject *parent = nullptr);

    // ── Configuration ──
    void setRegistry(ServiceRegistry *registry);

    // ── Contrôle ──
    Q_INVOKABLE void startMonitoring();
    Q_INVOKABLE void enableSafeBoot();
    Q_INVOKABLE void disableSafeBoot();
    Q_INVOKABLE void retryNonCriticalServices();
    Q_INVOKABLE void restartNormalMode();
    Q_INVOKABLE void startAutoRepair();

    // ── AutoRepair ──
    void setAutoRepair(SafeBootAutoRepair *repair);
    bool autoRepairRunning() const;

    // ── Observation ──
    void checkServiceStatus(const QString &serviceName, bool ready);
    void markServiceFailed(const QString &serviceName);

    // ── Accesseurs ──
    bool isSafeBootEnabled() const { return m_safeBootEnabled; }
    int  failedCount() const;
    int  degradedCount() const;
    int  readyCount() const;
    int  totalCount() const { return m_services.size(); }

    QVariantList getFailedServices() const;
    QVariantList getDegradedServices() const;
    QVariantList getStartupTimeline() const;
    QVariantList repairTimeline() const;

signals:
    void safeBootActivated();
    void safeBootDeactivated();
    void safeBootEnabledChanged();
    void serviceFailed(const QString &service);
    void serviceRecovered(const QString &service);
    void timelineUpdated();
    void criticalServicesReady();
    void autoRepairChanged();

private slots:
    void onServiceStateChanged(const QString &name,
                               const QString &oldState,
                               const QString &newState);
    void onAutoRepairCompleted();

private:
    // ── Classification ──
    SafeBoot::ServiceCriticality classifyService(const QString &name) const;
    void initServiceStates();

    // ── Timeouts ──
    void startTimeoutTimer(const QString &name);
    void onServiceTimeout(const QString &name);

    // ── Lazy-load ──
    void startLazyLoadTimer();
    void tryLazyLoadNext();

    // ── Timeline ──
    void addTimelineEvent(const QString &event,
                          const QString &serviceName,
                          const QString &detail = {});

    // ── Checks ──
    void checkCriticalReady();

    // ── Données ──
    ServiceRegistry *m_registry = nullptr;
    bool m_safeBootEnabled  = false;
    bool m_monitoring       = false;
    bool m_criticalEmitted  = false;

    QMap<QString, SafeBoot::SafeBootState>  m_services;
    QMap<QString, QTimer*>                  m_timeoutTimers;
    QMap<QString, QElapsedTimer>            m_startTimestamps;
    QList<SafeBoot::SafeBootTimeline>       m_timeline;

    // AutoRepair
    SafeBootAutoRepair *m_autoRepair = nullptr;

    // Lazy-load
    QTimer *m_lazyLoadTimer = nullptr;
    QStringList m_lazyQueue;
    QMap<QString, int> m_lazyRetryCount;

    // Classification
    static const QSet<QString> s_criticalServices;

    static constexpr int kTimeoutMs         = 45000;   // 45 s – marge pour faster_whisper CPU + cascade séquentielle
    static constexpr int kLazyLoadDelayMs   = 3000;
    static constexpr int kLazyRetryIntervalMs = 5000;
    static constexpr int kMaxLazyRetries    = 3;
};
