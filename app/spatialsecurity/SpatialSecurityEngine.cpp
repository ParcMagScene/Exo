#include "SpatialSecurityEngine.h"
#include <algorithm>

// ─────────────────────────────────────────────────────
//  Construction / Destruction
// ─────────────────────────────────────────────────────

SpatialSecurityEngine::SpatialSecurityEngine(QObject *parent)
    : QObject(parent),
      m_context(new SpatialSecurityContext(this)),
      m_memory(new SpatialSecurityMemory(this)),
      m_intrusion(new IntrusionDetector(this)),
      m_fire(new FireDetector(this)),
      m_electrical(new ElectricalRiskDetector(this)),
      m_network(new NetworkRiskDetector(this)),
      m_domotic(new DomoticAnomalyDetector(this))
{
    connect(&m_autoCycleTimer, &QTimer::timeout, this, &SpatialSecurityEngine::runSecurityCycle);
}

SpatialSecurityEngine::~SpatialSecurityEngine() = default;

// ─────────────────────────────────────────────────────
//  Sources de données
// ─────────────────────────────────────────────────────

void SpatialSecurityEngine::setFloorPlanModel(FloorPlanModel *model)
{
    m_floorModel = model;
}

void SpatialSecurityEngine::updateFromSensors(const QVariantMap &sensorData)
{
    m_sensorData = sensorData;
}

void SpatialSecurityEngine::updateFromNetwork(const QVariantMap &networkData, const QVariantList &deviceStatuses)
{
    m_networkData    = networkData;
    m_deviceStatuses = deviceStatuses;
}

void SpatialSecurityEngine::updateFromSimulation(const QVariantMap &heatmapData, const QVariantList &trajectories)
{
    m_heatmapData  = heatmapData;
    m_trajectories = trajectories;
}

void SpatialSecurityEngine::updateFromHomeGraph(const QVariantList &devices, const QVariantMap &consumptionData)
{
    m_homeGraphDevices = devices;
    m_consumptionData  = consumptionData;
}

void SpatialSecurityEngine::updateOccupancy(const QVariantMap &occupancyData)
{
    m_occupancyData = occupancyData;
}

// ─────────────────────────────────────────────────────
//  Cycle de sécurité
// ─────────────────────────────────────────────────────

void SpatialSecurityEngine::runSecurityCycle()
{
    if (m_running) return;
    m_running = true;
    emit runningChanged(true);

    phasePerception();
    phaseAnalysis();
    phaseDetection();
    phaseRiskAssessment();
    phaseActionPlanning();
    phaseSupervision();

    setPhase(SpatialSecurity::SecurityPhase::Idle);
    m_running = false;
    ++m_cycleCount;
    emit runningChanged(false);
    emit cycleCompleted(m_cycleCount);
}

void SpatialSecurityEngine::startAutoCycle(int intervalMs)
{
    m_autoCycleTimer.start(intervalMs);
}

void SpatialSecurityEngine::stopAutoCycle()
{
    m_autoCycleTimer.stop();
}

void SpatialSecurityEngine::setForbiddenZones(const QStringList &zoneIds)
{
    m_intrusion->setForbiddenZones(zoneIds);
}

void SpatialSecurityEngine::setSecurityThreshold(double threshold)
{
    m_threshold = qBound(0.0, threshold, 1.0);
}

// ─────────────────────────────────────────────────────
//  Pipeline — Phases
// ─────────────────────────────────────────────────────

void SpatialSecurityEngine::phasePerception()
{
    setPhase(SpatialSecurity::SecurityPhase::Perception);

    // Distribuer les données aux détecteurs
    m_intrusion->setSensorData(m_sensorData);
    m_intrusion->setOccupancyData(m_occupancyData);
    m_intrusion->setSimulationData(m_trajectories);

    m_fire->setSensorData(m_sensorData);
    m_fire->setSimulationData(m_heatmapData);

    m_electrical->setConsumptionData(m_consumptionData);
    m_electrical->setDeviceData(m_homeGraphDevices);

    m_network->setNetworkMapData(m_networkData);
    m_network->setDeviceStatusData(m_deviceStatuses);

    m_domotic->setDeviceStates(m_homeGraphDevices);
    m_domotic->setOccupancyData(m_occupancyData);
    m_domotic->setSensorData(m_sensorData);
}

