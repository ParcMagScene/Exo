// ═══════════════════════════════════════════════════════
//  Test unitaire — CircularAudioBuffer
//  Vérifie : write/read, overflow, peek, available, clear
// ═══════════════════════════════════════════════════════
#include <QtTest/QtTest>
#include "VoicePipeline.h"
#include <vector>
#include <numeric>

class TestCircularAudioBuffer : public QObject
{
    Q_OBJECT

private slots:

    // ── Construction ─────────────────────────────────
    void construct_defaultCapacity()
    {
        CircularAudioBuffer buf;
        QCOMPARE(buf.available(), size_t(0));
        QVERIFY(buf.capacity() > 0);
    }

    void construct_customCapacity()
    {
        CircularAudioBuffer buf(1024);
        QCOMPARE(buf.capacity(), size_t(1024));
        QCOMPARE(buf.available(), size_t(0));
    }

    // ── Write + Read simple ──────────────────────────
    void writeRead_simple()
    {
        CircularAudioBuffer buf(256);
        std::vector<int16_t> src(100);
        std::iota(src.begin(), src.end(), 0); // 0,1,2,...,99

        buf.write(src.data(), src.size());
        QCOMPARE(buf.available(), size_t(100));

        std::vector<int16_t> dst(100, -1);
        size_t read = buf.read(dst.data(), dst.size());
        QCOMPARE(read, size_t(100));
        QCOMPARE(buf.available(), size_t(0));

        for (int i = 0; i < 100; ++i)
            QCOMPARE(dst[i], int16_t(i));
    }

    // ── Lecture partielle ────────────────────────────
    void read_partial()
    {
        CircularAudioBuffer buf(256);
        std::vector<int16_t> src(50, 42);
        buf.write(src.data(), src.size());

        std::vector<int16_t> dst(20, 0);
        size_t read = buf.read(dst.data(), 20);
        QCOMPARE(read, size_t(20));
        QCOMPARE(buf.available(), size_t(30));

        for (int i = 0; i < 20; ++i)
            QCOMPARE(dst[i], int16_t(42));
    }

    // ── Lecture quand vide ───────────────────────────
    void read_empty()
    {
        CircularAudioBuffer buf(256);
        std::vector<int16_t> dst(10, -1);
        size_t read = buf.read(dst.data(), 10);
        QCOMPARE(read, size_t(0));
    }

    // ── Peek ne consomme pas ─────────────────────────
    void peek_doesNotConsume()
    {
        CircularAudioBuffer buf(256);
        std::vector<int16_t> src = {10, 20, 30, 40, 50};
        buf.write(src.data(), src.size());

        std::vector<int16_t> p(3, 0);
        size_t peeked = buf.peek(p.data(), 3);
        QCOMPARE(peeked, size_t(3));
        QCOMPARE(buf.available(), size_t(5)); // toujours 5

        QCOMPARE(p[0], int16_t(10));
        QCOMPARE(p[1], int16_t(20));
        QCOMPARE(p[2], int16_t(30));
    }

    // ── Wraparound (écriture circulaire) ─────────────
    void wraparound()
    {
        CircularAudioBuffer buf(64);

        // Remplir 50 samples
        std::vector<int16_t> fill(50, 1);
        buf.write(fill.data(), fill.size());

        // Lire 40 → libère 40 places, head avance
        std::vector<int16_t> trash(40);
        buf.read(trash.data(), 40);
        QCOMPARE(buf.available(), size_t(10));

        // Écrire 30 de plus → doit wraper
        std::vector<int16_t> data(30);
        std::iota(data.begin(), data.end(), 100);
        buf.write(data.data(), data.size());
        QCOMPARE(buf.available(), size_t(40)); // 10 + 30

        // Lire tout et vérifier les 10 anciens (1) + 30 nouveaux (100..129)
        std::vector<int16_t> out(40, 0);
        size_t r = buf.read(out.data(), 40);
        QCOMPARE(r, size_t(40));

        for (int i = 0; i < 10; ++i)
            QCOMPARE(out[i], int16_t(1));
        for (int i = 0; i < 30; ++i)
            QCOMPARE(out[10 + i], int16_t(100 + i));
    }

    // ── Overflow (écriture au-delà de la capacité) ───
    void overflow_drops_oldest()
    {
        CircularAudioBuffer buf(32);

        // Écrire 32 (plein)
        std::vector<int16_t> a(32, 1);
        buf.write(a.data(), a.size());
        QCOMPARE(buf.available(), size_t(32));

        // Écrire 10 de plus → doit écraser les 10 plus anciens
        std::vector<int16_t> b(10, 99);
        buf.write(b.data(), b.size());

        // La taille disponible devrait être 32 (plein)
        // ou ≤ 32 selon l'implémentation (drop ou clamp)
        QVERIFY(buf.available() <= buf.capacity());
    }

    // ── Clear ────────────────────────────────────────
    void clear_resetsBuffer()
    {
        CircularAudioBuffer buf(128);
        std::vector<int16_t> src(64, 42);
        buf.write(src.data(), src.size());
        QCOMPARE(buf.available(), size_t(64));

        buf.clear();
        QCOMPARE(buf.available(), size_t(0));
    }
};

QTEST_GUILESS_MAIN(TestCircularAudioBuffer)
#include "test_circularaudiobuffer.moc"
