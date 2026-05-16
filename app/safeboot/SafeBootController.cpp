#include "SafeBootController.h"
#include "SafeBootAutoRepair.h"
#include "../core/ServiceRegistry.h"
#include "../core/LogManager.h"
#include <QDateTime>

// ═══════════════════════════════════════════════════════
//  SafeBootController — implémentation EXO v30.3
// ═══════════════════════════════════════════════════════

const QSet<QString> SafeBootController::s_criticalServices = {
    QStringLiteral("orchestrator"),
    QStringLiteral("system"),
    QStringLiteral("memory"),
    QStringLiteral("context"),
    QStringLiteral("planner"),
    QStringLiteral("executor"),
    QStringLiteral("verifier")
};

// ── Construction ────────────────────────────────────────

SafeBootController::SafeBootController(QObject *parent)
    : QObject(parent)
{
    m_lazyLoadTimer = new QTimer(this);
    m_lazyLoadTimer->setSingleShot(false);
    m_lazyLoadTimer->setInterval(kLazyRetryIntervalMs);
    connect(m_lazyLoadTimer, &QTimer::timeout,
            this, &SafeBootController::tryLazyLoadNext);
}

void SafeBootController::setAutoRepair(SafeBootAutoRepair *repair)
{
    if (m_autoRepair) {
        disconnect(m_autoRepair, nullptr, this, nullptr);
    }
    m_autoRepair = repair;
    if (m_autoRepair) {
        connect(m_autoRepair, &SafeBootAutoRepair::repairCompleted,
                this, &SafeBootController::onAutoRepairCompleted);
        connect(m_autoRepair, &SafeBootAutoRepair::runningChanged,
                this, &SafeBootController::autoRepairChanged);
    }
}

bool SafeBootController::autoRepairRunning() const
{
    return m_autoRepair ? m_autoRepair->isRunning() : false;
}

void SafeBootController::startAutoRepair()
{
    if (!m_autoRepair) return;
    addTimelineEvent(QStringLiteral("autorepair_start"), {},
                     QStringLiteral("Réparation automatique lancée"));
    hLog() << "[SafeBoot] Lancement de l'AutoRepair";
    m_autoRepair->autoRepairAll();
}

void SafeBootController::setRegistry(ServiceRegistry *registry)
{
    if (m_registry)
        disconnect(m_registry, nullptr, this, nullptr);

    m_registry = registry;

    if (m_registry) {
        connect(m_registry, &ServiceRegistry::serviceStateChanged,
                this, &SafeBootController::onServiceStateChanged);
    }
}

// ── Classification ──────────────────────────────────────

SafeBoot::ServiceCriticality SafeBootController::classifyService(const QString &name) const
{
    return s_criticalServices.contains(name.toLower())
        ? SafeBoot::ServiceCriticality::Critical
        : SafeBoot::ServiceCriticality::NonCritical;
}

// ── Démarrage du monitoring ─────────────────────────────

void SafeBootController::startMonitoring()
{
    if (!m_registry || m_monitoring) return;
    m_monitoring = true;

    addTimelineEvent(QStringLiteral("monitoring_start"), {},
                     QStringLiteral("Surveillance des services démarrée"));

    initServiceStates();

    // Lancer un timer par service
    for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it) {
        m_startTimestamps[it.key()].start();
        startTimeoutTimer(it.key());
    }

    hLog() << "[SafeBoot] Monitoring démarré —"
           << m_services.size() << "services surveillés";
}

void SafeBootController::initServiceStates()
{
    m_services.clear();
    for (const QString &name : m_registry->serviceNames()) {
        SafeBoot::SafeBootState state;
        state.name = name;
        state.criticality = classifyService(name);
        state.status = SafeBoot::ServiceStatus::Pending;
        m_services.insert(name, state);
    }
}

// ── Timeouts (30 s par service) ──────────────────────────

void SafeBootController::startTimeoutTimer(const QString &name)
{
    auto *timer = new QTimer(this);
    timer->setSingleShot(true);
    timer->setInterval(kTimeoutMs);
    connect(timer, &QTimer::timeout, this,
            [this, name]() { onServiceTimeout(name); });
    m_timeoutTimers.insert(name, timer);
    timer->start();
}

