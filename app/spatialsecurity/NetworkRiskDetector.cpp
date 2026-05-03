#include "NetworkRiskDetector.h"
#include <QUuid>

NetworkRiskDetector::NetworkRiskDetector(QObject *parent)
    : QObject(parent)
{
}

NetworkRiskDetector::~NetworkRiskDetector() = default;

void NetworkRiskDetector::setNetworkMapData(const QVariantMap &networkData)     { m_networkData    = networkData; }
void NetworkRiskDetector::setDeviceStatusData(const QVariantList &deviceStatuses){ m_deviceStatuses = deviceStatuses; }
void NetworkRiskDetector::setLatencyData(const QVariantMap &latencyData)        { m_latencyData    = latencyData; }

// ── Appareils hors-ligne ──

QVector<SecurityAlert> NetworkRiskDetector::detectOfflineDevices()
{
    QVector<SecurityAlert> alerts;
    int offlineCount = 0;

    for (const auto &d : m_deviceStatuses) {
        const QVariantMap device = d.toMap();
        const QString deviceId  = device.value("deviceId").toString();
        const QString roomId    = device.value("roomId").toString();
        bool online             = device.value("online", true).toBool();
        bool isCritical         = device.value("critical", false).toBool();

        if (!online) {
            ++offlineCount;
            auto severity = isCritical
                ? SpatialSecurity::SecuritySeverity::Critical
                : SpatialSecurity::SecuritySeverity::Medium;

            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Appareil %1 hors-ligne dans %2").arg(deviceId, roomId),
                severity, isCritical ? 0.95 : 0.75,
                {{"trigger", "device_offline"}, {"deviceId", deviceId},
                 {"critical", isCritical}, {"lastSeen", device.value("lastSeen")}}
            ));
        }
    }

    // Alerte globale si trop d'appareils hors-ligne
    int totalDevices = m_deviceStatuses.size();
    if (totalDevices > 0 && offlineCount > totalDevices / 3) {
        alerts.append(makeAlert(
            QStringLiteral("global"),
            QStringLiteral("Panne réseau massive : %1/%2 appareils hors-ligne").arg(offlineCount).arg(totalDevices),
            SpatialSecurity::SecuritySeverity::Emergency, 0.98,
            {{"trigger", "mass_offline"}, {"offlineCount", offlineCount}, {"totalDevices", totalDevices}}
        ));
    }

    m_lastAlerts = alerts;
    for (const auto &a : alerts)
        emit networkRiskDetected(a.toVariantMap());

    return alerts;
}

// ── Latence élevée ──

QVector<SecurityAlert> NetworkRiskDetector::detectHighLatency()
{
    QVector<SecurityAlert> alerts;

    const auto endpoints = m_latencyData.value("endpoints").toList();
    for (const auto &e : endpoints) {
        const QVariantMap ep = e.toMap();
        const QString endpointId = ep.value("endpointId").toString();
        const QString roomId     = ep.value("roomId").toString();
        double latencyMs         = ep.value("latencyMs", 0.0).toDouble();
        double packetLoss        = ep.value("packetLoss", 0.0).toDouble();

        if (latencyMs >= SpatialSecurity::kHighLatencyMs) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Latence critique vers %1 : %.0fms").arg(endpointId).arg(latencyMs),
                SpatialSecurity::SecuritySeverity::High, 0.85,
                {{"trigger", "high_latency"}, {"endpointId", endpointId},
                 {"latencyMs", latencyMs}, {"threshold", SpatialSecurity::kHighLatencyMs}}
            ));
        }

        if (packetLoss > 0.1) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Perte de paquets sur %1 : %.1f%%").arg(endpointId).arg(packetLoss * 100),
                SpatialSecurity::SecuritySeverity::High, 0.80,
                {{"trigger", "packet_loss"}, {"endpointId", endpointId}, {"packetLoss", packetLoss}}
            ));
        }
    }

    m_lastAlerts.append(alerts);
    for (const auto &a : alerts)
        emit networkRiskDetected(a.toVariantMap());

    return alerts;
}

// ── Zones mortes ──

