#include "VisionModelRunner.h"
#include <QRandomGenerator>
#include <QUuid>
#include <QDebug>
#include <QtMath>

// ═════════════════════════════════════════════════════
//  VisionModelRunner
// ═════════════════════════════════════════════════════

VisionModelRunner::VisionModelRunner(QObject *parent)
    : QObject(parent)
{
    // Tous les modèles actifs par défaut
    m_enabledModels = {
        Vision::VisionModel::ObjectDetection,
        Vision::VisionModel::Segmentation,
        Vision::VisionModel::FireSmoke,
        Vision::VisionModel::PoseEstimation,
        Vision::VisionModel::BehaviorAnalysis,
        Vision::VisionModel::IntrusionLine
    };
}

// ─── Détection d'objets (YOLO-like) ───

QVector<VisionDetection> VisionModelRunner::runObjectDetection(const QImage &frame) const
{
    QVector<VisionDetection> results;
    if (frame.isNull()) return results;

    // Simulation : en production → ONNX Runtime / TensorRT
    auto *rng = QRandomGenerator::global();
    int w = frame.width(), h = frame.height();

    // Simuler 0-3 personnes
    int personCount = rng->bounded(4);
    for (int i = 0; i < personCount; ++i)
        results.append(simulatePersonDetection(i, w, h));

    // Simuler 0-1 animal
    if (rng->bounded(100) < 15)
        results.append(simulateAnimalDetection(0, w, h));

    return results;
}

// ─── Segmentation ───

QVector<VisionDetection> VisionModelRunner::runSegmentation(const QImage &frame) const
{
    QVector<VisionDetection> results;
    if (frame.isNull()) return results;

    // Simulation : contour simplifié autour des détections objets
    auto objects = runObjectDetection(frame);
    for (auto &det : objects) {
        double cx = det.bbox.x + det.bbox.width / 2.0;
        double cy = det.bbox.y + det.bbox.height / 2.0;
        double rx = det.bbox.width / 2.0;
        double ry = det.bbox.height / 2.0;

        // Contour elliptique simplifié
        det.maskContour.clear();
        for (int a = 0; a < 12; ++a) {
            double angle = a * (2.0 * M_PI / 12.0);
            det.maskContour.append(QPointF(cx + rx * qCos(angle), cy + ry * qSin(angle)));
        }
        results.append(det);
    }
    return results;
}

// ─── Détection feu/fumée ───

QVector<VisionDetection> VisionModelRunner::runFireSmokeDetection(const QImage &frame) const
{
    QVector<VisionDetection> results;
    if (frame.isNull()) return results;

    auto *rng = QRandomGenerator::global();
    int w = frame.width(), h = frame.height();

    // ~2% de chance de feu, ~3% de fumée (simulation)
    if (rng->bounded(100) < 2)
        results.append(simulateFireDetection(w, h));

    if (rng->bounded(100) < 3)
        results.append(simulateSmokeDetection(w, h));

    return results;
}

// ─── Estimation de posture ───

QVector<VisionDetection> VisionModelRunner::runPoseEstimation(const QImage &frame) const
{
    QVector<VisionDetection> results;
    if (frame.isNull()) return results;

    auto *rng = QRandomGenerator::global();
    int w = frame.width(), h = frame.height();

    // Simuler postures sur personnes détectées
    int personCount = rng->bounded(3);
    for (int i = 0; i < personCount; ++i) {
        auto det = simulatePersonDetection(i, w, h);
        int poseRoll = rng->bounded(100);
        if (poseRoll < 60)       det.posture = Vision::Posture::Standing;
        else if (poseRoll < 80)  det.posture = Vision::Posture::Sitting;
        else if (poseRoll < 90)  det.posture = Vision::Posture::Crouching;
        else if (poseRoll < 97)  det.posture = Vision::Posture::LyingDown;
        else                     det.posture = Vision::Posture::Falling;

        if (det.posture == Vision::Posture::Falling)
            det.type = Vision::DetectionType::Fall;

        results.append(det);
    }
    return results;
}

