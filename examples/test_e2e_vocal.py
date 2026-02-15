#!/usr/bin/env python3
"""
Test E2E Pipeline — EXO bout en bout avec réponse vocale.

Pipeline complet :
  Micro → VAD → Capture → Whisper STT → Wake word → Brain (GPT-4o-mini) → Kokoro TTS → Playback

Usage:
  python examples/test_e2e_vocal.py
  python examples/test_e2e_vocal.py --rounds 3
"""

import asyncio
import argparse
import sys
import os
import io
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("SUPPRESS_CONFIG_WARNINGS", "1")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("e2e_vocal")

# ─── Couleurs ────────────────────────────────────────────
G = "\033[92m"
Y = "\033[93m"
R = "\033[91m"
C = "\033[96m"
B = "\033[1m"
RST = "\033[0m"

SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
FOLLOWUP_TIMEOUT = 7.0


async def main():
    parser = argparse.ArgumentParser(description="Test E2E EXO — pipeline vocal complet")
    parser.add_argument("--rounds", type=int, default=3, help="Nombre de tours (default: 3)")
    parser.add_argument("--whisper", type=str, default=os.environ.get("WHISPER_MODEL", "base"))
    parser.add_argument("--device", type=int, default=None)
    args = parser.parse_args()

    import pyaudio
    import numpy as np

    print(f"\n{B}{'═' * 60}")
    print(f"  EXO — TEST E2E COMPLET (avec réponse vocale)")
    print(f"  Dites « Exo » suivi de votre commande")
    print(f"{'═' * 60}{RST}\n")

    # ── 1. Micro ──
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

    stream = pa.open(
        format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
        input=True, input_device_index=dev_idx, frames_per_buffer=CHUNK_SIZE,
    )

    # ── 2. Whisper ──
    print(f"  ⏳ Chargement Whisper ({args.whisper})...", end="", flush=True)
    from faster_whisper import WhisperModel
    t0 = time.time()
    loop = asyncio.get_running_loop()
    whisper = await loop.run_in_executor(
        None, lambda: WhisperModel(args.whisper, device="cpu", compute_type="float32"),
    )
    print(f" OK ({time.time() - t0:.1f}s)")

    def transcribe(audio_bytes: bytes) -> str:
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if len(samples) < 4800:
            return ""
        segments, _ = whisper.transcribe(samples, language="fr", beam_size=1)
        return " ".join(seg.text for seg in segments).strip()

    # ── 3. Brain ──
    print(f"  ⏳ Chargement BrainEngine...", end="", flush=True)
    from src.brain.brain_engine import BrainEngine
    brain = BrainEngine()
    await brain.initialize()
    print(f" OK")

    # ── 4. TTS ──
    print(f"  ⏳ Chargement TTS...", end="", flush=True)
    from src.assistant.tts_client import TTSClient
    tts = TTSClient()
    tts.preload()
    print(f" OK (engine={tts.preferred_engine}, {tts.sample_rate}Hz)")

    # ── 5. Pygame mixer ──
    import pygame
    pygame.mixer.init(frequency=tts.sample_rate, size=-16, channels=1)
    print(f"  ✅ Pygame mixer OK ({tts.sample_rate}Hz)")

    # ── 6. Calibration VAD ──
    from src.audio.wake_word import (
        calibrate_noise_floor, capture_utterance,
        contains_wake_word, extract_command_after_wake, is_hallucination,
    )
    print(f"  🔇 Calibration bruit ambiant...", end="", flush=True)
    noise = calibrate_noise_floor(stream, CHUNK_SIZE)
    print(f" OK (bruit={noise:.0f} RMS)")

    # ── Warm-up Whisper (1er appel lent) ──
    print(f"  🔥 Warm-up Whisper...", end="", flush=True)
    silence = b'\x00' * (SAMPLE_RATE * 2)  # 1s silence
    await loop.run_in_executor(None, transcribe, silence)
    print(f" OK")

    print(f"\n{B}{'═' * 60}")
    print(f"  PRÊT — Dites « Exo, <commande> » ({args.rounds} tours)")
    print(f"{'═' * 60}{RST}\n")

    results = []

    def flush_mic():
        try:
            avail = stream.get_read_available()
            while avail > 0:
                stream.read(min(avail, CHUNK_SIZE), exception_on_overflow=False)
                avail = stream.get_read_available()
        except Exception:
            pass

    for i in range(args.rounds):
        print(f"  {C}── Tour {i + 1}/{args.rounds} ──{RST}")
        print(f"  👂 En écoute... dites « Exo, ... »\n")

        # ── Capture ──
        t0_pipeline = time.time()
        utterance = await capture_utterance(
            stream, sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE, timeout_sec=20.0,
        )
        capture_time = time.time() - t0_pipeline

        if not utterance:
            print(f"  {Y}⏱  Timeout — aucune voix{RST}\n")
            results.append({"status": "timeout"})
            continue

        duration = len(utterance) / (SAMPLE_RATE * 2)

        # ── STT ──
        t0_stt = time.time()
        transcript = await loop.run_in_executor(None, transcribe, utterance)
        stt_time = time.time() - t0_stt

        if not transcript or is_hallucination(transcript):
            tag = "hallucination" if transcript else "vide"
            print(f"  {Y}✗  Transcription {tag} : « {transcript or ''} »{RST}\n")
            results.append({"status": tag})
            continue

        print(f"  📝 STT : « {B}{transcript}{RST} » (capture={capture_time:.2f}s, STT={stt_time:.2f}s)")

        # ── Wake word ? ──
        if not contains_wake_word(transcript):
            print(f"  ℹ️  Pas de wake word « Exo » — ignoré\n")
            results.append({"status": "no_wake", "text": transcript, "stt_time": stt_time})
            continue

        command = extract_command_after_wake(transcript)
        print(f"  {G}✨ WAKE WORD détecté !{RST}")

        # Si juste "Exo" sans commande, attendre la suite
        if len(command.split()) < 2:
            if command:
                print(f"  🔸 Fragment : « {command} » — attente suite...")
            else:
                print(f"  🔸 Juste « Exo » — attente commande...")
            print(f"  🎤 Parlez maintenant (timeout {FOLLOWUP_TIMEOUT}s)...")

            followup = b""
            deadline = time.time() + FOLLOWUP_TIMEOUT
            while time.time() < deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                followup = await capture_utterance(
                    stream, sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE,
                    min_sec=0.3, timeout_sec=remaining,
                )
                if followup:
                    break

            if not followup:
                print(f"  {Y}⏱  Timeout — pas de suite après « Exo »{RST}\n")
                results.append({"status": "wake_no_cmd"})
                continue

            followup_text = await loop.run_in_executor(None, transcribe, followup)
            if not followup_text:
                print(f"  {Y}✗  Suite transcrite vide{RST}\n")
                results.append({"status": "wake_no_cmd"})
                continue

            command = (command + " " + followup_text).strip() if command else followup_text
            print(f"  📝 Suite : « {followup_text} »")

        print(f"  {G}💬 Commande : « {command} »{RST}")

        # ── Couper le micro pendant la réponse ──
        stream.stop_stream()

        # ── Brain ──
        t0_brain = time.time()
        result = await brain.process_command(
            text=command, room="local", context={"source": "test_e2e"},
        )
        brain_time = time.time() - t0_brain
        response_text = result.get("text", "")
        function_calls = result.get("function_calls", [])

        print(f"  🤖 Brain ({brain_time:.2f}s) : « {B}{response_text}{RST} »")
        if function_calls:
            for fc in function_calls:
                print(f"  🔧 Action : {fc['name']}({fc['arguments']})")

        # ── TTS ──
        tts_time = 0.0
        play_time = 0.0
        if response_text:
            t0_tts = time.time()
            try:
                audio = await tts.speak(response_text)
                tts_time = time.time() - t0_tts
                print(f"  🔊 TTS ({tts_time:.2f}s, {len(audio) // 1024}KB)")

                # Playback
                t0_play = time.time()
                sound = pygame.mixer.Sound(io.BytesIO(audio))
                sound.play()
                while pygame.mixer.get_busy():
                    await asyncio.sleep(0.05)
                play_time = time.time() - t0_play
                print(f"  🔈 Playback ({play_time:.2f}s)")
            except Exception as e:
                print(f"  {R}✗ TTS/Playback erreur : {e}{RST}")
                print(f"  📄 Réponse texte : {response_text}")

        # ── Total ──
        total = time.time() - t0_pipeline
        print(f"\n  {B}⏱  TOTAL : {total:.2f}s{RST}")
        print(f"     Capture={capture_time:.2f}s + STT={stt_time:.2f}s + Brain={brain_time:.2f}s + TTS={tts_time:.2f}s + Play={play_time:.2f}s")

        speed = "🟢" if (stt_time + brain_time + tts_time) < 3.0 else ("🟡" if (stt_time + brain_time + tts_time) < 5.0 else "🔴")
        print(f"     Latence traitement (STT+Brain+TTS) : {stt_time + brain_time + tts_time:.2f}s {speed}\n")

        # ── Réactiver micro ──
        stream.start_stream()
        flush_mic()

        results.append({
            "status": "ok",
            "text": transcript,
            "command": command,
            "response": response_text,
            "capture_time": capture_time,
            "stt_time": stt_time,
            "brain_time": brain_time,
            "tts_time": tts_time,
            "play_time": play_time,
            "total_time": total,
            "processing_time": stt_time + brain_time + tts_time,
        })

    # ── Résumé final ──
    print(f"\n{B}{'═' * 60}")
    print(f"  RÉSUMÉ E2E")
    print(f"{'═' * 60}{RST}")

    ok = [r for r in results if r["status"] == "ok"]
    print(f"  Tours complets    : {len(ok)}/{args.rounds}")
    print(f"  Sans wake word    : {sum(1 for r in results if r['status'] == 'no_wake')}")
    print(f"  Timeouts          : {sum(1 for r in results if r['status'] == 'timeout')}")

    if ok:
        avg_proc = sum(r["processing_time"] for r in ok) / len(ok)
        avg_total = sum(r["total_time"] for r in ok) / len(ok)
        print(f"\n  Latence moyenne (STT+Brain+TTS) : {avg_proc:.2f}s")
        print(f"  Temps total moyen (avec capture) : {avg_total:.2f}s")

        print(f"\n  Détail par tour :")
        for j, r in enumerate(ok):
            print(f"    {j+1}. « {r['command'][:50]} »")
            print(f"       → « {r['response'][:60]} »")
            print(f"       STT={r['stt_time']:.2f}s  Brain={r['brain_time']:.2f}s  TTS={r['tts_time']:.2f}s  Total={r['total_time']:.2f}s")

    # Cleanup
    stream.stop_stream()
    stream.close()
    pa.terminate()
    await brain.close()
    pygame.mixer.quit()
    print(f"\n  🔌 Ressources libérées. Test terminé.\n")


if __name__ == "__main__":
    asyncio.run(main())
