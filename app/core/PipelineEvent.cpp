#include "PipelineEvent.h"
#include "LogManager.h"
#include <QJsonArray>
#include <mutex>

// ─────────────────────────────────────────────────────
//  PipelineEvent
// ─────────────────────────────────────────────────────

QString PipelineEvent::moduleToString(PipelineModule m)
{
    switch (m) {
    case PipelineModule::AudioCapture: return "audio_capture";
    case PipelineModule::Preprocessor: return "preprocessor";
    case PipelineModule::VAD:          return "vad";
    case PipelineModule::STT:          return "stt";
    case PipelineModule::NLU:          return "nlu";
    case PipelineModule::Claude:       return "claude";
    case PipelineModule::TTS:          return "tts";
    case PipelineModule::AudioOutput:  return "audio_output";
    case PipelineModule::WakeWord:     return "wake_word";
    case PipelineModule::Memory:       return "memory";
    case PipelineModule::Orchestrator: return "orchestrator";
    case PipelineModule::GUI:          return "gui";
    }
    return "unknown";
}

QString PipelineEvent::stateToString(ModuleState s)
{
    switch (s) {
    case ModuleState::Idle:        return "idle";
    case ModuleState::Active:      return "active";
    case ModuleState::Processing:  return "processing";
    case ModuleState::Error:       return "error";
    case ModuleState::Unavailable: return "unavailable";
    }
    return "unknown";
}

QJsonObject PipelineEvent::toJson() const
{
    QJsonObject obj;
    obj["timestamp"]      = timestamp;
    obj["module"]         = moduleToString(module);
    obj["event_type"]     = eventTypeToString(eventType);
    obj["correlation_id"] = correlationId;
    obj["elapsed_ms"]     = elapsedMs;
    if (!payload.isEmpty())
        obj["payload"] = payload;
    return obj;
}

// ─────────────────────────────────────────────────────
//  ModuleStatus
// ─────────────────────────────────────────────────────

QJsonObject ModuleStatus::toJson() const
{
    QJsonObject obj;
    obj["module"]        = PipelineEvent::moduleToString(module);
    obj["state"]         = PipelineEvent::stateToString(state);
    obj["last_active_ms"] = lastActiveMs;
    obj["last_event"]    = eventTypeToString(lastEvent);
    if (!metrics.isEmpty())
        obj["metrics"] = metrics;
    if (!lastError.isEmpty())
        obj["last_error"] = lastError;
    return obj;
}

// ─────────────────────────────────────────────────────
//  InteractionTrace
// ─────────────────────────────────────────────────────

QJsonObject InteractionTrace::toJson() const
{
    QJsonObject obj;
    obj["correlation_id"]    = correlationId;
    obj["start_timestamp"]   = startTimestamp;
    obj["end_timestamp"]     = endTimestamp;
    obj["duration_ms"]       = durationMs();
    QJsonArray modules;
    for (const auto &m : modulesTraversed)
        modules.append(m);
    obj["modules_traversed"] = modules;
    obj["event_count"]       = events.size();
    return obj;
}

// ─────────────────────────────────────────────────────
//  PipelineEventBus — singleton
// ─────────────────────────────────────────────────────

PipelineEventBus* PipelineEventBus::s_instance = nullptr;
static std::once_flag s_pipelineEventBusOnce;

PipelineEventBus* PipelineEventBus::instance()
{
    std::call_once(s_pipelineEventBusOnce, []() {
        s_instance = new PipelineEventBus();
    });
    return s_instance;
}

PipelineEventBus::PipelineEventBus(QObject *parent)
    : QObject(parent)
{
    // Initialiser l'état de tous les modules comme Unavailable
    const PipelineModule modules[] = {
        PipelineModule::AudioCapture, PipelineModule::Preprocessor,
        PipelineModule::VAD, PipelineModule::STT, PipelineModule::NLU,
        PipelineModule::Claude, PipelineModule::TTS, PipelineModule::AudioOutput,
        PipelineModule::WakeWord, PipelineModule::Memory,
        PipelineModule::Orchestrator, PipelineModule::GUI
    };
    for (auto m : modules) {
        ModuleStatus status;
        status.module = m;
        m_moduleStatuses[m] = status;
    }
}

// ── Correlation ID ──

