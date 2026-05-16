#pragma once
#include <QObject>
#include <QQmlApplicationEngine>
#include "ConfigManager.h"

class AssistantLifecycleManager : public QObject {
    Q_OBJECT
public:
    explicit AssistantLifecycleManager(QObject *parent = nullptr);
    ~AssistantLifecycleManager();

    void setQmlEngine(QQmlApplicationEngine *engine);
    void initConfigEarly(const QString &configPath = "config/assistant.conf");
    bool initializeWithConfig(const QString &configPath = "config/assistant.conf");

    ConfigManager* configManager() const;
    QQmlApplicationEngine* qmlEngine() const;

signals:
    void initializationComplete();

private:
    ConfigManager* m_configManager = nullptr;
    QQmlApplicationEngine* m_qmlEngine = nullptr;
    bool m_isInitialized = false;
};
