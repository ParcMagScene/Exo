#ifndef SPATIALKNOWLEDGEGRAPH_H
#define SPATIALKNOWLEDGEGRAPH_H

#include "SpatialEnums.h"

#include <QObject>
#include <QString>
#include <QHash>
#include <QVector>
#include <QPointF>
#include <QRectF>
#include <QVariantMap>
#include <QVariantList>

class FloorPlanModel;

// ─────────────────────────────────────────────────────
//  KnowledgeNode — Nœud du graphe de connaissances
// ─────────────────────────────────────────────────────
struct KnowledgeNode
{
    QString id;
    SpatialCognition::KnowledgeNodeType type = SpatialCognition::KnowledgeNodeType::Object;
    QString label;
    QString roomId;
    QPointF position;
    QRectF  bounds;
    QVariantMap properties;

    QVariantMap toVariantMap() const;
    static KnowledgeNode fromVariantMap(const QVariantMap &map);
};

// ─────────────────────────────────────────────────────
//  KnowledgeEdge — Arête relationnelle
// ─────────────────────────────────────────────────────
struct KnowledgeEdge
{
    QString fromId;
    QString toId;
    SpatialCognition::SpatialRelation relation = SpatialCognition::SpatialRelation::Adjacent;
    double  weight    = 1.0;
    double  confidence = 1.0;
    QVariantMap metadata;

    QVariantMap toVariantMap() const;
};

// ─────────────────────────────────────────────────────
//  SpatialKnowledgeGraph — Graphe de connaissances spatiales
//
//  Construit un graphe typé reliant pièces, murs, portes,
//  fenêtres, objets, capteurs, caméras, appareils et liens
//  réseau avec des relations spatiales qualitatives.
//
//  Sources : FloorPlanModel, NetworkMap, HomeGraph, Simulation
// ─────────────────────────────────────────────────────
class SpatialKnowledgeGraph : public QObject
{
    Q_OBJECT

public:
    explicit SpatialKnowledgeGraph(QObject *parent = nullptr);
    ~SpatialKnowledgeGraph() override;

    // ── Construction depuis les sources ──
    void buildFromFloorPlan(FloorPlanModel *model);
    void buildFromNetwork(const QVariantList &devices, const QVariantList &links);
    void buildFromHomeGraph(const QVariantList &entities);
    void buildFromSimulation(const QVariantList &simEntities, const QVariantList &simEvents);

    // ── CRUD nœuds ──
    void addNode(const KnowledgeNode &node);
    void removeNode(const QString &id);
    const KnowledgeNode *node(const QString &id) const;
    QVector<KnowledgeNode> allNodes() const { return m_nodes.values().toVector(); }
    int nodeCount() const { return m_nodes.size(); }

    // ── CRUD arêtes ──
    void addEdge(const KnowledgeEdge &edge);
    void removeEdge(const QString &fromId, const QString &toId);
    QVector<KnowledgeEdge> edgesFrom(const QString &id) const;
    QVector<KnowledgeEdge> edgesTo(const QString &id) const;
    int edgeCount() const { return m_edges.size(); }

    // ── Requêtes spatiales ──
    SpatialCognition::SpatialRelation querySpatialRelation(const QString &a, const QString &b) const;
    QVector<KnowledgeNode> findNeighbors(const QString &id, SpatialCognition::SpatialRelation relation) const;
    QStringList findPath(const QString &fromId, const QString &toId) const;
    QVector<KnowledgeNode> findVisibleObjects(const QString &cameraId) const;
    QVector<KnowledgeNode> findSensorsInRoom(const QString &roomId) const;
    QVector<KnowledgeNode> findDevicesInRoom(const QString &roomId) const;
    QVector<KnowledgeNode> nodesInRect(const QRectF &rect) const;
    QVector<KnowledgeNode> nodesOfType(SpatialCognition::KnowledgeNodeType type) const;

    // ── Requêtes avancées ──
    QVector<QString> roomsAdjacentTo(const QString &roomId) const;
    bool isAccessible(const QString &fromRoom, const QString &toRoom) const;
    double distanceBetween(const QString &a, const QString &b) const;

    // ── Export QML ──
    QVariantList nodesToVariantList() const;
    QVariantList edgesToVariantList() const;
    QVariantMap  toVariantMap() const;

    // ── Clear ──
    void clear();

signals:
    void graphUpdated();
    void nodeAdded(const QString &id);
    void nodeRemoved(const QString &id);
    void edgeAdded(const QString &fromId, const QString &toId);

private:
    void inferSpatialRelations();
    void inferAdjacency();
    void inferAccessibility();
    void inferVisibility();

    QHash<QString, KnowledgeNode> m_nodes;
    QVector<KnowledgeEdge>        m_edges;
    // Index rapide : roomId → nodeIds
    QHash<QString, QStringList>   m_roomIndex;
};

#endif // SPATIALKNOWLEDGEGRAPH_H
