#pragma once

#include <QObject>
#include <QString>
#include <QVector>
#include <QVariantMap>
#include <QVariantList>
#include "SpatialSecurityEnums.h"
#include "IntrusionDetector.h"  // SecurityAlert

class NetworkRiskDetector : public QObject
{
    Q_OBJECT

public:
    explicit NetworkRiskDetector(QObject *parent = nullptr);
    ~NetworkRiskDetector() override;

    // ── Données d'entrée ──
    void setNetworkMapData(const QVariantMap &networkData);
    void setDeviceStatusData(const QVariantList &deviceStatuses);
    void setLatencyData(const QVariantMap &latencyData);

    // ── Détections ──
    QVector<SecurityAlert> detectOfflineDevices();
    QVector<SecurityAlert> detectHighLatency();
    QVector<SecurityAlert> detectDeadZones();
    QVector<SecurityAlert> runAllDetections();

    // ── Explications ──
    QString explainNetworkRisk(const SecurityAlert &alert) const;

    // ── Export ──
    QVariantList alertsToVariantList() const;

signals:
    void networkRiskDetected(const QVariantMap &alert);

private:
    SecurityAlert makeAlert(const QString &roomId, const QString &description,
                            SpatialSecurity::SecuritySeverity severity, double confidence,
                            const QVariantMap &evidence) const;

    QVariantMap  m_networkData;
    QVariantList m_deviceStatuses;
    QVariantMap  m_latencyData;
    QVector<SecurityAlert> m_lastAlerts;
};
