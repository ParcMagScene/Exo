#include "SimulationEngine.h"
#include "FloorPlanModel.h"

#include <QUuid>
#include <QtMath>
#include <QDebug>

// ═════════════════════════════════════════════════════
//  SimulationEngine — Implémentation
// ═════════════════════════════════════════════════════

SimulationEngine::SimulationEngine(QObject *parent)
    : QObject(parent)
{
}

SimulationEngine::~SimulationEngine() = default;

// ─────────────────────────────────────────────────────
//  Setup
// ─────────────────────────────────────────────────────

void SimulationEngine::setFloorPlanModel(FloorPlanModel *model)
{
    m_floorPlan = model;
}

void SimulationEngine::setWorldSize(int width, int height)
{
    m_worldWidth  = width;
    m_worldHeight = height;
}

// ─────────────────────────────────────────────────────
//  Scenario
// ─────────────────────────────────────────────────────

void SimulationEngine::loadScenario(const SimulationScenario &scenario)
{
    reset();
    m_scenario = scenario;

    // Initialize propagation grid
    m_propagation.initialize(m_worldWidth, m_worldHeight, 10);

    // Build obstacles from floor plan
    buildObstaclesFromFloorPlan();

    // Create initial entities
    initEntitiesFromScenario();

    m_state = Simulation::SimState::Idle;
    emit stateChanged(m_state);
}

// ─────────────────────────────────────────────────────
//  Execution
// ─────────────────────────────────────────────────────

void SimulationEngine::runStep()
{
    if (m_state == Simulation::SimState::Completed ||
        m_state == Simulation::SimState::Aborted)
        return;

    if (m_state == Simulation::SimState::Idle)
        m_state = Simulation::SimState::Running;

    m_currentTick++;

    // 1) Advance entities (movement, spreading)
    stepEntities();

    // 2) Propagation (smoke, heat, water, etc.)
    stepPropagation();

    // 3) Check triggers (sensor → events)
    stepTriggers();

    // 4) Evaluate risks
    stepRisks();

    // 5) Snapshot
    if (m_currentTick % m_snapshotInterval == 0)
        recordSnapshot();

    // 6) Check completion
    checkCompletion();

    emit tickAdvanced(m_currentTick);
    emit propagationUpdated();
}

void SimulationEngine::runUntilComplete()
{
    int maxTicks = m_scenario.maxDurationTicks();
    while (m_state != Simulation::SimState::Completed &&
           m_state != Simulation::SimState::Aborted &&
           m_currentTick < maxTicks) {
        runStep();
    }
}

void SimulationEngine::reset()
{
    m_state       = Simulation::SimState::Idle;
    m_currentTick = 0;
    m_entities.clear();
    m_propagation.clear();
    m_result.clear();
    m_firedTriggers.clear();
    m_sensorPositions.clear();
    m_sensorTypes.clear();
    emit stateChanged(m_state);
}

// ─────────────────────────────────────────────────────
//  Entity management
// ─────────────────────────────────────────────────────

void SimulationEngine::spawnEntity(const SimulationEntity &entity)
{
    if (m_entities.size() >= Simulation::kMaxEntities) return;
    SimulationEntity e = entity;
    e.setTickBorn(m_currentTick);
    m_entities.append(e);

    auto data = e.toVariantMap();
    emit entitySpawned(data);

    SimEvent ev;
    ev.tick        = m_currentTick;
    ev.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
    ev.type        = "entity_spawned";
    ev.sourceId    = e.id();
    ev.description = QString("Entité %1 créée").arg(static_cast<int>(e.type()));
    ev.position    = e.position();
    ev.severity    = Simulation::Severity::Info;
    m_result.addEvent(ev);
}

void SimulationEngine::removeEntity(const QString &entityId)
{
    for (int i = 0; i < m_entities.size(); ++i) {
        if (m_entities[i].id() == entityId) {
            m_entities.removeAt(i);
            emit entityRemoved(entityId);
            return;
        }
    }
}

// ─────────────────────────────────────────────────────
//  Build obstacles from FloorPlan
// ─────────────────────────────────────────────────────

