#include "ElectricalRiskDetector.h"
#include <QUuid>

ElectricalRiskDetector::ElectricalRiskDetector(QObject *parent)
    : QObject(parent)
{
}

ElectricalRiskDetector::~ElectricalRiskDetector() = default;

void ElectricalRiskDetector::setConsumptionData(const QVariantMap &consumptionData) { m_consumptionData = consumptionData; }
void ElectricalRiskDetector::setDeviceData(const QVariantList &devices)             { m_devices          = devices; }
void ElectricalRiskDetector::setCircuitData(const QVariantMap &circuitData)         { m_circuitData      = circuitData; }

// ── Détection surcharge ──

QVector<SecurityAlert> ElectricalRiskDetector::detectOverload()
{
    QVector<SecurityAlert> alerts;

    const auto circuits = m_circuitData.value("circuits").toList();
    for (const auto &c : circuits) {
        const QVariantMap circuit = c.toMap();
        const QString circuitId  = circuit.value("circuitId").toString();
        const QString roomId     = circuit.value("roomId").toString();
        double currentWatts      = circuit.value("currentWatts", 0.0).toDouble();
        double maxWatts          = circuit.value("maxWatts", SpatialSecurity::kElectricalOverloadWatts).toDouble();

        double ratio = (maxWatts > 0) ? (currentWatts / maxWatts) : 0.0;

        if (currentWatts >= maxWatts) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Surcharge électrique circuit %1 : %.0fW / %.0fW").arg(circuitId).arg(currentWatts).arg(maxWatts),
                SpatialSecurity::SecuritySeverity::Critical, 0.95,
                {{"trigger", "overload"}, {"circuitId", circuitId}, {"currentWatts", currentWatts},
                 {"maxWatts", maxWatts}, {"ratio", ratio}}
            ));
        } else if (ratio >= 0.85) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Circuit %1 proche surcharge : %.0f%% capacité").arg(circuitId).arg(ratio * 100),
                SpatialSecurity::SecuritySeverity::High, 0.80,
                {{"trigger", "near_overload"}, {"circuitId", circuitId}, {"ratio", ratio},
                 {"currentWatts", currentWatts}, {"maxWatts", maxWatts}}
            ));
        }
    }

    // Consommation globale
    double totalWatts = m_consumptionData.value("totalWatts", 0.0).toDouble();
    double totalMax   = m_consumptionData.value("totalMaxWatts", 0.0).toDouble();
    if (totalMax > 0 && totalWatts >= totalMax) {
        alerts.append(makeAlert(
            QStringLiteral("global"),
            QStringLiteral("Surcharge globale : %.0fW / %.0fW").arg(totalWatts).arg(totalMax),
            SpatialSecurity::SecuritySeverity::Emergency, 0.98,
            {{"trigger", "global_overload"}, {"totalWatts", totalWatts}, {"totalMax", totalMax}}
        ));
    }

    m_lastAlerts = alerts;
    for (const auto &a : alerts)
        emit electricalRiskDetected(a.toVariantMap());

    return alerts;
}

// ── Détection appareil défectueux ──

QVector<SecurityAlert> ElectricalRiskDetector::detectFaultyDevice()
{
    QVector<SecurityAlert> alerts;

    for (const auto &d : m_devices) {
        const QVariantMap device = d.toMap();
        const QString deviceId  = device.value("deviceId").toString();
        const QString roomId    = device.value("roomId").toString();
        double consumption      = device.value("currentWatts", 0.0).toDouble();
        double nominalWatts     = device.value("nominalWatts", 0.0).toDouble();
        bool   isOn             = device.value("on", false).toBool();

        // Consommation anormale (>150% du nominal)
        if (isOn && nominalWatts > 0 && consumption > nominalWatts * 1.5) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Consommation anormale de %1 : %.0fW (nominal %.0fW)")
                    .arg(deviceId).arg(consumption).arg(nominalWatts),
                SpatialSecurity::SecuritySeverity::High, 0.80,
                {{"trigger", "abnormal_consumption"}, {"deviceId", deviceId},
                 {"consumption", consumption}, {"nominal", nominalWatts}}
            ));
        }

        // Appareil éteint mais consomme beaucoup (fuite)
        if (!isOn && consumption > 50.0) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Fuite électrique sur %1 : %.0fW en mode veille").arg(deviceId).arg(consumption),
                SpatialSecurity::SecuritySeverity::Medium, 0.70,
                {{"trigger", "phantom_consumption"}, {"deviceId", deviceId}, {"consumption", consumption}}
            ));
        }
    }

    m_lastAlerts.append(alerts);
    for (const auto &a : alerts)
        emit electricalRiskDetected(a.toVariantMap());

    return alerts;
}

// ── Anomalie électrique générale ──

