#include <QtTest/QtTest>
#include <QSignalSpy>
#include "HealthCheck.h"
#include "ConfigManager.h"

// ═══════════════════════════════════════════════════════
//  test_healthcheck — Tests unitaires pour HealthCheck
// ═══════════════════════════════════════════════════════

class TestHealthCheck : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();

    // ── Tests des états ──
    void testInitialState();
    void testServiceHealthEnum();
    void testOverallHealthEnum();
    void testHealthToString();

    // ── Tests sans connexion réseau ──
    void testConfigureWithoutConfig();
    void testStartWithoutConfigure();
    void testStopResetsState();
    void testCheckNowEmitsSignal();

    void cleanupTestCase();
};

void TestHealthCheck::initTestCase()
{
    qDebug() << "=== TestHealthCheck ===";
}

void TestHealthCheck::testInitialState()
{
    HealthCheck hc;

    // Avant configure(), tous les statuts doivent être "unknown"
    QCOMPARE(hc.sttStatus(), QStringLiteral("unknown"));
    QCOMPARE(hc.ttsStatus(), QStringLiteral("unknown"));
    QCOMPARE(hc.vadStatus(), QStringLiteral("unknown"));
    QCOMPARE(hc.wakewordStatus(), QStringLiteral("unknown"));
    QCOMPARE(hc.memoryStatus(), QStringLiteral("unknown"));
    QCOMPARE(hc.nluStatus(), QStringLiteral("unknown"));
    QCOMPARE(hc.overallStatus(), QStringLiteral("unknown"));
    QVERIFY(!hc.allHealthy());
}

void TestHealthCheck::testServiceHealthEnum()
{
    HealthCheck hc;
    // Vérifier que l'enum est exposée au méta-objet
    const QMetaObject *mo = hc.metaObject();
    int idx = mo->indexOfEnumerator("ServiceHealth");
    QVERIFY(idx >= 0);

    QMetaEnum me = mo->enumerator(idx);
    QCOMPARE(me.keyCount(), 4);  // Unknown, Healthy, Degraded, Down
}

void TestHealthCheck::testOverallHealthEnum()
{
    HealthCheck hc;
    const QMetaObject *mo = hc.metaObject();
    int idx = mo->indexOfEnumerator("OverallHealth");
    QVERIFY(idx >= 0);

    QMetaEnum me = mo->enumerator(idx);
    QCOMPARE(me.keyCount(), 4);  // Unknown, AllHealthy, Degraded, Critical
}

void TestHealthCheck::testHealthToString()
{
    // Tester via les accesseurs publics (état initial = unknown)
    HealthCheck hc;
    QCOMPARE(hc.serviceHealth("stt"),
             HealthCheck::ServiceHealth::Unknown);
    QCOMPARE(hc.overall(),
             HealthCheck::OverallHealth::Unknown);
    QCOMPARE(hc.latencyMs("stt"), -1);
}

void TestHealthCheck::testConfigureWithoutConfig()
{
    HealthCheck hc;
    // configure(nullptr) ne doit pas crasher
    hc.configure(nullptr);

    // Toujours unknown car aucun service ajouté
    QCOMPARE(hc.overallStatus(), QStringLiteral("unknown"));
}

void TestHealthCheck::testStartWithoutConfigure()
{
    HealthCheck hc;
    // start() sans configure() ne doit pas crasher — juste un warning
    hc.start(1000);
    hc.stop();
}

void TestHealthCheck::testStopResetsState()
{
    HealthCheck hc;
    ConfigManager cfg;
    cfg.loadConfiguration("nonexistent_config.conf");
    hc.configure(&cfg);

    // Après stop, tous les services doivent être unknown
    hc.stop();
    QCOMPARE(hc.sttStatus(), QStringLiteral("unknown"));
    QCOMPARE(hc.ttsStatus(), QStringLiteral("unknown"));
    QCOMPARE(hc.overallStatus(), QStringLiteral("unknown"));
}

void TestHealthCheck::testCheckNowEmitsSignal()
{
    HealthCheck hc;
    ConfigManager cfg;
    cfg.loadConfiguration("nonexistent_config.conf");
    hc.configure(&cfg);

    QSignalSpy spy(&hc, &HealthCheck::healthChanged);
    QVERIFY(spy.isValid());

    // checkNow() va envoyer des pings qui échoueront immédiatement
    // car aucun serveur n'est connecté → les signaux sont émis de façon synchrone
    hc.checkNow();

    // Laisser l'event loop traiter les signaux
    QCoreApplication::processEvents();

    // Au moins un signal healthChanged devrait avoir été émis (6 services → Down)
    QVERIFY(spy.count() >= 1);

    // Vérifier que tous les services sont "down"
    QCOMPARE(hc.sttStatus(), QStringLiteral("down"));
    QCOMPARE(hc.ttsStatus(), QStringLiteral("down"));
    QCOMPARE(hc.overallStatus(), QStringLiteral("critical"));
}

void TestHealthCheck::cleanupTestCase()
{
    qDebug() << "=== TestHealthCheck terminé ===";
}

QTEST_MAIN(TestHealthCheck)
#include "test_healthcheck.moc"
