#include "AssistantManager.h"
#include "AssistantMessageRouter.h"
#include "AssistantErrorManager.h"
#include "AssistantLifecycleManager.h"
#include "llm/AIMemoryManager.h"
#include "ConfigManager.h"
#include "LogManager.h"
#include "MetricsManager.h"
#include "TraceManager.h"
#include "HealthCheck.h"
#include "llm/ClaudeAPI.h"
#include "audio/VoicePipeline.h"
#include "audio/AudioDeviceManager.h"
#include "utils/WeatherManager.h"
#include "utils/SafeIO.h"
#include "PipelineEvent.h"
#include "PipelineTracer.h"
#include "ContextCache.h"
#include "LatencyMetrics.h"
#include "AssistantComponentFactory.h"
#include "AssistantConnectionBinder.h"
#include "AssistantToolDispatcher.h"
#include "AssistantFastPathEngine.h"
#include "AssistantSafeBootFacade.h"
#include "AssistantQmlExposer.h"
#include "AssistantPromptBuilder.h"
#include "safeboot/SafeBootController.h"
#include <QQmlContext>
#include <QTimer>
#include <QTime>
#include <QDate>
#include <QLocale>
#include <QMetaObject>
#include <QUuid>
#include <QElapsedTimer>

// ── Timeouts & intervalles (ms) ──────────────────────
static constexpr int WEATHER_CACHE_TTL_MS      = 60000;   // 60s
static constexpr int DATETIME_CACHE_TTL_MS     = 10000;   // 10s
static constexpr int HA_STATE_CACHE_TTL_MS     = 30000;   // 30s
static constexpr int CLAUDE_KEEPALIVE_MS       = 240000;  // 4 min
static constexpr int HEALTHCHECK_INTERVAL_MS   = 10000;   // 10s

AssistantManager::AssistantManager(QObject *parent)
    : QObject(parent)
    , m_isListening(false)
    , m_isInitialized(false)
    , m_lifecycleManager(new AssistantLifecycleManager(this))
    , m_errorManager(new AssistantErrorManager(this))
    , m_messageRouter(new AssistantMessageRouter(this))
    , m_configManager(nullptr)
    , m_claudeApi(nullptr)
    , m_voicePipeline(nullptr)
    , m_weatherManager(nullptr)
    , m_memoryManager(nullptr)
    , m_healthCheck(nullptr)
    , m_qmlEngine(nullptr)
{
    hAssistant() << "AssistantManager v30.3 créé";
}

AssistantManager::~AssistantManager()
{
    hAssistant() << "AssistantManager détruit";
}

void AssistantManager::setSafeBootController(SafeBootController *controller)
{
    m_safeBootController = controller;
    if (m_safeBootFacade) {
        m_safeBootFacade->setController(controller);
    }
}

bool AssistantManager::safeBootEnabled() const
{
    return m_safeBootFacade ? m_safeBootFacade->safeBootEnabled() : false;
}

QVariantList AssistantManager::failedServices() const
{
    return m_safeBootFacade ? m_safeBootFacade->failedServices() : QVariantList{};
}

QVariantList AssistantManager::degradedServices() const
{
    return m_safeBootFacade ? m_safeBootFacade->degradedServices() : QVariantList{};
}

QVariantList AssistantManager::startupTimeline() const
{
    return m_safeBootFacade ? m_safeBootFacade->startupTimeline() : QVariantList{};
}

void AssistantManager::onServiceReady(const QString &serviceName)
{
    if (m_safeBootFacade) {
        m_safeBootFacade->onServiceReady(serviceName);
    }
}

void AssistantManager::onServiceFailed(const QString &serviceName)
{
    if (m_safeBootFacade) {
        m_safeBootFacade->onServiceFailed(serviceName);
    }
}

bool AssistantManager::autoRepairRunning() const
{
    return m_safeBootFacade ? m_safeBootFacade->autoRepairRunning() : false;
}

