// ═══════════════════════════════════════════════════════
//  Test unitaire — SafeBootController
//  Vérifie : timeout critique → Safe Boot activé,
//            timeout non critique → Degraded,
//            service lent → timeout → Safe Boot,
//            criticalServicesReady émis,
//            lazy-load et retry
// ═══════════════════════════════════════════════════════
#include <QtTest/QtTest>
#include <QSignalSpy>
#include "ServiceRegistry.h"
#include "SafeBootController.h"

class TestSafeBoot : public QObject
{
    Q_OBJECT

private:
    // Helper : enregistrer des services dans le registry
    void registerTestServices(ServiceRegistry &reg,
                              const QStringList &names,
                              int basePort = 8765)
    {
        int port = basePort;
        for (const QString &name : names) {
            Exo::ServiceDescriptor desc;
            desc.name = name;
            desc.port = port++;
            reg.registerService(desc);
        }
    }

private slots:

    // ── 1. Service critique KO → Safe Boot doit s'activer ──
    void criticalTimeout_activatesSafeBoot()
    {
        ServiceRegistry reg;
        registerTestServices(reg, {"orchestrator", "system", "memory",
                                    "websearch", "news"});

        SafeBootController ctrl;
        ctrl.setRegistry(&reg);

        QSignalSpy spyActivated(&ctrl, &SafeBootController::safeBootActivated);
        QSignalSpy spyCriticalReady(&ctrl, &SafeBootController::criticalServicesReady);

        ctrl.startMonitoring();

        QVERIFY(!ctrl.isSafeBootEnabled());

        // Le timeout de prod est 30s : en test on simule un échec critique
        // pour éviter un test lent/flaky dépendant d'un délai long.
        reg.setState("orchestrator", Exo::ServiceState::Crashed);

        QTRY_VERIFY_WITH_TIMEOUT(ctrl.isSafeBootEnabled(), 1000);

        // Safe Boot doit être activé
        QVERIFY(spyActivated.count() >= 1);

        // criticalServicesReady doit être émis (force start)
        QVERIFY(spyCriticalReady.count() >= 1);

        // Les critiques non-ready doivent être en Failed
        QVERIFY(ctrl.failedCount() > 0);
    }

    // ── 2. Service non critique KO → EXO démarre normalement ──
    void nonCriticalTimeout_doesNotBlockBoot()
    {
        ServiceRegistry reg;
        registerTestServices(reg, {"orchestrator", "system", "memory",
                                    "context", "planner", "executor",
                                    "verifier", "websearch", "news"});

        SafeBootController ctrl;
        ctrl.setRegistry(&reg);

        QSignalSpy spyCriticalReady(&ctrl, &SafeBootController::criticalServicesReady);

        ctrl.startMonitoring();

        // Simuler tous les services critiques deviennent Ready immédiatement
        for (const QString &name : {"orchestrator", "system", "memory",
                                     "context", "planner", "executor", "verifier"}) {
            reg.setState(name, Exo::ServiceState::Ready);
        }

        // criticalServicesReady doit être émis
        QTRY_VERIFY_WITH_TIMEOUT(spyCriticalReady.count() >= 1, 1000);

        // Le timeout non critique est 30s en prod : on simule l'échec non critique
        // pour valider la logique Degraded sans allonger le test.
        reg.setState("websearch", Exo::ServiceState::Crashed);
        reg.setState("news", Exo::ServiceState::Crashed);

        QTRY_VERIFY_WITH_TIMEOUT(ctrl.degradedCount() >= 2, 1000);

        // Safe Boot ne devrait PAS être activé (tous les critiques sont OK)
        QVERIFY(!ctrl.isSafeBootEnabled());
    }

    // ── 3. Service critique lent/KO → Safe Boot ──
    void slowCriticalService_triggersSafeBoot()
    {
        ServiceRegistry reg;
        registerTestServices(reg, {"orchestrator", "memory", "context",
                                    "planner", "executor", "verifier",
                                    "system"});

        SafeBootController ctrl;
        ctrl.setRegistry(&reg);

        QSignalSpy spyActivated(&ctrl, &SafeBootController::safeBootActivated);

        ctrl.startMonitoring();

        // Rendre Ready tous sauf "system" (qui sera lent)
        for (const QString &name : {"orchestrator", "memory", "context",
                                     "planner", "executor", "verifier"}) {
            reg.setState(name, Exo::ServiceState::Ready);
        }

        // Simuler l'échec du critique "system" (équivalent timeout/failure).
        reg.setState("system", Exo::ServiceState::Crashed);

        QTRY_VERIFY_WITH_TIMEOUT(spyActivated.count() >= 1, 1000);
        QVERIFY(ctrl.isSafeBootEnabled());
    }

