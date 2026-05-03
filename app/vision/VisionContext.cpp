#include "VisionContext.h"
#include <QDebug>
#include <algorithm>
#include <numeric>

// ═══════════════════════════════════════════════════════
//  CameraSubsystemState
// ═══════════════════════════════════════════════════════

QVariantMap CameraSubsystemState::toVariant() const
{
    return {
        {"cameraId",       cameraId},
        {"roomId",         roomId},
        {"state",          static_cast<int>(state)},
        {"activityLevel",  activityLevel},
        {"personCount",    personCount},
        {"detectionCount", detectionCount},
        {"anomalyCount",   anomalyCount},
        {"lastUpdate",     lastUpdate.toString(Qt::ISODate)},
        {"details",        details}
    };
}

// ═══════════════════════════════════════════════════════
//  VisionContext
// ═══════════════════════════════════════════════════════

VisionContext::VisionContext(QObject *parent)
    : QObject(parent)
{
}

VisionContext::~VisionContext() = default;

// ── Mise à jour par caméra ──

void VisionContext::updateCameraState(const QString &cameraId, const CameraSubsystemState &state)
{
    m_cameras[cameraId] = state;
    recalculateGlobalLevel();
    emit cameraStateChanged(cameraId, static_cast<int>(state.state));
    emit contextUpdated();
}

void VisionContext::updateFromDetections(const QString &cameraId, const FrameDetections &fd)
{
    auto &cam = m_cameras[cameraId];
    cam.cameraId       = cameraId;
    cam.state          = Vision::CameraState::Streaming;
    cam.personCount    = fd.personCount();
    cam.detectionCount = fd.detections.size();
    cam.anomalyCount   = fd.hasAnomalies() ? 1 : 0;
    cam.lastUpdate     = fd.timestamp;

    // Activité proportionnelle aux détections
    cam.activityLevel = std::min(1.0, fd.detections.size() / 10.0);

    // Heatmap si roomId connu
    if (!cam.roomId.isEmpty()) {
        recordActivityInRoom(cam.roomId, cam.activityLevel);
    }

    if (fd.hasAnomalies()) {
        QVariantMap details;
        details["fireDetected"]        = fd.fireDetected;
        details["smokeDetected"]       = fd.smokeDetected;
        details["obstructionDetected"] = fd.obstructionDetected;
        details["obstructionLevel"]    = fd.obstructionLevel;
        emit anomalyDetected(cameraId, details);
    }

    recalculateGlobalLevel();
    emit contextUpdated();
}

void VisionContext::removeCameraState(const QString &cameraId)
{
    m_cameras.remove(cameraId);
    recalculateGlobalLevel();
    emit contextUpdated();
}

// ── Accès par caméra ──

CameraSubsystemState VisionContext::cameraState(const QString &cameraId) const
{
    return m_cameras.value(cameraId);
}

QStringList VisionContext::activeCameraIds() const
{
    QStringList ids;
    for (auto it = m_cameras.cbegin(); it != m_cameras.cend(); ++it) {
        if (it.value().state == Vision::CameraState::Streaming)
            ids.append(it.key());
    }
    return ids;
}

QStringList VisionContext::coveredRoomIds() const
{
    QStringList rooms;
    for (auto it = m_cameras.cbegin(); it != m_cameras.cend(); ++it) {
        if (!it.value().roomId.isEmpty() && !rooms.contains(it.value().roomId))
            rooms.append(it.value().roomId);
    }
    return rooms;
}

QStringList VisionContext::uncoveredRoomIds(const QStringList &allRoomIds) const
{
    QStringList covered = coveredRoomIds();
    QStringList uncovered;
    for (const auto &roomId : allRoomIds) {
        if (!covered.contains(roomId))
            uncovered.append(roomId);
    }
    return uncovered;
}

// ── État global ──

void VisionContext::update()
{
    recalculateGlobalLevel();
    emit contextUpdated();
}