QVariantList AssistantManager::repairTimeline() const
{
    return m_safeBootFacade ? m_safeBootFacade->repairTimeline() : QVariantList{};
}

bool AssistantManager::safeBootDecisionMade() const
{
    return m_safeBootFacade ? m_safeBootFacade->safeBootDecisionMade() : false;
}

void AssistantManager::setSafeBootDecisionMade(bool value)
{
    if (!m_safeBootFacade) {
        return;
    }
    m_safeBootFacade->setSafeBootDecisionMade(value);
}

void AssistantManager::onRepairAttempt(const QString &service, bool success)
{
    if (m_safeBootFacade) {
        m_safeBootFacade->onRepairAttempt(service, success);
    }
}

void AssistantManager::onRepairCompleted()
{
    if (m_safeBootFacade) {
        m_safeBootFacade->onRepairCompleted();
    }
}

void AssistantManager::setQmlEngine(QQmlApplicationEngine *engine)
{
    m_qmlEngine = engine;
    if (m_lifecycleManager) m_lifecycleManager->setQmlEngine(engine);
    hAssistant() << "QML Engine configuré";
}

void AssistantManager::initConfigEarly(const QString &configPath)
{
    if (m_lifecycleManager) m_lifecycleManager->initConfigEarly(configPath);
    m_configManager = m_lifecycleManager ? m_lifecycleManager->configManager() : nullptr;

    m_configManager = new ConfigManager(this);
    if (!m_configManager->loadConfiguration(configPath)) {
        hWarning(exoAssistant) << "Configuration par défaut utilisée (early)";
    }

    // Exposer immédiatement au QML pour que Component.onCompleted voit les vraies valeurs
    if (m_qmlEngine) {
        m_qmlEngine->rootContext()->setContextProperty("configManager", m_configManager);
        hAssistant() << "configManager exposé au QML (early)";
    }
}

bool AssistantManager::initializeWithConfig(const QString &configPath)
{
    if (m_lifecycleManager && !m_isInitialized) {
        m_lifecycleManager->initializeWithConfig(configPath);
        m_configManager = m_lifecycleManager->configManager();
        m_qmlEngine = m_lifecycleManager->qmlEngine();

        // ── Création des composants (VoicePipeline + AudioDeviceManager
        //    + AIMemoryManager + ClaudeAPI + WeatherManager + ...) ──
        // Sans cet appel, m_voicePipeline reste nul, l'audio n'est jamais
        // initialisé côté C++ et la GUI ne reçoit aucune source audio,
        // aucun VU‑mètre, aucun historique de conversation.
        initializeComponents();
        setupConnections();
        exposeToQml();

        m_isInitialized = true;
        emit initializationComplete();
        hAssistant() << "EXO Assistant initialisé (via LifecycleManager) !";
        sendWelcomeMessage();
        QTimer::singleShot(2000, this, [this]() {
            if (m_voicePipeline) {
                hVoice() << "Démarrage de l'écoute permanente";
                m_voicePipeline->startListening();
            } else {
                hWarning(exoAssistant) << "VoicePipeline NULL — startListening ignoré";
            }
        });
        return true;
    }
    return false;
}

void AssistantManager::initializeComponents()
{
    hAssistant() << "Initialisation des composants principaux...";

    const AssistantCoreComponents components =
        AssistantComponentFactory::createCoreComponents(this,
                                                        m_configManager,
                                                        WEATHER_CACHE_TTL_MS,
                                                        DATETIME_CACHE_TTL_MS,
                                                        HA_STATE_CACHE_TTL_MS,
                                                        CLAUDE_KEEPALIVE_MS,
                                                        HEALTHCHECK_INTERVAL_MS);

    m_claudeApi = components.claudeApi;
    m_voicePipeline = components.voicePipeline;
    m_weatherManager = components.weatherManager;
    m_memoryManager = components.memoryManager;
    m_contextCache = components.contextCache;
    m_healthCheck = components.healthCheck;

    // === SafeBoot facade ===
    m_safeBootFacade = new AssistantSafeBootFacade(this);
    if (m_safeBootController) {
        m_safeBootFacade->setController(m_safeBootController);
    }

    // === Fast-path engine ===
    m_fastPathEngine = new AssistantFastPathEngine(this);
    m_fastPathEngine->configure(m_configManager,
                                m_weatherManager,
                                m_voicePipeline);

    // === Tool dispatcher (microservices outils) ===
    m_toolDispatcher = new AssistantToolDispatcher(this);
    m_toolDispatcher->configure(m_configManager,
                                m_claudeApi,
                                m_voicePipeline,
                                m_weatherManager,
                                m_contextCache);
    m_toolDispatcher->initToolSockets();
}