void SpatialSecurityEngine::phaseAnalysis()
{
    setPhase(SpatialSecurity::SecurityPhase::Analysis);

    // Mettre à jour le contexte avec l'état courant de chaque sous-système
    m_context->updateIntrusionState({
        {"risk", m_intrusion->alertsToVariantList().isEmpty() ? 0.0
            : m_sensorData.value("intrusionRisk", 0.0).toDouble()},
        {"alertCount", m_intrusion->alertsToVariantList().size()}});

    m_context->updateNetworkState({
        {"risk", m_networkData.value("overallRisk", 0.0).toDouble()},
        {"alertCount", m_network->alertsToVariantList().size()}});

    m_context->updateSimulationState({
        {"risk", m_heatmapData.value("overallRisk", 0.0).toDouble()},
        {"alertCount", 0}});

    m_context->update();
}

void SpatialSecurityEngine::phaseDetection()
{
    setPhase(SpatialSecurity::SecurityPhase::Detection);

    m_lastAlerts.clear();

    // Exécuter toutes les détections
    m_lastAlerts.append(m_intrusion->runAllDetections());
    m_lastAlerts.append(m_fire->runAllDetections());
    m_lastAlerts.append(m_electrical->runAllDetections());
    m_lastAlerts.append(m_network->runAllDetections());
    m_lastAlerts.append(m_domotic->runAllDetections());

    emit alertsChanged();
}

void SpatialSecurityEngine::phaseRiskAssessment()
{
    setPhase(SpatialSecurity::SecurityPhase::RiskAssessment);

    // Mettre à jour le contexte avec les résultats de détection
    m_context->updateIntrusionState({
        {"risk", m_intrusion->alertsToVariantList().isEmpty() ? 0.0 : 0.7},
        {"alertCount", m_intrusion->alertsToVariantList().size()}});

    m_context->updateFireState({
        {"risk", m_fire->alertsToVariantList().isEmpty() ? 0.0 : 0.8},
        {"alertCount", m_fire->alertsToVariantList().size()}});

    m_context->updateElectricalState({
        {"risk", m_electrical->alertsToVariantList().isEmpty() ? 0.0 : 0.5},
        {"alertCount", m_electrical->alertsToVariantList().size()}});

    m_context->updateNetworkState({
        {"risk", m_network->alertsToVariantList().isEmpty() ? 0.0 : 0.4},
        {"alertCount", m_network->alertsToVariantList().size()}});

    m_context->updateDomoticState({
        {"risk", m_domotic->alertsToVariantList().isEmpty() ? 0.0 : 0.3},
        {"alertCount", m_domotic->alertsToVariantList().size()}});

    m_context->update();
    emit securityLevelChanged(m_context->globalSecurityLevel());

    // Enregistrer les incidents critiques en mémoire
    for (const auto &alert : m_lastAlerts) {
        if (alert.severity >= SpatialSecurity::SecuritySeverity::High) {
            m_memory->storeIncident({
                alert.id, alert.riskType, alert.severity,
                alert.roomId, alert.description, alert.confidence,
                alert.evidence, {}, QDateTime::currentDateTime(), false
            });
        }
    }

    processAlerts(m_lastAlerts);
}

void SpatialSecurityEngine::phaseActionPlanning()
{
    setPhase(SpatialSecurity::SecurityPhase::ActionPlanning);

    m_recommendedActions.clear();

    for (const auto &alert : m_lastAlerts) {
        if (alert.confidence >= m_threshold) {
            QVariantMap action = computeAction(alert);
            if (!action.isEmpty())
                m_recommendedActions.append(action);
        }
    }
}

void SpatialSecurityEngine::phaseSupervision()
{
    setPhase(SpatialSecurity::SecurityPhase::Supervision);

    // Vérifier les urgences
    for (const auto &alert : m_lastAlerts) {
        if (alert.severity >= SpatialSecurity::SecuritySeverity::Emergency) {
            escalateEmergency(alert);
        }
    }

    emit stateChanged();
    emit incidentsChanged();
}

// ─────────────────────────────────────────────────────
//  Helpers
// ─────────────────────────────────────────────────────

void SpatialSecurityEngine::processAlerts(const QVector<SecurityAlert> &alerts)
{
    for (const auto &alert : alerts) {
        emit securityAlertRaised(alert.toVariantMap());
    }
}

