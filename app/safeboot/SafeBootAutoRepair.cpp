#include "SafeBootAutoRepair.h"
#include "../core/ServiceRegistry.h"
#include "../core/LogManager.h"
#include "SafeBootController.h"
#include <QDir>
#include <QFile>
#include <QCoreApplication>
#include <QTcpSocket>
#include <QDateTime>
#include <QWebSocket>
#include <QEventLoop>
#include <QTimer>
#include <QThread>

#ifdef _WIN32
#include <windows.h>
#include <tlhelp32.h>
#endif

// ═══════════════════════════════════════════════════════
//  SafeBootAutoRepair — implémentation EXO v30.3
// ═══════════════════════════════════════════════════════

SafeBootAutoRepair::SafeBootAutoRepair(QObject *parent)
    : QObject(parent)
{
}

void SafeBootAutoRepair::setRegistry(ServiceRegistry *registry)
{
    m_registry = registry;
}

void SafeBootAutoRepair::setController(SafeBootController *controller)
{
    m_controller = controller;
}

// ── Contrôle ────────────────────────────────────────────

void SafeBootAutoRepair::autoRepairAll()
{
    if (!m_registry || m_running) return;

    m_repairQueue.clear();
    m_attemptCount.clear();
    m_repairTimeline.clear();
    emit repairTimelineChanged();

    // Collecter les services KO (Failed ou Degraded)
    for (const QString &name : m_registry->serviceNames()) {
        const auto &e = m_registry->entry(name);
        if (e.state == Exo::ServiceState::Failed
         || e.state == Exo::ServiceState::Crashed) {
            m_repairQueue.append(name);
            m_attemptCount[name] = 0;
        }
    }

    if (m_repairQueue.isEmpty()) {
        hLog() << "[AutoRepair] Aucun service à réparer";
        emit repairCompleted();
        return;
    }

    m_running = true;
    emit runningChanged();

    addRepairEvent(QStringLiteral("repair_start"), {},
                   QStringLiteral("%1 service(s) à réparer").arg(m_repairQueue.size()));

    hLog() << "[AutoRepair] ═══ Démarrage réparation automatique —"
           << m_repairQueue.size() << "services ═══";

    processRepairQueue();
}

void SafeBootAutoRepair::autoRepairLoop()
{
    autoRepairAll();
}

void SafeBootAutoRepair::stop()
{
    if (!m_running) return;
    m_running = false;
    m_repairQueue.clear();
    addRepairEvent(QStringLiteral("repair_stopped"), {},
                   QStringLiteral("Réparation interrompue"));
    emit runningChanged();
}

void SafeBootAutoRepair::attemptRepair(const QString &serviceName)
{
    if (!m_registry || !m_registry->contains(serviceName)) return;

    int attempt = m_attemptCount.value(serviceName, 0) + 1;
    m_attemptCount[serviceName] = attempt;

    addRepairEvent(QStringLiteral("repair_attempt"), serviceName,
                   QStringLiteral("Tentative %1/%2").arg(attempt).arg(kMaxRepairAttempts));

    hLog() << "[AutoRepair]" << serviceName
           << "— tentative" << attempt << "/" << kMaxRepairAttempts;

    // Étape 1 : Purger le cache JSON du service
    clearServiceCache(serviceName);

    // Étape 2 : Vérifier/libérer le port
    const auto &desc = m_registry->entry(serviceName).descriptor;
    if (!checkPortAvailable(desc.port)) {
        hLog() << "[AutoRepair]" << serviceName
               << "— port" << desc.port << "occupé, tentative de libération";
        if (killProcessOnPort(desc.port)) {
            addRepairEvent(QStringLiteral("port_freed"), serviceName,
                           QStringLiteral("Port %1 libéré").arg(desc.port));
        } else {
            addRepairEvent(QStringLiteral("port_stuck"), serviceName,
                           QStringLiteral("Impossible de libérer le port %1").arg(desc.port));
            emit repairAttempted(serviceName, false);
            return;
        }
    }

    // Étape 3 : Relancer le microservice
    bool launched = restartService(serviceName);
    if (!launched) {
        addRepairEvent(QStringLiteral("launch_failed"), serviceName,
                       QStringLiteral("Échec du lancement"));
        emit repairAttempted(serviceName, false);
        return;
    }

    // Étape 4 : Attendre le handshake READY
    bool ready = waitForReady(serviceName, kReadyTimeoutMs);

    if (ready) {
        addRepairEvent(QStringLiteral("repair_success"), serviceName,
                       QStringLiteral("Service réparé et opérationnel"));
        hLog() << "[AutoRepair] ✓" << serviceName << "réparé avec succès";

        m_registry->setState(serviceName, Exo::ServiceState::Ready);
        emit repairAttempted(serviceName, true);
    } else {
        addRepairEvent(QStringLiteral("repair_failed"), serviceName,
                       QStringLiteral("Pas de READY après %1 ms").arg(kReadyTimeoutMs));
        hWarning(exoMain) << "[AutoRepair] ✗" << serviceName << "— pas de READY";
        emit repairAttempted(serviceName, false);
    }
}

