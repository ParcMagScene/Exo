#ifndef SIMULATIONCONTROLLER_H
#define SIMULATIONCONTROLLER_H

#include "SimulationEngine.h"
#include "SimulationEnums.h"

#include <QObject>
#include <QTimer>
#include <QVariantMap>
#include <QVariantList>
#include <QtQml/qqml.h>

class FloorPlanModel;

// ─────────────────────────────────────────────────────
//  SimulationController — Pont QML ↔ SimulationEngine
//
//  Expose le moteur de simulation à QML.
//  Gère le tick timer, pause/play/stop,
//  export des résultats, intégration FloorPlanModel.
//
//  QML_ELEMENT : enregistré automatiquement.
// ─────────────────────────────────────────────────────
class SimulationController : public QObject
{
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(int  simState    READ simState    NOTIFY simStateChanged)
    Q_PROPERTY(int  currentTick READ currentTick NOTIFY tickChanged)
    Q_PROPERTY(int  maxTicks    READ maxTicks    NOTIFY scenarioChanged)
    Q_PROPERTY(bool running     READ running     NOTIFY simStateChanged)
    Q_PROPERTY(bool paused      READ paused      NOTIFY simStateChanged)
    Q_PROPERTY(double progress  READ progress    NOTIFY tickChanged)
    Q_PROPERTY(int  tickIntervalMs READ tickIntervalMs WRITE setTickIntervalMs NOTIFY tickIntervalChanged)

    Q_PROPERTY(QVariantList entities     READ entities     NOTIFY tickChanged)
    Q_PROPERTY(QVariantList heatmapSmoke READ heatmapSmoke NOTIFY propagationChanged)
    Q_PROPERTY(QVariantList heatmapHeat  READ heatmapHeat  NOTIFY propagationChanged)
    Q_PROPERTY(QVariantList heatmapWater READ heatmapWater NOTIFY propagationChanged)
    Q_PROPERTY(QVariantList trajectories READ trajectories  NOTIFY tickChanged)
    Q_PROPERTY(QVariantList risks        READ risks         NOTIFY risksChanged)
    Q_PROPERTY(QVariantList events       READ events        NOTIFY eventsChanged)
    Q_PROPERTY(QVariantMap  causalGraph  READ causalGraph   NOTIFY causalGraphChanged)

public:
    explicit SimulationController(QObject *parent = nullptr);
    ~SimulationController() override;

    // ── FloorPlan binding ──
    Q_INVOKABLE void setFloorPlan(FloorPlanModel *model);
    Q_INVOKABLE void setWorldSize(int w, int h);

    // ── Scenario loading ──
    Q_INVOKABLE void loadScenario(const QString &type, const QVariantMap &params);
    Q_INVOKABLE void loadPresetScenario(const QString &presetId);
    Q_INVOKABLE QVariantList availablePresets() const;

    // ── Playback control ──
    Q_INVOKABLE void start();
    Q_INVOKABLE void pause();
    Q_INVOKABLE void stop();
    Q_INVOKABLE void step();
    Q_INVOKABLE void reset();

    // ── Speed ──
    int  tickIntervalMs() const { return m_tickInterval; }
    void setTickIntervalMs(int ms);

    // ── State ──
    int    simState() const { return static_cast<int>(m_engine.state()); }
    int    currentTick() const { return m_engine.currentTick(); }
    int    maxTicks() const;
    bool   running() const { return m_engine.state() == Simulation::SimState::Running; }
    bool   paused() const { return m_engine.state() == Simulation::SimState::Paused; }
    double progress() const;

    // ── Data for QML ──
    QVariantList entities() const { return m_engine.entitiesState(); }
    QVariantList heatmapSmoke() const { return m_engine.currentHeatmap("smoke"); }
    QVariantList heatmapHeat() const { return m_engine.currentHeatmap("heat"); }
    QVariantList heatmapWater() const { return m_engine.currentHeatmap("water"); }
    QVariantList trajectories() const { return m_engine.currentTrajectories(); }
    QVariantList risks() const { return m_engine.currentRisks(); }
    QVariantList events() const;
    QVariantMap  causalGraph() const { return m_engine.causalGraph(); }

    // ── Query ──
    Q_INVOKABLE QVariantMap getState() const;
    Q_INVOKABLE QVariantList getRisks() const { return risks(); }
    Q_INVOKABLE QVariantMap  getCausalGraph() const { return causalGraph(); }
    Q_INVOKABLE QVariantMap  getResult() const;
    Q_INVOKABLE QVariantList getEventsAtTick(int tick) const;

signals:
    void simStateChanged();
    void tickChanged();
    void scenarioChanged();
    void tickIntervalChanged();
    void propagationChanged();
    void risksChanged();
    void eventsChanged();
    void causalGraphChanged();

    // Forwarded from engine
    void sensorTriggered(const QString &sensorId, int tick, const QVariantMap &data);
    void deviceActivated(const QString &deviceId, int tick, const QString &action);
    void riskDetected(const QVariantMap &risk);
    void simulationCompleted(const QVariantMap &summary);

private slots:
    void onTick();

private:
    SimulationEngine m_engine;
    QTimer           m_timer;
    int              m_tickInterval = Simulation::kDefaultTickMs;
};

#endif // SIMULATIONCONTROLLER_H
