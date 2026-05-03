#ifndef VISIONCONTEXT_H
#define VISIONCONTEXT_H

#include <QObject>
#include <QString>
#include <QVariantMap>
#include <QVariantList>
#include <QHash>
#include <QDateTime>
#include <QVector>

#include "VisionEnums.h"
#include "VisionDetections.h"

// ─────────────────────────────────────────────────────
//  CameraSubsystemState — État d'une caméra
// ─────────────────────────────────────────────────────

struct CameraSubsystemState {
    QString cameraId;
    QString roomId;
    Vision::CameraState state = Vision::CameraState::Disconnected;
    double activityLevel   = 0.0;   // 0..1
    int    personCount     = 0;
    int    detectionCount  = 0;
    int    anomalyCount    = 0;
    QDateTime lastUpdate;
    QVariantMap details;

    QVariantMap toVariant() const;
};

// ─────────────────────────────────────────────────────
//  VisionContext — État global du module vision
//
//  Agrège l'état de chaque caméra, zones couvertes,
//  détections actives, heatmap d'activité, anomalies.
// ─────────────────────────────────────────────────────

class VisionContext : public QObject
{
    Q_OBJECT

public:
    explicit VisionContext(QObject *parent = nullptr);
    ~VisionContext() override;

    // ── Mise à jour par caméra ──
    void updateCameraState(const QString &cameraId, const CameraSubsystemState &state);
    void updateFromDetections(const QString &cameraId, const FrameDetections &fd);
    void removeCameraState(const QString &cameraId);

    // ── Accès par caméra ──
    CameraSubsystemState cameraState(const QString &cameraId) const;
    QStringList activeCameraIds() const;
    QStringList coveredRoomIds() const;
    QStringList uncoveredRoomIds(const QStringList &allRoomIds) const;

    // ── État global ──
    void update();
    QVariantMap snapshot() const;
    QVariantMap diff(const QVariantMap &previous) const;

    // ── Métriques globales ──
    double globalActivityLevel() const;     // 0..1

    int totalPersonCount() const;
    int totalDetectionCount() const;
    int totalAnomalyCount() const;
    int activeCameraCount() const;

    // ── Heatmap d'activité ──
    void recordActivityInRoom(const QString &roomId, double intensity);
    QVariantMap activityHeatmap() const;
    double roomActivityLevel(const QString &roomId) const;

    // ── Requêtes spatiales ──
    QStringList roomsWithPersons() const;
    QStringList roomsWithAnomalies() const;
    QString busiestRoom() const;

signals:
    void contextUpdated();
    void cameraStateChanged(const QString &cameraId, int state);
    void activityLevelChanged(double level);
    void anomalyDetected(const QString &cameraId, const QVariantMap &details);

private:
    void recalculateGlobalLevel();

    QHash<QString, CameraSubsystemState> m_cameras;
    QHash<QString, double> m_roomActivity;       // roomId → activity 0..1
    double m_globalActivityLevel = 0.0;
};

#endif // VISIONCONTEXT_H