void SafeBootController::onServiceTimeout(const QString &name)
{
    auto it = m_services.find(name);
    if (it == m_services.end()) return;
    if (it->status == SafeBoot::ServiceStatus::Ready) return; // déjà prêt

    qint64 elapsed = m_startTimestamps.contains(name)
        ? m_startTimestamps[name].elapsed() : kTimeoutMs;
    it->responseTimeMs = elapsed;

    if (it->criticality == SafeBoot::ServiceCriticality::Critical) {
        it->status = SafeBoot::ServiceStatus::Failed;
        it->lastError = QStringLiteral("Timeout %1 ms").arg(elapsed);

        addTimelineEvent(QStringLiteral("timeout_critical"), name,
                         QStringLiteral("Service critique en timeout (%1 ms)").arg(elapsed));

        hWarning(exoMain) << "[SafeBoot] ⚠ Service critique" << name
                          << "timeout (" << elapsed << "ms) → activation Safe Boot";

        emit serviceFailed(name);
        enableSafeBoot();
    } else {
        it->status = SafeBoot::ServiceStatus::Degraded;
        it->lastError = QStringLiteral("Timeout %1 ms — lazy-load prévu").arg(elapsed);

        addTimelineEvent(QStringLiteral("timeout_noncritical"), name,
                         QStringLiteral("Service non critique dégradé (%1 ms)").arg(elapsed));

        hLog() << "[SafeBoot]" << name << "non critique timeout — marqué Degraded";
        emit serviceFailed(name);
    }

    emit timelineUpdated();
}

// ── Observation des changements d'état ──────────────────

void SafeBootController::onServiceStateChanged(const QString &name,
                                                const QString & /*oldState*/,
                                                const QString &newState)
{
    auto it = m_services.find(name);
    if (it == m_services.end()) return;

    if (newState == QLatin1String("ready")) {
        bool wasNotReady = (it->status != SafeBoot::ServiceStatus::Ready);
        it->status = SafeBoot::ServiceStatus::Ready;
        it->responseTimeMs = m_startTimestamps.contains(name)
            ? m_startTimestamps[name].elapsed() : 0;
        it->lastError.clear();

        // Annuler le timer
        if (auto *t = m_timeoutTimers.value(name)) {
            t->stop(); t->deleteLater();
            m_timeoutTimers.remove(name);
        }

        addTimelineEvent(QStringLiteral("service_ready"), name,
                         QStringLiteral("Prêt en %1 ms").arg(it->responseTimeMs));

        if (wasNotReady) {
            emit serviceRecovered(name);
        }

        checkCriticalReady();
        emit timelineUpdated();

    } else if (newState == QLatin1String("failed") || newState == QLatin1String("crashed")) {
        qint64 elapsed = m_startTimestamps.contains(name)
            ? m_startTimestamps[name].elapsed() : 0;
        it->responseTimeMs = elapsed;
        it->lastError = QStringLiteral("État: %1").arg(newState);

        if (it->criticality == SafeBoot::ServiceCriticality::Critical) {
            it->status = SafeBoot::ServiceStatus::Failed;
            addTimelineEvent(QStringLiteral("service_failed"), name,
                             QStringLiteral("Service critique en %1").arg(newState));
            enableSafeBoot();
        } else {
            it->status = SafeBoot::ServiceStatus::Degraded;
            addTimelineEvent(QStringLiteral("service_degraded"), name,
                             QStringLiteral("Service non critique en %1").arg(newState));
        }

        emit serviceFailed(name);
        emit timelineUpdated();
    }
}

void SafeBootController::checkServiceStatus(const QString &serviceName, bool ready)
{
    if (ready) {
        auto it = m_services.find(serviceName);
        if (it != m_services.end()) {
            it->status = SafeBoot::ServiceStatus::Ready;
            it->responseTimeMs = m_startTimestamps.contains(serviceName)
                ? m_startTimestamps[serviceName].elapsed() : 0;

            if (auto *t = m_timeoutTimers.value(serviceName)) {
                t->stop(); t->deleteLater();
                m_timeoutTimers.remove(serviceName);
            }

            checkCriticalReady();
            emit timelineUpdated();
        }
    } else {
        markServiceFailed(serviceName);
    }
}

void SafeBootController::markServiceFailed(const QString &serviceName)
{
    auto it = m_services.find(serviceName);
    if (it == m_services.end()) return;

    if (it->criticality == SafeBoot::ServiceCriticality::Critical) {
        it->status = SafeBoot::ServiceStatus::Failed;
        enableSafeBoot();
    } else {
        it->status = SafeBoot::ServiceStatus::Degraded;
    }

    addTimelineEvent(QStringLiteral("service_marked_failed"), serviceName,
                     QStringLiteral("Marqué manuellement en échec"));

    emit serviceFailed(serviceName);
    emit timelineUpdated();
}

