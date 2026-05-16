// ============================================================================
//  AudioAutoCorrector.cpp
//  Auto-correction temps reel des anomalies audio EXO (Phase 10).
// ============================================================================
#include "AudioAutoCorrector.h"
#include "AudioAnomalyDetector.h"
#include "TTSManager.h"           // PCMRingBuffer
#include "core/LogManager.h"

#include <QDebug>
#include <algorithm>
#include <cstring>
#include <vector>

// ----------------------------------------------------------------------------
//  Construction / cablage
// ----------------------------------------------------------------------------
AudioAutoCorrector::AudioAutoCorrector() = default;

void AudioAutoCorrector::attach(PCMRingBuffer *ring, AudioAnomalyDetector *detector)
{
    m_ring     = ring;
    m_detector = detector;
}

int64_t AudioAutoCorrector::nowUs() const
{
    return std::chrono::duration_cast<std::chrono::microseconds>(
               clock::now().time_since_epoch())
        .count();
}

// ----------------------------------------------------------------------------
//  Soft-clip (anti-saturation)
//    Au-dela de SOFTCLIP_THRESHOLD on applique une compression douce
//    pour eviter la coupure brutale a +/- 32767 (cause classique de pop).
// ----------------------------------------------------------------------------
int AudioAutoCorrector::applySoftClip(int16_t *samples, int count)
{
    int clipped = 0;
    for (int i = 0; i < count; ++i) {
        int s = samples[i];
        const int abs_s = s < 0 ? -s : s;
        if (abs_s <= SOFTCLIP_THRESHOLD) continue;

        // Soft-knee : compression progressive entre 32500 et 32767
        const double t = static_cast<double>(abs_s - SOFTCLIP_THRESHOLD)
                       / static_cast<double>(32767 - SOFTCLIP_THRESHOLD);
        const double smoothed = SOFTCLIP_THRESHOLD
                              + (SOFTCLIP_LIMIT - SOFTCLIP_THRESHOLD)
                                * (1.0 - std::exp(-2.5 * t));
        const int new_abs = std::min(static_cast<int>(smoothed), SOFTCLIP_LIMIT);
        samples[i] = static_cast<int16_t>(s < 0 ? -new_abs : new_abs);
        ++clipped;
    }
    return clipped;
}

// ----------------------------------------------------------------------------
//  Injection de silence proactive dans le ring (trou push)
// ----------------------------------------------------------------------------
void AudioAutoCorrector::injectSilenceIntoRing(int samples, const char *reason)
{
    if (!m_ring || samples <= 0) return;
    static thread_local std::vector<int16_t> zero;
    if (static_cast<int>(zero.size()) < samples) zero.assign(samples, 0);
    const int written = m_ring->pushSamples(zero.data(), samples);
    if (written > 0) {
        m_silenceInjections.fetch_add(1, std::memory_order_relaxed);
        m_gapInjections.fetch_add(1, std::memory_order_relaxed);
        if (m_verbose.load(std::memory_order_relaxed)) {
            hVoice() << "[AUTOFIX]" << reason << "-> injected silence"
                     << written << "samples";
        }
    }
}

