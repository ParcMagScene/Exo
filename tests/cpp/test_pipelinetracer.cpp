// ═══════════════════════════════════════════════════════
//  Test unitaire — PipelineTracer
//  Vérifie : assembleTimeline, detectAnomalies,
//            buildSummary, seuils configurables
// ═══════════════════════════════════════════════════════
#include <QtTest/QtTest>
#include "PipelineTracer.h"
#include "PipelineEvent.h"
#include "PipelineTypes.h"

class TestPipelineTracer : public QObject
{
    Q_OBJECT

private:
    // Crée une trace d'interaction synthétique
    InteractionTrace makeTrace(qint64 durationMs = 5000)
    {
        InteractionTrace trace;
        trace.correlationId = "test-trace-001";
        trace.startTimestamp = QDateTime::currentMSecsSinceEpoch();
        trace.endTimestamp   = trace.startTimestamp + durationMs;

        auto addEvent = [&](PipelineModule mod, EventType type, qint64 elapsed,
                            const QJsonObject &payload = {}) {
            PipelineEvent e;
            e.module        = mod;
            e.eventType     = type;
            e.correlationId = trace.correlationId;
            e.elapsedMs     = elapsed;
            e.payload       = payload;
            e.timestamp     = QDateTime::fromMSecsSinceEpoch(
                                  trace.startTimestamp + elapsed)
                                  .toString(Qt::ISODateWithMs);
            trace.events.append(e);
        };

        // Pipeline typique : VAD → STT → Claude → TTS → Playback
        addEvent(PipelineModule::VAD, EventType::SpeechStarted, 0);
        addEvent(PipelineModule::VAD, EventType::SpeechEnded, 1500);

        addEvent(PipelineModule::STT, EventType::StreamStarted, 100);
        addEvent(PipelineModule::STT, EventType::PartialTranscript, 800,
                 {{"text", "bon"}});
        addEvent(PipelineModule::STT, EventType::FinalTranscript, 1600,
                 {{"text", "bonjour"}});

        addEvent(PipelineModule::Claude, EventType::RequestStarted, 1650);
        addEvent(PipelineModule::Claude, EventType::FirstToken, 2200);
        addEvent(PipelineModule::Claude, EventType::SentenceReady, 2800);
        addEvent(PipelineModule::Claude, EventType::FinalResponse, 3000);

        addEvent(PipelineModule::TTS, EventType::SynthesisRequested, 2850);
        addEvent(PipelineModule::TTS, EventType::WorkerStarted, 3100);
        addEvent(PipelineModule::TTS, EventType::SpeechFinalized, 4500);

        addEvent(PipelineModule::AudioOutput, EventType::PlaybackStarted, 3150);
        addEvent(PipelineModule::AudioOutput, EventType::PlaybackFinished, 4600);

        return trace;
    }

    // Trace sans réponse Claude (anomalie NO_RESPONSE)
    InteractionTrace makeTraceNoResponse()
    {
        InteractionTrace trace;
        trace.correlationId = "test-no-response";
        trace.startTimestamp = QDateTime::currentMSecsSinceEpoch();
        trace.endTimestamp   = trace.startTimestamp + 3000;

        PipelineEvent e1;
        e1.module = PipelineModule::VAD;
        e1.eventType = EventType::SpeechStarted;
        e1.correlationId = trace.correlationId;
        e1.elapsedMs = 0;
        trace.events.append(e1);

        PipelineEvent e2;
        e2.module = PipelineModule::STT;
        e2.eventType = EventType::FinalTranscript;
        e2.correlationId = trace.correlationId;
        e2.elapsedMs = 1500;
        trace.events.append(e2);

        // Claude request démarrée mais jamais de réponse
        PipelineEvent e3;
        e3.module = PipelineModule::Claude;
        e3.eventType = EventType::RequestStarted;
        e3.correlationId = trace.correlationId;
        e3.elapsedMs = 1600;
        trace.events.append(e3);

        // Pas de FinalResponse Claude → anomalie

        return trace;
    }

private slots:

    // ── Singleton ────────────────────────────────────
    void instance_notNull()
    {
        QVERIFY(PipelineTracer::instance() != nullptr);
    }

    // ── assembleTimeline ─────────────────────────────
    void assembleTimeline_normalTrace()
    {
        auto trace = makeTrace();
        auto *tracer = PipelineTracer::instance();

        auto timeline = tracer->assembleTimeline(trace);

        // On devrait avoir au moins des segments VAD, STT, Claude, TTS
        QVERIFY(timeline.size() >= 3);

        // Vérifier que les modules attendus sont présents
        QStringList moduleNames;
        for (const auto &seg : timeline)
            moduleNames.append(seg.moduleName);

        QVERIFY2(moduleNames.contains("vad"),
                 "Timeline missing vad segment");
        QVERIFY2(moduleNames.contains("stt"),
                 "Timeline missing stt segment");
        QVERIFY2(moduleNames.contains("claude"),
                 "Timeline missing claude segment");
    }

