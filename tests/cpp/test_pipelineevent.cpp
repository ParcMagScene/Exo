// ═══════════════════════════════════════════════════════
//  Test unitaire — PipelineEventBus + EventType
//  Vérifie : eventTypeToString round-trip, postEvent,
//            beginInteraction/endInteraction, moduleStatus
// ═══════════════════════════════════════════════════════
#include <QtTest/QtTest>
#include <QSignalSpy>
#include "PipelineEvent.h"
#include "PipelineTypes.h"

class TestPipelineEvent : public QObject
{
    Q_OBJECT

private slots:

    // ── eventTypeToString couvre tous les enum ────────
    void eventTypeToString_allValues()
    {
        // Vérifie que chaque enum produit une string non-vide et != "unknown"
        const EventType types[] = {
            EventType::SpeechStarted, EventType::SpeechEnded,
            EventType::WakeWordDetected,
            EventType::StreamStarted, EventType::PartialTranscript,
            EventType::FinalTranscript, EventType::UtteranceFinished,
            EventType::STTError,
            EventType::RequestStarted, EventType::FirstToken,
            EventType::PartialResponse, EventType::FinalResponse,
            EventType::SentenceReady, EventType::ReplyFinished,
            EventType::ToolCall, EventType::ToolCallDispatched,
            EventType::NetworkError, EventType::ResponseReceived,
            EventType::SynthesisRequested, EventType::SentenceQueued,
            EventType::SpeechCancelled, EventType::WorkerStarted,
            EventType::WorkerError, EventType::SpeechFinalized,
            EventType::SpeakRequested, EventType::SentenceEnqueued,
            EventType::PcmChunk, EventType::PlaybackStarted,
            EventType::PlaybackFinished, EventType::TTSError,
            EventType::TranscriptDispatched, EventType::SpeechTranscribed,
            EventType::StateChanged, EventType::OrphanInteractionClosed
        };

        for (auto t : types) {
            QString s = eventTypeToString(t);
            QVERIFY2(!s.isEmpty(), "eventTypeToString returned empty");
            QVERIFY2(s != "unknown",
                      qPrintable("eventTypeToString returned 'unknown' for enum " +
                                 QString::number(static_cast<int>(t))));
        }
    }

    // ── Vérification de certaines valeurs spécifiques ─
    void eventTypeToString_specificValues()
    {
        QCOMPARE(eventTypeToString(EventType::SpeechStarted), QString("speech_started"));
        QCOMPARE(eventTypeToString(EventType::FinalTranscript), QString("final_transcript"));
        QCOMPARE(eventTypeToString(EventType::FirstToken), QString("first_token"));
        QCOMPARE(eventTypeToString(EventType::SpeechFinalized), QString("speech_finalized"));
        QCOMPARE(eventTypeToString(EventType::OrphanInteractionClosed), QString("orphan_interaction_closed"));
    }

    // ── STTError et TTSError produisent "error" ──────
    void eventTypeToString_errorDuality()
    {
        QCOMPARE(eventTypeToString(EventType::STTError), QString("error"));
        QCOMPARE(eventTypeToString(EventType::TTSError), QString("error"));
    }

    // ── PipelineEvent::toJson ────────────────────────
    void pipelineEvent_toJson()
    {
        PipelineEvent evt;
        evt.timestamp     = "2026-03-21T10:00:00.000Z";
        evt.module        = PipelineModule::STT;
        evt.eventType     = EventType::FinalTranscript;
        evt.correlationId = "test-corr-id";
        evt.payload       = {{"text", "bonjour"}};
        evt.elapsedMs     = 1234;

        QJsonObject json = evt.toJson();
        QCOMPARE(json["module"].toString(), PipelineEvent::moduleToString(PipelineModule::STT));
        QCOMPARE(json["event_type"].toString(), QString("final_transcript"));
        QCOMPARE(json["correlation_id"].toString(), QString("test-corr-id"));
        QCOMPARE(json["elapsed_ms"].toInt(), 1234);
        QVERIFY(json.contains("payload"));
        QCOMPARE(json["payload"].toObject()["text"].toString(), QString("bonjour"));
    }

