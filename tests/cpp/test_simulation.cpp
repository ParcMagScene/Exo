// ═══════════════════════════════════════════════════════
//  Test unitaire — Module de simulation spatiale
//  Vérifie : Entity, Scenario, Propagation, Result, Engine
// ═══════════════════════════════════════════════════════
#include <QtTest/QtTest>
#include <QSignalSpy>

#include "SimulationEnums.h"
#include "SimulationEntity.h"
#include "SimulationScenario.h"
#include "SimulationPropagation.h"
#include "SimulationResult.h"
#include "SimulationEngine.h"

using namespace Simulation;

class TestSimulation : public QObject
{
    Q_OBJECT

private slots:

    // ═════════════════════════════════════════════════
    //  SimulationEntity
    // ═════════════════════════════════════════════════

    void entity_defaultConstruction()
    {
        SimulationEntity e;
        QCOMPARE(e.type(), EntityType::Smoke);
        QCOMPARE(e.state(), EntityState::Idle);
        QCOMPARE(e.position(), QPointF(0, 0));
        QCOMPARE(e.speed(), 0.0);
        QCOMPARE(e.radius(), 10.0);
        QCOMPARE(e.intensity(), 1.0);
        QCOMPARE(e.tickExpiry(), -1);
        QVERIFY(!e.id().isEmpty());
    }

    void entity_typedConstruction()
    {
        SimulationEntity e(EntityType::Intruder);
        QCOMPARE(e.type(), EntityType::Intruder);
        QVERIFY(!e.id().isEmpty());
    }

    void entity_settersGetters()
    {
        SimulationEntity e;
        e.setPosition(QPointF(100, 200));
        e.setVelocity(QPointF(1.5, -0.5));
        e.setDirection(45.0);
        e.setSpeed(3.0);
        e.setRadius(25.0);
        e.setIntensity(0.8);
        e.setTickBorn(10);
        e.setTickExpiry(100);
        e.setRoomId("salon");
        e.setProperty("custom_key", 42);

        QCOMPARE(e.position(), QPointF(100, 200));
        QCOMPARE(e.velocity(), QPointF(1.5, -0.5));
        QCOMPARE(e.direction(), 45.0);
        QCOMPARE(e.speed(), 3.0);
        QCOMPARE(e.radius(), 25.0);
        QCOMPARE(e.intensity(), 0.8);
        QCOMPARE(e.tickBorn(), 10);
        QCOMPARE(e.tickExpiry(), 100);
        QCOMPARE(e.roomId(), QString("salon"));
        QCOMPARE(e.property("custom_key").toInt(), 42);
    }

    void entity_isExpired()
    {
        SimulationEntity e;
        // No expiry → never expired
        e.setTickExpiry(-1);
        QVERIFY(!e.isExpired(9999));

        // Expiry at tick 50
        e.setTickExpiry(50);
        QVERIFY(!e.isExpired(49));
        QVERIFY(e.isExpired(50));
        QVERIFY(e.isExpired(100));
    }

    void entity_advanceTick_velocity()
    {
        SimulationEntity e;
        e.setPosition(QPointF(10, 20));
        e.setVelocity(QPointF(2.0, 3.0));
        e.setState(EntityState::Active);

        e.advanceTick(1);
        // Position should have advanced by velocity
        QVERIFY(qAbs(e.position().x() - 12.0) < 0.01);
        QVERIFY(qAbs(e.position().y() - 23.0) < 0.01);
    }

    void entity_advanceTick_trajectory()
    {
        SimulationEntity e(EntityType::Intruder);
        e.setPosition(QPointF(0, 0));
        e.setTrajectory({QPointF(0, 0), QPointF(10, 10), QPointF(20, 20)});
        e.setTrajectoryIndex(0);
        e.setState(EntityState::Moving);

        // First advance: already at waypoint 0 → snaps, idx advances to 1
        e.advanceTick(1);
        QCOMPARE(e.trajectoryIndex(), 1);
        QCOMPARE(e.position(), QPointF(0, 0)); // was at waypoint 0, snapped

        // Subsequent advances: moves gradually towards waypoint 1
        for (int t = 2; t < 20; ++t)
            e.advanceTick(t);
        // After many steps, should be closer to (10,10)
        QVERIFY(e.position().x() > 0.0);
        QVERIFY(e.position().y() > 0.0);
    }

