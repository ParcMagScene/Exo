#ifndef SPATIALSECURITYENUMS_H
#define SPATIALSECURITYENUMS_H

#include <QObject>
#include <QtQml/qqml.h>

// ─────────────────────────────────────────────────────
//  SpatialSecurityEnums — Types et constantes du module
//  de sécurité spatiale EXO
// ─────────────────────────────────────────────────────

namespace SpatialSecurity {
Q_NAMESPACE
QML_ELEMENT

// ── Type de risque sécurité ──
enum class RiskType {
    Intrusion,
    Fire,
    Smoke,
    Electrical,
    NetworkFailure,
    DomoticAnomaly,
    Flood,
    GasLeak,
    SuspiciousActivity,
    Unauthorized,
    Custom
};
Q_ENUM_NS(RiskType)

// ── Sévérité sécurité ──
enum class SecuritySeverity {
    Info,
    Low,
    Medium,
    High,
    Critical,
    Emergency
};
Q_ENUM_NS(SecuritySeverity)

// ── Phase du cycle sécurité ──
enum class SecurityPhase {
    Idle,
    Perception,
    Analysis,
    Detection,
    RiskAssessment,
    ActionPlanning,
    Supervision
};
Q_ENUM_NS(SecurityPhase)

// ── Type de détecteur ──
enum class DetectorType {
    Intrusion,
    Fire,
    Electrical,
    Network,
    Domotic
};
Q_ENUM_NS(DetectorType)

// ── Type d'action sécurité ──
enum class SecurityActionType {
    LockDoors,
    UnlockDoors,
    ActivateAlarm,
    DeactivateAlarm,
    ActivateCamera,
    CutPower,
    CallEmergency,
    SendAlert,
    ActivateSprinklers,
    OpenWindows,
    ShutdownDevice,
    RestartDevice,
    IsolateZone,
    EvacuateZone,
    Custom
};
Q_ENUM_NS(SecurityActionType)

// ── État d'un sous-système de sécurité ──
enum class SubsystemStatus {
    Normal,
    Warning,
    Alert,
    Critical,
    Offline,
    Unknown
};
Q_ENUM_NS(SubsystemStatus)

// ── Constantes ──
constexpr double kFireTemperatureThreshold   = 50.0;   // °C
constexpr double kSmokeThreshold             = 0.3;    // 0..1
constexpr double kHighLatencyMs              = 500.0;
constexpr double kElectricalOverloadWatts    = 3500.0;
constexpr double kCO2DangerLevel             = 1500.0; // ppm
constexpr int    kMaxSecurityIncidents       = 10000;
constexpr int    kSecurityMemoryRetentionDays = 730;    // 2 ans
constexpr double kDefaultSecurityThreshold   = 0.5;
constexpr double kIntrusionConfidenceMin     = 0.6;
constexpr double kFireConfidenceMin          = 0.4;

} // namespace SpatialSecurity

#endif // SPATIALSECURITYENUMS_H
