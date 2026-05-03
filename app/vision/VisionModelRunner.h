#ifndef VISIONMODELRUNNER_H
#define VISIONMODELRUNNER_H

#include <QObject>
#include <QImage>
#include <QRectF>
#include <QVector>
#include <QVariantMap>
#include <QVariantList>

#include "VisionEnums.h"
#include "VisionDetections.h"

// ─────────────────────────────────────────────────────
//  IntrusionZone — Zone de détection d'intrusion virtuelle
// ─────────────────────────────────────────────────────
struct IntrusionZone {
    QString id;
    QVector<QPointF> polygon;      // points normalisés 0..1
    bool             lineMode = false;  // true = ligne virtuelle, false = zone
    QPointF          lineStart;
    QPointF          lineEnd;
};

// ─────────────────────────────────────────────────────
//  VisionModelRunner — Exécution modèles IA locaux
//  Détection objets, segmentation, feu/fumée, posture,
//  comportement, intrusion par ligne virtuelle
//  Abstraction : runtime ONNX / TensorRT / OpenVINO
// ─────────────────────────────────────────────────────

class VisionModelRunner : public QObject
{
    Q_OBJECT

public:
    explicit VisionModelRunner(QObject *parent = nullptr);

    // ── Modèles IA ──
    Q_INVOKABLE QVector<VisionDetection> runObjectDetection(const QImage &frame) const;
    Q_INVOKABLE QVector<VisionDetection> runSegmentation(const QImage &frame) const;
    Q_INVOKABLE QVector<VisionDetection> runFireSmokeDetection(const QImage &frame) const;
    Q_INVOKABLE QVector<VisionDetection> runPoseEstimation(const QImage &frame) const;
    Q_INVOKABLE QVector<VisionDetection> runBehaviorAnalysis(const QImage &frame,
                                                              const QVector<VisionDetection> &persons) const;
    Q_INVOKABLE QVector<VisionDetection> runIntrusionDetection(const QImage &frame,
                                                                const QVector<IntrusionZone> &zones) const;

    // ── Traitement complet sur une frame ──
    FrameDetections runAllModels(const QString &cameraId, const QImage &frame,
                                 const QVector<IntrusionZone> &zones = {}) const;

    // ── Configuration ──
    void setConfidenceThreshold(double threshold);
    void setEnabledModels(const QVector<Vision::VisionModel> &models);
    bool isModelEnabled(Vision::VisionModel model) const;

    double confidenceThreshold() const;

private:
    // Helpers simulation IA
    VisionDetection simulatePersonDetection(int idx, int w, int h) const;
    VisionDetection simulateAnimalDetection(int idx, int w, int h) const;
    VisionDetection simulateFireDetection(int w, int h) const;
    VisionDetection simulateSmokeDetection(int w, int h) const;
    VisionDetection simulateFallDetection(int w, int h) const;
    bool isPointInPolygon(const QPointF &pt, const QVector<QPointF> &polygon) const;
    bool lineSegmentsIntersect(const QPointF &a1, const QPointF &a2,
                                const QPointF &b1, const QPointF &b2) const;

    double m_confidenceThreshold = Vision::kDefaultConfidenceThreshold;
    QVector<Vision::VisionModel> m_enabledModels;
};

#endif // VISIONMODELRUNNER_H
