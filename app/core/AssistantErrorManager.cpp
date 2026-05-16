#include "AssistantErrorManager.h"
#include <QDebug>

AssistantErrorManager::AssistantErrorManager(QObject *parent)
    : QObject(parent) {}

AssistantErrorManager::~AssistantErrorManager() {}

void AssistantErrorManager::handleError(const QString &error) {
    qCritical().noquote() << QString("Erreur Assistant: %1").arg(error);
    emit errorOccurred(error);
}
