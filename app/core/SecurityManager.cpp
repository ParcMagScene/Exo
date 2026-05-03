#include "SecurityManager.h"
#include <QLoggingCategory>
#include <mutex>

Q_LOGGING_CATEGORY(exoSecurity, "exo.security")

SecurityManager *SecurityManager::s_instance = nullptr;
static std::once_flag s_securityManagerOnce;

SecurityManager::SecurityManager(QObject *parent)
    : QObject(parent)
{
    // Default allowed hosts for EXO services
    m_allowedHosts = {
        "localhost",
        "127.0.0.1",
        "api.anthropic.com",
        "api.openweathermap.org",
    };
}

SecurityManager* SecurityManager::instance()
{
    std::call_once(s_securityManagerOnce, []() {
        s_instance = new SecurityManager();
    });
    return s_instance;
}

// ── Permissions ──────────────────────────────────────

void SecurityManager::grant(const QString &module, const QString &permission)
{
    QMutexLocker lock(&m_mutex);
    m_permissions[module].insert(permission);
    qCDebug(exoSecurity) << "Granted" << permission << "to" << module;
}

void SecurityManager::revoke(const QString &module, const QString &permission)
{
    QMutexLocker lock(&m_mutex);
    auto it = m_permissions.find(module);
    if (it != m_permissions.end())
        it->remove(permission);
}

bool SecurityManager::isAllowed(const QString &module, const QString &permission) const
{
    QMutexLocker lock(&m_mutex);
    auto it = m_permissions.constFind(module);
    if (it == m_permissions.constEnd())
        return false;
    return it->contains(permission) || it->contains("*");
}

QStringList SecurityManager::permissionsFor(const QString &module) const
{
    QMutexLocker lock(&m_mutex);
    auto it = m_permissions.constFind(module);
    if (it == m_permissions.constEnd())
        return {};
    return it->values();
}

// ── API Key Masking ──────────────────────────────────

QString SecurityManager::maskApiKey(const QString &key)
{
    if (key.length() <= 8)
        return QStringLiteral("****");
    return key.left(4) + QStringLiteral("...") + key.right(4);
}

QString SecurityManager::maskSensitive(const QString &text)
{
    QString result = text;

    // sk-ant-api03-... (Anthropic)
    static const QRegularExpression reAnt(
        QStringLiteral("(sk-ant-[a-zA-Z0-9-]{4})[a-zA-Z0-9-]+"));
    result.replace(reAnt, QStringLiteral("\\1****"));

    // sk-... (OpenAI / generic)
    static const QRegularExpression reSk(
        QStringLiteral("(sk-[a-zA-Z0-9]{4})[a-zA-Z0-9-]+"));
    result.replace(reSk, QStringLiteral("\\1****"));

    // Bearer tokens
    static const QRegularExpression reBearer(
        QStringLiteral("(Bearer\\s+)[^\\s\"']+"),
        QRegularExpression::CaseInsensitiveOption);
    result.replace(reBearer, QStringLiteral("\\1****"));

    // key-... / token-... prefixed secrets
    static const QRegularExpression reKeyTok(
        QStringLiteral("((?:key|token)-[a-zA-Z0-9]{4})[a-zA-Z0-9-]+"),
        QRegularExpression::CaseInsensitiveOption);
    result.replace(reKeyTok, QStringLiteral("\\1****"));

    // password= / passwd= / pwd= in URLs or config strings
    static const QRegularExpression rePwd(
        QStringLiteral("((?:password|passwd|pwd)=)[^&\\s\"']+"),
        QRegularExpression::CaseInsensitiveOption);
    result.replace(rePwd, QStringLiteral("\\1****"));

    // appid= / api_key= / apikey= / client_secret= in URLs or config strings
    static const QRegularExpression reApiParam(
        QStringLiteral("((?:appid|api_key|apikey|client_secret|access_token|refresh_token)=)[^&\\s\"']+"),
        QRegularExpression::CaseInsensitiveOption);
    result.replace(reApiParam, QStringLiteral("\\1****"));

    // Basic auth (Authorization: Basic <base64>)
    static const QRegularExpression reBasic(
        QStringLiteral("(Basic\\s+)[A-Za-z0-9+/=]{8,}"),
        QRegularExpression::CaseInsensitiveOption);
    result.replace(reBasic, QStringLiteral("\\1****"));

    return result;
}

// ── Audit ────────────────────────────────────────────

void SecurityManager::audit(const QString &action, const QString &module,
                            const QString &principal, bool allowed,
                            const QJsonObject &details)
{
    QMutexLocker lock(&m_mutex);

    AuditEntry entry;
    entry.action    = action;
    entry.module    = module;
    entry.principal = principal;
    entry.allowed   = allowed;
    entry.timestamp = QDateTime::currentDateTime();
    entry.details   = details;

    if (m_auditLog.size() >= MAX_AUDIT_ENTRIES)
        m_auditLog.removeFirst();
    m_auditLog.append(entry);

    if (!allowed) {
        qCWarning(exoSecurity) << "DENIED:" << principal << action << "on" << module;
        lock.unlock();
        emit securityViolation(module, action);
    } else {
        qCDebug(exoSecurity) << principal << action << "on" << module;
        lock.unlock();
        emit auditLogged(entry.toJson());
    }
}

// ── Network Validation ───────────────────────────────

bool SecurityManager::isAllowedHost(const QString &host) const
{
    QMutexLocker lock(&m_mutex);
    return m_allowedHosts.contains(host);
}

void SecurityManager::addAllowedHost(const QString &host)
{
    QMutexLocker lock(&m_mutex);
    m_allowedHosts.insert(host);
}

// ── QML API ──────────────────────────────────────────

QJsonObject SecurityManager::getSecuritySummary() const
{
    QMutexLocker lock(&m_mutex);
    int denied = 0;
    for (const auto &entry : m_auditLog) {
        if (!entry.allowed) ++denied;
    }
    return {
        {"module_count", m_permissions.size()},
        {"audit_entries", m_auditLog.size()},
        {"denied_actions", denied},
        {"allowed_hosts", static_cast<int>(m_allowedHosts.size())},
    };
}

QJsonArray SecurityManager::getAuditLog(int maxCount) const
{
    QMutexLocker lock(&m_mutex);
    QJsonArray arr;
    int start = qMax(0, m_auditLog.size() - maxCount);
    for (int i = start; i < m_auditLog.size(); ++i)
        arr.append(m_auditLog[i].toJson());
    return arr;
}

bool SecurityManager::checkPermission(const QString &module,
                                      const QString &permission) const
{
    return isAllowed(module, permission);
}
