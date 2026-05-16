#include "AssistantSafeBootFacade.h"

#include "LogManager.h"
#include "safeboot/SafeBootController.h"

AssistantSafeBootFacade::AssistantSafeBootFacade(QObject *parent)
    : QObject(parent)
{
}

void AssistantSafeBootFacade::setController(SafeBootController *controller)
{
    if (m_safeBootController == controller) {
        return;
    }

    m_safeBootController = controller;
    if (m_safeBootController) {
        connect(m_safeBootController, &SafeBootController::safeBootActivated,
                this, &AssistantSafeBootFacade::safeBootChanged);
        connect(m_safeBootController, &SafeBootController::safeBootDeactivated,
                this, &AssistantSafeBootFacade::safeBootChanged);
        connect(m_safeBootController, &SafeBootController::serviceFailed,
                this, &AssistantSafeBootFacade::safeBootChanged);
        connect(m_safeBootController, &SafeBootController::serviceRecovered,
                this, &AssistantSafeBootFacade::safeBootChanged);
        connect(m_safeBootController, &SafeBootController::timelineUpdated,
                this, &AssistantSafeBootFacade::safeBootChanged);

        connect(m_safeBootController, &SafeBootController::criticalServicesReady,
                this, [this]() {
                    setSafeBootDecisionMade(true);
                });
        connect(m_safeBootController, &SafeBootController::safeBootActivated,
                this, [this]() {
                    setSafeBootDecisionMade(true);
                });

        const bool decisionAlreadyMade = m_safeBootController->isSafeBootEnabled()
            || m_safeBootController->readyCount() >= (m_safeBootController->totalCount()
                                                      - m_safeBootController->degradedCount());
        setSafeBootDecisionMade(decisionAlreadyMade);
    }

    emit safeBootChanged();
}

bool AssistantSafeBootFacade::safeBootEnabled() const
{
    return m_safeBootController ? m_safeBootController->isSafeBootEnabled() : false;
}

QVariantList AssistantSafeBootFacade::failedServices() const
{
    return m_safeBootController ? m_safeBootController->getFailedServices() : QVariantList{};
}

QVariantList AssistantSafeBootFacade::degradedServices() const
{
    return m_safeBootController ? m_safeBootController->getDegradedServices() : QVariantList{};
}

QVariantList AssistantSafeBootFacade::startupTimeline() const
{
    return m_safeBootController ? m_safeBootController->getStartupTimeline() : QVariantList{};
}

bool AssistantSafeBootFacade::autoRepairRunning() const
{
    return m_safeBootController ? m_safeBootController->autoRepairRunning() : false;
}

QVariantList AssistantSafeBootFacade::repairTimeline() const
{
    return m_safeBootController ? m_safeBootController->repairTimeline() : QVariantList{};
}

bool AssistantSafeBootFacade::safeBootDecisionMade() const
{
    return m_safeBootDecisionMade;
}

void AssistantSafeBootFacade::setSafeBootDecisionMade(bool value)
{
    if (m_safeBootDecisionMade == value) {
        return;
    }

    m_safeBootDecisionMade = value;
    hAssistant() << "[SafeBoot] Decision made:" << (value ? "true" : "false")
                 << "| safeBootEnabled:" << safeBootEnabled();
    emit safeBootDecisionMadeChanged();
}

void AssistantSafeBootFacade::onServiceReady(const QString &serviceName)
{
    hAssistant() << "[SafeBoot] Service prêt :" << serviceName;
    emit serviceReady(serviceName);
    emit safeBootChanged();
}

void AssistantSafeBootFacade::onServiceFailed(const QString &serviceName)
{
    hWarning(exoAssistant) << "[SafeBoot] Service en échec :" << serviceName;
    emit serviceFailed(serviceName);
    emit safeBootChanged();
}

void AssistantSafeBootFacade::onRepairAttempt(const QString &service, bool success)
{
    if (success) {
        hAssistant() << "[AutoRepair] Service repare:" << service;
    } else {
        hWarning(exoAssistant) << "[AutoRepair] Echec reparation:" << service;
    }
    emit safeBootChanged();
}

void AssistantSafeBootFacade::onRepairCompleted()
{
    hAssistant() << "[AutoRepair] Reparation automatique terminee";
    emit safeBootChanged();
}
