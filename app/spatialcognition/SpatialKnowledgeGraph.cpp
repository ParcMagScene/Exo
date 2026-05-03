#include "SpatialKnowledgeGraph.h"
#include "floorplan/FloorPlanModel.h"

#include <QUuid>
#include <QtMath>
#include <algorithm>

// ─────────────────────────────────────────────────────
//  KnowledgeNode
// ─────────────────────────────────────────────────────

QVariantMap KnowledgeNode::toVariantMap() const
{
    return {
        {"id",         id},
        {"type",       static_cast<int>(type)},
        {"label",      label},
        {"roomId",     roomId},
        {"x",          position.x()},
        {"y",          position.y()},
        {"properties", properties}
    };
}

KnowledgeNode KnowledgeNode::fromVariantMap(const QVariantMap &map)
{
    KnowledgeNode n;
    n.id         = map.value("id").toString();
    n.type       = static_cast<SpatialCognition::KnowledgeNodeType>(map.value("type").toInt());
    n.label      = map.value("label").toString();
    n.roomId     = map.value("roomId").toString();
    n.position   = QPointF(map.value("x").toDouble(), map.value("y").toDouble());
    n.properties = map.value("properties").toMap();
    return n;
}

// ─────────────────────────────────────────────────────
//  KnowledgeEdge
// ─────────────────────────────────────────────────────

QVariantMap KnowledgeEdge::toVariantMap() const
{
    return {
        {"fromId",     fromId},
        {"toId",       toId},
        {"relation",   static_cast<int>(relation)},
        {"weight",     weight},
        {"confidence", confidence},
        {"metadata",   metadata}
    };
}

// ─────────────────────────────────────────────────────
//  SpatialKnowledgeGraph
// ─────────────────────────────────────────────────────

SpatialKnowledgeGraph::SpatialKnowledgeGraph(QObject *parent)
    : QObject(parent)
{
}

SpatialKnowledgeGraph::~SpatialKnowledgeGraph() = default;

// ── Construction depuis FloorPlan ──

void SpatialKnowledgeGraph::buildFromFloorPlan(FloorPlanModel *model)
{
    if (!model)
        return;

    const auto ids = model->getItemIds();
    for (const auto &itemId : ids) {
        const QVariantMap data = model->getItemData(itemId);
        if (data.isEmpty())
            continue;

        KnowledgeNode node;
        node.id    = itemId;
        node.label = data.value("label", data.value("type")).toString();

        const QString type = data.value("type").toString().toLower();
        if (type == "room")
            node.type = SpatialCognition::KnowledgeNodeType::Room;
        else if (type == "wall")
            node.type = SpatialCognition::KnowledgeNodeType::Wall;
        else if (type == "door")
            node.type = SpatialCognition::KnowledgeNodeType::Door;
        else if (type == "window")
            node.type = SpatialCognition::KnowledgeNodeType::Window;
        else if (type == "sensor")
            node.type = SpatialCognition::KnowledgeNodeType::Sensor;
        else if (type == "camera")
            node.type = SpatialCognition::KnowledgeNodeType::Camera;
        else
            node.type = SpatialCognition::KnowledgeNodeType::Object;

        const QVariantMap pos = data.value("position").toMap();
        node.position = QPointF(pos.value("x").toDouble(), pos.value("y").toDouble());

        const QVariantMap sz = data.value("size").toMap();
        node.bounds = QRectF(node.position, QSizeF(sz.value("width", 10).toDouble(),
                                                     sz.value("height", 10).toDouble()));

        node.roomId    = data.value("roomId").toString();
        node.properties = data.value("properties").toMap();

        addNode(node);
    }

    inferSpatialRelations();
    emit graphUpdated();
}

// ── Construction depuis Network ──

void SpatialKnowledgeGraph::buildFromNetwork(const QVariantList &devices, const QVariantList &links)
{
    for (const auto &dev : devices) {
        const QVariantMap d = dev.toMap();
        KnowledgeNode node;
        node.id     = d.value("id").toString();
        node.type   = SpatialCognition::KnowledgeNodeType::Device;
        node.label  = d.value("name", d.value("hostname")).toString();
        node.roomId = d.value("roomId").toString();
        node.position = QPointF(d.value("x").toDouble(), d.value("y").toDouble());
        node.properties = d;
        addNode(node);
    }

    for (const auto &lnk : links) {
        const QVariantMap l = lnk.toMap();
        KnowledgeEdge edge;
        edge.fromId   = l.value("sourceId").toString();
        edge.toId     = l.value("targetId").toString();
        edge.relation = SpatialCognition::SpatialRelation::Connected;
        edge.weight   = l.value("bandwidth", 1.0).toDouble();
        edge.metadata = l;
        addEdge(edge);
    }

    emit graphUpdated();
}

