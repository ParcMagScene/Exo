#pragma once

#include <QObject>
#include <QVariantList>

class SafeBootController;

class AssistantSafeBootFacade : public QObject
{
    Q_OBJECT

public:
    explicit AssistantSafeBootFacade(QObject *parent = nullptr);

    void setController(SafeBootController *controller);

    bool safeBootEnabled() const;
    QVariantList failedServices() const;
    QVariantList degradedServices() const;
    QVariantList startupTimeline() const;

    bool autoRepairRunning() const;
    QVariantList repairTimeline() const;

    bool safeBootDecisionMade() const;
    void setSafeBootDecisionMade(bool value);

    void onServiceReady(const QString &serviceName);
    void onServiceFailed(const QString &serviceName);
    void onRepairAttempt(const QString &service, bool success);
    void onRepairCompleted();

signals:
    void safeBootChanged();
    void safeBootDecisionMadeChanged();
    void serviceReady(const QString &service);
    void serviceFailed(const QString &service);

private:
    SafeBootController *m_safeBootController = nullptr;
    bool m_safeBootDecisionMade = false;
};
