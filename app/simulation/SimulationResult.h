#ifndef SIMULATIONRESULT_H
#define SIMULATIONRESULT_H

#include "SimulationEnums.h"
#include "SimulationEntity.h"

#include <QObject>
#include <QString>
#include <QVariantMap>
#include <QVariantList>
#include <QVector>
#include <QPointF>

// ─────────────────────────────────────────────────────
//  SimEvent — Événement horodaté de la simulation
// ─────────────────────────────────────────────────────
struct SimEvent
{
    int     tick      = 0;
    QString id;
    QString type;       // "sensor_triggered", "device_activated", "entity_spawned", "propagation", "risk"
    QString sourceId;
    QString description;
    QPointF position;
    Simulation::Severity severity = Simulation::Severity::Info;
    QVariantMap data;

    QVariantMap toVariantMap() const;
};

// ─────────────────────────────────────────────────────
//  SimRisk — Risque détecté
// ─────────────────────────────────────────────────────
struct SimRisk
{
    QString id;
    QString label;
    double  probability  = 0.0;
    double  impact       = 0.0;
    double  score() const { return probability * impact; }
    QString zone;
    QString category;
    QString recommendation;
    int     detectedAtTick = 0;
    Simulation::Severity severity = Simulation::Severity::Info;

    QVariantMap toVariantMap() const;
};

// ─────────────────────────────────────────────────────
//  CausalLink — Lien dans le graphe causal
// ─────────────────────────────────────────────────────
struct CausalLink
{
    QString fromId;
    QString toId;
    QString relation;   // "triggers", "causes", "activates", "detects"
    double  weight = 1.0;
    int     tick   = 0;

    QVariantMap toVariantMap() const;
};

// ─────────────────────────────────────────────────────
//  CausalNode — Nœud du graphe causal
// ─────────────────────────────────────────────────────
struct CausalNode
{
    QString id;
    Simulation::CausalNodeType type = Simulation::CausalNodeType::Event;
    QString label;
    int     tick = 0;

    QVariantMap toVariantMap() const;
};

// ─────────────────────────────────────────────────────
//  TickSnapshot — État complet à un tick donné
// ─────────────────────────────────────────────────────
struct TickSnapshot
{
    int tick = 0;
    QVector<SimulationEntity> entities;
    QVector<SimEvent>         events;
    QVariantMap               metrics; // smoke_coverage, heat_max, etc.
};

// ─────────────────────────────────────────────────────
//  SimulationResult — Résultat complet d'une simulation
//
//  Contient :
//   • timeline des événements
//   • snapshots par tick (clés)
//   • risques détectés
//   • graphe causal
//   • capteurs déclenchés
//   • appareils activés
//   • zones impactées
// ─────────────────────────────────────────────────────
class SimulationResult
{
public:
    SimulationResult();

    // ── Build ──
    void addEvent(const SimEvent &event);
    void addRisk(const SimRisk &risk);
    void addCausalNode(const CausalNode &node);
    void addCausalLink(const CausalLink &link);
    void addSnapshot(const TickSnapshot &snap);
    void addTriggeredSensor(const QString &sensorId, int tick);
    void addActivatedDevice(const QString &deviceId, int tick, const QString &action);
    void addImpactedZone(const QString &roomId, const QString &impactType, double level);
    void setTotalTicks(int ticks) { m_totalTicks = ticks; }

    // ── Query ──
    int totalTicks() const { return m_totalTicks; }
    const QVector<SimEvent>  &events() const { return m_events; }
    const QVector<SimRisk>   &risks() const { return m_risks; }
    const QVector<CausalNode> &causalNodes() const { return m_causalNodes; }
    const QVector<CausalLink> &causalLinks() const { return m_causalLinks; }
    const QVector<TickSnapshot> &snapshots() const { return m_snapshots; }

    QVariantList triggeredSensors() const { return m_triggeredSensors; }
    QVariantList activatedDevices() const { return m_activatedDevices; }
    QVariantList impactedZones() const { return m_impactedZones; }

    // ── Export to QML-friendly format ──
    QVariantMap toVariantMap() const;
    QVariantList eventsToVariantList() const;
    QVariantList risksToVariantList() const;
    QVariantList causalNodesToVariantList() const;
    QVariantList causalLinksToVariantList() const;
    QVariantMap  timelineToVariantMap() const;

    // ── Clear ──
    void clear();

private:
    int                       m_totalTicks = 0;
    QVector<SimEvent>         m_events;
    QVector<SimRisk>          m_risks;
    QVector<CausalNode>       m_causalNodes;
    QVector<CausalLink>       m_causalLinks;
    QVector<TickSnapshot>     m_snapshots;
    QVariantList              m_triggeredSensors;
    QVariantList              m_activatedDevices;
    QVariantList              m_impactedZones;
};

#endif // SIMULATIONRESULT_H
