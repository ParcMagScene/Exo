#include "ErrorManager.h"
#include <QLoggingCategory>
#include <mutex>

Q_LOGGING_CATEGORY(exoError, "exo.error")

ErrorManager *ErrorManager::s_instance = nullptr;
static std::once_flag s_errorManagerOnce;

ErrorManager::ErrorManager(QObject *parent)
    : QObject(parent)
{
}

ErrorManager* ErrorManager::instance()
{
    std::call_once(s_errorManagerOnce, []() {
        s_instance = new ErrorManager();
    });
    return s_instance;
}

// ── Enregistrement ───────────────────────────────────

void ErrorManager::reportError(const QString &module, const QString &message,
                               ErrorRecord::Severity severity,
                               const QJsonObject &context)
{
    QMutexLocker lock(&m_mutex);

    ErrorRecord rec;
    rec.id        = QString("ERR-%1").arg(m_nextId++, 5, 10, QChar('0'));
    rec.module    = module;
    rec.message   = message;
    rec.severity  = severity;
    rec.timestamp = QDateTime::currentDateTime();
    rec.context   = context;

    if (m_errors.size() >= MAX_ERRORS)
        m_errors.removeFirst();
    m_errors.append(rec);

    switch (severity) {
    case ErrorRecord::Warning:
        qCWarning(exoError) << "[" << module << "]" << message;
        break;
    case ErrorRecord::Error:
        qCWarning(exoError) << "[" << module << "] ERROR:" << message;
        break;
    case ErrorRecord::Critical:
    case ErrorRecord::Fatal:
        qCCritical(exoError) << "[" << module << "] CRITICAL:" << message;
        break;
    }

    QJsonObject json = rec.toJson();
    lock.unlock();

    emit errorOccurred(json);
    if (severity >= ErrorRecord::Critical)
        emit criticalError(module, message);
}

void ErrorManager::reportRecovery(const QString &errorId)
{
    QMutexLocker lock(&m_mutex);
    for (auto &rec : m_errors) {
        if (rec.id == errorId) {
            rec.recovered = true;
            qCInfo(exoError) << "Erreur récupérée :" << errorId;
            return;
        }
    }
}

// ── Query ────────────────────────────────────────────

int ErrorManager::errorCount(ErrorRecord::Severity minSeverity) const
{
    QMutexLocker lock(&m_mutex);
    int count = 0;
    for (const auto &rec : m_errors) {
        if (rec.severity >= minSeverity)
            ++count;
    }
    return count;
}

int ErrorManager::unresolvedCount() const
{
    QMutexLocker lock(&m_mutex);
    int count = 0;
    for (const auto &rec : m_errors) {
        if (!rec.recovered)
            ++count;
    }
    return count;
}

QVector<ErrorRecord> ErrorManager::recentErrors(int maxCount) const
{
    QMutexLocker lock(&m_mutex);
    int start = qMax(0, m_errors.size() - maxCount);
    return m_errors.mid(start);
}

QVector<ErrorRecord> ErrorManager::errorsByModule(const QString &module) const
{
    QMutexLocker lock(&m_mutex);
    QVector<ErrorRecord> result;
    for (const auto &rec : m_errors) {
        if (rec.module == module)
            result.append(rec);
    }
    return result;
}

// ── QML API ──────────────────────────────────────────

QJsonObject ErrorManager::getErrorSummary() const
{
    QMutexLocker lock(&m_mutex);
    int warnings = 0, errors = 0, criticals = 0, unresolved = 0;
    for (const auto &rec : m_errors) {
        switch (rec.severity) {
        case ErrorRecord::Warning:  ++warnings;  break;
        case ErrorRecord::Error:    ++errors;    break;
        case ErrorRecord::Critical:
        case ErrorRecord::Fatal:    ++criticals; break;
        }
        if (!rec.recovered) ++unresolved;
    }
    return {
        {"total", m_errors.size()},
        {"warnings", warnings},
        {"errors", errors},
        {"criticals", criticals},
        {"unresolved", unresolved},
    };
}

QJsonArray ErrorManager::getRecentErrors(int maxCount) const
{
    QJsonArray arr;
    auto recent = recentErrors(maxCount);
    for (const auto &rec : recent)
        arr.append(rec.toJson());
    return arr;
}

int ErrorManager::getErrorCount() const
{
    return errorCount(ErrorRecord::Error);
}

int ErrorManager::getCriticalCount() const
{
    return errorCount(ErrorRecord::Critical);
}

void ErrorManager::clear()
{
    QMutexLocker lock(&m_mutex);
    m_errors.clear();
    m_nextId = 1;
}
