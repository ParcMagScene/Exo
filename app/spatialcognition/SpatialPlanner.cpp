#include "SpatialPlanner.h"

#include <QUuid>

// ─────────────────────────────────────────────────────
//  PlannedAction
// ─────────────────────────────────────────────────────

QVariantMap PlannedAction::toVariantMap() const
{
    return {
        {"id",          id},
        {"type",        static_cast<int>(type)},
        {"targetId",    targetId},
        {"description", description},
        {"parameters",  parameters},
        {"priority",    priority},
        {"confidence",  confidence},
        {"reason",      reason}
    };
}

// ─────────────────────────────────────────────────────
//  SpatialPlan
// ─────────────────────────────────────────────────────

QVariantMap SpatialPlan::toVariantMap() const
{
    QVariantList actionList;
    for (const auto &a : actions)
        actionList.append(a.toVariantMap());

    return {
        {"id",                 id},
        {"goalDescription",    goalDescription},
        {"goalType",           static_cast<int>(goalType)},
        {"actions",            actionList},
        {"actionCount",        actionCount()},
        {"overallConfidence",  overallConfidence},
        {"explanation",        explanation}
    };
}

// ─────────────────────────────────────────────────────
//  SpatialPlanner
// ─────────────────────────────────────────────────────

SpatialPlanner::SpatialPlanner(QObject *parent)
    : QObject(parent)
{
}

SpatialPlanner::~SpatialPlanner() = default;

void SpatialPlanner::setKnowledgeGraph(SpatialKnowledgeGraph *graph)
{
    m_graph = graph;
}

void SpatialPlanner::setContext(SpatialContext *context)
{
    m_context = context;
}

// ── Planification par objectif ──

SpatialPlan SpatialPlanner::planForGoal(SpatialCognition::GoalType goal, const QVariantMap &params)
{
    SpatialPlan plan;

    switch (goal) {
    case SpatialCognition::GoalType::Secure:      plan = planSecure(params); break;
    case SpatialCognition::GoalType::Illuminate:   plan = planIlluminate(params); break;
    case SpatialCognition::GoalType::Ventilate:    plan = planVentilate(params); break;
    case SpatialCognition::GoalType::SaveEnergy:   plan = planSaveEnergy(params); break;
    case SpatialCognition::GoalType::Monitor:      plan = planMonitor(params); break;
    case SpatialCognition::GoalType::Alert:        plan = planAlert(params); break;
    case SpatialCognition::GoalType::Custom:
        plan.id              = QUuid::createUuid().toString(QUuid::WithoutBraces);
        plan.goalType        = goal;
        plan.goalDescription = params.value("description", "Plan personnalisé").toString();
        break;
    }

    m_lastPlans.append(plan);
    emit planGenerated(plan.toVariantMap());
    return plan;
}

SpatialPlan SpatialPlanner::planForRisk(const Inference &riskInference)
{
    SpatialPlan plan;
    plan.id              = QUuid::createUuid().toString(QUuid::WithoutBraces);
    plan.goalDescription = QStringLiteral("Atténuer : %1").arg(riskInference.description);

    if (riskInference.description.contains("incendie", Qt::CaseInsensitive)) {
        plan.goalType = SpatialCognition::GoalType::Secure;
        if (!riskInference.roomId.isEmpty()) {
            plan.actions.append(makeAction(SpatialCognition::ActionType::SendNotification,
                                           riskInference.roomId,
                                           QStringLiteral("Alerte incendie — %1").arg(riskInference.roomId), 10));
            plan.actions.append(makeAction(SpatialCognition::ActionType::ActivateCamera,
                                           riskInference.roomId,
                                           QStringLiteral("Activer caméra — %1").arg(riskInference.roomId), 9));
            plan.actions.append(makeAction(SpatialCognition::ActionType::Open,
                                           riskInference.roomId,
                                           QStringLiteral("Ouvrir fenêtres — %1").arg(riskInference.roomId), 8));
        }
    } else if (riskInference.description.contains("intrusion", Qt::CaseInsensitive)) {
        plan.goalType = SpatialCognition::GoalType::Secure;
        plan.actions.append(makeAction(SpatialCognition::ActionType::ActivateCamera,
                                       riskInference.roomId,
                                       "Activer toutes les caméras", 10));
        plan.actions.append(makeAction(SpatialCognition::ActionType::TurnOn,
                                       riskInference.roomId,
                                       "Allumer toutes les lumières", 9));
        plan.actions.append(makeAction(SpatialCognition::ActionType::SendNotification,
                                       "owner",
                                       "Notifier le propriétaire", 10));
    } else if (riskInference.description.contains("inondation", Qt::CaseInsensitive)) {
        plan.goalType = SpatialCognition::GoalType::Secure;
        plan.actions.append(makeAction(SpatialCognition::ActionType::Close,
                                       riskInference.roomId,
                                       "Couper l'arrivée d'eau", 10));
        plan.actions.append(makeAction(SpatialCognition::ActionType::SendNotification,
                                       "owner",
                                       "Alerter inondation", 10));
    } else if (riskInference.description.contains("réseau", Qt::CaseInsensitive)
               || riskInference.description.contains("offline", Qt::CaseInsensitive)) {
        plan.goalType = SpatialCognition::GoalType::Monitor;
        plan.actions.append(makeAction(SpatialCognition::ActionType::SendNotification,
                                       "admin",
                                       "Alerter panne réseau", 8));
    } else {
        plan.goalType = SpatialCognition::GoalType::Alert;
        plan.actions.append(makeAction(SpatialCognition::ActionType::SendNotification,
                                       "owner",
                                       QStringLiteral("Risque détecté : %1").arg(riskInference.description), 7));
    }

    plan.overallConfidence = riskInference.confidence;
    plan.explanation = QStringLiteral("Plan généré en réponse au risque : %1 (confiance %.0f%%)")
                           .arg(riskInference.description)
                           .arg(riskInference.confidence * 100);

    m_lastPlans.append(plan);
    emit planGenerated(plan.toVariantMap());
    return plan;
}