// ============================================================================
//  PRODUCTEUR : pre-traitement push
// ============================================================================
int AudioAutoCorrector::onPush(QByteArray &pcm)
{
    if (!m_enabled.load(std::memory_order_relaxed)) return 0;
    if (pcm.isEmpty()) return 0;

    // 1) Alignement octets : drop d'un octet residuel impair
    if ((pcm.size() & 1) != 0) {
        pcm.chop(1);
        m_blockNormalized.fetch_add(1, std::memory_order_relaxed);
        if (m_verbose.load(std::memory_order_relaxed)) {
            hVoice() << "[AUTOFIX] block alignment -> chopped 1 stray byte";
        }
    }

    // 2) Normalisation taille : on conserve uniquement les blocs entiers
    //    de 960 samples (1920 bytes). Le residu < 960 est tronque pour
    //    eviter les mini-blocs qui faussent la cadence 40 ms.
    const int residual = pcm.size() % EXPECTED_BYTES;
    if (residual != 0 && pcm.size() > EXPECTED_BYTES) {
        pcm.chop(residual);
        m_blockNormalized.fetch_add(1, std::memory_order_relaxed);
        if (m_verbose.load(std::memory_order_relaxed)) {
            hVoice() << "[AUTOFIX] block normalization -> chopped"
                     << residual << "trailing bytes (mini-block)";
        }
    }
    // Si pcm < 1920 bytes, on le laisse passer (premier/dernier chunk reel).

    // 3) Soft-clip in-place
    const int sampleCount = pcm.size() / 2;
    int clipped = 0;
    if (sampleCount > 0) {
        clipped = applySoftClip(reinterpret_cast<int16_t *>(pcm.data()), sampleCount);
        if (clipped > 0) {
            m_softClipped.fetch_add(static_cast<uint64_t>(clipped),
                                    std::memory_order_relaxed);
            if (m_verbose.load(std::memory_order_relaxed)) {
                hVoice() << "[AUTOFIX] saturation soft-clip ->"
                         << clipped << "samples";
            }
        }
    }

    // 4) Trou push : si dt > 60 ms depuis le dernier push, injecter un
    //    silence d'EXPECTED_SAMPLES samples AVANT d'ecrire ce nouveau bloc
    //    pour preserver la continuite cote pump.
    const int64_t now = nowUs();
    const int64_t prev = m_lastPushTickUs.exchange(now, std::memory_order_relaxed);
    if (prev != 0) {
        const int64_t dtUs = now - prev;
        if (dtUs > static_cast<int64_t>(GAP_THRESHOLD_MS) * 1000) {
            const double dtMs = static_cast<double>(dtUs) / 1000.0;
            if (m_verbose.load(std::memory_order_relaxed)) {
                hVoice() << "[AUTOFIX] push gap" << dtMs << "ms -> injecting silence";
            }
            injectSilenceIntoRing(EXPECTED_SAMPLES, "push gap");
        }
        // Note : burst (< 10 ms) -> on ne fait rien d'agressif au niveau
        // producteur ; le ring lisse naturellement vers le pump 5 ms.
        // Trace seulement.
        else if (dtUs < static_cast<int64_t>(BURST_THRESHOLD_MS) * 1000) {
            if (m_verbose.load(std::memory_order_relaxed)) {
                const double dtMs = static_cast<double>(dtUs) / 1000.0;
                hVoice() << "[AUTOFIX] push burst" << dtMs
                         << "ms -> ring will smooth";
            }
        }
    }

    return clipped;
}

// ----------------------------------------------------------------------------
//  PRODUCTEUR : post-write (correction overflow)
// ----------------------------------------------------------------------------
void AudioAutoCorrector::afterRingWrite(int requestedBytes, int writtenBytes)
{
    if (!m_enabled.load(std::memory_order_relaxed)) return;
    if (writtenBytes >= requestedBytes) return;
    if (!m_ring) return;

    // Overflow : le ring a tronque. On drop un bloc de tete (oldest = 960
    // samples) pour faire de la place et eviter qu'un overflow ne se
    // reproduise sur le push suivant.
    const int lostBytes   = requestedBytes - writtenBytes;
    const int lostSamples = lostBytes / 2;
    m_ring->dropSamples(EXPECTED_SAMPLES);
    m_overflowDrops.fetch_add(1, std::memory_order_relaxed);
    if (m_verbose.load(std::memory_order_relaxed)) {
        hWarning(exoVoice) << "[AUTOFIX] overflow -> dropped"
                           << EXPECTED_SAMPLES << "samples (lost"
                           << lostSamples << "incoming samples)";
    }
}

