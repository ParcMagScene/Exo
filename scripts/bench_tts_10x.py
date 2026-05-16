"""Bench charge : 10 syntheses TTS (1.5-4 s audio cible), mesure RTF + first_chunk + WS stabilite.

Sortie : D:\\EXO\\logs\\bench_tts_10x_<ts>.json
"""
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import websockets

# 10 phrases visant ~1.5 a 4 s d'audio chacune (RTF ~1.3 -> 30 a 130 chars).
PHRASES = [
    "Bonjour. Comment vas-tu aujourd'hui ?",
    "Quelle est la meteo prevue pour cet apres-midi a Paris ?",
    "OK, c'est note pour vingt heures.",
    "Je peux t'aider a programmer une alarme pour demain matin a sept heures et demie.",
    "Lance la lecture de la playlist detente sur l'enceinte du salon, s'il te plait.",
    "Voici la liste des taches que tu m'as confiees ce matin pour ta journee de travail.",
    "D'accord.",
    "Le rendez-vous chez le dentiste est confirme pour vendredi prochain a quatorze heures.",
    "Un nouveau message de Marie est arrive. Veux-tu que je te le lise maintenant ?",
    "Resume des actualites du jour : trois articles importants ont ete selectionnes pour toi.",
]


async def one(uri: str, text: str, idx: int):
    t0 = time.time()
    first_byte_ms = None
    n_bytes = 0
    end_msg = None
    ws_error = None
    try:
        async with websockets.connect(uri, max_size=None, open_timeout=5, close_timeout=2) as ws:
            msg = json.loads(await ws.recv())
            assert msg.get("type") == "ready", msg
            await ws.send(json.dumps({"type": "synthesize", "text": text, "voice": "amelie"}))
            while True:
                msg = await ws.recv()
                if isinstance(msg, (bytes, bytearray)):
                    if first_byte_ms is None:
                        first_byte_ms = (time.time() - t0) * 1000
                    n_bytes += len(msg)
                else:
                    obj = json.loads(msg)
                    if obj.get("type") == "end":
                        end_msg = obj
                        break
                    if obj.get("type") == "error":
                        ws_error = obj
                        break
    except Exception as e:
        ws_error = {"type": "exception", "msg": repr(e)}
    total_ms = (time.time() - t0) * 1000
    audio_s = n_bytes / 2 / 24000
    rtf = (end_msg or {}).get("rtf")
    status = "OK" if (end_msg and not ws_error) else f"FAIL({ws_error})"
    print(f"  [{idx:2d}] len={len(text):3d} first={first_byte_ms or -1:6.0f}ms "
          f"total={total_ms:7.0f}ms audio={audio_s:4.2f}s rtf={rtf} {status}")
    return {
        "idx": idx,
        "len": len(text),
        "text": text,
        "first_ms": first_byte_ms,
        "total_ms": total_ms,
        "audio_s": audio_s,
        "rtf": rtf,
        "ok": end_msg is not None and ws_error is None,
        "error": ws_error,
        "ts": datetime.now().isoformat(timespec="milliseconds"),
    }


async def main():
    uri = "ws://127.0.0.1:8767"
    print(f"=== Bench TTS x10 vers {uri} ===")
    print(f"Start: {datetime.now().isoformat(timespec='seconds')}")
    results = []
    t_start = time.time()
    for i, p in enumerate(PHRASES, 1):
        r = await one(uri, p, i)
        results.append(r)
        await asyncio.sleep(0.4)
    t_dur = time.time() - t_start

    ok = [r for r in results if r["ok"]]
    fails = [r for r in results if not r["ok"]]
    firsts = [r["first_ms"] for r in ok if r["first_ms"] is not None]
    rtfs = [r["rtf"] for r in ok if r["rtf"] is not None]
    audios = [r["audio_s"] for r in ok]

    summary = {
        "n_total": len(results),
        "n_ok": len(ok),
        "n_fail": len(fails),
        "duration_s": round(t_dur, 2),
        "first_ms": {
            "min": min(firsts) if firsts else None,
            "max": max(firsts) if firsts else None,
            "avg": round(sum(firsts) / len(firsts), 1) if firsts else None,
            "p50": sorted(firsts)[len(firsts) // 2] if firsts else None,
            "p90": sorted(firsts)[int(len(firsts) * 0.9)] if firsts else None,
        },
        "rtf": {
            "min": round(min(rtfs), 3) if rtfs else None,
            "max": round(max(rtfs), 3) if rtfs else None,
            "avg": round(sum(rtfs) / len(rtfs), 3) if rtfs else None,
        },
        "audio_s": {
            "min": round(min(audios), 2) if audios else None,
            "max": round(max(audios), 2) if audios else None,
            "avg": round(sum(audios) / len(audios), 2) if audios else None,
            "total": round(sum(audios), 2),
        },
    }

    print("\n=== RESUME ===")
    print(json.dumps(summary, indent=2))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(r"D:\EXO\logs") / f"bench_tts_10x_{ts}.json"
    out.write_text(json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8")
    print(f"\nSaved: {out}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
