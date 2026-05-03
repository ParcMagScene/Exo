#include "DomoticAnomalyDetector.h"
#include <QUuid>

DomoticAnomalyDetector::DomoticAnomalyDetector(QObject *parent)
    : QObject(parent)
{
}

DomoticAnomalyDetector::~DomoticAnomalyDetector() = default;

void DomoticAnomalyDetector::setDeviceStates(const QVariantList &deviceStates)       { m_deviceStates   = deviceStates; }
void DomoticAnomalyDetector::setOccupancyData(const QVariantMap &occupancyData)      { m_occupancyData  = occupancyData; }
void DomoticAnomalyDetector::setSensorData(const QVariantMap &sensorData)            { m_sensorData     = sensorData; }
void DomoticAnomalyDetector::setAutomationHistory(const QVariantList &automationLogs){ m_automationLogs = automationLogs; }

// ── Lumière allumée dans pièce vide ──

QVector<SecurityAlert> DomoticAnomalyDetector::detectLightAnomaly()
{
    QVector<SecurityAlert> alerts;

    for (const auto &d : m_deviceStates) {
        const QVariantMap device = d.toMap();
        if (device.value("type").toString() != "light") continue;

        const QString roomId   = device.value("roomId").toString();
        const QString deviceId = device.value("deviceId").toString();
        bool lightOn    = device.value("on", false).toBool();
        bool occupied   = m_occupancyData.value(roomId, false).toBool();

        if (lightOn && !occupied) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Lumière allumée dans %1 (pièce vide) : %2").arg(roomId, deviceId),
                SpatialSecurity::SecuritySeverity::Low, 0.60,
                {{"trigger", "light_empty_room"}, {"deviceId", deviceId}}
            ));
        }
    }

    m_lastAlerts = alerts;
    for (const auto &a : alerts)
        emit domoticAnomalyDetected(a.toVariantMap());

    return alerts;
}

// ── Chauffage avec fenêtre ouverte ──

QVector<SecurityAlert> DomoticAnomalyDetector::detectHvacAnomaly()
{
    QVector<SecurityAlert> alerts;

    for (const auto &d : m_deviceStates) {
        const QVariantMap device = d.toMap();
        if (device.value("type").toString() != "heating"
            && device.value("type").toString() != "cooling") continue;

        const QString roomId   = device.value("roomId").toString();
        const QString deviceId = device.value("deviceId").toString();
        bool hvacOn = device.value("on", false).toBool();

        if (!hvacOn) continue;

        // Vérifier les ouvertures dans la pièce
        const auto openings = m_sensorData.value("openings").toList();
        for (const auto &o : openings) {
            const QVariantMap opening = o.toMap();
            if (opening.value("roomId").toString() != roomId) continue;
            bool isOpen = opening.value("open", false).toBool();

            if (isOpen) {
                QString hvacType = device.value("type").toString() == "heating"
                    ? QStringLiteral("Chauffage") : QStringLiteral("Climatisation");
                alerts.append(makeAlert(
                    roomId,
                    QStringLiteral("%1 actif dans %2 avec %3 ouverte")
                        .arg(hvacType, roomId, opening.value("name").toString()),
                    SpatialSecurity::SecuritySeverity::Medium, 0.80,
                    {{"trigger", "hvac_open_window"}, {"deviceId", deviceId},
                     {"opening", opening.value("name")}, {"hvacType", device.value("type")}}
                ));
            }
        }
    }

    m_lastAlerts.append(alerts);
    for (const auto &a : alerts)
        emit domoticAnomalyDetected(a.toVariantMap());

    return alerts;
}

// ── Incohérence capteurs ──

QVector<SecurityAlert> DomoticAnomalyDetector::detectSensorInconsistency()
{
    QVector<SecurityAlert> alerts;

    const auto rooms = m_sensorData.value("rooms").toList();
    for (const auto &r : rooms) {
        const QVariantMap room = r.toMap();
        const QString roomId  = room.value("roomId").toString();

        // Capteurs multiples de température dans la même pièce
        const auto temps = room.value("temperatures").toList();
        if (temps.size() >= 2) {
            double minT = 999.0, maxT = -999.0;
            for (const auto &t : temps) {
                double v = t.toDouble();
                if (v < minT) minT = v;
                if (v > maxT) maxT = v;
            }
            double delta = maxT - minT;
            if (delta > 5.0) {
                alerts.append(makeAlert(
                    roomId,
                    QStringLiteral("Écart température de %.1f°C dans %1 entre capteurs").arg(delta).arg(roomId),
                    SpatialSecurity::SecuritySeverity::Medium, 0.70,
                    {{"trigger", "sensor_inconsistency"}, {"delta", delta},
                     {"minTemp", minT}, {"maxTemp", maxT}, {"sensorCount", temps.size()}}
                ));
            }
        }

        // Capteur hors plage
        double humidity = room.value("humidity", -1.0).toDouble();
        if (humidity > 100.0 || (humidity >= 0.0 && humidity < 5.0)) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Capteur humidité suspect dans %1 : %.1f%%").arg(roomId).arg(humidity),
                SpatialSecurity::SecuritySeverity::Low, 0.65,
                {{"trigger", "sensor_out_of_range"}, {"sensorType", "humidity"}, {"value", humidity}}
            ));
        }
    }

    m_lastAlerts.append(alerts);
    for (const auto &a : alerts)
        emit domoticAnomalyDetected(a.toVariantMap());

    return alerts;
}

// ── Boucle d'automatisation ──

