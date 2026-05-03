#include "MetricsManager.h"
#include <QLoggingCategory>
#include <mutex>

Q_LOGGING_CATEGORY(exoMetrics, "exo.metrics")

MetricsManager *MetricsManager::s_instance = nullptr;
static std::once_flag s_metricsManagerOnce;

MetricsManager::MetricsManager(QObject *parent)
    : QObject(parent)
{
}

MetricsManager* MetricsManager::instance()
{
    std::call_once(s_metricsManagerOnce, []() {
        s_instance = new MetricsManager();
    });
    return s_instance;
}

// ── Compteurs ────────────────────────────────────────

void MetricsManager::increment(const QString &name, qint64 delta)
{
    QMutexLocker lock(&m_mutex);
    m_counters[name] += delta;
}

qint64 MetricsManager::counter(const QString &name) const
{
    QMutexLocker lock(&m_mutex);
    return m_counters.value(name, 0);
}

// ── Gauges ───────────────────────────────────────────

void MetricsManager::setGauge(const QString &name, double value)
{
    QMutexLocker lock(&m_mutex);
    m_gauges[name] = value;
}

double MetricsManager::gauge(const QString &name) const
{
    QMutexLocker lock(&m_mutex);
    return m_gauges.value(name, 0.0);
}

// ── Histogrammes ─────────────────────────────────────

void MetricsManager::recordValue(const QString &name, double value)
{
    QMutexLocker lock(&m_mutex);
    auto &h = m_histograms[name];
    h.sum += value;
    h.count++;
    if (value < h.min) h.min = value;
    if (value > h.max) h.max = value;
    if (h.values.size() < MAX_HISTOGRAM_VALUES)
        h.values.append(value);
}

QJsonObject MetricsManager::histogram(const QString &name) const
{
    QMutexLocker lock(&m_mutex);
    auto it = m_histograms.constFind(name);
    if (it == m_histograms.constEnd())
        return {};
    const auto &h = it.value();
    return {
        {"name", name},
        {"count", h.count},
        {"sum", h.sum},
        {"avg", h.count > 0 ? h.sum / h.count : 0.0},
        {"min", h.count > 0 ? h.min : 0.0},
        {"max", h.count > 0 ? h.max : 0.0},
    };
}

// ── Snapshot / Reset ─────────────────────────────────

QJsonObject MetricsManager::snapshot() const
{
    QMutexLocker lock(&m_mutex);
    QJsonObject counters;
    for (auto it = m_counters.constBegin(); it != m_counters.constEnd(); ++it)
        counters[it.key()] = it.value();

    QJsonObject gauges;
    for (auto it = m_gauges.constBegin(); it != m_gauges.constEnd(); ++it)
        gauges[it.key()] = it.value();

    QJsonArray hists;
    for (auto it = m_histograms.constBegin(); it != m_histograms.constEnd(); ++it) {
        const auto &h = it.value();
        hists.append(QJsonObject{
            {"name", it.key()},
            {"count", h.count},
            {"avg", h.count > 0 ? h.sum / h.count : 0.0},
            {"min", h.count > 0 ? h.min : 0.0},
            {"max", h.count > 0 ? h.max : 0.0},
        });
    }

    return {
        {"counters", counters},
        {"gauges", gauges},
        {"histograms", hists},
    };
}

void MetricsManager::reset()
{
    QMutexLocker lock(&m_mutex);
    m_counters.clear();
    m_gauges.clear();
    m_histograms.clear();
}

// ── QML API ──────────────────────────────────────────

QJsonObject MetricsManager::getMetricsReport() const
{
    QJsonObject report = snapshot();
    report["latency"] = latency()->getLatencyReport();
    return report;
}

QJsonArray MetricsManager::getCounterNames() const
{
    QMutexLocker lock(&m_mutex);
    QJsonArray names;
    for (auto it = m_counters.constBegin(); it != m_counters.constEnd(); ++it)
        names.append(it.key());
    return names;
}

double MetricsManager::getCounter(const QString &name) const
{
    return static_cast<double>(counter(name));
}

double MetricsManager::getGauge(const QString &name) const
{
    return gauge(name);
}
