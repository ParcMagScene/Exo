#pragma once

#include <QObject>
#include <QProcess>
#include <QTimer>
#include <QVector>
#include <QMap>
#include <QUrl>
#include <QJsonArray>
#include "WebSocketClient.h"

// ═══════════════════════════════════════════════════════
//  ServiceManager — Auto-launch & health-probe des services EXO
//
//  Au démarrage de la GUI :
//    1. Charge services.json
//    2. Vérifie chaque service (tentative WS connect)
//    3. Lance ceux qui ne répondent pas via QProcess
//    4. Attend que tous soient prêts (readiness probe)
//    5. Émet allServicesReady()
//
//  Expose des Q_PROPERTY pour le splash screen QML.
// ═══════════════════════════════════════════════════════

class ServiceManager : public QObject
{
    Q_OBJECT

    Q_PROPERTY(bool     allReady      READ allReady      NOTIFY allServicesReady)
    Q_PROPERTY(int      totalServices READ totalServices  NOTIFY serviceCountChanged)
    Q_PROPERTY(int      readyCount    READ readyCount     NOTIFY serviceStatusChanged)
    Q_PROPERTY(QString  currentAction READ currentAction  NOTIFY currentActionChanged)
    Q_PROPERTY(QVariantList serviceStatuses READ serviceStatuses NOTIFY serviceStatusChanged)

public:
    explicit ServiceManager(QObject *parent = nullptr);
    ~ServiceManager() override;

    // Point d'entrée — appelé depuis main.cpp
    Q_INVOKABLE void start(const QString &servicesJsonPath);

    // Accesseurs Q_PROPERTY
    bool     allReady() const { return m_allReady; }
    int      totalServices() const { return m_services.size(); }
    int      readyCount() const;
    QString  currentAction() const { return m_currentAction; }
    QVariantList serviceStatuses() const;

    // Arrêt propre de tous les processus lancés par ServiceManager
    Q_INVOKABLE void shutdownAll();

signals:
    void allServicesReady();
    void serviceCountChanged();
    void serviceStatusChanged();
    void currentActionChanged();
    void startupFailed(const QString &reason);

private:
    struct ServiceInfo {
        QString     name;
        int         port       = 0;
        QString     venv;        // e.g. ".venv_stt_tts"
        QString     script;      // relative path
        QStringList args;

        // Runtime
        enum Status { Unknown, Checking, Running, Launching, Ready, Failed };
        Status              status  = Unknown;
        QProcess           *process = nullptr;   // non-null if we launched it
        WebSocketClient    *probe   = nullptr;
    };

    void loadServices(const QString &path);
    void checkNext();
    void probeService(int index);
    void launchService(int index);
    void onServiceProbeConnected(int index);
    void onServiceProbeFailed(int index);
    void advanceIndex();
    void setCurrentAction(const QString &action);
    QString pythonExeForVenv(const QString &venv) const;
    QStringList buildEnvList() const;
    QString projectDir() const;

    QVector<ServiceInfo> m_services;
    int     m_currentIndex = 0;
    bool    m_allReady     = false;
    QString m_currentAction;
    QTimer  m_probeTimeout;
    int     m_probeTimeoutMs = 30000;  // 30s max per service
};