void AssistantManager::setupConnections()
{
    AssistantConnectionBinder::bindSetupConnections(this,
                                                    m_configManager,
                                                    m_claudeApi,
                                                    m_voicePipeline,
                                                    m_weatherManager,
                                                    m_safeBootFacade,
                                                    m_toolDispatcher);
}

void AssistantManager::exposeToQml()
{
    AssistantQmlExposer::expose(m_qmlEngine,
                                this,
                                m_configManager,
                                m_claudeApi,
                                m_voicePipeline,
                                m_weatherManager,
                                m_memoryManager,
                                m_healthCheck);
}

AudioDeviceManager* AssistantManager::audioDeviceManager() const
{
    return m_voicePipeline ? m_voicePipeline->audioDeviceManager() : nullptr;
}

void AssistantManager::sendMessage(const QString &message)
{
    if (m_messageRouter) m_messageRouter->routeMessage(message);
    if (!m_claudeApi) {
        hWarning(exoAssistant) << "sendMessage: Claude API NULL!";
        emit errorOccurred("Claude API non disponible");
        return;
    }

    hAssistant() << "=== sendMessage ===" << message.left(80)
                 << "claudeReady=" << m_claudeApi->isReady();
    MetricsManager::instance()->increment(QStringLiteral("assistant.messages_sent"));
    m_currentTraceId = TraceManager::instance()->startTrace(QStringLiteral("assistant.sendMessage"));
    
    // Stocker le message utilisateur pour la mémoire
    m_lastUserMessage = message;

    // v26.3: Fast-path — bypass Claude for simple intents (300–500 ms)
    if (tryFastPath(message))
        return;
    
    const QString systemContext = AssistantPromptBuilder::buildSystemContext(m_memoryManager);
    
    // Construire les outils EXO Function Calling
    QJsonArray tools = ClaudeAPI::buildEXOTools();

    // Envoyer le message avec streaming + function calling
    m_claudeApi->sendMessageFull(message, systemContext, tools, true);
}

void AssistantManager::sendManualQuery(const QString &text)
{
    QString trimmed = text.trimmed();
    if (trimmed.isEmpty()) return;
    hAssistant() << "Requête manuelle:" << trimmed.left(50);
    sendMessage(trimmed);
}

void AssistantManager::testTTS(const QString &text)
{
    QString phrase = text.trimmed();
    if (phrase.isEmpty()) {
        phrase = QStringLiteral("Bonjour, je suis EXO.");
    }

    if (!m_voicePipeline) {
        hWarning(exoAssistant) << "Test TTS impossible: VoicePipeline indisponible";
        emit errorOccurred(QStringLiteral("Le service vocal n'est pas prêt"));
        return;
    }

    hVoice() << "Test TTS demandé depuis Settings:" << phrase.left(80);
    m_voicePipeline->speak(phrase);
}

// ═══════════════════════════════════════════════════════
//  v26.3 Fast-path — bypass Claude for trivial intents
//  Target: 300–500 ms instead of 4 s via LLM round-trip
// ═══════════════════════════════════════════════════════

