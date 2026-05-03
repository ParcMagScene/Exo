#pragma once

#include <QString>

// ═══════════════════════════════════════════════════════
//  SafeBootTimeline — Entrée chronologique du boot
// ═══════════════════════════════════════════════════════

namespace SafeBoot {

struct SafeBootTimeline {
    QString event;
    qint64  timestamp = 0;
    QString serviceName;
    QString detail;
};

} // namespace SafeBoot
