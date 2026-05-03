#include "SpatialCognitiveEngine.h"
#include "app/floorplan/FloorPlanModel.h"

// ─────────────────────────────────────────────────────
//  Construction / Destruction
// ─────────────────────────────────────────────────────

SpatialCognitiveEngine::SpatialCognitiveEngine(QObject *parent)
    : QObject(parent)
    , m_graph(new SpatialKnowledgeGraph(this))
    , m_context(new SpatialContext(this))
    , m_memory(new SpatialMemory(this))
    , m_reasoner(new SpatialReasoner(this))
    , m_planner(new SpatialPlanner(this))
    , m_supervisor(new SpatialSupervisor(this))
{
    // Câbler les sous-modules entre eux
    m_reasoner->setKnowledgeGraph(m_graph);
    m_reasoner->setContext(m_context);
    m_planner->setKnowledgeGraph(m_graph);
    m_planner->setContext(m_context);
    m_supervisor->setContext(m_context);
    m_supervisor->setMemory(m_memory);

    // Charger les règles par défaut
    m_reasoner->loadDefaultRules();

    // Timer auto-cycle
    connect(&m_autoCycleTimer, &QTimer::timeout, this, &SpatialCognitiveEngine::runCognitiveCycle);
}

SpatialCognitiveEngine::~SpatialCognitiveEngine() = default;

// ─────────────────────────────────────────────────────
//  Sources de données
// ─────────────────────────────────────────────────────

void SpatialCognitiveEngine::setFloorPlanModel(FloorPlanModel *model)
{
    m_floorModel = model;
}

void SpatialCognitiveEngine::updateFromNetwork(const QVariantList &devices, const QVariantList &links)
{
    m_graph->buildFromNetwork(devices, links);
    m_context->updateNetworkState({{"devices", QVariant::fromValue(devices)},
                                    {"links",   QVariant::fromValue(links)}});
}

void SpatialCognitiveEngine::updateFromHomeGraph(const QVariantList &entities)
{
    m_graph->buildFromHomeGraph(entities);
}

void SpatialCognitiveEngine::updateFromSimulation(const QVariantList &simEntities, const QVariantList &simEvents)
{
    m_graph->buildFromSimulation(simEntities, simEvents);
    m_context->updateSimulationState({{"entities", QVariant::fromValue(simEntities)},
                                       {"events",   QVariant::fromValue(simEvents)}});
}

// ─────────────────────────────────────────────────────
//  Cycle cognitif complet
// ─────────────────────────────────────────────────────

void SpatialCognitiveEngine::runCognitiveCycle()
{
    m_running = true;
    emit runningChanged(true);

    phasePerception();
    phaseSymbolic();
    phaseInference();
    phasePlanning();
    phaseSimulation();
    phaseDecision();
    phaseSupervision();

    setPhase(SpatialCognition::CognitivePhase::Idle);
    m_cycleCount++;
    m_running = false;

    emit runningChanged(false);
    emit cycleCompleted(m_cycleCount);
    emit stateChanged();
}

void SpatialCognitiveEngine::startAutoCycle(int intervalMs)
{
    m_autoCycleTimer.start(intervalMs);
}

void SpatialCognitiveEngine::stopAutoCycle()
{
    m_autoCycleTimer.stop();
}

// ─────────────────────────────────────────────────────
//  Étapes du pipeline
// ─────────────────────────────────────────────────────

void SpatialCognitiveEngine::phasePerception()
{
    setPhase(SpatialCognition::CognitivePhase::Perception);

    // Reconstruire le graphe depuis la source principale
    if (m_floorModel)
        m_graph->buildFromFloorPlan(m_floorModel);

    // Mettre à jour le contexte
    m_context->update();
}

