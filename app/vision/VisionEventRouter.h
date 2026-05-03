#ifndef VISIONEVENTROUTER_H
#define VISIONEVENTROUTER_H

#include <QObject>
#include <QString>
#include <QVariantMap>
#include <QVariantList>
#include <QVector>

#include "VisionEnums.h"
#include "VisionDetections.h"

// ─────────────────────────────────────────────────────
//  VisionEventRouter — Routage des événements vision
//
//  Reçoit les détections et événements du pipeline vision
//  et les route vers :
//    • SpatialSecurityEngine  (intrusion, feu, fumée, obstruction)
//    • SpatialCognitiveEngine (détections, comportements, anomalies)
//    • SimulationEngine       (validation états simulés)
//    • QML                    (SpatialOverlay, CausalityGraph, RiskPanel)
// ─────────────────────────────────────────────────────

class VisionEventRouter : public QObject
{
    Q_OBJECT

public:
    explicit VisionEventRouter(QObject *parent = nullptr);

    // ── Entrée : détections d'une frame ──
    void routeFrameDetections(const FrameDetections &fd);

    // ── Entrée : événement vision unique ──
    void routeEvent(const VisionEvent &event);

    // ── Entrée : lot d'événements ──
    void routeEvents(const QVector<VisionEvent> &events);

    // ── Configuration des cibles ──
    void setSecurityEnabled(bool enabled);
    void setCognitionEnabled(bool enabled);
    void setSimulationEnabled(bool enabled);

    bool isSecurityEnabled() const;
    bool isCognitionEnabled() const;
    bool isSimulationEnabled() const;

    // ── Statistiques ──
    int totalRoutedEvents() const;
    int securityRouteCount() const;
    int cognitionRouteCount() const;
    int simulationRouteCount() const;
    QVariantMap routingStatistics() const;
    void resetStatistics();

signals:
    // ── Vers SpatialSecurityEngine ──
    void intrusionDetected(const QVariantMap &data);
    void fireDetected(const QVariantMap &data);
    void smokeDetected(const QVariantMap &data);
    void obstructionDetected(const QVariantMap &data);
    void fallDetected(const QVariantMap &data);
    void securityAnomaly(const QVariantMap &data);

    // ── Vers SpatialCognitiveEngine ──
    void detectionsForReasoner(const QVariantMap &data);
    void behaviorForPlanner(const QVariantMap &data);
    void anomalyForSupervisor(const QVariantMap &data);

    // ── Vers SimulationEngine ──
    void simulationValidation(const QVariantMap &data);

    // ── Vers QML ──
    void overlayUpdate(const QVariantMap &data);
    void eventForDisplay(const QVariantMap &event);

private:
    void routeToSecurity(const VisionEvent &event);
    void routeToCognition(const FrameDetections &fd);
    void routeToSimulation(const FrameDetections &fd);
    void routeToQml(const VisionEvent &event);

    QVariantMap detectionToVariant(const VisionDetection &det) const;
    QVariantMap frameToOverlayData(const FrameDetections &fd) const;

    bool m_securityEnabled   = true;
    bool m_cognitionEnabled  = true;
    bool m_simulationEnabled = true;

    int m_totalRouted     = 0;
    int m_securityRouted  = 0;
    int m_cognitionRouted = 0;
    int m_simulationRouted = 0;
};

#endif // VISIONEVENTROUTER_H
