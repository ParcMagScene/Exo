"""Bench rapide : 5 syntheses TTS, mesure RTF + first_chunk_ms."""
import asyncio
import json
import sys
import time

import websockets

PHRASES = [
    "Bonjour. Comment vas-tu ?",
    "Quelle est la meteo aujourd'hui a Paris ?",
    "Je peux t'aider a programmer une alarme pour demain matin a sept heures.",
    "OK, c'est note.",
    "Voici la liste des taches que tu m'as confiees ce matin pour ta journee.",
]


async def one(uri: str, text: str, idx: int):
    t0 = time.time()
    first_byte_ms = None
    n_bytes = 0
    end_msg = None
    async with websockets.connect(uri, max_size=None) as ws:
        # attendre 'ready'
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
                    print(f"  ERR: {obj}")
                    return None
    total_ms = (time.time() - t0) * 1000
    print(f"  [{idx}] len={len(text):3d} first={first_byte_ms:6.0f}ms total={total_ms:7.1f}ms "
          f"audio={(n_bytes/2/24000):.2f}s rtf={(end_msg or {}).get('rtf', '?')}")
    return {
        "len": len(text),
        "first_ms": first_byte_ms,
        "total_ms": total_ms,
        "rtf": (end_msg or {}).get("rtf"),
        "audio_s": n_bytes / 2 / 24000,
    }


async def main():
    uri = "ws://127.0.0.1:8767"
    results = []
    for i, p in enumerate(PHRASES, 1):
        r = await one(uri, p, i)
        if r:
            results.append(r)
        await asyncio.sleep(0.5)
    print("\n=== RESUME ===")
    if results:
        firsts = [r["first_ms"] for r in results]
        rtfs = [r["rtf"] for r in results if r["rtf"] is not None]
        print(f"first_chunk_ms : min={min(firsts):.0f} max={max(firsts):.0f} avg={sum(firsts)/len(firsts):.0f}")
        if rtfs:
            print(f"rtf            : min={min(rtfs):.2f} max={max(rtfs):.2f} avg={sum(rtfs)/len(rtfs):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
