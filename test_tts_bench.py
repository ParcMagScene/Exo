"""Benchmark TTS WS: mesure first_chunk_ms, total_ms, chunks, RTF."""
import asyncio, json, time, sys
import websockets

URI = "ws://localhost:8767"
SAMPLE_RATE = 24000  # PCM16 mono 24 kHz
PHRASES = [
    "Bonjour, ceci est un test de synthèse vocale en français.",
    "Je parle normalement, avec des liaisons et une prosodie naturelle.",
    "Les nombres 42, 2026 et 3,14 doivent être lus en français.",
]

async def synth_one(idx: int, text: str):
    chunks = 0
    total_bytes = 0
    first_chunk_ms = None
    t0 = time.monotonic()
    async with websockets.connect(URI, max_size=None) as ws:
        await ws.send(json.dumps({
            "type": "synthesize",
            "text": text,
            "voice": "exo_default",
            "lang": "fr",
            "rate": 1.0,
            "pitch": 1.0,
        }))
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=60.0)
            except asyncio.TimeoutError:
                print(f"[{idx}] TIMEOUT après {(time.monotonic()-t0)*1000:.0f} ms")
                break
            if isinstance(msg, (bytes, bytearray)):
                if first_chunk_ms is None:
                    first_chunk_ms = (time.monotonic() - t0) * 1000
                chunks += 1
                total_bytes += len(msg)
            else:
                try:
                    data = json.loads(msg)
                except Exception:
                    continue
                if data.get("type") in ("end", "complete", "done"):
                    break
                if data.get("type") == "error":
                    print(f"[{idx}] ERROR msg: {data}")
                    break
    total_ms = (time.monotonic() - t0) * 1000
    audio_sec = (total_bytes / 2) / SAMPLE_RATE if total_bytes else 0.0
    rtf = (total_ms / 1000.0) / audio_sec if audio_sec > 0 else float("inf")
    print(f"[{idx}] text={text!r}")
    print(f"     first_chunk_ms={first_chunk_ms:.0f}  total_ms={total_ms:.0f}  chunks={chunks}  audio={audio_sec:.2f}s  RTF={rtf:.2f}")
    return first_chunk_ms, total_ms, chunks, audio_sec, rtf

async def main():
    results = []
    for i, p in enumerate(PHRASES, 1):
        try:
            r = await synth_one(i, p)
            results.append(r)
        except Exception as e:
            print(f"[{i}] EXC: {e}")
            results.append(None)
        await asyncio.sleep(0.5)
    print("\n=== SUMMARY ===")
    for i, r in enumerate(results, 1):
        if r is None:
            print(f"  #{i}: FAILED")
        else:
            fc, tot, n, sec, rtf = r
            print(f"  #{i}: first={fc:.0f}ms total={tot:.0f}ms chunks={n} audio={sec:.2f}s RTF={rtf:.2f}")

if __name__ == "__main__":
    asyncio.run(main())