    void entity_toVariantMap_roundTrip()
    {
        SimulationEntity orig(EntityType::Robot);
        orig.setPosition(QPointF(42.5, 77.3));
        orig.setVelocity(QPointF(1.0, -1.0));
        orig.setDirection(90.0);
        orig.setSpeed(5.0);
        orig.setRadius(15.0);
        orig.setIntensity(0.5);
        orig.setTickBorn(3);
        orig.setTickExpiry(200);
        orig.setRoomId("cuisine");
        orig.setState(EntityState::Moving);
        orig.setProperty("tag", "patrol");

        QVariantMap map = orig.toVariantMap();
        QVERIFY(!map.isEmpty());

        SimulationEntity restored = SimulationEntity::fromVariantMap(map);
        QCOMPARE(restored.id(), orig.id());
        QCOMPARE(restored.type(), orig.type());
        QCOMPARE(restored.state(), orig.state());
        QCOMPARE(restored.position(), orig.position());
        QCOMPARE(restored.speed(), orig.speed());
        QCOMPARE(restored.radius(), orig.radius());
        QCOMPARE(restored.intensity(), orig.intensity());
        QCOMPARE(restored.tickBorn(), orig.tickBorn());
        QCOMPARE(restored.tickExpiry(), orig.tickExpiry());
        QCOMPARE(restored.roomId(), orig.roomId());
    }

    // ═════════════════════════════════════════════════
    //  SimulationScenario
    // ═════════════════════════════════════════════════

    void scenario_defaultConstruction()
    {
        SimulationScenario s;
        QCOMPARE(s.type(), ScenarioType::Custom);
        QCOMPARE(s.propagationSpeed(), kDefaultPropagSpeed);
        QCOMPARE(s.intensity(), 1.0);
        QCOMPARE(s.maxDurationTicks(), 3000);
        QVERIFY(s.initialEntities().isEmpty());
        QVERIFY(s.triggers().isEmpty());
    }

    void scenario_typedConstruction()
    {
        SimulationScenario s(ScenarioType::Fire);
        QCOMPARE(s.type(), ScenarioType::Fire);
    }

    void scenario_factoryFire()
    {
        auto s = SimulationScenario::createFireScenario(QPointF(100, 100), "salon");
        QCOMPARE(s.type(), ScenarioType::Fire);
        QCOMPARE(s.startPosition(), QPointF(100, 100));
        QCOMPARE(s.startRoomId(), QString("salon"));
        QVERIFY(!s.name().isEmpty());
        QVERIFY(!s.initialEntities().isEmpty());
    }

    void scenario_factoryIntrusion()
    {
        QVector<QPointF> path = {QPointF(0, 0), QPointF(50, 50), QPointF(100, 100)};
        auto s = SimulationScenario::createIntrusionScenario(QPointF(0, 0), path);
        QCOMPARE(s.type(), ScenarioType::Intrusion);
        QCOMPARE(s.startPosition(), QPointF(0, 0));
        QVERIFY(!s.initialEntities().isEmpty());
    }

    void scenario_factoryBlackout()
    {
        auto s = SimulationScenario::createBlackoutScenario();
        QCOMPARE(s.type(), ScenarioType::Blackout);
        QVERIFY(!s.name().isEmpty());
    }

    void scenario_factoryNetworkFailure()
    {
        auto s = SimulationScenario::createNetworkFailureScenario();
        QCOMPARE(s.type(), ScenarioType::NetworkFailure);
        QVERIFY(!s.name().isEmpty());
    }

    void scenario_factoryFlood()
    {
        auto s = SimulationScenario::createFloodScenario(QPointF(200, 300), "sdb");
        QCOMPARE(s.type(), ScenarioType::Flood);
        QCOMPARE(s.startRoomId(), QString("sdb"));
        QVERIFY(!s.initialEntities().isEmpty());
    }

