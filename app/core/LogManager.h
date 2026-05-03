#pragma once

#include <QObject>
#include <QLoggingCategory>
#include <QString>
#include <QJsonObject>
#include <QMutex>
#include <QMutexLocker>

/**
 * @brief Gestionnaire centralisé de logging pour EXO
 * 
 * Fournit des catégories de logging organisées et configurables
 * pour remplacer les qDebug() dispersés dans le code.
 */

// Déclaration des catégories de logging
Q_DECLARE_LOGGING_CATEGORY(exoMain)
Q_DECLARE_LOGGING_CATEGORY(exoConfig)
Q_DECLARE_LOGGING_CATEGORY(exoClaude)
Q_DECLARE_LOGGING_CATEGORY(exoVoice)
Q_DECLARE_LOGGING_CATEGORY(exoWeather)
Q_DECLARE_LOGGING_CATEGORY(exoAssistant)

class LogManager : public QObject
{
    Q_OBJECT

public:
    enum LogLevel {
        Debug = 0,
        Info = 1,
        Warning = 2,
        Critical = 3
    };
    Q_ENUM(LogLevel)

    static LogManager* instance();
    
    // Configuration du système de logging
    void initialize(LogLevel level = Info, bool enableConsole = true, bool enableFile = false);
    void setLogLevel(LogLevel level);
    void setLogLevel(const QString &levelName);
    
    // Gestion des fichiers de log
    void enableFileLogging(const QString &logFilePath = QString());
    void disableFileLogging();
    
    // Utilitaires
    static QString logLevelToString(LogLevel level);
    static LogLevel stringToLogLevel(const QString &levelName);

    Q_INVOKABLE QStringList getRecentLogs() const { QMutexLocker lk(&m_logMutex); return m_recentLogs; }
    Q_INVOKABLE QStringList getLogsByFilter(const QString &filter) const;
    Q_INVOKABLE void clearLogs() { QMutexLocker lk(&m_logMutex); m_recentLogs.clear(); }
    Q_INVOKABLE void copyToClipboard(const QString &text);

    // Structured pipeline logging
    Q_INVOKABLE QStringList getRecentPipelineEvents() const { QMutexLocker lk(&m_logMutex); return m_pipelineEvents; }
    void logPipelineEvent(const QJsonObject &event);

signals:
    void newLogEntry(const QString &entry);
    void newPipelineEvent(const QJsonObject &event);

public slots:
    void handleMessage(QtMsgType type, const QMessageLogContext &context, const QString &msg);

private:
    explicit LogManager(QObject *parent = nullptr);
    ~LogManager();
    
    void setupLoggingRules();
    void createLogFile();
    void rotateIfNeeded();
    
    static LogManager* s_instance;
    
    LogLevel m_currentLevel;
    bool m_consoleEnabled;
    bool m_fileEnabled;
    QString m_logFilePath;
    
    // Ancienne fonction de message pour restauration
    QtMessageHandler m_oldHandler;

    // Mutex pour accès thread-safe aux buffers
    mutable QMutex m_logMutex;

    // Buffer circulaire pour le QML LogPanel
    QStringList m_recentLogs;
    static constexpr int MAX_LOG_ENTRIES = 500;

    // Pipeline events for structured logging
    QStringList m_pipelineEvents;
    static constexpr int MAX_PIPELINE_EVENTS = 200;
    static constexpr qint64 MAX_LOG_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
    static constexpr int MAX_LOG_BACKUP_COUNT = 3;
};

// Macros de convenance pour un usage simplifié
#define hLog()      qCInfo(exoMain)
#define hConfig()   qCInfo(exoConfig)
#define hClaude()   qCInfo(exoClaude)
#define hVoice()    qCInfo(exoVoice)
#define hWeather()  qCInfo(exoWeather)
#define hAssistant() qCInfo(exoAssistant)

#define hDebug(category)    qCDebug(category)
#define hWarning(category)  qCWarning(category)
#define hCritical(category) qCCritical(category)