// ── Activation / Désactivation ──────────────────────────

void SafeBootController::enableSafeBoot()
{
    if (m_safeBootEnabled) return;
    m_safeBootEnabled = true;

    addTimelineEvent(QStringLiteral("safeboot_enabled"), {},
                     QStringLiteral("Mode dégradé activé — services non critiques ignorés"));

    qWarning() << "[SAFEBOOT] Mode dégradé activé — services non critiques ignorés";

    emit safeBootActivated();
    emit safeBootEnabledChanged();
    emit timelineUpdated();

    // Forcer le démarrage de l'UI : émettre criticalServicesReady
    // même si tous les critiques ne sont pas Ready (c'est le principe du Safe Boot)
    if (!m_criticalEmitted) {
        m_criticalEmitted = true;
        addTimelineEvent(QStringLiteral("force_start"), {},
                         QStringLiteral("Démarrage forcé de l'UI en mode Safe Boot"));
        hLog() << "[SafeBoot] ═══ FORCE START — UI démarre en mode dégradé ═══";
        emit criticalServicesReady();
    }

    // Lancer le lazy-load après un délai
    QTimer::singleShot(kLazyLoadDelayMs, this, &SafeBootController::startLazyLoadTimer);

    // Lancer la réparation automatique si disponible
    if (m_autoRepair) {
        QTimer::singleShot(kLazyLoadDelayMs, this, &SafeBootController::startAutoRepair);
    }
}

void SafeBootController::disableSafeBoot()
{
    if (!m_safeBootEnabled) return;
    m_safeBootEnabled = false;

    addTimelineEvent(QStringLiteral("safeboot_disabled"), {},
                     QStringLiteral("Mode normal restauré"));

    hLog() << "[SafeBoot] Mode normal restauré";

    m_lazyLoadTimer->stop();

    emit safeBootDeactivated();
    emit safeBootEnabledChanged();
    emit timelineUpdated();
}

// ── Vérification des critiques ──────────────────────────

void SafeBootController::checkCriticalReady()
{
    if (m_criticalEmitted) return;

    for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it) {
        if (it->criticality == SafeBoot::ServiceCriticality::Critical
            && it->status != SafeBoot::ServiceStatus::Ready) {
            return; // au moins un critique pas prêt
        }
    }

    m_criticalEmitted = true;

    addTimelineEvent(QStringLiteral("critical_ready"), {},
                     QStringLiteral("Tous les services critiques sont prêts"));

    hLog() << "[SafeBoot] ═══ SERVICES CRITIQUES PRÊTS ═══";

    emit criticalServicesReady();

    // Si safe boot actif, lancer le lazy-load
    if (m_safeBootEnabled) {
        QTimer::singleShot(kLazyLoadDelayMs, this, &SafeBootController::startLazyLoadTimer);
    }
}

// ── Lazy-load ───────────────────────────────────────────

void SafeBootController::startLazyLoadTimer()
{
    m_lazyQueue.clear();
    for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it) {
        if (it->criticality == SafeBoot::ServiceCriticality::NonCritical
            && it->status != SafeBoot::ServiceStatus::Ready) {

            // Vérification croisée : le service est peut-être déjà Ready
            // dans le ServiceRegistry (race entre timeout SafeBoot et boot supervisor)
            if (m_registry && m_registry->contains(it.key()
                ) && m_registry->entry(it.key()).state == Exo::ServiceState::Ready) {
                m_services[it.key()].status = SafeBoot::ServiceStatus::Ready;
                hLog() << "[SafeBoot] Lazy-load skip" << it.key()
                       << "— déjà Ready dans le registry";
                continue;
            }

            m_lazyQueue.append(it.key());
            m_lazyRetryCount[it.key()] = 0;
        }
    }

    if (m_lazyQueue.isEmpty()) return;

    addTimelineEvent(QStringLiteral("lazy_load_start"), {},
                     QStringLiteral("%1 services non critiques en file de lazy-load")
                         .arg(m_lazyQueue.size()));

    hLog() << "[SafeBoot] Lazy-load démarré —" << m_lazyQueue.size() << "services en file";

    m_lazyLoadTimer->start();
}

