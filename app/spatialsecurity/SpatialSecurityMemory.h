#ifndef SPATIALSECURITYMEMORY_H
#define SPATIALSECURITYMEMORY_H

#include <QObject>
#include <QString>
#include <QVector>
#include <QVariantMap>
#include <QVariantList>
#include <QDateTime>
#include <QHash>

#include "SpatialSecurityEnums.h"

// ─────────────────────────────────────────────────────
//  SecurityIncident — Entrée mémoire d'un incident
// ─────────────────────────────────────────────────────

struct SecurityIncident {
    QString id;
    SpatialSecurity::RiskType type;
    SpatialSecurity::SecuritySeverity severity;
    QString roomId;
    QString description;
    double  confidence = 0.0;
    QVariantMap data;
    QStringList tags;
    QDateTime timestamp;
    bool resolved = false;

    QVariantMap toVariantMap() const;
    static SecurityIncident fromVariantMap(const QVariantMap &map);
};

// ─────────────────────────────────────────────────────
//  SpatialSecurityMemory — Mémoire persistante sécurité
//
//  Stocke l'historique des incidents, risques, anomalies,
//  intrusions, incendies. Permet la recherche par type,
//  pièce, période, similarité.
// ─────────────────────────────────────────────────────

class SpatialSecurityMemory : public QObject
{
    Q_OBJECT

public:
    explicit SpatialSecurityMemory(QObject *parent = nullptr);
    ~SpatialSecurityMemory() override;

    // ── Stockage ──
    void storeIncident(const SecurityIncident &incident);
    void storeRisk(SpatialSecurity::RiskType type, const QString &roomId,
                   const QString &description, double severity);
    void resolveIncident(const QString &incidentId);

    // ── Requêtes ──
    QVector<SecurityIncident> queryByType(SpatialSecurity::RiskType type, int maxCount = 50) const;
    QVector<SecurityIncident> queryByRoom(const QString &roomId, int maxCount = 50) const;
    QVector<SecurityIncident> queryByTimeRange(const QDateTime &from, const QDateTime &to) const;
    QVector<SecurityIncident> queryBySeverity(SpatialSecurity::SecuritySeverity minSeverity, int maxCount = 50) const;
    QVector<SecurityIncident> querySimilarIncidents(const SecurityIncident &reference, int maxCount = 10) const;
    QVector<SecurityIncident> retrievePastIntrusions(int maxCount = 20) const;
    QVector<SecurityIncident> retrievePastFires(int maxCount = 20) const;
    QVector<SecurityIncident> unresolvedIncidents() const;

    // ── Statistiques ──
    int totalIncidents() const;
    int unresolvedCount() const;
    QVariantMap statisticsByType() const;
    QVariantMap statisticsByRoom() const;

    // ── Persistance ──
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
    double computeSimilarity(const SecurityIncident &a, const SecurityIncident &b) const;

    QVector<SecurityIncident> m_incidents;
    int m_maxCapacity = SpatialSecurity::kMaxSecurityIncidents;
};

#endif // SPATIALSECURITYMEMORY_H
