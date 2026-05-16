#include "AssistantMessageRouter.h"
#include <QDebug>

AssistantMessageRouter::AssistantMessageRouter(QObject *parent)
    : QObject(parent) {}

AssistantMessageRouter::~AssistantMessageRouter() {}

void AssistantMessageRouter::routeMessage(const QString &message) {
    qInfo().noquote() << QString("Message routé: %1").arg(message.left(80));
    emit messageRouted(message);
}
