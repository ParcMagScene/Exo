// ═══════════════════════════════════════════════════════
//  Test unitaire — TTS DSP chain
//  Vérifie : TTSEqualizer, TTSCompressor, TTSNormalizer,
//            TTSDSPProcessor (chaîne complète)
// ═══════════════════════════════════════════════════════
#include <QtTest/QtTest>
#include "TTSManager.h"
#include <vector>
#include <cmath>

class TestTTSDsp : public QObject
{
    Q_OBJECT

private:
    // Génère un sinus float -1..+1
    static std::vector<float> sineFloat(int count, float freq, int sr, float amp = 1.0f)
    {
        std::vector<float> buf(count);
        for (int i = 0; i < count; ++i)
            buf[i] = amp * std::sin(2.0f * float(M_PI) * freq * float(i) / float(sr));
        return buf;
    }

    // Génère un sinus int16
    static std::vector<int16_t> sineInt16(int count, float freq, int sr, float amp)
    {
        std::vector<int16_t> buf(count);
        for (int i = 0; i < count; ++i)
            buf[i] = int16_t(amp * std::sin(2.0f * float(M_PI) * freq * float(i) / float(sr)));
        return buf;
    }

    // RMS float
    static double rmsF(const float *buf, int count)
    {
        double sum = 0;
        for (int i = 0; i < count; ++i) sum += double(buf[i]) * double(buf[i]);
        return std::sqrt(sum / count);
    }

    // RMS int16
    static double rmsI16(const int16_t *buf, int count)
    {
        double sum = 0;
        for (int i = 0; i < count; ++i) sum += double(buf[i]) * double(buf[i]);
        return std::sqrt(sum / count);
    }

    // Peak float
    static float peakF(const float *buf, int count)
    {
        float mx = 0;
        for (int i = 0; i < count; ++i) mx = std::max(mx, std::abs(buf[i]));
        return mx;
    }

private slots:

    // ══════════════════════════════════════════════════
    //  TTSEqualizer
    // ══════════════════════════════════════════════════

    void equalizer_boostsPresenceBand()
    {
        TTSEqualizer eq;
        eq.configure(24000, 3000.0f, 6.0f, 1.0f); // +6 dB boost

        // Sinus à 3000 Hz (bande de présence)
        auto buf = sineFloat(8000, 3000.0f, 24000, 0.3f);
        double rmsBefore = rmsF(buf.data(), buf.size());

        eq.process(buf.data(), buf.size());
        double rmsAfter = rmsF(buf.data(), buf.size());

        // Le boost devrait augmenter le RMS
        QVERIFY2(rmsAfter > rmsBefore,
                 qPrintable(QString("EQ did not boost: before=%1 after=%2")
                            .arg(rmsBefore).arg(rmsAfter)));
    }

    void equalizer_reset()
    {
        TTSEqualizer eq;
        eq.configure(24000, 3000.0f, 3.0f, 1.0f);

        auto buf = sineFloat(4000, 3000.0f, 24000, 0.5f);
        eq.process(buf.data(), buf.size());

        eq.reset();
        // Après reset, retraiter ne doit pas crasher
        auto buf2 = sineFloat(4000, 3000.0f, 24000, 0.5f);
        eq.process(buf2.data(), buf2.size());
        QVERIFY(true);
    }

    // ══════════════════════════════════════════════════
    //  TTSCompressor
    // ══════════════════════════════════════════════════

    void compressor_reducesLoudSignal()
    {
        TTSCompressor comp;
        comp.configure(24000, -18.0f, 4.0f, 1.0f, 20.0f);

        // Signal fort (-6 dBFS ~= 0.5 amplitude)
        auto buf = sineFloat(8000, 1000.0f, 24000, 0.5f);
        double rmsBefore = rmsF(buf.data(), buf.size());

        comp.process(buf.data(), buf.size());
        double rmsAfter = rmsF(buf.data(), buf.size());

        // Le compresseur devrait réduire le niveau
        QVERIFY2(rmsAfter < rmsBefore,
                 qPrintable(QString("Compressor did not compress: before=%1 after=%2")
                            .arg(rmsBefore).arg(rmsAfter)));
    }

