#include "SimulationScenario.h"

#include <QUuid>

// ═════════════════════════════════════════════════════
//  SimulationTrigger
// ═════════════════════════════════════════════════════

QVariantMap SimulationTrigger::toVariantMap() const
{
    return {
        {"deviceId",   deviceId},
        {"condition",  condition},
        {"threshold",  threshold},
        {"delayTicks", delayTicks},
        {"action",     action},
        {"parameters", parameters}
    };
}

SimulationTrigger SimulationTrigger::fromVariantMap(const QVariantMap &data)
{
    SimulationTrigger t;
    t.deviceId   = data.value("deviceId").toString();
    t.condition  = data.value("condition").toString();
    t.threshold  = data.value("threshold").toDouble();
    t.delayTicks = data.value("delayTicks").toInt();
    t.action     = data.value("action").toString();
    t.parameters = data.value("parameters").toMap();
    return t;
}

// ═════════════════════════════════════════════════════
//  SimulationScenario
// ═════════════════════════════════════════════════════

SimulationScenario::SimulationScenario()
    : m_id(QUuid::createUuid().toString(QUuid::WithoutBraces))
{
}

SimulationScenario::SimulationScenario(Simulation::ScenarioType type)
    : m_id(QUuid::createUuid().toString(QUuid::WithoutBraces))
    , m_type(type)
{
}

// ── Serialization ──

QJsonObject SimulationScenario::toJson() const
{
    QJsonObject obj;
    obj["id"]               = m_id;
    obj["name"]             = m_name;
    obj["description"]      = m_description;
    obj["type"]             = static_cast<int>(m_type);
    obj["startX"]           = m_startPosition.x();
    obj["startY"]           = m_startPosition.y();
    obj["startRoomId"]      = m_startRoomId;
    obj["propagationSpeed"] = m_propagationSpeed;
    obj["intensity"]        = m_intensity;
    obj["maxDurationTicks"] = m_maxDurationTicks;
    obj["parameters"]       = QJsonObject::fromVariantMap(m_parameters);

    QJsonArray entities;
    for (const auto &e : m_initialEntities)
        entities.append(QJsonObject::fromVariantMap(e.toVariantMap()));
    obj["initialEntities"] = entities;

    QJsonArray trigs;
    for (const auto &t : m_triggers)
        trigs.append(QJsonObject::fromVariantMap(t.toVariantMap()));
    obj["triggers"] = trigs;

    return obj;
}

SimulationScenario SimulationScenario::fromJson(const QJsonObject &obj)
{
    SimulationScenario s;
    s.m_id               = obj["id"].toString();
    s.m_name             = obj["name"].toString();
    s.m_description      = obj["description"].toString();
    s.m_type             = static_cast<Simulation::ScenarioType>(obj["type"].toInt());
    s.m_startPosition    = QPointF(obj["startX"].toDouble(), obj["startY"].toDouble());
    s.m_startRoomId      = obj["startRoomId"].toString();
    s.m_propagationSpeed = obj["propagationSpeed"].toDouble(1.0);
    s.m_intensity        = obj["intensity"].toDouble(1.0);
    s.m_maxDurationTicks = obj["maxDurationTicks"].toInt(3000);
    s.m_parameters       = obj["parameters"].toObject().toVariantMap();

    for (const auto &v : obj["initialEntities"].toArray())
        s.m_initialEntities.append(SimulationEntity::fromVariantMap(v.toObject().toVariantMap()));

    for (const auto &v : obj["triggers"].toArray())
        s.m_triggers.append(SimulationTrigger::fromVariantMap(v.toObject().toVariantMap()));

    return s;
}

QVariantMap SimulationScenario::toVariantMap() const
{
    QVariantList entities;
    for (const auto &e : m_initialEntities)
        entities.append(e.toVariantMap());

    QVariantList trigs;
    for (const auto &t : m_triggers)
        trigs.append(t.toVariantMap());

    return {
        {"id",               m_id},
        {"name",             m_name},
        {"description",      m_description},
        {"type",             static_cast<int>(m_type)},
        {"startX",           m_startPosition.x()},
        {"startY",           m_startPosition.y()},
        {"startRoomId",      m_startRoomId},
        {"propagationSpeed", m_propagationSpeed},
        {"intensity",        m_intensity},
        {"maxDurationTicks", m_maxDurationTicks},
        {"parameters",       m_parameters},
        {"initialEntities",  entities},
        {"triggers",         trigs}
    };
}

// ═════════════════════════════════════════════════════
//  Factory — Scénarios prédéfinis
// ═════════════════════════════════════════════════════