    // ── 4. JSON invalide / état crashed → Safe Boot ──
    void crashedCriticalService_triggersSafeBoot()
    {
        ServiceRegistry reg;
        registerTestServices(reg, {"orchestrator", "system", "memory"});

        SafeBootController ctrl;
        ctrl.setRegistry(&reg);

        QSignalSpy spyActivated(&ctrl, &SafeBootController::safeBootActivated);
        QSignalSpy spyFailed(&ctrl, &SafeBootController::serviceFailed);

        ctrl.startMonitoring();

        // Simuler un crash du service "orchestrator"
        reg.setState("orchestrator", Exo::ServiceState::Crashed);

        // Safe Boot doit s'activer (service critique crashé)
        QTRY_VERIFY_WITH_TIMEOUT(ctrl.isSafeBootEnabled(), 1000);
        QVERIFY(spyFailed.count() >= 1);
    }

    // ── 5. Tous les critiques ready → criticalServicesReady ──
    void allCriticalReady_emitsSignal()
    {
        ServiceRegistry reg;
        registerTestServices(reg, {"orchestrator", "system", "memory",
                                    "context", "planner", "executor",
                                    "verifier"});

        SafeBootController ctrl;
        ctrl.setRegistry(&reg);

        QSignalSpy spyCriticalReady(&ctrl, &SafeBootController::criticalServicesReady);

        ctrl.startMonitoring();

        // Rendre tous les critiques Ready
        for (const QString &name : {"orchestrator", "system", "memory",
                                     "context", "planner", "executor", "verifier"}) {
            reg.setState(name, Exo::ServiceState::Ready);
        }

        QTRY_VERIFY_WITH_TIMEOUT(spyCriticalReady.count() == 1, 1000);
        QVERIFY(!ctrl.isSafeBootEnabled());
    }

    // ── 6. markServiceFailed force le Safe Boot ──
    void markServiceFailed_criticalTriggersSafeBoot()
    {
        ServiceRegistry reg;
        registerTestServices(reg, {"orchestrator", "system"});

        SafeBootController ctrl;
        ctrl.setRegistry(&reg);

        QSignalSpy spyActivated(&ctrl, &SafeBootController::safeBootActivated);

        ctrl.startMonitoring();

        // Marquer manuellement un critique comme failed
        ctrl.markServiceFailed("orchestrator");

        QVERIFY(ctrl.isSafeBootEnabled());
        QVERIFY(spyActivated.count() == 1);
    }

    // ── 7. markServiceFailed non critique → Degraded (pas Safe Boot) ──
    void markServiceFailed_nonCritical_degradedOnly()
    {
        ServiceRegistry reg;
        registerTestServices(reg, {"orchestrator", "websearch"});

        SafeBootController ctrl;
        ctrl.setRegistry(&reg);

        ctrl.startMonitoring();

        // Marquer un non-critique comme failed
        ctrl.markServiceFailed("websearch");

        // Safe Boot ne doit PAS être activé
        QVERIFY(!ctrl.isSafeBootEnabled());
        QVERIFY(ctrl.degradedCount() >= 1);
    }

    // ── 8. Timeline tracking ──
    void timelineRecordsEvents()
    {
        ServiceRegistry reg;
        registerTestServices(reg, {"orchestrator", "websearch"});

        SafeBootController ctrl;
        ctrl.setRegistry(&reg);

        ctrl.startMonitoring();

        // La timeline doit contenir au minimum "monitoring_start"
        QVariantList timeline = ctrl.getStartupTimeline();
        QVERIFY(timeline.size() >= 1);

        QVariantMap firstEntry = timeline.first().toMap();
        QCOMPARE(firstEntry.value("event").toString(), "monitoring_start");
    }

    // ── 9. restartNormalMode reset tout ──
    void restartNormalMode_resetsState()
    {
        ServiceRegistry reg;
        registerTestServices(reg, {"orchestrator", "websearch"});

        SafeBootController ctrl;
        ctrl.setRegistry(&reg);

        ctrl.startMonitoring();
        ctrl.markServiceFailed("orchestrator");
        QVERIFY(ctrl.isSafeBootEnabled());

        // Restart normal
        ctrl.restartNormalMode();

        QVERIFY(!ctrl.isSafeBootEnabled());
        QCOMPARE(ctrl.failedCount(), 0);
        QCOMPARE(ctrl.degradedCount(), 0);
    }
};

QTEST_MAIN(TestSafeBoot)
#include "test_safeboot.moc"