// ── Construction depuis HomeGraph ──

void SpatialKnowledgeGraph::buildFromHomeGraph(const QVariantList &entities)
{
    for (const auto &ent : entities) {
        const QVariantMap e = ent.toMap();
        const QString id = e.value("entity_id").toString();
        if (m_nodes.contains(id))
            continue;

        KnowledgeNode node;
        node.id     = id;
        node.type   = SpatialCognition::KnowledgeNodeType::Device;
        node.label  = e.value("friendly_name", id).toString();
        node.roomId = e.value("area_id").toString();
        node.properties = e;
        addNode(node);
    }

    emit graphUpdated();
}

// ── Construction depuis Simulation ──

void SpatialKnowledgeGraph::buildFromSimulation(const QVariantList &simEntities,
                                                 const QVariantList &simEvents)
{
    for (const auto &ent : simEntities) {
        const QVariantMap e = ent.toMap();
        const QString id = QStringLiteral("sim_") + e.value("id").toString();
        KnowledgeNode node;
        node.id     = id;
        node.type   = SpatialCognition::KnowledgeNodeType::Object;
        node.label  = e.value("type").toString();
        node.position = QPointF(e.value("x").toDouble(), e.value("y").toDouble());
        node.properties = e;
        addNode(node);
    }

    // Causal edges from simulation events
    for (const auto &ev : simEvents) {
        const QVariantMap e = ev.toMap();
        const QString src = e.value("sourceId").toString();
        const QString tgt = e.value("targetId").toString();
        if (!src.isEmpty() && !tgt.isEmpty()) {
            KnowledgeEdge edge;
            edge.fromId   = src;
            edge.toId     = tgt;
            edge.relation = SpatialCognition::SpatialRelation::Dangerous;
            edge.metadata = e;
            addEdge(edge);
        }
    }

    emit graphUpdated();
}

// ── CRUD nœuds ──

void SpatialKnowledgeGraph::addNode(const KnowledgeNode &node)
{
    m_nodes.insert(node.id, node);
    if (!node.roomId.isEmpty())
        m_roomIndex[node.roomId].append(node.id);
    emit nodeAdded(node.id);
}

void SpatialKnowledgeGraph::removeNode(const QString &id)
{
    if (!m_nodes.contains(id))
        return;

    const auto &n = m_nodes[id];
    if (!n.roomId.isEmpty())
        m_roomIndex[n.roomId].removeAll(id);

    m_nodes.remove(id);

    // Retirer les arêtes liées
    m_edges.erase(std::remove_if(m_edges.begin(), m_edges.end(),
                                  [&](const KnowledgeEdge &e) {
                                      return e.fromId == id || e.toId == id;
                                  }),
                   m_edges.end());

    emit nodeRemoved(id);
    emit graphUpdated();
}

const KnowledgeNode *SpatialKnowledgeGraph::node(const QString &id) const
{
    auto it = m_nodes.constFind(id);
    return it != m_nodes.constEnd() ? &(*it) : nullptr;
}

// ── CRUD arêtes ──

void SpatialKnowledgeGraph::addEdge(const KnowledgeEdge &edge)
{
    m_edges.append(edge);
    emit edgeAdded(edge.fromId, edge.toId);
}

void SpatialKnowledgeGraph::removeEdge(const QString &fromId, const QString &toId)
{
    m_edges.erase(std::remove_if(m_edges.begin(), m_edges.end(),
                                  [&](const KnowledgeEdge &e) {
                                      return e.fromId == fromId && e.toId == toId;
                                  }),
                   m_edges.end());
}

QVector<KnowledgeEdge> SpatialKnowledgeGraph::edgesFrom(const QString &id) const
{
    QVector<KnowledgeEdge> result;
    for (const auto &e : m_edges) {
        if (e.fromId == id)
            result.append(e);
    }
    return result;
}

QVector<KnowledgeEdge> SpatialKnowledgeGraph::edgesTo(const QString &id) const
{
    QVector<KnowledgeEdge> result;
    for (const auto &e : m_edges) {
        if (e.toId == id)
            result.append(e);
    }
    return result;
}

// ── Requêtes spatiales ──

SpatialCognition::SpatialRelation
SpatialKnowledgeGraph::querySpatialRelation(const QString &a, const QString &b) const
{
    for (const auto &e : m_edges) {
        if ((e.fromId == a && e.toId == b) || (e.fromId == b && e.toId == a))
            return e.relation;
    }
    return SpatialCognition::SpatialRelation::Blocked;
}