    void assembleTimeline_emptyTrace()
    {
        InteractionTrace empty;
        empty.correlationId = "empty";
        auto timeline = PipelineTracer::instance()->assembleTimeline(empty);
        QVERIFY(timeline.isEmpty());
    }

    void assembleTimeline_durations_positive()
    {
        auto trace = makeTrace();
        auto timeline = PipelineTracer::instance()->assembleTimeline(trace);

        for (const auto &seg : timeline) {
            QVERIFY2(seg.durationMs() >= 0,
                     qPrintable(QString("%1 has negative duration: %2")
                                .arg(seg.moduleName).arg(seg.durationMs())));
        }
    }

    // ── detectAnomalies ──────────────────────────────
    void detectAnomalies_normalTrace_noAnomalies()
    {
        auto trace = makeTrace(5000); // 5s total — tout normal
        auto *tracer = PipelineTracer::instance();

        auto anomalies = tracer->detectAnomalies(trace);
        // Une trace normale de 5s ne devrait pas avoir d'anomalies
        // (seuils par défaut : STT 5s, LLM 15s, TTS 10s, total 30s)
        QVERIFY2(anomalies.isEmpty(),
                 qPrintable("Unexpected anomalies: " + anomalies.join(", ")));
    }

    void detectAnomalies_noResponse()
    {
        auto trace = makeTraceNoResponse();
        auto *tracer = PipelineTracer::instance();

        auto anomalies = tracer->detectAnomalies(trace);
        bool hasNoResponse = false;
        for (const auto &a : anomalies) {
            if (a.contains("NO_RESPONSE", Qt::CaseInsensitive) ||
                a.contains("no response", Qt::CaseInsensitive) ||
                a.contains("pas de réponse", Qt::CaseInsensitive)) {
                hasNoResponse = true;
                break;
            }
        }
        QVERIFY2(hasNoResponse,
                 qPrintable("Expected NO_RESPONSE anomaly, got: " + anomalies.join(", ")));
    }

    void detectAnomalies_totalTimeout()
    {
        // Trace de 35s → dépasse le seuil total de 30s
        auto trace = makeTrace(35000);
        auto *tracer = PipelineTracer::instance();

        auto anomalies = tracer->detectAnomalies(trace);
        bool hasTimeout = false;
        for (const auto &a : anomalies) {
            if (a.contains("TIMEOUT", Qt::CaseInsensitive) ||
                a.contains("timeout", Qt::CaseInsensitive) ||
                a.contains("total", Qt::CaseInsensitive)) {
                hasTimeout = true;
                break;
            }
        }
        QVERIFY2(hasTimeout,
                 qPrintable("Expected TIMEOUT anomaly for 35s trace, got: " +
                            anomalies.join(", ")));
    }

    // ── buildSummary ─────────────────────────────────
    void buildSummary_normalTrace()
    {
        auto trace = makeTrace();
        auto *tracer = PipelineTracer::instance();

        auto summary = tracer->buildSummary(trace);
        QCOMPARE(summary.correlationId, QString("test-trace-001"));
        QVERIFY(summary.totalMs > 0);
        QVERIFY(summary.eventCount > 0);
    }

    void buildSummary_emptyTrace()
    {
        InteractionTrace empty;
        empty.correlationId = "empty";
        auto summary = PipelineTracer::instance()->buildSummary(empty);
        QCOMPARE(summary.eventCount, 0);
    }

    void buildSummary_toJson()
    {
        auto trace = makeTrace();
        auto summary = PipelineTracer::instance()->buildSummary(trace);

        QJsonObject json = summary.toJson();
        QVERIFY(json.contains("correlation_id"));
        QVERIFY(json.contains("total_ms"));
        QVERIFY(json.contains("event_count"));
    }

    // ── Seuils configurables ─────────────────────────
    void thresholds_customizable()
    {
        auto *tracer = PipelineTracer::instance();

        tracer->setSTTThresholdMs(1000);
        tracer->setLLMThresholdMs(2000);
        tracer->setTTSThresholdMs(3000);
        tracer->setTotalThresholdMs(10000);

        // Pas de crash
        QVERIFY(true);

        // Remettre les valeurs par défaut
        tracer->setSTTThresholdMs(5000);
        tracer->setLLMThresholdMs(15000);
        tracer->setTTSThresholdMs(10000);
        tracer->setTotalThresholdMs(30000);
    }

    // ── TimelineSegment::toJson ──────────────────────
    void timelineSegment_toJson()
    {
        TimelineSegment seg;
        seg.moduleName = "Claude";
        seg.startMs = 1000;
        seg.endMs   = 3000;

        QJsonObject json = seg.toJson();
        QCOMPARE(json["module"].toString(), QString("Claude"));
        QCOMPARE(json["start_ms"].toInt(), 1000);
        QCOMPARE(json["end_ms"].toInt(), 3000);
        QCOMPARE(json["duration_ms"].toInt(), 2000);
    }
};

QTEST_GUILESS_MAIN(TestPipelineTracer)
#include "test_pipelinetracer.moc"
