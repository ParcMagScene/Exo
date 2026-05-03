#ifndef SPATIALSUPERVISOR_H
#define SPATIALSUPERVISOR_H

#include <QObject>
#include <QString>
#include <QVariantMap>
#include <QVector>

#include "SpatialEnums.h"
#include "SpatialPlanner.h"
#include "SpatialContext.h"
#include "SpatialMemory.h"

// ─────────────────────────────────────────────────────
//  Résultat de validation d'une action / d'un plan
// ─────────────────────────────────────────────────────

struct ValidationResult {
    bool        approved       = false;
    QString     reason;
    double      riskScore      = 0.0;   // 0..1
    QStringList warnings;

    QVariantMap toVariantMap() const;
};

// ─────────────────────────────────────────────────────
//  SpatialSupervisor — couche de gouvernance cognitive
//  Valide, approuve ou rejette les plans avant exécution.
// ─────────────────────────────────────────────────────

class SpatialSupervisor : public QObject
{
    Q_OBJECT

public:
    explicit SpatialSupervisor(QObject *parent = nullptr);
    ~SpatialSupervisor() override;

    // ── Dépendances ──
    void setContext(SpatialContext *context);
    void setMemory(SpatialMemory *memory);

    // ── Seuils ──
    void   setRiskThreshold(double t);
    double riskThreshold() const;

    void setMaxActionsPerPlan(int n);
    int  maxActionsPerPlan() const;

    // ── Validation ──
    ValidationResult validatePlan(const SpatialPlan &plan);
    ValidationResult validateAction(const PlannedAction &action);
    SpatialCognition::SupervisorDecision approveOrReject(const SpatialPlan &plan);

    // ── Historique ──
    QVariantList validationHistory() const;
    void clearHistory();

    // ── Export QML ──
    Q_INVOKABLE QVariantMap lastValidation() const;

signals:
    void planApproved(const QVariantMap &plan);
    void planRejected(const QVariantMap &plan, const QString &reason);
    void planModified(const QVariantMap &plan, const QStringList &warnings);

private:
    double evaluateActionRisk(const PlannedAction &action) const;
    bool   checkSecurityConstraints(const PlannedAction &action) const;
    bool   checkCoherence(const SpatialPlan &plan) const;
    bool   checkHistoricalPrecedent(const SpatialPlan &plan) const;

    SpatialContext *m_context = nullptr;
    SpatialMemory  *m_memory  = nullptr;

    double m_riskThreshold      = SpatialCognition::kDefaultRiskThreshold;
    int    m_maxActionsPerPlan  = 20;

    struct ValidationEntry {
        QString          planId;
        ValidationResult result;
        SpatialCognition::SupervisorDecision decision;
    };
    QVector<ValidationEntry> m_history;
    ValidationResult         m_lastResult;
};

#endif // SPATIALSUPERVISOR_H