// ─── Analyse comportementale ───

QVector<VisionDetection> VisionModelRunner::runBehaviorAnalysis(
    const QImage &frame, const QVector<VisionDetection> &persons) const
{
    QVector<VisionDetection> results;
    if (frame.isNull()) return results;

    auto *rng = QRandomGenerator::global();

    for (const auto &person : persons) {
        VisionDetection det = person;
        int behavRoll = rng->bounded(100);
        if (behavRoll < 70)       det.behavior = Vision::Behavior::Normal;
        else if (behavRoll < 80)  det.behavior = Vision::Behavior::Loitering;
        else if (behavRoll < 88)  det.behavior = Vision::Behavior::Running;
        else if (behavRoll < 93)  det.behavior = Vision::Behavior::Wandering;
        else if (behavRoll < 97)  det.behavior = Vision::Behavior::Agitated;
        else                      det.behavior = Vision::Behavior::Suspicious;

        // Direction et vitesse simulées
        det.direction = QPointF(rng->bounded(2.0) - 1.0, rng->bounded(2.0) - 1.0);
        det.speed     = rng->bounded(5.0);

        if (det.behavior == Vision::Behavior::Loitering)
            det.type = Vision::DetectionType::Loitering;
        else if (det.behavior == Vision::Behavior::Agitated)
            det.type = Vision::DetectionType::Agitation;
        else if (det.behavior == Vision::Behavior::Suspicious)
            det.type = Vision::DetectionType::AbnormalMovement;

        results.append(det);
    }
    return results;
}

// ─── Détection d'intrusion (ligne/zone virtuelle) ───

QVector<VisionDetection> VisionModelRunner::runIntrusionDetection(
    const QImage &frame, const QVector<IntrusionZone> &zones) const
{
    QVector<VisionDetection> results;
    if (frame.isNull() || zones.isEmpty()) return results;

    // Vérifier chaque personne détectée contre les zones
    auto persons = runObjectDetection(frame);
    for (const auto &person : persons) {
        if (person.type != Vision::DetectionType::Person) continue;

        QPointF center(person.bbox.x + person.bbox.width / 2.0,
                       person.bbox.y + person.bbox.height / 2.0);

        for (const auto &zone : zones) {
            bool triggered = false;

            if (zone.lineMode) {
                // Vérifier si trajectoire croise la ligne
                QPointF prevPos(center.x() - person.direction.x() * 0.05,
                                center.y() - person.direction.y() * 0.05);
                triggered = lineSegmentsIntersect(prevPos, center, zone.lineStart, zone.lineEnd);
            } else {
                // Vérifier si dans le polygone
                triggered = isPointInPolygon(center, zone.polygon);
            }

            if (triggered) {
                VisionDetection det = person;
                det.id          = QUuid::createUuid().toString(QUuid::WithoutBraces);
                det.type        = Vision::DetectionType::Intrusion;
                det.crossedLine = zone.lineMode;
                det.zoneId      = zone.id;
                det.confidence  = qMax(det.confidence, Vision::kIntrusionConfidenceMin);
                results.append(det);
            }
        }
    }
    return results;
}

// ─── Pipeline complet ───

