#ifndef SIMULATIONENTITY_H
#define SIMULATIONENTITY_H

#include "SimulationEnums.h"

#include <QObject>
#include <QPointF>
#include <QSizeF>
#include <QString>
#include <QVariantMap>
#include <QVector>
#include <QUuid>

// ─────────────────────────────────────────────────────
//  SimulationEntity — Entité simulée dans l'espace
//
//  Représente un élément dynamique :
//    intrus, robot, fumée, chaleur, bruit, lumière, eau,
//    agent cognitif (symbolique)
//
//  Lightweight value class — pas QObject.
// ─────────────────────────────────────────────────────
class SimulationEntity
{
public:
    SimulationEntity();
    explicit SimulationEntity(Simulation::EntityType type);

    // ── Identity ──
    QString id() const { return m_id; }
    void    setId(const QString &id) { m_id = id; }

    // ── Type ──
    Simulation::EntityType type() const { return m_type; }
    void setType(Simulation::EntityType t) { m_type = t; }

    // ── State ──
    Simulation::EntityState state() const { return m_state; }
    void setState(Simulation::EntityState s) { m_state = s; }

    // ── Position and motion ──
    QPointF position() const { return m_position; }
    void    setPosition(const QPointF &pos) { m_position = pos; }

    QPointF velocity() const { return m_velocity; }
    void    setVelocity(const QPointF &vel) { m_velocity = vel; }

    qreal direction() const { return m_direction; }
    void  setDirection(qreal deg) { m_direction = deg; }

    qreal speed() const { return m_speed; }
    void  setSpeed(qreal s) { m_speed = s; }

    // ── Spatial extent ──
    qreal radius() const { return m_radius; }
    void  setRadius(qreal r) { m_radius = r; }

    qreal intensity() const { return m_intensity; }
    void  setIntensity(qreal i) { m_intensity = i; }

    // ── Lifetime ──
    int  tickBorn() const { return m_tickBorn; }
    void setTickBorn(int tick) { m_tickBorn = tick; }

    int  tickExpiry() const { return m_tickExpiry; }
    void setTickExpiry(int tick) { m_tickExpiry = tick; }

    bool isExpired(int currentTick) const;

    // ── Trajectory (for path-based entities) ──
    QVector<QPointF> trajectory() const { return m_trajectory; }
    void setTrajectory(const QVector<QPointF> &path) { m_trajectory = path; }
    int  trajectoryIndex() const { return m_trajectoryIdx; }
    void setTrajectoryIndex(int idx) { m_trajectoryIdx = idx; }
    bool hasTrajectory() const { return !m_trajectory.isEmpty(); }

    // ── Room association ──
    QString roomId() const { return m_roomId; }
    void    setRoomId(const QString &id) { m_roomId = id; }

    // ── Custom properties ──
    QVariantMap properties() const { return m_properties; }
    void setProperties(const QVariantMap &props) { m_properties = props; }
    QVariant property(const QString &key) const { return m_properties.value(key); }
    void setProperty(const QString &key, const QVariant &val) { m_properties.insert(key, val); }

    // ── Serialization ──
    QVariantMap toVariantMap() const;
    static SimulationEntity fromVariantMap(const QVariantMap &data);

    // ── Step simulation for this entity ──
    void advanceTick(int currentTick);

private:
    QString                   m_id;
    Simulation::EntityType    m_type    = Simulation::EntityType::Smoke;
    Simulation::EntityState   m_state   = Simulation::EntityState::Idle;
    QPointF                   m_position;
    QPointF                   m_velocity;
    qreal                     m_direction  = 0.0;
    qreal                     m_speed      = 0.0;
    qreal                     m_radius     = 10.0;
    qreal                     m_intensity  = 1.0;
    int                       m_tickBorn   = 0;
    int                       m_tickExpiry = -1; // -1 = no expiry
    QVector<QPointF>          m_trajectory;
    int                       m_trajectoryIdx = 0;
    QString                   m_roomId;
    QVariantMap               m_properties;
};

#endif // SIMULATIONENTITY_H