void SpatialCognitiveEngine::phaseSymbolic()
{
    setPhase(SpatialCognition::CognitivePhase::Symbolic);

    // Le graphe de connaissances est déjà à jour (phase Perception).
    // Ici on pourrait enrichir avec des relations avancées.
    // Pour l'instant : snapshot du contexte dans la mémoire épisodique.
    m_memory->storeState(m_context->snapshot());
}

void SpatialCognitiveEngine::phaseInference()
{
    setPhase(SpatialCognition::CognitivePhase::Inference);

    m_lastInferences = m_reasoner->infer();

    // Détecter anomalies et risques supplémentaires
    auto anomalies = m_reasoner->detectAnomalies();
    auto riskInfs  = m_reasoner->detectRisks();

    m_lastInferences.append(anomalies);

    m_lastRisks.clear();
    m_lastRisks.append(riskInfs);

    // Stocker les risques en mémoire
    for (const auto &r : riskInfs) {
        QVariantMap riskData;
        riskData["roomId"]      = r.roomId;
        riskData["description"] = r.description;
        riskData["score"]       = static_cast<int>(r.severity) / 4.0;
        m_memory->storeRisk(riskData);
    }

    emit inferencesChanged();
    emit risksChanged();
}

void SpatialCognitiveEngine::phasePlanning()
{
    setPhase(SpatialCognition::CognitivePhase::Planning);

    m_planner->clearPlans();
    m_lastPlans.clear();

    // Générer un plan pour chaque risque détecté
    for (const auto &risk : m_lastRisks) {
        auto plan = m_planner->planForRisk(risk);
        m_lastPlans.append(plan);
    }

    emit plansChanged();
}

void SpatialCognitiveEngine::phaseSimulation()
{
    setPhase(SpatialCognition::CognitivePhase::Simulation);

    // Phase optionnelle : on pourrait lancer des simulations
    // pour valider les plans. Pour l'instant, pass-through.
}

void SpatialCognitiveEngine::phaseDecision()
{
    setPhase(SpatialCognition::CognitivePhase::Decision);

    // Calculer le risque global
    double maxRisk = 0.0;
    if (m_context)
        maxRisk = m_context->globalRiskLevel();
    for (const auto &r : m_lastRisks) {
        double riskVal = static_cast<int>(r.severity) / 4.0;
        maxRisk = qMax(maxRisk, riskVal);
    }

    if (qAbs(maxRisk - m_globalRisk) > 0.01) {
        m_globalRisk = maxRisk;
        emit globalRiskChanged(m_globalRisk);
    }

    // Émettre les risques individuels
    for (const auto &r : m_lastRisks) {
        QVariantMap riskData;
        riskData["id"]          = r.id;
        riskData["description"] = r.description;
        riskData["severity"]    = static_cast<int>(r.severity);
        riskData["roomId"]      = r.roomId;
        riskData["confidence"]  = r.confidence;
        emit riskDetected(riskData);
    }
}

void SpatialCognitiveEngine::phaseSupervision()
{
    setPhase(SpatialCognition::CognitivePhase::Supervision);

    for (const auto &plan : m_lastPlans) {
        auto decision = m_supervisor->approveOrReject(plan);

        if (decision == SpatialCognition::SupervisorDecision::Approved
            || decision == SpatialCognition::SupervisorDecision::Modified) {
            // Émettre les actions recommandées
            for (const auto &action : plan.actions) {
                emit actionRecommended(action.toVariantMap());
            }
            // Mémoriser la décision
            m_memory->storeDecision(plan.toVariantMap());
        }
    }
}

// ─────────────────────────────────────────────────────
//  Accès aux résultats
// ─────────────────────────────────────────────────────

int SpatialCognitiveEngine::phase() const
{
    return static_cast<int>(m_phase);
}

bool SpatialCognitiveEngine::isRunning() const
{
    return m_running;
}

int SpatialCognitiveEngine::cycleCount() const
{
    return m_cycleCount;
}

double SpatialCognitiveEngine::globalRisk() const
{
    return m_globalRisk;
}

