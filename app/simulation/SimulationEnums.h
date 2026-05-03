#ifndef SIMULATIONENUMS_H
#define SIMULATIONENUMS_H

#include <QObject>
#include <QtQml/qqml.h>

// ─────────────────────────────────────────────────────
//  SimulationEnums — Types et constantes du moteur de
//  simulation spatiale EXO
// ─────────────────────────────────────────────────────

namespace Simulation {
Q_NAMESPACE
QML_ELEMENT

// ── Type de scénario ──
enum class ScenarioType {
    Fire,
    Intrusion,
    Blackout,
    NetworkFailure,
    Flood,
    Custom
};
Q_ENUM_NS(ScenarioType)

// ── Type d'entité simulée ──
enum class EntityType {
    Intruder,
    Robot,
    Smoke,
    Heat,
    Noise,
    Light,
    Water,
    CognitiveAgent
};
Q_ENUM_NS(EntityType)

// ── Type de propagation ──
enum class PropagationType {
    Diffusion,     // fumée, gaz
    Conduction,    // chaleur mur→mur
    Convection,    // chaleur air
    Attenuation,   // bruit
    ConeProjection,// lumière
    FluidFlow,     // eau
    PathBased      // trajectoire A*
};
Q_ENUM_NS(PropagationType)

// ── État d'une entité ──
enum class EntityState {
    Idle,
    Active,
    Moving,
    Spreading,
    Fading,
    Triggered,
    Destroyed
};
Q_ENUM_NS(EntityState)

// ── État de la simulation ──
enum class SimState {
    Idle,
    Running,
    Paused,
    Completed,
    Aborted
};
Q_ENUM_NS(SimState)

// ── Sévérité d'un événement ──
enum class Severity {
    Info,
    Warning,
    High,
    Critical
};
Q_ENUM_NS(Severity)

// ── Type de nœud causal ──
enum class CausalNodeType {
    Event,
    Sensor,
    Device,
    Agent,
    Propagation,
    Risk
};
Q_ENUM_NS(CausalNodeType)

// ── Constantes ──
constexpr int    kDefaultTickMs       = 100;
constexpr int    kMaxEntities         = 500;
constexpr int    kMaxTicks            = 6000;  // 10 min @ 100ms
constexpr double kDefaultPropagSpeed  = 1.0;
constexpr double kDefaultAttenuation  = 0.05;

} // namespace Simulation

#endif // SIMULATIONENUMS_H
