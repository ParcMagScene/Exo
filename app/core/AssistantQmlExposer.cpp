#include "AssistantQmlExposer.h"

#include "ConfigManager.h"
#include "HealthCheck.h"
#include "LogManager.h"
#include "PipelineEvent.h"
#include "audio/AudioDeviceManager.h"
#include "audio/VoicePipeline.h"
#include "llm/AIMemoryManager.h"
#include "llm/ClaudeAPI.h"
#include "utils/WeatherManager.h"

#include <QQmlApplicationEngine>
#include <QQmlContext>

bool AssistantQmlExposer::expose(QQmlApplicationEngine *engine,
                                 QObject *assistantManager,
                                 ConfigManager *configManager,
                                 ClaudeAPI *claudeApi,
                                 VoicePipeline *voicePipeline,
                                 WeatherManager *weatherManager,
                                 AIMemoryManager *memoryManager,
                                 HealthCheck *healthCheck)
{
    if (!engine) {
        hWarning(exoAssistant) << "QML Engine non disponible pour l'exposition";
        return false;
    }

    QQmlContext *root = engine->rootContext();
    root->setContextProperty("assistantManager", assistantManager);

    if (claudeApi) {
        root->setContextProperty("claudeAPI", claudeApi);
    }
    if (voicePipeline) {
        root->setContextProperty("voiceManager", voicePipeline);
    }
    if (weatherManager) {
        root->setContextProperty("weatherManager", weatherManager);
    }
    if (configManager) {
        root->setContextProperty("configManager", configManager);
    }
    if (memoryManager) {
        root->setContextProperty("memoryManager", memoryManager);
    }
    if (healthCheck) {
        root->setContextProperty("healthCheck", healthCheck);
    }
    if (voicePipeline && voicePipeline->audioDeviceManager()) {
        root->setContextProperty("audioDeviceManager", voicePipeline->audioDeviceManager());
    }

    root->setContextProperty("logManager", LogManager::instance());
    root->setContextProperty("pipelineEventBus", PipelineEventBus::instance());

    hAssistant() << "Composants exposés au QML avec succès";
    return true;
}