QString PipelineEventBus::beginInteraction()
{
    QMutexLocker lk(&m_mutex);

    // Clore l'interaction précédente si elle n'a pas été terminée
    if (!m_currentCorrelationId.isEmpty()) {
        m_currentTrace.endTimestamp = QDateTime::currentMSecsSinceEpoch();
        m_traces.append(m_currentTrace);
        pruneHistory();
    }

    m_currentCorrelationId = QUuid::createUuid().toString(QUuid::WithoutBraces).left(8);
    m_interactionTimer.restart();

    m_currentTrace = InteractionTrace();
    m_currentTrace.correlationId  = m_currentCorrelationId;
    m_currentTrace.startTimestamp = QDateTime::currentMSecsSinceEpoch();

    lk.unlock();

    hLog() << "[PIPELINE] Interaction démarrée — ID:" << m_currentCorrelationId;
    Q_EMIT interactionStarted(m_currentCorrelationId);
    return m_currentCorrelationId;
}

void PipelineEventBus::endInteraction(const QString &correlationId)
{
    QMutexLocker lk(&m_mutex);

    if (m_currentCorrelationId != correlationId) return;

    m_currentTrace.endTimestamp = QDateTime::currentMSecsSinceEpoch();
    qint64 duration = m_currentTrace.durationMs();
    m_traces.append(m_currentTrace);
    pruneHistory();

    QString oldId = m_currentCorrelationId;
    m_currentCorrelationId.clear();
    m_currentTrace = InteractionTrace();

    lk.unlock();

    hLog() << "[PIPELINE] Interaction terminée — ID:" << oldId
           << "durée:" << duration << "ms";
    Q_EMIT interactionEnded(oldId, duration);
}

QString PipelineEventBus::currentCorrelationId() const
{
    QMutexLocker lk(&m_mutex);
    return m_currentCorrelationId;
}

// ── Emission d'événements ──

void PipelineEventBus::postEvent(PipelineModule module, EventType eventType,
                                 const QJsonObject &payload)
{
    QString cid;
    {
        QMutexLocker lk(&m_mutex);
        cid = m_currentCorrelationId;
    }
    emitWithId(cid, module, eventType, payload);
}

void PipelineEventBus::emitWithId(const QString &correlationId,
                                  PipelineModule module, EventType eventType,
                                  const QJsonObject &payload)
{
    PipelineEvent evt;
    evt.timestamp     = QDateTime::currentDateTime().toString(Qt::ISODateWithMs);
    evt.module        = module;
    evt.eventType     = eventType;
    evt.correlationId = correlationId;
    evt.payload       = payload;

    {
        QMutexLocker lk(&m_mutex);
        evt.elapsedMs = m_interactionTimer.isValid() ? m_interactionTimer.elapsed() : 0;
    }

    dispatchEvent(evt);
}

void PipelineEventBus::dispatchEvent(const PipelineEvent &event)
{
    QJsonObject json = event.toJson();

    {
        QMutexLocker lk(&m_mutex);

        // Mettre à jour l'état du module
        auto &status = m_moduleStatuses[event.module];
        status.lastActiveMs = QDateTime::currentMSecsSinceEpoch();
        status.lastEvent    = event.eventType;

        // Ajouter à l'historique récent
        m_recentEvents.append(event);
        while (m_recentEvents.size() > MAX_RECENT_EVENTS)
            m_recentEvents.removeFirst();

        // Ajouter à la trace courante
        if (!m_currentCorrelationId.isEmpty() &&
            event.correlationId == m_currentCorrelationId) {
            m_currentTrace.events.append(event);
            QString modName = PipelineEvent::moduleToString(event.module);
            if (!m_currentTrace.modulesTraversed.contains(modName))
                m_currentTrace.modulesTraversed.append(modName);
        }
    }

    // Log structuré
    hLog() << QString("[%1] %2 | cid=%3 | +%4ms")
              .arg(PipelineEvent::moduleToString(event.module).toUpper(),
                   eventTypeToString(event.eventType),
                   event.correlationId.isEmpty() ? "-" : event.correlationId)
              .arg(event.elapsedMs);

    // Notifier GUI et inspecteur
    Q_EMIT eventEmitted(json);
    broadcastToInspector(json);
}

// ── État des modules ──

