#include "AssistantComponentFactory.h"

#include "ConfigManager.h"
#include "ContextCache.h"
#include "HealthCheck.h"
#include "LogManager.h"
#include "PipelineTracer.h"
#include "audio/VoicePipeline.h"
#include "llm/AIMemoryManager.h"
#include "llm/ClaudeAPI.h"
#include "utils/WeatherManager.h"

#include <QDate>
#include <QJsonObject>
#include <QLocale>
#include <QTime>

AssistantCoreComponents AssistantComponentFactory::createCoreComponents(
    QObject *owner,
    ConfigManager *configManager,
    int weatherCacheTtlMs,
    int datetimeCacheTtlMs,
    int haStateCacheTtlMs,
    int claudeKeepaliveMs,
    int healthcheckIntervalMs)
{
    AssistantCoreComponents components;

    if (!owner || !configManager) {
        return components;
    }

    components.claudeApi = new ClaudeAPI(owner);
    const QString claudeKey = configManager->getClaudeApiKey();
    if (!claudeKey.isEmpty()) {
        components.claudeApi->setApiKey(claudeKey);
        components.claudeApi->setModel(configManager->getClaudeModel());
        hClaude() << "Claude API configure avec le modele:" << configManager->getClaudeModel();
    } else {
        hWarning(exoClaude) << "Cle API Claude manquante - fonctionnalite desactivee";
    }

    components.voicePipeline = new VoicePipeline(owner);

    const QString audioBackend = configManager->getString("Audio", "backend", "qt");
    components.voicePipeline->setAudioBackend(audioBackend);
    components.voicePipeline->initAudio();

    const QString vadBackend = configManager->getVADBackend();
    VADEngine::Backend vadEnum = VADEngine::Backend::Builtin;
    if (vadBackend == "silero") {
        vadEnum = VADEngine::Backend::SileroONNX;
    } else if (vadBackend == "hybrid") {
        vadEnum = VADEngine::Backend::Hybrid;
    }
    const QString vadUrl = configManager->getString("VAD", "server_url", "ws://localhost:8768");
    components.voicePipeline->initVAD(vadEnum, vadUrl);

    components.voicePipeline->initSTT(configManager->getSTTServerUrl());
    components.voicePipeline->initTTS(configManager->getTTSServerUrl());

    const bool wakewordNeural = configManager->getBool("WakeWord", "neural_enabled", false);
    if (wakewordNeural) {
        const QString wakewordUrl = configManager->getString("WakeWord", "server_url", "ws://localhost:8770");
        components.voicePipeline->initWakeWordServer(wakewordUrl);
    }

    components.voicePipeline->setTTSVoice(configManager->getTTSVoice());
    components.voicePipeline->setTTSLanguage(configManager->getTTSLanguage());
    components.voicePipeline->setTTSStyle(configManager->getTTSStyle());
    components.voicePipeline->setTTSEngine(configManager->getTTSEngine());
    components.voicePipeline->setTTSOutputDevice(configManager->getString("Audio", "output_device", QString()));
    components.voicePipeline->setTTSPitch(configManager->getString("TTS", "pitch", "1.0").toFloat());
    components.voicePipeline->setTTSRate(configManager->getString("TTS", "rate", "1.0").toFloat());

    components.voicePipeline->setNoiseGate(configManager->getString("Audio", "noise_gate", "0.001").toFloat());
    components.voicePipeline->setAGC(configManager->getBool("Audio", "agc_enabled", true));

    components.voicePipeline->setSTTLanguage(configManager->getSTTLanguage());
    components.voicePipeline->setVADThreshold(static_cast<float>(configManager->getVADThreshold()));
    components.voicePipeline->setWakeWord(configManager->getWakeWord());
    components.voicePipeline->connectToServer(configManager->getGUIServerUrl());

    hVoice() << "VoicePipeline configure (wake-word logiciel)"
             << "STT:" << configManager->getSTTServerUrl()
             << "TTS:" << configManager->getTTSServerUrl()
             << "GUI:" << configManager->getGUIServerUrl();

    components.weatherManager = new WeatherManager(owner);
    const QString weatherKey = configManager->getWeatherApiKey();
    if (!weatherKey.isEmpty()) {
        components.weatherManager->setApiKey(weatherKey);
        components.weatherManager->setCity(configManager->getWeatherCity());
        components.weatherManager->initialize();
        hWeather() << "Weather Manager configure pour:" << configManager->getWeatherCity();
    } else {
        hWarning(exoWeather) << "Cle API meteo manquante - fonctionnalite desactivee";
    }

    components.memoryManager = new AIMemoryManager(owner);
    const QString memoryUrl = configManager->getString("Memory", "semantic_server_url", "ws://localhost:8771");
    const bool semanticEnabled = configManager->getBool("Memory", "semantic_enabled", true);
    if (semanticEnabled) {
        components.memoryManager->initSemanticServer(memoryUrl);
    }
    hAssistant() << "Memory Manager initialise - memoire EXO activee";

    PipelineTracer::instance();
    hAssistant() << "PipelineTracer initialise - analyse post-interaction activee";

    components.contextCache = new ContextCache(owner);
    components.contextCache->addRefreshRule("weather", weatherCacheTtlMs);
    components.contextCache->addRefreshRule("datetime", datetimeCacheTtlMs);
    components.contextCache->addRefreshRule("ha_state", haStateCacheTtlMs);
    components.contextCache->startBackgroundRefresh();

    ContextCache *cache = components.contextCache;
    QObject::connect(cache, &ContextCache::refreshNeeded, cache,
                     [cache, datetimeCacheTtlMs](const QString &key) {
                         if (key == "datetime") {
                             QJsonObject dt;
                             dt["date"] = QDate::currentDate().toString(Qt::ISODate);
                             dt["time"] = QTime::currentTime().toString("HH:mm:ss");
                             dt["day_name"] = QLocale(QLocale::French).dayName(QDate::currentDate().dayOfWeek());
                             cache->set(key, dt, datetimeCacheTtlMs);
                         }
                     });

    {
        QJsonObject dt;
        dt["date"] = QDate::currentDate().toString(Qt::ISODate);
        dt["time"] = QTime::currentTime().toString("HH:mm:ss");
        dt["day_name"] = QLocale(QLocale::French).dayName(QDate::currentDate().dayOfWeek());
        components.contextCache->set("datetime", dt, datetimeCacheTtlMs);
    }
    hAssistant() << "ContextCache initialise avec regles de rafraichissement";

    if (components.claudeApi && components.claudeApi->isReady()) {
        components.claudeApi->initWarmup();
        components.claudeApi->startKeepAlive(claudeKeepaliveMs);
    }

    components.healthCheck = new HealthCheck(owner);
    components.healthCheck->configure(configManager);
    components.healthCheck->start(healthcheckIntervalMs);
    hAssistant() << "HealthCheck initialise - surveillance des microservices activee";

    return components;
}