    void scenario_jsonRoundTrip()
    {
        auto orig = SimulationScenario::createFireScenario(QPointF(50, 60), "chambre");
        orig.addTrigger(SimulationTrigger{"smoke_det_1", "threshold", 0.5, 0, "alert", {}});

        QJsonObject json = orig.toJson();
        QVERIFY(!json.isEmpty());

        auto restored = SimulationScenario::fromJson(json);
        QCOMPARE(restored.type(), orig.type());
        QCOMPARE(restored.name(), orig.name());
        QCOMPARE(restored.startPosition(), orig.startPosition());
        QCOMPARE(restored.startRoomId(), orig.startRoomId());
        QCOMPARE(restored.propagationSpeed(), orig.propagationSpeed());
        QCOMPARE(restored.intensity(), orig.intensity());
        QCOMPARE(restored.maxDurationTicks(), orig.maxDurationTicks());
        QCOMPARE(restored.triggers().size(), orig.triggers().size());
    }

    void scenario_triggers()
    {
        SimulationScenario s;
        SimulationTrigger t1{"sensor_1", "proximity", 2.0, 5, "alert", {}};
        SimulationTrigger t2{"cam_1", "threshold", 0.8, 0, "activate", {}};

        s.addTrigger(t1);
        s.addTrigger(t2);

        QCOMPARE(s.triggers().size(), 2);
        QCOMPARE(s.triggers().at(0).deviceId, QString("sensor_1"));
        QCOMPARE(s.triggers().at(1).deviceId, QString("cam_1"));
    }

    // ═════════════════════════════════════════════════
    //  SimulationPropagation
    // ═════════════════════════════════════════════════

    void propagation_initialize()
    {
        SimulationPropagation prop;
        prop.initialize(200, 100, 10);

        QCOMPARE(prop.gridWidth(), 20);
        QCOMPARE(prop.gridHeight(), 10);
        QCOMPARE(prop.cellSize(), 10);
    }

    void propagation_gridConversion()
    {
        SimulationPropagation prop;
        prop.initialize(200, 100, 10);

        QCOMPARE(prop.toGridX(55.0), 5);
        QCOMPARE(prop.toGridY(35.0), 3);
        QCOMPARE(prop.toWorldX(5), 55.0);
        QCOMPARE(prop.toWorldY(3), 35.0);
    }

    void propagation_injectSmoke()
    {
        SimulationPropagation prop;
        prop.initialize(200, 200, 10);

        prop.injectSmoke(QPointF(50, 50), 1.0);
        double level = prop.smokeLevelAt(QPointF(50, 50));
        QVERIFY(level > 0.0);
    }

    void propagation_injectHeat()
    {
        SimulationPropagation prop;
        prop.initialize(200, 200, 10);

        prop.injectHeat(QPointF(100, 100), 2.0);
        double level = prop.heatLevelAt(QPointF(100, 100));
        QVERIFY(level > 0.0);
    }

    void propagation_injectWater()
    {
        SimulationPropagation prop;
        prop.initialize(200, 200, 10);

        prop.injectWater(QPointF(75, 75), 1.5);
        double level = prop.waterLevelAt(QPointF(75, 75));
        QVERIFY(level > 0.0);
    }

    void propagation_smokeSpread()
    {
        SimulationPropagation prop;
        prop.initialize(200, 200, 10);

        prop.injectSmoke(QPointF(100, 100), 5.0);

        // After diffusion, neighbor cells should have picked up some smoke
        prop.propagateSmoke(1.0, 0.01);

        double centerLevel = prop.smokeLevelAt(QPointF(100, 100));
        double neighborLevel = prop.smokeLevelAt(QPointF(110, 100));
        QVERIFY(centerLevel > 0.0);
        QVERIFY(neighborLevel > 0.0);
        QVERIFY(centerLevel > neighborLevel);
    }

    void propagation_obstacle()
    {
        SimulationPropagation prop;
        prop.initialize(200, 200, 10);

        // Add a wall obstacle directly
        Obstacle wall;
        wall.rect = QRectF(90, 0, 20, 200);
        wall.type = "wall";
        wall.permeability = 0.0;
        prop.addObstacle(wall);

        // Cell at (100, 100) should fall within the wall
        int gx = prop.toGridX(100);
        int gy = prop.toGridY(100);
        const auto &cell = prop.cellAt(gx, gy);
        QVERIFY(cell.isObstacle);
    }