QVariantMap VisionContext::snapshot() const
{
    QVariantList cameraStates;
    for (auto it = m_cameras.cbegin(); it != m_cameras.cend(); ++it)
        cameraStates.append(it.value().toVariant());

    return {
        {"globalActivityLevel", m_globalActivityLevel},
        {"activeCameras",       activeCameraCount()},
        {"totalPersons",        totalPersonCount()},
        {"totalDetections",     totalDetectionCount()},
        {"totalAnomalies",      totalAnomalyCount()},
        {"cameras",             cameraStates},
        {"activityHeatmap",     activityHeatmap()}
    };
}

QVariantMap VisionContext::diff(const QVariantMap &previous) const
{
    QVariantMap current = snapshot();
    QVariantMap result;
    for (auto it = current.cbegin(); it != current.cend(); ++it) {
        if (previous.value(it.key()) != it.value())
            result[it.key()] = it.value();
    }
    return result;
}

// ── Métriques globales ──

double VisionContext::globalActivityLevel() const
{
    return m_globalActivityLevel;
}

int VisionContext::totalPersonCount() const
{
    int total = 0;
    for (auto it = m_cameras.cbegin(); it != m_cameras.cend(); ++it)
        total += it.value().personCount;
    return total;
}

int VisionContext::totalDetectionCount() const
{
    int total = 0;
    for (auto it = m_cameras.cbegin(); it != m_cameras.cend(); ++it)
        total += it.value().detectionCount;
    return total;
}

int VisionContext::totalAnomalyCount() const
{
    int total = 0;
    for (auto it = m_cameras.cbegin(); it != m_cameras.cend(); ++it)
        total += it.value().anomalyCount;
    return total;
}

int VisionContext::activeCameraCount() const
{
    return activeCameraIds().size();
}

// ── Heatmap d'activité ──

void VisionContext::recordActivityInRoom(const QString &roomId, double intensity)
{
    // Moyenne mobile exponentielle
    double current = m_roomActivity.value(roomId, 0.0);
    m_roomActivity[roomId] = current * 0.7 + intensity * 0.3;
}

QVariantMap VisionContext::activityHeatmap() const
{
    QVariantMap map;
    for (auto it = m_roomActivity.cbegin(); it != m_roomActivity.cend(); ++it)
        map[it.key()] = it.value();
    return map;
}

double VisionContext::roomActivityLevel(const QString &roomId) const
{
    return m_roomActivity.value(roomId, 0.0);
}

// ── Requêtes spatiales ──

QStringList VisionContext::roomsWithPersons() const
{
    QStringList rooms;
    for (auto it = m_cameras.cbegin(); it != m_cameras.cend(); ++it) {
        if (it.value().personCount > 0 && !it.value().roomId.isEmpty()
            && !rooms.contains(it.value().roomId))
            rooms.append(it.value().roomId);
    }
    return rooms;
}

QStringList VisionContext::roomsWithAnomalies() const
{
    QStringList rooms;
    for (auto it = m_cameras.cbegin(); it != m_cameras.cend(); ++it) {
        if (it.value().anomalyCount > 0 && !it.value().roomId.isEmpty()
            && !rooms.contains(it.value().roomId))
            rooms.append(it.value().roomId);
    }
    return rooms;
}

QString VisionContext::busiestRoom() const
{
    QString busiest;
    double maxActivity = -1.0;
    for (auto it = m_roomActivity.cbegin(); it != m_roomActivity.cend(); ++it) {
        if (it.value() > maxActivity) {
            maxActivity = it.value();
            busiest = it.key();
        }
    }
    return busiest;
}

// ── Helpers ──

void VisionContext::recalculateGlobalLevel()
{
    if (m_cameras.isEmpty()) {
        m_globalActivityLevel = 0.0;
        emit activityLevelChanged(0.0);
        return;
    }

    double sum = 0.0;
    for (auto it = m_cameras.cbegin(); it != m_cameras.cend(); ++it)
        sum += it.value().activityLevel;

    m_globalActivityLevel = sum / m_cameras.size();
    emit activityLevelChanged(m_globalActivityLevel);
}
