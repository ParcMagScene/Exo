#include "CameraVisionEngine.h"

#include <QDebug>
#include <QPointF>
#include <QDateTime>

// ═══════════════════════════════════════════════════════
//  CameraVisionEngine — Orchestrateur Vision IA
// ═══════════════════════════════════════════════════════

CameraVisionEngine::CameraVisionEngine(QObject *parent)
    : QObject(parent)
    , m_streams(new CameraStreamManager(this))
    , m_models(new VisionModelRunner(this))
    , m_detections(new VisionDetections(this))
    , m_context(new VisionContext(this))
    , m_memory(new VisionMemory(this))
    , m_router(new VisionEventRouter(this))
{
    // Relayer les événements critiques
    connect(m_detections, &VisionDetections::criticalEventDetected,
            this, &CameraVisionEngine::criticalEventDetected);

    // Relayer le compteur de caméras
    connect(m_streams, &CameraStreamManager::cameraCountChanged, this, [this]() {
        emit cameraCountChanged(m_streams->activeCameraCount());
    });

    // Relayer les événements routés vers QML
    connect(m_router, &VisionEventRouter::eventForDisplay,
            this, &CameraVisionEngine::visionEventDetected);

    // Auto-cycle timer
    connect(&m_autoCycleTimer, &QTimer::timeout, this, &CameraVisionEngine::runVisionCycle);
}

CameraVisionEngine::~CameraVisionEngine()
{
    stopAutoCycle();
    m_streams->closeAllStreams();
}

// ── Gestion caméras ──

bool CameraVisionEngine::registerCamera(const QString &cameraId, const QString &url,
                                          const QString &roomId)
{
    bool ok = m_streams->registerCamera(cameraId, url, roomId);
    if (ok) {
        CameraSubsystemState state;
        state.cameraId = cameraId;
        state.roomId   = roomId;
        state.state    = Vision::CameraState::Disconnected;
        m_context->updateCameraState(cameraId, state);
    }
    return ok;
}

bool CameraVisionEngine::unregisterCamera(const QString &cameraId)
{
    m_context->removeCameraState(cameraId);
    return m_streams->unregisterCamera(cameraId);
}

bool CameraVisionEngine::startCamera(const QString &cameraId)
{
    return m_streams->openStream(cameraId);
}

void CameraVisionEngine::stopCamera(const QString &cameraId)
{
    m_streams->closeStream(cameraId);
}

void CameraVisionEngine::stopAllCameras()
{
    m_streams->closeAllStreams();
}

// ── Zones d'intrusion virtuelles ──

void CameraVisionEngine::addIntrusionZone(const QString &zoneId,
                                            const QVariantList &polygon,
                                            bool lineMode)
{
    IntrusionZone zone;
    zone.id       = zoneId;
    zone.lineMode = lineMode;

    for (const auto &pt : polygon) {
        QVariantMap m = pt.toMap();
        zone.polygon.append(QPointF(m.value("x").toDouble(), m.value("y").toDouble()));
    }

    if (lineMode && zone.polygon.size() >= 2) {
        zone.lineStart = zone.polygon.first();
        zone.lineEnd   = zone.polygon.last();
    }

    // Remplacer si existe déjà
    for (int i = 0; i < m_intrusionZones.size(); ++i) {
        if (m_intrusionZones[i].id == zoneId) {
            m_intrusionZones[i] = zone;
            return;
        }
    }
    m_intrusionZones.append(zone);
}

void CameraVisionEngine::removeIntrusionZone(const QString &zoneId)
{
    for (int i = 0; i < m_intrusionZones.size(); ++i) {
        if (m_intrusionZones[i].id == zoneId) {
            m_intrusionZones.removeAt(i);
            return;
        }
    }
}

QStringList CameraVisionEngine::intrusionZoneIds() const
{
    QStringList ids;
    for (const auto &z : m_intrusionZones)
        ids.append(z.id);
    return ids;
}

// ── Cycle de vision ──

