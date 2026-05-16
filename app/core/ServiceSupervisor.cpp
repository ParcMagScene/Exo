#include "ServiceSupervisor.h"
#include "LogManager.h"
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QProcess>
#include <QProcessEnvironment>
#include <algorithm>

// ── Constantes de timing (ms) ────────────────────────
static constexpr int QUICK_PROBE_TIMEOUT_MS   = 2000;  // 2s — probe si le service tourne déjà
static constexpr int READINESS_POLL_MS        = 500;   // 500ms — intervalle de poll readiness
static constexpr int PROCESS_START_TIMEOUT_MS = 5000;  // 5s — waitForStarted

// ═══════════════════════════════════════════════════════
//  ServiceSupervisor — implémentation EXO v5
// ═══════════════════════════════════════════════════════

ServiceSupervisor::ServiceSupervisor(QObject *parent)
    : QObject(parent)
{
}

ServiceSupervisor::~ServiceSupervisor()
{
    shutdownAll();
}

// ── Point d'entrée ──────────────────────────────────────

void ServiceSupervisor::start(const QString &servicesJsonPath)
{
    loadDescriptors(servicesJsonPath);
    if (m_bootOrder.isEmpty()) {
        emit startupFailed("Aucun service dans services.json");
        return;
    }
    emit serviceCountChanged();
    m_bootIndex = 0;
    startNext();
}

// ── Chargement des descripteurs ─────────────────────────

void ServiceSupervisor::loadDescriptors(const QString &path)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        qWarning() << "[Superviseur] Impossible d'ouvrir" << path;
        return;
    }

    QJsonParseError err;
    QJsonDocument doc = QJsonDocument::fromJson(file.readAll(), &err);
    if (err.error != QJsonParseError::NoError) {
        qWarning() << "[Superviseur] Erreur de parsing JSON :" << err.errorString();
        return;
    }

    const QJsonArray arr = doc.array();
    for (const QJsonValue &v : arr) {
        Exo::ServiceDescriptor desc = Exo::ServiceDescriptor::fromJson(v.toObject());
        m_registry.registerService(desc);
        m_bootOrder.append(desc.name);
    }

    hLog() << "[Superviseur]" << m_bootOrder.size() << "services chargés";
}

// ── Boucle de boot séquentiel ───────────────────────────

void ServiceSupervisor::startNext()
{
    if (m_bootIndex >= m_bootOrder.size()) {
        // v5.1: des services lancés en parallèle peuvent encore charger
        if (m_registry.allReady()) {
            setCurrentAction("Tous les services sont prêts");
            hLog() << "[Superviseur] ═══ TOUS LES SERVICES PRÊTS ═══";
            emit allServicesReady();
        } else {
            setCurrentAction("Attente des services en cours de chargement…");
            hLog() << "[Superviseur] Boot séquentiel terminé — attente services parallèles…";
        }
        return;
    }

    const QString &name = m_bootOrder[m_bootIndex];
    launchService(name);
}

// ── Lancement d'un service ──────────────────────────────

void ServiceSupervisor::launchService(const QString &name)
{
    auto &entry = m_registry.entry(name);
    const auto &desc = entry.descriptor;

    setCurrentAction(QStringLiteral("Lancement de %1…").arg(name));
    m_registry.setState(name, Exo::ServiceState::Starting);
    emit progressChanged();

    // Vérifier d'abord si le service tourne déjà (probe rapide)
    auto *quickProbe = new WebSocketClient(QStringLiteral("QuickProbe-") + name, this);
    quickProbe->setReconnectEnabled(false);

    QUrl url(QStringLiteral("ws://localhost:%1").arg(desc.port));
    auto *quickTimeout = new QTimer(this);
    quickTimeout->setSingleShot(true);
    quickTimeout->setInterval(QUICK_PROBE_TIMEOUT_MS);

    connect(quickProbe, &WebSocketClient::connected, this,
        [this, name, quickProbe, quickTimeout]() {
            quickTimeout->stop(); quickTimeout->deleteLater();
            quickProbe->close();
            quickProbe->deleteLater();
            hLog() << "[Superviseur]" << name << "déjà en cours d'exécution";
            // Passer directement à la phase readiness
            m_registry.setState(name, Exo::ServiceState::WaitingReady);
            probeReadiness(name);
        });

    connect(quickProbe, &WebSocketClient::errorOccurred, this,
        [this, name, quickProbe, quickTimeout](const QString &) {
            if (!quickTimeout->isActive()) return;
            quickTimeout->stop(); quickTimeout->deleteLater();
            quickProbe->close();
            quickProbe->deleteLater();
            // Service pas là → le lancer
            doLaunchProcess(name);
        });

    // Si le probe ne répond pas en 2s → le service n'est pas là
    connect(quickTimeout, &QTimer::timeout, this,
        [this, name, quickProbe]() {
            quickProbe->deleteLater();
            doLaunchProcess(name);
        });

    quickTimeout->start();
    quickProbe->open(url);
}

