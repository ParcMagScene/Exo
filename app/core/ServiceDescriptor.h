#pragma once

#include <QString>
#include <QStringList>
#include <QJsonObject>
#include <QJsonArray>

// ═══════════════════════════════════════════════════════
//  ServiceDescriptor — Description statique d'un microservice EXO v5
//
//  Chargé depuis services.json enrichi. Contient toutes les
//  métadonnées nécessaires au lancement et à la supervision.
// ═══════════════════════════════════════════════════════

namespace Exo {

struct RetryPolicy {
    int     baseMs       = 250;    // Délai initial
    int     maxMs        = 8000;   // Plafond
    int     maxAttempts  = 7;      // Abandon après N tentatives
    bool    exponential  = true;   // Backoff exponentiel

    int delayForAttempt(int attempt) const {
        if (!exponential) return baseMs;
        int delay = baseMs * (1 << qMin(attempt, 5));
        return qMin(delay, maxMs);
    }

    static RetryPolicy fromJson(const QJsonObject &obj) {
        RetryPolicy rp;
        rp.baseMs      = obj.value(QStringLiteral("base_ms")).toInt(250);
        rp.maxMs        = obj.value(QStringLiteral("max_ms")).toInt(8000);
        rp.maxAttempts  = obj.value(QStringLiteral("max_attempts")).toInt(7);
        rp.exponential  = obj.value(QStringLiteral("exponential")).toBool(true);
        return rp;
    }
};

struct ServiceDescriptor {
    QString     name;
    int         port        = 0;
    QString     venv;           // e.g. ".venv_stt_tts"
    QString     script;         // relative path
    QStringList args;

    // v5 extensions
    int         startupTimeoutMs  = 30000;  // Temps max pour atteindre Ready
    int         readinessTimeoutMs = 10000; // Temps max entre WaitingReady → Ready
    RetryPolicy retryPolicy;
    QStringList dependencies;               // Noms des services qui doivent être Ready avant

    static ServiceDescriptor fromJson(const QJsonObject &obj) {
        ServiceDescriptor sd;
        sd.name   = obj.value(QStringLiteral("name")).toString().toLower();
        sd.port   = obj.value(QStringLiteral("port")).toInt();
        sd.venv   = obj.value(QStringLiteral("venv")).toString();
        sd.script = obj.value(QStringLiteral("script")).toString();

        const QJsonArray argsArr = obj.value(QStringLiteral("args")).toArray();
        for (const QJsonValue &a : argsArr)
            sd.args << a.toString();

        sd.startupTimeoutMs   = obj.value(QStringLiteral("startup_timeout_ms")).toInt(30000);
        sd.readinessTimeoutMs = obj.value(QStringLiteral("readiness_timeout_ms")).toInt(10000);

        if (obj.contains(QStringLiteral("retry_policy")))
            sd.retryPolicy = RetryPolicy::fromJson(obj.value(QStringLiteral("retry_policy")).toObject());

        const QJsonArray deps = obj.value(QStringLiteral("dependencies")).toArray();
        for (const QJsonValue &d : deps)
            sd.dependencies << d.toString();

        return sd;
    }
};

} // namespace Exo
