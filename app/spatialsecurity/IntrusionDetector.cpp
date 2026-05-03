#include "IntrusionDetector.h"
#include <QUuid>

// ─────────────────────────────────────────────────────
//  SecurityAlert
// ─────────────────────────────────────────────────────

QVariantMap SecurityAlert::toVariantMap() const
{
    return {
        {"id",           id},
        {"riskType",     static_cast<int>(riskType)},
        {"severity",     static_cast<int>(severity)},
        {"detectorType", static_cast<int>(detectorType)},
        {"roomId",       roomId},
        {"description",  description},
        {"confidence",   confidence},
        {"evidence",     evidence},
        {"explanation",  explanation},
        {"timestamp",    timestamp.toString(Qt::ISODate)}
    };
}

// ─────────────────────────────────────────────────────
//  IntrusionDetector
// ─────────────────────────────────────────────────────

IntrusionDetector::IntrusionDetector(QObject *parent)
    : QObject(parent)
{
}

IntrusionDetector::~IntrusionDetector() = default;

void IntrusionDetector::setSensorData(const QVariantMap &sensorData)      { m_sensorData    = sensorData; }
void IntrusionDetector::setOccupancyData(const QVariantMap &occupancyData){ m_occupancyData = occupancyData; }
void IntrusionDetector::setSimulationData(const QVariantList &trajectories){ m_trajectories  = trajectories; }
void IntrusionDetector::setForbiddenZones(const QStringList &zoneIds)     { m_forbiddenZones = zoneIds; }

// ── Détection d'intrusion principale ──

QVector<SecurityAlert> IntrusionDetector::detectIntrusion()
{
    QVector<SecurityAlert> alerts;

    // 1) Mouvement dans pièce non occupée
    const auto rooms = m_sensorData.value("rooms").toList();
    for (const auto &r : rooms) {
        const QVariantMap room = r.toMap();
        const QString roomId = room.value("roomId").toString();
        bool occupied = m_occupancyData.value(roomId, false).toBool();
        bool motionDetected = room.value("motion", false).toBool();

        if (motionDetected && !occupied) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Mouvement détecté dans %1 (pièce non occupée)").arg(roomId),
                SpatialSecurity::SecuritySeverity::High, 0.85,
                {{"trigger", "motion_unoccupied"}, {"motion", true}, {"occupied", false}}
            ));
        }

        // 2) Incohérence capteurs : mouvement sans chaleur humaine
        bool hasHeat = room.value("humanHeat", false).toBool();
        if (motionDetected && !hasHeat) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Mouvement sans signature thermique dans %1").arg(roomId),
                SpatialSecurity::SecuritySeverity::Medium, 0.6,
                {{"trigger", "motion_no_heat"}, {"motion", true}, {"humanHeat", false}}
            ));
        }
    }

    // 3) Ouverture porte/fenêtre inattendue
    const auto openings = m_sensorData.value("openings").toList();
    for (const auto &o : openings) {
        const QVariantMap opening = o.toMap();
        bool isOpen    = opening.value("open", false).toBool();
        bool expected  = opening.value("expected", true).toBool();
        const QString roomId = opening.value("roomId").toString();

        if (isOpen && !expected) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Ouverture inattendue : %1 dans %2")
                    .arg(opening.value("name").toString(), roomId),
                SpatialSecurity::SecuritySeverity::High, 0.9,
                {{"trigger", "unexpected_opening"}, {"device", opening.value("name")}}
            ));
        }
    }

    m_lastAlerts = alerts;
    for (const auto &a : alerts)
        emit intrusionDetected(a.toVariantMap());

    return alerts;
}

// ── Mouvement suspect (via simulation) ──

QVector<SecurityAlert> IntrusionDetector::detectSuspiciousMovement()
{
    QVector<SecurityAlert> alerts;

    for (const auto &t : m_trajectories) {
        const QVariantMap traj = t.toMap();
        bool suspicious = traj.value("suspicious", false).toBool();
        double speed    = traj.value("speed", 0.0).toDouble();
        const QString roomId = traj.value("roomId").toString();

        if (suspicious || speed > 5.0) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Trajectoire suspecte dans %1 (vitesse %.1f m/s)").arg(roomId).arg(speed),
                SpatialSecurity::SecuritySeverity::High, 0.75,
                {{"trigger", "suspicious_trajectory"}, {"speed", speed}, {"entityId", traj.value("entityId")}}
            ));
        }
    }

    m_lastAlerts.append(alerts);
    for (const auto &a : alerts)
        emit intrusionDetected(a.toVariantMap());

    return alerts;
}