SimulationScenario SimulationScenario::createFireScenario(const QPointF &origin, const QString &roomId)
{
    SimulationScenario s(Simulation::ScenarioType::Fire);
    s.setName("Incendie");
    s.setDescription("Simulation incendie : fumée + chaleur + propagation");
    s.setStartPosition(origin);
    s.setStartRoomId(roomId);
    s.setPropagationSpeed(0.8);
    s.setIntensity(1.0);
    s.setMaxDurationTicks(3000);

    // Entité fumée
    SimulationEntity smoke(Simulation::EntityType::Smoke);
    smoke.setPosition(origin);
    smoke.setRoomId(roomId);
    smoke.setState(Simulation::EntityState::Spreading);
    s.addInitialEntity(smoke);

    // Entité chaleur
    SimulationEntity heat(Simulation::EntityType::Heat);
    heat.setPosition(origin);
    heat.setRoomId(roomId);
    heat.setState(Simulation::EntityState::Spreading);
    s.addInitialEntity(heat);

    // Triggers : détecteurs de fumée
    s.addTrigger({"smoke_detector_*", "threshold", 0.3, 0, "alert", {{"type", "fire_alarm"}}});
    s.addTrigger({"thermostat_*",     "threshold", 0.5, 5, "alert", {{"type", "heat_alarm"}}});

    return s;
}

SimulationScenario SimulationScenario::createIntrusionScenario(const QPointF &entry, const QVector<QPointF> &path)
{
    SimulationScenario s(Simulation::ScenarioType::Intrusion);
    s.setName("Intrusion");
    s.setDescription("Simulation intrusion : trajectoire + détection + réponse");
    s.setStartPosition(entry);
    s.setPropagationSpeed(1.5);
    s.setMaxDurationTicks(1800);

    // Entité intrus
    SimulationEntity intruder(Simulation::EntityType::Intruder);
    intruder.setPosition(entry);
    intruder.setState(Simulation::EntityState::Moving);
    intruder.setTrajectory(path);
    s.addInitialEntity(intruder);

    // Triggers : détecteurs de mouvement
    s.addTrigger({"motion_sensor_*", "proximity", 30.0, 0, "alert",    {{"type", "motion_detected"}}});
    s.addTrigger({"camera_*",        "proximity", 50.0, 2, "activate", {{"type", "record"}}});
    s.addTrigger({"door_lock_*",     "proximity", 20.0, 5, "lock",     {{"type", "lockdown"}}});

    return s;
}

SimulationScenario SimulationScenario::createBlackoutScenario()
{
    SimulationScenario s(Simulation::ScenarioType::Blackout);
    s.setName("Coupure courant");
    s.setDescription("Simulation blackout : perte alimentation + UPS + arrêt gracieux");
    s.setMaxDurationTicks(1200);

    // Triggers : tous les appareils
    s.addTrigger({"ups_*",     "timer", 0.0, 0,  "activate", {{"type", "battery_mode"}}});
    s.addTrigger({"light_*",   "timer", 0.0, 1,  "deactivate", {{"type", "power_loss"}}});
    s.addTrigger({"server_*",  "timer", 0.0, 50, "deactivate", {{"type", "graceful_shutdown"}}});

    return s;
}

SimulationScenario SimulationScenario::createNetworkFailureScenario()
{
    SimulationScenario s(Simulation::ScenarioType::NetworkFailure);
    s.setName("Panne réseau");
    s.setDescription("Simulation panne réseau : perte connectivité + mode hors ligne");
    s.setMaxDurationTicks(1800);

    s.addTrigger({"router_*",  "timer", 0.0, 0,  "deactivate", {{"type", "network_down"}}});
    s.addTrigger({"camera_*",  "timer", 0.0, 10, "deactivate", {{"type", "stream_loss"}}});
    s.addTrigger({"server_*",  "timer", 0.0, 5,  "activate",   {{"type", "offline_mode"}}});

    return s;
}

SimulationScenario SimulationScenario::createFloodScenario(const QPointF &origin, const QString &roomId)
{
    SimulationScenario s(Simulation::ScenarioType::Flood);
    s.setName("Fuite d'eau");
    s.setDescription("Simulation inondation : propagation eau + dégâts");
    s.setStartPosition(origin);
    s.setStartRoomId(roomId);
    s.setPropagationSpeed(0.4);
    s.setIntensity(0.7);
    s.setMaxDurationTicks(3600);

    SimulationEntity water(Simulation::EntityType::Water);
    water.setPosition(origin);
    water.setRoomId(roomId);
    water.setState(Simulation::EntityState::Spreading);
    s.addInitialEntity(water);

    s.addTrigger({"water_sensor_*", "threshold", 0.2, 0,  "alert",      {{"type", "water_detected"}}});
    s.addTrigger({"valve_*",        "threshold", 0.5, 10, "deactivate", {{"type", "shutoff_valve"}}});

    return s;
}
