#include "ServiceManager.h"
#include <QCoreApplication>
#include <QDeadlineTimer>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QProcessEnvironment>
#include <QDebug>

// ═══════════════════════════════════════════════════════
//  ServiceManager — implémentation
// ═══════════════════════════════════════════════════════

ServiceManager::ServiceManager(QObject *parent)
    : QObject(parent)
{
    m_probeTimeout.setSingleShot(true);
}

ServiceManager::~ServiceManager()
{
    shutdownAll();
}

// ── Point d'entrée ──────────────────────────────────────

void ServiceManager::start(const QString &servicesJsonPath)
{
    loadServices(servicesJsonPath);
    if (m_services.isEmpty()) {
        emit startupFailed("Aucun service dans services.json");
        return;
    }
    emit serviceCountChanged();
    m_currentIndex = 0;
    checkNext();
}

// ── Chargement JSON ─────────────────────────────────────

void ServiceManager::loadServices(const QString &path)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        qWarning() << "[ServiceManager] Cannot open" << path;
        return;
    }

    QJsonParseError err;
    QJsonDocument doc = QJsonDocument::fromJson(file.readAll(), &err);
    if (err.error != QJsonParseError::NoError) {
        qWarning() << "[ServiceManager] JSON parse error:" << err.errorString();
        return;
    }

    const QJsonArray arr = doc.array();
    m_services.reserve(arr.size());

    for (const QJsonValue &v : arr) {
        QJsonObject obj = v.toObject();
        ServiceInfo si;
        si.name   = obj.value(QStringLiteral("name")).toString();
        si.port   = obj.value(QStringLiteral("port")).toInt();
        si.venv   = obj.value(QStringLiteral("venv")).toString();
        si.script = obj.value(QStringLiteral("script")).toString();

        const QJsonArray argsArr = obj.value(QStringLiteral("args")).toArray();
        for (const QJsonValue &a : argsArr)
            si.args << a.toString();

        si.status = ServiceInfo::Unknown;
        m_services.append(si);
    }

    qInfo() << "[ServiceManager]" << m_services.size() << "services loaded";
}

// ── Boucle séquentielle : check → probe → launch ───────

void ServiceManager::checkNext()
{
    if (m_currentIndex >= m_services.size()) {
        // Tous les services ont été traités
        m_allReady = true;
        setCurrentAction("Tous les services sont prêts");
        qInfo() << "[GUI] All services ready → loading interface";
        emit allServicesReady();
        return;
    }

    probeService(m_currentIndex);
}

void ServiceManager::probeService(int index)
{
    ServiceInfo &si = m_services[index];
    si.status = ServiceInfo::Checking;
    setCurrentAction(QStringLiteral("Vérification de %1…").arg(si.name));
    qInfo().noquote() << QStringLiteral("[GUI] Checking service %1...").arg(si.name);
    emit serviceStatusChanged();

    // Créer un probe WebSocket temporaire
    si.probe = new WebSocketClient(QStringLiteral("Probe-") + si.name, this);
    si.probe->setReconnectEnabled(false);

    QUrl url(QStringLiteral("ws://localhost:%1").arg(si.port));

    // Timeout : si pas connecté en 3s → service absent
    auto *timeout = new QTimer(this);
    timeout->setSingleShot(true);
    timeout->setInterval(3000);

    connect(si.probe, &WebSocketClient::connected, this,
            [this, index, timeout]() {
                timeout->stop();
                timeout->deleteLater();
                onServiceProbeConnected(index);
            });

    connect(si.probe, &WebSocketClient::errorOccurred, this,
            [this, index, timeout](const QString &) {
                if (timeout->isActive()) {
                    timeout->stop();
                    timeout->deleteLater();
                    onServiceProbeFailed(index);
                }
            });

    connect(timeout, &QTimer::timeout, this,
            [this, index]() {
                onServiceProbeFailed(index);
            });

    timeout->start();
    si.probe->open(url);
}

void ServiceManager::onServiceProbeConnected(int index)
{
    ServiceInfo &si = m_services[index];

    // Fermer le probe, le service tourne déjà
    si.probe->close();
    si.probe->deleteLater();
    si.probe = nullptr;

    si.status = ServiceInfo::Ready;
    qInfo().noquote() << QStringLiteral("[GUI] %1 ready").arg(si.name);
    emit serviceStatusChanged();
    advanceIndex();
}

