#ifndef SPATIALCOGNITIVEENGINE_H
#define SPATIALCOGNITIVEENGINE_H

#include <QObject>
#include <QTimer>
#include <QString>
#include <QVariantMap>
#include <QVariantList>
#include <qqml.h>

#include "SpatialEnums.h"
#include "SpatialKnowledgeGraph.h"
#include "SpatialContext.h"
#include "SpatialMemory.h"
#include "SpatialReasoner.h"
#include "SpatialPlanner.h"
#include "SpatialSupervisor.h"

class FloorPlanModel;

// ─────────────────────────────────────────────────────
//  SpatialCognitiveEngine — orchestrateur principal
//  Pipeline : Perception → Symbolique → Inférence →
//             Planification → Simulation → Décision → Supervision
// ─────────────────────────────────────────────────────

class SpatialCognitiveEngine : public QObject
{
    Q_OBJECT
    QML_ELEMENT

    // ── Propriétés QML ──
    Q_PROPERTY(int phase READ phase NOTIFY phaseChanged)
    Q_PROPERTY(bool running READ isRunning NOTIFY runningChanged)
    Q_PROPERTY(int cycleCount READ cycleCount NOTIFY cycleCompleted)
    Q_PROPERTY(double globalRisk READ globalRisk NOTIFY globalRiskChanged)
    Q_PROPERTY(QVariantList inferences READ inferences NOTIFY inferencesChanged)
    Q_PROPERTY(QVariantList plans READ plans NOTIFY plansChanged)
    Q_PROPERTY(QVariantList risks READ risks NOTIFY risksChanged)
    Q_PROPERTY(QVariantMap cognitiveState READ cognitiveState NOTIFY stateChanged)

public:
    explicit SpatialCognitiveEngine(QObject *parent = nullptr);
    ~SpatialCognitiveEngine() override;

    // ── Sources de données ──
    void setFloorPlanModel(FloorPlanModel *model);
    Q_INVOKABLE void updateFromNetwork(const QVariantList &devices, const QVariantList &links);
    Q_INVOKABLE void updateFromHomeGraph(const QVariantList &entities);
    Q_INVOKABLE void updateFromSimulation(const QVariantList &simEntities, const QVariantList &simEvents);

    // ── Cycle cognitif ──
    Q_INVOKABLE void runCognitiveCycle();
    Q_INVOKABLE void startAutoCycle(int intervalMs = 5000);
    Q_INVOKABLE void stopAutoCycle();

    // ── Accès aux résultats ──
    int  phase() const;
    bool isRunning() const;
    int  cycleCount() const;
    double globalRisk() const;

    QVariantList inferences() const;
    QVariantList plans() const;
    QVariantList risks() const;
    QVariantMap  cognitiveState() const;

    Q_INVOKABLE QVariantMap  getSpatialExplanation(const QString &eventId) const;
    Q_INVOKABLE QVariantList getPredictions() const;
    Q_INVOKABLE QVariantList getRisks() const;
    Q_INVOKABLE QVariantList getRecommendedActions() const;

    // ── Sous-modules (accès pour tests / intégration avancée) ──
    SpatialKnowledgeGraph *knowledgeGraph() const;
    SpatialContext        *context() const;
    SpatialMemory         *memory() const;
    SpatialReasoner       *reasoner() const;
    SpatialPlanner        *planner() const;
    SpatialSupervisor     *supervisor() const;

signals:
    void phaseChanged(int phase);
    void runningChanged(bool running);
    void cycleCompleted(int count);
    void globalRiskChanged(double risk);
    void inferencesChanged();
    void plansChanged();
    void risksChanged();
    void stateChanged();

    void riskDetected(const QVariantMap &risk);
    void actionRecommended(const QVariantMap &action);
    void explanationReady(const QString &eventId, const QVariantMap &explanation);

private:
    void setPhase(SpatialCognition::CognitivePhase p);

    // ── Étapes du pipeline ──
    void phasePerception();
    void phaseSymbolic();
    void phaseInference();
    void phasePlanning();
    void phaseSimulation();
    void phaseDecision();
    void phaseSupervision();

    // ── Sous-modules (propriété totale) ──
    SpatialKnowledgeGraph *m_graph      = nullptr;
    SpatialContext        *m_context    = nullptr;
    SpatialMemory         *m_memory    = nullptr;
    SpatialReasoner       *m_reasoner  = nullptr;
    SpatialPlanner        *m_planner   = nullptr;
    SpatialSupervisor     *m_supervisor = nullptr;

    FloorPlanModel *m_floorModel = nullptr;

    // ── État du cycle ──
    SpatialCognition::CognitivePhase m_phase = SpatialCognition::CognitivePhase::Idle;
    bool m_running     = false;
    int  m_cycleCount  = 0;
    double m_globalRisk = 0.0;

    QTimer m_autoCycleTimer;

    // ── Résultats du dernier cycle ──
    QVector<Inference>  m_lastInferences;
    QVector<SpatialPlan> m_lastPlans;
    QVector<Inference>  m_lastRisks;
};

#endif // SPATIALCOGNITIVEENGINE_H
