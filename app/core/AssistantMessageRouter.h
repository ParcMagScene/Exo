#pragma once
#include <QObject>
#include <QString>

class AssistantMessageRouter : public QObject {
    Q_OBJECT
public:
    explicit AssistantMessageRouter(QObject *parent = nullptr);
    ~AssistantMessageRouter();

    void routeMessage(const QString &message);

signals:
    void messageRouted(const QString &message);
};
