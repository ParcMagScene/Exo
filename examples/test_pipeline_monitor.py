#!/usr/bin/env python3
"""
Test Pipeline Monitor — Diagnostic complet EXO.

Teste en temps réel :
  1. Niveaux micro (RMS) + calibration bruit ambiant
  2. Seuil VAD adaptatif
  3. Capture d'utterance (durée, chunks vocaux)
  4. Transcription Whisper (précision + latence)
  5. Détection wake word "EXO"
  6. Extraction commande

Usage:
  python examples/test_pipeline_monitor.py
  python examples/test_pipeline_monitor.py --rounds 10
  python examples/test_pipeline_monitor.py --whisper small
"""

import asyncio
import argparse
import sys
import os
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("SUPPRESS_CONFIG_WARNINGS", "1")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline_monitor")

# ─── Couleurs terminal ───────────────────────────────────
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

SAMPLE_RATE = 16000
CHUNK_SIZE = 1024


def bar(value: float, max_val: float = 2000, width: int = 40) -> str:
    """Barre visuelle ASCII pour un niveau RMS."""
    ratio = min(value / max_val, 1.0)
    filled = int(ratio * width)
    if ratio < 0.15:
        color = ""
    elif ratio < 0.4:
        color = YELLOW
    else:
        color = GREEN
    return f"{color}{'█' * filled}{'░' * (width - filled)}{RESET}"


async def phase_1_mic_levels(stream, duration: float = 5.0):
    """Phase 1 : Affiche les niveaux micro en temps réel."""
    from src.audio.wake_word import rms_energy

    print(f"\n{BOLD}{'═' * 60}")
    print(f"  PHASE 1 — Niveaux micro ({duration}s)")
    print(f"{'═' * 60}{RESET}")
    print(f"  Parlez, faites du bruit, restez silencieux...")
    print(f"  Les barres montrent le niveau RMS du micro.\n")

    energies = []
    t0 = time.time()
    while time.time() - t0 < duration:
        try:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            e = rms_energy(data)
            energies.append(e)
            print(f"\r  RMS: {e:6.0f}  {bar(e)}  ", end="", flush=True)
        except Exception:
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.01)

    print()

    if energies:
        import numpy as np
        arr = np.array(energies)
        print(f"\n  📊 Statistiques sur {len(energies)} échantillons :")
        print(f"     Min : {arr.min():.0f}")
        print(f"     Max : {arr.max():.0f}")
        print(f"     Médiane : {np.median(arr):.0f}")
        print(f"     Moyenne : {arr.mean():.0f}")
        print(f"     Écart-type : {arr.std():.0f}")
        print(f"     P95 (bruit) : {np.percentile(arr, 95):.0f}")
    return energies


async def phase_2_calibration(stream):
    """Phase 2 : Calibration du bruit ambiant."""
    from src.audio.wake_word import (
        calibrate_noise_floor,
        get_adaptive_threshold,
        DEFAULT_VOICE_THRESHOLD,
        ADAPTIVE_MULTIPLIER,
    )

    print(f"\n{BOLD}{'═' * 60}")
    print(f"  PHASE 2 — Calibration bruit ambiant")
    print(f"{'═' * 60}{RESET}")
    print(f"  Restez silencieux pendant 2 secondes...\n")

    await asyncio.sleep(0.5)  # Petit délai pour que l'utilisateur se prépare

    noise = calibrate_noise_floor(stream, CHUNK_SIZE)
    threshold = get_adaptive_threshold(DEFAULT_VOICE_THRESHOLD)

    print(f"  🔇 Bruit ambiant (médiane)  : {noise:.0f} RMS")
    print(f"  📐 Multiplicateur adaptatif  : ×{ADAPTIVE_MULTIPLIER}")
    print(f"  🎯 Seuil adaptatif calculé   : {noise * ADAPTIVE_MULTIPLIER:.0f} RMS")
    print(f"  🎯 Seuil effectif (borné)    : {threshold:.0f} RMS")
    print(f"  📏 Seuil fixe (référence)    : {DEFAULT_VOICE_THRESHOLD} RMS")

    if threshold < 200:
        print(f"  {YELLOW}⚠️  Seuil très bas — risque de faux positifs{RESET}")
    elif threshold > 600:
        print(f"  {RED}⚠️  Seuil élevé — risque de rater des voix douces{RESET}")
    else:
        print(f"  {GREEN}✅ Seuil dans la plage optimale{RESET}")

    return threshold


