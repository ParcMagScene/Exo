#include "AssistantToolDispatcher.h"

#include "ConfigManager.h"
#include "LogManager.h"
#include "MetricsManager.h"
#include "PipelineEvent.h"
#include "ContextCache.h"
#include "llm/ClaudeAPI.h"
#include "audio/VoicePipeline.h"
#include "utils/WeatherManager.h"
#include "utils/SafeIO.h"

#include <QWebSocket>
#include <QWebSocketProtocol>
#include <QJsonDocument>
#include <QTimer>
#include <QDate>
#include <QTime>
#include <QLocale>
#include <QUuid>
#include <QSharedPointer>
#include <QDateTime>

namespace {
static constexpr int NETWORK_SCAN_FAST_MS = 30000;
static constexpr int NETWORK_SCAN_FULL_MS = 120000;
static constexpr int HOMEGRAPH_TIMEOUT_MS = 60000;
static constexpr int DEVICE_COMMAND_TIMEOUT_MS = 15000;
static constexpr int SCENARIO_TIMEOUT_MS = 30000;
// Audit P1.2/P2.2 : aligner avec Executor step (30s) + marge réseau
static constexpr int TOOL_CALL_TIMEOUT_MS = 35000;
}

AssistantToolDispatcher::AssistantToolDispatcher(QObject *parent)
    : QObject(parent)
{
}

void AssistantToolDispatcher::configure(ConfigManager *configManager,
                                        ClaudeAPI *claudeApi,
                                        VoicePipeline *voicePipeline,
                                        WeatherManager *weatherManager,
                                        ContextCache *contextCache)
{
    m_configManager = configManager;
    m_claudeApi = claudeApi;
    m_voicePipeline = voicePipeline;
    m_weatherManager = weatherManager;
    m_contextCache = contextCache;
}

void AssistantToolDispatcher::requestNetworkScan(bool fast)
{
    QString guiId = QStringLiteral("gui_") + QUuid::createUuid().toString(QUuid::Id128);
    m_guiToolCalls.insert(guiId);

    auto *ws = m_toolSockets.value(QStringLiteral("network"));
    if (!ws || !ws->isValid()) {
        hWarning(exoAssistant) << "Network socket non disponible";
        QJsonObject err;
        err[QStringLiteral("status")] = QStringLiteral("error");
        err[QStringLiteral("message")] = QStringLiteral("Service reseau non disponible");
        m_guiToolCalls.remove(guiId);
        emit networkScanCompleted(err);
        return;
    }

    m_pendingToolCalls.insert(QStringLiteral("network"), guiId);

    QJsonObject request;
    request[QStringLiteral("action")] = fast ? QStringLiteral("scan_fast")
                                              : QStringLiteral("scan");
    request[QStringLiteral("params")] = QJsonObject();
    exo::safeio::wsSafeSend(ws,
        QString::fromUtf8(QJsonDocument(request).toJson(QJsonDocument::Compact)),
        "network/scan");

    hAssistant() << "GUI network scan:" << (fast ? "fast" : "full");

    int timeoutMs = fast ? NETWORK_SCAN_FAST_MS : NETWORK_SCAN_FULL_MS;
    QTimer::singleShot(timeoutMs, this, [this, guiId]() {
        if (m_guiToolCalls.remove(guiId)) {
            if (m_pendingToolCalls.value(QStringLiteral("network")) == guiId)
                m_pendingToolCalls.remove(QStringLiteral("network"));
            hWarning(exoAssistant) << "GUI network scan timeout";
            QJsonObject err;
            err[QStringLiteral("status")] = QStringLiteral("error");
            err[QStringLiteral("message")] = QStringLiteral("Timeout scan reseau");
            emit networkScanCompleted(err);
        }
    });
}

