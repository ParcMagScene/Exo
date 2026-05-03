#include "SpatialSupervisor.h"

// ─────────────────────────────────────────────────────
//  ValidationResult
// ─────────────────────────────────────────────────────

QVariantMap ValidationResult::toVariantMap() const
{
    QVariantList warnList;
    for (const auto &w : warnings)
        warnList.append(w);

    return {
        {"approved",  approved},
        {"reason",    reason},
        {"riskScore", riskScore},
        {"warnings",  warnList}
    };
}

// ─────────────────────────────────────────────────────
//  SpatialSupervisor
// ─────────────────────────────────────────────────────

SpatialSupervisor::SpatialSupervisor(QObject *parent)
    : QObject(parent)
{
}

SpatialSupervisor::~SpatialSupervisor() = default;

void SpatialSupervisor::setContext(SpatialContext *context) { m_context = context; }
void SpatialSupervisor::setMemory(SpatialMemory *memory)   { m_memory  = memory;  }

void   SpatialSupervisor::setRiskThreshold(double t)     { m_riskThreshold = t; }
double SpatialSupervisor::riskThreshold() const           { return m_riskThreshold; }

void SpatialSupervisor::setMaxActionsPerPlan(int n)       { m_maxActionsPerPlan = n; }
int  SpatialSupervisor::maxActionsPerPlan() const         { return m_maxActionsPerPlan; }

// ── Validation d'un plan complet ──

ValidationResult SpatialSupervisor::validatePlan(const SpatialPlan &plan)
{
    ValidationResult result;
    result.approved = true;
    result.riskScore = 0.0;

    // 1) Nombre d'actions
    if (plan.actionCount() > m_maxActionsPerPlan) {
        result.warnings.append(QStringLiteral("Plan contient %1 actions (max %2)")
                                   .arg(plan.actionCount())
                                   .arg(m_maxActionsPerPlan));
    }

    // 2) Confiance globale trop basse
    if (plan.overallConfidence < 0.3) {
        result.warnings.append(QStringLiteral("Confiance très basse : %.0f%%")
                                   .arg(plan.overallConfidence * 100));
    }

    // 3) Valider chaque action individuellement
    double maxActionRisk = 0.0;
    for (const auto &action : plan.actions) {
        auto actionResult = validateAction(action);
        if (!actionResult.approved) {
            result.warnings.append(QStringLiteral("Action refusée : %1 — %2")
                                       .arg(action.description, actionResult.reason));
        }
        maxActionRisk = qMax(maxActionRisk, actionResult.riskScore);
        result.riskScore = qMax(result.riskScore, actionResult.riskScore);
    }

    // 4) Vérifier la cohérence interne
    if (!checkCoherence(plan)) {
        result.warnings.append("Incohérence détectée dans le plan (actions contradictoires)");
        result.riskScore = qMax(result.riskScore, 0.5);
    }

    // 5) Vérifier le précédent historique
    if (!checkHistoricalPrecedent(plan)) {
        result.warnings.append("Aucun précédent historique pour ce type de plan");
    }

    // 6) Décision finale
    if (result.riskScore > m_riskThreshold) {
        result.approved = false;
        result.reason = QStringLiteral("Score de risque trop élevé : %.0f%% (seuil %.0f%%)")
                            .arg(result.riskScore * 100)
                            .arg(m_riskThreshold * 100);
    } else if (!result.warnings.isEmpty()) {
        result.reason = QStringLiteral("Approuvé avec %1 avertissement(s)")
                            .arg(result.warnings.size());
    } else {
        result.reason = "Approuvé sans réserve";
    }

    m_lastResult = result;
    m_history.append({plan.id, result, result.approved
                                        ? SpatialCognition::SupervisorDecision::Approved
                                        : SpatialCognition::SupervisorDecision::Rejected});
    return result;
}

// ── Validation d'une action isolée ──

ValidationResult SpatialSupervisor::validateAction(const PlannedAction &action)
{
    ValidationResult result;
    result.approved = true;
    result.riskScore = evaluateActionRisk(action);

    if (!checkSecurityConstraints(action)) {
        result.approved  = false;
        result.riskScore = 1.0;
        result.reason    = "Contrainte de sécurité violée";
        return result;
    }

    if (result.riskScore > m_riskThreshold) {
        result.approved = false;
        result.reason = QStringLiteral("Risque trop élevé pour l'action '%1'").arg(action.description);
    } else {
        result.reason = "Action validée";
    }

    return result;
}

// ── Décision du superviseur ──