void CameraVisionEngine::runVisionCycle()
{
    if (m_running) return;
    m_running = true;
    emit runningChanged(true);

    m_lastFrameDetections.clear();

    phaseCapture();
    phasePreprocessing();
    phaseInference();
    phasePostProcessing();
    phaseEventRouting();
    phaseCognitionSync();

    setPhase(Vision::VisionPhase::Idle);
    m_running = false;
    ++m_cycleCount;
    emit runningChanged(false);
    emit cycleCompleted(m_cycleCount);
    emit stateChanged();
}

void CameraVisionEngine::startAutoCycle(int intervalMs)
{
    m_autoCycleTimer.start(intervalMs);
    qDebug() << "[CameraVisionEngine] Cycle automatique démarré toutes les" << intervalMs << "ms";
}

void CameraVisionEngine::stopAutoCycle()
{
    m_autoCycleTimer.stop();
    qDebug() << "[CameraVisionEngine] Cycle automatique arrêté";
}

// ── Configuration ──

void CameraVisionEngine::setConfidenceThreshold(double threshold)
{
    m_models->setConfidenceThreshold(threshold);
}

void CameraVisionEngine::setEnabledModels(const QVariantList &modelIds)
{
    QVector<Vision::VisionModel> models;
    for (const auto &v : modelIds)
        models.append(static_cast<Vision::VisionModel>(v.toInt()));
    m_models->setEnabledModels(models);
}

// ── Accès aux résultats ──

int CameraVisionEngine::phase() const { return static_cast<int>(m_phase); }
bool CameraVisionEngine::isRunning() const { return m_running; }
int CameraVisionEngine::cycleCount() const { return m_cycleCount; }
int CameraVisionEngine::activeCameraCount() const { return m_streams->activeCameraCount(); }
int CameraVisionEngine::totalDetections() const { return m_detections->totalDetections(); }
int CameraVisionEngine::totalPersons() const { return m_detections->personCount(); }
double CameraVisionEngine::globalActivity() const { return m_context->globalActivityLevel(); }

QVariantList CameraVisionEngine::recentEvents() const
{
    return m_detections->recentEvents();
}

QVariantMap CameraVisionEngine::visionState() const
{
    return {
        {"phase",           static_cast<int>(m_phase)},
        {"running",         m_running},
        {"cycleCount",      m_cycleCount},
        {"activeCameras",   m_streams->activeCameraCount()},
        {"totalDetections", m_detections->totalDetections()},
        {"totalPersons",    m_detections->personCount()},
        {"globalActivity",  m_context->globalActivityLevel()},
        {"context",         m_context->snapshot()},
        {"routingStats",    m_router->routingStatistics()},
        {"memorySize",      m_memory->totalIncidents()}
    };
}

QVariantMap CameraVisionEngine::getCameraStatus(const QString &cameraId) const
{
    return m_streams->getCameraInfo(cameraId);
}

QVariantList CameraVisionEngine::getDetectionsByCamera(const QString &cameraId) const
{
    return m_detections->getDetectionsByCamera(cameraId);
}

QVariantList CameraVisionEngine::getDetectionsByRoom(const QString &roomId) const
{
    return m_detections->getDetectionsByRoom(roomId);
}

QVariantMap CameraVisionEngine::getActivityHeatmap() const
{
    return m_context->activityHeatmap();
}

QVariantList CameraVisionEngine::getIncidentHistory(int maxCount) const
{
    return m_memory->incidentsToVariantList(maxCount);
}

QVariantMap CameraVisionEngine::getVisionExplanation(const QString &eventId) const
{
    // Recherche l'événement et génère une explication structurée
    auto events = m_memory->queryByType(Vision::DetectionType::Custom, 1000);

    for (const auto &inc : m_memory->unresolvedIncidents()) {
        if (inc.id == eventId) {
            QVariantMap explanation;
            explanation["id"]          = inc.id;
            explanation["type"]        = static_cast<int>(inc.type);
            explanation["severity"]    = static_cast<int>(inc.severity);
            explanation["description"] = inc.description;
            explanation["camera"]      = inc.cameraId;
            explanation["room"]        = inc.roomId;
            explanation["confidence"]  = inc.confidence;
            explanation["timestamp"]   = inc.timestamp.toString(Qt::ISODate);
            explanation["data"]        = inc.data;

            // Incidents similaires
            auto similar = m_memory->querySimilar(inc, 5);
            QVariantList simList;
            for (const auto &s : similar) simList.append(s.toVariant());
            explanation["similarIncidents"] = simList;

            return explanation;
        }
    }

    return {{"error", "Event not found"}, {"id", eventId}};
}