void AssistantToolDispatcher::requestHomeGraph()
{
    QString guiId = QStringLiteral("gui_") + QUuid::createUuid().toString(QUuid::Id128);
    m_guiToolCalls.insert(guiId);

    auto *ws = m_toolSockets.value(QStringLiteral("homegraph"));
    if (!ws || !ws->isValid()) {
        QJsonObject err;
        err[QStringLiteral("status")] = QStringLiteral("error");
        err[QStringLiteral("message")] = QStringLiteral("Service HomeGraph non disponible");
        m_guiToolCalls.remove(guiId);
        emit homeGraphReceived(err);
        return;
    }

    m_pendingToolCalls.insert(QStringLiteral("homegraph"), guiId);

    QJsonObject request;
    request[QStringLiteral("action")] = QStringLiteral("gui_state");
    request[QStringLiteral("params")] = QJsonObject();
    exo::safeio::wsSafeSend(ws,
        QString::fromUtf8(QJsonDocument(request).toJson(QJsonDocument::Compact)),
        "homegraph/gui_state");

    hAssistant() << "GUI HomeGraph state requested";

    QTimer::singleShot(HOMEGRAPH_TIMEOUT_MS, this, [this, guiId]() {
        if (m_guiToolCalls.remove(guiId)) {
            if (m_pendingToolCalls.value(QStringLiteral("homegraph")) == guiId)
                m_pendingToolCalls.remove(QStringLiteral("homegraph"));
            QJsonObject err;
            err[QStringLiteral("status")] = QStringLiteral("error");
            err[QStringLiteral("message")] = QStringLiteral("Timeout HomeGraph");
            emit homeGraphReceived(err);
        }
    });
}

void AssistantToolDispatcher::requestDeviceCommand(const QString &deviceId,
                                                   const QString &command,
                                                   const QJsonObject &params)
{
    QString guiId = QStringLiteral("gui_") + QUuid::createUuid().toString(QUuid::Id128);
    m_guiToolCalls.insert(guiId);

    auto *ws = m_toolSockets.value(QStringLiteral("homegraph"));
    if (!ws || !ws->isValid()) {
        QJsonObject err;
        err[QStringLiteral("status")] = QStringLiteral("error");
        err[QStringLiteral("message")] = QStringLiteral("Service HomeGraph non disponible");
        m_guiToolCalls.remove(guiId);
        emit deviceCommandResult(err);
        return;
    }

    m_pendingToolCalls.insert(QStringLiteral("homegraph"), guiId);

    QJsonObject cmdParams;
    cmdParams[QStringLiteral("id_exo")] = deviceId;
    cmdParams[QStringLiteral("command")] = command;
    if (!params.isEmpty())
        cmdParams[QStringLiteral("params")] = params;

    QJsonObject request;
    request[QStringLiteral("action")] = QStringLiteral("apply_command");
    request[QStringLiteral("params")] = cmdParams;
    exo::safeio::wsSafeSend(ws,
        QString::fromUtf8(QJsonDocument(request).toJson(QJsonDocument::Compact)),
        "homegraph/apply_command");

    hAssistant() << "GUI device command:" << deviceId << command;

    QTimer::singleShot(DEVICE_COMMAND_TIMEOUT_MS, this, [this, guiId]() {
        if (m_guiToolCalls.remove(guiId)) {
            if (m_pendingToolCalls.value(QStringLiteral("homegraph")) == guiId)
                m_pendingToolCalls.remove(QStringLiteral("homegraph"));
            QJsonObject err;
            err[QStringLiteral("status")] = QStringLiteral("error");
            err[QStringLiteral("message")] = QStringLiteral("Timeout commande appareil");
            emit deviceCommandResult(err);
        }
    });
}