FrameDetections VisionModelRunner::runAllModels(const QString &cameraId, const QImage &frame,
                                                  const QVector<IntrusionZone> &zones) const
{
    FrameDetections fd;
    fd.cameraId   = cameraId;
    fd.frameIndex = 0;
    fd.timestamp  = QDateTime::currentDateTimeUtc();
    fd.frameWidth = frame.width();
    fd.frameHeight = frame.height();

    if (frame.isNull()) return fd;

    // 1) Détection objets
    if (isModelEnabled(Vision::VisionModel::ObjectDetection)) {
        auto objects = runObjectDetection(frame);
        fd.detections.append(objects);
    }

    // 2) Feu/fumée
    if (isModelEnabled(Vision::VisionModel::FireSmoke)) {
        auto fireSmoke = runFireSmokeDetection(frame);
        for (const auto &d : fireSmoke) {
            fd.detections.append(d);
            if (d.type == Vision::DetectionType::Fire) fd.fireDetected = true;
            if (d.type == Vision::DetectionType::Smoke) fd.smokeDetected = true;
        }
    }

    // 3) Estimation posture
    if (isModelEnabled(Vision::VisionModel::PoseEstimation)) {
        auto poses = runPoseEstimation(frame);
        // Fusionner avec détections existantes (enrichir les personnes)
        for (const auto &pose : poses) {
            if (pose.type == Vision::DetectionType::Fall)
                fd.detections.append(pose);
        }
    }

    // 4) Analyse comportementale (sur les personnes déjà détectées)
    if (isModelEnabled(Vision::VisionModel::BehaviorAnalysis)) {
        QVector<VisionDetection> persons;
        for (const auto &d : fd.detections)
            if (d.type == Vision::DetectionType::Person) persons.append(d);
        auto behaviors = runBehaviorAnalysis(frame, persons);
        for (const auto &b : behaviors) {
            if (b.behavior != Vision::Behavior::Normal)
                fd.detections.append(b);
        }
    }

    // 5) Détection intrusion
    if (isModelEnabled(Vision::VisionModel::IntrusionLine) && !zones.isEmpty()) {
        auto intrusions = runIntrusionDetection(frame, zones);
        fd.detections.append(intrusions);
    }

    // Limiter le nombre de détections
    if (fd.detections.size() > Vision::kMaxDetectionsPerFrame)
        fd.detections.resize(Vision::kMaxDetectionsPerFrame);

    return fd;
}

// ─── Configuration ───

void VisionModelRunner::setConfidenceThreshold(double threshold)
{
    m_confidenceThreshold = qBound(0.0, threshold, 1.0);
}

void VisionModelRunner::setEnabledModels(const QVector<Vision::VisionModel> &models)
{
    m_enabledModels = models;
}

bool VisionModelRunner::isModelEnabled(Vision::VisionModel model) const
{
    return m_enabledModels.contains(model);
}

double VisionModelRunner::confidenceThreshold() const
{
    return m_confidenceThreshold;
}

// ─── Helpers simulation ───

VisionDetection VisionModelRunner::simulatePersonDetection(int idx, int w, int h) const
{
    auto *rng = QRandomGenerator::global();
    VisionDetection det;
    det.id         = QUuid::createUuid().toString(QUuid::WithoutBraces);
    det.type       = Vision::DetectionType::Person;
    det.className  = "person";
    det.confidence = 0.6 + rng->bounded(0.35);
    det.bbox.x     = (0.1 + idx * 0.25 + rng->bounded(0.1)) / 1.0;
    det.bbox.y     = 0.2 + rng->bounded(0.3);
    det.bbox.width = 0.08 + rng->bounded(0.06);
    det.bbox.height= 0.2 + rng->bounded(0.15);
    Q_UNUSED(w); Q_UNUSED(h);
    return det;
}

VisionDetection VisionModelRunner::simulateAnimalDetection(int idx, int w, int h) const
{
    auto *rng = QRandomGenerator::global();
    VisionDetection det;
    det.id         = QUuid::createUuid().toString(QUuid::WithoutBraces);
    det.type       = Vision::DetectionType::Animal;
    det.className  = rng->bounded(2) == 0 ? "cat" : "dog";
    det.confidence = 0.5 + rng->bounded(0.4);
    det.bbox.x     = rng->bounded(0.8);
    det.bbox.y     = 0.5 + rng->bounded(0.3);
    det.bbox.width = 0.05 + rng->bounded(0.05);
    det.bbox.height= 0.05 + rng->bounded(0.05);
    Q_UNUSED(idx); Q_UNUSED(w); Q_UNUSED(h);
    return det;
}

