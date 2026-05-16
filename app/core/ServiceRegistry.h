#pragma once

#include <QObject>
#include <QMap>
#include <QVariantList>
#include "ServiceState.h"
#include "ServiceDescriptor.h"

class QProcess;

// ═══════════════════════════════════════════════════════
//  ServiceRegistry — Table centrale des services EXO v5
//
//  Source de vérité unique : descripteurs + états runtime.
//  Observable par QML via Q_PROPERTY.
// ═══════════════════════════════════════════════════════

class ServiceRegistry : public QObject
{
    Q_OBJECT

    Q_PROPERTY(int  totalServices READ totalServices NOTIFY registryChanged)
    Q_PROPERTY(int  readyCount    READ readyCount    NOTIFY registryChanged)
    Q_PROPERTY(bool allReady      READ allReady      NOTIFY allServicesReady)
    Q_PROPERTY(QVariantList serviceStatuses READ serviceStatuses NOTIFY registryChanged)

public:
    struct ServiceEntry {
        Exo::ServiceDescriptor descriptor;
        Exo::ServiceState      state   = Exo::ServiceState::Stopped;
        Exo::ReadinessPhase    phase   = Exo::ReadinessPhase::None;
        QProcess              *process = nullptr;
        int                    retryCount = 0;
        qint64                 pid     = 0;

        // Champs enrichis pour le statut détaillé
        QString                message;
        qint64                 startupTimeMs = -1;
        qint64                 latencyMs = -1;
        int                    restarts = 0;
        qint64                 lastHeartbeat = 0;
        double                 cpu = 0.0;
        double                 ram = 0.0;
    };

    explicit ServiceRegistry(QObject *parent = nullptr);

    // ── Enregistrement ──
    void registerService(const Exo::ServiceDescriptor &desc);

    // ── Accès ──
    bool contains(const QString &name) const;
    const ServiceEntry& entry(const QString &name) const;
    ServiceEntry& entry(const QString &name);
    QStringList serviceNames() const;
    int totalServices() const { return m_entries.size(); }
    int readyCount() const;
    bool allReady() const;

    // ── Mutation d'état ──
    void setState(const QString &name, Exo::ServiceState newState);
    void setPhase(const QString &name, Exo::ReadinessPhase phase);
    void setProcess(const QString &name, QProcess *proc, qint64 pid);
    void incrementRetry(const QString &name);
    void resetRetry(const QString &name);

    // ── QML ──
    QVariantList serviceStatuses() const;
    Q_INVOKABLE QString serviceState(const QString &name) const;
    Q_INVOKABLE QString servicePhase(const QString &name) const;

signals:
    void registryChanged();
    void allServicesReady();
    void serviceStateChanged(const QString &name, const QString &oldState, const QString &newState);
    void servicePhaseChanged(const QString &name, const QString &phase);

private:
    QMap<QString, ServiceEntry> m_entries;
    QStringList m_insertionOrder;  // preserve registration order for splash screen
    static ServiceEntry s_nullEntry;
};