void ServiceSupervisor::doLaunchProcess(const QString &name)
{
    auto &entry = m_registry.entry(name);
    const auto &desc = entry.descriptor;

    QString pythonExe = pythonExeForVenv(desc.venv);
    if (pythonExe.isEmpty() || !QFile::exists(pythonExe)) {
        qWarning() << "[Superviseur] Python introuvable pour" << name << ":" << pythonExe;
        m_registry.setState(name, Exo::ServiceState::Failed);
        emit progressChanged();
        advanceToNext();
        return;
    }

    QString scriptPath = QDir(projectDir()).absoluteFilePath(desc.script);
    if (!QFile::exists(scriptPath)) {
        qWarning() << "[Superviseur] Script introuvable:" << scriptPath;
        m_registry.setState(name, Exo::ServiceState::Failed);
        emit progressChanged();
        advanceToNext();
        return;
    }

    QStringList processArgs;
    processArgs << scriptPath << desc.args;

    auto *proc = new QProcess(this);
    proc->setWorkingDirectory(projectDir());

    // Variables d'environnement EXO
    QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
    QDir projectDir = QDir(QCoreApplication::applicationDirPath());
    projectDir.cdUp(); projectDir.cdUp();
    const QString ssd = qEnvironmentVariable("EXO_SSD_ROOT", projectDir.absolutePath());
    env.insert(QStringLiteral("EXO_WHISPER_MODELS"),  "D:/EXO/models/whisper");
    env.insert(QStringLiteral("EXO_WHISPERCPP_BIN"),  ssd + "/whispercpp/build_vk/bin/Release");
    env.insert(QStringLiteral("EXO_FAISS_DIR"),        ssd + "/faiss/semantic_memory");
    env.insert(QStringLiteral("EXO_WAKEWORD_MODELS"),  "D:/EXO/models/wakeword");
    env.insert(QStringLiteral("HF_HOME"),              ssd + "/cache/huggingface");
    env.insert(QStringLiteral("TRANSFORMERS_CACHE"),   ssd + "/cache/huggingface/hub");
    env.insert(QStringLiteral("EXO_SSD_ROOT"),         ssd);
    env.insert(QStringLiteral("EXO_FILES_DIR"),        ssd + "/files");
    env.insert(QStringLiteral("TORCH_HOME"),           ssd + "/cache/torch");
    const QString pythonRoot = QDir(projectDir.absolutePath()).absoluteFilePath(QStringLiteral("python"));
    const QString pythonPath = env.value(QStringLiteral("PYTHONPATH"));
    env.insert(QStringLiteral("PYTHONPATH"),
               pythonPath.isEmpty()
                   ? pythonRoot
                   : pythonRoot + QChar(QLatin1Char(';')) + pythonPath);
    proc->setProcessEnvironment(env);

    // Logs
    QDir logDir(ssd + "/logs");
    logDir.mkpath(".");
    proc->setStandardOutputFile(logDir.absoluteFilePath(name.toLower() + "_stdout.log"));
    proc->setStandardErrorFile(logDir.absoluteFilePath(name.toLower() + "_stderr.log"));

    // Détection de crash
    connect(proc, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
        this, [this, name](int exitCode, QProcess::ExitStatus exitStatus) {
            Q_UNUSED(exitStatus)
            auto &e = m_registry.entry(name);
            if (e.state == Exo::ServiceState::Ready) {
                // Service était opérationnel → crash
                onServiceCrashed(name, exitCode);
            }
        });

    proc->start(pythonExe, processArgs);

    if (!proc->waitForStarted(PROCESS_START_TIMEOUT_MS)) {
        qWarning() << "[Superviseur] Échec démarrage" << name;
        proc->deleteLater();
        m_registry.setState(name, Exo::ServiceState::Failed);
        emit progressChanged();
        retryOrFail(name);
        return;
    }

    qint64 pid = proc->processId();
    m_registry.setProcess(name, proc, pid);
    hLog() << "[Superviseur]" << name << "lancé (PID" << pid << ") — attente readiness…";

    m_registry.setState(name, Exo::ServiceState::WaitingReady);
    emit progressChanged();

    probeReadiness(name);
}