QVector<KnowledgeNode>
SpatialKnowledgeGraph::findNeighbors(const QString &id, SpatialCognition::SpatialRelation relation) const
{
    QVector<KnowledgeNode> result;
    for (const auto &e : m_edges) {
        if (e.relation != relation)
            continue;
        if (e.fromId == id) {
            if (auto *n = node(e.toId))
                result.append(*n);
        } else if (e.toId == id) {
            if (auto *n = node(e.fromId))
                result.append(*n);
        }
    }
    return result;
}

QStringList SpatialKnowledgeGraph::findPath(const QString &fromId, const QString &toId) const
{
    // BFS sur les arêtes Accessible/Adjacent
    QHash<QString, QString> parent;
    QVector<QString> queue;
    queue.append(fromId);
    parent[fromId] = QString();

    while (!queue.isEmpty()) {
        const QString current = queue.takeFirst();
        if (current == toId) {
            // Reconstruire le chemin
            QStringList path;
            QString c = toId;
            while (!c.isEmpty()) {
                path.prepend(c);
                c = parent.value(c);
            }
            return path;
        }

        for (const auto &e : m_edges) {
            if (e.relation != SpatialCognition::SpatialRelation::Adjacent &&
                e.relation != SpatialCognition::SpatialRelation::Accessible)
                continue;

            QString next;
            if (e.fromId == current)
                next = e.toId;
            else if (e.toId == current)
                next = e.fromId;

            if (!next.isEmpty() && !parent.contains(next)) {
                parent[next] = current;
                queue.append(next);
            }
        }
    }

    return {}; // pas de chemin
}

QVector<KnowledgeNode> SpatialKnowledgeGraph::findVisibleObjects(const QString &cameraId) const
{
    return findNeighbors(cameraId, SpatialCognition::SpatialRelation::Visible);
}

QVector<KnowledgeNode> SpatialKnowledgeGraph::findSensorsInRoom(const QString &roomId) const
{
    QVector<KnowledgeNode> result;
    const auto ids = m_roomIndex.value(roomId);
    for (const auto &id : ids) {
        if (auto *n = node(id)) {
            if (n->type == SpatialCognition::KnowledgeNodeType::Sensor)
                result.append(*n);
        }
    }
    return result;
}

QVector<KnowledgeNode> SpatialKnowledgeGraph::findDevicesInRoom(const QString &roomId) const
{
    QVector<KnowledgeNode> result;
    const auto ids = m_roomIndex.value(roomId);
    for (const auto &id : ids) {
        if (auto *n = node(id)) {
            if (n->type == SpatialCognition::KnowledgeNodeType::Device)
                result.append(*n);
        }
    }
    return result;
}

QVector<KnowledgeNode> SpatialKnowledgeGraph::nodesInRect(const QRectF &rect) const
{
    QVector<KnowledgeNode> result;
    for (const auto &n : m_nodes) {
        if (rect.contains(n.position))
            result.append(n);
    }
    return result;
}

QVector<KnowledgeNode> SpatialKnowledgeGraph::nodesOfType(SpatialCognition::KnowledgeNodeType type) const
{
    QVector<KnowledgeNode> result;
    for (const auto &n : m_nodes) {
        if (n.type == type)
            result.append(n);
    }
    return result;
}

QVector<QString> SpatialKnowledgeGraph::roomsAdjacentTo(const QString &roomId) const
{
    QVector<QString> result;
    for (const auto &e : m_edges) {
        if (e.relation != SpatialCognition::SpatialRelation::Adjacent)
            continue;
        if (e.fromId == roomId)
            result.append(e.toId);
        else if (e.toId == roomId)
            result.append(e.fromId);
    }
    return result;
}

bool SpatialKnowledgeGraph::isAccessible(const QString &fromRoom, const QString &toRoom) const
{
    return !findPath(fromRoom, toRoom).isEmpty();
}

double SpatialKnowledgeGraph::distanceBetween(const QString &a, const QString &b) const
{
    const auto *na = node(a);
    const auto *nb = node(b);
    if (!na || !nb)
        return -1.0;

    const double dx = na->position.x() - nb->position.x();
    const double dy = na->position.y() - nb->position.y();
    return qSqrt(dx * dx + dy * dy);
}

// ── Export QML ──

QVariantList SpatialKnowledgeGraph::nodesToVariantList() const
{
    QVariantList list;
    for (const auto &n : m_nodes)
        list.append(n.toVariantMap());
    return list;
}

