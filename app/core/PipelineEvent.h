#pragma once

#include "PipelineTypes.h"
#include <QObject>
#include <QString>
#include <QJsonObject>
#include <QJsonDocument>
#include <QJsonArray>
#include <QDateTime>
#include <QElapsedTimer>
#include <QUuid>
#include <QMutex>
#include <QWebSocket>
#include <QTimer>
#include <QMap>
#include <QVector>

// ─────────────────────────────────────────────────────
//  PipelineModule — identifiant de module dans le pipeline
// ─────────────────────────────────────────────────────
enum class PipelineModule {
    AudioCapture,
    Preprocessor,
    VAD,
    STT,
    NLU,
    Claude,
    TTS,
    AudioOutput,
    WakeWord,
    Memory,
    Orchestrator,
    GUI
};

// ─────────────────────────────────────────────────────
//  ModuleState — état courant d'un module
// ─────────────────────────────────────────────────────
enum class ModuleState {
    Idle,
    Active,
    Processing,
    Error,
    Unavailable
};

// ─────────────────────────────────────────────────────
//  PipelineEvent — événement structuré traversant le bus
//
//  Schéma JSON minimal :
//    { timestamp, module, event_type, correlation_id,
//      payload: { ... } }
// ─────────────────────────────────────────────────────
struct PipelineEvent
{
    QString       timestamp;       // ISO 8601 ms precision
    PipelineModule module;
    EventType     eventType;       // enum typé (compile-time safe)
    QString       correlationId;   // ID unique par interaction utilisateur
    QJsonObject   payload;         // données spécifiques à l'événement
    qint64        elapsedMs = 0;   // ms depuis début de l'interaction

    QJsonObject toJson() const;
    static QString moduleToString(PipelineModule m);
    static QString stateToString(ModuleState s);
};

// ─────────────────────────────────────────────────────
//  ModuleStatus — snapshot d'un module pour l'inspecteur
// ─────────────────────────────────────────────────────
struct ModuleStatus
{
    PipelineModule module;
    ModuleState    state       = ModuleState::Unavailable;
    qint64         lastActiveMs = 0;   // timestamp dernier événement
    EventType      lastEvent   = EventType::SpeechStarted; // dernier event_type
    QJsonObject    metrics;            // métriques propres au module
    QString        lastError;

    QJsonObject toJson() const;
};

// ─────────────────────────────────────────────────────
//  InteractionTrace — trace complète d'une interaction
//    (wake → STT → Claude → TTS → fin)
// ─────────────────────────────────────────────────────
struct InteractionTrace
{
    QString         correlationId;
    qint64          startTimestamp = 0;    // epoch ms
    qint64          endTimestamp   = 0;
    QVector<PipelineEvent> events;
    QStringList     modulesTraversed;

    QJsonObject toJson() const;
    qint64 durationMs() const { return endTimestamp - startTimestamp; }
};

// ─────────────────────────────────────────────────────
//  PipelineEventBus — bus d'événements centralisé (singleton)
//
//  Rôles :
//    • Réception d'événements de tous les modules
//    • Gestion du correlation ID (début/fin d'interaction)
//    • Maintien de l'état courant de chaque module
//    • Exposition WebSocket pour GUI / inspecteur
//    • Historique des N dernières interactions
// ─────────────────────────────────────────────────────
class PipelineEventBus : public QObject
{
    Q_OBJECT

public:
    static PipelineEventBus* instance();

    // ── Correlation ID ──
    QString beginInteraction();          // retourne un nouveau correlationId
    void    endInteraction(const QString &correlationId);
    QString currentCorrelationId() const;

    // ── Emission d'événements ──
    void postEvent(PipelineModule module, EventType eventType,
                   const QJsonObject &payload = {});
    void emitWithId(const QString &correlationId,
                    PipelineModule module, EventType eventType,
                    const QJsonObject &payload = {});

    // ── État des modules ──
    void setModuleState(PipelineModule module, ModuleState state);
    void setModuleMetrics(PipelineModule module, const QJsonObject &metrics);
    void setModuleError(PipelineModule module, const QString &error);
    ModuleStatus moduleStatus(PipelineModule module) const;
    QJsonObject  allModuleStatuses() const;

    // ── Historique / traces ──
    QVector<InteractionTrace> recentTraces(int maxCount = 10) const;
    InteractionTrace currentTrace() const;

    // ── WebSocket inspecteur ──
    void setInspectorSocket(QWebSocket *ws);

    // ── QML API ──
    Q_INVOKABLE QJsonObject getPipelineSnapshot() const;
    Q_INVOKABLE QJsonArray  getRecentEvents(int maxCount = 50) const;
    Q_INVOKABLE QJsonArray  getModuleTimeline(const QString &moduleName, int maxCount = 20) const;
    Q_INVOKABLE QString     getCorrelationId() const { return currentCorrelationId(); }

signals:
    void eventEmitted(const QJsonObject &event);       // pour LogPanel / GUI
    void moduleStateChanged(const QString &module, const QString &state);
    void interactionStarted(const QString &correlationId);
    void interactionEnded(const QString &correlationId, qint64 durationMs);

private:
    explicit PipelineEventBus(QObject *parent = nullptr);
    ~PipelineEventBus() = default;

    void dispatchEvent(const PipelineEvent &event);
    void broadcastToInspector(const QJsonObject &msg);
    void pruneHistory();

    static PipelineEventBus *s_instance;

    // ── Correlation ID courant ──
    QString        m_currentCorrelationId;
    QElapsedTimer  m_interactionTimer;

    // ── État des modules ──
    mutable QMutex m_mutex;
    QMap<PipelineModule, ModuleStatus> m_moduleStatuses;

    // ── Historique ──
    QVector<PipelineEvent>       m_recentEvents;
    QVector<InteractionTrace>    m_traces;
    InteractionTrace             m_currentTrace;
    static constexpr int MAX_RECENT_EVENTS = 500;
    static constexpr int MAX_TRACES        = 50;

    // ── WebSocket inspecteur ──
    QWebSocket *m_inspectorWs = nullptr;
};

// ─────────────────────────────────────────────────────
//  Macros de log pipeline (usage simplifié)
//
//  Usage :  PIPELINE_EVENT(PipelineModule::STT, EventType::PartialTranscript,
//               {{"text", "bonjour"}, {"confidence", 0.95}});
// ─────────────────────────────────────────────────────
#define PIPELINE_EVENT(module, eventType, ...) \
    PipelineEventBus::instance()->postEvent(module, eventType, ##__VA_ARGS__)

#define PIPELINE_STATE(module, state) \
    PipelineEventBus::instance()->setModuleState(module, state)