void ServiceManager::onServiceProbeFailed(int index)
{
    ServiceInfo &si = m_services[index];

    // Fermer le probe
    if (si.probe) {
        si.probe->close();
        si.probe->deleteLater();
        si.probe = nullptr;
    }

    qInfo().noquote() << QStringLiteral("[GUI] %1 not running → launching...").arg(si.name);
    launchService(index);
}

// ── Lancement d'un service via QProcess ─────────────────

void ServiceManager::launchService(int index)
{
    ServiceInfo &si = m_services[index];
    si.status = ServiceInfo::Launching;
    setCurrentAction(QStringLiteral("Lancement de %1…").arg(si.name));
    emit serviceStatusChanged();

    QString pythonExe = pythonExeForVenv(si.venv);
    if (pythonExe.isEmpty() || !QFile::exists(pythonExe)) {
        qWarning() << "[ServiceManager] Python not found for" << si.name << ":" << pythonExe;
        si.status = ServiceInfo::Failed;
        emit serviceStatusChanged();
        advanceIndex();
        return;
    }

    QString scriptPath = QDir(projectDir()).absoluteFilePath(si.script);
    if (!QFile::exists(scriptPath)) {
        qWarning() << "[ServiceManager] Script not found:" << scriptPath;
        si.status = ServiceInfo::Failed;
        emit serviceStatusChanged();
        advanceIndex();
        return;
    }

    QStringList processArgs;
    processArgs << scriptPath << si.args;

    si.process = new QProcess(this);
    si.process->setWorkingDirectory(projectDir());

    // Injecter les variables d'environnement EXO
    QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
    const QString ssd = qEnvironmentVariable("EXO_SSD_ROOT", QStringLiteral("D:/EXO"));
    env.insert(QStringLiteral("EXO_WHISPER_MODELS"),  ssd + "/models/whisper");
    env.insert(QStringLiteral("EXO_WHISPERCPP_BIN"),  ssd + "/whispercpp/build_vk/bin/Release");
    env.insert(QStringLiteral("EXO_COSYVOICE_MODELS"), ssd + "/models/cosyvoice_fr");
    env.insert(QStringLiteral("EXO_FAISS_DIR"),        ssd + "/faiss/semantic_memory");
    env.insert(QStringLiteral("EXO_WAKEWORD_MODELS"),  ssd + "/models/wakeword");
    env.insert(QStringLiteral("HF_HOME"),              ssd + "/cache/huggingface");
    env.insert(QStringLiteral("TRANSFORMERS_CACHE"),   ssd + "/cache/huggingface/hub");
    env.insert(QStringLiteral("EXO_SSD_ROOT"),         ssd);
    env.insert(QStringLiteral("EXO_FILES_DIR"),        ssd + "/files");
    env.insert(QStringLiteral("TORCH_HOME"),           ssd + "/cache/torch");
    const QString pythonRoot = QDir(projectDir()).absoluteFilePath(QStringLiteral("python"));
    const QString pythonPath = env.value(QStringLiteral("PYTHONPATH"));
    env.insert(QStringLiteral("PYTHONPATH"),
               pythonPath.isEmpty()
                   ? pythonRoot
                   : pythonRoot + QDir::listSeparator() + pythonPath);
    si.process->setProcessEnvironment(env);

    // Rediriger les logs
    QDir logDir(ssd + "/logs");
    logDir.mkpath(".");
    si.process->setStandardOutputFile(logDir.absoluteFilePath(si.name.toLower() + "_stdout.log"));
    si.process->setStandardErrorFile(logDir.absoluteFilePath(si.name.toLower() + "_stderr.log"));

    si.process->start(pythonExe, processArgs);

    if (!si.process->waitForStarted(5000)) {
        qWarning() << "[ServiceManager] Failed to start" << si.name;
        si.status = ServiceInfo::Failed;
        emit serviceStatusChanged();
        advanceIndex();
        return;
    }

    qInfo().noquote() << QStringLiteral("[GUI] %1 launched (PID %2) — waiting for readiness...")
                             .arg(si.name).arg(si.process->processId());

    // Poll : tenter de se connecter au port toutes les 500 ms, timeout 30s
    si.status = ServiceInfo::Running;
    emit serviceStatusChanged();

    auto *pollTimer = new QTimer(this);
    auto *deadline  = new QTimer(this);
    pollTimer->setInterval(500);
    deadline->setSingleShot(true);
    deadline->setInterval(m_probeTimeoutMs);

    auto *readyProbe = new WebSocketClient(QStringLiteral("Ready-") + si.name, this);
    readyProbe->setReconnectEnabled(false);

    connect(readyProbe, &WebSocketClient::connected, this,
            [this, index, pollTimer, deadline, readyProbe]() {
                pollTimer->stop(); pollTimer->deleteLater();
                deadline->stop();  deadline->deleteLater();
                readyProbe->close(); readyProbe->deleteLater();
                m_services[index].status = ServiceInfo::Ready;
                qInfo().noquote() << QStringLiteral("[GUI] %1 ready").arg(m_services[index].name);
                emit serviceStatusChanged();
                advanceIndex();
            });

    connect(pollTimer, &QTimer::timeout, this,
            [readyProbe, index, this]() {
                QUrl url(QStringLiteral("ws://localhost:%1").arg(m_services[index].port));
                readyProbe->close();
                readyProbe->open(url);
            });

    connect(deadline, &QTimer::timeout, this,
            [this, index, pollTimer, readyProbe]() {
                pollTimer->stop(); pollTimer->deleteLater();
                readyProbe->close(); readyProbe->deleteLater();
                qWarning() << "[ServiceManager]" << m_services[index].name << "readiness timeout";
                m_services[index].status = ServiceInfo::Failed;
                emit serviceStatusChanged();
                advanceIndex();
            });

    deadline->start();
    pollTimer->start();
}

