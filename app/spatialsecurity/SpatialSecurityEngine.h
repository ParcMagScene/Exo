#pragma once

#include <QObject>
#include <QTimer>
#include <QString>
#include <QVariantMap>
#include <QVariantList>
#include <QVector>
#include <qqml.h>

#include "SpatialSecurityEnums.h"
#include "SpatialSecurityContext.h"
#include "SpatialSecurityMemory.h"
#include "IntrusionDetector.h"
#include "FireDetector.h"
#include "ElectricalRiskDetector.h"
#include "NetworkRiskDetector.h"
#include "DomoticAnomalyDetector.h"

class FloorPlanModel;

// ─────────────────────────────────────────────────────
//  SpatialSecurityEngine — orchestrateur principal
//  Pipeline : Perception → Analysis → Detection →
//             RiskAssessment → ActionPlanning → Supervision
// ─────────────────────────────────────────────────────

class SpatialSecurityEngine : public QObject
{
    Q_OBJECT
    QML_ELEMENT

    // ── Propriétés QML ──
    Q_PROPERTY(int phase READ phase NOTIFY phaseChanged)
    Q_PROPERTY(bool running READ isRunning NOTIFY runningChanged)
    Q_PROPERTY(int cycleCount READ cycleCount NOTIFY cycleCompleted)
    Q_PROPERTY(double globalSecurityLevel READ globalSecurityLevel NOTIFY securityLevelChanged)
    Q_PROPERTY(int overallSeverity READ overallSeverityInt NOTIFY securityLevelChanged)
    Q_PROPERTY(QVariantList activeAlerts READ activeAlerts NOTIFY alertsChanged)
    Q_PROPERTY(QVariantList recentIncidents READ recentIncidents NOTIFY incidentsChanged)
    Q_PROPERTY(QVariantMap securityState READ securityState NOTIFY stateChanged)

public:
    explicit SpatialSecurityEngine(QObject *parent = nullptr);
    ~SpatialSecurityEngine() override;

    // ── Sources de données ──
    void setFloorPlanModel(FloorPlanModel *model);
    Q_INVOKABLE void updateFromSensors(const QVariantMap &sensorData);
    Q_INVOKABLE void updateFromNetwork(const QVariantMap &networkData, const QVariantList &deviceStatuses);
    Q_INVOKABLE void updateFromSimulation(const QVariantMap &heatmapData, const QVariantList &trajectories);
    Q_INVOKABLE void updateFromHomeGraph(const QVariantList &devices, const QVariantMap &consumptionData);
    Q_INVOKABLE void updateOccupancy(const QVariantMap &occupancyData);

    // ── Cycle de sécurité ──
    Q_INVOKABLE void runSecurityCycle();
    Q_INVOKABLE void startAutoCycle(int intervalMs = 3000);
    Q_INVOKABLE void stopAutoCycle();

    // ── Configuration ──
    Q_INVOKABLE void setForbiddenZones(const QStringList &zoneIds);
    Q_INVOKABLE void setSecurityThreshold(double threshold);

    // ── Accès aux résultats ──
    int  phase() const;
    bool isRunning() const;
    int  cycleCount() const;
    double globalSecurityLevel() const;
    int  overallSeverityInt() const;

    QVariantList activeAlerts() const;
    QVariantList recentIncidents() const;
    QVariantMap  securityState() const;

    Q_INVOKABLE QVariantList getDetectedRisks() const;
    Q_INVOKABLE QVariantMap  getSecurityExplanation(const QString &alertId) const;
    Q_INVOKABLE QVariantList getRecommendedActions() const;
    Q_INVOKABLE QVariantList getAlertsByRoom(const QString &roomId) const;
    Q_INVOKABLE QVariantMap  getRoomSecurityStatus(const QString &roomId) const;
    Q_INVOKABLE QVariantList getIncidentHistory(int maxCount = 50) const;

    // ── Sous-modules (accès pour tests / intégration) ──
    SpatialSecurityContext *securityContext() const;
    SpatialSecurityMemory  *securityMemory() const;
    IntrusionDetector      *intrusionDetector() const;
    FireDetector           *fireDetector() const;
    ElectricalRiskDetector *electricalDetector() const;
    NetworkRiskDetector    *networkDetector() const;
    DomoticAnomalyDetector *domoticDetector() const;

signals:
    void phaseChanged(int phase);
    void runningChanged(bool running);
    void cycleCompleted(int count);
    void securityLevelChanged(double level);
    void alertsChanged();
    void incidentsChanged();
    void stateChanged();

    void securityAlertRaised(const QVariantMap &alert);
    void securityActionRecommended(const QVariantMap &action);
    void emergencyDetected(const QVariantMap &details);

private:
    void setPhase(SpatialSecurity::SecurityPhase p);

    // ── Étapes du pipeline ──
    void phasePerception();
    void phaseAnalysis();
    void phaseDetection();
    void phaseRiskAssessment();
    void phaseActionPlanning();
    void phaseSupervision();

    // ── Helpers ──
    void processAlerts(const QVector<SecurityAlert> &alerts);
    QVariantMap computeAction(const SecurityAlert &alert) const;
    void escalateEmergency(const SecurityAlert &alert);

    // ── Sous-modules (propriété totale) ──
    SpatialSecurityContext *m_context    = nullptr;
    SpatialSecurityMemory  *m_memory    = nullptr;
    IntrusionDetector      *m_intrusion  = nullptr;
    FireDetector           *m_fire       = nullptr;
    ElectricalRiskDetector *m_electrical = nullptr;
    NetworkRiskDetector    *m_network    = nullptr;
    DomoticAnomalyDetector *m_domotic    = nullptr;

    FloorPlanModel *m_floorModel = nullptr;

    // ── État du cycle ──
    SpatialSecurity::SecurityPhase m_phase = SpatialSecurity::SecurityPhase::Idle;
    bool m_running     = false;
    int  m_cycleCount  = 0;
    double m_threshold = SpatialSecurity::kDefaultSecurityThreshold;

    QTimer m_autoCycleTimer;

    // ── Données d'entrée courantes ──
    QVariantMap  m_sensorData;
    QVariantMap  m_occupancyData;
    QVariantMap  m_networkData;
    QVariantList m_deviceStatuses;
    QVariantMap  m_heatmapData;
    QVariantList m_trajectories;
    QVariantList m_homeGraphDevices;
    QVariantMap  m_consumptionData;

    // ── Résultats du dernier cycle ──
    QVector<SecurityAlert> m_lastAlerts;
    QVariantList m_recommendedActions;
};