// ── Pipeline de réparation ──────────────────────────────

void SafeBootAutoRepair::processRepairQueue()
{
    if (m_repairQueue.isEmpty()) {
        m_running = false;
        emit runningChanged();

        addRepairEvent(QStringLiteral("repair_complete"), {},
                       QStringLiteral("Cycle de réparation terminé"));

        hLog() << "[AutoRepair] ═══ Cycle de réparation terminé ═══";
        emit repairCompleted();
        return;
    }

    QString name = m_repairQueue.first();
    int attempts = m_attemptCount.value(name, 0);

    if (attempts >= kMaxRepairAttempts) {
        // Abandon pour ce service
        m_repairQueue.removeFirst();
        addRepairEvent(QStringLiteral("repair_abandoned"), name,
                       QStringLiteral("Abandon après %1 tentatives").arg(kMaxRepairAttempts));
        hWarning(exoMain) << "[AutoRepair]" << name
                          << "— abandon après" << kMaxRepairAttempts << "tentatives";

        // Continuer avec le prochain
        QTimer::singleShot(0, this, &SafeBootAutoRepair::processRepairQueue);
        return;
    }

    // Lancer la tentative de réparation
    attemptRepair(name);

    // Vérifier le résultat
    const auto &entry = m_registry->entry(name);
    if (entry.state == Exo::ServiceState::Ready) {
        // Succès → retirer de la queue
        m_repairQueue.removeFirst();
    } else if (m_attemptCount.value(name, 0) >= kMaxRepairAttempts) {
        // Max atteint → retirer
        m_repairQueue.removeFirst();
    }
    // Sinon : reste dans la queue pour un prochain essai

    // Prochain service avec backoff exponentiel
    int retryCount = m_attemptCount.value(name, 1);
    int delay = qMin(kRepairBaseDelayMs * (1 << (retryCount - 1)), kRepairMaxDelayMs);
    hLog() << "[AutoRepair]" << name << "— prochain essai dans" << delay << "ms";
    QTimer::singleShot(delay, this, &SafeBootAutoRepair::processRepairQueue);
}

// ── Relancer un microservice ────────────────────────────

bool SafeBootAutoRepair::restartService(const QString &serviceName)
{
    if (!m_registry->contains(serviceName)) return false;

    auto &entry = m_registry->entry(serviceName);
    const auto &desc = entry.descriptor;

    // Tuer le processus existant s'il tourne encore
    if (entry.process && entry.process->state() != QProcess::NotRunning) {
        hLog() << "[AutoRepair] Arrêt du processus existant" << serviceName;
        entry.process->terminate();
        // Attendre de manière non bloquante (force-kill après 2s)
        QProcess *oldProc = entry.process;
        QTimer::singleShot(2000, oldProc, [oldProc]() {
            if (oldProc->state() != QProcess::NotRunning)
                oldProc->kill();
            oldProc->deleteLater();
        });
        entry.process = nullptr;
    }

    // Construire les chemins
    QString pythonExe = pythonExeForVenv(desc.venv);
    if (!QFile::exists(pythonExe)) {
        hWarning(exoMain) << "[AutoRepair] Python introuvable:" << pythonExe;
        return false;
    }

    QString scriptPath = QDir(projectDir()).absoluteFilePath(desc.script);
    if (!QFile::exists(scriptPath)) {
        hWarning(exoMain) << "[AutoRepair] Script introuvable:" << scriptPath;
        return false;
    }

    // Lancer le processus
    auto *proc = new QProcess(this);
    proc->setWorkingDirectory(projectDir());

    // Variables d'environnement EXO
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
    proc->setProcessEnvironment(env);

    // Logs
    QDir logDir(ssd + "/logs");
    logDir.mkpath(".");
    proc->setStandardOutputFile(logDir.absoluteFilePath(
        serviceName.toLower() + "_repair_stdout.log"));
    proc->setStandardErrorFile(logDir.absoluteFilePath(
        serviceName.toLower() + "_repair_stderr.log"));

    QStringList args;
    args << scriptPath << desc.args;

    proc->start(pythonExe, args);

    if (!proc->waitForStarted(5000)) {
        hWarning(exoMain) << "[AutoRepair] Échec lancement" << serviceName;
        proc->deleteLater();
        return false;
    }

    qint64 pid = proc->processId();
    m_registry->setProcess(serviceName, proc, pid);
    m_registry->setState(serviceName, Exo::ServiceState::WaitingReady);

    hLog() << "[AutoRepair]" << serviceName
           << "relancé (PID" << pid << ")";

    return true;
}

// ── Purge du cache service ──────────────────────────────

