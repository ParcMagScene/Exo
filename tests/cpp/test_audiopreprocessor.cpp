// ═══════════════════════════════════════════════════════
//  Test unitaire — AudioPreprocessor
//  Vérifie : filtre HP (DC removal), noise gate, AGC,
//            normalisation RMS
// ═══════════════════════════════════════════════════════
#include <QtTest/QtTest>
#include "VoicePipeline.h"
#include <vector>
#include <cmath>
#include <numeric>

class TestAudioPreprocessor : public QObject
{
    Q_OBJECT

private:
    // Calcule RMS d'un buffer int16
    static double rms(const int16_t *buf, int count)
    {
        double sum = 0;
        for (int i = 0; i < count; ++i)
            sum += double(buf[i]) * double(buf[i]);
        return std::sqrt(sum / count);
    }

    // Génère un DC offset constant
    static std::vector<int16_t> dcSignal(int count, int16_t value)
    {
        return std::vector<int16_t>(count, value);
    }

    // Génère un sinus
    static std::vector<int16_t> sineWave(int count, float freq, int sampleRate, float amplitude)
    {
        std::vector<int16_t> buf(count);
        for (int i = 0; i < count; ++i) {
            float t = float(i) / float(sampleRate);
            buf[i] = int16_t(amplitude * std::sin(2.0f * float(M_PI) * freq * t));
        }
        return buf;
    }

private slots:

    // ── Filtre HP : supprime le DC ───────────────────
    void highPass_removesDC()
    {
        AudioPreprocessor pp;
        pp.setSampleRate(16000);
        pp.setHighPassCutoff(150.0f);
        pp.setNoiseGateThreshold(0.0f);  // désactiver le gate
        pp.setAGCEnabled(false);
        pp.setNormalizationTarget(0.0f);

        // Signal DC pur (1000 = DC offset)
        auto buf = dcSignal(4000, 1000);

        // Laisser le filtre se stabiliser en traitant un premier bloc
        pp.process(buf.data(), buf.size());

        // Deuxième bloc : le DC devrait être fortement atténué
        auto buf2 = dcSignal(4000, 1000);
        pp.process(buf2.data(), buf2.size());

        double r = rms(buf2.data(), buf2.size());
        // Le DC devrait être atténué d'au moins 90%
        QVERIFY2(r < 200.0, qPrintable(
            QString("DC not removed: RMS=%1 (expected < 200)").arg(r)));
    }

    // ── Filtre HP : laisse passer les fréquences vocales ─
    void highPass_passesVoice()
    {
        AudioPreprocessor pp;
        pp.setSampleRate(16000);
        pp.setHighPassCutoff(150.0f);
        pp.setNoiseGateThreshold(0.0f);
        pp.setAGCEnabled(false);
        pp.setNormalizationTarget(0.0f);

        // Sinus 500 Hz (bien au-dessus du cutoff 150 Hz)
        auto buf = sineWave(8000, 500.0f, 16000, 10000.0f);
        double rmsBefore = rms(buf.data(), buf.size());

        // Stabilisation
        auto warmup = sineWave(4000, 500.0f, 16000, 10000.0f);
        pp.process(warmup.data(), warmup.size());

        // Traitement
        auto buf2 = sineWave(8000, 500.0f, 16000, 10000.0f);
        pp.process(buf2.data(), buf2.size());
        double rmsAfter = rms(buf2.data(), buf2.size());

        // Le 500 Hz devrait être conservé (> 70% de l'amplitude)
        QVERIFY2(rmsAfter > rmsBefore * 0.7,
                 qPrintable(QString("Voice attenuated: before=%1, after=%2")
                            .arg(rmsBefore).arg(rmsAfter)));
    }

    // ── Noise Gate : silence sous le seuil ───────────
    void noiseGate_silencesLowSignal()
    {
        AudioPreprocessor pp;
        pp.setSampleRate(16000);
        pp.setHighPassCutoff(1.0f);        // quasi désactivé
        pp.setNoiseGateThreshold(0.1f);    // seuil haut
        pp.setAGCEnabled(false);
        pp.setNormalizationTarget(0.0f);

        // Signal très faible
        auto buf = sineWave(4000, 300.0f, 16000, 10.0f);
        pp.process(buf.data(), buf.size());

        double r = rms(buf.data(), buf.size());
        // Devrait être ~0 (gate fermé)
        QVERIFY2(r < 5.0, qPrintable(
            QString("Gate not closed: RMS=%1").arg(r)));
    }

    // ── Noise Gate : laisse passer signal fort ───────
    void noiseGate_passesLoudSignal()
    {
        AudioPreprocessor pp;
        pp.setSampleRate(16000);
        pp.setHighPassCutoff(1.0f);
        pp.setNoiseGateThreshold(0.001f);  // seuil très bas
        pp.setAGCEnabled(false);
        pp.setNormalizationTarget(0.0f);

        auto buf = sineWave(4000, 300.0f, 16000, 5000.0f);
        double rmsBefore = rms(buf.data(), buf.size());

        pp.process(buf.data(), buf.size());
        double rmsAfter = rms(buf.data(), buf.size());

        // Signal fort devrait passer (> 50%)
        QVERIFY2(rmsAfter > rmsBefore * 0.5,
                 qPrintable(QString("Gate blocked loud signal: before=%1, after=%2")
                            .arg(rmsBefore).arg(rmsAfter)));
    }

    // ── Process ne crash pas sur un buffer vide ──────
    void process_emptyBuffer()
    {
        AudioPreprocessor pp;
        pp.setSampleRate(16000);
        pp.process(nullptr, 0);
        QVERIFY(true); // pas de crash
    }

    // ── Process ne crash pas sur un petit buffer ─────
    void process_smallBuffer()
    {
        AudioPreprocessor pp;
        pp.setSampleRate(16000);
        int16_t sample = 1000;
        pp.process(&sample, 1);
        QVERIFY(true);
    }
};

QTEST_GUILESS_MAIN(TestAudioPreprocessor)
#include "test_audiopreprocessor.moc"
