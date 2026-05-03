#ifndef SPATIALSECURITYCONTEXT_H
#define SPATIALSECURITYCONTEXT_H

#include <QObject>
#include <QString>
#include <QVariantMap>
#include <QVariantList>
#include <QHash>
#include <QDateTime>

#include "SpatialSecurityEnums.h"

// ─────────────────────────────────────────────────────
//  État d'un sous-système de sécurité
// ─────────────────────────────────────────────────────

struct SecuritySubsystemState {
    SpatialSecurity::SubsystemStatus status = SpatialSecurity::SubsystemStatus::Unknown;
    double riskLevel     = 0.0;   // 0..1
    int    activeAlerts  = 0;
    int    incidentCount = 0;
    QDateTime lastUpdate;
    QVariantMap details;

    QVariantMap toVariantMap() const;
};

// ─────────────────────────────────────────────────────
//  SpatialSecurityContext — État global de sécurité
//
//  Agrège l'état de chaque sous-système :
//  intrusion, incendie, réseau, électrique, domotique,
//  simulation, cognition.
// ─────────────────────────────────────────────────────

class SpatialSecurityContext : public QObject
{
    Q_OBJECT

public:
    explicit SpatialSecurityContext(QObject *parent = nullptr);
    ~SpatialSecurityContext() override;

    // ── Mise à jour par sous-système ──
    void updateIntrusionState(const QVariantMap &state);
    void updateFireState(const QVariantMap &state);
    void updateNetworkState(const QVariantMap &state);
    void updateElectricalState(const QVariantMap &state);
    void updateDomoticState(const QVariantMap &state);
    void updateSimulationState(const QVariantMap &state);
    void updateCognitionState(const QVariantMap &state);

    // ── Accès aux états ──
    SecuritySubsystemState intrusionState() const;
    SecuritySubsystemState fireState() const;
    SecuritySubsystemState networkState() const;
    SecuritySubsystemState electricalState() const;
    SecuritySubsystemState domoticState() const;
    SecuritySubsystemState simulationState() const;
    SecuritySubsystemState cognitionState() const;

    // ── État global ──
    void update();
    QVariantMap snapshot() const;
    QVariantMap diff(const QVariantMap &previous) const;

    // ── Requêtes ──
    double globalSecurityLevel() const;    // 0..1 (0=sûr, 1=critique)
    SpatialSecurity::SecuritySeverity overallSeverity() const;
    QStringList activeAlertRooms() const;
    QStringList criticalSubsystems() const;

signals:
    void contextUpdated();
    void subsystemChanged(int detectorType, const QVariantMap &state);
    void securityLevelChanged(double level);
    void alertTriggered(const QVariantMap &alert);

private:
    void recalculateGlobalLevel();
    SpatialSecurity::SubsystemStatus statusFromRisk(double riskLevel) const;

    SecuritySubsystemState m_intrusion;
    SecuritySubsystemState m_fire;
    SecuritySubsystemState m_network;
    SecuritySubsystemState m_electrical;
    SecuritySubsystemState m_domotic;
    SecuritySubsystemState m_simulation;
    SecuritySubsystemState m_cognition;

    double m_globalSecurityLevel = 0.0;
    QHash<QString, QStringList> m_roomAlerts;
};

#endif // SPATIALSECURITYCONTEXT_H