// ── Probe de readiness (WS connect + message "ready") ──

void ServiceSupervisor::probeReadiness(const QString &name)
{
    const auto &desc = m_registry.entry(name).descriptor;
    QUrl url(QStringLiteral("ws://localhost:%1").arg(desc.port));

    cleanupProbe(name);

    ReadinessProbe probe;
    probe.client = new WebSocketClient(QStringLiteral("Ready-") + name, this);
    probe.client->setReconnectEnabled(false);

    probe.timeout = new QTimer(this);
    probe.timeout->setSingleShot(true);
    probe.timeout->setInterval(desc.startupTimeoutMs);

    probe.poll = new QTimer(this);
    probe.poll->setInterval(READINESS_POLL_MS);

    m_probes.insert(name, probe);

    // Quand connecté → on attend le message "ready"
    connect(probe.client, &WebSocketClient::connected, this,
        [this, name]() { onReadinessConnected(name); });

    // Messages reçus → chercher "ready"
    connect(probe.client, &WebSocketClient::textReceived, this,
        [this, name](const QString &msg) { onReadinessMessage(name, msg); });

    // v5.1: si la connexion readiness tombe, relancer le poll
    connect(probe.client, &WebSocketClient::disconnected, this,
        [this, name]() {
            auto it = m_probes.find(name);
            if (it != m_probes.end() && it->poll && !it->poll->isActive()) {
                hLog() << "[Superviseur]" << name
                       << "WS readiness perdu — relance poll";
                it->poll->start();
            }
        });

    // Poll : réessayer la connexion WS avec backoff exponentiel (500ms -> 15s)
    connect(probe.poll, &QTimer::timeout, this,
        [this, name, url]() {
            auto it = m_probes.find(name);
            if (it == m_probes.end()) return;
            if (it->client && !it->client->isConnected()) {
                // open() fait destroySocket() en interne (disconnect signaux + abort + delete)
                // Pas de close() ici : il provoque un wildcard warning Qt
                it->client->open(url);
                it->pollIntervalMs = std::min(15000, it->pollIntervalMs * 2);
                it->poll->setInterval(it->pollIntervalMs);
            }
        });

    // Timeout global
    connect(probe.timeout, &QTimer::timeout, this,
        [this, name]() { onReadinessTimeout(name); });

    probe.timeout->start();
    probe.poll->start();
    probe.client->open(url);
}

void ServiceSupervisor::onReadinessConnected(const QString &name)
{
    hLog() << "[Superviseur]" << name << "WebSocket connecté — attente message ready…";
    // Arrêter le poll, on est connecté ; reset backoff pour la prochaine perte
    auto it = m_probes.find(name);
    if (it != m_probes.end()) {
        if (it->poll) it->poll->stop();
        it->pollIntervalMs = 500;
        if (it->poll) it->poll->setInterval(500);
    }
}

