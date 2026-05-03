#pragma once

#include <QString>
#include "SafeBootEnums.h"

// ═══════════════════════════════════════════════════════
//  SafeBootState — État d'un service vu par le Safe Boot
// ═══════════════════════════════════════════════════════

namespace SafeBoot {

struct SafeBootState {
    QString             name;
    ServiceCriticality  criticality = ServiceCriticality::NonCritical;
    ServiceStatus       status      = ServiceStatus::Pending;
    qint64              responseTimeMs = -1;
    QString             lastError;
};

} // namespace SafeBoot
