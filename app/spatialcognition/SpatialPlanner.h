#ifndef SPATIALPLANNER_H
#define SPATIALPLANNER_H

#include "SpatialEnums.h"
#include "SpatialReasoner.h"

#include <QObject>
#include <QString>
#include <QVector>
#include <QVariantMap>
#include <QVariantList>

// ─────────────────────────────────────────────────────
//  PlannedAction — Action planifiée par le planificateur
// ─────────────────────────────────────────────────────
struct PlannedAction
{
    QString id;
    SpatialCognition::ActionType type = SpatialCognition::ActionType::Custom;
    QString targetId;      // device, camera, room, etc.
    QString description;
    QVariantMap parameters;
    int     priority   = 5;
    double  confidence = 0.5;
    QString reason;        // justification

    QVariantMap toVariantMap() const;
};

// ─────────────────────────────────────────────────────
//  SpatialPlan — Plan d'actions ordonné
// ─────────────────────────────────────────────────────
struct SpatialPlan
{
    QString id;
    QString goalDescription;
    SpatialCognition::GoalType goalType = SpatialCognition::GoalType::Custom;
    QVector<PlannedAction> actions;
    double  overallConfidence = 0.0;
    QString explanation;

    QVariantMap toVariantMap() const;
    int actionCount() const { return actions.size(); }
};

// ─────────────────────────────────────────────────────
//  SpatialPlanner — Planificateur spatial HTN
//
//  Génère des plans d'actions pour atteindre des objectifs
//  spatiaux : sécuriser, éclairer, ventiler, économiser
//  énergie, surveiller.
//
//  Sources : Inférences du SpatialReasoner
// ─────────────────────────────────────────────────────
class SpatialPlanner : public QObject
{
    Q_OBJECT

public:
    explicit SpatialPlanner(QObject *parent = nullptr);
    ~SpatialPlanner() override;

    // ── Configuration ──
    void setKnowledgeGraph(SpatialKnowledgeGraph *graph);
    void setContext(SpatialContext *context);

    // ── Planification par objectif ──
    SpatialPlan planForGoal(SpatialCognition::GoalType goal, const QVariantMap &params = {});
    SpatialPlan planForRisk(const Inference &riskInference);
    SpatialPlan planForEvent(const QVariantMap &event);
    SpatialPlan planForScenario(const QVariantMap &scenario);

    // ── Accès aux plans ──
    const QVector<SpatialPlan> &lastPlans() const { return m_lastPlans; }

    // ── Export QML ──
    QVariantList plansToVariantList() const;

    // ── Clear ──
    void clearPlans();

signals:
    void planGenerated(const QVariantMap &plan);

private:
    SpatialPlan planSecure(const QVariantMap &params);
    SpatialPlan planIlluminate(const QVariantMap &params);
    SpatialPlan planVentilate(const QVariantMap &params);
    SpatialPlan planSaveEnergy(const QVariantMap &params);
    SpatialPlan planMonitor(const QVariantMap &params);
    SpatialPlan planAlert(const QVariantMap &params);

    PlannedAction makeAction(SpatialCognition::ActionType type,
                             const QString &targetId,
                             const QString &description,
                             int priority = 5,
                             const QVariantMap &params = {});

    SpatialKnowledgeGraph *m_graph   = nullptr;
    SpatialContext         *m_context = nullptr;
    QVector<SpatialPlan>    m_lastPlans;
};

#endif // SPATIALPLANNER_H
