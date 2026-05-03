#ifndef CAMERAVISIONENGINE_H
#define CAMERAVISIONENGINE_H

#include <QObject>
#include <QTimer>
#include <QString>
#include <QVariantMap>
#include <QVariantList>
#include <QVector>
#include <qqml.h>

#include "VisionEnums.h"
#include "VisionDetections.h"
#include "CameraStreamManager.h"
#include "VisionModelRunner.h"
#include "VisionContext.h"
#include "VisionMemory.h"
#include "VisionEventRouter.h"

// ─────────────────────────────────────────────────────
//  CameraVisionEngine — orchestrateur principal
//  Pipeline : Capture → Preprocessing → IA →
//             PostProcessing → Events → CognitionSync
// ─────────────────────────────────────────────────────

class CameraVisionEngine : public QObject
{
    Q_OBJECT
    QML_ELEMENT

    // ── Propriétés QML ──
    Q_PROPERTY(int phase READ phase NOTIFY phaseChanged)
    Q_PROPERTY(bool running READ isRunning NOTIFY runningChanged)
    Q_PROPERTY(int cycleCount READ cycleCount NOTIFY cycleCompleted)
    Q_PROPERTY(int activeCameras READ activeCameraCount NOTIFY cameraCountChanged)
    Q_PROPERTY(int totalDetections READ totalDetections NOTIFY detectionsChanged)
    Q_PROPERTY(int totalPersons READ totalPersons NOTIFY detectionsChanged)
    Q_PROPERTY(double globalActivity READ globalActivity NOTIFY activityChanged)
    Q_PROPERTY(QVariantList recentEvents READ recentEvents NOTIFY eventsChanged)
    Q_PROPERTY(QVariantMap visionState READ visionState NOTIFY stateChanged)

public:
    explicit CameraVisionEngine(QObject *parent = nullptr);
    ~CameraVisionEngine() override;

    // ── Gestion caméras ──
    Q_INVOKABLE bool registerCamera(const QString &cameraId, const QString &url,
                                     const QString &roomId = QString());
    Q_INVOKABLE bool unregisterCamera(const QString &cameraId);
    Q_INVOKABLE bool startCamera(const QString &cameraId);
    Q_INVOKABLE void stopCamera(const QString &cameraId);
    Q_INVOKABLE void stopAllCameras();

    // ── Zones d'intrusion virtuelles ──
    Q_INVOKABLE void addIntrusionZone(const QString &zoneId,
                                       const QVariantList &polygon,
                                       bool lineMode = false);
    Q_INVOKABLE void removeIntrusionZone(const QString &zoneId);
    Q_INVOKABLE QStringList intrusionZoneIds() const;

    // ── Cycle de vision ──
    Q_INVOKABLE void runVisionCycle();
    Q_INVOKABLE void startAutoCycle(int intervalMs = 2000);
    Q_INVOKABLE void stopAutoCycle();

    // ── Configuration ──
    Q_INVOKABLE void setConfidenceThreshold(double threshold);
    Q_INVOKABLE void setEnabledModels(const QVariantList &modelIds);

    // ── Accès aux résultats ──
    int  phase() const;
    bool isRunning() const;
    int  cycleCount() const;
    int  activeCameraCount() const;
    int  totalDetections() const;
    int  totalPersons() const;
    double globalActivity() const;

    QVariantList recentEvents() const;
    QVariantMap  visionState() const;

    Q_INVOKABLE QVariantMap  getCameraStatus(const QString &cameraId) const;
    Q_INVOKABLE QVariantList getDetectionsByCamera(const QString &cameraId) const;
    Q_INVOKABLE QVariantList getDetectionsByRoom(const QString &roomId) const;
    Q_INVOKABLE QVariantMap  getActivityHeatmap() const;
    Q_INVOKABLE QVariantList getIncidentHistory(int maxCount = 50) const;
    Q_INVOKABLE QVariantMap  getVisionExplanation(const QString &eventId) const;

    // ── Sous-modules (accès pour tests / intégration) ──
    CameraStreamManager *streamManager() const;
    VisionModelRunner   *modelRunner() const;
    VisionDetections    *detections() const;
    VisionContext       *visionContext() const;
    VisionMemory        *visionMemory() const;
    VisionEventRouter   *eventRouter() const;

    // ── Persistance ──
    Q_INVOKABLE bool saveMemory(const QString &path) const;
    Q_INVOKABLE bool loadMemory(const QString &path);

signals:
    void phaseChanged(int phase);
    void runningChanged(bool running);
    void cycleCompleted(int count);
    void cameraCountChanged(int count);
    void detectionsChanged();
    void activityChanged(double level);
    void eventsChanged();
    void stateChanged();

    void visionEventDetected(const QVariantMap &event);
    void criticalEventDetected(const QVariantMap &event);

private:
    void setPhase(Vision::VisionPhase p);

    // ── Étapes du pipeline ──
    void phaseCapture();
    void phasePreprocessing();
    void phaseInference();
    void phasePostProcessing();
    void phaseEventRouting();
    void phaseCognitionSync();

    // ── Helpers ──
    void processFrameForCamera(const QString &cameraId);
    QVector<IntrusionZone> activeIntrusionZones() const;

    // ── Sous-modules (propriété totale) ──
    CameraStreamManager *m_streams    = nullptr;
    VisionModelRunner   *m_models     = nullptr;
    VisionDetections    *m_detections = nullptr;
    VisionContext       *m_context    = nullptr;
    VisionMemory        *m_memory    = nullptr;
    VisionEventRouter   *m_router    = nullptr;

    // ── État du cycle ──
    Vision::VisionPhase m_phase = Vision::VisionPhase::Idle;
    bool m_running     = false;
    int  m_cycleCount  = 0;

    QTimer m_autoCycleTimer;

    // ── Zones d'intrusion ──
    QVector<IntrusionZone> m_intrusionZones;

    // ── Résultats du dernier cycle ──
    QVector<FrameDetections> m_lastFrameDetections;
};

#endif // CAMERAVISIONENGINE_H
