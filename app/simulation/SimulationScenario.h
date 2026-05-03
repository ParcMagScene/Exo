#ifndef SIMULATIONSCENARIO_H
#define SIMULATIONSCENARIO_H

#include "SimulationEnums.h"
#include "SimulationEntity.h"

#include <QObject>
#include <QPointF>
#include <QString>
#include <QVariantMap>
#include <QVector>
#include <QJsonObject>
#include <QJsonArray>

// ─────────────────────────────────────────────────────
//  SimulationTrigger — Déclencheur de capteur/appareil
// ─────────────────────────────────────────────────────
struct SimulationTrigger
{
    QString deviceId;         // capteur ou appareil
    QString condition;        // "proximity", "threshold", "timer"
    double  threshold = 0.0;
    int     delayTicks = 0;   // délai avant activation
    QString action;           // "alert", "activate", "deactivate", "lock", "unlock"
    QVariantMap parameters;

    QVariantMap toVariantMap() const;
    static SimulationTrigger fromVariantMap(const QVariantMap &data);
};

// ─────────────────────────────────────────────────────
//  SimulationScenario — Description complète d'un scénario
//
//  Incendie, intrusion, blackout, inondation, custom.
//  Contient :
//   • type et paramètres
//   • position et pièce de départ
//   • entités initiales
//   • triggers (capteurs/appareils)
//   • durée max
// ─────────────────────────────────────────────────────
class SimulationScenario
{
public:
    SimulationScenario();
    explicit SimulationScenario(Simulation::ScenarioType type);

    // ── Identity ──
    QString id() const { return m_id; }
    void    setId(const QString &id) { m_id = id; }

    QString name() const { return m_name; }
    void    setName(const QString &name) { m_name = name; }

    QString description() const { return m_description; }
    void    setDescription(const QString &desc) { m_description = desc; }

    // ── Type ──
    Simulation::ScenarioType type() const { return m_type; }
    void setType(Simulation::ScenarioType t) { m_type = t; }

    // ── Start conditions ──
    QPointF startPosition() const { return m_startPosition; }
    void    setStartPosition(const QPointF &pos) { m_startPosition = pos; }

    QString startRoomId() const { return m_startRoomId; }
    void    setStartRoomId(const QString &id) { m_startRoomId = id; }

    // ── Parameters ──
    double propagationSpeed() const { return m_propagationSpeed; }
    void   setPropagationSpeed(double s) { m_propagationSpeed = s; }

    double intensity() const { return m_intensity; }
    void   setIntensity(double i) { m_intensity = i; }

    int maxDurationTicks() const { return m_maxDurationTicks; }
    void setMaxDurationTicks(int ticks) { m_maxDurationTicks = ticks; }

    QVariantMap parameters() const { return m_parameters; }
    void setParameters(const QVariantMap &params) { m_parameters = params; }

    // ── Initial entities ──
    QVector<SimulationEntity> initialEntities() const { return m_initialEntities; }
    void setInitialEntities(const QVector<SimulationEntity> &entities) { m_initialEntities = entities; }
    void addInitialEntity(const SimulationEntity &e) { m_initialEntities.append(e); }

    // ── Triggers ──
    QVector<SimulationTrigger> triggers() const { return m_triggers; }
    void setTriggers(const QVector<SimulationTrigger> &triggers) { m_triggers = triggers; }
    void addTrigger(const SimulationTrigger &t) { m_triggers.append(t); }

    // ── Serialization ──
    QJsonObject toJson() const;
    static SimulationScenario fromJson(const QJsonObject &obj);
    QVariantMap toVariantMap() const;

    // ── Factory — scénarios prédéfinis ──
    static SimulationScenario createFireScenario(const QPointF &origin, const QString &roomId);
    static SimulationScenario createIntrusionScenario(const QPointF &entry, const QVector<QPointF> &path);
    static SimulationScenario createBlackoutScenario();
    static SimulationScenario createNetworkFailureScenario();
    static SimulationScenario createFloodScenario(const QPointF &origin, const QString &roomId);

private:
    QString                      m_id;
    QString                      m_name;
    QString                      m_description;
    Simulation::ScenarioType     m_type = Simulation::ScenarioType::Custom;
    QPointF                      m_startPosition;
    QString                      m_startRoomId;
    double                       m_propagationSpeed = Simulation::kDefaultPropagSpeed;
    double                       m_intensity = 1.0;
    int                          m_maxDurationTicks = 3000; // 5 min
    QVariantMap                  m_parameters;
    QVector<SimulationEntity>    m_initialEntities;
    QVector<SimulationTrigger>   m_triggers;
};

#endif // SIMULATIONSCENARIO_H
