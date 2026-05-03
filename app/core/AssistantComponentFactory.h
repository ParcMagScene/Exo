#pragma once

class QObject;
class ConfigManager;
class ClaudeAPI;
class VoicePipeline;
class WeatherManager;
class AIMemoryManager;
class ContextCache;
class HealthCheck;

struct AssistantCoreComponents
{
    ClaudeAPI *claudeApi = nullptr;
    VoicePipeline *voicePipeline = nullptr;
    WeatherManager *weatherManager = nullptr;
    AIMemoryManager *memoryManager = nullptr;
    ContextCache *contextCache = nullptr;
    HealthCheck *healthCheck = nullptr;
};

class AssistantComponentFactory
{
public:
    static AssistantCoreComponents createCoreComponents(QObject *owner,
                                                        ConfigManager *configManager,
                                                        int weatherCacheTtlMs,
                                                        int datetimeCacheTtlMs,
                                                        int haStateCacheTtlMs,
                                                        int claudeKeepaliveMs,
                                                        int healthcheckIntervalMs);
};
