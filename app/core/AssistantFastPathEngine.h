#pragma once

#include <QObject>

class ConfigManager;
class WeatherManager;
class VoicePipeline;

class AssistantFastPathEngine : public QObject
{
    Q_OBJECT

public:
    explicit AssistantFastPathEngine(QObject *parent = nullptr);

    void configure(ConfigManager *configManager,
                   WeatherManager *weatherManager,
                   VoicePipeline *voicePipeline);

    bool tryHandleMessage(const QString &message, QString *responseOut);

private:
    ConfigManager *m_configManager = nullptr;
    WeatherManager *m_weatherManager = nullptr;
    VoicePipeline *m_voicePipeline = nullptr;
};
