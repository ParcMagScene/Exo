"""Transcrit les WAV de reference et compare au prompt_text de voices.json.
Si decalage important -> reecrit voices.json avec la transcription reelle
(critique pour la qualite zero-shot CosyVoice2).
"""
from __future__ import annotations
import json, os, sys, difflib
from pathlib import Path

ROOT = Path(r"D:\EXO\models\cosyvoice_fr")
VOICES_JSON = ROOT / "voices.json"
VOICES_DIR = ROOT / "voices"

def main(write: bool = False) -> int:
    from faster_whisper import WhisperModel
    print("[info] Chargement Whisper large-v3 (peut prendre 30s)...", flush=True)
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")

    entries = json.loads(VOICES_JSON.read_text(encoding="utf-8"))
    changes = []
    for v in entries:
        wav = VOICES_DIR / v.get("file", "")
        if not wav.is_file():
            print(f"[skip] {v.get('id')}: wav absent ({wav})")
            continue
        segments, _ = model.transcribe(
            str(wav), language="fr", beam_size=5, vad_filter=False,
            condition_on_previous_text=False,
        )
        transcript = " ".join(seg.text.strip() for seg in segments).strip()
        old = v.get("prompt_text", "")
        ratio = difflib.SequenceMatcher(None, old.lower(), transcript.lower()).ratio()
        print(f"\n=== {v.get('id')} ({v.get('file')}) ===")
        print(f"  voices.json  : {old!r}")
        print(f"  transcription: {transcript!r}")
        print(f"  similarity   : {ratio:.2%}")
        if transcript and ratio < 0.95:
            changes.append((v.get("id"), old, transcript))
            if write:
                v["prompt_text"] = transcript

    if write and changes:
        backup = VOICES_JSON.with_suffix(".json.bak")
        if not backup.exists():
            backup.write_text(VOICES_JSON.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"\n[backup] {backup}")
        VOICES_JSON.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[write] voices.json mis a jour ({len(changes)} entrees)")
    elif changes:
        print(f"\n[dry-run] {len(changes)} prompt_text divergent(s). Relance avec --write pour appliquer.")
    else:
        print("\n[ok] Tous les prompt_text correspondent (>= 95% similarite).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(write="--write" in sys.argv))
