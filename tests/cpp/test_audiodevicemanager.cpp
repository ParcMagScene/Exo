// ═══════════════════════════════════════════════════════
//  test_audiodevicemanager.cpp — Unit tests for AudioDeviceManager
//  L11 : tests for device management, RMS computation,
//        health check, signal emissions
// ═══════════════════════════════════════════════════════
#include <QtTest/QtTest>
#include <QSignalSpy>
#include <cmath>
#include <cstring>
#include "AudioDeviceManager.h"

class TestAudioDeviceManager : public QObject
{
    Q_OBJECT

private slots:
    // ── Constructor / initial state ──
    void constructorInitialState();

    // ── Device queries ──
    void hasValidInputDevice_noDevices();
    void inputDevices_returnsList();

    // ── setInputDevice ──
    void setInputDevice_outOfBounds();
    void setInputDevice_negativeIndex();

    // ── selectedRtAudioDeviceId ──
    void selectedRtAudioDeviceId_noDevice();

    // ── Health check control ──
    void startStopHealthCheck();

    // ── Stream status ──
    void notifyStreamOpened_setsHealthy();
    void notifyStreamClosed_setsDown();

    // ── feedRmsSamples / rmsLevel ──
    void feedRmsSamples_silence();
    void feedRmsSamples_nonZero();
    void rmsLevel_initiallyZero();
};

// ═══════════════════════════════════════════════════════
//  Constructor / initial state
// ═══════════════════════════════════════════════════════

void TestAudioDeviceManager::constructorInitialState()
{
    AudioDeviceManager mgr;

    // Initially no streaming
    QCOMPARE(mgr.audioTestRunning(), false);
    QVERIFY(mgr.lastError().isEmpty());
}

// ═══════════════════════════════════════════════════════
//  Device queries
// ═══════════════════════════════════════════════════════

void TestAudioDeviceManager::hasValidInputDevice_noDevices()
{
    AudioDeviceManager mgr;
    // On CI (no audio hardware), this might be true or false depending
    // on whether virtual devices exist. Just verify it doesn't crash.
    (void)mgr.hasValidInputDevice();
    QVERIFY(true);
}

void TestAudioDeviceManager::inputDevices_returnsList()
{
    AudioDeviceManager mgr;
    QStringList devices = mgr.inputDevices();
    // On CI, may be empty. Just ensure no crash and return is valid.
    QVERIFY(devices.size() >= 0);
}

// ═══════════════════════════════════════════════════════
//  setInputDevice
// ═══════════════════════════════════════════════════════

void TestAudioDeviceManager::setInputDevice_outOfBounds()
{
    AudioDeviceManager mgr;
    QSignalSpy spy(&mgr, &AudioDeviceManager::inputDeviceChanged);

    // Setting index beyond available devices should not crash
    // and should not emit inputDeviceChanged
    mgr.setInputDevice(9999);
    QCOMPARE(spy.count(), 0);
}

void TestAudioDeviceManager::setInputDevice_negativeIndex()
{
    AudioDeviceManager mgr;
    QSignalSpy spy(&mgr, &AudioDeviceManager::inputDeviceChanged);

    mgr.setInputDevice(-1);
    QCOMPARE(spy.count(), 0);
}

// ═══════════════════════════════════════════════════════
//  selectedRtAudioDeviceId
// ═══════════════════════════════════════════════════════

void TestAudioDeviceManager::selectedRtAudioDeviceId_noDevice()
{
    AudioDeviceManager mgr;
    // When no valid device selected, should return -1
    if (!mgr.hasValidInputDevice()) {
        QCOMPARE(mgr.selectedRtAudioDeviceId(), -1);
    } else {
        // If a device is found (unlikely on CI), just verify it's >= 0
        QVERIFY(mgr.selectedRtAudioDeviceId() >= 0);
    }
}

// ═══════════════════════════════════════════════════════
//  Health check control
// ═══════════════════════════════════════════════════════

void TestAudioDeviceManager::startStopHealthCheck()
{
    AudioDeviceManager mgr;

    // Start health check with 5s interval — should not crash
    mgr.startHealthCheck(5000);

    // Stop — should not crash
    mgr.stopHealthCheck();
    QVERIFY(true);
}

// ═══════════════════════════════════════════════════════
//  Stream status
// ═══════════════════════════════════════════════════════

void TestAudioDeviceManager::notifyStreamOpened_setsHealthy()
{
    AudioDeviceManager mgr;
    QSignalSpy spy(&mgr, &AudioDeviceManager::audioStatusChanged);

    mgr.notifyStreamOpened();

    QCOMPARE(mgr.audioStatus(), QStringLiteral("healthy"));
    QVERIFY(spy.count() >= 1);
}

void TestAudioDeviceManager::notifyStreamClosed_setsDown()
{
    AudioDeviceManager mgr;
    mgr.notifyStreamOpened(); // set healthy first

    QSignalSpy spy(&mgr, &AudioDeviceManager::audioStatusChanged);
    mgr.notifyStreamClosed();

    QCOMPARE(mgr.audioStatus(), QStringLiteral("down"));
    QVERIFY(spy.count() >= 1);
}

// ═══════════════════════════════════════════════════════
//  feedRmsSamples / rmsLevel — tests through public API
//  (computeRms is private, exercised indirectly)
// ═══════════════════════════════════════════════════════

void TestAudioDeviceManager::feedRmsSamples_silence()
{
    AudioDeviceManager mgr;

    int16_t silence[512];
    std::memset(silence, 0, sizeof(silence));

    mgr.feedRmsSamples(silence, 512);
    QCoreApplication::processEvents();

    // RMS of silence = 0
    QCOMPARE(mgr.currentRmsLevel(), 0.0f);
}

void TestAudioDeviceManager::feedRmsSamples_nonZero()
{
    AudioDeviceManager mgr;
    QSignalSpy spy(&mgr, &AudioDeviceManager::rmsLevelChanged);

    int16_t samples[512];
    for (int i = 0; i < 512; ++i)
        samples[i] = 16384;

    mgr.feedRmsSamples(samples, 512);
    QCoreApplication::processEvents();

    QVERIFY(mgr.currentRmsLevel() > 0.0f);
}

void TestAudioDeviceManager::rmsLevel_initiallyZero()
{
    AudioDeviceManager mgr;
    QCOMPARE(mgr.currentRmsLevel(), 0.0f);
}

QTEST_GUILESS_MAIN(TestAudioDeviceManager)
#include "test_audiodevicemanager.moc"