void AssistantToolDispatcher::requestRunScenario(const QString &name)
{
    QString guiId = QStringLiteral("gui_") + QUuid::createUuid().toString(QUuid::Id128);
    m_guiToolCalls.insert(guiId);

    auto *ws = m_toolSockets.value(QStringLiteral("homegraph"));
    if (!ws || !ws->isValid()) {
        QJsonObject err;
        err[QStringLiteral("status")] = QStringLiteral("error");
        err[QStringLiteral("message")] = QStringLiteral("Service HomeGraph non disponible");
        m_guiToolCalls.remove(guiId);
        emit scenarioResult(err);
        return;
    }

    m_pendingToolCalls.insert(QStringLiteral("homegraph"), guiId);

    QJsonObject scParams;
    scParams[QStringLiteral("name")] = name;

    QJsonObject request;
    request[QStringLiteral("action")] = QStringLiteral("run_scenario");
    request[QStringLiteral("params")] = scParams;
    exo::safeio::wsSafeSend(ws,
        QString::fromUtf8(QJsonDocument(request).toJson(QJsonDocument::Compact)),
        "homegraph/run_scenario");

    hAssistant() << "GUI run scenario:" << name;

    QTimer::singleShot(SCENARIO_TIMEOUT_MS, this, [this, guiId]() {
        if (m_guiToolCalls.remove(guiId)) {
            if (m_pendingToolCalls.value(QStringLiteral("homegraph")) == guiId)
                m_pendingToolCalls.remove(QStringLiteral("homegraph"));
            QJsonObject err;
            err[QStringLiteral("status")] = QStringLiteral("error");
            err[QStringLiteral("message")] = QStringLiteral("Timeout scenario");
            emit scenarioResult(err);
        }
    });
}

