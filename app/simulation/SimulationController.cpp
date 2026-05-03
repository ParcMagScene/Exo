#include "SimulationController.h"

#include <QDebug>

// ═════════════════════════════════════════════════════
//  SimulationController — Implémentation
// ═════════════════════════════════════════════════════

SimulationController::SimulationController(QObject *parent)
    : QObject(parent)
{
    m_timer.setTimerType(Qt::PreciseTimer);
    connect(&m_timer, &QTimer::timeout, this, &SimulationController::onTick);

    // Forward engine signals
    connect(&m_engine, &SimulationEngine::stateChanged, this, [this]() {
        emit simStateChanged();
    });
    connect(&m_engine, &SimulationEngine::tickAdvanced, this, [this]() {
        emit tickChanged();
        emit eventsChanged();
    });
    connect(&m_engine, &SimulationEngine::propagationUpdated, this, [this]() {
        emit propagationChanged();
    });
    connect(&m_engine, &SimulationEngine::sensorTriggered, this, &SimulationController::sensorTriggered);
    connect(&m_engine, &SimulationEngine::deviceActivated, this, &SimulationController::deviceActivated);
    connect(&m_engine, &SimulationEngine::riskDetected, this, [this](const QVariantMap &risk) {
        emit riskDetected(risk);
        emit risksChanged();
    });
    connect(&m_engine, &SimulationEngine::causalLinkAdded, this, [this]() {
        emit causalGraphChanged();
    });
    connect(&m_engine, &SimulationEngine::simulationCompleted, this, [this](const QVariantMap &summary) {
        m_timer.stop();
        emit simulationCompleted(summary);
        emit simStateChanged();
    });
}

SimulationController::~SimulationController() = default;

// ─────────────────────────────────────────────────────
//  FloorPlan binding
// ─────────────────────────────────────────────────────

void SimulationController::setFloorPlan(FloorPlanModel *model)
{
    m_engine.setFloorPlanModel(model);
}

void SimulationController::setWorldSize(int w, int h)
{
    m_engine.setWorldSize(w, h);
}

// ─────────────────────────────────────────────────────
//  Scenario loading
// ─────────────────────────────────────────────────────

void SimulationController::loadScenario(const QString &type, const QVariantMap &params)
{
    SimulationScenario scenario;

    if (type == "fire")            scenario.setType(Simulation::ScenarioType::Fire);
    else if (type == "intrusion")  scenario.setType(Simulation::ScenarioType::Intrusion);
    else if (type == "blackout")   scenario.setType(Simulation::ScenarioType::Blackout);
    else if (type == "network")    scenario.setType(Simulation::ScenarioType::NetworkFailure);
    else if (type == "flood")      scenario.setType(Simulation::ScenarioType::Flood);
    else                           scenario.setType(Simulation::ScenarioType::Custom);

    scenario.setName(params.value("name", type).toString());
    scenario.setDescription(params.value("description", "").toString());

    if (params.contains("startX") && params.contains("startY"))
        scenario.setStartPosition(QPointF(params["startX"].toDouble(), params["startY"].toDouble()));

    if (params.contains("startRoomId"))
        scenario.setStartRoomId(params["startRoomId"].toString());

    if (params.contains("propagationSpeed"))
        scenario.setPropagationSpeed(params["propagationSpeed"].toDouble());

    if (params.contains("intensity"))
        scenario.setIntensity(params["intensity"].toDouble());

    if (params.contains("maxDurationTicks"))
        scenario.setMaxDurationTicks(params["maxDurationTicks"].toInt());

    scenario.setParameters(params);

    m_engine.loadScenario(scenario);
    emit scenarioChanged();
}

