#pragma once

#include "LatencyMetrics.h"
#include <QObject>
#include <QJsonObject>
#include <QJsonArray>
#include <QMutex>
#include <QMap>
#include <QElapsedTimer>

// ─────────────────────────────────────────────────────
//  MetricsManager — façade métriques unifiée (v26)
//
//  Agrège LatencyMetrics (pipeline) + compteurs par module
//  + gauges temps-réel. API QML pour le dashboard.
// ─────────────────────────────────────────────────────
class MetricsManager : public QObject
{
    Q_OBJECT

public:
    static MetricsManager* instance();

    // ── Compteurs (monotoniques) ─────────────────────
    void increment(const QString &name, qint64 delta = 1);
    qint64 counter(const QString &name) const;

    // ── Gauges (valeur courante) ─────────────────────
    void setGauge(const QString &name, double value);
    double gauge(const QString &name) const;

    // ── Histogrammes (distribution) ──────────────────
    void recordValue(const QString &name, double value);
    QJsonObject histogram(const QString &name) const;

    // ── Pipeline latency (délègue à LatencyMetrics) ──
    LatencyMetrics* latency() const { return LatencyMetrics::instance(); }

    // ── Snapshots ────────────────────────────────────
    QJsonObject snapshot() const;
    void reset();

    // ── QML API ──────────────────────────────────────
    Q_INVOKABLE QJsonObject getMetricsReport() const;
    Q_INVOKABLE QJsonArray  getCounterNames() const;
    Q_INVOKABLE double      getCounter(const QString &name) const;
    Q_INVOKABLE double      getGauge(const QString &name) const;

signals:
    void metricsUpdated();

private:
    explicit MetricsManager(QObject *parent = nullptr);

    mutable QMutex m_mutex;
    QMap<QString, qint64>  m_counters;
    QMap<QString, double>  m_gauges;

    struct HistogramData {
        QVector<double> values;
        double sum   = 0;
        double min   = std::numeric_limits<double>::max();
        double max   = std::numeric_limits<double>::lowest();
        int    count = 0;
    };
    QMap<QString, HistogramData> m_histograms;

    static MetricsManager *s_instance;
    static constexpr int MAX_HISTOGRAM_VALUES = 1000;
};