void SafeBootController::tryLazyLoadNext()
{
    if (m_lazyQueue.isEmpty()) {
        m_lazyLoadTimer->stop();
        addTimelineEvent(QStringLiteral("lazy_load_complete"), {},
                         QStringLiteral("File de lazy-load vide"));
        hLog() << "[SafeBoot] Lazy-load terminé";

        // Vérifier si on peut désactiver le safe boot
        bool allOk = true;
        for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it) {
            if (it->status != SafeBoot::ServiceStatus::Ready) {
                allOk = false;
                break;
            }
        }
        if (allOk)
            disableSafeBoot();

        return;
    }

    QString name = m_lazyQueue.first();
    int retries = m_lazyRetryCount.value(name, 0);

    // Vérifier si le service est devenu Ready entre-temps
    auto it = m_services.find(name);
    if (it != m_services.end() && it->status == SafeBoot::ServiceStatus::Ready) {
        m_lazyQueue.removeFirst();
        addTimelineEvent(QStringLiteral("lazy_recovered"), name,
                         QStringLiteral("Service récupéré pendant lazy-load"));
        emit serviceRecovered(name);
        emit timelineUpdated();
        return;
    }

    // Vérification supplémentaire dans le registry (source de vérité réelle)
    if (m_registry && m_registry->contains(name)
        && m_registry->entry(name).state == Exo::ServiceState::Ready) {
        if (it != m_services.end()) {
            it->status = SafeBoot::ServiceStatus::Ready;
        }
        m_lazyQueue.removeFirst();
        addTimelineEvent(QStringLiteral("lazy_recovered"), name,
                         QStringLiteral("Service déjà prêt dans le registry"));
        hLog() << "[SafeBoot] Lazy-load skip" << name << "— Ready confirmé dans le registry";
        emit serviceRecovered(name);
        emit timelineUpdated();
        return;
    }

    if (retries >= kMaxLazyRetries) {
        // Abandon — marquer Degraded définitif
        m_lazyQueue.removeFirst();
        if (it != m_services.end()) {
            it->status = SafeBoot::ServiceStatus::Degraded;
            it->lastError = QStringLiteral("Abandon après %1 tentatives lazy-load").arg(retries);
        }
        addTimelineEvent(QStringLiteral("lazy_abandoned"), name,
                         QStringLiteral("Abandon après %1 retries").arg(retries));
        hWarning(exoMain) << "[SafeBoot]" << name << "— abandon lazy-load après" << retries << "retries";
        emit timelineUpdated();
        return;
    }

    // Incrémenter le compteur de retry
    m_lazyRetryCount[name] = retries + 1;

    addTimelineEvent(QStringLiteral("lazy_retry"), name,
                     QStringLiteral("Tentative lazy-load %1/%2")
                         .arg(retries + 1).arg(kMaxLazyRetries));

    hLog() << "[SafeBoot] Lazy-load retry" << name
           << "(" << (retries + 1) << "/" << kMaxLazyRetries << ")";

    // ServiceSupervisor gère déjà les retries — ici on attend simplement
    // que le ServiceRegistry nous notifie via onServiceStateChanged.
    // On repasse le service en fin de file pour tenter le prochain.
    m_lazyQueue.removeFirst();
    m_lazyQueue.append(name);
}

void SafeBootController::retryNonCriticalServices()
{
    addTimelineEvent(QStringLiteral("retry_noncritical"), {},
                     QStringLiteral("Relance manuelle des services non critiques"));

    hLog() << "[SafeBoot] Relance manuelle des services non critiques";

    for (auto it = m_services.begin(); it != m_services.end(); ++it) {
        if (it->criticality == SafeBoot::ServiceCriticality::NonCritical
            && it->status != SafeBoot::ServiceStatus::Ready) {
            it->status = SafeBoot::ServiceStatus::Pending;
            m_lazyRetryCount[it.key()] = 0;
            m_startTimestamps[it.key()].start();
        }
    }

    startLazyLoadTimer();
    emit timelineUpdated();
}

// ── Redémarrage normal ──────────────────────────────────

void SafeBootController::restartNormalMode()
{
    addTimelineEvent(QStringLiteral("restart_normal"), {},
                     QStringLiteral("Redémarrage en mode normal"));

    hLog() << "[SafeBoot] ═══ RESTART NORMAL MODE ═══";

    // Stopper tout
    m_lazyLoadTimer->stop();
    for (auto *t : m_timeoutTimers)
        { t->stop(); t->deleteLater(); }
    m_timeoutTimers.clear();

    // Reset état
    m_safeBootEnabled = false;
    m_criticalEmitted = false;
    m_lazyQueue.clear();
    m_lazyRetryCount.clear();
    m_timeline.clear();

    // Réinitialiser tous les services à Pending
    for (auto it = m_services.begin(); it != m_services.end(); ++it) {
        it->status = SafeBoot::ServiceStatus::Pending;
        it->responseTimeMs = -1;
        it->lastError.clear();
        m_startTimestamps[it.key()].start();
        startTimeoutTimer(it.key());
    }

    addTimelineEvent(QStringLiteral("monitoring_restart"), {},
                     QStringLiteral("Surveillance relancée — tous les services réinitialisés"));

    emit safeBootDeactivated();
    emit safeBootEnabledChanged();
    emit timelineUpdated();
}

