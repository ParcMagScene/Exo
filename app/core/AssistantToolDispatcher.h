#pragma once

#include <QObject>
#include <QJsonObject>
#include <QMap>
#include <QSet>

class ConfigManager;
class ClaudeAPI;
class VoicePipeline;
class WeatherManager;
class ContextCache;
class QWebSocket;

class AssistantToolDispatcher : public QObject
{
    Q_OBJECT

public:
    explicit AssistantToolDispatcher(QObject *parent = nullptr);

    void configure(ConfigManager *configManager,
                   ClaudeAPI *claudeApi,
                   VoicePipeline *voicePipeline,
                   WeatherManager *weatherManager,
                   ContextCache *contextCache);

    void initToolSockets();
    void handleToolCall(const QString &toolUseId,
                        const QString &toolName,
                        const QJsonObject &arguments);

    void requestNetworkScan(bool fast);
    void requestHomeGraph();
    void requestDeviceCommand(const QString &deviceId,
                              const QString &command,
                              const QJsonObject &params = {});
    void requestRunScenario(const QString &name);

    QWebSocket *toolSocket(const QString &service) const;

signals:
    void networkScanCompleted(const QJsonObject &result);
    void homeGraphReceived(const QJsonObject &result);
    void deviceCommandResult(const QJsonObject &result);
    void scenarioResult(const QJsonObject &result);

private:
    void dispatchToolToService(const QString &service,
                               const QString &toolUseId,
                               const QString &action,
                               const QJsonObject &params);
    void onToolServiceMessage(const QString &service, const QString &message);

    ConfigManager *m_configManager = nullptr;
    ClaudeAPI *m_claudeApi = nullptr;
    VoicePipeline *m_voicePipeline = nullptr;
    WeatherManager *m_weatherManager = nullptr;
    ContextCache *m_contextCache = nullptr;

    QMap<QString, QWebSocket*> m_toolSockets;
    QMap<QString, QString> m_pendingToolCalls;
    QSet<QString> m_guiToolCalls;
};
