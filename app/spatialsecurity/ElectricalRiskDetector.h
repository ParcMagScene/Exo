#pragma once

#include <QObject>
#include <QString>
#include <QVector>
#include <QVariantMap>
#include <QVariantList>
#include "SpatialSecurityEnums.h"
#include "IntrusionDetector.h"  // SecurityAlert

class ElectricalRiskDetector : public QObject
{
    Q_OBJECT

public:
    explicit ElectricalRiskDetector(QObject *parent = nullptr);
    ~ElectricalRiskDetector() override;

    // ── Données d'entrée ──
    void setConsumptionData(const QVariantMap &consumptionData);
    void setDeviceData(const QVariantList &devices);
    void setCircuitData(const QVariantMap &circuitData);

    // ── Détections ──
    QVector<SecurityAlert> detectOverload();
    QVector<SecurityAlert> detectFaultyDevice();
    QVector<SecurityAlert> detectElectricalAnomaly();
    QVector<SecurityAlert> runAllDetections();

    // ── Explications ──
    QString explainElectricalRisk(const SecurityAlert &alert) const;

    // ── Export ──
    QVariantList alertsToVariantList() const;

signals:
    void electricalRiskDetected(const QVariantMap &alert);

private:
    SecurityAlert makeAlert(const QString &roomId, const QString &description,
                            SpatialSecurity::SecuritySeverity severity, double confidence,
                            const QVariantMap &evidence) const;

    QVariantMap  m_consumptionData;
    QVariantList m_devices;
    QVariantMap  m_circuitData;
    QVector<SecurityAlert> m_lastAlerts;
};