async def phase_3_capture_and_stt(stream, whisper_model, rounds: int = 5):
    """Phase 3 : Capture + transcription + wake word."""
    from src.audio.wake_word import (
        capture_utterance,
        contains_wake_word,
        extract_command_after_wake,
        is_hallucination,
        DEFAULT_VOICE_THRESHOLD,
        DEFAULT_SILENCE_CHUNKS,
        DEFAULT_MIN_UTTERANCE_SEC,
    )

    print(f"\n{BOLD}{'═' * 60}")
    print(f"  PHASE 3 — Capture + Whisper ({rounds} tours)")
    print(f"{'═' * 60}{RESET}")
    print(f"  Modèle Whisper : {whisper_model}")
    print(f"  Seuil VAD      : {DEFAULT_VOICE_THRESHOLD} (adaptatif activé)")
    print(f"  Silence fin    : {DEFAULT_SILENCE_CHUNKS} chunks (~{DEFAULT_SILENCE_CHUNKS * CHUNK_SIZE / SAMPLE_RATE:.2f}s)")
    print(f"  Min utterance  : {DEFAULT_MIN_UTTERANCE_SEC}s")
    print(f"\n  Dites des phrases — essayez « Exo, quelle heure est-il ? »")
    print(f"  ou « Exo, allume la lumière »\n")

    # Charger Whisper
    print(f"  ⏳ Chargement Whisper ({whisper_model})...", end="", flush=True)
    from faster_whisper import WhisperModel
    import numpy as np

    t0 = time.time()
    loop = asyncio.get_running_loop()
    whisper = await loop.run_in_executor(
        None,
        lambda: WhisperModel(whisper_model, device="cpu", compute_type="float32"),
    )
    print(f" OK ({time.time() - t0:.1f}s)")

    def transcribe(audio_bytes: bytes) -> str:
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if len(samples) < 4800:
            return ""
        segments, _ = whisper.transcribe(samples, language="fr", beam_size=1)
        return " ".join(seg.text for seg in segments).strip()

    results = []

    for i in range(rounds):
        print(f"\n  {CYAN}── Tour {i + 1}/{rounds} ──{RESET}")
        print(f"  👂 En écoute... (parlez maintenant, timeout 15s)")

        # Capture
        t0_capture = time.time()
        utterance = await capture_utterance(
            stream,
            sample_rate=SAMPLE_RATE,
            chunk_size=CHUNK_SIZE,
            timeout_sec=15.0,
        )
        capture_time = time.time() - t0_capture

        if not utterance:
            print(f"  {YELLOW}⏱  Timeout — aucune voix détectée{RESET}")
            results.append({"status": "timeout"})
            continue

        duration = len(utterance) / (SAMPLE_RATE * 2)
        print(f"  📦 Capturé : {duration:.2f}s audio ({len(utterance) // 1024}KB) en {capture_time:.2f}s")

        # Transcription
        t0_stt = time.time()
        transcript = await loop.run_in_executor(None, transcribe, utterance)
        stt_time = time.time() - t0_stt

        if not transcript:
            print(f"  {YELLOW}✗  Transcription vide{RESET}")
            results.append({"status": "empty", "capture_time": capture_time, "stt_time": stt_time})
            continue

        # Hallucination ?
        if is_hallucination(transcript):
            print(f"  {YELLOW}👻 Hallucination filtrée : « {transcript} »{RESET}")
            results.append({"status": "hallucination", "text": transcript, "stt_time": stt_time})
            continue

        # Résultat STT
        print(f"  📝 Transcrit : « {BOLD}{transcript}{RESET} » (STT={stt_time:.2f}s)")

        # Wake word ?
        has_wake = contains_wake_word(transcript)
        if has_wake:
            command = extract_command_after_wake(transcript)
            print(f"  {GREEN}✨ WAKE WORD détecté !{RESET}")
            if command and len(command.split()) >= 2:
                print(f"  {GREEN}💬 Commande : « {command} »{RESET}")
            elif command:
                print(f"  {YELLOW}🔸 Fragment : « {command} » (trop court, attente suite){RESET}")
            else:
                print(f"  {YELLOW}🔸 Juste « Exo » — pas de commande{RESET}")
        else:
            command = ""
            print(f"  ℹ️  Pas de wake word « Exo »")

        # Timing
        total = capture_time + stt_time
        speed_indicator = "🟢" if stt_time < 1.0 else ("🟡" if stt_time < 2.0 else "🔴")
        print(f"  ⏱  Timing : capture={capture_time:.2f}s + STT={stt_time:.2f}s = {total:.2f}s {speed_indicator}")

        results.append({
            "status": "ok",
            "text": transcript,
            "wake_word": has_wake,
            "command": command,
            "audio_duration": duration,
            "capture_time": capture_time,
            "stt_time": stt_time,
            "total_time": total,
        })

    # Résumé
    print(f"\n{BOLD}{'═' * 60}")
    print(f"  RÉSUMÉ")
    print(f"{'═' * 60}{RESET}")

    ok_results = [r for r in results if r.get("status") == "ok"]
    timeouts = sum(1 for r in results if r.get("status") == "timeout")
    hallucinations = sum(1 for r in results if r.get("status") == "hallucination")
    empties = sum(1 for r in results if r.get("status") == "empty")

    print(f"  Tours réussis     : {len(ok_results)}/{rounds}")
    print(f"  Timeouts          : {timeouts}")
    print(f"  Hallucinations    : {hallucinations}")
    print(f"  Transcription vide: {empties}")

    if ok_results:
        avg_stt = sum(r["stt_time"] for r in ok_results) / len(ok_results)
        avg_total = sum(r["total_time"] for r in ok_results) / len(ok_results)
        wakes = sum(1 for r in ok_results if r["wake_word"])
        print(f"  Wake words détectés: {wakes}/{len(ok_results)}")
        print(f"  STT moyen         : {avg_stt:.2f}s")
        print(f"  Latence totale moy: {avg_total:.2f}s (capture+STT)")

        print(f"\n  Transcriptions :")
        for r in ok_results:
            wake_tag = f"{GREEN}[EXO]{RESET} " if r["wake_word"] else ""
            print(f"    {wake_tag}« {r['text']} » ({r['stt_time']:.2f}s)")


