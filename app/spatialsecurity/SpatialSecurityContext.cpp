#include "SpatialSecurityContext.h"

// ─────────────────────────────────────────────────────
//  SecuritySubsystemState
// ─────────────────────────────────────────────────────

QVariantMap SecuritySubsystemState::toVariantMap() const
{
    return {
        {"status",        static_cast<int>(status)},
        {"riskLevel",     riskLevel},
        {"activeAlerts",  activeAlerts},
        {"incidentCount", incidentCount},
        {"lastUpdate",    lastUpdate.toString(Qt::ISODate)},
        {"details",       details}
    };
}

// ─────────────────────────────────────────────────────
//  SpatialSecurityContext
// ─────────────────────────────────────────────────────

SpatialSecurityContext::SpatialSecurityContext(QObject *parent)
    : QObject(parent)
{
}

SpatialSecurityContext::~SpatialSecurityContext() = default;

// ── Mise à jour par sous-système ──

static void applyState(SecuritySubsystemState &ss, const QVariantMap &state)
{
    ss.riskLevel    = state.value("riskLevel", ss.riskLevel).toDouble();
    ss.activeAlerts = state.value("activeAlerts", ss.activeAlerts).toInt();
    ss.incidentCount = state.value("incidentCount", ss.incidentCount).toInt();
    ss.details      = state;
    ss.lastUpdate   = QDateTime::currentDateTime();

    if (ss.riskLevel >= 0.8)
        ss.status = SpatialSecurity::SubsystemStatus::Critical;
    else if (ss.riskLevel >= 0.5)
        ss.status = SpatialSecurity::SubsystemStatus::Alert;
    else if (ss.riskLevel >= 0.2)
        ss.status = SpatialSecurity::SubsystemStatus::Warning;
    else
        ss.status = SpatialSecurity::SubsystemStatus::Normal;
}

void SpatialSecurityContext::updateIntrusionState(const QVariantMap &state)
{
    applyState(m_intrusion, state);
    emit subsystemChanged(static_cast<int>(SpatialSecurity::DetectorType::Intrusion), m_intrusion.toVariantMap());
    recalculateGlobalLevel();
}

void SpatialSecurityContext::updateFireState(const QVariantMap &state)
{
    applyState(m_fire, state);
    emit subsystemChanged(static_cast<int>(SpatialSecurity::DetectorType::Fire), m_fire.toVariantMap());
    recalculateGlobalLevel();
}

void SpatialSecurityContext::updateNetworkState(const QVariantMap &state)
{
    applyState(m_network, state);
    emit subsystemChanged(static_cast<int>(SpatialSecurity::DetectorType::Network), m_network.toVariantMap());
    recalculateGlobalLevel();
}

void SpatialSecurityContext::updateElectricalState(const QVariantMap &state)
{
    applyState(m_electrical, state);
    emit subsystemChanged(static_cast<int>(SpatialSecurity::DetectorType::Electrical), m_electrical.toVariantMap());
    recalculateGlobalLevel();
}

void SpatialSecurityContext::updateDomoticState(const QVariantMap &state)
{
    applyState(m_domotic, state);
    emit subsystemChanged(static_cast<int>(SpatialSecurity::DetectorType::Domotic), m_domotic.toVariantMap());
    recalculateGlobalLevel();
}

void SpatialSecurityContext::updateSimulationState(const QVariantMap &state)
{
    applyState(m_simulation, state);
    recalculateGlobalLevel();
}

void SpatialSecurityContext::updateCognitionState(const QVariantMap &state)
{
    applyState(m_cognition, state);
    recalculateGlobalLevel();
}

// ── Accès aux états ──

SecuritySubsystemState SpatialSecurityContext::intrusionState() const   { return m_intrusion; }
SecuritySubsystemState SpatialSecurityContext::fireState() const        { return m_fire; }
SecuritySubsystemState SpatialSecurityContext::networkState() const     { return m_network; }
SecuritySubsystemState SpatialSecurityContext::electricalState() const  { return m_electrical; }
SecuritySubsystemState SpatialSecurityContext::domoticState() const     { return m_domotic; }
SecuritySubsystemState SpatialSecurityContext::simulationState() const  { return m_simulation; }
SecuritySubsystemState SpatialSecurityContext::cognitionState() const   { return m_cognition; }

// ── État global ──

void SpatialSecurityContext::update()
{
    recalculateGlobalLevel();
    emit contextUpdated();
}

