#pragma once

#include <QObject>
#include <QString>
#include <QVector>
#include <QVariantMap>
#include <QVariantList>
#include <QDateTime>
#include "SpatialSecurityEnums.h"
#include "IntrusionDetector.h"  // SecurityAlert

class FireDetector : public QObject
{
    Q_OBJECT

public:
    explicit FireDetector(QObject *parent = nullptr);
    ~FireDetector() override;

    // ── Données d'entrée ──
    void setSensorData(const QVariantMap &sensorData);
    void setSimulationData(const QVariantMap &heatmapData);
    void setHvacData(const QVariantMap &hvacData);

    // ── Détections ──
    QVector<SecurityAlert> detectFire();
    QVector<SecurityAlert> detectSmoke();
    QVector<SecurityAlert> detectHeatAnomaly();
    QVector<SecurityAlert> runAllDetections();

    // ── Explications ──
    QString explainFire(const SecurityAlert &alert) const;

    // ── Export ──
    QVariantList alertsToVariantList() const;

signals:
    void fireDetected(const QVariantMap &alert);

private:
    SecurityAlert makeAlert(const QString &roomId, const QString &description,
                            SpatialSecurity::SecuritySeverity severity, double confidence,
                            const QVariantMap &evidence) const;

    QVariantMap  m_sensorData;
    QVariantMap  m_heatmapData;
    QVariantMap  m_hvacData;
    QVector<SecurityAlert> m_lastAlerts;
};