QVector<SecurityAlert> NetworkRiskDetector::detectDeadZones()
{
    QVector<SecurityAlert> alerts;

    const auto coverageZones = m_networkData.value("coverageMap").toList();
    for (const auto &z : coverageZones) {
        const QVariantMap zone = z.toMap();
        const QString roomId  = zone.value("roomId").toString();
        double signalStrength = zone.value("signalStrength", 0.0).toDouble();
        bool   hasDevices     = zone.value("hasDevices", false).toBool();

        // Zone avec appareils mais sans couverture
        if (hasDevices && signalStrength < -80.0) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Zone morte réseau dans %1 (signal %.0f dBm)").arg(roomId).arg(signalStrength),
                SpatialSecurity::SecuritySeverity::Medium, 0.70,
                {{"trigger", "dead_zone"}, {"signalStrength", signalStrength}, {"hasDevices", true}}
            ));
        }

        // Zone totalement sans couverture
        if (signalStrength < -90.0) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Aucune couverture réseau dans %1").arg(roomId),
                SpatialSecurity::SecuritySeverity::High, 0.90,
                {{"trigger", "no_coverage"}, {"signalStrength", signalStrength}}
            ));
        }
    }

    m_lastAlerts.append(alerts);
    for (const auto &a : alerts)
        emit networkRiskDetected(a.toVariantMap());

    return alerts;
}

QVector<SecurityAlert> NetworkRiskDetector::runAllDetections()
{
    m_lastAlerts.clear();
    detectOfflineDevices();
    detectHighLatency();
    detectDeadZones();
    return m_lastAlerts;
}

// ── Explication ──

QString NetworkRiskDetector::explainNetworkRisk(const SecurityAlert &alert) const
{
    const QString trigger = alert.evidence.value("trigger").toString();

    if (trigger == "device_offline") {
        bool critical = alert.evidence.value("critical").toBool();
        return QStringLiteral("L'appareil %1 dans %2 est hors-ligne%3. "
                              "Dernière activité : %4.")
                    .arg(alert.evidence.value("deviceId").toString(), alert.roomId,
                         critical ? QStringLiteral(" (CRITIQUE)") : QString(),
                         alert.evidence.value("lastSeen").toString());
    }

    if (trigger == "mass_offline")
        return QStringLiteral("Panne réseau massive : %1 appareils sur %2 sont hors-ligne. "
                              "Vérifier le routeur, le switch ou l'alimentation électrique.")
                    .arg(alert.evidence.value("offlineCount").toInt())
                    .arg(alert.evidence.value("totalDevices").toInt());

    if (trigger == "high_latency")
        return QStringLiteral("La latence vers %1 atteint %.0fms (seuil : %.0fms). "
                              "Les commandes domotiques peuvent être retardées.")
                    .arg(alert.evidence.value("endpointId").toString())
                    .arg(alert.evidence.value("latencyMs").toDouble())
                    .arg(alert.evidence.value("threshold").toDouble());

    if (trigger == "packet_loss")
        return QStringLiteral("Perte de paquets de %.1f%% sur %1. "
                              "Fiabilité des capteurs et actionneurs compromise.")
                    .arg(alert.evidence.value("packetLoss").toDouble() * 100)
                    .arg(alert.evidence.value("endpointId").toString());

    if (trigger == "dead_zone")
        return QStringLiteral("La pièce %1 est une zone morte réseau (signal %.0f dBm) "
                              "contenant des appareils connectés. Ajouter un répéteur recommandé.")
                    .arg(alert.roomId)
                    .arg(alert.evidence.value("signalStrength").toDouble());

    if (trigger == "no_coverage")
        return QStringLiteral("Aucune couverture réseau dans %1 (signal %.0f dBm). "
                              "Les capteurs dans cette zone ne peuvent pas communiquer.")
                    .arg(alert.roomId)
                    .arg(alert.evidence.value("signalStrength").toDouble());

    return alert.description;
}

QVariantList NetworkRiskDetector::alertsToVariantList() const
{
    QVariantList list;
    for (const auto &a : m_lastAlerts)
        list.append(a.toVariantMap());
    return list;
}

SecurityAlert NetworkRiskDetector::makeAlert(const QString &roomId, const QString &description,
                                              SpatialSecurity::SecuritySeverity severity, double confidence,
                                              const QVariantMap &evidence) const
{
    SecurityAlert alert;
    alert.id           = QUuid::createUuid().toString(QUuid::WithoutBraces);
    alert.riskType     = SpatialSecurity::RiskType::NetworkFailure;
    alert.severity     = severity;
    alert.detectorType = SpatialSecurity::DetectorType::Network;
    alert.roomId       = roomId;
    alert.description  = description;
    alert.confidence   = confidence;
    alert.evidence     = evidence;
    alert.explanation  = description;
    alert.timestamp    = QDateTime::currentDateTime();
    return alert;
}
