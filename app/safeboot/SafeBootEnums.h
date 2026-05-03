#pragma once

#include <QString>

// ═══════════════════════════════════════════════════════
//  SafeBootEnums — Enums du module Safe Boot EXO v30.2
// ═══════════════════════════════════════════════════════

namespace SafeBoot {

enum class ServiceCriticality {
    Critical,
    NonCritical
};

enum class ServiceStatus {
    Pending,
    Ready,
    Failed,
    Degraded
};

inline QString criticalityToString(ServiceCriticality c) {
    switch (c) {
    case ServiceCriticality::Critical:    return QStringLiteral("critical");
    case ServiceCriticality::NonCritical: return QStringLiteral("non_critical");
    }
    return QStringLiteral("unknown");
}

inline QString statusToString(ServiceStatus s) {
    switch (s) {
    case ServiceStatus::Pending:  return QStringLiteral("pending");
    case ServiceStatus::Ready:    return QStringLiteral("ready");
    case ServiceStatus::Failed:   return QStringLiteral("failed");
    case ServiceStatus::Degraded: return QStringLiteral("degraded");
    }
    return QStringLiteral("unknown");
}

} // namespace SafeBoot
