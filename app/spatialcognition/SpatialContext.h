#ifndef SPATIALCONTEXT_H
#define SPATIALCONTEXT_H

#include "SpatialEnums.h"

#include <QObject>
#include <QString>
#include <QHash>
#include <QVariantMap>
#include <QVariantList>
#include <QDateTime>

// ─────────────────────────────────────────────────────
//  RoomState — État courant d'une pièce
// ─────────────────────────────────────────────────────
struct RoomState
{
    QString roomId;
    bool    occupied      = false;
    bool    illuminated   = false;
    double  temperature   = 20.0;
    double  humidity      = 50.0;
    double  noiseLevel    = 0.0;
    double  smokeLevel    = 0.0;
    double  co2Level      = 400.0;
    int     deviceCount   = 0;
    int     sensorCount   = 0;
    QStringList activeAlerts;

    QVariantMap toVariantMap() const;
};

// ─────────────────────────────────────────────────────
//  SpatialContext — Agrégateur d'état global spatial
//
//  Fusionne les données de :
//   • FloorPlan (pièces, objets)
//   • Réseau (appareils, connexions)
//   • Domotique (capteurs, états)
//   • Simulation (entités, propagation)
//   • Cognition (inférences, risques)
//
//  Fournit un snapshot cohérent pour le cycle cognitif.
// ─────────────────────────────────────────────────────
class SpatialContext : public QObject
{
    Q_OBJECT

public:
    explicit SpatialContext(QObject *parent = nullptr);
    ~SpatialContext() override;

    // ── Mise à jour par source ──
    void updateRoomStates(const QVariantList &rooms);
    void updateSensorStates(const QVariantMap &sensorData);
    void updateDeviceStates(const QVariantMap &deviceData);
    void updateNetworkState(const QVariantMap &networkData);
    void updateSimulationState(const QVariantMap &simState);
    void updateCognitionState(const QVariantMap &cognitionData);

    // ── Accès à l'état ──
    RoomState roomState(const QString &roomId) const;
    QVariantMap sensorState(const QString &sensorId) const;
    QVariantMap deviceState(const QString &deviceId) const;
    QVariantMap networkState() const { return m_networkState; }
    QVariantMap simulationState() const { return m_simulationState; }
    QVariantMap cognitionState() const { return m_cognitionState; }

    // ── Snapshot / Diff ──
    QVariantMap snapshot() const;
    QVariantMap diff(const QVariantMap &previousSnapshot) const;
    void update();

    // ── Requêtes ──
    QStringList occupiedRooms() const;
    QStringList alertRooms() const;
    QStringList offlineDevices() const;
    double globalRiskLevel() const;

    // ── Timestamp ──
    QDateTime lastUpdate() const { return m_lastUpdate; }

    // ── Clear ──
    void clear();

signals:
    void contextUpdated();
    void roomStateChanged(const QString &roomId);
    void alertTriggered(const QString &roomId, const QString &alertType);

private:
    QHash<QString, RoomState>   m_rooms;
    QHash<QString, QVariantMap> m_sensors;
    QHash<QString, QVariantMap> m_devices;
    QVariantMap                 m_networkState;
    QVariantMap                 m_simulationState;
    QVariantMap                 m_cognitionState;
    QDateTime                   m_lastUpdate;
};

#endif // SPATIALCONTEXT_H
