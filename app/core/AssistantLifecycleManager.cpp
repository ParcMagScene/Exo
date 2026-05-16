#include "AssistantLifecycleManager.h"
#include "ConfigManager.h"
#include <QQmlContext>
#include <QDebug>

AssistantLifecycleManager::AssistantLifecycleManager(QObject *parent)
    : QObject(parent)
{
}

AssistantLifecycleManager::~AssistantLifecycleManager() {}

void AssistantLifecycleManager::setQmlEngine(QQmlApplicationEngine *engine) {
    m_qmlEngine = engine;
    qInfo().noquote() << "QML Engine configuré (LifecycleManager)";
}

void AssistantLifecycleManager::initConfigEarly(const QString &configPath) {
    if (m_configManager) return;
    m_configManager = new ConfigManager(this);
    if (!m_configManager->loadConfiguration(configPath)) {
        qWarning().noquote() << "Configuration par défaut utilisée (early)";
    }
    if (m_qmlEngine) {
        m_qmlEngine->rootContext()->setContextProperty("configManager", m_configManager);
        qInfo().noquote() << "configManager exposé au QML (early)";
    }
}

bool AssistantLifecycleManager::initializeWithConfig(const QString &configPath) {
    if (m_isInitialized) return true;
    if (!m_configManager) {
        m_configManager = new ConfigManager(this);
        if (!m_configManager->loadConfiguration(configPath)) {
            qWarning().noquote() << "Configuration par défaut utilisée";
        }
    }
    m_isInitialized = true;
    emit initializationComplete();
    return true;
}

ConfigManager* AssistantLifecycleManager::configManager() const {
    return m_configManager;
}

QQmlApplicationEngine* AssistantLifecycleManager::qmlEngine() const {
    return m_qmlEngine;
}
