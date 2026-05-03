#include "FireDetector.h"
#include <QUuid>

FireDetector::FireDetector(QObject *parent)
    : QObject(parent)
{
}

FireDetector::~FireDetector() = default;

void FireDetector::setSensorData(const QVariantMap &sensorData)      { m_sensorData  = sensorData; }
void FireDetector::setSimulationData(const QVariantMap &heatmapData) { m_heatmapData = heatmapData; }
void FireDetector::setHvacData(const QVariantMap &hvacData)          { m_hvacData    = hvacData; }

// ── Détection incendie ──

QVector<SecurityAlert> FireDetector::detectFire()
{
    QVector<SecurityAlert> alerts;

    const auto rooms = m_sensorData.value("rooms").toList();
    for (const auto &r : rooms) {
        const QVariantMap room = r.toMap();
        const QString roomId  = room.value("roomId").toString();
        double temperature    = room.value("temperature", 20.0).toDouble();
        double rateOfRise     = room.value("temperatureRateOfRise", 0.0).toDouble();

        // Seuil absolu de température
        if (temperature >= SpatialSecurity::kFireTemperatureThreshold) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Température critique dans %1 : %.1f°C").arg(roomId).arg(temperature),
                SpatialSecurity::SecuritySeverity::Emergency, 0.95,
                {{"trigger", "high_temperature"}, {"temperature", temperature},
                 {"threshold", SpatialSecurity::kFireTemperatureThreshold}}
            ));
        }
        // Montée rapide (>2°C/min)
        else if (rateOfRise > 2.0) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Montée rapide de température dans %1 : +%.1f°C/min").arg(roomId).arg(rateOfRise),
                SpatialSecurity::SecuritySeverity::High, 0.80,
                {{"trigger", "rapid_rise"}, {"rateOfRise", rateOfRise}, {"temperature", temperature}}
            ));
        }
    }

    m_lastAlerts = alerts;
    for (const auto &a : alerts)
        emit fireDetected(a.toVariantMap());

    return alerts;
}

// ── Détection fumée ──

QVector<SecurityAlert> FireDetector::detectSmoke()
{
    QVector<SecurityAlert> alerts;

    const auto rooms = m_sensorData.value("rooms").toList();
    for (const auto &r : rooms) {
        const QVariantMap room = r.toMap();
        const QString roomId = room.value("roomId").toString();
        double smokeLevel = room.value("smokeLevel", 0.0).toDouble();
        double co2Level   = room.value("co2", 0.0).toDouble();

        if (smokeLevel >= SpatialSecurity::kSmokeThreshold) {
            auto severity = (smokeLevel >= 0.7)
                ? SpatialSecurity::SecuritySeverity::Emergency
                : SpatialSecurity::SecuritySeverity::Critical;

            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Fumée détectée dans %1 (niveau %.0f%%)").arg(roomId).arg(smokeLevel * 100),
                severity, 0.90,
                {{"trigger", "smoke_detected"}, {"smokeLevel", smokeLevel}}
            ));
        }

        // CO₂ élevé peut indiquer un feu couvant
        if (co2Level >= SpatialSecurity::kCO2DangerLevel) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("CO₂ élevé dans %1 : %.0f ppm").arg(roomId).arg(co2Level),
                SpatialSecurity::SecuritySeverity::High, 0.70,
                {{"trigger", "high_co2"}, {"co2Level", co2Level},
                 {"threshold", SpatialSecurity::kCO2DangerLevel}}
            ));
        }
    }

    m_lastAlerts.append(alerts);
    for (const auto &a : alerts)
        emit fireDetected(a.toVariantMap());

    return alerts;
}

// ── Anomalie thermique ──