    void propagation_findPath_noObstacle()
    {
        SimulationPropagation prop;
        prop.initialize(200, 200, 10);

        QVector<QPointF> path = prop.findPath(QPointF(10, 10), QPointF(190, 190));
        // A* should find a path in an empty grid
        QVERIFY(!path.isEmpty());
        // First point should be near start, last near goal
        QVERIFY(path.first().x() <= 20.0);
        QVERIFY(path.last().x() >= 180.0);
    }

    void propagation_heatmap()
    {
        SimulationPropagation prop;
        prop.initialize(100, 100, 10);

        prop.injectSmoke(QPointF(50, 50), 3.0);
        QVector<QVariantMap> heatmap = prop.smokeHeatmap();
        // At least one cell should have non-zero value
        bool found = false;
        for (const auto &cell : heatmap) {
            if (cell.value("value").toDouble() > 0.0) {
                found = true;
                break;
            }
        }
        QVERIFY(found);
    }

    void propagation_clear()
    {
        SimulationPropagation prop;
        prop.initialize(200, 200, 10);
        prop.injectSmoke(QPointF(100, 100), 5.0);
        QVERIFY(prop.smokeLevelAt(QPointF(100, 100)) > 0.0);

        prop.clear();
        // After clear, grid should be reset
        // Re-initialize required → levels at 0
        prop.initialize(200, 200, 10);
        QCOMPARE(prop.smokeLevelAt(QPointF(100, 100)), 0.0);
    }

    // ═════════════════════════════════════════════════
    //  SimulationResult
    // ═════════════════════════════════════════════════

    void result_addEvent()
    {
        SimulationResult res;
        SimEvent evt;
        evt.tick = 5;
        evt.id = "evt_1";
        evt.type = "sensor_triggered";
        evt.description = "Détecteur fumée déclenché";
        evt.severity = Severity::Warning;

        res.addEvent(evt);
        QCOMPARE(res.events().size(), 1);
        QCOMPARE(res.events().first().id, QString("evt_1"));
    }

    void result_addRisk()
    {
        SimulationResult res;
        SimRisk risk;
        risk.id = "risk_1";
        risk.label = "Propagation incendie";
        risk.probability = 0.8;
        risk.impact = 0.9;
        risk.zone = "salon";
        risk.severity = Severity::Critical;

        res.addRisk(risk);
        QCOMPARE(res.risks().size(), 1);
        QVERIFY(qAbs(res.risks().first().score() - 0.72) < 0.01);
    }

    void result_causalGraph()
    {
        SimulationResult res;

        CausalNode n1;
        n1.id = "fire_start";
        n1.type = CausalNodeType::Event;
        n1.label = "Départ de feu";
        n1.tick = 0;

        CausalNode n2;
        n2.id = "smoke_detect";
        n2.type = CausalNodeType::Sensor;
        n2.label = "Détection fumée";
        n2.tick = 15;

        CausalLink link;
        link.fromId = "fire_start";
        link.toId = "smoke_detect";
        link.relation = "triggers";
        link.tick = 15;

        res.addCausalNode(n1);
        res.addCausalNode(n2);
        res.addCausalLink(link);

        QCOMPARE(res.causalNodes().size(), 2);
        QCOMPARE(res.causalLinks().size(), 1);
        QCOMPARE(res.causalLinks().first().relation, QString("triggers"));
    }

    void result_triggeredSensors()
    {
        SimulationResult res;
        res.addTriggeredSensor("smoke_1", 10);
        res.addTriggeredSensor("temp_1", 25);

        QCOMPARE(res.triggeredSensors().size(), 2);
    }

    void result_activatedDevices()
    {
        SimulationResult res;
        res.addActivatedDevice("alarm_1", 15, "activate");
        QCOMPARE(res.activatedDevices().size(), 1);
    }

