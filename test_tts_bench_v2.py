"""Bench TTS WS comparatif: pointe sur un port donné via argv."""
import asyncio, json, time, sys, hashlib
import websockets

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8867
URI = f"ws://localhost:{PORT}"
SAMPLE_RATE = 24000
PHRASES = [
    "Bonjour, ceci est un test de synthèse vocale en français.",
    "Je parle normalement, avec des liaisons et une prosodie naturelle.",
    "Les nombres 42, 2026 et 3,14 doivent être lus en français.",
]

async def synth_one(idx: int, text: str):
    chunks = 0
    total_bytes = 0
    first_chunk_ms = None
    md5 = hashlib.md5()
    end_meta = None
    t0 = time.monotonic()
    async with websockets.connect(URI, max_size=None) as ws:
        # consume ready
        try:
            ready = await asyncio.wait_for(ws.recv(), timeout=5.0)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({
            "type": "synthesize", "text": text, "voice": "exo_default",
            "lang": "fr", "rate": 1.0,
        }))
        t0 = time.monotonic()
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=120.0)
            except asyncio.TimeoutError:
                print(f"[{idx}] TIMEOUT")
                break
            if isinstance(msg, (bytes, bytearray)):
                if first_chunk_ms is None:
                    first_chunk_ms = (time.monotonic() - t0) * 1000
                chunks += 1
                total_bytes += len(msg)
                md5.update(msg)
            else:
                try:
                    data = json.loads(msg)
                except Exception:
                    continue
                if data.get("type") in ("end", "complete", "done"):
                    end_meta = data
                    break
                if data.get("type") == "error":
                    print(f"[{idx}] ERROR: {data}"); break
    total_ms = (time.monotonic() - t0) * 1000
    audio_sec = (total_bytes / 2) / SAMPLE_RATE if total_bytes else 0.0
    rtf = (total_ms / 1000.0) / audio_sec if audio_sec > 0 else float("inf")
    digest = md5.hexdigest()[:12]
    print(f"[{idx}] first={first_chunk_ms:.0f}ms total={total_ms:.0f}ms "
          f"chunks={chunks} audio={audio_sec:.2f}s RTF={rtf:.2f} md5={digest}")
    if end_meta:
        print(f"     server_end={end_meta}")
    return first_chunk_ms, total_ms, chunks, audio_sec, rtf, digest

async def main():
    print(f"=== Bench TTS @ {URI} ===")
    digests = []
    for i, p in enumerate(PHRASES, 1):
        try:
            r = await synth_one(i, p)
            digests.append(r[5] if r else None)
        except Exception as e:
            print(f"[{i}] EXC: {e}")
            digests.append(None)
        await asyncio.sleep(0.3)
    print("\n=== UNIQUENESS CHECK ===")
    if len(set(d for d in digests if d)) == len([d for d in digests if d]):
        print("  OK: tous les audios diffèrent (md5 distincts)")
    else:
        print(f"  KO: collisions détectées -> {digests}")

if __name__ == "__main__":
    asyncio.run(main())