void AssistantToolDispatcher::handleToolCall(const QString &toolUseId,
                                             const QString &toolName,
                                             const QJsonObject &arguments)
{
    if (!m_claudeApi) {
        return;
    }

    hAssistant() << "Tool call recu:" << toolName << "- id:" << toolUseId;
    PIPELINE_EVENT(PipelineModule::Claude, EventType::ToolCallDispatched,
                   QJsonObject{{"tool", toolName}, {"tool_use_id", toolUseId}});

    QJsonObject result;

    if (toolName == QLatin1String("get_weather")) {
        const QString requestedCity = arguments.value(QStringLiteral("city")).toString().trimmed();
        const QString defaultCity = m_configManager ? m_configManager->getWeatherCity() : QString();
        const bool isDefaultCity = requestedCity.isEmpty()
            || requestedCity.compare(defaultCity, Qt::CaseInsensitive) == 0;

        // Cache séparé par ville (clé "weather:<city>") pour éviter qu'une
        // réponse Paris ne « pollue » les requêtes pour d'autres villes.
        const QString cacheKey = QStringLiteral("weather:%1")
            .arg(isDefaultCity ? defaultCity.toLower() : requestedCity.toLower());

        if (m_contextCache && m_contextCache->has(cacheKey)) {
            result = m_contextCache->get(cacheKey);
            result[QStringLiteral("cached")] = true;
            m_claudeApi->sendToolResult(toolUseId, result);
            return;
        }

        // Cas 1 : ville par défaut → on peut servir l'état déjà rafraîchi
        // périodiquement par WeatherManager (latence quasi nulle).
        if (isDefaultCity && m_weatherManager) {
            result[QStringLiteral("status")]      = QStringLiteral("success");
            result[QStringLiteral("temperature")] = m_weatherManager->temperature();
            result[QStringLiteral("description")] = m_weatherManager->description();
            result[QStringLiteral("city")]        = defaultCity;
            if (m_contextCache)
                m_contextCache->set(cacheKey, result, 60000);
            m_claudeApi->sendToolResult(toolUseId, result);
            return;
        }

        // Cas 2 : ville arbitraire → requête one-shot async vers OpenWeatherMap.
        if (m_weatherManager) {
            ClaudeAPI *api = m_claudeApi;
            ContextCache *cache = m_contextCache;
            QString useId = toolUseId;
            QString keyCopy = cacheKey;
            m_weatherManager->fetchWeatherFor(requestedCity,
                [api, cache, useId, keyCopy](const QJsonObject &res) {
                    if (cache && res.value(QStringLiteral("status")).toString()
                                    == QLatin1String("success")) {
                        cache->set(keyCopy, res, 60000);
                    }
                    if (api) api->sendToolResult(useId, res);
                });
            return;
        }

        result[QStringLiteral("status")] = QStringLiteral("error");
        result[QStringLiteral("message")] = QStringLiteral("Service meteo non disponible");
        m_claudeApi->sendToolResult(toolUseId, result);
        return;
    }

    if (toolName == QLatin1String("get_datetime")) {
        if (m_contextCache && m_contextCache->has("datetime")) {
            result = m_contextCache->get("datetime");
            result[QStringLiteral("cached")] = true;
            m_claudeApi->sendToolResult(toolUseId, result);
            return;
        }
        result[QStringLiteral("status")] = QStringLiteral("success");
        result[QStringLiteral("date")] = QDate::currentDate().toString(Qt::ISODate);
        result[QStringLiteral("time")] = QTime::currentTime().toString(QStringLiteral("HH:mm:ss"));
        result[QStringLiteral("day")] = QLocale(QStringLiteral("fr_FR"))
            .dayName(QDate::currentDate().dayOfWeek());
        if (m_contextCache)
            m_contextCache->set("datetime", result, 10000);
        m_claudeApi->sendToolResult(toolUseId, result);
        return;
    }

    if (toolName.startsWith(QLatin1String("ha_"))) {
        QJsonObject haCommand;
        haCommand[QStringLiteral("type")] = QStringLiteral("ha_command");
        haCommand[QStringLiteral("tool")] = toolName;
        haCommand[QStringLiteral("arguments")] = arguments;
        haCommand[QStringLiteral("tool_use_id")] = toolUseId;

        if (m_voicePipeline) {
            QJsonDocument doc(haCommand);
            m_voicePipeline->sendWebSocketMessage(
                QString::fromUtf8(doc.toJson(QJsonDocument::Compact)));
        }

        result[QStringLiteral("status")] = QStringLiteral("success");
        result[QStringLiteral("message")] =
            QStringLiteral("Commande %1 envoyee pour %2")
                .arg(toolName,
                     arguments[QStringLiteral("entity_id")].toString());
        m_claudeApi->sendToolResult(toolUseId, result);
        return;
    }

    if (toolName == QLatin1String("search_web")) {
        dispatchToolToService(QStringLiteral("websearch"), toolUseId,
                              QStringLiteral("search_web"), arguments);
        return;
    }
    if (toolName == QLatin1String("get_news")) {
        dispatchToolToService(QStringLiteral("news"), toolUseId,
                              QStringLiteral("get_news"), arguments);
        return;
    }
    if (toolName == QLatin1String("get_summary")) {
        dispatchToolToService(QStringLiteral("knowledge"), toolUseId,
                              QStringLiteral("get_summary"), arguments);
        return;
    }
    if (toolName == QLatin1String("calculate")) {
        dispatchToolToService(QStringLiteral("tools"), toolUseId,
                              QStringLiteral("calculate"), arguments);
        return;
    }
    if (toolName == QLatin1String("convert")) {
        dispatchToolToService(QStringLiteral("tools"), toolUseId,
                              QStringLiteral("convert"), arguments);
        return;
    }

    if (toolName == QLatin1String("remember_info")) {
        dispatchToolToService(QStringLiteral("memory"), toolUseId,
                              QStringLiteral("add"), arguments);
        return;
    }
    if (toolName == QLatin1String("recall_info")) {
        dispatchToolToService(QStringLiteral("memory"), toolUseId,
                              QStringLiteral("search"), arguments);
        return;
    }

    if (toolName == QLatin1String("get_context")) {
        dispatchToolToService(QStringLiteral("context"), toolUseId,
                              QStringLiteral("get_context"), arguments);
        return;
    }
    if (toolName == QLatin1String("create_plan")) {
        dispatchToolToService(QStringLiteral("planner"), toolUseId,
                              QStringLiteral("create_plan"), arguments);
        return;
    }

    if (toolName == QLatin1String("execute_plan")) {
        dispatchToolToService(QStringLiteral("executor"), toolUseId,
                              QStringLiteral("execute_plan"), arguments);
        return;
    }
    if (toolName == QLatin1String("verify_result")) {
        dispatchToolToService(QStringLiteral("verifier"), toolUseId,
                              QStringLiteral("verify_result"), arguments);
        return;
    }
    if (toolName == QLatin1String("summarize_conversation")) {
        dispatchToolToService(QStringLiteral("memory"), toolUseId,
                              QStringLiteral("summarize_history"), arguments);
        return;
    }

    if (toolName == QLatin1String("file_read")) {
        dispatchToolToService(QStringLiteral("files"), toolUseId,
                              QStringLiteral("file_read"), arguments);
        return;
    }
    if (toolName == QLatin1String("file_write")) {
        dispatchToolToService(QStringLiteral("files"), toolUseId,
                              QStringLiteral("file_write"), arguments);
        return;
    }
    if (toolName == QLatin1String("file_list")) {
        dispatchToolToService(QStringLiteral("files"), toolUseId,
                              QStringLiteral("file_list"), arguments);
        return;
    }

    if (toolName == QLatin1String("calendar_add")) {
        dispatchToolToService(QStringLiteral("calendar"), toolUseId,
                              QStringLiteral("calendar_add"), arguments);
        return;
    }
    if (toolName == QLatin1String("calendar_list")) {
        dispatchToolToService(QStringLiteral("calendar"), toolUseId,
                              QStringLiteral("calendar_list"), arguments);
        return;
    }

    if (toolName == QLatin1String("system_info")) {
        dispatchToolToService(QStringLiteral("system"), toolUseId,
                              QStringLiteral("system_info"), arguments);
        return;
    }

    if (toolName == QLatin1String("domotic_action")) {
        dispatchToolToService(QStringLiteral("homegraph"), toolUseId,
                              QStringLiteral("domotic_action"), arguments);
        return;
    }
    if (toolName == QLatin1String("domotic_query")) {
        dispatchToolToService(QStringLiteral("homegraph"), toolUseId,
                              QStringLiteral("domotic_query"), arguments);
        return;
    }
    if (toolName == QLatin1String("network_scan")) {
        dispatchToolToService(QStringLiteral("network"), toolUseId,
                              QStringLiteral("scan"), arguments);
        return;
    }

    hWarning(exoAssistant) << "Tool inconnu:" << toolName;
    result[QStringLiteral("status")] = QStringLiteral("error");
    result[QStringLiteral("message")] =
        QStringLiteral("Outil '%1' non reconnu").arg(toolName);
    m_claudeApi->sendToolResult(toolUseId, result);
}