QVariantList SpatialKnowledgeGraph::edgesToVariantList() const
{
    QVariantList list;
    for (const auto &e : m_edges)
        list.append(e.toVariantMap());
    return list;
}

QVariantMap SpatialKnowledgeGraph::toVariantMap() const
{
    return {
        {"nodes",     nodesToVariantList()},
        {"edges",     edgesToVariantList()},
        {"nodeCount", nodeCount()},
        {"edgeCount", edgeCount()}
    };
}

void SpatialKnowledgeGraph::clear()
{
    m_nodes.clear();
    m_edges.clear();
    m_roomIndex.clear();
    emit graphUpdated();
}

// ── Inférence des relations spatiales ──

void SpatialKnowledgeGraph::inferSpatialRelations()
{
    inferAdjacency();
    inferAccessibility();
    inferVisibility();
}

void SpatialKnowledgeGraph::inferAdjacency()
{
    // Détecter l'adjacence : deux pièces partagent un mur/porte
    const auto rooms = nodesOfType(SpatialCognition::KnowledgeNodeType::Room);
    for (int i = 0; i < rooms.size(); ++i) {
        for (int j = i + 1; j < rooms.size(); ++j) {
            const auto &r1 = rooms[i];
            const auto &r2 = rooms[j];
            // Adjacence si les bounds se touchent (distance < seuil)
            if (r1.bounds.isValid() && r2.bounds.isValid()) {
                const QRectF expanded = r1.bounds.adjusted(-5, -5, 5, 5);
                if (expanded.intersects(r2.bounds)) {
                    KnowledgeEdge edge;
                    edge.fromId   = r1.id;
                    edge.toId     = r2.id;
                    edge.relation = SpatialCognition::SpatialRelation::Adjacent;
                    edge.confidence = 0.9;
                    addEdge(edge);
                }
            }
        }
    }
}

void SpatialKnowledgeGraph::inferAccessibility()
{
    // Deux pièces sont accessibles si reliées par une porte
    const auto doors = nodesOfType(SpatialCognition::KnowledgeNodeType::Door);
    for (const auto &door : doors) {
        // Trouver pièces adjacentes à la porte
        const auto rooms = nodesOfType(SpatialCognition::KnowledgeNodeType::Room);
        QStringList adjacentRooms;
        for (const auto &room : rooms) {
            if (room.bounds.isValid() && room.bounds.adjusted(-10, -10, 10, 10).contains(door.position))
                adjacentRooms.append(room.id);
        }
        // Relier les pièces adjacentes via la porte
        for (int i = 0; i < adjacentRooms.size(); ++i) {
            for (int j = i + 1; j < adjacentRooms.size(); ++j) {
                KnowledgeEdge edge;
                edge.fromId   = adjacentRooms[i];
                edge.toId     = adjacentRooms[j];
                edge.relation = SpatialCognition::SpatialRelation::Accessible;
                edge.confidence = 1.0;
                edge.metadata.insert("via", door.id);
                addEdge(edge);
            }
        }
    }
}

void SpatialKnowledgeGraph::inferVisibility()
{
    // Caméras : marquer les objets dans leur champ de vision
    const auto cameras = nodesOfType(SpatialCognition::KnowledgeNodeType::Camera);
    for (const auto &cam : cameras) {
        const double fov   = cam.properties.value("fov", 90).toDouble();
        const double range = cam.properties.value("range", 200).toDouble();
        const double angle = cam.properties.value("angle", 0).toDouble();

        Q_UNUSED(fov); // utilisé pour le cone ci-dessous
        const double halfFov = fov * M_PI / 360.0;
        const double angleRad = angle * M_PI / 180.0;

        for (const auto &n : m_nodes) {
            if (n.id == cam.id)
                continue;
            const double dx = n.position.x() - cam.position.x();
            const double dy = n.position.y() - cam.position.y();
            const double dist = qSqrt(dx * dx + dy * dy);
            if (dist > range)
                continue;

            const double objAngle = qAtan2(dy, dx);
            double diff = objAngle - angleRad;
            // Normaliser dans [-π, π]
            while (diff > M_PI)  diff -= 2.0 * M_PI;
            while (diff < -M_PI) diff += 2.0 * M_PI;

            if (qAbs(diff) <= halfFov) {
                KnowledgeEdge edge;
                edge.fromId   = cam.id;
                edge.toId     = n.id;
                edge.relation = SpatialCognition::SpatialRelation::Visible;
                edge.weight   = 1.0 - (dist / range); // plus proche = plus visible
                addEdge(edge);
            }
        }
    }
}