void SimulationEngine::buildObstaclesFromFloorPlan()
{
    if (!m_floorPlan) return;

    QVector<Obstacle> obstacles;
    auto ids = m_floorPlan->getItemIds();

    for (const auto &id : ids) {
        auto data = m_floorPlan->getItemData(id);
        QString type = data.value("type").toString();
        QPointF pos  = data.value("position").toPointF();
        QSizeF  sz   = data.value("size").toSizeF();

        if (type == "wall") {
            obstacles.append({QRectF(pos, sz), "wall", 0.0});
        } else if (type == "door") {
            obstacles.append({QRectF(pos, sz), "door", 0.6});
        } else if (type == "window") {
            obstacles.append({QRectF(pos, sz), "window", 0.3});
        } else if (type == "furniture") {
            obstacles.append({QRectF(pos, sz), "furniture", 0.0});
        }

        // Track sensors and cameras for trigger evaluation
        if (type == "sensor" || type == "camera") {
            m_sensorPositions[id] = QPointF(pos.x() + sz.width() / 2, pos.y() + sz.height() / 2);
            m_sensorTypes[id]     = data.value("properties").toMap().value("sensorType", type).toString();
        }
        if (type == "device") {
            m_sensorPositions[id] = QPointF(pos.x() + sz.width() / 2, pos.y() + sz.height() / 2);
            m_sensorTypes[id]     = "device";
        }
    }

    m_propagation.setObstacles(obstacles);
}

// ─────────────────────────────────────────────────────
//  Init entities from scenario
// ─────────────────────────────────────────────────────

void SimulationEngine::initEntitiesFromScenario()
{
    for (const auto &e : m_scenario.initialEntities()) {
        spawnEntity(e);
    }
}

// ─────────────────────────────────────────────────────
//  Step: Entities
// ─────────────────────────────────────────────────────

void SimulationEngine::stepEntities()
{
    for (auto &entity : m_entities) {
        if (entity.state() == Simulation::EntityState::Destroyed)
            continue;

        entity.advanceTick(m_currentTick);

        // Spreading entities inject into propagation grid
        if (entity.state() == Simulation::EntityState::Spreading) {
            switch (entity.type()) {
            case Simulation::EntityType::Smoke:
                m_propagation.injectSmoke(entity.position(), entity.intensity() * 0.08);
                break;
            case Simulation::EntityType::Heat:
                m_propagation.injectHeat(entity.position(), entity.intensity() * 0.06);
                break;
            case Simulation::EntityType::Water:
                m_propagation.injectWater(entity.position(), entity.intensity() * 0.05);
                break;
            default:
                break;
            }
        }
    }

    // Remove destroyed entities
    m_entities.erase(
        std::remove_if(m_entities.begin(), m_entities.end(),
            [](const SimulationEntity &e) {
                return e.state() == Simulation::EntityState::Destroyed;
            }),
        m_entities.end()
    );
}

// ─────────────────────────────────────────────────────
//  Step: Propagation
// ─────────────────────────────────────────────────────

void SimulationEngine::stepPropagation()
{
    double speed = m_scenario.propagationSpeed();

    // Smoke diffusion
    m_propagation.propagateSmoke(speed, Simulation::kDefaultAttenuation);

    // Heat: conduction + convection
    m_propagation.propagateHeat(speed * 0.5, speed * 0.3, Simulation::kDefaultAttenuation * 0.8);

    // Water
    m_propagation.propagateWater(speed * 0.6, Simulation::kDefaultAttenuation * 0.5);

    // Noise: from active noise entities
    for (const auto &e : m_entities) {
        if (e.type() == Simulation::EntityType::Noise && e.state() != Simulation::EntityState::Destroyed)
            m_propagation.propagateNoise(e.position(), e.intensity(), 0.02);
    }

    // Light: from active light entities
    for (const auto &e : m_entities) {
        if (e.type() == Simulation::EntityType::Light && e.state() != Simulation::EntityState::Destroyed) {
            double angle = e.direction();
            double fov   = e.property("fov").toDouble();
            if (fov <= 0) fov = 90.0;
            m_propagation.propagateLight(e.position(), angle, fov, e.intensity());
        }
    }
}

// ─────────────────────────────────────────────────────
//  Step: Triggers
// ─────────────────────────────────────────────────────

void SimulationEngine::stepTriggers()
{
    for (const auto &trigger : m_scenario.triggers()) {
        // Check delay
        if (m_currentTick < trigger.delayTicks) continue;

        evaluateTrigger(trigger);
    }
}