void SimulationController::loadPresetScenario(const QString &presetId)
{
    SimulationScenario scenario;

    if (presetId == "fire") {
        scenario = SimulationScenario::createFireScenario(QPointF(400, 300), "room_main");
    } else if (presetId == "intrusion") {
        QVector<QPointF> path = {
            {50, 300}, {150, 300}, {250, 250}, {350, 200}, {450, 200}, {500, 150}
        };
        scenario = SimulationScenario::createIntrusionScenario(QPointF(50, 300), path);
    } else if (presetId == "blackout") {
        scenario = SimulationScenario::createBlackoutScenario();
    } else if (presetId == "network") {
        scenario = SimulationScenario::createNetworkFailureScenario();
    } else if (presetId == "flood") {
        scenario = SimulationScenario::createFloodScenario(QPointF(200, 400), "room_bathroom");
    } else {
        qWarning() << "[SimController] Unknown preset:" << presetId;
        return;
    }

    m_engine.loadScenario(scenario);
    emit scenarioChanged();
}

QVariantList SimulationController::availablePresets() const
{
    return {
        QVariantMap{{"id", "fire"},      {"label", "Incendie"},        {"icon", "🔥"}, {"color", "#F44747"}, {"severity", "critical"}},
        QVariantMap{{"id", "intrusion"}, {"label", "Intrusion"},       {"icon", "🚨"}, {"color", "#CE9178"}, {"severity", "high"}},
        QVariantMap{{"id", "blackout"},  {"label", "Coupure courant"}, {"icon", "⚡"}, {"color", "#569CD6"}, {"severity", "high"}},
        QVariantMap{{"id", "network"},   {"label", "Panne réseau"},    {"icon", "📡"}, {"color", "#DCDCAA"}, {"severity", "medium"}},
        QVariantMap{{"id", "flood"},     {"label", "Fuite d'eau"},     {"icon", "💧"}, {"color", "#4EC9B0"}, {"severity", "high"}}
    };
}

// ─────────────────────────────────────────────────────
//  Playback control
// ─────────────────────────────────────────────────────

void SimulationController::start()
{
    if (m_engine.state() == Simulation::SimState::Completed ||
        m_engine.state() == Simulation::SimState::Aborted)
        return;

    m_timer.start(m_tickInterval);
    emit simStateChanged();
}

void SimulationController::pause()
{
    m_timer.stop();
    // We track paused state via timer running + engine state
    emit simStateChanged();
}

void SimulationController::stop()
{
    m_timer.stop();
    m_engine.reset();
    emit simStateChanged();
    emit tickChanged();
    emit propagationChanged();
}

void SimulationController::step()
{
    m_timer.stop();
    m_engine.runStep();
}

void SimulationController::reset()
{
    m_timer.stop();
    m_engine.reset();
    emit simStateChanged();
    emit tickChanged();
    emit propagationChanged();
    emit risksChanged();
    emit eventsChanged();
    emit causalGraphChanged();
}

void SimulationController::setTickIntervalMs(int ms)
{
    m_tickInterval = qMax(10, ms);
    if (m_timer.isActive())
        m_timer.setInterval(m_tickInterval);
    emit tickIntervalChanged();
}

// ─────────────────────────────────────────────────────
//  State queries
// ─────────────────────────────────────────────────────

int SimulationController::maxTicks() const
{
    return m_engine.currentScenario().maxDurationTicks();
}

double SimulationController::progress() const
{
    int max = maxTicks();
    if (max <= 0) return 0.0;
    return static_cast<double>(m_engine.currentTick()) / max;
}

QVariantList SimulationController::events() const
{
    return m_engine.result().eventsToVariantList();
}

QVariantMap SimulationController::getState() const
{
    return {
        {"state",       simState()},
        {"tick",        currentTick()},
        {"maxTicks",    maxTicks()},
        {"progress",    progress()},
        {"entityCount", m_engine.entities().size()},
        {"eventCount",  m_engine.result().events().size()},
        {"riskCount",   m_engine.result().risks().size()}
    };
}

QVariantMap SimulationController::getResult() const
{
    return m_engine.result().toVariantMap();
}

QVariantList SimulationController::getEventsAtTick(int tick) const
{
    return m_engine.eventsAtTick(tick);
}

// ─────────────────────────────────────────────────────
//  Timer tick
// ─────────────────────────────────────────────────────

void SimulationController::onTick()
{
    m_engine.runStep();
}