SpatialCognition::SupervisorDecision SpatialSupervisor::approveOrReject(const SpatialPlan &plan)
{
    auto result = validatePlan(plan);

    if (result.approved && result.warnings.isEmpty()) {
        emit planApproved(plan.toVariantMap());
        return SpatialCognition::SupervisorDecision::Approved;
    }

    if (result.approved && !result.warnings.isEmpty()) {
        emit planModified(plan.toVariantMap(), result.warnings);
        return SpatialCognition::SupervisorDecision::Modified;
    }

    emit planRejected(plan.toVariantMap(), result.reason);
    return SpatialCognition::SupervisorDecision::Rejected;
}

// ── Historique ──

QVariantList SpatialSupervisor::validationHistory() const
{
    QVariantList list;
    for (const auto &e : m_history) {
        QVariantMap entry;
        entry["planId"]   = e.planId;
        entry["result"]   = e.result.toVariantMap();
        entry["decision"] = static_cast<int>(e.decision);
        list.append(entry);
    }
    return list;
}

void SpatialSupervisor::clearHistory()
{
    m_history.clear();
}

QVariantMap SpatialSupervisor::lastValidation() const
{
    return m_lastResult.toVariantMap();
}

// ── Évaluation du risque d'une action ──

double SpatialSupervisor::evaluateActionRisk(const PlannedAction &action) const
{
    // Actions à haut risque intrinsèque
    switch (action.type) {
    case SpatialCognition::ActionType::Open:
        return 0.4;   // ouvrir porte/fenêtre = risque modéré
    case SpatialCognition::ActionType::Close:
        return 0.2;
    case SpatialCognition::ActionType::TurnOn:
    case SpatialCognition::ActionType::TurnOff:
        return 0.1;
    case SpatialCognition::ActionType::ActivateCamera:
        return 0.05;
    case SpatialCognition::ActionType::SendNotification:
        return 0.0;
    case SpatialCognition::ActionType::AdjustSetting:
        return 0.15;
    case SpatialCognition::ActionType::LaunchScenario:
        return 0.5;   // lancer un scénario = risque élevé
    case SpatialCognition::ActionType::RequestHuman:
        return 0.0;
    case SpatialCognition::ActionType::Custom:
        return 0.6;   // inconnu = conservateur
    }
    return 0.3;
}

// ── Vérifications de sécurité ──

bool SpatialSupervisor::checkSecurityConstraints(const PlannedAction &action) const
{
    // Interdire d'ouvrir des portes si alerte intrusion active
    if (action.type == SpatialCognition::ActionType::Open && m_context) {
        const auto alerts = m_context->alertRooms();
        for (const auto &roomId : alerts) {
            if (action.targetId == roomId || action.targetId.contains("door")) {
                return false;   // ne pas ouvrir pendant une alerte
            }
        }
    }

    // Interdire d'éteindre l'alarme si risque global élevé
    if (action.type == SpatialCognition::ActionType::TurnOff
        && action.targetId == "alarm"
        && m_context
        && m_context->globalRiskLevel() > 0.5) {
        return false;
    }

    return true;
}

// ── Cohérence interne du plan ──

bool SpatialSupervisor::checkCoherence(const SpatialPlan &plan) const
{
    // Détecter des contradictions : TurnOn + TurnOff sur la même cible
    QHash<QString, SpatialCognition::ActionType> seen;
    for (const auto &a : plan.actions) {
        if (seen.contains(a.targetId)) {
            auto prev = seen[a.targetId];
            if ((prev == SpatialCognition::ActionType::TurnOn  && a.type == SpatialCognition::ActionType::TurnOff)
                || (prev == SpatialCognition::ActionType::TurnOff && a.type == SpatialCognition::ActionType::TurnOn)
                || (prev == SpatialCognition::ActionType::Open    && a.type == SpatialCognition::ActionType::Close)
                || (prev == SpatialCognition::ActionType::Close   && a.type == SpatialCognition::ActionType::Open)) {
                return false;
            }
        }
        seen[a.targetId] = a.type;
    }
    return true;
}

// ── Précédent historique ──

bool SpatialSupervisor::checkHistoricalPrecedent(const SpatialPlan &plan) const
{
    if (!m_memory)
        return true;   // pas de mémoire = on ne peut pas vérifier

    const auto pastDecisions = m_memory->retrievePastDecisions(5);
    for (const auto &d : pastDecisions) {
        const auto data = d.toVariantMap();
        if (data.value("goalType").toInt() == static_cast<int>(plan.goalType))
            return true;   // un précédent trouvé
    }

    return false;
}