    void result_impactedZones()
    {
        SimulationResult res;
        res.addImpactedZone("salon", "smoke", 0.85);
        res.addImpactedZone("cuisine", "heat", 0.6);
        QCOMPARE(res.impactedZones().size(), 2);
    }

    void result_exportVariantMap()
    {
        SimulationResult res;
        res.setTotalTicks(100);
        SimEvent evt;
        evt.tick = 1;
        evt.id = "e1";
        evt.type = "test";
        res.addEvent(evt);

        QVariantMap map = res.toVariantMap();
        QVERIFY(!map.isEmpty());
        QCOMPARE(map.value("totalTicks").toInt(), 100);
    }

    void result_clear()
    {
        SimulationResult res;
        SimEvent evt;
        evt.id = "e1";
        res.addEvent(evt);
        SimRisk risk;
        risk.id = "r1";
        res.addRisk(risk);

        res.clear();
        QCOMPARE(res.events().size(), 0);
        QCOMPARE(res.risks().size(), 0);
        QCOMPARE(res.causalNodes().size(), 0);
        QCOMPARE(res.causalLinks().size(), 0);
        QCOMPARE(res.totalTicks(), 0);
    }

    // ═════════════════════════════════════════════════
    //  SimulationEngine
    // ═════════════════════════════════════════════════

    void engine_initialState()
    {
        SimulationEngine engine;
        QCOMPARE(engine.state(), SimState::Idle);
        QCOMPARE(engine.currentTick(), 0);
        QVERIFY(engine.entities().isEmpty());
    }

    void engine_setWorldSize()
    {
        SimulationEngine engine;
        engine.setWorldSize(800, 600);
        // Grid is initialized on loadScenario, not setWorldSize alone
        SimulationScenario s(ScenarioType::Custom);
        s.setMaxDurationTicks(5);
        engine.loadScenario(s);
        QVERIFY(engine.propagation().gridWidth() > 0);
        QVERIFY(engine.propagation().gridHeight() > 0);
    }

    void engine_loadScenario()
    {
        SimulationEngine engine;
        engine.setWorldSize(400, 400);

        auto scenario = SimulationScenario::createFireScenario(QPointF(200, 200), "salon");
        engine.loadScenario(scenario);

        QCOMPARE(engine.currentScenario().type(), ScenarioType::Fire);
        QCOMPARE(engine.state(), SimState::Idle);
    }

    void engine_runStep_stateTransition()
    {
        SimulationEngine engine;
        engine.setWorldSize(400, 400);

        auto scenario = SimulationScenario::createFireScenario(QPointF(200, 200), "salon");
        engine.loadScenario(scenario);

        QSignalSpy stateSpy(&engine, &SimulationEngine::stateChanged);
        QSignalSpy tickSpy(&engine, &SimulationEngine::tickAdvanced);

        engine.runStep();
        QCOMPARE(engine.state(), SimState::Running);
        QCOMPARE(engine.currentTick(), 1);
        QVERIFY(tickSpy.count() >= 1);
    }

    void engine_multipleSteps()
    {
        SimulationEngine engine;
        engine.setWorldSize(400, 400);

        auto scenario = SimulationScenario::createFireScenario(QPointF(200, 200), "salon");
        engine.loadScenario(scenario);

        for (int i = 0; i < 10; ++i)
            engine.runStep();

        QCOMPARE(engine.currentTick(), 10);
        QCOMPARE(engine.state(), SimState::Running);
    }

    void engine_reset()
    {
        SimulationEngine engine;
        engine.setWorldSize(400, 400);

        auto scenario = SimulationScenario::createFireScenario(QPointF(200, 200), "salon");
        engine.loadScenario(scenario);

        engine.runStep();
        engine.runStep();
        QCOMPARE(engine.currentTick(), 2);

        engine.reset();
        QCOMPARE(engine.state(), SimState::Idle);
        QCOMPARE(engine.currentTick(), 0);
    }

    void engine_entitySpawn()
    {
        SimulationEngine engine;
        engine.setWorldSize(400, 400);

        auto scenario = SimulationScenario::createFireScenario(QPointF(200, 200), "salon");
        engine.loadScenario(scenario);

        QSignalSpy spawnSpy(&engine, &SimulationEngine::entitySpawned);

        SimulationEntity e(EntityType::Smoke);
        e.setPosition(QPointF(100, 100));
        e.setIntensity(1.0);
        engine.spawnEntity(e);

        QVERIFY(!engine.entities().isEmpty());
        QVERIFY(spawnSpy.count() >= 1);
    }

