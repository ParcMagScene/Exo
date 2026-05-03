#pragma once

#include <QObject>
#include <QJsonObject>
#include <QJsonArray>
#include <QMutex>
#include <QVector>
#include <QDateTime>

// ─────────────────────────────────────────────────────
//  ErrorRecord — erreur structurée
// ─────────────────────────────────────────────────────
struct ErrorRecord
{
    enum Severity { Warning, Error, Critical, Fatal };

    QString   id;
    QString   module;
    QString   message;
    Severity  severity = Error;
    QDateTime timestamp;
    QJsonObject context;
    bool      recovered = false;

    QJsonObject toJson() const {
        static const char* sevNames[] = {"warning", "error", "critical", "fatal"};
        return {
            {"id", id}, {"module", module}, {"message", message},
            {"severity", sevNames[severity]},
            {"timestamp", timestamp.toString(Qt::ISODate)},
            {"recovered", recovered}, {"context", context},
        };
    }
};

// ─────────────────────────────────────────────────────
//  ErrorManager — gestion centralisée des erreurs (v26)
//
//  Catégorise, enregistre et expose les erreurs de tous
//  les modules. Fournit des compteurs par sévérité et
//  module, et une API QML pour le dashboard.
// ─────────────────────────────────────────────────────
class ErrorManager : public QObject
{
    Q_OBJECT

public:
    static ErrorManager* instance();

    // ── Enregistrement ───────────────────────────────
    void reportError(const QString &module, const QString &message,
                     ErrorRecord::Severity severity = ErrorRecord::Error,
                     const QJsonObject &context = {});
    void reportRecovery(const QString &errorId);

    // ── Query ────────────────────────────────────────
    int errorCount(ErrorRecord::Severity minSeverity = ErrorRecord::Warning) const;
    int unresolvedCount() const;
    QVector<ErrorRecord> recentErrors(int maxCount = 50) const;
    QVector<ErrorRecord> errorsByModule(const QString &module) const;

    // ── QML API ──────────────────────────────────────
    Q_INVOKABLE QJsonObject getErrorSummary() const;
    Q_INVOKABLE QJsonArray  getRecentErrors(int maxCount = 20) const;
    Q_INVOKABLE int         getErrorCount() const;
    Q_INVOKABLE int         getCriticalCount() const;

    // ── Housekeeping ─────────────────────────────────
    void clear();

signals:
    void errorOccurred(const QJsonObject &error);
    void criticalError(const QString &module, const QString &message);

private:
    explicit ErrorManager(QObject *parent = nullptr);

    mutable QMutex m_mutex;
    QVector<ErrorRecord> m_errors;
    int m_nextId = 1;

    static ErrorManager *s_instance;
    static constexpr int MAX_ERRORS = 500;
};