void PipelineEventBus::setModuleState(PipelineModule module, ModuleState state)
{
    {
        QMutexLocker lk(&m_mutex);
        m_moduleStatuses[module].state = state;
        m_moduleStatuses[module].lastActiveMs = QDateTime::currentMSecsSinceEpoch();
        if (state != ModuleState::Error)
            m_moduleStatuses[module].lastError.clear();
    }
    QString modStr = PipelineEvent::moduleToString(module);
    QString stateStr = PipelineEvent::stateToString(state);
    Q_EMIT moduleStateChanged(modStr, stateStr);
    broadcastToInspector({
        {"type", "module_state"},
        {"module", modStr},
        {"state", stateStr}
    });
}

void PipelineEventBus::setModuleMetrics(PipelineModule module, const QJsonObject &metrics)
{
    QMutexLocker lk(&m_mutex);
    m_moduleStatuses[module].metrics = metrics;
}

void PipelineEventBus::setModuleError(PipelineModule module, const QString &error)
{
    {
        QMutexLocker lk(&m_mutex);
        m_moduleStatuses[module].state = ModuleState::Error;
        m_moduleStatuses[module].lastError = error;
    }
    QString modStr = PipelineEvent::moduleToString(module);
    Q_EMIT moduleStateChanged(modStr, "error");
    broadcastToInspector({
        {"type", "module_error"},
        {"module", modStr},
        {"error", error}
    });
}

// ── Historique / traces ──

QVector<InteractionTrace> PipelineEventBus::recentTraces(int maxCount) const
{
    QMutexLocker lk(&m_mutex);
    int start = qMax(0, m_traces.size() - maxCount);
    return m_traces.mid(start);
}

InteractionTrace PipelineEventBus::currentTrace() const
{
    QMutexLocker lk(&m_mutex);
    return m_currentTrace;
}

// ── WebSocket inspecteur ──

void PipelineEventBus::setInspectorSocket(QWebSocket *ws)
{
    m_inspectorWs = ws;
}

void PipelineEventBus::broadcastToInspector(const QJsonObject &msg)
{
    if (!m_inspectorWs ||
        m_inspectorWs->state() != QAbstractSocket::ConnectedState)
        return;
    m_inspectorWs->sendTextMessage(
        QString::fromUtf8(QJsonDocument(msg).toJson(QJsonDocument::Compact)));
}

// ── QML API ──

QJsonObject PipelineEventBus::getPipelineSnapshot() const
{
    QJsonObject snapshot;
    snapshot["module_statuses"] = allModuleStatuses();

    QMutexLocker lk(&m_mutex);
    snapshot["current_correlation_id"] = m_currentCorrelationId;
    snapshot["active_interaction"] = !m_currentCorrelationId.isEmpty();
    if (!m_currentCorrelationId.isEmpty()) {
        snapshot["interaction_elapsed_ms"] = m_interactionTimer.elapsed();
        snapshot["interaction_modules"] = QJsonArray::fromStringList(
            m_currentTrace.modulesTraversed);
    }
    return snapshot;
}

QJsonArray PipelineEventBus::getRecentEvents(int maxCount) const
{
    QMutexLocker lk(&m_mutex);
    QJsonArray arr;
    int start = qMax(0, m_recentEvents.size() - maxCount);
    for (int i = start; i < m_recentEvents.size(); ++i)
        arr.append(m_recentEvents[i].toJson());
    return arr;
}

QJsonArray PipelineEventBus::getModuleTimeline(const QString &moduleName, int maxCount) const
{
    QMutexLocker lk(&m_mutex);
    QJsonArray arr;
    int count = 0;
    for (int i = m_recentEvents.size() - 1; i >= 0 && count < maxCount; --i) {
        if (PipelineEvent::moduleToString(m_recentEvents[i].module) == moduleName) {
            arr.prepend(m_recentEvents[i].toJson());
            ++count;
        }
    }
    return arr;
}

QJsonObject PipelineEventBus::allModuleStatuses() const
{
    QMutexLocker lk(&m_mutex);
    QJsonObject obj;
    for (auto it = m_moduleStatuses.constBegin(); it != m_moduleStatuses.constEnd(); ++it) {
        obj[PipelineEvent::moduleToString(it.key())] = it.value().toJson();
    }
    return obj;
}

ModuleStatus PipelineEventBus::moduleStatus(PipelineModule module) const
{
    QMutexLocker lk(&m_mutex);
    return m_moduleStatuses.value(module);
}

void PipelineEventBus::pruneHistory()
{
    // Appelé sous verrou
    while (m_traces.size() > MAX_TRACES)
        m_traces.removeFirst();
}
