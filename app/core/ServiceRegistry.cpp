#include "ServiceRegistry.h"
#include "LogManager.h"
#include <QProcess>

ServiceRegistry::ServiceEntry ServiceRegistry::s_nullEntry;

ServiceRegistry::ServiceRegistry(QObject *parent)
    : QObject(parent)
{
}

void ServiceRegistry::registerService(const Exo::ServiceDescriptor &desc)
{
    ServiceEntry entry;
    entry.descriptor = desc;
    entry.state = Exo::ServiceState::Stopped;
    m_entries.insert(desc.name, entry);
    if (!m_insertionOrder.contains(desc.name))
        m_insertionOrder.append(desc.name);
    emit registryChanged();
}

bool ServiceRegistry::contains(const QString &name) const
{
    return m_entries.contains(name);
}

const ServiceRegistry::ServiceEntry& ServiceRegistry::entry(const QString &name) const
{
    auto it = m_entries.constFind(name);
    return (it != m_entries.constEnd()) ? it.value() : s_nullEntry;
}

ServiceRegistry::ServiceEntry& ServiceRegistry::entry(const QString &name)
{
    return m_entries[name];
}

QStringList ServiceRegistry::serviceNames() const
{
    return m_insertionOrder;
}

int ServiceRegistry::readyCount() const
{
    int count = 0;
    for (auto it = m_entries.constBegin(); it != m_entries.constEnd(); ++it)
        if (it->state == Exo::ServiceState::Ready) ++count;
    return count;
}

bool ServiceRegistry::allReady() const
{
    if (m_entries.isEmpty()) return false;
    for (auto it = m_entries.constBegin(); it != m_entries.constEnd(); ++it)
        if (it->state != Exo::ServiceState::Ready) return false;
    return true;
}

void ServiceRegistry::setState(const QString &name, Exo::ServiceState newState)
{
    auto it = m_entries.find(name);
    if (it == m_entries.end()) return;

    Exo::ServiceState oldState = it->state;
    if (oldState == newState) return;

    it->state = newState;

    QString oldStr = Exo::serviceStateToString(oldState);
    QString newStr = Exo::serviceStateToString(newState);
    hLog() << "[Registry]" << name << ":" << oldStr << "→" << newStr;

    emit serviceStateChanged(name, oldStr, newStr);
    emit registryChanged();

    if (allReady())
        emit allServicesReady();
}

void ServiceRegistry::setProcess(const QString &name, QProcess *proc, qint64 pid)
{
    auto it = m_entries.find(name);
    if (it == m_entries.end()) return;
    it->process = proc;
    it->pid = pid;
}

void ServiceRegistry::setPhase(const QString &name, Exo::ReadinessPhase phase)
{
    auto it = m_entries.find(name);
    if (it == m_entries.end()) return;
    if (it->phase == phase) return;

    it->phase = phase;
    QString phaseStr = Exo::readinessPhaseToString(phase);
    hLog() << "[Registry]" << name << "phase →" << phaseStr;
    emit servicePhaseChanged(name, phaseStr);
    emit registryChanged();
}

void ServiceRegistry::incrementRetry(const QString &name)
{
    auto it = m_entries.find(name);
    if (it != m_entries.end()) ++it->retryCount;
}

void ServiceRegistry::resetRetry(const QString &name)
{
    auto it = m_entries.find(name);
    if (it != m_entries.end()) it->retryCount = 0;
}

QVariantList ServiceRegistry::serviceStatuses() const
{
    QVariantList list;
    // Iterate in registration order (boot order from services.json)
    for (const QString &name : m_insertionOrder) {
        auto it = m_entries.constFind(name);
        if (it == m_entries.constEnd()) continue;
        QVariantMap m;
        m[QStringLiteral("name")]   = it->descriptor.name;
        m[QStringLiteral("port")]   = it->descriptor.port;
        m[QStringLiteral("status")] = Exo::serviceStateToString(it->state);
        m[QStringLiteral("phase")]  = Exo::readinessPhaseToString(it->phase);
        m[QStringLiteral("pid")]    = it->pid;
        m[QStringLiteral("retries")] = it->retryCount;
        list.append(m);
    }
    return list;
}

QString ServiceRegistry::serviceState(const QString &name) const
{
    auto it = m_entries.constFind(name);
    if (it == m_entries.constEnd()) return QStringLiteral("unknown");
    return Exo::serviceStateToString(it->state);
}

QString ServiceRegistry::servicePhase(const QString &name) const
{
    auto it = m_entries.constFind(name);
    if (it == m_entries.constEnd()) return QStringLiteral("none");
    return Exo::readinessPhaseToString(it->phase);
}