void ServiceSupervisor::onReadinessMessage(const QString &name, const QString &msg)
{
    QJsonDocument doc = QJsonDocument::fromJson(msg.toUtf8());
    if (!doc.isObject()) return;

    QJsonObject obj = doc.object();
    QString type = obj.value(QStringLiteral("type")).toString();

    // Injection des métriques détaillées si présentes
    auto &entry = m_registry.entry(name);
    if (obj.contains("message"))        entry.message = obj.value("message").toString();
    if (obj.contains("startupTimeMs"))  entry.startupTimeMs = obj.value("startupTimeMs").toVariant().toLongLong();
    if (obj.contains("latencyMs"))      entry.latencyMs = obj.value("latencyMs").toVariant().toLongLong();
    if (obj.contains("restarts"))       entry.restarts = obj.value("restarts").toInt();
    if (obj.contains("lastHeartbeat"))  entry.lastHeartbeat = obj.value("lastHeartbeat").toVariant().toLongLong();
    if (obj.contains("cpu"))            entry.cpu = obj.value("cpu").toDouble();
    if (obj.contains("ram"))            entry.ram = obj.value("ram").toDouble();

    if (type == QLatin1String("ready")) {
        QString phaseStr = obj.value(QStringLiteral("phase")).toString();

        if (phaseStr.isEmpty()) {
            // Backward compat: services sans phase → ready immédiat
            markReady(name);
            return;
        }

        Exo::ReadinessPhase phase = Exo::readinessPhaseFromString(phaseStr);
        m_registry.setPhase(name, phase);

        if (phase == Exo::ReadinessPhase::Online) {
            // Service pleinement opérationnel
            markReady(name);
        } else {
            // Phase intermédiaire — mettre à jour l'action et avancer
            // sans attendre (le probe reste actif en arrière-plan)
            static const QMap<Exo::ReadinessPhase, QString> phaseLabels = {
                {Exo::ReadinessPhase::Init,    QStringLiteral("Initialisation %1…")},
                {Exo::ReadinessPhase::Loading,  QStringLiteral("Chargement modèle %1…")},
                {Exo::ReadinessPhase::Warmup,   QStringLiteral("Préchauffage GPU %1…")},
            };
            auto label = phaseLabels.value(phase, QStringLiteral("%1 en cours…"));
            setCurrentAction(label.arg(name.toUpper()));
            hLog() << "[Superviseur]" << name << "phase:" << phaseStr;

            // v5.1: avancer au service suivant dès la première phase reçue
            // (le probe reste actif pour ce service)
            if (!m_advancedPast.contains(name)) {
                m_advancedPast.insert(name);
                hLog() << "[Superviseur]" << name
                       << "phase intermédiaire — lancement du prochain service en parallèle";
                advanceToNext();
            }
        }
    }
}

void ServiceSupervisor::onReadinessTimeout(const QString &name)
{
    hWarning(exoMain) << "[Superviseur]" << name << "délai readiness dépassé";
    cleanupProbe(name);
    retryOrFail(name);
}

void ServiceSupervisor::onServiceCrashed(const QString &name, int exitCode)
{
    // Pendant l'arrêt normal, les processus sont terminés intentionnellement ;
    // ne pas les traiter comme des crashs pour éviter la création de timers de retry orphelins.
    if (m_shutdownDone) return;

    hWarning(exoMain) << "[Superviseur]" << name << "PLANTÉ (code sortie" << exitCode << ")";
    m_registry.setState(name, Exo::ServiceState::Crashed);
    emit progressChanged();

    // Tentative de relance automatique
    retryOrFail(name);
}

// ── RetryPolicy ─────────────────────────────────────────

void ServiceSupervisor::retryOrFail(const QString &name)
{
    auto &entry = m_registry.entry(name);
    const auto &policy = entry.descriptor.retryPolicy;

    if (entry.retryCount >= policy.maxAttempts) {
        hWarning(exoMain) << "[Superviseur]" << name << "— abandon après"
                          << entry.retryCount << "tentatives";
        m_registry.setState(name, Exo::ServiceState::Failed);
        emit progressChanged();
        advanceToNext();
        return;
    }

    m_registry.incrementRetry(name);
    int delay = policy.delayForAttempt(entry.retryCount);

    hLog() << "[Superviseur]" << name << "— retry" << entry.retryCount
           << "dans" << delay << "ms";

    m_registry.setState(name, Exo::ServiceState::Restarting);
    emit progressChanged();

    QTimer::singleShot(delay, this, [this, name]() {
        // Tuer l'ancien processus si encore vivant
        auto &e = m_registry.entry(name);
        if (e.process && e.process->state() != QProcess::NotRunning) {
            e.process->terminate();
            // Async : lancer le service après arrêt (ou force-kill après timeout)
            auto *proc = e.process;
            connect(proc, qOverload<int, QProcess::ExitStatus>(&QProcess::finished),
                    this, [this, name]() { launchService(name); },
                    Qt::SingleShotConnection);
            QTimer::singleShot(3000, proc, [this, proc, name]() {
                if (proc->state() != QProcess::NotRunning) {
                    proc->kill();
                    launchService(name);
                }
            });
        } else {
            launchService(name);
        }
    });
}

// ── Marquage Ready et avancement ────────────────────────

