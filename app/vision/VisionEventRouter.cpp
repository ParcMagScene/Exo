#include "VisionEventRouter.h"
#include <QDebug>
#include <QUuid>
#include <QDateTime>

// ═══════════════════════════════════════════════════════
//  VisionEventRouter
// ═══════════════════════════════════════════════════════

VisionEventRouter::VisionEventRouter(QObject *parent)
    : QObject(parent)
{
}

// ── Entrée : détections d'une frame ──

void VisionEventRouter::routeFrameDetections(const FrameDetections &fd)
{
    // 1. Route vers cognition (toutes les détections)
    if (m_cognitionEnabled) {
        routeToCognition(fd);
    }

    // 2. Route vers simulation (validation)
    if (m_simulationEnabled) {
        routeToSimulation(fd);
    }

    // 3. Génère des événements sécurité pour les détections critiques
    for (const auto &det : fd.detections) {
        VisionEvent event;
        event.id        = QUuid::createUuid().toString(QUuid::WithoutBraces);
        event.cameraId  = fd.cameraId;
        event.type      = det.type;
        event.roomId    = det.roomId;
        event.confidence = det.confidence;
        event.timestamp = fd.timestamp;

        bool isSecurityRelevant = false;

        switch (det.type) {
        case Vision::DetectionType::Intrusion:
            event.severity    = Vision::VisionSeverity::Critical;
            event.description = QStringLiteral("Intrusion détectée — ligne virtuelle franchie");
            isSecurityRelevant = true;
            break;
        case Vision::DetectionType::Fire:
            event.severity    = Vision::VisionSeverity::Emergency;
            event.description = QStringLiteral("Feu détecté par caméra");
            isSecurityRelevant = true;
            break;
        case Vision::DetectionType::Smoke:
            event.severity    = Vision::VisionSeverity::High;
            event.description = QStringLiteral("Fumée détectée par caméra");
            isSecurityRelevant = true;
            break;
        case Vision::DetectionType::Fall:
            event.severity    = Vision::VisionSeverity::Critical;
            event.description = QStringLiteral("Chute détectée — personne au sol");
            isSecurityRelevant = true;
            break;
        case Vision::DetectionType::Obstruction:
            event.severity    = Vision::VisionSeverity::High;
            event.description = QStringLiteral("Caméra obstruée — visibilité réduite");
            isSecurityRelevant = true;
            break;
        case Vision::DetectionType::Loitering:
            event.severity    = Vision::VisionSeverity::Medium;
            event.description = QStringLiteral("Comportement suspect — errance prolongée");
            isSecurityRelevant = true;
            break;
        case Vision::DetectionType::Agitation:
            event.severity    = Vision::VisionSeverity::High;
            event.description = QStringLiteral("Agitation détectée");
            isSecurityRelevant = true;
            break;
        default:
            break;
        }

        if (isSecurityRelevant) {
            event.details = detectionToVariant(det);
            routeEvent(event);
        }
    }

    // 4. Anomalies globales de la frame
    if (fd.fireDetected) {
        VisionEvent fire;
        fire.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
        fire.cameraId    = fd.cameraId;
        fire.type        = Vision::DetectionType::Fire;
        fire.severity    = Vision::VisionSeverity::Emergency;
        fire.description = QStringLiteral("Feu — détection frame globale");
        fire.timestamp   = fd.timestamp;
        routeEvent(fire);
    }

    if (fd.smokeDetected) {
        VisionEvent smoke;
        smoke.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
        smoke.cameraId    = fd.cameraId;
        smoke.type        = Vision::DetectionType::Smoke;
        smoke.severity    = Vision::VisionSeverity::High;
        smoke.description = QStringLiteral("Fumée — détection frame globale");
        smoke.timestamp   = fd.timestamp;
        routeEvent(smoke);
    }

    if (fd.obstructionDetected) {
        VisionEvent obs;
        obs.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
        obs.cameraId    = fd.cameraId;
        obs.type        = Vision::DetectionType::Obstruction;
        obs.severity    = Vision::VisionSeverity::High;
        obs.description = QStringLiteral("Obstruction — niveau %1%").arg(
            QString::number(fd.obstructionLevel * 100, 'f', 0));
        obs.timestamp   = fd.timestamp;
        routeEvent(obs);
    }

    // 5. Overlay QML
    emit overlayUpdate(frameToOverlayData(fd));

    ++m_totalRouted;
}

// ── Entrée : événement vision unique ──

void VisionEventRouter::routeEvent(const VisionEvent &event)
{
    if (m_securityEnabled) {
        routeToSecurity(event);
    }

    routeToQml(event);
    ++m_totalRouted;
}

void VisionEventRouter::routeEvents(const QVector<VisionEvent> &events)
{
    for (const auto &event : events)
        routeEvent(event);
}

// ── Configuration ──

void VisionEventRouter::setSecurityEnabled(bool enabled)  { m_securityEnabled = enabled; }
void VisionEventRouter::setCognitionEnabled(bool enabled)  { m_cognitionEnabled = enabled; }
void VisionEventRouter::setSimulationEnabled(bool enabled) { m_simulationEnabled = enabled; }

bool VisionEventRouter::isSecurityEnabled() const  { return m_securityEnabled; }
bool VisionEventRouter::isCognitionEnabled() const  { return m_cognitionEnabled; }
bool VisionEventRouter::isSimulationEnabled() const { return m_simulationEnabled; }