// ============================================================================
//  CONSOMMATEUR : underflow (silence-fill cote pump)
// ============================================================================
int AudioAutoCorrector::onPop(char *buffer, int actualBytes, int wantedBytes,
                              int /*ringFreeBytes*/)
{
    if (!m_enabled.load(std::memory_order_relaxed)) return actualBytes;
    if (!buffer || wantedBytes <= 0)                 return actualBytes;
    if (actualBytes >= wantedBytes)                  return actualBytes;

    // Underflow : on complete par un silence absolu (zero) jusqu'a
    // wantedBytes, en alignant sur la frontiere int16.
    const int aligned = wantedBytes & ~1;
    const int padFrom = std::max(0, actualBytes & ~1);
    if (aligned <= padFrom) return actualBytes;

    std::memset(buffer + padFrom, 0, static_cast<size_t>(aligned - padFrom));
    const int padBytes   = aligned - padFrom;
    const int padSamples = padBytes / 2;
    m_silenceInjections.fetch_add(1, std::memory_order_relaxed);

    if (m_verbose.load(std::memory_order_relaxed)) {
        hWarning(exoVoice) << "[AUTOFIX] underflow -> injected silence"
                           << padSamples << "samples (filled" << padBytes
                           << "bytes)";
    }
    return aligned;
}

// ----------------------------------------------------------------------------
//  CONSOMMATEUR : tracking derive + pacing
// ----------------------------------------------------------------------------
void AudioAutoCorrector::onBlockWritten(int64_t /*writeMicros*/)
{
    if (!m_enabled.load(std::memory_order_relaxed)) return;

    const int64_t now  = nowUs();
    const int64_t prev = m_lastPopTickUs.exchange(now, std::memory_order_relaxed);
    if (prev == 0) return;

    const int64_t dtUs        = now - prev;
    const int64_t expectedUs  = static_cast<int64_t>(EXPECTED_DT_MS * 1000.0);
    const int64_t deltaUs     = dtUs - expectedUs;
    // Cumul borne pour eviter l'emballement
    int64_t cumul = m_driftCumulUs.load(std::memory_order_relaxed) + deltaUs;
    cumul = std::clamp<int64_t>(cumul, -200000, 200000);
    m_driftCumulUs.store(cumul, std::memory_order_relaxed);
}

int64_t AudioAutoCorrector::suggestPacingAdjustmentUs()
{
    if (!m_enabled.load(std::memory_order_relaxed)) return 0;

    const int64_t cumul = m_driftCumulUs.load(std::memory_order_relaxed);
    if (std::llabs(cumul) < static_cast<int64_t>(DRIFT_LIMIT_US)) return 0;

    // Compensation : ramene le pump de +/-1 ms vers la cadence ideale.
    const int64_t adjUs = (cumul > 0) ? -1000 : +1000;
    // On consomme l'equivalent du drift compense
    m_driftCumulUs.fetch_add(-adjUs, std::memory_order_relaxed);
    m_pacingAdjustments.fetch_add(1, std::memory_order_relaxed);

    if (m_verbose.load(std::memory_order_relaxed)) {
        const double adjMs = static_cast<double>(adjUs) / 1000.0;
        hVoice() << "[AUTOFIX] drift correction -> pacing"
                 << (adjMs > 0 ? "+" : "") << adjMs << "ms"
                 << "(cumul" << static_cast<double>(cumul) / 1000.0 << "ms)";
    }
    return adjUs;
}

// ----------------------------------------------------------------------------
//  Reset
// ----------------------------------------------------------------------------
void AudioAutoCorrector::reset()
{
    m_lastPushTickUs.store(0, std::memory_order_relaxed);
    m_lastPopTickUs.store(0, std::memory_order_relaxed);
    m_driftCumulUs.store(0, std::memory_order_relaxed);
    m_silenceInjections.store(0, std::memory_order_relaxed);
    m_overflowDrops.store(0, std::memory_order_relaxed);
    m_softClipped.store(0, std::memory_order_relaxed);
    m_blockNormalized.store(0, std::memory_order_relaxed);
    m_gapInjections.store(0, std::memory_order_relaxed);
    m_pacingAdjustments.store(0, std::memory_order_relaxed);
}
