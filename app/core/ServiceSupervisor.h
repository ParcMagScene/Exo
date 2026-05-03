#pragma once

#include <QObject>
#include <QTimer>
#include <QMap>
#include <QSet>
#include "ServiceRegistry.h"
#include "ServiceDescriptor.h"
#include "WebSocketClient.h"

class QProcess;

// ═══════════════════════════════════════════════════════
//  ServiceSupervisor — Orchestrateur central EXO v5
//
//  Remplace ServiceManager v4. Responsable de :
//    1. Charger les ServiceDescriptors depuis services.json
//    2. Lancer les services séquentiellement
//    3. Superviser le ReadinessProtocol (WS connect → ready msg)
//    4. Appliquer la RetryPolicy (backoff exponentiel)
//    5. Détecter les crashs et relancer
//    6. Émettre allServicesReady quand tout est OK
//
//  Expose des Q_PROPERTY pour le splash screen QML.
// ═══════════════════════════════════════════════════════

class ServiceSupervisor : public QObject
{
    Q_OBJECT

    Q_PROPERTY(bool     allReady      READ allReady      NOTIFY allServicesReady)
    Q_PROPERTY(int      totalServices READ totalServices  NOTIFY serviceCountChanged)
    Q_PROPERTY(int      readyCount    READ readyCount     NOTIFY progressChanged)
    Q_PROPERTY(QString  currentAction READ currentAction  NOTIFY currentActionChanged)
    Q_PROPERTY(QVariantList serviceStatuses READ serviceStatuses NOTIFY progressChanged)

public:
    explicit ServiceSupervisor(QObject *parent = nullptr);
    ~ServiceSupervisor() override;

    // Point d'entrée — appelé depuis main.cpp
    Q_INVOKABLE void start(const QString &servicesJsonPath);

    // Accesseurs
    bool     allReady() const;
    int      totalServices() const;
    int      readyCount() const;
    QString  currentAction() const { return m_currentAction; }
    QVariantList serviceStatuses() const;

    // Accès au Registry
    ServiceRegistry* registry() { return &m_registry; }

    // QML — état d'un service par clé ("stt", "tts", etc.)
    Q_INVOKABLE QString serviceState(const QString &name) const;

    // Arrêt propre
    Q_INVOKABLE void shutdownAll();

signals:
    void allServicesReady();
    void serviceCountChanged();
    void progressChanged();
    void currentActionChanged();
    void startupFailed(const QString &reason);
    void serviceReady(const QString &name);

private:
    // ── Lifecycle ──
    void loadDescriptors(const QString &path);
    void startNext();
    void launchService(const QString &name);
    void doLaunchProcess(const QString &name);
    void probeReadiness(const QString &name);
    void onReadinessMessage(const QString &name, const QString &msg);
    void onReadinessConnected(const QString &name);
    void onReadinessTimeout(const QString &name);
    void onServiceCrashed(const QString &name, int exitCode);
    void retryOrFail(const QString &name);
    void markReady(const QString &name);
    void advanceToNext();

    // ── Utilitaires ──
    void setCurrentAction(const QString &action);
    QString pythonExeForVenv(const QString &venv) const;
    QString projectDir() const;

    // ── Données ──
    ServiceRegistry m_registry;
    QStringList     m_bootOrder;        // Ordre de lancement
    int             m_bootIndex = 0;
    QString         m_currentAction;
    bool            m_shutdownDone = false; // Protège contre le double shutdownAll()

    // ── Probes de readiness (une par service en cours) ──
    struct ReadinessProbe {
        WebSocketClient *client  = nullptr;
        QTimer          *timeout = nullptr;
        QTimer          *poll    = nullptr;
    };
    QMap<QString, ReadinessProbe> m_probes;

    // v5.1: services qui ont déjà avancé le bootIndex (phases intermédiaires)
    QSet<QString> m_advancedPast;

    void cleanupProbe(const QString &name);
};
