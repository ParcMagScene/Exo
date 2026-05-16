#include "AssistantConnectionBinder.h"

#include "AssistantManager.h"
#include "AssistantSafeBootFacade.h"
#include "AssistantToolDispatcher.h"
#include "ConfigManager.h"
#include "LogManager.h"
#include "PipelineEvent.h"
#include "audio/VoicePipeline.h"
#include "llm/ClaudeAPI.h"
#include "utils/WeatherManager.h"

void AssistantConnectionBinder::bindSetupConnections(AssistantManager *manager,
                                                     ConfigManager *configManager,
                                                     ClaudeAPI *claudeApi,
                                                     VoicePipeline *voicePipeline,
                                                     WeatherManager *weatherManager,
                                                     AssistantSafeBootFacade *safeBootFacade,
                                                     AssistantToolDispatcher *toolDispatcher)
{
    if (!manager) {
        return;
    }

    hAssistant() << "Configuration des connexions entre composants...";

    if (claudeApi) {
        QObject::connect(claudeApi, &ClaudeAPI::finalResponse,
                         manager, &AssistantManager::onClaudeResponse);
        QObject::connect(claudeApi, &ClaudeAPI::partialResponse,
                         manager, &AssistantManager::onClaudePartial);
        QObject::connect(claudeApi, &ClaudeAPI::toolCallDetected,
                         manager, &AssistantManager::onToolCall);
        QObject::connect(claudeApi, &ClaudeAPI::errorOccurred,
                         manager, &AssistantManager::onError);
    }

    if (voicePipeline) {
        QObject::connect(voicePipeline, &VoicePipeline::listeningChanged,
                         manager, [manager, voicePipeline]() {
                             manager->listeningStateChanged(voicePipeline->isListening());
                         });
        QObject::connect(voicePipeline, &VoicePipeline::commandDetected,
                         manager, &AssistantManager::sendMessage);
        QObject::connect(voicePipeline, &VoicePipeline::speechTranscribed,
                         manager, &AssistantManager::onSpeechTranscribed);
    }

    if (weatherManager) {
        QObject::connect(weatherManager, &WeatherManager::weatherUpdated,
                         manager, &AssistantManager::onWeatherUpdate);
    }

    if (configManager && weatherManager) {
        QObject::connect(configManager, &ConfigManager::weatherConfigChanged,
                         manager, [weatherManager](const QString &city, const QString &apiKey) {
                             hWeather() << "Configuration météo mise à jour - Ville:" << city;
                             weatherManager->setCity(city);
                             weatherManager->setApiKey(apiKey);
                             weatherManager->initialize();
                         });
    }

    if (claudeApi && voicePipeline) {
        QObject::connect(claudeApi, &ClaudeAPI::sentenceReady,
                         voicePipeline, [voicePipeline](const QString &sentence) {
                             voicePipeline->speakSentence(sentence);
                         });
        hAssistant() << "Connexion Claude sentenceReady -> VoicePipeline établie";
    }

    if (voicePipeline) {
        QObject::connect(voicePipeline, &VoicePipeline::voiceError,
                         manager, [manager](const QString &error) {
                             hWarning(exoVoice) << "Erreur vocale:" << error;
                             manager->errorOccurred(error);
                         });
        QObject::connect(voicePipeline, &VoicePipeline::statusChanged,
                         manager, [](const QString &status) {
                             hVoice() << "État vocal :" << status;
                         });
        QObject::connect(voicePipeline, &VoicePipeline::wakeWordDetected,
                         manager, []() {
                             hVoice() << "Wake word détecté";
                         });
    }

    if (safeBootFacade) {
        QObject::connect(safeBootFacade, &AssistantSafeBootFacade::safeBootChanged,
                         manager, &AssistantManager::safeBootChanged);
        QObject::connect(safeBootFacade, &AssistantSafeBootFacade::safeBootDecisionMadeChanged,
                         manager, &AssistantManager::safeBootDecisionMadeChanged);
        QObject::connect(safeBootFacade, &AssistantSafeBootFacade::serviceReady,
                         manager, &AssistantManager::serviceReady);
        QObject::connect(safeBootFacade, &AssistantSafeBootFacade::serviceFailed,
                         manager, &AssistantManager::serviceFailed);
    }

    if (toolDispatcher) {
        QObject::connect(toolDispatcher, &AssistantToolDispatcher::networkScanCompleted,
                         manager, &AssistantManager::networkScanCompleted);
        QObject::connect(toolDispatcher, &AssistantToolDispatcher::homeGraphReceived,
                         manager, &AssistantManager::homeGraphReceived);
        QObject::connect(toolDispatcher, &AssistantToolDispatcher::deviceCommandResult,
                         manager, &AssistantManager::deviceCommandResult);
        QObject::connect(toolDispatcher, &AssistantToolDispatcher::scenarioResult,
                         manager, &AssistantManager::scenarioResult);
    }

    auto *eventBus = PipelineEventBus::instance();
    QObject::connect(eventBus, &PipelineEventBus::eventEmitted,
                     LogManager::instance(), &LogManager::logPipelineEvent);

    PIPELINE_STATE(PipelineModule::Orchestrator, ModuleState::Idle);
    PIPELINE_STATE(PipelineModule::AudioCapture, ModuleState::Idle);
    if (claudeApi) {
        PIPELINE_STATE(PipelineModule::Claude, ModuleState::Idle);
    }
    if (voicePipeline) {
        PIPELINE_STATE(PipelineModule::VAD, ModuleState::Idle);
        PIPELINE_STATE(PipelineModule::STT, ModuleState::Idle);
        PIPELINE_STATE(PipelineModule::TTS, ModuleState::Idle);
        PIPELINE_STATE(PipelineModule::AudioOutput, ModuleState::Idle);
    }

    hAssistant() << "Pipeline Event Bus initialisé et connecté";
}
