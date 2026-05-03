#ifndef SIMULATIONENGINE_H
#define SIMULATIONENGINE_H

#include "SimulationEnums.h"
#include "SimulationScenario.h"
#include "SimulationEntity.h"
#include "SimulationPropagation.h"
#include "SimulationResult.h"

#include <QObject>
#include <QVector>
#include <QHash>
#include <QPointF>
#include <QVariantMap>
#include <QVariantList>
#include <QTimer>

class FloorPlanModel;

// ─────────────────────────────────────────────────────
//  SimulationEngine — Moteur de simulation discret
//
//  Tick = 100ms simulé.  Gère :
//   • Scénarios (load / build)
//   • Entités (spawn / move / destroy)
//   • Propagation (grille 2D via SimulationPropagation)
//   • Triggers (capteurs, appareils)
//   • Causalité (event → consequence)
//   • Risques (probability × impact)
//   • Résultat (SimulationResult)
//
//  Thread: main (QML-bound via SimulationController).
// ─────────────────────────────────────────────────────
class SimulationEngine : public QObject
{
    Q_OBJECT

public:
    explicit SimulationEngine(QObject *parent = nullptr);
    ~SimulationEngine() override;

    // ── Setup ──
    void setFloorPlanModel(FloorPlanModel *model);
    void setWorldSize(int width, int height);

    // ── Scenario ──
    void loadScenario(const SimulationScenario &scenario);
    const SimulationScenario &currentScenario() const { return m_scenario; }

    // ── Execution ──
    void runStep();
    void runUntilComplete();
    void reset();

    // ── State ──
    Simulation::SimState state() const { return m_state; }
    int currentTick() const { return m_currentTick; }

    // ── Entities ──
    const QVector<SimulationEntity> &entities() const { return m_entities; }
    void spawnEntity(const SimulationEntity &entity);
    void removeEntity(const QString &entityId);

    // ── Results ──
    const SimulationResult &result() const { return m_result; }
    SimulationResult &result() { return m_result; }

    // ── Propagation access ──
    const SimulationPropagation &propagation() const { return m_propagation; }

    // ── Export for QML ──
    QVariantList entitiesState() const;
    QVariantList eventsAtTick(int tick) const;
    QVariantList currentHeatmap(const QString &type) const;
    QVariantList currentTrajectories() const;
    QVariantList currentRisks() const;
    QVariantMap  causalGraph() const;

signals:
    void stateChanged(Simulation::SimState state);
    void tickAdvanced(int tick);
    void entitySpawned(const QVariantMap &entity);
    void entityRemoved(const QString &entityId);
    void sensorTriggered(const QString &sensorId, int tick, const QVariantMap &data);
    void deviceActivated(const QString &deviceId, int tick, const QString &action);
    void riskDetected(const QVariantMap &risk);
    void causalLinkAdded(const QVariantMap &link);
    void simulationCompleted(const QVariantMap &summary);
    void propagationUpdated();

private:
    // ── Internal steps ──
    void buildObstaclesFromFloorPlan();
    void initEntitiesFromScenario();
    void stepEntities();
    void stepPropagation();
    void stepTriggers();
    void stepRisks();
    void checkCompletion();
    void recordSnapshot();

    // ── Trigger evaluation ──
    void evaluateTrigger(const SimulationTrigger &trigger);
    bool matchDevicePattern(const QString &pattern, const QString &deviceId) const;
    double proximityToEntity(const QPointF &sensorPos, Simulation::EntityType entityType) const;

    // ── Causal helpers ──
    void addCausal(const QString &fromId, Simulation::CausalNodeType fromType, const QString &fromLabel,
                   const QString &toId, Simulation::CausalNodeType toType, const QString &toLabel,
                   const QString &relation);

    // ── State ──
    Simulation::SimState         m_state = Simulation::SimState::Idle;
    int                          m_currentTick = 0;
    SimulationScenario           m_scenario;
    QVector<SimulationEntity>    m_entities;
    SimulationPropagation        m_propagation;
    SimulationResult             m_result;
    FloorPlanModel              *m_floorPlan = nullptr;
    int                          m_worldWidth  = 800;
    int                          m_worldHeight = 600;

    // Trigger state: track which triggers have fired
    QHash<QString, bool>         m_firedTriggers;
    // Sensor positions (from floor plan)
    QHash<QString, QPointF>      m_sensorPositions;
    QHash<QString, QString>      m_sensorTypes;
    // Snapshot every N ticks
    int                          m_snapshotInterval = 10;
};

#endif // SIMULATIONENGINE_H
