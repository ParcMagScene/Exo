// =============================================================================
//  Hardening.h — Macros et helpers défensifs C++ pour EXO (2026)
// -----------------------------------------------------------------------------
//  Politique :
//    - JAMAIS de modification de VoicePipeline.cpp, AudioEngine.cpp,
//      WebSocketClient.cpp, OrpheusDecoder.cpp.
//    - Les macros ci-dessous sont OPT-IN : on les utilise là où une protection
//      additionnelle a du sens (init de modules, chargement de fichiers,
//      callbacks externes, parsing JSON, dispatch d'outils, etc.).
//    - Toutes les macros routent leur log via qWarning / qCritical, donc via
//      LogManager → panneau « Journaux » de la GUI (déjà francisé).
//    - Aucune exception lancée : on retourne / on early-exit proprement.
// =============================================================================
#pragma once

#include <QtCore/QDebug>
#include <QtCore/QElapsedTimer>
#include <QtCore/QHash>
#include <QtCore/QMutex>
#include <QtCore/QString>

// ---- Vérifications de pointeurs ---------------------------------------------
#define EXO_REQUIRE_PTR(ptr, msgFr)                                            \
    do {                                                                       \
        if ((ptr) == nullptr) {                                                \
            qWarning() << "[Hardening] Pointeur nul :" << (msgFr);             \
            return;                                                            \
        }                                                                      \
    } while (0)

#define EXO_REQUIRE_PTR_RET(ptr, msgFr, retVal)                                \
    do {                                                                       \
        if ((ptr) == nullptr) {                                                \
            qWarning() << "[Hardening] Pointeur nul :" << (msgFr);             \
            return (retVal);                                                   \
        }                                                                      \
    } while (0)

// ---- Vérifications de buffers / tailles -------------------------------------
#define EXO_REQUIRE_SIZE(value, minSz, msgFr)                                  \
    do {                                                                       \
        if (static_cast<qsizetype>(value) < static_cast<qsizetype>(minSz)) {   \
            qWarning() << "[Hardening] Taille insuffisante :" << (msgFr)       \
                       << "(" << (value) << "<" << (minSz) << ")";             \
            return;                                                            \
        }                                                                      \
    } while (0)

#define EXO_REQUIRE_RANGE(value, lo, hi, msgFr)                                \
    do {                                                                       \
        const auto _v = (value);                                               \
        if (_v < (lo) || _v > (hi)) {                                          \
            qWarning() << "[Hardening] Valeur hors borne :" << (msgFr)         \
                       << _v << "∉ [" << (lo) << "," << (hi) << "]";           \
            return;                                                            \
        }                                                                      \
    } while (0)

// ---- Division par zéro ------------------------------------------------------
#define EXO_SAFE_DIV(num, den, fallback)                                       \
    (((den) != 0) ? ((num) / (den)) : (fallback))

// ---- Retour d'erreur d'API --------------------------------------------------
#define EXO_REQUIRE_OK(expr, msgFr)                                            \
    do {                                                                       \
        if (!(expr)) {                                                         \
            qWarning() << "[Hardening] Échec d'appel :" << (msgFr);            \
            return;                                                            \
        }                                                                      \
    } while (0)

// ---- État invalide ----------------------------------------------------------
#define EXO_REQUIRE_STATE(cond, msgFr)                                         \
    do {                                                                       \
        if (!(cond)) {                                                         \
            qWarning() << "[Hardening] État invalide :" << (msgFr);            \
            return;                                                            \
        }                                                                      \
    } while (0)

namespace exo {
namespace hardening {

// ---- Throttle de reconnexion ------------------------------------------------
/**
 * Empêche les reconnexions / actions répétées trop rapidement.
 * Usage :
 *     static exo::hardening::Throttle t(500); // 500 ms minimum
 *     if (!t.allow("ws_reconnect")) return;
 */
class Throttle {
public:
    explicit Throttle(int minIntervalMs) : m_minIntervalMs(minIntervalMs) {}

    bool allow(const QString& key) {
        QMutexLocker lock(&m_mutex);
        QElapsedTimer& timer = m_timers[key];
        if (!timer.isValid()) {
            timer.start();
            return true;
        }
        if (timer.elapsed() < m_minIntervalMs) {
            return false;
        }
        timer.restart();
        return true;
    }

    void reset(const QString& key) {
        QMutexLocker lock(&m_mutex);
        m_timers.remove(key);
    }

private:
    int m_minIntervalMs;
    QHash<QString, QElapsedTimer> m_timers;
    QMutex m_mutex;
};

// ---- Backoff exponentiel borné ---------------------------------------------
class ExpBackoff {
public:
    ExpBackoff(int initialMs = 250, int maxMs = 30000, double factor = 2.0)
        : m_initialMs(initialMs), m_maxMs(maxMs), m_factor(factor),
          m_currentMs(initialMs) {}

    int next() {
        const int v = m_currentMs;
        m_currentMs = qMin(m_maxMs,
                           static_cast<int>(m_currentMs * m_factor));
        return v;
    }

    void reset() { m_currentMs = m_initialMs; }
    int current() const { return m_currentMs; }

private:
    int m_initialMs;
    int m_maxMs;
    double m_factor;
    int m_currentMs;
};

// ---- Détection de latence audio anormale -----------------------------------
/**
 * Surveille les écarts entre frames audio. Retourne true si la latence dépasse
 * le seuil (à utiliser dans un callback non critique, pour log uniquement).
 */
class LatencyWatchdog {
public:
    explicit LatencyWatchdog(int thresholdMs) : m_thresholdMs(thresholdMs) {}

    bool tick() {
        if (!m_timer.isValid()) {
            m_timer.start();
            return false;
        }
        const qint64 elapsed = m_timer.restart();
        if (elapsed > m_thresholdMs) {
            qWarning() << "[Hardening] Latence anormale détectée :"
                       << elapsed << "ms (seuil" << m_thresholdMs << "ms)";
            return true;
        }
        return false;
    }

    void reset() { m_timer.invalidate(); }

private:
    int m_thresholdMs;
    QElapsedTimer m_timer;
};

} // namespace hardening
} // namespace exo