bool AssistantManager::tryFastPath(const QString &message)
{
    if (!m_fastPathEngine) {
        return false;
    }

    QString response;
    if (!m_fastPathEngine->tryHandleMessage(message, &response)) {
        return false;
    }

    if (m_voicePipeline) {
        m_voicePipeline->speakSentence(response);
    }

    emit claudeResponseReceived(response);

    if (m_memoryManager && !m_lastUserMessage.isEmpty()) {
        m_memoryManager->addConversation(m_lastUserMessage, response);
        m_lastUserMessage.clear();
    }

    return true;
}

void AssistantManager::startListening()
{
    if (!m_voicePipeline) {
        hWarning(exoAssistant) << "Voice Pipeline non disponible";
        return;
    }
    
    if (m_isListening) return;
    
    m_voicePipeline->startListening();
    m_isListening = true;
    emit listeningStateChanged(true);
    hVoice() << "Écoute vocale démarrée";
}

void AssistantManager::stopListening()
{
    if (!m_voicePipeline) return;
    
    if (!m_isListening) return;
    
    m_voicePipeline->stopListening();
    m_isListening = false;
    emit listeningStateChanged(false);
    hVoice() << "Écoute vocale arrêtée";
}

QString AssistantManager::getWeatherSummary() const
{
    if (!m_weatherManager) {
        return "Service météo non disponible";
    }
    
    return QString("Météo %1 : %2°C, %3")
           .arg(m_configManager->getWeatherCity())
           .arg(m_weatherManager->temperature())
           .arg(m_weatherManager->description());
}

void AssistantManager::requestNetworkScan(bool fast)
{
    if (!m_toolDispatcher) {
        QJsonObject err;
        err[QStringLiteral("status")] = QStringLiteral("error");
        err[QStringLiteral("message")] = QStringLiteral("Service outils non disponible");
        emit networkScanCompleted(err);
        return;
    }
    m_toolDispatcher->requestNetworkScan(fast);
}

void AssistantManager::requestHomeGraph()
{
    if (!m_toolDispatcher) {
        QJsonObject err;
        err[QStringLiteral("status")] = QStringLiteral("error");
        err[QStringLiteral("message")] = QStringLiteral("Service outils non disponible");
        emit homeGraphReceived(err);
        return;
    }
    m_toolDispatcher->requestHomeGraph();
}

void AssistantManager::requestDeviceCommand(const QString &deviceId,
                                             const QString &command,
                                             const QJsonObject &params)
{
    if (!m_toolDispatcher) {
        QJsonObject err;
        err[QStringLiteral("status")] = QStringLiteral("error");
        err[QStringLiteral("message")] = QStringLiteral("Service outils non disponible");
        emit deviceCommandResult(err);
        return;
    }
    m_toolDispatcher->requestDeviceCommand(deviceId, command, params);
}

void AssistantManager::requestRunScenario(const QString &name)
{
    if (!m_toolDispatcher) {
        QJsonObject err;
        err[QStringLiteral("status")] = QStringLiteral("error");
        err[QStringLiteral("message")] = QStringLiteral("Service outils non disponible");
        emit scenarioResult(err);
        return;
    }
    m_toolDispatcher->requestRunScenario(name);
}

// Slots

void AssistantManager::onWeatherUpdate()
{
    hWeather() << "Données météo mises à jour";
}

void AssistantManager::onError(const QString &error)
{
    if (m_errorManager) m_errorManager->handleError(error);
    // Énoncer vocalement les erreurs Claude « actionnables » pour l'utilisateur
    if (m_voicePipeline) {
        static const QStringList userActionablePrefixes = {
            QStringLiteral("Crédits Anthropic épuisés"),
            QStringLiteral("Clé API Claude invalide"),
            QStringLiteral("Modèle Claude introuvable"),
            QStringLiteral("Limite de requêtes Claude")
        };
        for (const QString &prefix : userActionablePrefixes) {
            if (error.startsWith(prefix)) {
                m_voicePipeline->speakSentence(error);
                break;
            }
        }
    }
}

