#ifndef VISIONDETECTIONS_H
#define VISIONDETECTIONS_H

#include <QObject>
#include <QString>
#include <QVariantMap>
#include <QVariantList>
#include <QRectF>
#include <QPointF>
#include <QVector>
#include <QDateTime>
#include <qqml.h>

#include "VisionEnums.h"

// ─────────────────────────────────────────────────────
//  BoundingBox — Rectangle de détection normalisé
// ─────────────────────────────────────────────────────
struct BoundingBox {
    double x      = 0.0;   // 0..1 normalisé
    double y      = 0.0;
    double width   = 0.0;
    double height  = 0.0;
    double confidence = 0.0;
    QString label;

    QVariantMap toVariant() const;
    static BoundingBox fromVariant(const QVariantMap &v);
};

// ─────────────────────────────────────────────────────
//  VisionDetection — Détection unique
// ─────────────────────────────────────────────────────
struct VisionDetection {
    QString id;
    Vision::DetectionType type     = Vision::DetectionType::Object;
    BoundingBox bbox;
    double confidence              = 0.0;
    QString className;

    // Segmentation (optionnel)
    QVector<QPointF> maskContour;

    // Posture / Comportement (optionnel)
    Vision::Posture  posture       = Vision::Posture::Unknown;
    Vision::Behavior behavior      = Vision::Behavior::Normal;

    // Mouvement
    QPointF  direction;             // vecteur direction normalisé
    double   speed                 = 0.0;  // px/s estimé
    bool     crossedLine           = false; // ligne virtuelle franchie

    // Contexte spatial
    QString roomId;
    QString zoneId;

    QVariantMap toVariant() const;
    static VisionDetection fromVariant(const QVariantMap &v);
};

// ─────────────────────────────────────────────────────
//  FrameDetections — Ensemble des détections d'une frame
// ─────────────────────────────────────────────────────
struct FrameDetections {
    QString cameraId;
    qint64 frameIndex              = 0;
    QDateTime timestamp;
    int frameWidth                 = 0;
    int frameHeight                = 0;

    QVector<VisionDetection> detections;

    // Anomalies globales
    bool obstructionDetected       = false;
    double obstructionLevel        = 0.0;
    bool fireDetected              = false;
    bool smokeDetected             = false;

    // Résumé
    int personCount() const;
    int animalCount() const;
    int vehicleCount() const;
    bool hasAnomalies() const;

    QVariantMap  toVariant() const;
    QVariantList detectionsToVariantList() const;
    static FrameDetections fromVariant(const QVariantMap &v);
};

// ─────────────────────────────────────────────────────
//  VisionEvent — Événement vision routé
// ─────────────────────────────────────────────────────
struct VisionEvent {
    QString id;
    QString cameraId;
    Vision::DetectionType type     = Vision::DetectionType::Object;
    Vision::VisionSeverity severity = Vision::VisionSeverity::Info;
    QString description;
    QString roomId;
    double confidence              = 0.0;
    QVariantMap details;
    QDateTime timestamp;

    QVariantMap toVariant() const;
    static VisionEvent fromVariant(const QVariantMap &v);
};

// ─────────────────────────────────────────────────────
//  VisionDetections — Gestionnaire de détections (QML)
// ─────────────────────────────────────────────────────

class VisionDetections : public QObject
{
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(int totalDetections READ totalDetections NOTIFY detectionsChanged)
    Q_PROPERTY(int personCount READ personCount NOTIFY detectionsChanged)
    Q_PROPERTY(QVariantList currentDetections READ currentDetections NOTIFY detectionsChanged)
    Q_PROPERTY(QVariantList recentEvents READ recentEvents NOTIFY eventsChanged)

public:
    explicit VisionDetections(QObject *parent = nullptr);

    void addFrameDetections(const FrameDetections &fd);
    void addEvent(const VisionEvent &event);

    int totalDetections() const;
    int personCount() const;
    QVariantList currentDetections() const;
    QVariantList recentEvents() const;

    Q_INVOKABLE QVariantList getDetectionsByCamera(const QString &cameraId) const;
    Q_INVOKABLE QVariantList getDetectionsByType(int type) const;
    Q_INVOKABLE QVariantList getDetectionsByRoom(const QString &roomId) const;
    Q_INVOKABLE QVariantList getEventsByType(int type) const;
    Q_INVOKABLE QVariantList getEventsBySeverity(int minSeverity) const;
    Q_INVOKABLE void clearDetections();
    Q_INVOKABLE void clearEvents();

signals:
    void detectionsChanged();
    void eventsChanged();
    void criticalEventDetected(const QVariantMap &event);

private:
    QMap<QString, FrameDetections> m_currentByCamera;
    QVector<VisionEvent> m_events;
};

#endif // VISIONDETECTIONS_H