QVariantMap SpatialSecurityContext::snapshot() const
{
    return {
        {"intrusion",  m_intrusion.toVariantMap()},
        {"fire",       m_fire.toVariantMap()},
        {"network",    m_network.toVariantMap()},
        {"electrical", m_electrical.toVariantMap()},
        {"domotic",    m_domotic.toVariantMap()},
        {"simulation", m_simulation.toVariantMap()},
        {"cognition",  m_cognition.toVariantMap()},
        {"globalSecurityLevel", m_globalSecurityLevel}
    };
}

QVariantMap SpatialSecurityContext::diff(const QVariantMap &previous) const
{
    QVariantMap result;
    const auto current = snapshot();
    for (auto it = current.constBegin(); it != current.constEnd(); ++it) {
        if (!previous.contains(it.key()) || previous.value(it.key()) != it.value())
            result.insert(it.key(), it.value());
    }
    return result;
}

// ── Requêtes ──

double SpatialSecurityContext::globalSecurityLevel() const
{
    return m_globalSecurityLevel;
}

SpatialSecurity::SecuritySeverity SpatialSecurityContext::overallSeverity() const
{
    if (m_globalSecurityLevel >= 0.9) return SpatialSecurity::SecuritySeverity::Emergency;
    if (m_globalSecurityLevel >= 0.7) return SpatialSecurity::SecuritySeverity::Critical;
    if (m_globalSecurityLevel >= 0.5) return SpatialSecurity::SecuritySeverity::High;
    if (m_globalSecurityLevel >= 0.3) return SpatialSecurity::SecuritySeverity::Medium;
    if (m_globalSecurityLevel >= 0.1) return SpatialSecurity::SecuritySeverity::Low;
    return SpatialSecurity::SecuritySeverity::Info;
}

QStringList SpatialSecurityContext::activeAlertRooms() const
{
    QStringList rooms;
    for (auto it = m_roomAlerts.constBegin(); it != m_roomAlerts.constEnd(); ++it) {
        if (!it.value().isEmpty())
            rooms.append(it.key());
    }
    return rooms;
}

QStringList SpatialSecurityContext::criticalSubsystems() const
{
    QStringList result;
    if (m_intrusion.status  == SpatialSecurity::SubsystemStatus::Critical) result.append("intrusion");
    if (m_fire.status       == SpatialSecurity::SubsystemStatus::Critical) result.append("fire");
    if (m_network.status    == SpatialSecurity::SubsystemStatus::Critical) result.append("network");
    if (m_electrical.status == SpatialSecurity::SubsystemStatus::Critical) result.append("electrical");
    if (m_domotic.status    == SpatialSecurity::SubsystemStatus::Critical) result.append("domotic");
    return result;
}

// ── Interne ──

void SpatialSecurityContext::recalculateGlobalLevel()
{
    // Pondération : incendie et intrusion prioritaires
    const double weights[] = { 0.25, 0.30, 0.10, 0.15, 0.10, 0.05, 0.05 };
    const double levels[]  = {
        m_intrusion.riskLevel,
        m_fire.riskLevel,
        m_network.riskLevel,
        m_electrical.riskLevel,
        m_domotic.riskLevel,
        m_simulation.riskLevel,
        m_cognition.riskLevel
    };

    double weighted = 0.0;
    double maxLevel = 0.0;
    for (int i = 0; i < 7; ++i) {
        weighted += levels[i] * weights[i];
        maxLevel = qMax(maxLevel, levels[i]);
    }

    // Le risque global est le max entre la moyenne pondérée et 80% du max individuel
    double newLevel = qMax(weighted, maxLevel * 0.8);
    newLevel = qBound(0.0, newLevel, 1.0);

    if (qAbs(newLevel - m_globalSecurityLevel) > 0.005) {
        m_globalSecurityLevel = newLevel;
        emit securityLevelChanged(m_globalSecurityLevel);
    }
}

SpatialSecurity::SubsystemStatus SpatialSecurityContext::statusFromRisk(double riskLevel) const
{
    if (riskLevel >= 0.8) return SpatialSecurity::SubsystemStatus::Critical;
    if (riskLevel >= 0.5) return SpatialSecurity::SubsystemStatus::Alert;
    if (riskLevel >= 0.2) return SpatialSecurity::SubsystemStatus::Warning;
    return SpatialSecurity::SubsystemStatus::Normal;
}