// ── Statistiques ──

int VisionEventRouter::totalRoutedEvents() const   { return m_totalRouted; }
int VisionEventRouter::securityRouteCount() const   { return m_securityRouted; }
int VisionEventRouter::cognitionRouteCount() const  { return m_cognitionRouted; }
int VisionEventRouter::simulationRouteCount() const { return m_simulationRouted; }

QVariantMap VisionEventRouter::routingStatistics() const
{
    return {
        {"totalRouted",      m_totalRouted},
        {"securityRouted",   m_securityRouted},
        {"cognitionRouted",  m_cognitionRouted},
        {"simulationRouted", m_simulationRouted}
    };
}

void VisionEventRouter::resetStatistics()
{
    m_totalRouted = m_securityRouted = m_cognitionRouted = m_simulationRouted = 0;
}

// ── Routage vers SpatialSecurityEngine ──

void VisionEventRouter::routeToSecurity(const VisionEvent &event)
{
    QVariantMap data = event.toVariant();

    switch (event.type) {
    case Vision::DetectionType::Intrusion:
        emit intrusionDetected(data);
        break;
    case Vision::DetectionType::Fire:
        emit fireDetected(data);
        break;
    case Vision::DetectionType::Smoke:
        emit smokeDetected(data);
        break;
    case Vision::DetectionType::Obstruction:
        emit obstructionDetected(data);
        break;
    case Vision::DetectionType::Fall:
        emit fallDetected(data);
        break;
    case Vision::DetectionType::Loitering:
    case Vision::DetectionType::Agitation:
    case Vision::DetectionType::AbnormalMovement:
        emit securityAnomaly(data);
        break;
    default:
        break;
    }

    ++m_securityRouted;
}

// ── Routage vers SpatialCognitiveEngine ──

void VisionEventRouter::routeToCognition(const FrameDetections &fd)
{
    // Résumé des détections pour le Reasoner
    QVariantList detList;
    for (const auto &det : fd.detections)
        detList.append(detectionToVariant(det));

    QVariantMap reasonerData = {
        {"cameraId",    fd.cameraId},
        {"timestamp",   fd.timestamp.toString(Qt::ISODate)},
        {"personCount", fd.personCount()},
        {"detections",  detList}
    };
    emit detectionsForReasoner(reasonerData);

    // Comportements pour le Planner
    QVariantList behaviors;
    for (const auto &det : fd.detections) {
        if (det.behavior != Vision::Behavior::Normal) {
            behaviors.append(detectionToVariant(det));
        }
    }
    if (!behaviors.isEmpty()) {
        QVariantMap plannerData = {
            {"cameraId",   fd.cameraId},
            {"timestamp",  fd.timestamp.toString(Qt::ISODate)},
            {"behaviors",  behaviors}
        };
        emit behaviorForPlanner(plannerData);
    }

    // Anomalies pour le Supervisor
    if (fd.hasAnomalies()) {
        QVariantMap supervisorData = {
            {"cameraId",    fd.cameraId},
            {"timestamp",   fd.timestamp.toString(Qt::ISODate)},
            {"fire",        fd.fireDetected},
            {"smoke",       fd.smokeDetected},
            {"obstruction", fd.obstructionDetected},
            {"obstructionLevel", fd.obstructionLevel}
        };
        emit anomalyForSupervisor(supervisorData);
    }

    ++m_cognitionRouted;
}

// ── Routage vers SimulationEngine ──

void VisionEventRouter::routeToSimulation(const FrameDetections &fd)
{
    QVariantMap data = {
        {"cameraId",       fd.cameraId},
        {"timestamp",      fd.timestamp.toString(Qt::ISODate)},
        {"personCount",    fd.personCount()},
        {"animalCount",    fd.animalCount()},
        {"vehicleCount",   fd.vehicleCount()},
        {"fireDetected",   fd.fireDetected},
        {"smokeDetected",  fd.smokeDetected},
        {"obstructionDetected", fd.obstructionDetected}
    };
    emit simulationValidation(data);
    ++m_simulationRouted;
}

// ── Routage vers QML ──

void VisionEventRouter::routeToQml(const VisionEvent &event)
{
    emit eventForDisplay(event.toVariant());
}

// ── Helpers ──

QVariantMap VisionEventRouter::detectionToVariant(const VisionDetection &det) const
{
    return det.toVariant();
}

QVariantMap VisionEventRouter::frameToOverlayData(const FrameDetections &fd) const
{
    QVariantList boxes;
    for (const auto &det : fd.detections) {
        boxes.append(QVariantMap{
            {"x",         det.bbox.x},
            {"y",         det.bbox.y},
            {"width",     det.bbox.width},
            {"height",    det.bbox.height},
            {"label",     det.className},
            {"confidence", det.confidence},
            {"type",      static_cast<int>(det.type)}
        });
    }

    return {
        {"cameraId",    fd.cameraId},
        {"frameIndex",  fd.frameIndex},
        {"timestamp",   fd.timestamp.toString(Qt::ISODate)},
        {"personCount", fd.personCount()},
        {"boxes",       boxes},
        {"fire",        fd.fireDetected},
        {"smoke",       fd.smokeDetected},
        {"obstruction", fd.obstructionDetected}
    };
}