void AssistantToolDispatcher::initToolSockets()
{
    if (!m_configManager) {
        hWarning(exoAssistant) << "Tool dispatcher non configure";
        return;
    }

    struct ServiceDef {
        QString name;
        QString section;
        QString key;
        QString defaultUrl;
    };

    const ServiceDef services[] = {
        { QStringLiteral("websearch"), QStringLiteral("Tools"), QStringLiteral("websearch_url"), QStringLiteral("ws://localhost:8773") },
        { QStringLiteral("news"),      QStringLiteral("Tools"), QStringLiteral("news_url"),      QStringLiteral("ws://localhost:8774") },
        { QStringLiteral("knowledge"), QStringLiteral("Tools"), QStringLiteral("knowledge_url"), QStringLiteral("ws://localhost:8775") },
        { QStringLiteral("tools"),     QStringLiteral("Tools"), QStringLiteral("tools_url"),     QStringLiteral("ws://localhost:8776") },
        { QStringLiteral("context"),   QStringLiteral("Tools"), QStringLiteral("context_url"),   QStringLiteral("ws://localhost:8777") },
        { QStringLiteral("planner"),   QStringLiteral("Tools"), QStringLiteral("planner_url"),   QStringLiteral("ws://localhost:8778") },
        { QStringLiteral("memory"),    QStringLiteral("Memory"), QStringLiteral("semantic_server_url"), QStringLiteral("ws://localhost:8771") },
        { QStringLiteral("executor"),  QStringLiteral("Tools"), QStringLiteral("executor_url"),  QStringLiteral("ws://localhost:8779") },
        { QStringLiteral("verifier"),  QStringLiteral("Tools"), QStringLiteral("verifier_url"),  QStringLiteral("ws://localhost:8780") },
        { QStringLiteral("files"),     QStringLiteral("Tools"), QStringLiteral("files_url"),     QStringLiteral("ws://localhost:8781") },
        { QStringLiteral("calendar"),  QStringLiteral("Tools"), QStringLiteral("calendar_url"),  QStringLiteral("ws://localhost:8782") },
        { QStringLiteral("system"),    QStringLiteral("Tools"), QStringLiteral("system_url"),    QStringLiteral("ws://localhost:8783") },
        { QStringLiteral("homegraph"), QStringLiteral("Domotique"), QStringLiteral("homegraph_url"), QStringLiteral("ws://localhost:8784") },
        { QStringLiteral("domotic"),   QStringLiteral("Domotique"), QStringLiteral("domotic_url"),   QStringLiteral("ws://localhost:8785") },
        { QStringLiteral("camera"),    QStringLiteral("Domotique"), QStringLiteral("camera_url"),    QStringLiteral("ws://localhost:8786") },
        { QStringLiteral("samsung"),   QStringLiteral("Domotique"), QStringLiteral("samsung_url"),   QStringLiteral("ws://localhost:8787") },
        { QStringLiteral("voltalis"),  QStringLiteral("Domotique"), QStringLiteral("voltalis_url"),  QStringLiteral("ws://localhost:8788") },
        { QStringLiteral("echo"),      QStringLiteral("Domotique"), QStringLiteral("echo_url"),      QStringLiteral("ws://localhost:8789") },
        { QStringLiteral("network"),   QStringLiteral("Domotique"), QStringLiteral("network_url"),   QStringLiteral("ws://localhost:8790") },
    };

    for (const auto &svc : services) {
        QString url = m_configManager->getString(svc.section, svc.key, svc.defaultUrl);
        auto *ws = new QWebSocket(QString(), QWebSocketProtocol::VersionLatest, this);

        const QString serviceName = svc.name;

        // Pour les services lazy (boot différé par ServiceSupervisor), le port
        // n'est pas encore écouté lors du tout premier open() → Qt émet alors
        // un signal disconnected() qui pollue les logs avec "Tool socket
        // deconnecte". On ne signale donc une déconnexion qu'après avoir été
        // au moins une fois connecté.
        auto wasConnected = QSharedPointer<bool>::create(false);

        connect(ws, &QWebSocket::connected, this, [serviceName, wasConnected]() {
            *wasConnected = true;
            hAssistant() << "Tool socket connecte:" << serviceName;
        });

        connect(ws, &QWebSocket::disconnected, this, [this, serviceName, url, wasConnected]() {
            if (*wasConnected) {
                hAssistant() << "Tool socket deconnecte:" << serviceName;
                *wasConnected = false;
            } else {
                // Service pas encore prêt (lazy boot). Retry silencieux.
                hDebug(exoAssistant) << "Tool socket en attente (service non prêt):" << serviceName;
            }
            QTimer::singleShot(3000, this, [this, serviceName, url]() {
                if (auto *sock = m_toolSockets.value(serviceName)) {
                    sock->open(QUrl(url));
                }
            });
        });

        connect(ws, &QWebSocket::textMessageReceived, this,
                [this, serviceName](const QString &msg) {
                    onToolServiceMessage(serviceName, msg);
                });

        m_toolSockets.insert(svc.name, ws);
        ws->open(QUrl(url));
        hAssistant() << "Tool socket" << svc.name << "->" << url;
    }
}