// ── Entrée non autorisée (zone interdite) ──

QVector<SecurityAlert> IntrusionDetector::detectUnauthorizedEntry()
{
    QVector<SecurityAlert> alerts;

    const auto rooms = m_sensorData.value("rooms").toList();
    for (const auto &r : rooms) {
        const QVariantMap room = r.toMap();
        const QString roomId = room.value("roomId").toString();
        bool motionDetected = room.value("motion", false).toBool();

        if (motionDetected && m_forbiddenZones.contains(roomId)) {
            alerts.append(makeAlert(
                roomId,
                QStringLiteral("Présence dans zone interdite : %1").arg(roomId),
                SpatialSecurity::SecuritySeverity::Critical, 0.95,
                {{"trigger", "forbidden_zone"}, {"zone", roomId}}
            ));
        }
    }

    m_lastAlerts.append(alerts);
    for (const auto &a : alerts)
        emit intrusionDetected(a.toVariantMap());

    return alerts;
}

QVector<SecurityAlert> IntrusionDetector::runAllDetections()
{
    m_lastAlerts.clear();
    detectIntrusion();
    detectSuspiciousMovement();
    detectUnauthorizedEntry();
    return m_lastAlerts;
}

// ── Explication ──

QString IntrusionDetector::explainIntrusion(const SecurityAlert &alert) const
{
    const QString trigger = alert.evidence.value("trigger").toString();

    if (trigger == "motion_unoccupied")
        return QStringLiteral("Un capteur de mouvement a détecté une activité dans %1, "
                              "mais aucun occupant n'est enregistré dans cette pièce. "
                              "Cela peut indiquer une intrusion.").arg(alert.roomId);

    if (trigger == "motion_no_heat")
        return QStringLiteral("Un mouvement a été détecté dans %1 sans signature thermique "
                              "humaine correspondante. Possible animal, courant d'air, ou intrusion.").arg(alert.roomId);

    if (trigger == "unexpected_opening")
        return QStringLiteral("L'ouverture de %1 dans %2 n'était pas prévue. "
                              "Vérifier si un occupant autorisé est présent.")
                    .arg(alert.evidence.value("device").toString(), alert.roomId);

    if (trigger == "suspicious_trajectory")
        return QStringLiteral("Une trajectoire anormale a été simulée dans %1 "
                              "(vitesse %.1f m/s). Mouvement rapide ou erratique suspect.")
                    .arg(alert.roomId).arg(alert.evidence.value("speed").toDouble());

    if (trigger == "forbidden_zone")
        return QStringLiteral("Une présence a été détectée dans la zone interdite %1. "
                              "Alerte de sécurité maximale.").arg(alert.roomId);

    return alert.description;
}

QVariantList IntrusionDetector::alertsToVariantList() const
{
    QVariantList list;
    for (const auto &a : m_lastAlerts)
        list.append(a.toVariantMap());
    return list;
}

// ── Interne ──

SecurityAlert IntrusionDetector::makeAlert(const QString &roomId, const QString &description,
                                            SpatialSecurity::SecuritySeverity severity, double confidence,
                                            const QVariantMap &evidence) const
{
    SecurityAlert alert;
    alert.id           = QUuid::createUuid().toString(QUuid::WithoutBraces);
    alert.riskType     = SpatialSecurity::RiskType::Intrusion;
    alert.severity     = severity;
    alert.detectorType = SpatialSecurity::DetectorType::Intrusion;
    alert.roomId       = roomId;
    alert.description  = description;
    alert.confidence   = confidence;
    alert.evidence     = evidence;
    alert.explanation  = description;
    alert.timestamp    = QDateTime::currentDateTime();
    return alert;
}