QVariantMap SpatialSecurityEngine::computeAction(const SecurityAlert &alert) const
{
    QVariantMap action;
    action["alertId"]  = alert.id;
    action["roomId"]   = alert.roomId;
    action["severity"] = static_cast<int>(alert.severity);
    action["timestamp"] = QDateTime::currentDateTime().toString(Qt::ISODate);

    switch (alert.riskType) {
    case SpatialSecurity::RiskType::Intrusion:
        action["type"]   = static_cast<int>(SpatialSecurity::SecurityActionType::ActivateAlarm);
        action["label"]  = QStringLiteral("Activer alarme intrusion");
        action["detail"] = QStringLiteral("Verrouiller les accès et activer les caméras dans %1").arg(alert.roomId);
        break;

    case SpatialSecurity::RiskType::Fire:
    case SpatialSecurity::RiskType::Smoke:
        action["type"]   = static_cast<int>(SpatialSecurity::SecurityActionType::ActivateSprinklers);
        action["label"]  = QStringLiteral("Activer sprinklers");
        action["detail"] = QStringLiteral("Couper ventilation et activer sprinklers dans %1").arg(alert.roomId);
        break;

    case SpatialSecurity::RiskType::Electrical:
        action["type"]   = static_cast<int>(SpatialSecurity::SecurityActionType::CutPower);
        action["label"]  = QStringLiteral("Couper alimentation");
        action["detail"] = QStringLiteral("Isoler le circuit électrique dans %1").arg(alert.roomId);
        break;

    case SpatialSecurity::RiskType::NetworkFailure:
        action["type"]   = static_cast<int>(SpatialSecurity::SecurityActionType::RestartDevice);
        action["label"]  = QStringLiteral("Redémarrer équipement réseau");
        action["detail"] = QStringLiteral("Tenter un redémarrage du point d'accès pour %1").arg(alert.roomId);
        break;

    case SpatialSecurity::RiskType::DomoticAnomaly:
        action["type"]   = static_cast<int>(SpatialSecurity::SecurityActionType::ShutdownDevice);
        action["label"]  = QStringLiteral("Arrêter appareil suspect");
        action["detail"] = QStringLiteral("Désactiver l'appareil anomalique dans %1").arg(alert.roomId);
        break;

    default:
        action["type"]   = static_cast<int>(SpatialSecurity::SecurityActionType::SendAlert);
        action["label"]  = QStringLiteral("Envoyer notification");
        action["detail"] = alert.description;
        break;
    }

    return action;
}

void SpatialSecurityEngine::escalateEmergency(const SecurityAlert &alert)
{
    QVariantMap emergency;
    emergency["alertId"]     = alert.id;
    emergency["riskType"]    = static_cast<int>(alert.riskType);
    emergency["severity"]    = static_cast<int>(alert.severity);
    emergency["roomId"]      = alert.roomId;
    emergency["description"] = alert.description;
    emergency["timestamp"]   = QDateTime::currentDateTime().toString(Qt::ISODate);
    emergency["actions"]     = QVariantList{
        QVariantMap{{"type", static_cast<int>(SpatialSecurity::SecurityActionType::CallEmergency)},
                    {"label", QStringLiteral("Appeler les secours")}},
        QVariantMap{{"type", static_cast<int>(SpatialSecurity::SecurityActionType::EvacuateZone)},
                    {"label", QStringLiteral("Évacuer %1").arg(alert.roomId)}}
    };

    emit emergencyDetected(emergency);
}

void SpatialSecurityEngine::setPhase(SpatialSecurity::SecurityPhase p)
{
    if (m_phase == p) return;
    m_phase = p;
    emit phaseChanged(static_cast<int>(p));
}

// ─────────────────────────────────────────────────────
//  Accesseurs
// ─────────────────────────────────────────────────────

int  SpatialSecurityEngine::phase() const           { return static_cast<int>(m_phase); }
bool SpatialSecurityEngine::isRunning() const       { return m_running; }
int  SpatialSecurityEngine::cycleCount() const      { return m_cycleCount; }
double SpatialSecurityEngine::globalSecurityLevel() const { return m_context->globalSecurityLevel(); }
int  SpatialSecurityEngine::overallSeverityInt() const    { return static_cast<int>(m_context->overallSeverity()); }

QVariantList SpatialSecurityEngine::activeAlerts() const
{
    QVariantList list;
    for (const auto &a : m_lastAlerts)
        list.append(a.toVariantMap());
    return list;
}

