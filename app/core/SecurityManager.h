#pragma once

#include <QObject>
#include <QJsonObject>
#include <QJsonArray>
#include <QMutex>
#include <QMap>
#include <QSet>
#include <QDateTime>

// ─────────────────────────────────────────────────────
//  AuditEntry — entrée d'audit de sécurité
// ─────────────────────────────────────────────────────
struct AuditEntry
{
    QString   action;
    QString   module;
    QString   principal;   // "system", "user", "llm"
    bool      allowed = true;
    QDateTime timestamp;
    QJsonObject details;

    QJsonObject toJson() const {
        return {
            {"action", action}, {"module", module},
            {"principal", principal}, {"allowed", allowed},
            {"timestamp", timestamp.toString(Qt::ISODate)},
            {"details", details},
        };
    }
};

// ─────────────────────────────────────────────────────
//  SecurityManager — sécurité et audit centralisé (v26)
//
//  Gère les permissions par module, masque les clés API,
//  valide les appels réseau et tient un journal d'audit.
// ─────────────────────────────────────────────────────
class SecurityManager : public QObject
{
    Q_OBJECT

public:
    static SecurityManager* instance();

    // ── Permissions ──────────────────────────────────
    void grant(const QString &module, const QString &permission);
    void revoke(const QString &module, const QString &permission);
    bool isAllowed(const QString &module, const QString &permission) const;
    QStringList permissionsFor(const QString &module) const;

    // ── API key masking ──────────────────────────────
    static QString maskApiKey(const QString &key);
    static QString maskSensitive(const QString &text);

    // ── Audit ────────────────────────────────────────
    void audit(const QString &action, const QString &module,
               const QString &principal = QStringLiteral("system"),
               bool allowed = true, const QJsonObject &details = {});
    QVector<AuditEntry> recentAudit(int maxCount = 100) const;

    // ── Network validation ───────────────────────────
    bool isAllowedHost(const QString &host) const;
    void addAllowedHost(const QString &host);

    // ── QML API ──────────────────────────────────────
    Q_INVOKABLE QJsonObject getSecuritySummary() const;
    Q_INVOKABLE QJsonArray  getAuditLog(int maxCount = 50) const;
    Q_INVOKABLE bool        checkPermission(const QString &module,
                                            const QString &permission) const;

signals:
    void securityViolation(const QString &module, const QString &action);
    void auditLogged(const QJsonObject &entry);

private:
    explicit SecurityManager(QObject *parent = nullptr);

    mutable QMutex m_mutex;
    QMap<QString, QSet<QString>> m_permissions;
    QSet<QString>                m_allowedHosts;
    QVector<AuditEntry>          m_auditLog;

    static SecurityManager *s_instance;
    static constexpr int MAX_AUDIT_ENTRIES = 1000;
};