// ── AutoRepair callback ─────────────────────────────────

void SafeBootController::onAutoRepairCompleted()
{
    addTimelineEvent(QStringLiteral("autorepair_done"), {},
                     QStringLiteral("Réparation automatique terminée"));

    // Vérifier si tous les services critiques sont maintenant Ready
    bool allCriticalOk = true;
    for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it) {
        if (it->criticality == SafeBoot::ServiceCriticality::Critical
            && it->status != SafeBoot::ServiceStatus::Ready) {
            allCriticalOk = false;
            break;
        }
    }

    if (allCriticalOk && m_safeBootEnabled) {
        addTimelineEvent(QStringLiteral("autorepair_success"), {},
                         QStringLiteral("Tous les critiques réparés — retour en mode normal"));
        hLog() << "[SafeBoot] ═══ AUTO-RÉPARATION RÉUSSIE — retour mode normal ═══";

        disableSafeBoot();

        // Relancer les non-critiques
        retryNonCriticalServices();
    } else if (m_safeBootEnabled) {
        hWarning(exoMain) << "[SafeBoot] AutoRepair terminé — des critiques restent KO";
    }

    emit autoRepairChanged();
    emit timelineUpdated();
}

// ── Accesseurs ──────────────────────────────────────────

int SafeBootController::failedCount() const
{
    int n = 0;
    for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it)
        if (it->status == SafeBoot::ServiceStatus::Failed) ++n;
    return n;
}

int SafeBootController::degradedCount() const
{
    int n = 0;
    for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it)
        if (it->status == SafeBoot::ServiceStatus::Degraded) ++n;
    return n;
}

int SafeBootController::readyCount() const
{
    int n = 0;
    for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it)
        if (it->status == SafeBoot::ServiceStatus::Ready) ++n;
    return n;
}

QVariantList SafeBootController::getFailedServices() const
{
    QVariantList list;
    for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it) {
        if (it->status == SafeBoot::ServiceStatus::Failed) {
            QVariantMap m;
            m[QStringLiteral("name")]        = it->name;
            m[QStringLiteral("criticality")] = SafeBoot::criticalityToString(it->criticality);
            m[QStringLiteral("status")]      = SafeBoot::statusToString(it->status);
            m[QStringLiteral("responseMs")]  = it->responseTimeMs;
            m[QStringLiteral("error")]       = it->lastError;
            list.append(m);
        }
    }
    return list;
}

QVariantList SafeBootController::getDegradedServices() const
{
    QVariantList list;
    for (auto it = m_services.constBegin(); it != m_services.constEnd(); ++it) {
        if (it->status == SafeBoot::ServiceStatus::Degraded) {
            QVariantMap m;
            m[QStringLiteral("name")]        = it->name;
            m[QStringLiteral("criticality")] = SafeBoot::criticalityToString(it->criticality);
            m[QStringLiteral("status")]      = SafeBoot::statusToString(it->status);
            m[QStringLiteral("responseMs")]  = it->responseTimeMs;
            m[QStringLiteral("error")]       = it->lastError;
            list.append(m);
        }
    }
    return list;
}

QVariantList SafeBootController::getStartupTimeline() const
{
    QVariantList list;
    for (const auto &entry : m_timeline) {
        QVariantMap m;
        m[QStringLiteral("event")]       = entry.event;
        m[QStringLiteral("timestamp")]   = entry.timestamp;
        m[QStringLiteral("serviceName")] = entry.serviceName;
        m[QStringLiteral("detail")]      = entry.detail;
        list.append(m);
    }
    return list;
}

QVariantList SafeBootController::repairTimeline() const
{
    return m_autoRepair ? m_autoRepair->repairTimeline() : QVariantList{};
}

// ── Timeline ────────────────────────────────────────────

void SafeBootController::addTimelineEvent(const QString &event,
                                           const QString &serviceName,
                                           const QString &detail)
{
    SafeBoot::SafeBootTimeline entry;
    entry.event       = event;
    entry.timestamp   = QDateTime::currentMSecsSinceEpoch();
    entry.serviceName = serviceName;
    entry.detail      = detail;
    m_timeline.append(entry);
}