async def main():
    parser = argparse.ArgumentParser(description="Test pipeline EXO — monitoring micro")
    parser.add_argument("--rounds", type=int, default=5, help="Nombre de tours de capture (default: 5)")
    parser.add_argument("--whisper", type=str, default=os.environ.get("WHISPER_MODEL", "base"),
                        help="Modèle Whisper (tiny/base/small/medium)")
    parser.add_argument("--skip-levels", action="store_true", help="Sauter la phase niveaux micro")
    parser.add_argument("--device", type=int, default=None, help="Index du micro PyAudio")
    args = parser.parse_args()

    import pyaudio

    print(f"\n{BOLD}{'═' * 60}")
    print(f"  EXO — PIPELINE MONITOR")
    print(f"  Diagnostic complet du pipeline vocal")
    print(f"{'═' * 60}{RESET}\n")

    # Ouvrir le micro
    pa = pyaudio.PyAudio()

    if args.device is None:
        try:
            info = pa.get_default_input_device_info()
            dev_idx = int(info["index"])
        except Exception:
            dev_idx = 0
    else:
        dev_idx = args.device

    dev_info = pa.get_device_info_by_index(dev_idx)
    print(f"  🎤 Micro : {dev_info['name']} (index {dev_idx})")
    print(f"  📐 Sample rate : {SAMPLE_RATE} Hz, chunk : {CHUNK_SIZE}")

    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        input_device_index=dev_idx,
        frames_per_buffer=CHUNK_SIZE,
    )

    try:
        # Phase 1 : Niveaux micro
        if not args.skip_levels:
            await phase_1_mic_levels(stream, duration=5.0)

        # Phase 2 : Calibration
        await phase_2_calibration(stream)

        # Phase 3 : Capture + STT + wake word
        await phase_3_capture_and_stt(stream, args.whisper, rounds=args.rounds)

    except KeyboardInterrupt:
        print(f"\n\n  ⚠️  Arrêt par l'utilisateur")

    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
        print(f"\n  🔌 Micro fermé. Test terminé.\n")


if __name__ == "__main__":
    asyncio.run(main())