QVector<SecurityAlert> FireDetector::detectHeatAnomaly()
{
    QVector<SecurityAlert> alerts;

    // Vérifier propagation anormale via heatmap de simulation
    const auto zones = m_heatmapData.value("zones").toList();
    for (const auto &z : zones) {
        const QVariantMap zone = z.toMap();
        const QString roomId  = zone.value("roomId").toString();
        double heatIntensity  = zone.value("intensity", 0.0).toDouble();
        bool   isVentilated   = m_hvacData.value(roomId).toMap().value("active", false).toBool();

        // Chaleur intense dans pièce fermée (pas de ventilation)
        if (heatIntensity > 0.7 && !isVentilated) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Anomalie thermique dans %1 (intensité %.0f%%, sans ventilation)")
                    .arg(roomId).arg(heatIntensity * 100),
                SpatialSecurity::SecuritySeverity::High, 0.75,
                {{"trigger", "heat_anomaly"}, {"intensity", heatIntensity}, {"ventilated", false}}
            ));
        }

        // Propagation anormale : chaleur dans une pièce adjacente non chauffée
        bool unexpectedHeat = zone.value("unexpectedPropagation", false).toBool();
        if (unexpectedHeat) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Propagation thermique inattendue vers %1").arg(roomId),
                SpatialSecurity::SecuritySeverity::Medium, 0.65,
                {{"trigger", "heat_propagation"}, {"intensity", heatIntensity}}
            ));
        }
    }

    m_lastAlerts.append(alerts);
    for (const auto &a : alerts)
        emit fireDetected(a.toVariantMap());

    return alerts;
}

QVector<SecurityAlert> FireDetector::runAllDetections()
{
    m_lastAlerts.clear();
    detectFire();
    detectSmoke();
    detectHeatAnomaly();
    return m_lastAlerts;
}

// ── Explication ──

QString FireDetector::explainFire(const SecurityAlert &alert) const
{
    const QString trigger = alert.evidence.value("trigger").toString();

    if (trigger == "high_temperature")
        return QStringLiteral("La température dans %1 a atteint %.1f°C, dépassant le seuil critique "
                              "de %.0f°C. Risque d'incendie confirmé. Activation des sprinklers recommandée.")
                    .arg(alert.roomId)
                    .arg(alert.evidence.value("temperature").toDouble())
                    .arg(alert.evidence.value("threshold").toDouble());

    if (trigger == "rapid_rise")
        return QStringLiteral("La température dans %1 augmente à +%.1f°C/min. Cette montée rapide "
                              "peut indiquer un départ de feu. Surveillance renforcée recommandée.")
                    .arg(alert.roomId)
                    .arg(alert.evidence.value("rateOfRise").toDouble());

    if (trigger == "smoke_detected")
        return QStringLiteral("Le capteur de fumée dans %1 indique un niveau de %.0f%%. "
                              "Évacuation et vérification sur place recommandées.")
                    .arg(alert.roomId)
                    .arg(alert.evidence.value("smokeLevel").toDouble() * 100);

    if (trigger == "high_co2")
        return QStringLiteral("Le taux de CO₂ dans %1 atteint %.0f ppm (seuil : %.0f ppm). "
                              "Peut indiquer un feu couvant ou une ventilation défaillante.")
                    .arg(alert.roomId)
                    .arg(alert.evidence.value("co2Level").toDouble())
                    .arg(alert.evidence.value("threshold").toDouble());

    if (trigger == "heat_anomaly")
        return QStringLiteral("Concentrations thermiques anormales dans %1 (intensité %.0f%%) "
                              "sans ventilation active. Origine à vérifier.").arg(alert.roomId)
                    .arg(alert.evidence.value("intensity").toDouble() * 100);

    if (trigger == "heat_propagation")
        return QStringLiteral("Propagation de chaleur inattendue vers %1. "
                              "Vérifier s'il existe un foyer actif dans une pièce adjacente.").arg(alert.roomId);

    return alert.description;
}

QVariantList FireDetector::alertsToVariantList() const
{
    QVariantList list;
    for (const auto &a : m_lastAlerts)
        list.append(a.toVariantMap());
    return list;
}

SecurityAlert FireDetector::makeAlert(const QString &roomId, const QString &description,
                                       SpatialSecurity::SecuritySeverity severity, double confidence,
                                       const QVariantMap &evidence) const
{
    SecurityAlert alert;
    alert.id           = QUuid::createUuid().toString(QUuid::WithoutBraces);
    alert.riskType     = SpatialSecurity::RiskType::Fire;
    alert.severity     = severity;
    alert.detectorType = SpatialSecurity::DetectorType::Fire;
    alert.roomId       = roomId;
    alert.description  = description;
    alert.confidence   = confidence;
    alert.evidence     = evidence;
    alert.explanation  = description;
    alert.timestamp    = QDateTime::currentDateTime();
    return alert;
}