VisionDetection VisionModelRunner::simulateFireDetection(int w, int h) const
{
    auto *rng = QRandomGenerator::global();
    VisionDetection det;
    det.id         = QUuid::createUuid().toString(QUuid::WithoutBraces);
    det.type       = Vision::DetectionType::Fire;
    det.className  = "fire";
    det.confidence = Vision::kFireConfidenceThreshold + rng->bounded(0.5);
    det.bbox.x     = rng->bounded(0.7);
    det.bbox.y     = rng->bounded(0.5);
    det.bbox.width = 0.1 + rng->bounded(0.15);
    det.bbox.height= 0.1 + rng->bounded(0.15);
    Q_UNUSED(w); Q_UNUSED(h);
    return det;
}

VisionDetection VisionModelRunner::simulateSmokeDetection(int w, int h) const
{
    auto *rng = QRandomGenerator::global();
    VisionDetection det;
    det.id         = QUuid::createUuid().toString(QUuid::WithoutBraces);
    det.type       = Vision::DetectionType::Smoke;
    det.className  = "smoke";
    det.confidence = Vision::kSmokeConfidenceThreshold + rng->bounded(0.5);
    det.bbox.x     = rng->bounded(0.6);
    det.bbox.y     = 0.0;
    det.bbox.width = 0.2 + rng->bounded(0.3);
    det.bbox.height= 0.15 + rng->bounded(0.2);
    Q_UNUSED(w); Q_UNUSED(h);
    return det;
}

VisionDetection VisionModelRunner::simulateFallDetection(int w, int h) const
{
    auto *rng = QRandomGenerator::global();
    VisionDetection det;
    det.id         = QUuid::createUuid().toString(QUuid::WithoutBraces);
    det.type       = Vision::DetectionType::Fall;
    det.className  = "person";
    det.posture    = Vision::Posture::Falling;
    det.confidence = Vision::kFallConfidenceMin + rng->bounded(0.3);
    det.bbox.x     = rng->bounded(0.7);
    det.bbox.y     = 0.5 + rng->bounded(0.3);
    det.bbox.width = 0.15 + rng->bounded(0.1);
    det.bbox.height= 0.06 + rng->bounded(0.06);
    Q_UNUSED(w); Q_UNUSED(h);
    return det;
}

bool VisionModelRunner::isPointInPolygon(const QPointF &pt, const QVector<QPointF> &polygon) const
{
    int n = polygon.size();
    if (n < 3) return false;
    bool inside = false;
    for (int i = 0, j = n - 1; i < n; j = i++) {
        if (((polygon[i].y() > pt.y()) != (polygon[j].y() > pt.y())) &&
            (pt.x() < (polygon[j].x() - polygon[i].x()) * (pt.y() - polygon[i].y()) /
                        (polygon[j].y() - polygon[i].y()) + polygon[i].x()))
            inside = !inside;
    }
    return inside;
}

bool VisionModelRunner::lineSegmentsIntersect(const QPointF &a1, const QPointF &a2,
                                                const QPointF &b1, const QPointF &b2) const
{
    double d1 = (b2.x() - b1.x()) * (a1.y() - b1.y()) - (b2.y() - b1.y()) * (a1.x() - b1.x());
    double d2 = (b2.x() - b1.x()) * (a2.y() - b1.y()) - (b2.y() - b1.y()) * (a2.x() - b1.x());
    double d3 = (a2.x() - a1.x()) * (b1.y() - a1.y()) - (a2.y() - a1.y()) * (b1.x() - a1.x());
    double d4 = (a2.x() - a1.x()) * (b2.y() - a1.y()) - (a2.y() - a1.y()) * (b2.x() - a1.x());
    return (d1 * d2 < 0) && (d3 * d4 < 0);
}
