#ifndef SPATIALREASONER_H
#define SPATIALREASONER_H

#include "SpatialEnums.h"
#include "SpatialKnowledgeGraph.h"
#include "SpatialContext.h"

#include <QObject>
#include <QString>
#include <QVector>
#include <QVariantMap>
#include <QVariantList>

// ─────────────────────────────────────────────────────
//  SpatialRule — Règle d'inférence spatiale
// ─────────────────────────────────────────────────────
struct SpatialRule
{
    QString id;
    QString name;
    QString description;
    SpatialCognition::InferenceType type = SpatialCognition::InferenceType::RuleBased;
    double  priority   = 1.0;
    bool    enabled    = true;

    // Conditions : liste de prédicats {field, operator, value}
    QVariantList conditions;
    // Actions résultantes si la règle match
    QVariantList conclusions;

    QVariantMap toVariantMap() const;
};

// ─────────────────────────────────────────────────────
//  Inference — Résultat d'une inférence
// ─────────────────────────────────────────────────────
struct Inference
{
    QString id;
    QString ruleId;
    QString description;
    SpatialCognition::InferenceType type = SpatialCognition::InferenceType::RuleBased;
    SpatialCognition::CognitiveSeverity severity = SpatialCognition::CognitiveSeverity::Info;
    double  confidence = 0.0;
    QString roomId;
    QVariantMap data;
    QVariantList evidence;     // liste de faits ayant déclenché l'inférence
    QString explanation;

    QVariantMap toVariantMap() const;
};

// ─────────────────────────────────────────────────────
//  SpatialReasoner — Moteur d'inférence spatiale
//
//  Applique des règles (if/then), causalité spatiale,
//  propagation logique, détection d'incohérences/risques,
//  et génère des explications.
//
//  Sources : SpatialKnowledgeGraph, SpatialContext
// ─────────────────────────────────────────────────────
class SpatialReasoner : public QObject
{
    Q_OBJECT

public:
    explicit SpatialReasoner(QObject *parent = nullptr);
    ~SpatialReasoner() override;

    // ── Configuration ──
    void setKnowledgeGraph(SpatialKnowledgeGraph *graph);
    void setContext(SpatialContext *context);
    void addRule(const SpatialRule &rule);
    void removeRule(const QString &ruleId);
    void setRuleEnabled(const QString &ruleId, bool enabled);
    int ruleCount() const { return m_rules.size(); }

    // ── Inférence ──
    QVector<Inference> infer();
    QVector<Inference> detectAnomalies();
    QVector<Inference> detectRisks();

    // ── Explication ──
    QString explain(const QString &eventId) const;
    QString explain(const Inference &inference) const;

    // ── Accès aux résultats ──
    const QVector<Inference> &lastInferences() const { return m_lastInferences; }

    // ── Export QML ──
    QVariantList inferencesToVariantList() const;
    QVariantList rulesToVariantList() const;

    // ── Règles par défaut ──
    void loadDefaultRules();

    // ── Clear ──
    void clearRules();
    void clearInferences();

signals:
    void inferenceCompleted(int count);
    void anomalyDetected(const QVariantMap &anomaly);
    void riskDetected(const QVariantMap &risk);

private:
    bool evaluateConditions(const SpatialRule &rule) const;
    bool evaluateCondition(const QVariantMap &condition) const;
    Inference buildInference(const SpatialRule &rule, const QVariantList &evidence) const;
    QVariantList gatherEvidence(const SpatialRule &rule) const;

    SpatialKnowledgeGraph  *m_graph   = nullptr;
    SpatialContext          *m_context = nullptr;
    QVector<SpatialRule>     m_rules;
    QVector<Inference>       m_lastInferences;
};

#endif // SPATIALREASONER_H