void AssistantToolDispatcher::dispatchToolToService(const QString &service,
                                                    const QString &toolUseId,
                                                    const QString &action,
                                                    const QJsonObject &params)
{
    auto *ws = m_toolSockets.value(service);
    if (!ws || !ws->isValid()) {
        QJsonObject err;
        err[QStringLiteral("status")] = QStringLiteral("error");
        err[QStringLiteral("message")] =
            QStringLiteral("Service %1 non disponible").arg(service);
        if (m_claudeApi) {
            m_claudeApi->sendToolResult(toolUseId, err);
        }
        return;
    }

    m_pendingToolCalls.insert(service, toolUseId);
    // Audit P3.4 : tracker timestamp départ pour calcul durée réponse
    m_pendingStartTimes.insert(service, QDateTime::currentMSecsSinceEpoch());
    MetricsManager::instance()->increment(QStringLiteral("tool.calls.") + service);

    QJsonObject request;
    request[QStringLiteral("action")] = action;
    request[QStringLiteral("params")] = params;

    QJsonDocument doc(request);
    ws->sendTextMessage(QString::fromUtf8(doc.toJson(QJsonDocument::Compact)));

    hAssistant() << "Tool dispatch:" << action << "->" << service
                 << "(tool_use_id:" << toolUseId << ")";

    QTimer::singleShot(TOOL_CALL_TIMEOUT_MS, this, [this, service, toolUseId]() {
        if (m_pendingToolCalls.value(service) == toolUseId) {
            m_pendingToolCalls.remove(service);
            m_pendingStartTimes.remove(service);
            MetricsManager::instance()->increment(QStringLiteral("tool.timeouts.") + service);
            QJsonObject err;
            err[QStringLiteral("status")] = QStringLiteral("error");
            err[QStringLiteral("message")] =
                QStringLiteral("Timeout: le service %1 n'a pas repondu").arg(service);
            if (m_claudeApi) {
                m_claudeApi->sendToolResult(toolUseId, err);
            }
        }
    });
}