void AssistantManager::sendWelcomeMessage()
{
    const QString welcomeMessage = "EXO prêt.";
    
    // Émettre le message d'accueil pour l'interface (texte seulement)
    emit claudeResponseReceived(welcomeMessage);
    
    // Pas de TTS au démarrage — l'utilisateur peut tester la voix dans les paramètres
    
    hAssistant() << "Message d'accueil EXO envoyé:" << welcomeMessage;
}

void AssistantManager::onConfigurationLoaded()
{
    hConfig() << "Configuration chargée avec succès";
}

void AssistantManager::onClaudeResponse(const QString &response)
{
    hClaude() << "Réponse Claude reçue:" << response.left(80) + "...";
    MetricsManager::instance()->increment(QStringLiteral("assistant.responses_received"));
    MetricsManager::instance()->recordValue(QStringLiteral("assistant.response_length"),
                                            response.length());
    if (!m_currentTraceId.isEmpty()) {
        TraceManager::instance()->endSpan(m_currentTraceId);
        m_currentTraceId.clear();
    }
    PIPELINE_EVENT(PipelineModule::Claude, EventType::ResponseReceived,
                   QJsonObject{{"length", response.length()}});
    PIPELINE_STATE(PipelineModule::Claude, ModuleState::Idle);
    
    emit claudeResponseReceived(response);
    
    // Stocker la conversation + analyse auto des souvenirs
    if (m_memoryManager && !m_lastUserMessage.isEmpty()) {
        m_memoryManager->addConversation(m_lastUserMessage, response);
        m_memoryManager->analyzeAndMaybeStore(m_lastUserMessage);
    }

    // v7: notifier le ContextEngine de l'interaction
    if (!m_lastUserMessage.isEmpty()) {
        auto *ctxWs = m_toolDispatcher
            ? m_toolDispatcher->toolSocket(QStringLiteral("context"))
            : nullptr;
        if (ctxWs && ctxWs->isValid()) {
            QJsonObject interaction;
            interaction[QStringLiteral("action")] = QStringLiteral("add_interaction");
            QJsonObject params;
            params[QStringLiteral("user")] = m_lastUserMessage;
            params[QStringLiteral("assistant")] = response.left(200);
            interaction[QStringLiteral("params")] = params;
            exo::safeio::wsSafeSend(ctxWs,
                QString::fromUtf8(QJsonDocument(interaction).toJson(QJsonDocument::Compact)),
                "context/add_interaction");
        }
        m_lastUserMessage.clear();
    }
}

void AssistantManager::onSpeechTranscribed(const QString &transcription)
{
    hClaude() << "=== onSpeechTranscribed ===" << transcription.left(80);
    MetricsManager::instance()->increment(QStringLiteral("assistant.transcriptions_received"));
    PIPELINE_EVENT(PipelineModule::Orchestrator, EventType::SpeechTranscribed,
                   QJsonObject{{"text", transcription}, {"length", transcription.length()}});
    
    // L'affichage dans le chat est géré côté QML via Connections { target: voiceManager }
    // → onSpeechTranscribed → transcriptView.addMessage()
}

void AssistantManager::onClaudePartial(const QString &text)
{
    PIPELINE_EVENT(PipelineModule::Claude, EventType::PartialResponse,
                   QJsonObject{{"length", text.length()}});
    // Relayer le streaming partiel vers l'interface QML
    emit claudePartialResponse(text);
}

void AssistantManager::onToolCall(const QString &toolUseId,
                                  const QString &toolName,
                                  const QJsonObject &arguments)
{
    if (!m_toolDispatcher) {
        hWarning(exoAssistant) << "Dispatcher outils non disponible";
        if (m_claudeApi) {
            QJsonObject result;
            result[QStringLiteral("status")] = QStringLiteral("error");
            result[QStringLiteral("message")] = QStringLiteral("Dispatcher outils indisponible");
            m_claudeApi->sendToolResult(toolUseId, result);
        }
        return;
    }

    m_toolDispatcher->handleToolCall(toolUseId, toolName, arguments);
}

