#include "SimulationEntity.h"

#include <QtMath>

// ─────────────────────────────────────────────────────
//  SimulationEntity — Implémentation
// ─────────────────────────────────────────────────────

SimulationEntity::SimulationEntity()
    : m_id(QUuid::createUuid().toString(QUuid::WithoutBraces))
{
}

SimulationEntity::SimulationEntity(Simulation::EntityType type)
    : m_id(QUuid::createUuid().toString(QUuid::WithoutBraces))
    , m_type(type)
{
    // Defaults par type
    switch (type) {
    case Simulation::EntityType::Smoke:
        m_speed     = 0.3;
        m_radius    = 15.0;
        m_intensity = 0.8;
        break;
    case Simulation::EntityType::Heat:
        m_speed     = 0.15;
        m_radius    = 20.0;
        m_intensity = 1.0;
        break;
    case Simulation::EntityType::Noise:
        m_speed     = 3.0;  // bruit se propage vite
        m_radius    = 30.0;
        m_intensity = 0.9;
        break;
    case Simulation::EntityType::Light:
        m_speed     = 0.0;  // statique (cône)
        m_radius    = 50.0;
        m_intensity = 1.0;
        break;
    case Simulation::EntityType::Water:
        m_speed     = 0.5;
        m_radius    = 10.0;
        m_intensity = 0.7;
        break;
    case Simulation::EntityType::Intruder:
        m_speed     = 1.5;
        m_radius    = 3.0;
        m_intensity = 1.0;
        break;
    case Simulation::EntityType::Robot:
        m_speed     = 1.0;
        m_radius    = 4.0;
        m_intensity = 1.0;
        break;
    case Simulation::EntityType::CognitiveAgent:
        m_speed     = 0.0;
        m_radius    = 5.0;
        m_intensity = 1.0;
        break;
    }
}

bool SimulationEntity::isExpired(int currentTick) const
{
    if (m_tickExpiry < 0) return false;
    return currentTick >= m_tickExpiry;
}

void SimulationEntity::advanceTick(int currentTick)
{
    if (m_state == Simulation::EntityState::Destroyed ||
        m_state == Simulation::EntityState::Idle)
        return;

    // Check expiry
    if (isExpired(currentTick)) {
        m_state = Simulation::EntityState::Fading;
        m_intensity *= 0.9;
        if (m_intensity < 0.01) {
            m_state = Simulation::EntityState::Destroyed;
        }
        return;
    }

    // Path-based movement
    if (hasTrajectory() && m_trajectoryIdx < m_trajectory.size()) {
        QPointF target = m_trajectory[m_trajectoryIdx];
        QPointF delta  = target - m_position;
        qreal dist = std::sqrt(delta.x() * delta.x() + delta.y() * delta.y());

        if (dist < m_speed + 0.5) {
            m_position = target;
            m_trajectoryIdx++;
        } else {
            qreal nx = delta.x() / dist;
            qreal ny = delta.y() / dist;
            m_position += QPointF(nx * m_speed, ny * m_speed);
            m_direction = qRadiansToDegrees(std::atan2(ny, nx));
        }
    }
    // Velocity-based movement
    else if (!m_velocity.isNull()) {
        m_position += m_velocity;
    }

    // Spreading entities grow radius
    if (m_state == Simulation::EntityState::Spreading) {
        m_radius += m_speed * 0.5;
        m_intensity = qMax(0.0, m_intensity - Simulation::kDefaultAttenuation * 0.1);
    }
}

QVariantMap SimulationEntity::toVariantMap() const
{
    return {
        {"id",          m_id},
        {"type",        static_cast<int>(m_type)},
        {"state",       static_cast<int>(m_state)},
        {"x",           m_position.x()},
        {"y",           m_position.y()},
        {"vx",          m_velocity.x()},
        {"vy",          m_velocity.y()},
        {"direction",   m_direction},
        {"speed",       m_speed},
        {"radius",      m_radius},
        {"intensity",   m_intensity},
        {"tickBorn",    m_tickBorn},
        {"tickExpiry",  m_tickExpiry},
        {"roomId",      m_roomId},
        {"properties",  m_properties}
    };
}

SimulationEntity SimulationEntity::fromVariantMap(const QVariantMap &data)
{
    SimulationEntity e;
    e.m_id          = data.value("id").toString();
    e.m_type        = static_cast<Simulation::EntityType>(data.value("type").toInt());
    e.m_state       = static_cast<Simulation::EntityState>(data.value("state").toInt());
    e.m_position    = QPointF(data.value("x").toDouble(), data.value("y").toDouble());
    e.m_velocity    = QPointF(data.value("vx").toDouble(), data.value("vy").toDouble());
    e.m_direction   = data.value("direction").toDouble();
    e.m_speed       = data.value("speed").toDouble();
    e.m_radius      = data.value("radius").toDouble();
    e.m_intensity   = data.value("intensity").toDouble();
    e.m_tickBorn    = data.value("tickBorn").toInt();
    e.m_tickExpiry  = data.value("tickExpiry").toInt();
    e.m_roomId      = data.value("roomId").toString();
    e.m_properties  = data.value("properties").toMap();
    return e;
}
