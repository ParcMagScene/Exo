#pragma once

class AssistantManager;
class ConfigManager;
class ClaudeAPI;
class VoicePipeline;
class WeatherManager;
class AssistantSafeBootFacade;
class AssistantToolDispatcher;

class AssistantConnectionBinder
{
public:
    static void bindSetupConnections(AssistantManager *manager,
                                     ConfigManager *configManager,
                                     ClaudeAPI *claudeApi,
                                     VoicePipeline *voicePipeline,
                                     WeatherManager *weatherManager,
                                     AssistantSafeBootFacade *safeBootFacade,
                                     AssistantToolDispatcher *toolDispatcher);
};
