#ifndef SPATIALENUMS_H
#define SPATIALENUMS_H

#include <QObject>
#include <QtQml/qqml.h>

// ─────────────────────────────────────────────────────
//  SpatialEnums — Types et constantes du module de
//  cognition spatiale EXO
// ─────────────────────────────────────────────────────

namespace SpatialCognition {
Q_NAMESPACE
QML_ELEMENT

// ── Type de relation spatiale ──
enum class SpatialRelation {
    Adjacent,
    Accessible,
    Visible,
    Covered,
    Dangerous,
    Occupied,
    Illuminated,
    Hot,
    Cold,
    Noisy,
    Silent,
    Connected,
    Blocked
};
Q_ENUM_NS(SpatialRelation)

// ── Type de nœud dans le graphe de connaissances ──
enum class KnowledgeNodeType {
    Room,
    Wall,
    Door,
    Window,
    Object,
    Sensor,
    Camera,
    Device,
    NetworkLink,
    Zone
};
Q_ENUM_NS(KnowledgeNodeType)

// ── Type d'inférence du raisonneur ──
enum class InferenceType {
    RuleBased,
    Causal,
    Propagation,
    Anomaly,
    Risk
};
Q_ENUM_NS(InferenceType)

// ── Sévérité cognitive ──
enum class CognitiveSeverity {
    Info,
    Low,
    Medium,
    High,
    Critical
};
Q_ENUM_NS(CognitiveSeverity)

// ── Type de but pour le planificateur ──
enum class GoalType {
    Secure,
    Illuminate,
    Ventilate,
    SaveEnergy,
    Monitor,
    Alert,
    Custom
};
Q_ENUM_NS(GoalType)

// ── Type d'action planifiée ──
enum class ActionType {
    TurnOn,
    TurnOff,
    Open,
    Close,
    ActivateCamera,
    DeactivateCamera,
    SendNotification,
    LaunchScenario,
    AdjustSetting,
    RequestHuman,
    Custom
};
Q_ENUM_NS(ActionType)

// ── État du cycle cognitif ──
enum class CognitivePhase {
    Idle,
    Perception,
    Symbolic,
    Inference,
    Planning,
    Simulation,
    Decision,
    Supervision,
    Execution
};
Q_ENUM_NS(CognitivePhase)

// ── Décision du superviseur ──
enum class SupervisorDecision {
    Approved,
    Modified,
    Rejected,
    NeedsReview,
    Deferred
};
Q_ENUM_NS(SupervisorDecision)

// ── Constantes ──
constexpr int    kMaxKnowledgeNodes     = 2000;
constexpr int    kMaxInferenceRules     = 500;
constexpr int    kMaxPlanDepth          = 20;
constexpr int    kMemoryRetentionDays   = 365;
constexpr double kDefaultRiskThreshold  = 0.6;
constexpr double kDefaultConfidence     = 0.5;

} // namespace SpatialCognition

#endif // SPATIALENUMS_H
