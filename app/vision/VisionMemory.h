#ifndef VISIONMEMORY_H
#define VISIONMEMORY_H

#include <QObject>
#include <QString>
#include <QVector>
#include <QVariantMap>
#include <QVariantList>
#include <QDateTime>
#include <QHash>

#include "VisionEnums.h"
#include "VisionDetections.h"

// ─────────────────────────────────────────────────────
//  VisionIncident — Entrée mémoire persistante
// ─────────────────────────────────────────────────────

struct VisionIncident {
    QString id;
    QString cameraId;
    QString roomId;
    Vision::DetectionType type;
    Vision::VisionSeverity severity;
    QString description;
    double  confidence = 0.0;
    QVariantMap data;
    QStringList tags;
    QDateTime timestamp;
    bool resolved = false;

    QVariantMap toVariant() const;
    static VisionIncident fromVariant(const QVariantMap &map);
};

// ─────────────────────────────────────────────────────
//  VisionMemory — Mémoire persistante vision IA
//
//  Stocke les historiques de détections, anomalies,
//  comportements. Recherche par type, pièce, période,
//  similarité (Jaccard sur tags). Persistance JSON.
// ─────────────────────────────────────────────────────

class VisionMemory : public QObject
{
    Q_OBJECT

public:
    explicit VisionMemory(QObject *parent = nullptr);
    ~VisionMemory() override;

    // ── Stockage ──
    void storeIncident(const VisionIncident &incident);
    void storeFromEvent(const VisionEvent &event);
    void resolveIncident(const QString &incidentId);

    // ── Requêtes ──
    QVector<VisionIncident> queryByType(Vision::DetectionType type, int maxCount = 50) const;
    QVector<VisionIncident> queryByCamera(const QString &cameraId, int maxCount = 50) const;
    QVector<VisionIncident> queryByRoom(const QString &roomId, int maxCount = 50) const;
    QVector<VisionIncident> queryByTimeRange(const QDateTime &from, const QDateTime &to) const;
    QVector<VisionIncident> queryBySeverity(Vision::VisionSeverity minSeverity, int maxCount = 50) const;
    QVector<VisionIncident> querySimilar(const VisionIncident &reference, int maxCount = 10) const;
    QVector<VisionIncident> unresolvedIncidents() const;

    // ── Statistiques ──
    int totalIncidents() const;
    int unresolvedCount() const;
    QVariantMap statisticsByType() const;
    QVariantMap statisticsByCamera() const;
    QVariantMap statisticsByRoom() const;

    // ── Persistance JSON ──
    bool saveToFile(const QString &path) const;
    bool loadFromFile(const QString &path);

    // ── Capacité ──
    void setMaxCapacity(int max);
    void clear();

    // ── Export QML ──
    QVariantList incidentsToVariantList(int maxCount = 100) const;

signals:
    void incidentStored(const QVariantMap &incident);
    void incidentResolved(const QString &incidentId);
    void memoryCleared();

private:
    void evictIfNeeded();
    double computeSimilarity(const VisionIncident &a, const VisionIncident &b) const;

    QVector<VisionIncident> m_incidents;
    int m_maxCapacity = Vision::kMaxVisionEvents;
};

#endif // VISIONMEMORY_H