void AssistantToolDispatcher::onToolServiceMessage(const QString &service,
                                                   const QString &message)
{
    QJsonDocument doc = QJsonDocument::fromJson(message.toUtf8());
    if (doc.isNull()) {
        return;
    }

    QJsonObject msg = doc.object();

    QString type = msg.value(QStringLiteral("type")).toString();
    if (type == QLatin1String("ready") || type == QLatin1String("pong")) {
        return;
    }

    QString toolUseId = m_pendingToolCalls.value(service);
    if (toolUseId.isEmpty()) {
        hAssistant() << "Message tool recu sans requete en attente:" << service;
        return;
    }

    m_pendingToolCalls.remove(service);

    // Audit P3.4 : enregistrer durée réponse + statut succès/échec
    const qint64 startMs = m_pendingStartTimes.take(service);
    if (startMs > 0) {
        const qint64 durationMs = QDateTime::currentMSecsSinceEpoch() - startMs;
        MetricsManager::instance()->recordValue(
            QStringLiteral("tool.duration_ms.") + service, static_cast<double>(durationMs));
    }
    const bool ok = msg.value(QStringLiteral("ok")).toBool();
    MetricsManager::instance()->increment(
        ok ? (QStringLiteral("tool.success.") + service)
           : (QStringLiteral("tool.errors.") + service));

    if (m_guiToolCalls.remove(toolUseId)) {
        QJsonObject result;
        if (msg.value(QStringLiteral("ok")).toBool()) {
            result = msg.value(QStringLiteral("data")).toObject();
            result[QStringLiteral("status")] = QStringLiteral("success");
        } else {
            result[QStringLiteral("status")] = QStringLiteral("error");
            result[QStringLiteral("message")] =
                msg.value(QStringLiteral("error")).toString(QStringLiteral("Erreur inconnue"));
        }

        if (service == QLatin1String("network")) {
            emit networkScanCompleted(result);
        } else if (service == QLatin1String("homegraph")) {
            if (result.contains(QStringLiteral("devices"))
                || result.contains(QStringLiteral("rooms"))
                || result.contains(QStringLiteral("scenarios"))) {
                emit homeGraphReceived(result);
            } else if (result.contains(QStringLiteral("state"))
                       || result.contains(QStringLiteral("ok"))) {
                emit deviceCommandResult(result);
            } else {
                emit homeGraphReceived(result);
            }
        } else {
            emit homeGraphReceived(result);
        }
        return;
    }

    QJsonObject result;
    if (msg.value(QStringLiteral("ok")).toBool()) {
        result[QStringLiteral("status")] = QStringLiteral("success");
        QJsonObject data = msg.value(QStringLiteral("data")).toObject();
        for (auto it = data.begin(); it != data.end(); ++it) {
            result.insert(it.key(), it.value());
        }
    } else {
        result[QStringLiteral("status")] = QStringLiteral("error");
        result[QStringLiteral("message")] =
            msg.value(QStringLiteral("error")).toString(QStringLiteral("Erreur inconnue"));
    }

    if (m_claudeApi) {
        m_claudeApi->sendToolResult(toolUseId, result);
    }
}

QWebSocket *AssistantToolDispatcher::toolSocket(const QString &service) const
{
    return m_toolSockets.value(service, nullptr);
}