QVariantList SpatialSecurityEngine::recentIncidents() const
{
    const auto incidents = m_memory->unresolvedIncidents();
    QVariantList list;
    for (const auto &i : incidents)
        list.append(i.toVariantMap());
    return list;
}

QVariantMap SpatialSecurityEngine::securityState() const
{
    QVariantMap state;
    state["phase"]         = static_cast<int>(m_phase);
    state["running"]       = m_running;
    state["cycleCount"]    = m_cycleCount;
    state["securityLevel"] = m_context->globalSecurityLevel();
    state["severity"]      = static_cast<int>(m_context->overallSeverity());
    state["alertCount"]    = m_lastAlerts.size();
    state["incidentCount"] = m_memory->totalIncidents();
    state["context"]       = m_context->snapshot();
    return state;
}

QVariantList SpatialSecurityEngine::getDetectedRisks() const
{
    return activeAlerts();
}

QVariantMap SpatialSecurityEngine::getSecurityExplanation(const QString &alertId) const
{
    QVariantMap explanation;
    for (const auto &alert : m_lastAlerts) {
        if (alert.id == alertId) {
            explanation["alertId"]     = alert.id;
            explanation["riskType"]    = static_cast<int>(alert.riskType);
            explanation["roomId"]      = alert.roomId;
            explanation["confidence"]  = alert.confidence;

            // Appeler le bon détecteur pour l'explication
            switch (alert.detectorType) {
            case SpatialSecurity::DetectorType::Intrusion:
                explanation["explanation"] = m_intrusion->explainIntrusion(alert);
                break;
            case SpatialSecurity::DetectorType::Fire:
                explanation["explanation"] = m_fire->explainFire(alert);
                break;
            case SpatialSecurity::DetectorType::Electrical:
                explanation["explanation"] = m_electrical->explainElectricalRisk(alert);
                break;
            case SpatialSecurity::DetectorType::Network:
                explanation["explanation"] = m_network->explainNetworkRisk(alert);
                break;
            case SpatialSecurity::DetectorType::Domotic:
                explanation["explanation"] = m_domotic->explainDomoticAnomaly(alert);
                break;
            }
            break;
        }
    }
    return explanation;
}

QVariantList SpatialSecurityEngine::getRecommendedActions() const
{
    return m_recommendedActions;
}

QVariantList SpatialSecurityEngine::getAlertsByRoom(const QString &roomId) const
{
    QVariantList list;
    for (const auto &a : m_lastAlerts) {
        if (a.roomId == roomId)
            list.append(a.toVariantMap());
    }
    return list;
}

QVariantMap SpatialSecurityEngine::getRoomSecurityStatus(const QString &roomId) const
{
    QVariantMap status;
    status["roomId"] = roomId;

    int alertCount = 0;
    int maxSeverity = 0;
    QVariantList roomAlerts;
    for (const auto &a : m_lastAlerts) {
        if (a.roomId == roomId) {
            ++alertCount;
            maxSeverity = qMax(maxSeverity, static_cast<int>(a.severity));
            roomAlerts.append(a.toVariantMap());
        }
    }

    status["alertCount"]  = alertCount;
    status["maxSeverity"] = maxSeverity;
    status["alerts"]      = roomAlerts;
    status["safe"]        = (alertCount == 0);
    return status;
}

QVariantList SpatialSecurityEngine::getIncidentHistory(int maxCount) const
{
    const auto all = m_memory->queryByTimeRange(
        QDateTime::currentDateTime().addDays(-30), QDateTime::currentDateTime());

    QVariantList list;
    int count = 0;
    for (auto it = all.rbegin(); it != all.rend() && count < maxCount; ++it, ++count)
        list.append(it->toVariantMap());
    return list;
}

// ── Accès sous-modules ──

SpatialSecurityContext *SpatialSecurityEngine::securityContext() const  { return m_context; }
SpatialSecurityMemory  *SpatialSecurityEngine::securityMemory() const  { return m_memory; }
IntrusionDetector      *SpatialSecurityEngine::intrusionDetector() const { return m_intrusion; }
FireDetector           *SpatialSecurityEngine::fireDetector() const      { return m_fire; }
ElectricalRiskDetector *SpatialSecurityEngine::electricalDetector() const{ return m_electrical; }
NetworkRiskDetector    *SpatialSecurityEngine::networkDetector() const   { return m_network; }
DomoticAnomalyDetector *SpatialSecurityEngine::domoticDetector() const  { return m_domotic; }
