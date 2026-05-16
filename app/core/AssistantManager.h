#pragma once

#include <QObject>
#include <QTimer>
#include <QJsonObject>
#include <QJsonDocument>
#include <QQmlApplicationEngine>
#include "ConfigManager.h"
#include "HealthCheck.h"

class ClaudeAPI;
class WeatherManager;
class VoicePipeline;
class AIMemoryManager;
class AudioDeviceManager;
class ContextCache;
class SafeBootController;
class AssistantToolDispatcher;
class AssistantFastPathEngine;
class AssistantSafeBootFacade;
class AssistantConnectionBinder;
class AssistantMessageRouter;
class AssistantErrorManager;
class AssistantLifecycleManager;

Q_DECLARE_METATYPE(ConfigManager*)

/**
 * @brief Gestionnaire principal de l'assistant EXO (version simplifiée)
 * 
 * Coordonne les interactions entre Claude API, Weather Manager et l'interface QML
 */
class AssistantManager : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool isListening READ isListening NOTIFY listeningStateChanged)
    Q_PROPERTY(bool isInitialized READ isInitialized NOTIFY initializationComplete)
    Q_PROPERTY(ConfigManager* configManager READ configManager CONSTANT)
    Q_PROPERTY(HealthCheck* healthCheck READ healthCheck CONSTANT)
    Q_PROPERTY(AudioDeviceManager* audioDeviceManager READ audioDeviceManager CONSTANT)
    Q_PROPERTY(bool safeBootEnabled READ safeBootEnabled NOTIFY safeBootChanged)
    Q_PROPERTY(QVariantList failedServices READ failedServices NOTIFY safeBootChanged)
    Q_PROPERTY(QVariantList degradedServices READ degradedServices NOTIFY safeBootChanged)
    Q_PROPERTY(QVariantList startupTimeline READ startupTimeline NOTIFY safeBootChanged)
    Q_PROPERTY(bool autoRepairRunning READ autoRepairRunning NOTIFY autoRepairChanged)
    Q_PROPERTY(QVariantList repairTimeline READ repairTimeline NOTIFY repairTimelineChanged)
    Q_PROPERTY(bool safeBootDecisionMade READ safeBootDecisionMade NOTIFY safeBootDecisionMadeChanged)

public:
    explicit AssistantManager(QObject *parent = nullptr);
    ~AssistantManager();

    // Propriétés
    bool isListening() const { return m_isListening; }
    bool isInitialized() const { return m_isInitialized; }
    
    // Configuration
    // Délégation au lifecycle manager
    void setQmlEngine(QQmlApplicationEngine *engine);
    void initConfigEarly(const QString &configPath = "config/assistant.conf");

    // Méthodes publiques
    Q_INVOKABLE bool initializeWithConfig(const QString &configPath = "config/assistant.conf");
    Q_INVOKABLE void sendMessage(const QString &message);
    Q_INVOKABLE void sendManualQuery(const QString &text);
    Q_INVOKABLE void testTTS(const QString &text);
    Q_INVOKABLE void startListening();
    Q_INVOKABLE void stopListening();
    Q_INVOKABLE QString getWeatherSummary() const;
    Q_INVOKABLE void requestNetworkScan(bool fast = false);
    Q_INVOKABLE void requestHomeGraph();
    Q_INVOKABLE void requestDeviceCommand(const QString &deviceId,
                                           const QString &command,
                                           const QJsonObject &params = {});
    Q_INVOKABLE void requestRunScenario(const QString &name);
    
    // Accès aux composants pour l'exposition QML  
    ClaudeAPI* claudeApi() const { return m_claudeApi; }
    VoicePipeline* voicePipeline() const { return m_voicePipeline; }
    WeatherManager* weatherManager() const { return m_weatherManager; }
    ConfigManager* configManager() const { return m_configManager; }
    AIMemoryManager* memoryManager() const { return m_memoryManager; }
    HealthCheck* healthCheck() const { return m_healthCheck; }
    AudioDeviceManager* audioDeviceManager() const;

    // Safe Boot
    void setSafeBootController(SafeBootController *controller);
    bool safeBootEnabled() const;
    QVariantList failedServices() const;
    QVariantList degradedServices() const;
    QVariantList startupTimeline() const;

    // AutoRepair
    bool autoRepairRunning() const;
    QVariantList repairTimeline() const;

    // Safe Boot decision
    bool safeBootDecisionMade() const;
    void setSafeBootDecisionMade(bool value);

    // Safe Boot — réception des événements service
    Q_INVOKABLE void onServiceReady(const QString &serviceName);
    Q_INVOKABLE void onServiceFailed(const QString &serviceName);
    Q_INVOKABLE void onRepairAttempt(const QString &service, bool success);
    Q_INVOKABLE void onRepairCompleted();

signals:
    void messageReceived(const QString &sender, const QString &message);
    void claudeResponseReceived(const QString &response);
    void claudePartialResponse(const QString &partialText);
    void listeningStateChanged(bool isListening);
    void initializationComplete();
    void errorOccurred(const QString &error);
    void networkScanCompleted(const QJsonObject &result);
    void homeGraphReceived(const QJsonObject &result);
    void deviceCommandResult(const QJsonObject &result);
    void scenarioResult(const QJsonObject &result);
    void safeBootChanged();
    void safeBootDecisionMadeChanged();
    void autoRepairChanged();
    void repairTimelineChanged();
    void serviceReady(const QString &service);
    void serviceFailed(const QString &service);

private slots:
    void onClaudeResponse(const QString &response);
    void onClaudePartial(const QString &text);
    void onToolCall(const QString &toolUseId,
                    const QString &toolName,
                    const QJsonObject &arguments);
    void onWeatherUpdate();
    void onError(const QString &error);
    void onConfigurationLoaded();

private:
            AssistantMessageRouter* m_messageRouter = nullptr;
        AssistantErrorManager* m_errorManager = nullptr;
    friend class AssistantConnectionBinder;

    void initializeComponents();
    void setupConnections();
    void exposeToQml();
    void sendWelcomeMessage();
    void onSpeechTranscribed(const QString &transcription);

    // v26.3: Fast-path — bypass Claude for simple intents
    bool tryFastPath(const QString &message);

    // Membres privés
    bool m_isListening;
    bool m_isInitialized;
    QString m_lastUserMessage;
    QString m_currentTraceId;
    
    // Composants
// Ajout du LifecycleManager

private:
    // Nouveau : gestionnaire de cycle de vie
    AssistantLifecycleManager* m_lifecycleManager = nullptr;
    ConfigManager *m_configManager;
    ClaudeAPI *m_claudeApi;
    VoicePipeline *m_voicePipeline;
    WeatherManager *m_weatherManager;
    AIMemoryManager *m_memoryManager;
    HealthCheck *m_healthCheck;
    QQmlApplicationEngine *m_qmlEngine;
    AssistantToolDispatcher *m_toolDispatcher = nullptr;
    AssistantFastPathEngine *m_fastPathEngine = nullptr;
    AssistantSafeBootFacade *m_safeBootFacade = nullptr;

    // v8.1 ULL: Context cache
    ContextCache *m_contextCache = nullptr;
            // SafeBoot controller is injected before components are initialized.
            SafeBootController *m_safeBootController = nullptr;

};