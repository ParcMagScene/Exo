#pragma once

class QObject;
class QQmlApplicationEngine;
class ConfigManager;
class ClaudeAPI;
class VoicePipeline;
class WeatherManager;
class AIMemoryManager;
class HealthCheck;

class AssistantQmlExposer
{
public:
    static bool expose(QQmlApplicationEngine *engine,
                       QObject *assistantManager,
                       ConfigManager *configManager,
                       ClaudeAPI *claudeApi,
                       VoicePipeline *voicePipeline,
                       WeatherManager *weatherManager,
                       AIMemoryManager *memoryManager,
                       HealthCheck *healthCheck);
};
