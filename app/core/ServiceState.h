#pragma once

#include <QObject>
#include <QString>

// ═══════════════════════════════════════════════════════
//  ServiceState — Machine à états pour les microservices EXO v5
//
//  STOPPED → STARTING → WAITING_READY → READY
//                ↓            ↓
//             FAILED ← ─ ─ ─ ┘
//                ↓
//          RESTARTING → STARTING ...
//
//  READY → CRASHED → RESTARTING → STARTING ...
// ═══════════════════════════════════════════════════════

namespace Exo {

enum class ServiceState {
    Stopped,          // Pas démarré
    Starting,         // QProcess lancé, en attente du port
    WaitingReady,     // Port ouvert, en attente du message READY
    Ready,            // Service opérationnel (ready reçu)
    Failed,           // Échec au démarrage (timeout ou erreur)
    Crashed,          // Était Ready puis processus mort
    Restarting        // Tentative de redémarrage en cours
};

// v5.1: TTS advanced readiness sub-phases
enum class ReadinessPhase {
    None,             // Not applicable (non-TTS services)
    Init,             // Python lancé
    Loading,          // Modèle XTTS en cours de chargement
    Warmup,           // GPU + DSP en préchauffage
    Online            // Service pleinement opérationnel
};

inline QString serviceStateToString(ServiceState s) {
    switch (s) {
    case ServiceState::Stopped:       return QStringLiteral("stopped");
    case ServiceState::Starting:      return QStringLiteral("starting");
    case ServiceState::WaitingReady:  return QStringLiteral("waiting_ready");
    case ServiceState::Ready:         return QStringLiteral("ready");
    case ServiceState::Failed:        return QStringLiteral("failed");
    case ServiceState::Crashed:       return QStringLiteral("crashed");
    case ServiceState::Restarting:    return QStringLiteral("restarting");
    }
    return QStringLiteral("unknown");
}

inline QString readinessPhaseToString(ReadinessPhase p) {
    switch (p) {
    case ReadinessPhase::None:     return QStringLiteral("none");
    case ReadinessPhase::Init:     return QStringLiteral("ready_init");
    case ReadinessPhase::Loading:  return QStringLiteral("ready_loading");
    case ReadinessPhase::Warmup:   return QStringLiteral("ready_warmup");
    case ReadinessPhase::Online:   return QStringLiteral("ready_online");
    }
    return QStringLiteral("none");
}

inline ReadinessPhase readinessPhaseFromString(const QString &s) {
    if (s == QLatin1String("ready_init"))    return ReadinessPhase::Init;
    if (s == QLatin1String("ready_loading")) return ReadinessPhase::Loading;
    if (s == QLatin1String("ready_warmup"))  return ReadinessPhase::Warmup;
    if (s == QLatin1String("ready_online"))  return ReadinessPhase::Online;
    return ReadinessPhase::None;
}

} // namespace Exo
