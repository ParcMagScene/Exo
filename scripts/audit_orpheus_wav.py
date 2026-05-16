"""
Audit Orpheus -> WAV 24 kHz mono 16-bit
======================================

Genere un fichier WAV de reference depuis le serveur Orpheus pour tester en
dehors du pipeline audio EXO (VLC, Windows Media Player, Audacity...).

Usage :
    python scripts/audit_orpheus_wav.py [--text "..."] [--out audit_orpheus.wav]
                                        [--http http://127.0.0.1:8899/tts]
                                        [--ws   ws://127.0.0.1:8767]
                                        [--voice ...] [--mode auto|http|ws]

Comportement :
  - mode=auto (defaut) : essaie HTTP d'abord, fallback WS.
  - mode=http : utilise uniquement l'endpoint HTTP /tts (server_gguf.py).
  - mode=ws   : utilise uniquement le WS streaming (server_ws.py).

Verifications post-generation :
  - sample rate == 24000 Hz
  - channels   == 1 (mono)
  - sample width == 2 bytes (PCM16)
  - duree, RMS, peak, %clipping, %silence, taille fichier
  - tentative ffprobe si dispo (info supplementaire)
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import shutil
import struct
import subprocess
import sys
import math
import time
import wave
from pathlib import Path
from typing import Optional

DEFAULT_TEXT = (
    "Bonjour, ceci est un test audio de reference pour diagnostiquer "
    "les craquements dans le pipeline EXO. La synthese est realisee a "
    "vingt-quatre kilohertz, mono, seize bits."
)


# ---------------------------------------------------------------------------
#  HTTP backend (server_gguf.py)
# ---------------------------------------------------------------------------
def synth_http(url: str, text: str, voice: Optional[str], timeout: float) -> bytes:
    import urllib.request

    payload = {"text": text}
    if voice:
        payload["voice"] = voice
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
    elapsed = time.time() - t0
    obj = json.loads(body)
    if "audio_b64" not in obj:
        raise RuntimeError(f"reponse HTTP inattendue : {list(obj.keys())}")
    wav_bytes = base64.b64decode(obj["audio_b64"])
    print(
        f"[HTTP] OK  sample_rate={obj.get('sample_rate')} "
        f"duration={obj.get('duration_s'):.2f}s rtf={obj.get('rtf'):.2f} "
        f"voice={obj.get('voice')} elapsed={elapsed:.2f}s "
        f"wav_size={len(wav_bytes)} bytes"
    )
    return wav_bytes


# ---------------------------------------------------------------------------
#  WS backend (server_ws.py) — streaming PCM16 brut, on assemble en WAV
# ---------------------------------------------------------------------------
async def synth_ws_async(url: str, text: str, voice: Optional[str], timeout: float) -> bytes:
    try:
        import websockets
    except ImportError:
        raise RuntimeError(
            "websockets non installe. Active le venv : "
            r".\.venv_stt_tts\Scripts\Activate.ps1"
        )

    pcm_chunks: list[bytes] = []
    sample_rate = 24000

    async with websockets.connect(url, max_size=None, ping_interval=None) as ws:
        # Attend le "ready" emis a la connexion par services/orpheus/server_ws.py.
        try:
            ready = await asyncio.wait_for(ws.recv(), timeout=10.0)
            print(f"[WS] hello : {ready[:160] if isinstance(ready, str) else f'<{len(ready)}B>'}")
        except asyncio.TimeoutError:
            print("[WS] pas de ready en 10s, on tente quand meme")
        # Protocole Orpheus WS streaming : type=synthesize / type=end
        req: dict = {"type": "synthesize", "text": text}
        if voice:
            req["voice"] = voice
        await ws.send(json.dumps(req))
        t0 = time.time()
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                raise RuntimeError(f"timeout WS apres {timeout:.0f}s")
            if isinstance(msg, (bytes, bytearray)):
                pcm_chunks.append(bytes(msg))
            else:
                try:
                    obj = json.loads(msg)
                except Exception:
                    print(f"[WS] msg texte non-JSON ignore : {msg[:120]!r}")
                    continue
                ev = obj.get("type") or obj.get("event")
                if ev in ("start", "info", "ready"):
                    sr = obj.get("sample_rate")
                    if sr:
                        sample_rate = int(sr)
                    print(f"[WS] {ev} sample_rate={sample_rate} voice={obj.get('voice')}")
                elif ev in ("end", "done", "finished"):
                    print(f"[WS] done elapsed={time.time()-t0:.2f}s "
                          f"chunks={len(pcm_chunks)} bytes={sum(len(c) for c in pcm_chunks)}")
                    break
                elif ev == "error":
                    raise RuntimeError(f"WS error : {obj}")
                else:
                    print(f"[WS] event={ev} obj={obj}")
        pcm = b"".join(pcm_chunks)

    # Encapsule le PCM brut dans un WAV mono 16-bit
    return pcm_to_wav(pcm, sample_rate=sample_rate, channels=1, sample_width=2)


def synth_ws(url: str, text: str, voice: Optional[str], timeout: float) -> bytes:
    return asyncio.run(synth_ws_async(url, text, voice, timeout))


def pcm_to_wav(pcm: bytes, sample_rate: int, channels: int, sample_width: int) -> bytes:
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sample_width)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


# ---------------------------------------------------------------------------
#  Verification du WAV
# ---------------------------------------------------------------------------
def analyze_wav(path: Path) -> dict:
    with wave.open(str(path), "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        nframes = w.getnframes()
        raw = w.readframes(nframes)

    info = {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sample_rate": sr,
        "channels": nch,
        "sample_width_bytes": sw,
        "frames": nframes,
        "duration_s": nframes / sr if sr else 0.0,
    }

    # Statistiques amplitude (PCM16 mono attendu)
    if sw == 2 and nch == 1 and nframes > 0:
        # Decode int16
        samples = struct.unpack(f"<{nframes}h", raw)
        n = len(samples)
        peak = max(abs(s) for s in samples)
        rms = (sum(s * s for s in samples) / n) ** 0.5
        clip_count = sum(1 for s in samples if s >= 32760 or s <= -32760)
        sil_count = sum(1 for s in samples if -10 <= s <= 10)
        info["peak"]            = peak
        info["rms"]             = round(rms, 1)
        info["clipping_pct"]    = round(100.0 * clip_count / n, 4)
        info["near_silence_pct"] = round(100.0 * sil_count / n, 2)
        info["dbfs_peak"]       = round(20.0 * math.log10(peak / 32767.0), 2) if peak > 0 else -120.0
    return info


def maybe_ffprobe(path: Path) -> Optional[str]:
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout
    except Exception as e:
        return f"ffprobe error: {e}"


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default=DEFAULT_TEXT)
    ap.add_argument("--out",  default="audit_orpheus.wav")
    ap.add_argument("--http", default="http://127.0.0.1:8899/tts")
    ap.add_argument("--ws",   default="ws://127.0.0.1:8767")
    ap.add_argument("--voice", default=None)
    ap.add_argument("--mode", choices=["auto", "http", "ws"], default="auto")
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args()

    out = Path(args.out).resolve()

    wav_bytes: Optional[bytes] = None
    used = None

    def try_http() -> Optional[bytes]:
        try:
            print(f"[*] tentative HTTP : {args.http}")
            return synth_http(args.http, args.text, args.voice, args.timeout)
        except Exception as e:
            print(f"[!] HTTP echec : {e}")
            return None

    def try_ws() -> Optional[bytes]:
        try:
            print(f"[*] tentative WS   : {args.ws}")
            return synth_ws(args.ws, args.text, args.voice, args.timeout)
        except Exception as e:
            print(f"[!] WS echec : {e}")
            return None

    if args.mode in ("auto", "http"):
        wav_bytes = try_http()
        used = "http" if wav_bytes else used
    if wav_bytes is None and args.mode in ("auto", "ws"):
        wav_bytes = try_ws()
        used = "ws" if wav_bytes else used

    if wav_bytes is None:
        print("\n[X] ECHEC : aucun endpoint Orpheus accessible.")
        print("    - Verifie que server_gguf.py (8899) ou server_ws.py (8767) tourne.")
        print("    - Pour HTTP : powershell -File services\\orpheus\\start_orpheus.ps1")
        print("    - Pour WS   : EXO doit etre lance (Get-EXOStatus).")
        return 2

    out.write_bytes(wav_bytes)
    print(f"\n[OK] WAV ecrit : {out}  ({len(wav_bytes)} bytes)  via {used.upper()}")

    info = analyze_wav(out)
    print("\n=== Format WAV ===")
    for k, v in info.items():
        print(f"  {k:<22} {v}")

    # Verdict format
    issues = []
    if info["sample_rate"] != 24000:
        issues.append(f"sample_rate={info['sample_rate']} (attendu 24000)")
    if info["channels"] != 1:
        issues.append(f"channels={info['channels']} (attendu 1)")
    if info["sample_width_bytes"] != 2:
        issues.append(f"sample_width={info['sample_width_bytes']} (attendu 2 = PCM16)")
    if info.get("clipping_pct", 0) > 0.5:
        issues.append(f"clipping eleve : {info['clipping_pct']}%")
    if info.get("near_silence_pct", 0) > 80:
        issues.append(f"silence dominant : {info['near_silence_pct']}%")
    if info["duration_s"] < 0.3:
        issues.append(f"duree tres courte : {info['duration_s']:.2f}s")

    print("\n=== Verdict format ===")
    if not issues:
        print("  [OK] WAV conforme : 24 kHz mono PCM16, contenu coherent.")
    else:
        print("  [WARN] anomalies detectees :")
        for i in issues:
            print(f"    - {i}")

    probe = maybe_ffprobe(out)
    if probe:
        print("\n=== ffprobe ===")
        print(probe)
    else:
        print("\n(ffprobe non installe -- skip)")

    print("\nProchaine etape :")
    print(f"  1) Lis {out} dans VLC.   -> reponds : 'VLC : OK' ou 'VLC : craque'")
    print(f"  2) Lis {out} dans WMP.   -> reponds : 'WMP : OK' ou 'WMP : craque'")
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