QVector<SecurityAlert> ElectricalRiskDetector::detectElectricalAnomaly()
{
    QVector<SecurityAlert> alerts;

    // Fluctuations de tension
    double voltage = m_consumptionData.value("voltage", 230.0).toDouble();
    if (voltage < 200.0 || voltage > 250.0) {
        alerts.append(makeAlert(
            QStringLiteral("global"),
            QStringLiteral("Tension anormale : %.1fV (plage sécuritaire : 200-250V)").arg(voltage),
            (voltage < 180.0 || voltage > 260.0)
                ? SpatialSecurity::SecuritySeverity::Critical
                : SpatialSecurity::SecuritySeverity::Medium,
            0.85,
            {{"trigger", "voltage_anomaly"}, {"voltage", voltage}}
        ));
    }

    // Fréquence anormale
    double frequency = m_consumptionData.value("frequency", 50.0).toDouble();
    if (frequency < 49.5 || frequency > 50.5) {
        alerts.append(makeAlert(
            QStringLiteral("global"),
            QStringLiteral("Fréquence réseau anormale : %.2fHz").arg(frequency),
            SpatialSecurity::SecuritySeverity::Medium, 0.65,
            {{"trigger", "frequency_anomaly"}, {"frequency", frequency}}
        ));
    }

    m_lastAlerts.append(alerts);
    for (const auto &a : alerts)
        emit electricalRiskDetected(a.toVariantMap());

    return alerts;
}

QVector<SecurityAlert> ElectricalRiskDetector::runAllDetections()
{
    m_lastAlerts.clear();
    detectOverload();
    detectFaultyDevice();
    detectElectricalAnomaly();
    return m_lastAlerts;
}

// ── Explication ──

QString ElectricalRiskDetector::explainElectricalRisk(const SecurityAlert &alert) const
{
    const QString trigger = alert.evidence.value("trigger").toString();

    if (trigger == "overload")
        return QStringLiteral("Le circuit %1 consomme %.0fW pour une capacité maximale de %.0fW. "
                              "Risque de déclenchement du disjoncteur ou de surchauffe des câbles.")
                    .arg(alert.evidence.value("circuitId").toString())
                    .arg(alert.evidence.value("currentWatts").toDouble())
                    .arg(alert.evidence.value("maxWatts").toDouble());

    if (trigger == "near_overload")
        return QStringLiteral("Le circuit %1 fonctionne à %.0f%% de sa capacité. "
                              "Réduire la charge pour éviter une surcharge.")
                    .arg(alert.evidence.value("circuitId").toString())
                    .arg(alert.evidence.value("ratio").toDouble() * 100);

    if (trigger == "global_overload")
        return QStringLiteral("La consommation totale (%.0fW) dépasse la capacité maximale (%.0fW). "
                              "Risque de coupure générale imminente.")
                    .arg(alert.evidence.value("totalWatts").toDouble())
                    .arg(alert.evidence.value("totalMax").toDouble());

    if (trigger == "abnormal_consumption")
        return QStringLiteral("L'appareil %1 consomme %.0fW, soit plus de 150%% "
                              "de sa consommation nominale (%.0fW). Possible dysfonctionnement.")
                    .arg(alert.evidence.value("deviceId").toString())
                    .arg(alert.evidence.value("consumption").toDouble())
                    .arg(alert.evidence.value("nominal").toDouble());

    if (trigger == "phantom_consumption")
        return QStringLiteral("L'appareil %1 consomme %.0fW bien qu'il soit éteint. "
                              "Vérifier un possible court-circuit ou défaut d'isolation.")
                    .arg(alert.evidence.value("deviceId").toString())
                    .arg(alert.evidence.value("consumption").toDouble());

    if (trigger == "voltage_anomaly")
        return QStringLiteral("Tension réseau à %.1fV. La plage nominale est 200-250V. "
                              "Hors plage : risque pour les équipements sensibles.")
                    .arg(alert.evidence.value("voltage").toDouble());

    if (trigger == "frequency_anomaly")
        return QStringLiteral("Fréquence réseau à %.2fHz (nominal 50Hz). "
                              "Instabilité du réseau électrique détectée.")
                    .arg(alert.evidence.value("frequency").toDouble());

    return alert.description;
}

QVariantList ElectricalRiskDetector::alertsToVariantList() const
{
    QVariantList list;
    for (const auto &a : m_lastAlerts)
        list.append(a.toVariantMap());
    return list;
}

SecurityAlert ElectricalRiskDetector::makeAlert(const QString &roomId, const QString &description,
                                                 SpatialSecurity::SecuritySeverity severity, double confidence,
                                                 const QVariantMap &evidence) const
{
    SecurityAlert alert;
    alert.id           = QUuid::createUuid().toString(QUuid::WithoutBraces);
    alert.riskType     = SpatialSecurity::RiskType::Electrical;
    alert.severity     = severity;
    alert.detectorType = SpatialSecurity::DetectorType::Electrical;
    alert.roomId       = roomId;
    alert.description  = description;
    alert.confidence   = confidence;
    alert.evidence     = evidence;
    alert.explanation  = description;
    alert.timestamp    = QDateTime::currentDateTime();
    return alert;
}