QVariantList SpatialCognitiveEngine::inferences() const
{
    QVariantList list;
    for (const auto &inf : m_lastInferences) {
        QVariantMap m;
        m["id"]          = inf.id;
        m["ruleId"]      = inf.ruleId;
        m["description"] = inf.description;
        m["type"]        = static_cast<int>(inf.type);
        m["severity"]    = static_cast<int>(inf.severity);
        m["confidence"]  = inf.confidence;
        m["roomId"]      = inf.roomId;
        m["explanation"]  = inf.explanation;
        list.append(m);
    }
    return list;
}

QVariantList SpatialCognitiveEngine::plans() const
{
    QVariantList list;
    for (const auto &p : m_lastPlans)
        list.append(p.toVariantMap());
    return list;
}

QVariantList SpatialCognitiveEngine::risks() const
{
    QVariantList list;
    for (const auto &r : m_lastRisks) {
        QVariantMap m;
        m["id"]          = r.id;
        m["description"] = r.description;
        m["severity"]    = static_cast<int>(r.severity);
        m["confidence"]  = r.confidence;
        m["roomId"]      = r.roomId;
        list.append(m);
    }
    return list;
}

QVariantMap SpatialCognitiveEngine::cognitiveState() const
{
    return {
        {"phase",       static_cast<int>(m_phase)},
        {"running",     m_running},
        {"cycleCount",  m_cycleCount},
        {"globalRisk",  m_globalRisk},
        {"nodeCount",   m_graph->nodesToVariantList().size()},
        {"edgeCount",   m_graph->edgesToVariantList().size()},
        {"inferenceCount", m_lastInferences.size()},
        {"planCount",      m_lastPlans.size()},
        {"riskCount",      m_lastRisks.size()},
        {"memorySize",     m_memory->queryByCategory("").size()}
    };
}

QVariantMap SpatialCognitiveEngine::getSpatialExplanation(const QString &eventId) const
{
    auto explanation = m_reasoner->explain(eventId);
    return {{"eventId", eventId}, {"explanation", explanation}};
}

QVariantList SpatialCognitiveEngine::getPredictions() const
{
    // Prédictions basées sur les inférences et la mémoire historique
    QVariantList predictions;
    for (const auto &inf : m_lastInferences) {
        if (inf.confidence > 0.6) {
            QVariantMap pred;
            pred["description"] = QStringLiteral("Prédiction basée sur : %1").arg(inf.description);
            pred["confidence"]  = inf.confidence;
            pred["roomId"]      = inf.roomId;
            pred["severity"]    = static_cast<int>(inf.severity);
            predictions.append(pred);
        }
    }
    return predictions;
}

QVariantList SpatialCognitiveEngine::getRisks() const
{
    return risks();
}

QVariantList SpatialCognitiveEngine::getRecommendedActions() const
{
    QVariantList actions;
    for (const auto &plan : m_lastPlans) {
        for (const auto &action : plan.actions)
            actions.append(action.toVariantMap());
    }
    return actions;
}

// ── Sous-modules ──

SpatialKnowledgeGraph *SpatialCognitiveEngine::knowledgeGraph() const { return m_graph; }
SpatialContext        *SpatialCognitiveEngine::context() const        { return m_context; }
SpatialMemory         *SpatialCognitiveEngine::memory() const         { return m_memory; }
SpatialReasoner       *SpatialCognitiveEngine::reasoner() const       { return m_reasoner; }
SpatialPlanner        *SpatialCognitiveEngine::planner() const        { return m_planner; }
SpatialSupervisor     *SpatialCognitiveEngine::supervisor() const     { return m_supervisor; }

// ── Interne ──

void SpatialCognitiveEngine::setPhase(SpatialCognition::CognitivePhase p)
{
    if (m_phase != p) {
        m_phase = p;
        emit phaseChanged(static_cast<int>(p));
    }
}
