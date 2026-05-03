#pragma once

#include <QObject>
#include <QTimer>
#include <QVariantMap>
#include <QVariantList>
#include <QMap>
#include <QElapsedTimer>
#include <QJsonObject>
#include <QJsonDocument>
#include <QJsonArray>
#include <QQmlEngine>
#include "WebSocketClient.h"

// ═══════════════════════════════════════════════════════
//  TestController — Stability tests exposed to QML
//
//  Connects to each microservice independently, sends
//  application-level pings, measures latency, detects
//  timeouts and flapping, runs auto-loop until stable.
//
//  Non-intrusive: does NOT touch the voice pipeline at all.
// ═══════════════════════════════════════════════════════

class ConfigManager;

class TestController : public QObject
{
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(QVariantList serviceResults READ serviceResults NOTIFY resultsChanged)
    Q_PROPERTY(QString      overallStatus  READ overallStatus  NOTIFY resultsChanged)
    Q_PROPERTY(bool         running        READ running        NOTIFY runningChanged)
    Q_PROPERTY(int          loopCount      READ loopCount      NOTIFY resultsChanged)
    Q_PROPERTY(QVariantList errorLog       READ errorLog       NOTIFY resultsChanged)

public:
    explicit TestController(QObject *parent = nullptr);
    ~TestController() override;

    void configure(ConfigManager *config);

    // ── QML API ──
    Q_INVOKABLE QVariantMap runPing(const QString &target);
    Q_INVOKABLE void        runAllPings();
    Q_INVOKABLE QVariantMap getPipelineState();
    Q_INVOKABLE QVariantList getErrors();
    Q_INVOKABLE void        startAutoTestLoop();
    Q_INVOKABLE void        stopAutoTestLoop();

    // ── Property accessors ──
    QVariantList serviceResults() const;
    QString      overallStatus()  const;
    bool         running()        const;
    int          loopCount()      const;
    QVariantList errorLog()       const;

signals:
    void resultsChanged();
    void runningChanged();
    void testComplete(bool allGreen);
    void loopFinished(int loopNum, bool allGreen);

private slots:
    void onAutoLoopTick();

private:
    // Per-service test state
    struct ServiceTest {
        QString              name;
        QUrl                 url;
        WebSocketClient     *client   = nullptr;
        bool                 pingPending = false;
        QElapsedTimer        timer;
        QString              status;     // "unknown","ok","timeout","down","flapping"
        double               latencyMs  = -1;
        QString              error;
        // Flap tracking
        QList<QPair<qint64, QString>> history;
    };

    void setupService(const QString &name, const QUrl &url);
    void sendTestPing(const QString &name);
    void onConnected(const QString &name);
    void onDisconnected(const QString &name);
    void onMessage(const QString &name, const QString &msg);
    void checkTimeouts();
    void evaluateResults();
    bool isFlapping(ServiceTest &svc) const;

    QMap<QString, ServiceTest>  m_services;
    QTimer                      m_autoTimer;
    QTimer                      m_timeoutTimer;
    bool                        m_running     = false;
    int                         m_loopCount   = 0;
    int                         m_pendingCount = 0;
    int                         m_timeoutMs   = 5000;
    QStringList                 m_errorLog;

    static constexpr int FLAP_WINDOW_S   = 30;
    static constexpr int FLAP_THRESHOLD  = 3;
    static constexpr int AUTO_LOOP_MS    = 5000;
};