    // ── PipelineEvent::moduleToString ────────────────
    void moduleToString_allValues()
    {
        // Vérifie que chaque module retourne une string non-vide
        QVERIFY(!PipelineEvent::moduleToString(PipelineModule::STT).isEmpty());
        QVERIFY(!PipelineEvent::moduleToString(PipelineModule::TTS).isEmpty());
        QVERIFY(!PipelineEvent::moduleToString(PipelineModule::Claude).isEmpty());
        QVERIFY(!PipelineEvent::moduleToString(PipelineModule::VAD).isEmpty());
        QVERIFY(!PipelineEvent::moduleToString(PipelineModule::AudioCapture).isEmpty());
        QVERIFY(!PipelineEvent::moduleToString(PipelineModule::Orchestrator).isEmpty());
    }

    // ── PipelineEvent::stateToString ─────────────────
    void stateToString_allValues()
    {
        QCOMPARE(PipelineEvent::stateToString(ModuleState::Idle), QString("idle"));
        QCOMPARE(PipelineEvent::stateToString(ModuleState::Active), QString("active"));
        QCOMPARE(PipelineEvent::stateToString(ModuleState::Processing), QString("processing"));
        QCOMPARE(PipelineEvent::stateToString(ModuleState::Error), QString("error"));
        QCOMPARE(PipelineEvent::stateToString(ModuleState::Unavailable), QString("unavailable"));
    }

    // ── Singleton : beginInteraction/endInteraction ──
    void interaction_lifecycle()
    {
        auto *bus = PipelineEventBus::instance();
        QVERIFY(bus != nullptr);

        QSignalSpy startSpy(bus, &PipelineEventBus::interactionStarted);
        QSignalSpy endSpy(bus, &PipelineEventBus::interactionEnded);

        QString corrId = bus->beginInteraction();
        QVERIFY(!corrId.isEmpty());
        QCOMPARE(bus->currentCorrelationId(), corrId);
        QCOMPARE(startSpy.count(), 1);

        bus->endInteraction(corrId);
        QCOMPARE(endSpy.count(), 1);
    }

    // ── postEvent émet eventEmitted ──────────────────
    void postEvent_emitsSignal()
    {
        auto *bus = PipelineEventBus::instance();
        QSignalSpy spy(bus, &PipelineEventBus::eventEmitted);

        bus->postEvent(PipelineModule::STT, EventType::FinalTranscript,
                       {{"text", "test"}});

        QVERIFY(spy.count() >= 1);
        QJsonObject emitted = spy.last().at(0).toJsonObject();
        QCOMPARE(emitted["event_type"].toString(), QString("final_transcript"));
    }

    // ── setModuleState + moduleStatus ────────────────
    void moduleState_roundTrip()
    {
        auto *bus = PipelineEventBus::instance();

        bus->setModuleState(PipelineModule::TTS, ModuleState::Processing);
        ModuleStatus status = bus->moduleStatus(PipelineModule::TTS);
        QCOMPARE(status.state, ModuleState::Processing);

        bus->setModuleState(PipelineModule::TTS, ModuleState::Idle);
        status = bus->moduleStatus(PipelineModule::TTS);
        QCOMPARE(status.state, ModuleState::Idle);
    }

    // ── setModuleError ───────────────────────────────
    void moduleError_setsState()
    {
        auto *bus = PipelineEventBus::instance();

        bus->setModuleError(PipelineModule::Claude, "timeout");
        ModuleStatus status = bus->moduleStatus(PipelineModule::Claude);
        QCOMPARE(status.state, ModuleState::Error);
        QCOMPARE(status.lastError, QString("timeout"));
    }

    // ── allModuleStatuses retourne un objet valide ───
    void allModuleStatuses_valid()
    {
        auto *bus = PipelineEventBus::instance();
        bus->setModuleState(PipelineModule::STT, ModuleState::Active);

        QJsonObject all = bus->allModuleStatuses();
        QVERIFY(!all.isEmpty());
        // La clé est le résultat de moduleToString (lowercase)
        QString sttKey = PipelineEvent::moduleToString(PipelineModule::STT);
        QVERIFY2(all.contains(sttKey),
                 qPrintable("Missing key: " + sttKey));
    }

    // ── getPipelineSnapshot ──────────────────────────
    void pipelineSnapshot_valid()
    {
        auto *bus = PipelineEventBus::instance();
        QJsonObject snap = bus->getPipelineSnapshot();
        // Vérifier que le snapshot est un objet JSON non-vide
        QVERIFY(!snap.isEmpty());
    }
};

QTEST_GUILESS_MAIN(TestPipelineEvent)
#include "test_pipelineevent.moc"