void SimulationEngine::evaluateTrigger(const SimulationTrigger &trigger)
{
    // Iterate over sensors matching the pattern
    for (auto it = m_sensorPositions.constBegin(); it != m_sensorPositions.constEnd(); ++it) {
        QString sensorId = it.key();
        QPointF sensorPos = it.value();

        if (!matchDevicePattern(trigger.deviceId, sensorId))
            continue;

        QString triggerKey = trigger.deviceId + "_" + sensorId;
        if (m_firedTriggers.value(triggerKey, false))
            continue;

        bool fired = false;

        if (trigger.condition == "threshold") {
            // Check propagation level at sensor
            double level = 0.0;
            level = qMax(level, m_propagation.smokeLevelAt(sensorPos));
            level = qMax(level, m_propagation.heatLevelAt(sensorPos));
            level = qMax(level, m_propagation.waterLevelAt(sensorPos));
            fired = (level >= trigger.threshold);
        }
        else if (trigger.condition == "proximity") {
            // Check proximity to any moving entity
            double minDist = 1e9;
            for (const auto &e : m_entities) {
                if (e.type() == Simulation::EntityType::Intruder ||
                    e.type() == Simulation::EntityType::Robot) {
                    double dx = e.position().x() - sensorPos.x();
                    double dy = e.position().y() - sensorPos.y();
                    double dist = std::sqrt(dx * dx + dy * dy);
                    minDist = qMin(minDist, dist);
                }
            }
            fired = (minDist <= trigger.threshold);
        }
        else if (trigger.condition == "timer") {
            fired = (m_currentTick >= trigger.delayTicks);
        }

        if (fired) {
            m_firedTriggers[triggerKey] = true;

            // Record event
            SimEvent ev;
            ev.tick        = m_currentTick;
            ev.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
            ev.type        = "sensor_triggered";
            ev.sourceId    = sensorId;
            ev.description = QString("Capteur %1 déclenché → %2").arg(sensorId, trigger.action);
            ev.position    = sensorPos;
            ev.severity    = Simulation::Severity::Warning;
            ev.data        = trigger.parameters;
            m_result.addEvent(ev);
            m_result.addTriggeredSensor(sensorId, m_currentTick);

            emit sensorTriggered(sensorId, m_currentTick, trigger.parameters);

            // Device activation event
            SimEvent devEv;
            devEv.tick        = m_currentTick;
            devEv.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
            devEv.type        = "device_activated";
            devEv.sourceId    = sensorId;
            devEv.description = QString("Action: %1 sur %2").arg(trigger.action, sensorId);
            devEv.position    = sensorPos;
            devEv.severity    = Simulation::Severity::Info;
            m_result.addEvent(devEv);
            m_result.addActivatedDevice(sensorId, m_currentTick, trigger.action);

            emit deviceActivated(sensorId, m_currentTick, trigger.action);

            // Causal link: scenario source → sensor trigger
            addCausal(
                m_scenario.id(), Simulation::CausalNodeType::Event, m_scenario.name(),
                sensorId, Simulation::CausalNodeType::Sensor, QString("Capteur %1").arg(sensorId),
                "triggers"
            );
            addCausal(
                sensorId, Simulation::CausalNodeType::Sensor, QString("Capteur %1").arg(sensorId),
                sensorId + "_action", Simulation::CausalNodeType::Device, trigger.action,
                "activates"
            );
        }
    }
}

bool SimulationEngine::matchDevicePattern(const QString &pattern, const QString &deviceId) const
{
    // Simple wildcard: "smoke_detector_*" matches "smoke_detector_1"
    if (pattern.endsWith('*')) {
        QString prefix = pattern.left(pattern.length() - 1);
        return deviceId.startsWith(prefix);
    }
    return pattern == deviceId;
}

double SimulationEngine::proximityToEntity(const QPointF &sensorPos, Simulation::EntityType entityType) const
{
    double minDist = 1e9;
    for (const auto &e : m_entities) {
        if (e.type() != entityType) continue;
        double dx = e.position().x() - sensorPos.x();
        double dy = e.position().y() - sensorPos.y();
        minDist = qMin(minDist, std::sqrt(dx * dx + dy * dy));
    }
    return minDist;
}

// ─────────────────────────────────────────────────────
//  Step: Risks
// ─────────────────────────────────────────────────────

