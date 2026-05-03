#ifndef INTRUSIONDETECTOR_H
#define INTRUSIONDETECTOR_H

#include <QObject>
#include <QString>
#include <QVariantMap>
#include <QVariantList>
#include <QVector>
#include <QDateTime>

#include "SpatialSecurityEnums.h"
#include "SpatialSecurityContext.h"

// ─────────────────────────────────────────────────────
//  SecurityAlert — Alerte produite par un détecteur
// ─────────────────────────────────────────────────────

struct SecurityAlert {
    QString id;
    SpatialSecurity::RiskType riskType;
    SpatialSecurity::SecuritySeverity severity;
    SpatialSecurity::DetectorType detectorType;
    QString roomId;
    QString description;
    double  confidence = 0.0;
    QVariantMap evidence;
    QString explanation;
    QDateTime timestamp;

    QVariantMap toVariantMap() const;
};

// ─────────────────────────────────────────────────────
//  IntrusionDetector — Détection d'intrusions spatiales
//
//  Détecte : mouvement en pièce vide, ouverture inattendue,
//  trajectoire suspecte, zone interdite, incohérence capteurs.
// ─────────────────────────────────────────────────────

class IntrusionDetector : public QObject
{
    Q_OBJECT

public:
    explicit IntrusionDetector(QObject *parent = nullptr);
    ~IntrusionDetector() override;

    // ── Données d'entrée ──
    void setSensorData(const QVariantMap &sensorData);
    void setOccupancyData(const QVariantMap &occupancyData);
    void setSimulationData(const QVariantList &trajectories);
    void setForbiddenZones(const QStringList &zoneIds);

    // ── Détection ──
    QVector<SecurityAlert> detectIntrusion();
    QVector<SecurityAlert> detectSuspiciousMovement();
    QVector<SecurityAlert> detectUnauthorizedEntry();
    QVector<SecurityAlert> runAllDetections();

    // ── Explication ──
    QString explainIntrusion(const SecurityAlert &alert) const;

    // ── Export ──
    QVariantList alertsToVariantList() const;

signals:
    void intrusionDetected(const QVariantMap &alert);

private:
    SecurityAlert makeAlert(const QString &roomId, const QString &description,
                            SpatialSecurity::SecuritySeverity severity, double confidence,
                            const QVariantMap &evidence) const;

    QVariantMap  m_sensorData;
    QVariantMap  m_occupancyData;
    QVariantList m_trajectories;
    QStringList  m_forbiddenZones;
    QVector<SecurityAlert> m_lastAlerts;
};

#endif // INTRUSIONDETECTOR_H