void ServiceSupervisor::markReady(const QString &name)
{
    cleanupProbe(name);
    m_registry.resetRetry(name);
    m_registry.setState(name, Exo::ServiceState::Ready);
    m_registry.setPhase(name, Exo::ReadinessPhase::Online);

    hLog() << "[Superviseur] OK" << name << "PRET";
    emit serviceReady(name);
    emit progressChanged();

    // v5.1: si on avait déjà avancé le boot index pour ce service
    // (boot parallèle), ne pas ré-avancer — vérifier si tout est prêt
    if (m_advancedPast.contains(name)) {
        m_advancedPast.remove(name);
        if (m_registry.allReady()) {
            setCurrentAction("Tous les services sont prêts");
            hLog() << "[Superviseur] ═══ TOUS LES SERVICES PRÊTS ═══";
            emit allServicesReady();
        }
    } else {
        advanceToNext();
    }
}

void ServiceSupervisor::advanceToNext()
{
    m_bootIndex++;
    startNext();
}

// ── Cleanup d'une probe ─────────────────────────────────

void ServiceSupervisor::cleanupProbe(const QString &name)
{
    auto it = m_probes.find(name);
    if (it == m_probes.end()) return;

    // Stopper les timers d'abord pour empêcher tout callback
    if (it->timeout) { it->timeout->stop(); it->timeout->deleteLater(); }
    if (it->poll)    { it->poll->stop();    it->poll->deleteLater(); }
    // Fermer proprement la connexion avant destruction pour éviter les
    // sessions fantômes côté serveur Python (le abort() du destructeur
    // ne notifie pas le pair et bloque les serveurs single-session)
    if (it->client)  { it->client->close(); it->client->deleteLater(); }

    m_probes.erase(it);
}

// ── Arrêt propre ────────────────────────────────────────

void ServiceSupervisor::shutdownAll()
{
    // Idempotence : protège contre le double-appel (aboutToQuit + destructeur)
    if (m_shutdownDone) return;
    m_shutdownDone = true;

    // Nettoyer les probes — deleteLater() pour éviter les callbacks sur mémoire libérée
    for (auto it = m_probes.begin(); it != m_probes.end(); ++it) {
        if (it->timeout) { it->timeout->stop(); it->timeout->deleteLater(); }
        if (it->poll)    { it->poll->stop();    it->poll->deleteLater(); }
        if (it->client)  { it->client->close(); it->client->deleteLater(); }
    }
    m_probes.clear();

    // La guard m_shutdownDone dans onServiceCrashed() évite les retries parasites ;
    // pas besoin de changer l'état ici.

    // Envoyer terminate() à TOUS les processus en parallèle (non bloquant)
    QList<QProcess *> procs;
    for (const QString &name : m_registry.serviceNames()) {
        auto &entry = m_registry.entry(name);
        if (entry.process && entry.process->state() != QProcess::NotRunning) {
            hLog() << "[Superviseur] Arrêt de" << name << "(PID" << entry.pid << ")";
            entry.process->terminate();
            procs.append(entry.process);
        }
    }

    // Attendre collectivement avec un timeout global de 2 s,
    // puis force-kill ce qui reste — SANS bloquer N×5s en séquence
    QDeadlineTimer deadline(2000);
    for (QProcess *proc : procs) {
        int remaining = static_cast<int>(deadline.remainingTime());
        if (remaining <= 0 || !proc->waitForFinished(remaining))
            proc->kill();
    }
}

// ── Accesseurs Q_PROPERTY ───────────────────────────────

bool ServiceSupervisor::allReady() const
{
    return m_registry.allReady();
}

int ServiceSupervisor::totalServices() const
{
    return m_registry.totalServices();
}

int ServiceSupervisor::readyCount() const
{
    return m_registry.readyCount();
}

QVariantList ServiceSupervisor::serviceStatuses() const
{
    return m_registry.serviceStatuses();
}

QString ServiceSupervisor::serviceState(const QString &name) const
{
    return m_registry.serviceState(name);
}

// ── Utilitaires ─────────────────────────────────────────

void ServiceSupervisor::setCurrentAction(const QString &action)
{
    if (m_currentAction != action) {
        m_currentAction = action;
        emit currentActionChanged();
    }
}

QString ServiceSupervisor::pythonExeForVenv(const QString &venv) const
{
    return QDir(projectDir()).absoluteFilePath(venv + "/Scripts/python.exe");
}

QString ServiceSupervisor::projectDir() const
{
    QDir dir(QCoreApplication::applicationDirPath());
    dir.cdUp(); // Debug/Release → build
    dir.cdUp(); // build → racine
    return dir.absolutePath();
}