void SimulationEngine::stepRisks()
{
    // Evaluate risks every 20 ticks
    if (m_currentTick % 20 != 0) return;

    auto scenarioType = m_scenario.type();

    // Fire risks
    if (scenarioType == Simulation::ScenarioType::Fire) {
        // Check max smoke/heat levels
        double maxSmoke = 0.0, maxHeat = 0.0;
        for (int x = 0; x < m_propagation.gridWidth(); ++x) {
            for (int y = 0; y < m_propagation.gridHeight(); ++y) {
                const auto &cell = m_propagation.cellAt(x, y);
                maxSmoke = qMax(maxSmoke, cell.smokeLevel);
                maxHeat  = qMax(maxHeat, cell.heatLevel);
            }
        }

        if (maxSmoke > 0.5) {
            SimRisk risk;
            risk.id             = "risk_smoke_hazard";
            risk.label          = "Fumée dangereuse";
            risk.probability    = qMin(1.0, maxSmoke);
            risk.impact         = 0.8;
            risk.zone           = m_scenario.startRoomId();
            risk.category       = "fire";
            risk.recommendation = "Évacuation immédiate, ventilation d'urgence";
            risk.detectedAtTick = m_currentTick;
            risk.severity       = Simulation::Severity::Critical;
            m_result.addRisk(risk);
            emit riskDetected(risk.toVariantMap());
        }

        if (maxHeat > 0.6) {
            SimRisk risk;
            risk.id             = "risk_heat_danger";
            risk.label          = "Chaleur extrême";
            risk.probability    = qMin(1.0, maxHeat);
            risk.impact         = 0.9;
            risk.zone           = m_scenario.startRoomId();
            risk.category       = "fire";
            risk.recommendation = "Coupure électrique, appel pompiers";
            risk.detectedAtTick = m_currentTick;
            risk.severity       = Simulation::Severity::Critical;
            m_result.addRisk(risk);
            emit riskDetected(risk.toVariantMap());
        }
    }

    // Intrusion risks
    if (scenarioType == Simulation::ScenarioType::Intrusion) {
        for (const auto &e : m_entities) {
            if (e.type() != Simulation::EntityType::Intruder) continue;

            SimRisk risk;
            risk.id             = "risk_intrusion_" + e.id();
            risk.label          = "Intrus détecté";
            risk.probability    = 0.95;
            risk.impact         = 0.7;
            risk.zone           = e.roomId();
            risk.category       = "security";
            risk.recommendation = "Verrouillage périmètre, alerte sécurité";
            risk.detectedAtTick = m_currentTick;
            risk.severity       = Simulation::Severity::High;
            m_result.addRisk(risk);
            emit riskDetected(risk.toVariantMap());
        }
    }

    // Flood risks
    if (scenarioType == Simulation::ScenarioType::Flood) {
        double maxWater = 0.0;
        for (int x = 0; x < m_propagation.gridWidth(); ++x)
            for (int y = 0; y < m_propagation.gridHeight(); ++y)
                maxWater = qMax(maxWater, m_propagation.cellAt(x, y).waterLevel);

        if (maxWater > 0.3) {
            SimRisk risk;
            risk.id             = "risk_flood_damage";
            risk.label          = "Dégâts des eaux";
            risk.probability    = qMin(1.0, maxWater);
            risk.impact         = 0.6;
            risk.zone           = m_scenario.startRoomId();
            risk.category       = "flood";
            risk.recommendation = "Fermer la vanne principale, protéger les équipements";
            risk.detectedAtTick = m_currentTick;
            risk.severity       = maxWater > 0.7 ? Simulation::Severity::Critical : Simulation::Severity::High;
            m_result.addRisk(risk);
            emit riskDetected(risk.toVariantMap());
        }
    }

    // Blackout / Network — time-based risks
    if (scenarioType == Simulation::ScenarioType::Blackout && m_currentTick > 100) {
        SimRisk risk;
        risk.id             = "risk_data_loss";
        risk.label          = "Perte de données possible";
        risk.probability    = qMin(1.0, m_currentTick / 600.0);
        risk.impact         = 0.8;
        risk.category       = "infrastructure";
        risk.recommendation = "Basculer sur UPS, sauvegarder état";
        risk.detectedAtTick = m_currentTick;
        risk.severity       = Simulation::Severity::High;
        m_result.addRisk(risk);
        emit riskDetected(risk.toVariantMap());
    }

    if (scenarioType == Simulation::ScenarioType::NetworkFailure && m_currentTick > 50) {
        SimRisk risk;
        risk.id             = "risk_connectivity_loss";
        risk.label          = "Perte de connectivité prolongée";
        risk.probability    = 0.9;
        risk.impact         = 0.5;
        risk.category       = "network";
        risk.recommendation = "Activer mode hors-ligne, file d'attente locale";
        risk.detectedAtTick = m_currentTick;
        risk.severity       = Simulation::Severity::Warning;
        m_result.addRisk(risk);
        emit riskDetected(risk.toVariantMap());
    }
}

// ─────────────────────────────────────────────────────
//  Completion check
// ─────────────────────────────────────────────────────

