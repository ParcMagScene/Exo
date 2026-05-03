#pragma once

#include <QObject>
#include <QString>
#include <QVector>
#include <QVariantMap>
#include <QVariantList>
#include "SpatialSecurityEnums.h"
#include "IntrusionDetector.h"  // SecurityAlert

class DomoticAnomalyDetector : public QObject
{
    Q_OBJECT

public:
    explicit DomoticAnomalyDetector(QObject *parent = nullptr);
    ~DomoticAnomalyDetector() override;

    // ── Données d'entrée ──
    void setDeviceStates(const QVariantList &deviceStates);
    void setOccupancyData(const QVariantMap &occupancyData);
    void setSensorData(const QVariantMap &sensorData);
    void setAutomationHistory(const QVariantList &automationLogs);

    // ── Détections ──
    QVector<SecurityAlert> detectLightAnomaly();
    QVector<SecurityAlert> detectHvacAnomaly();
    QVector<SecurityAlert> detectSensorInconsistency();
    QVector<SecurityAlert> detectAutomationLoop();
    QVector<SecurityAlert> detectCameraOffline();
    QVector<SecurityAlert> runAllDetections();

    // ── Explications ──
    QString explainDomoticAnomaly(const SecurityAlert &alert) const;

    // ── Export ──
    QVariantList alertsToVariantList() const;

signals:
    void domoticAnomalyDetected(const QVariantMap &alert);

private:
    SecurityAlert makeAlert(const QString &roomId, const QString &description,
                            SpatialSecurity::SecuritySeverity severity, double confidence,
                            const QVariantMap &evidence) const;

    QVariantList m_deviceStates;
    QVariantMap  m_occupancyData;
    QVariantMap  m_sensorData;
    QVariantList m_automationLogs;
    QVector<SecurityAlert> m_lastAlerts;
};