// ── Sous-modules ──

CameraStreamManager *CameraVisionEngine::streamManager() const { return m_streams; }
VisionModelRunner   *CameraVisionEngine::modelRunner() const   { return m_models; }
VisionDetections    *CameraVisionEngine::detections() const    { return m_detections; }
VisionContext       *CameraVisionEngine::visionContext() const { return m_context; }
VisionMemory        *CameraVisionEngine::visionMemory() const { return m_memory; }
VisionEventRouter   *CameraVisionEngine::eventRouter() const  { return m_router; }

// ── Persistance ──

bool CameraVisionEngine::saveMemory(const QString &path) const
{
    return m_memory->saveToFile(path);
}

bool CameraVisionEngine::loadMemory(const QString &path)
{
    return m_memory->loadFromFile(path);
}

// ── Pipeline phases ──

void CameraVisionEngine::setPhase(Vision::VisionPhase p)
{
    if (m_phase == p) return;
    m_phase = p;
    emit phaseChanged(static_cast<int>(p));
}

void CameraVisionEngine::phaseCapture()
{
    setPhase(Vision::VisionPhase::Capture);
    // Rien de spécial — les caméras capturent en continu via CameraStreamManager
}

void CameraVisionEngine::phasePreprocessing()
{
    setPhase(Vision::VisionPhase::Preprocessing);
    // Futur : resize, normalisation, augmentation
}

void CameraVisionEngine::phaseInference()
{
    setPhase(Vision::VisionPhase::Inference);

    QStringList cameraIds = m_streams->registeredCameraIds();
    for (const auto &camId : cameraIds) {
        if (m_streams->isCameraActive(camId)) {
            processFrameForCamera(camId);
        }
    }
}

void CameraVisionEngine::phasePostProcessing()
{
    setPhase(Vision::VisionPhase::PostProcessing);

    // Mettre à jour le contexte avec les dernières détections
    for (const auto &fd : m_lastFrameDetections) {
        m_context->updateFromDetections(fd.cameraId, fd);
        m_detections->addFrameDetections(fd);
    }

    emit detectionsChanged();
    emit activityChanged(m_context->globalActivityLevel());
}

void CameraVisionEngine::phaseEventRouting()
{
    setPhase(Vision::VisionPhase::EventRouting);

    // Router toutes les frames du cycle
    for (const auto &fd : m_lastFrameDetections) {
        m_router->routeFrameDetections(fd);
    }

    emit eventsChanged();
}

void CameraVisionEngine::phaseCognitionSync()
{
    setPhase(Vision::VisionPhase::CognitionSync);

    // Stocker les événements critiques en mémoire persistante
    for (const auto &fd : m_lastFrameDetections) {
        if (fd.hasAnomalies()) {
            VisionEvent event;
            event.id          = QString("cycle_%1_%2").arg(m_cycleCount).arg(fd.cameraId);
            event.cameraId    = fd.cameraId;
            event.type        = fd.fireDetected ? Vision::DetectionType::Fire
                              : fd.smokeDetected ? Vision::DetectionType::Smoke
                              : Vision::DetectionType::Obstruction;
            event.severity    = fd.fireDetected ? Vision::VisionSeverity::Emergency
                              : Vision::VisionSeverity::High;
            event.description = QStringLiteral("Anomalie cycle %1 — cam %2").arg(m_cycleCount).arg(fd.cameraId);
            event.timestamp   = fd.timestamp;
            m_memory->storeFromEvent(event);
        }
    }

    m_context->update();
}

// ── Helpers ──

void CameraVisionEngine::processFrameForCamera(const QString &cameraId)
{
    QImage frame = m_streams->readFrame(cameraId);
    if (frame.isNull()) return;

    FrameDetections fd = m_models->runAllModels(cameraId, frame, activeIntrusionZones());
    m_lastFrameDetections.append(fd);
}

QVector<IntrusionZone> CameraVisionEngine::activeIntrusionZones() const
{
    return m_intrusionZones;
}
