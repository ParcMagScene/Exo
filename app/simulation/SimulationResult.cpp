#include "SimulationResult.h"

#include <QUuid>

// ═════════════════════════════════════════════════════
//  SimEvent
// ═════════════════════════════════════════════════════

QVariantMap SimEvent::toVariantMap() const
{
    return {
        {"tick",        tick},
        {"id",          id},
        {"type",        type},
        {"sourceId",    sourceId},
        {"description", description},
        {"x",           position.x()},
        {"y",           position.y()},
        {"severity",    static_cast<int>(severity)},
        {"data",        data}
    };
}

// ═════════════════════════════════════════════════════
//  SimRisk
// ═════════════════════════════════════════════════════

QVariantMap SimRisk::toVariantMap() const
{
    return {
        {"id",             id},
        {"label",          label},
        {"probability",    probability},
        {"impact",         impact},
        {"score",          score()},
        {"zone",           zone},
        {"category",       category},
        {"recommendation", recommendation},
        {"detectedAtTick", detectedAtTick},
        {"severity",       static_cast<int>(severity)}
    };
}

// ═════════════════════════════════════════════════════
//  CausalLink / CausalNode
// ═════════════════════════════════════════════════════

QVariantMap CausalLink::toVariantMap() const
{
    return {
        {"from",     fromId},
        {"to",       toId},
        {"relation", relation},
        {"weight",   weight},
        {"tick",     tick}
    };
}

QVariantMap CausalNode::toVariantMap() const
{
    return {
        {"id",    id},
        {"type",  static_cast<int>(type)},
        {"label", label},
        {"tick",  tick}
    };
}

// ═════════════════════════════════════════════════════
//  SimulationResult
// ═════════════════════════════════════════════════════

SimulationResult::SimulationResult() = default;

void SimulationResult::addEvent(const SimEvent &event)
{
    m_events.append(event);
}

void SimulationResult::addRisk(const SimRisk &risk)
{
    // Update if same id
    for (auto &r : m_risks) {
        if (r.id == risk.id) {
            r = risk;
            return;
        }
    }
    m_risks.append(risk);
}

void SimulationResult::addCausalNode(const CausalNode &node)
{
    for (const auto &n : m_causalNodes) {
        if (n.id == node.id) return; // already present
    }
    m_causalNodes.append(node);
}

void SimulationResult::addCausalLink(const CausalLink &link)
{
    m_causalLinks.append(link);
}

void SimulationResult::addSnapshot(const TickSnapshot &snap)
{
    m_snapshots.append(snap);
}

void SimulationResult::addTriggeredSensor(const QString &sensorId, int tick)
{
    m_triggeredSensors.append(QVariantMap{{"sensorId", sensorId}, {"tick", tick}});
}

void SimulationResult::addActivatedDevice(const QString &deviceId, int tick, const QString &action)
{
    m_activatedDevices.append(QVariantMap{{"deviceId", deviceId}, {"tick", tick}, {"action", action}});
}

void SimulationResult::addImpactedZone(const QString &roomId, const QString &impactType, double level)
{
    // Update if existing
    for (int i = 0; i < m_impactedZones.size(); ++i) {
        auto map = m_impactedZones[i].toMap();
        if (map.value("roomId").toString() == roomId && map.value("impactType").toString() == impactType) {
            map["level"] = qMax(map.value("level").toDouble(), level);
            m_impactedZones[i] = map;
            return;
        }
    }
    m_impactedZones.append(QVariantMap{{"roomId", roomId}, {"impactType", impactType}, {"level", level}});
}

void SimulationResult::clear()
{
    m_totalTicks = 0;
    m_events.clear();
    m_risks.clear();
    m_causalNodes.clear();
    m_causalLinks.clear();
    m_snapshots.clear();
    m_triggeredSensors.clear();
    m_activatedDevices.clear();
    m_impactedZones.clear();
}

// ── Export ──

QVariantMap SimulationResult::toVariantMap() const
{
    return {
        {"totalTicks",        m_totalTicks},
        {"events",            eventsToVariantList()},
        {"risks",             risksToVariantList()},
        {"causalNodes",       causalNodesToVariantList()},
        {"causalLinks",       causalLinksToVariantList()},
        {"triggeredSensors",  m_triggeredSensors},
        {"activatedDevices",  m_activatedDevices},
        {"impactedZones",     m_impactedZones}
    };
}

QVariantList SimulationResult::eventsToVariantList() const
{
    QVariantList list;
    for (const auto &e : m_events)
        list.append(e.toVariantMap());
    return list;
}

QVariantList SimulationResult::risksToVariantList() const
{
    QVariantList list;
    for (const auto &r : m_risks)
        list.append(r.toVariantMap());
    return list;
}

QVariantList SimulationResult::causalNodesToVariantList() const
{
    QVariantList list;
    for (const auto &n : m_causalNodes)
        list.append(n.toVariantMap());
    return list;
}

QVariantList SimulationResult::causalLinksToVariantList() const
{
    QVariantList list;
    for (const auto &l : m_causalLinks)
        list.append(l.toVariantMap());
    return list;
}

QVariantMap SimulationResult::timelineToVariantMap() const
{
    QVariantMap timeline;
    QVariantList entries;
    for (const auto &e : m_events) {
        entries.append(QVariantMap{
            {"tick",     e.tick},
            {"type",     e.type},
            {"label",    e.description},
            {"severity", static_cast<int>(e.severity)}
        });
    }
    timeline["entries"]    = entries;
    timeline["totalTicks"] = m_totalTicks;
    return timeline;
}
