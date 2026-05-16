#pragma once
#include <QObject>

class AssistantErrorManager : public QObject {
    Q_OBJECT
public:
    explicit AssistantErrorManager(QObject *parent = nullptr);
    ~AssistantErrorManager();

    void handleError(const QString &error);

signals:
    void errorOccurred(const QString &error);
};