    void engine_entityRemoval()
    {
        SimulationEngine engine;
        engine.setWorldSize(400, 400);

        SimulationEntity e(EntityType::Robot);
        e.setPosition(QPointF(100, 100));
        QString eid = e.id();
        engine.spawnEntity(e);

        QVERIFY(!engine.entities().isEmpty());

        engine.removeEntity(eid);
        // Entity should no longer be in the list
        bool found = false;
        for (const auto &ent : engine.entities()) {
            if (ent.id() == eid) { found = true; break; }
        }
        QVERIFY(!found);
    }

    void engine_entitiesState_export()
    {
        SimulationEngine engine;
        engine.setWorldSize(400, 400);

        SimulationEntity e(EntityType::Intruder);
        e.setPosition(QPointF(50, 50));
        engine.spawnEntity(e);

        QVariantList state = engine.entitiesState();
        QCOMPARE(state.size(), 1);
        QVariantMap first = state.first().toMap();
        QVERIFY(first.contains("id"));
        QVERIFY(first.contains("x"));
        QVERIFY(first.contains("y"));
    }

    void engine_propagation_smokeAfterFireStep()
    {
        SimulationEngine engine;
        engine.setWorldSize(400, 400);

        auto scenario = SimulationScenario::createFireScenario(QPointF(200, 200), "salon");
        engine.loadScenario(scenario);

        // Run a few steps — smoke should propagate
        for (int i = 0; i < 20; ++i)
            engine.runStep();

        QVariantList heatmap = engine.currentHeatmap("smoke");
        // After 20 ticks of fire, there should be some smoke data
        bool hasSmoke = false;
        for (const auto &v : heatmap) {
            if (v.toMap().value("value").toDouble() > 0.0) {
                hasSmoke = true;
                break;
            }
        }
        QVERIFY(hasSmoke);
    }

    void engine_causalGraph_valid()
    {
        SimulationEngine engine;
        engine.setWorldSize(400, 400);

        auto scenario = SimulationScenario::createFireScenario(QPointF(200, 200), "salon");
        engine.loadScenario(scenario);

        for (int i = 0; i < 5; ++i)
            engine.runStep();

        QVariantMap graph = engine.causalGraph();
        // Should have at least nodes and links keys
        QVERIFY(graph.contains("nodes") || graph.contains("links"));
    }

    void engine_runUntilComplete()
    {
        SimulationEngine engine;
        engine.setWorldSize(200, 200);

        SimulationScenario s(ScenarioType::Custom);
        s.setMaxDurationTicks(10); // Very short scenario
        engine.loadScenario(s);

        engine.runUntilComplete();

        QCOMPARE(engine.state(), SimState::Completed);
        QCOMPARE(engine.currentTick(), 10);
    }

    void engine_completionSignal()
    {
        SimulationEngine engine;
        engine.setWorldSize(200, 200);

        SimulationScenario s(ScenarioType::Custom);
        s.setMaxDurationTicks(5);
        engine.loadScenario(s);

        QSignalSpy completedSpy(&engine, &SimulationEngine::simulationCompleted);

        engine.runUntilComplete();

        QCOMPARE(completedSpy.count(), 1);
        QVariantMap summary = completedSpy.first().at(0).toMap();
        QVERIFY(!summary.isEmpty());
    }

    // ═════════════════════════════════════════════════
    //  Constantes du namespace
    // ═════════════════════════════════════════════════

    void constants_valid()
    {
        QCOMPARE(kDefaultTickMs, 100);
        QCOMPARE(kMaxEntities, 500);
        QCOMPARE(kMaxTicks, 6000);
        QCOMPARE(kDefaultPropagSpeed, 1.0);
        QCOMPARE(kDefaultAttenuation, 0.05);
    }
};

QTEST_GUILESS_MAIN(TestSimulation)
#include "test_simulation.moc"