SpatialPlan SpatialPlanner::planForEvent(const QVariantMap &event)
{
    const QString type = event.value("type").toString();
    Inference fakeInf;
    fakeInf.description = event.value("description", type).toString();
    fakeInf.roomId      = event.value("roomId").toString();
    fakeInf.confidence  = event.value("confidence", 0.5).toDouble();
    return planForRisk(fakeInf);
}

SpatialPlan SpatialPlanner::planForScenario(const QVariantMap &scenario)
{
    SpatialPlan plan;
    plan.id              = QUuid::createUuid().toString(QUuid::WithoutBraces);
    plan.goalType        = SpatialCognition::GoalType::Secure;
    plan.goalDescription = QStringLiteral("Plan pour scénario : %1").arg(scenario.value("name").toString());

    plan.actions.append(makeAction(SpatialCognition::ActionType::ActivateCamera,
                                   "all",
                                   "Activer surveillance complète", 10));
    plan.actions.append(makeAction(SpatialCognition::ActionType::SendNotification,
                                   "owner",
                                   QStringLiteral("Scénario '%1' en cours").arg(scenario.value("name").toString()), 9));
    plan.actions.append(makeAction(SpatialCognition::ActionType::LaunchScenario,
                                   scenario.value("id").toString(),
                                   "Lancer la simulation", 8, scenario));

    plan.overallConfidence = 0.8;
    plan.explanation = QStringLiteral("Plan de réponse au scénario '%1'").arg(scenario.value("name").toString());

    m_lastPlans.append(plan);
    emit planGenerated(plan.toVariantMap());
    return plan;
}

// ── Export QML ──

QVariantList SpatialPlanner::plansToVariantList() const
{
    QVariantList list;
    for (const auto &p : m_lastPlans)
        list.append(p.toVariantMap());
    return list;
}

void SpatialPlanner::clearPlans()
{
    m_lastPlans.clear();
}

// ── Planification spécialisée ──

SpatialPlan SpatialPlanner::planSecure(const QVariantMap &params)
{
    SpatialPlan plan;
    plan.id              = QUuid::createUuid().toString(QUuid::WithoutBraces);
    plan.goalType        = SpatialCognition::GoalType::Secure;
    plan.goalDescription = "Sécuriser le logement";

    const QString roomId = params.value("roomId").toString();

    plan.actions.append(makeAction(SpatialCognition::ActionType::Close, roomId.isEmpty() ? "all_doors" : roomId,
                                   "Fermer les portes/fenêtres", 10));
    plan.actions.append(makeAction(SpatialCognition::ActionType::ActivateCamera, "all",
                                   "Activer toutes les caméras", 9));
    plan.actions.append(makeAction(SpatialCognition::ActionType::TurnOn, "alarm",
                                   "Activer l'alarme", 10));

    plan.overallConfidence = 0.9;
    plan.explanation = "Plan de sécurisation : fermeture, caméras, alarme";
    return plan;
}

