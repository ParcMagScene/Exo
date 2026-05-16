#include "LogManager.h"
#include <QDebug>
#include <QDir>
#include <QStandardPaths>
#include <QDateTime>
#include <QTextStream>
#include <QCoreApplication>
#include <QJsonDocument>
#include <QGuiApplication>
#include <QClipboard>
#include <iostream>
#include <mutex>

// Définition des catégories de logging
Q_LOGGING_CATEGORY(exoMain, "exo.main")
Q_LOGGING_CATEGORY(exoConfig, "exo.config")
Q_LOGGING_CATEGORY(exoClaude, "exo.claude")
Q_LOGGING_CATEGORY(exoVoice, "exo.voice")
Q_LOGGING_CATEGORY(exoWeather, "exo.weather")
Q_LOGGING_CATEGORY(exoAssistant, "exo.assistant")

LogManager* LogManager::s_instance = nullptr;
static std::once_flag s_logManagerOnce;

LogManager* LogManager::instance()
{
    std::call_once(s_logManagerOnce, []() {
        s_instance = new LogManager();
    });
    return s_instance;
}

LogManager::LogManager(QObject *parent)
    : QObject(parent)
    , m_currentLevel(Info)
    , m_consoleEnabled(true)
    , m_fileEnabled(true)
    , m_oldHandler(nullptr)
    , m_sessionTimestamp()
{
    generateSessionTimestamp();
}
void LogManager::generateSessionTimestamp()
{
    // Format : YYYYMMDD_HHMMSS
    m_sessionTimestamp = QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss");
}

LogManager::~LogManager()
{
    if (m_oldHandler) {
        qInstallMessageHandler(m_oldHandler);
    }
}

void LogManager::initialize(LogLevel level, bool enableConsole, bool enableFile)
{
    m_currentLevel = level;
    m_consoleEnabled = enableConsole;
    m_fileEnabled = enableFile;
    
    // Installer notre gestionnaire de messages
    m_oldHandler = qInstallMessageHandler([](QtMsgType type, const QMessageLogContext &context, const QString &msg) {
        LogManager::instance()->handleMessage(type, context, msg);
    });
    
    // Configurer les règles de logging
    setupLoggingRules();
    
    if (m_fileEnabled) {
        enableFileLogging(); // Configure le chemin par défaut et crée le fichier
    }
    
    hLog() << "=== Système de logging EXO initialisé ===";
    hLog() << "Niveau:" << logLevelToString(m_currentLevel);
    hLog() << "Console:" << (m_consoleEnabled ? "Activée" : "Désactivée");
    hLog() << "Fichier:" << (m_fileEnabled ? "Activé" : "Désactivé");
}

void LogManager::setLogLevel(LogLevel level)
{
    m_currentLevel = level;
    setupLoggingRules();
    hLog() << "Niveau de logging changé à:" << logLevelToString(level);
}

void LogManager::setLogLevel(const QString &levelName)
{
    LogLevel level = stringToLogLevel(levelName);
    setLogLevel(level);
}

void LogManager::enableFileLogging(const QString &logFilePath)
{
    if (logFilePath.isEmpty()) {
        QString logDir = qEnvironmentVariable("EXO_LOGS_DIR", QStringLiteral("D:/EXO/logs"));
        if (!QDir().mkpath(logDir)) {
            fprintf(stderr, "[LogManager] mkpath failed for %s\n", qPrintable(logDir));
        }
        // Utiliser le timestamp de session pour le nom du fichier
        m_logFilePath = QDir(logDir).filePath(QString("exo_%1.log").arg(m_sessionTimestamp));
    } else {
        m_logFilePath = logFilePath;
    }

    m_fileEnabled = true;
    createLogFile();
    hLog() << "Logging fichier activé:" << m_logFilePath;
}

void LogManager::disableFileLogging()
{
    m_fileEnabled = false;
    m_logFilePath.clear();
    hLog() << "Logging fichier désactivé";
}

QString LogManager::logLevelToString(LogLevel level)
{
    switch (level) {
        case Debug:    return "Debug";
        case Info:     return "Info";
        case Warning:  return "Warning";
        case Critical: return "Critical";
        default:       return "Unknown";
    }
}

LogManager::LogLevel LogManager::stringToLogLevel(const QString &levelName)
{
    QString lower = levelName.toLower();
    if (lower == "debug") return Debug;
    if (lower == "info") return Info;
    if (lower == "warning") return Warning;
    if (lower == "critical") return Critical;
    return Info; // Par défaut
}

void LogManager::setupLoggingRules()
{
    // Activer/désactiver les catégories selon le niveau
    bool debugEnabled = (m_currentLevel <= Debug);
    bool infoEnabled = (m_currentLevel <= Info);
    bool warningEnabled = (m_currentLevel <= Warning);
    
    // Configuration des règles Qt Logging
    QString rules;
    if (debugEnabled) {
        rules += "exo.*.debug=true\n";
    } else {
        rules += "exo.*.debug=false\n";
    }
    
    if (infoEnabled) {
        rules += "exo.*.info=true\n";
    } else {
        rules += "exo.*.info=false\n";
    }
    
    if (warningEnabled) {
        rules += "exo.*.warning=true\n";
    } else {
        rules += "exo.*.warning=false\n";
    }
    
    rules += "exo.*.critical=true\n"; // Toujours activé
    
    QLoggingCategory::setFilterRules(rules);
}