bool SafeBootAutoRepair::clearServiceCache(const QString &serviceName)
{
    // Les microservices EXO stockent des caches dans D:/EXO/cache/<service>/
    const QString ssd = qEnvironmentVariable("EXO_SSD_ROOT", QStringLiteral("D:/EXO"));
    QDir cacheDir(ssd + "/cache/" + serviceName.toLower());

    if (!cacheDir.exists()) return true; // Pas de cache → OK

    // Supprimer uniquement les fichiers .json temporaires
    QStringList jsonFiles = cacheDir.entryList({"*.json.tmp", "*.json.lock"}, QDir::Files);
    for (const QString &f : jsonFiles) {
        cacheDir.remove(f);
    }

    hLog() << "[AutoRepair] Cache purgé pour" << serviceName
           << "(" << jsonFiles.size() << "fichiers)";
    return true;
}

// ── Vérification port ───────────────────────────────────

bool SafeBootAutoRepair::checkPortAvailable(int port)
{
    QTcpSocket socket;
    socket.connectToHost(QStringLiteral("127.0.0.1"), port);
    bool connected = socket.waitForConnected(200);
    socket.close();
    // Si on PEUT se connecter → le port est occupé → pas disponible
    return !connected;
}

bool SafeBootAutoRepair::killProcessOnPort(int port)
{
#ifdef _WIN32
    // Utiliser netstat pour trouver le PID, puis taskkill
    QProcess netstat;
    netstat.start(QStringLiteral("cmd.exe"),
                  {"/c", QStringLiteral("netstat -ano | findstr :%1 | findstr LISTENING").arg(port)});
    netstat.waitForFinished(3000);

    QString output = QString::fromLocal8Bit(netstat.readAllStandardOutput());
    QStringList lines = output.split('\n', Qt::SkipEmptyParts);

    for (const QString &line : lines) {
        QStringList parts = line.trimmed().split(QRegularExpression("\\s+"), Qt::SkipEmptyParts);
        if (parts.size() >= 5) {
            QString pidStr = parts.last().trimmed();
            bool ok;
            DWORD pid = pidStr.toULong(&ok);
            if (ok && pid > 0) {
                hLog() << "[AutoRepair] Kill PID" << pid << "sur port" << port;
                HANDLE hProc = OpenProcess(PROCESS_TERMINATE, FALSE, pid);
                if (hProc) {
                    TerminateProcess(hProc, 1);
                    CloseHandle(hProc);
                    // Attendre un instant que le port se libère
                    QThread::msleep(300);
                    return true;
                }
            }
        }
    }
    return false;
#else
    Q_UNUSED(port)
    return false;
#endif
}

// ── Attente du handshake READY via WebSocket ────────────

bool SafeBootAutoRepair::waitForReady(const QString &serviceName, int timeoutMs)
{
    if (!m_registry->contains(serviceName)) return false;

    const auto &desc = m_registry->entry(serviceName).descriptor;
    QUrl url(QStringLiteral("ws://localhost:%1").arg(desc.port));

    QWebSocket ws;
    QEventLoop loop;
    QTimer timer;
    bool gotReady = false;

    timer.setSingleShot(true);
    timer.setInterval(timeoutMs);

    QObject::connect(&timer, &QTimer::timeout, &loop, &QEventLoop::quit);
    QObject::connect(&ws, &QWebSocket::textMessageReceived,
                     [&](const QString &msg) {
        if (msg.contains(QLatin1String("ready"), Qt::CaseInsensitive)) {
            gotReady = true;
            loop.quit();
        }
    });
    QObject::connect(&ws, &QWebSocket::connected, [&]() {
        // Certains services envoient "ready" à la connexion
        // d'autres nécessitent un ping
    });

    // Polling de connexion : le service peut mettre du temps à ouvrir le port
    QTimer pollTimer;
    pollTimer.setInterval(200);
    int elapsed = 0;
    QObject::connect(&pollTimer, &QTimer::timeout, [&]() {
        elapsed += 200;
        if (elapsed > timeoutMs) {
            loop.quit();
            return;
        }
        if (ws.state() == QAbstractSocket::UnconnectedState) {
            ws.open(url);
        }
    });

    timer.start();
    pollTimer.start();
    ws.open(url);

    loop.exec();

    pollTimer.stop();
    timer.stop();
    ws.close();

    return gotReady;
}

// ── Utilitaires ─────────────────────────────────────────

QString SafeBootAutoRepair::pythonExeForVenv(const QString &venv) const
{
    return QDir(projectDir()).absoluteFilePath(venv + "/Scripts/python.exe");
}

QString SafeBootAutoRepair::projectDir() const
{
    QDir dir(QCoreApplication::applicationDirPath());
    dir.cdUp(); // Release → build
    dir.cdUp(); // build → racine
    return dir.absolutePath();
}

void SafeBootAutoRepair::addRepairEvent(const QString &event,
                                         const QString &service,
                                         const QString &detail)
{
    QVariantMap entry;
    entry[QStringLiteral("event")]     = event;
    entry[QStringLiteral("timestamp")] = QDateTime::currentDateTime().toString(Qt::ISODateWithMs);
    entry[QStringLiteral("service")]   = service;
    entry[QStringLiteral("detail")]    = detail;
    m_repairTimeline.append(entry);
    emit repairTimelineChanged();
}