// ── Navigation séquentielle ─────────────────────────────

void ServiceManager::advanceIndex()
{
    m_currentIndex++;
    checkNext();
}

// ── Arrêt propre ────────────────────────────────────────

void ServiceManager::shutdownAll()
{
    // Fermer les probes en premier
    for (auto &si : m_services) {
        if (si.probe) {
            si.probe->close();
            si.probe->deleteLater();
            si.probe = nullptr;
        }
    }

    // Envoyer terminate() à tous les processus en parallèle
    QList<QProcess *> procs;
    for (auto &si : m_services) {
        if (si.process && si.process->state() != QProcess::NotRunning) {
            qInfo().noquote() << QStringLiteral("[ServiceManager] Stopping %1 (PID %2)")
                                     .arg(si.name).arg(si.process->processId());
            si.process->terminate();
            procs.append(si.process);
        }
    }

    // Attendre collectivement avec un deadline global de 3s,
    // puis force-kill ce qui reste (évite N×5s séquentiel)
    QDeadlineTimer deadline(3000);
    for (QProcess *proc : procs) {
        int remaining = static_cast<int>(deadline.remainingTime());
        if (remaining <= 0 || !proc->waitForFinished(remaining))
            proc->kill();
    }
}

// ── Utilitaires ─────────────────────────────────────────

int ServiceManager::readyCount() const
{
    int count = 0;
    for (const auto &si : m_services)
        if (si.status == ServiceInfo::Ready)
            ++count;
    return count;
}

QVariantList ServiceManager::serviceStatuses() const
{
    QVariantList list;
    for (const auto &si : m_services) {
        QVariantMap m;
        m[QStringLiteral("name")] = si.name;
        m[QStringLiteral("port")] = si.port;
        QString statusStr;
        switch (si.status) {
        case ServiceInfo::Unknown:   statusStr = QStringLiteral("unknown");   break;
        case ServiceInfo::Checking:  statusStr = QStringLiteral("checking");  break;
        case ServiceInfo::Running:   statusStr = QStringLiteral("running");   break;
        case ServiceInfo::Launching: statusStr = QStringLiteral("launching"); break;
        case ServiceInfo::Ready:     statusStr = QStringLiteral("ready");     break;
        case ServiceInfo::Failed:    statusStr = QStringLiteral("failed");    break;
        }
        m[QStringLiteral("status")] = statusStr;
        list.append(m);
    }
    return list;
}

void ServiceManager::setCurrentAction(const QString &action)
{
    if (m_currentAction != action) {
        m_currentAction = action;
        emit currentActionChanged();
    }
}

QString ServiceManager::pythonExeForVenv(const QString &venv) const
{
    return QDir(projectDir()).absoluteFilePath(venv + "/Scripts/python.exe");
}

QString ServiceManager::projectDir() const
{
    // Remonter de build/Debug → racine du projet
    QDir dir(QCoreApplication::applicationDirPath());
    dir.cdUp(); // Debug → build
    dir.cdUp(); // build → racine
    return dir.absolutePath();
}