QVector<SecurityAlert> DomoticAnomalyDetector::detectAutomationLoop()
{
    QVector<SecurityAlert> alerts;

    // Détecter si un même appareil a été actionné >5 fois en 5 minutes
    QHash<QString, int> actionCounts;
    for (const auto &log : m_automationLogs) {
        const QVariantMap entry = log.toMap();
        const QString deviceId = entry.value("deviceId").toString();
        actionCounts[deviceId]++;
    }

    for (auto it = actionCounts.constBegin(); it != actionCounts.constEnd(); ++it) {
        if (it.value() > 5) {
            // Trouver la pièce de l'appareil
            QString roomId = QStringLiteral("unknown");
            for (const auto &d : m_deviceStates) {
                if (d.toMap().value("deviceId").toString() == it.key()) {
                    roomId = d.toMap().value("roomId").toString();
                    break;
                }
            }

            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Boucle d'automatisation détectée : %1 actionné %2 fois").arg(it.key()).arg(it.value()),
                SpatialSecurity::SecuritySeverity::High, 0.85,
                {{"trigger", "automation_loop"}, {"deviceId", it.key()}, {"actionCount", it.value()}}
            ));
        }
    }

    m_lastAlerts.append(alerts);
    for (const auto &a : alerts)
        emit domoticAnomalyDetected(a.toVariantMap());

    return alerts;
}

// ── Caméra hors-ligne ──

QVector<SecurityAlert> DomoticAnomalyDetector::detectCameraOffline()
{
    QVector<SecurityAlert> alerts;

    for (const auto &d : m_deviceStates) {
        const QVariantMap device = d.toMap();
        if (device.value("type").toString() != "camera") continue;

        const QString roomId   = device.value("roomId").toString();
        const QString deviceId = device.value("deviceId").toString();
        bool online = device.value("online", true).toBool();

        if (!online) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Caméra %1 hors-ligne dans %2").arg(deviceId, roomId),
                SpatialSecurity::SecuritySeverity::High, 0.90,
                {{"trigger", "camera_offline"}, {"deviceId", deviceId}}
            ));
        }
    }

    m_lastAlerts.append(alerts);
    for (const auto &a : alerts)
        emit domoticAnomalyDetected(a.toVariantMap());

    return alerts;
}

QVector<SecurityAlert> DomoticAnomalyDetector::runAllDetections()
{
    m_lastAlerts.clear();
    detectLightAnomaly();
    detectHvacAnomaly();
    detectSensorInconsistency();
    detectAutomationLoop();
    detectCameraOffline();
    return m_lastAlerts;
}

// ── Explication ──

QString DomoticAnomalyDetector::explainDomoticAnomaly(const SecurityAlert &alert) const
{
    const QString trigger = alert.evidence.value("trigger").toString();

    if (trigger == "light_empty_room")
        return QStringLiteral("La lumière %1 est allumée dans %2 alors qu'aucun occupant "
                              "n'est détecté. Gaspillage énergétique ou oubli.")
                    .arg(alert.evidence.value("deviceId").toString(), alert.roomId);

    if (trigger == "hvac_open_window")
        return QStringLiteral("Le système %1 fonctionne dans %2 avec %3 ouverte. "
                              "Perte d'énergie significative et risque de surchauffe du système.")
                    .arg(alert.evidence.value("hvacType").toString(), alert.roomId,
                         alert.evidence.value("opening").toString());

    if (trigger == "sensor_inconsistency")
        return QStringLiteral("Les %1 capteurs de température dans %2 montrent un écart de %.1f°C "
                              "(%.1f°C à %.1f°C). Un capteur est probablement défectueux.")
                    .arg(alert.evidence.value("sensorCount").toInt())
                    .arg(alert.roomId)
                    .arg(alert.evidence.value("delta").toDouble())
                    .arg(alert.evidence.value("minTemp").toDouble())
                    .arg(alert.evidence.value("maxTemp").toDouble());

    if (trigger == "sensor_out_of_range")
        return QStringLiteral("Le capteur %1 dans %2 rapporte une valeur anormale (%.1f). "
                              "Le capteur doit être recalibré ou remplacé.")
                    .arg(alert.evidence.value("sensorType").toString(), alert.roomId)
                    .arg(alert.evidence.value("value").toDouble());

    if (trigger == "automation_loop")
        return QStringLiteral("L'appareil %1 a été actionné %2 fois en peu de temps. "
                              "Probable boucle entre deux automatisations contradictoires.")
                    .arg(alert.evidence.value("deviceId").toString())
                    .arg(alert.evidence.value("actionCount").toInt());

    if (trigger == "camera_offline")
        return QStringLiteral("La caméra %1 dans %2 est hors-ligne. "
                              "Zone de surveillance non couverte. Vérifier alimentation et connexion.")
                    .arg(alert.evidence.value("deviceId").toString(), alert.roomId);

    return alert.description;
}

QVariantList DomoticAnomalyDetector::alertsToVariantList() const
{
    QVariantList list;
    for (const auto &a : m_lastAlerts)
        list.append(a.toVariantMap());
    return list;
}

SecurityAlert DomoticAnomalyDetector::makeAlert(const QString &roomId, const QString &description,
                                                  SpatialSecurity::SecuritySeverity severity, double confidence,
                                                  const QVariantMap &evidence) const
{
    SecurityAlert alert;
    alert.id           = QUuid::createUuid().toString(QUuid::WithoutBraces);
    alert.riskType     = SpatialSecurity::RiskType::DomoticAnomaly;
    alert.severity     = severity;
    alert.detectorType = SpatialSecurity::DetectorType::Domotic;
    alert.roomId       = roomId;
    alert.description  = description;
    alert.confidence   = confidence;
    alert.evidence     = evidence;
    alert.explanation  = description;
    alert.timestamp    = QDateTime::currentDateTime();
    return alert;
}