    void compressor_passesQuietSignal()
    {
        TTSCompressor comp;
        comp.configure(24000, -18.0f, 4.0f, 5.0f, 50.0f);

        // Signal faible (-30 dBFS ~= 0.03 amplitude) — sous le threshold
        auto buf = sineFloat(8000, 1000.0f, 24000, 0.03f);
        double rmsBefore = rmsF(buf.data(), buf.size());

        comp.process(buf.data(), buf.size());
        double rmsAfter = rmsF(buf.data(), buf.size());

        // Signal sous le seuil ne devrait pas être compressé significativement
        double ratio = rmsAfter / rmsBefore;
        QVERIFY2(ratio > 0.8,
                 qPrintable(QString("Compressor attenuated quiet signal: ratio=%1").arg(ratio)));
    }

    // ══════════════════════════════════════════════════
    //  TTSNormalizer
    // ══════════════════════════════════════════════════

    void normalizer_reachesTarget()
    {
        TTSNormalizer norm;
        norm.setTargetDb(-14.0f);

        // Signal bas (~-30 dBFS)
        auto buf = sineFloat(8000, 1000.0f, 24000, 0.03f);

        norm.process(buf.data(), buf.size());
        float peak = peakF(buf.data(), buf.size());

        // Target -14 dBFS ≈ 0.2 amplitude peak. Tolérance large.
        QVERIFY2(peak > 0.05f && peak < 1.0f,
                 qPrintable(QString("Normalizer peak unexpected: %1").arg(peak)));
    }

    void normalizer_doesNotClip()
    {
        TTSNormalizer norm;
        norm.setTargetDb(-14.0f);

        auto buf = sineFloat(8000, 1000.0f, 24000, 0.8f);
        norm.process(buf.data(), buf.size());

        float peak = peakF(buf.data(), buf.size());
        QVERIFY2(peak <= 1.01f, // petite tolérance numérique
                 qPrintable(QString("Normalizer clipped: peak=%1").arg(peak)));
    }

    // ══════════════════════════════════════════════════
    //  TTSDSPProcessor (chaîne complète)
    // ══════════════════════════════════════════════════

    void dspChain_processesWithoutCrash()
    {
        TTSDSPProcessor dsp;
        dsp.configure(24000);
        dsp.setEnabled(true);

        auto buf = sineInt16(4800, 1000.0f, 24000, 8000.0f);
        dsp.process(buf.data(), buf.size(), false);
        QVERIFY(true);

        // Final chunk
        auto buf2 = sineInt16(4800, 1000.0f, 24000, 8000.0f);
        dsp.process(buf2.data(), buf2.size(), true);
        QVERIFY(true);
    }

    void dspChain_disabled_passthrough()
    {
        TTSDSPProcessor dsp;
        dsp.configure(24000);
        dsp.setEnabled(false);

        auto buf = sineInt16(4800, 1000.0f, 24000, 8000.0f);
        auto original = buf; // copie

        dsp.process(buf.data(), buf.size(), false);

        // Quand désactivé, le buffer devrait être identique
        QCOMPARE(buf, original);
    }

    void dspChain_reset()
    {
        TTSDSPProcessor dsp;
        dsp.configure(24000);
        dsp.setEnabled(true);

        auto buf = sineInt16(4800, 1000.0f, 24000, 8000.0f);
        dsp.process(buf.data(), buf.size(), false);

        dsp.reset();

        auto buf2 = sineInt16(4800, 1000.0f, 24000, 8000.0f);
        dsp.process(buf2.data(), buf2.size(), false);
        QVERIFY(true);
    }
};

QTEST_GUILESS_MAIN(TestTTSDsp)
#include "test_tts_dsp.moc"