SpatialPlan SpatialPlanner::planIlluminate(const QVariantMap & /*params*/)
{
    SpatialPlan plan;
    plan.id              = QUuid::createUuid().toString(QUuid::WithoutBraces);
    plan.goalType        = SpatialCognition::GoalType::Illuminate;
    plan.goalDescription = "Éclairer les zones nécessaires";

    if (m_context) {
        const auto occupied = m_context->occupiedRooms();
        for (const auto &roomId : occupied) {
            const auto state = m_context->roomState(roomId);
            if (!state.illuminated) {
                plan.actions.append(makeAction(SpatialCognition::ActionType::TurnOn,
                                               roomId,
                                               QStringLiteral("Allumer %1").arg(roomId), 7));
            }
        }
    }

    plan.overallConfidence = 0.95;
    plan.explanation = "Allumer les lumières dans les pièces occupées";
    return plan;
}

SpatialPlan SpatialPlanner::planVentilate(const QVariantMap &params)
{
    SpatialPlan plan;
    plan.id              = QUuid::createUuid().toString(QUuid::WithoutBraces);
    plan.goalType        = SpatialCognition::GoalType::Ventilate;
    plan.goalDescription = "Ventiler les zones à CO2 élevé";

    const QString roomId = params.value("roomId").toString();

    if (!roomId.isEmpty()) {
        plan.actions.append(makeAction(SpatialCognition::ActionType::Open, roomId,
                                       QStringLiteral("Ouvrir fenêtre — %1").arg(roomId), 7));
        plan.actions.append(makeAction(SpatialCognition::ActionType::TurnOn, roomId + "_vmc",
                                       QStringLiteral("Activer VMC — %1").arg(roomId), 6));
    }

    plan.overallConfidence = 0.85;
    plan.explanation = "Plan de ventilation pour améliorer la qualité de l'air";
    return plan;
}

SpatialPlan SpatialPlanner::planSaveEnergy(const QVariantMap &params)
{
    Q_UNUSED(params);
    SpatialPlan plan;
    plan.id              = QUuid::createUuid().toString(QUuid::WithoutBraces);
    plan.goalType        = SpatialCognition::GoalType::SaveEnergy;
    plan.goalDescription = "Économiser l'énergie";

    if (m_context) {
        const auto snap = m_context->snapshot();
        const auto rooms = snap.value("rooms").toList();
        for (const auto &r : rooms) {
            const QVariantMap rm = r.toMap();
            if (rm.value("illuminated").toBool() && !rm.value("occupied").toBool()) {
                plan.actions.append(makeAction(SpatialCognition::ActionType::TurnOff,
                                               rm.value("roomId").toString(),
                                               QStringLiteral("Éteindre %1 (vide)").arg(rm.value("roomId").toString()), 5));
            }
        }
    }

    plan.overallConfidence = 0.9;
    plan.explanation = "Éteindre les lumières dans les pièces non occupées";
    return plan;
}

SpatialPlan SpatialPlanner::planMonitor(const QVariantMap &params)
{
    SpatialPlan plan;
    plan.id              = QUuid::createUuid().toString(QUuid::WithoutBraces);
    plan.goalType        = SpatialCognition::GoalType::Monitor;
    plan.goalDescription = "Surveillance active";

    plan.actions.append(makeAction(SpatialCognition::ActionType::ActivateCamera, "all",
                                   "Activer toutes les caméras", 8));

    const QString roomId = params.value("roomId").toString();
    if (!roomId.isEmpty()) {
        plan.actions.append(makeAction(SpatialCognition::ActionType::AdjustSetting,
                                       roomId,
                                       QStringLiteral("Augmenter fréquence capteurs — %1").arg(roomId), 6,
                                       {{"sensorInterval", 5000}}));
    }

    plan.overallConfidence = 0.85;
    plan.explanation = "Plan de surveillance active avec caméras et capteurs";
    return plan;
}

SpatialPlan SpatialPlanner::planAlert(const QVariantMap &params)
{
    SpatialPlan plan;
    plan.id              = QUuid::createUuid().toString(QUuid::WithoutBraces);
    plan.goalType        = SpatialCognition::GoalType::Alert;
    plan.goalDescription = "Alerter";

    plan.actions.append(makeAction(SpatialCognition::ActionType::SendNotification,
                                   "owner",
                                   params.value("message", "Alerte spatiale").toString(), 10));
    plan.actions.append(makeAction(SpatialCognition::ActionType::TurnOn,
                                   "alarm",
                                   "Activer alarme sonore", 9));

    plan.overallConfidence = 0.95;
    plan.explanation = "Plan d'alerte immédiate";
    return plan;
}

PlannedAction SpatialPlanner::makeAction(SpatialCognition::ActionType type,
                                          const QString &targetId,
                                          const QString &description,
                                          int priority,
                                          const QVariantMap &params)
{
    PlannedAction a;
    a.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
    a.type        = type;
    a.targetId    = targetId;
    a.description = description;
    a.priority    = priority;
    a.parameters  = params;
    a.confidence  = 0.8;
    a.reason      = description;
    return a;
}
