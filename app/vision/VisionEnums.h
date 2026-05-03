#ifndef VISIONENUMS_H
#define VISIONENUMS_H

#include <QObject>
#include <QtQml/qqml.h>

// ─────────────────────────────────────────────────────
//  VisionEnums — Types et constantes du module
//  de vision IA embarquée EXO
// ─────────────────────────────────────────────────────

namespace Vision {
Q_NAMESPACE
QML_ELEMENT

// ── Type de détection vision ──
enum class DetectionType {
    Person,
    Animal,
    Vehicle,
    Object,
    Fire,
    Smoke,
    Obstruction,        // Caméra obstruée
    Fall,               // Chute détectée
    Intrusion,          // Ligne virtuelle franchie
    Loitering,          // Errance
    Agitation,          // Comportement agité
    AbnormalMovement,   // Mouvement anormal
    ObjectDisplaced,    // Objet déplacé
    ProlongedAbsence,   // Absence prolongée
    Custom
};
Q_ENUM_NS(DetectionType)

// ── Phase du pipeline vision ──
enum class VisionPhase {
    Idle,
    Capture,
    Preprocessing,
    Inference,
    PostProcessing,
    EventRouting,
    CognitionSync
};
Q_ENUM_NS(VisionPhase)

// ── État d'une caméra ──
enum class CameraState {
    Disconnected,
    Connecting,
    Streaming,
    Paused,
    Error,
    Obstructed
};
Q_ENUM_NS(CameraState)

// ── Type de modèle IA ──
enum class VisionModel {
    ObjectDetection,
    Segmentation,
    FireSmoke,
    PoseEstimation,
    BehaviorAnalysis,
    IntrusionLine
};
Q_ENUM_NS(VisionModel)

// ── Posture détectée ──
enum class Posture {
    Unknown,
    Standing,
    Sitting,
    LyingDown,
    Crouching,
    Falling
};
Q_ENUM_NS(Posture)

// ── Comportement détecté ──
enum class Behavior {
    Normal,
    Loitering,
    Running,
    Agitated,
    Suspicious,
    Fighting,
    Wandering
};
Q_ENUM_NS(Behavior)

// ── Sévérité événement vision ──
enum class VisionSeverity {
    Info,
    Low,
    Medium,
    High,
    Critical,
    Emergency
};
Q_ENUM_NS(VisionSeverity)

// ── Constantes ──
constexpr double kDefaultConfidenceThreshold = 0.5;
constexpr double kFireConfidenceThreshold    = 0.35;
constexpr double kSmokeConfidenceThreshold   = 0.30;
constexpr double kIntrusionConfidenceMin     = 0.55;
constexpr double kFallConfidenceMin          = 0.60;
constexpr double kObstructionThreshold       = 0.80;   // % pixels bloqués
constexpr int    kMaxDetectionsPerFrame      = 100;
constexpr int    kMaxVisionEvents            = 5000;
constexpr int    kVisionMemoryRetentionDays  = 365;
constexpr int    kDefaultFps                 = 15;
constexpr int    kFrameBufferSize            = 30;

} // namespace Vision

#endif // VISIONENUMS_H