void LogManager::createLogFile()
{
    if (m_logFilePath.isEmpty()) {
        return;
    }
    
    // S'assurer que le répertoire existe
    QFileInfo fileInfo(m_logFilePath);
    if (!QDir().mkpath(fileInfo.absolutePath())) {
        fprintf(stderr, "[LogManager] mkpath failed for %s\n",
                qPrintable(fileInfo.absolutePath()));
    }

    // Le fichier sera créé automatiquement lors de la première écriture
}

void LogManager::handleMessage(QtMsgType type, const QMessageLogContext &context, const QString &msg)
{
    // Filtrer les warnings internes Qt (QWebSocket destructor sur QTcpSocket détruit)
    if (type == QtWarningMsg && msg.contains(QLatin1String("wildcard call disconnects")))
        return;

    LogManager* manager = LogManager::instance();
    
    // Format du message
    QString timestamp = QDateTime::currentDateTime().toString("yyyy-MM-dd hh:mm:ss.zzz");
    QString typeStr;
    
    switch (type) {
        case QtDebugMsg:    typeStr = "DEBUG"; break;
        case QtInfoMsg:     typeStr = "INFO "; break;
        case QtWarningMsg:  typeStr = "WARN "; break;
        case QtCriticalMsg: typeStr = "CRIT "; break;
        case QtFatalMsg:    typeStr = "FATAL"; break;
    }
    
    // Extraire la catégorie proprement
    QString category = QString(context.category);
    if (category.startsWith("exo.")) {
        category = category.mid(4); // Supprimer "exo."
    }
    
    QString formattedMsg = QString("[%1] %2 [%3] %4")
                          .arg(timestamp)
                          .arg(typeStr)
                          .arg(category.toUpper())
                          .arg(msg);
    
    // Sortie console
    if (manager->m_consoleEnabled) {
        std::cout << formattedMsg.toStdString() << std::endl;
    }
    
    // Buffer pour exposition QML (thread-safe)
    {
        QMutexLocker lk(&manager->m_logMutex);
        manager->m_recentLogs.append(formattedMsg);
        while (manager->m_recentLogs.size() > MAX_LOG_ENTRIES)
            manager->m_recentLogs.removeFirst();
    }
    emit manager->newLogEntry(formattedMsg);

    // Sortie fichier
    if (manager->m_fileEnabled && !manager->m_logFilePath.isEmpty()) {
        manager->rotateIfNeeded();
        QFile logFile(manager->m_logFilePath);
        if (logFile.open(QIODevice::WriteOnly | QIODevice::Append)) {
            QTextStream stream(&logFile);
            stream << formattedMsg << Qt::endl;
            stream.flush(); // flush explicite pour visibilité immédiate
        }
    }
    
    // Pour les messages fatals, restaurer le gestionnaire par défaut
    if (type == QtFatalMsg) {
        if (manager->m_oldHandler) {
            qInstallMessageHandler(manager->m_oldHandler);
        }
        abort();
    }
}

void LogManager::rotateIfNeeded()
{
    QFileInfo fi(m_logFilePath);
    if (!fi.exists() || fi.size() < MAX_LOG_FILE_SIZE)
        return;

    // Rotation par session : exo_YYYYMMDD_HHMMSS.log.N
    for (int i = MAX_LOG_BACKUP_COUNT; i >= 1; --i) {
        QString src = (i == 1) ? m_logFilePath
                               : m_logFilePath + QStringLiteral(".%1").arg(i - 1);
        QString dst = m_logFilePath + QStringLiteral(".%1").arg(i);
        QFile::remove(dst);
        QFile::rename(src, dst);
    }
}

void LogManager::logPipelineEvent(const QJsonObject &event)
{
    QString compact = QString::fromUtf8(
        QJsonDocument(event).toJson(QJsonDocument::Compact));

    {
        QMutexLocker lk(&m_logMutex);
        m_pipelineEvents.append(compact);
        while (m_pipelineEvents.size() > MAX_PIPELINE_EVENTS)
            m_pipelineEvents.removeFirst();
    }

    emit newPipelineEvent(event);

    // Also write to log file if enabled
    if (m_fileEnabled && !m_logFilePath.isEmpty()) {
        QFile logFile(m_logFilePath);
        if (logFile.open(QIODevice::WriteOnly | QIODevice::Append)) {
            QTextStream stream(&logFile);
            stream << "[PIPELINE] " << compact << Qt::endl;
            stream.flush(); // flush explicite pour visibilité immédiate
        }
    }
}

QStringList LogManager::getLogsByFilter(const QString &filter) const
{
    QMutexLocker lk(&m_logMutex);
    if (filter.isEmpty()) return m_recentLogs;
    QStringList result;
    for (const QString &line : m_recentLogs) {
        if (line.contains(filter, Qt::CaseInsensitive))
            result.append(line);
    }
    return result;
}

void LogManager::copyToClipboard(const QString &text)
{
    if (auto *clip = QGuiApplication::clipboard())
        clip->setText(text);
}