void SimulationEngine::checkCompletion()
{
    if (m_currentTick >= m_scenario.maxDurationTicks()) {
        m_state = Simulation::SimState::Completed;
        m_result.setTotalTicks(m_currentTick);
        emit stateChanged(m_state);
        emit simulationCompleted(m_result.toVariantMap());
        return;
    }

    // Check if all entities are destroyed/fading
    bool allDone = true;
    for (const auto &e : m_entities) {
        if (e.state() != Simulation::EntityState::Destroyed &&
            e.state() != Simulation::EntityState::Fading &&
            e.state() != Simulation::EntityState::Idle) {
            allDone = false;
            break;
        }
    }

    // For path-based scenarios: intruder reached end
    if (allDone && !m_entities.isEmpty() && m_currentTick > 10) {
        m_state = Simulation::SimState::Completed;
        m_result.setTotalTicks(m_currentTick);
        emit stateChanged(m_state);
        emit simulationCompleted(m_result.toVariantMap());
    }
}

// ─────────────────────────────────────────────────────
//  Snapshot
// ─────────────────────────────────────────────────────

void SimulationEngine::recordSnapshot()
{
    TickSnapshot snap;
    snap.tick     = m_currentTick;
    snap.entities = m_entities;

    // Collect events for this range
    for (const auto &ev : m_result.events()) {
        if (ev.tick > m_currentTick - m_snapshotInterval && ev.tick <= m_currentTick)
            snap.events.append(ev);
    }

    m_result.addSnapshot(snap);
}

// ─────────────────────────────────────────────────────
//  Causal helpers
// ─────────────────────────────────────────────────────

void SimulationEngine::addCausal(
    const QString &fromId, Simulation::CausalNodeType fromType, const QString &fromLabel,
    const QString &toId,   Simulation::CausalNodeType toType,   const QString &toLabel,
    const QString &relation)
{
    CausalNode from;
    from.id    = fromId;
    from.type  = fromType;
    from.label = fromLabel;
    from.tick  = m_currentTick;
    m_result.addCausalNode(from);

    CausalNode to;
    to.id    = toId;
    to.type  = toType;
    to.label = toLabel;
    to.tick  = m_currentTick;
    m_result.addCausalNode(to);

    CausalLink link;
    link.fromId   = fromId;
    link.toId     = toId;
    link.relation = relation;
    link.weight   = 1.0;
    link.tick     = m_currentTick;
    m_result.addCausalLink(link);

    emit causalLinkAdded(link.toVariantMap());
}

// ─────────────────────────────────────────────────────
//  QML export
// ─────────────────────────────────────────────────────

QVariantList SimulationEngine::entitiesState() const
{
    QVariantList list;
    for (const auto &e : m_entities)
        list.append(e.toVariantMap());
    return list;
}

QVariantList SimulationEngine::eventsAtTick(int tick) const
{
    QVariantList list;
    for (const auto &ev : m_result.events()) {
        if (ev.tick == tick)
            list.append(ev.toVariantMap());
    }
    return list;
}

QVariantList SimulationEngine::currentHeatmap(const QString &type) const
{
    QVariantList list;
    QVector<QVariantMap> data;

    if (type == "smoke")
        data = m_propagation.smokeHeatmap();
    else if (type == "heat")
        data = m_propagation.heatHeatmap();
    else if (type == "water")
        data = m_propagation.waterHeatmap();

    for (const auto &d : data)
        list.append(d);
    return list;
}

QVariantList SimulationEngine::currentTrajectories() const
{
    QVariantList list;
    for (const auto &e : m_entities) {
        if (!e.hasTrajectory()) continue;

        QVariantList points;
        for (const auto &p : e.trajectory())
            points.append(QVariantMap{{"x", p.x()}, {"y", p.y()}});

        QString color;
        switch (e.type()) {
        case Simulation::EntityType::Intruder: color = "#F44747"; break;
        case Simulation::EntityType::Robot:    color = "#569CD6"; break;
        default: color = "#D4D4D4"; break;
        }

        list.append(QVariantMap{
            {"entityId", e.id()},
            {"points",   points},
            {"color",    color},
            {"currentIndex", e.trajectoryIndex()}
        });
    }
    return list;
}

QVariantList SimulationEngine::currentRisks() const
{
    return m_result.risksToVariantList();
}

QVariantMap SimulationEngine::causalGraph() const
{
    return {
        {"nodes", m_result.causalNodesToVariantList()},
        {"links", m_result.causalLinksToVariantList()}
    };
}
