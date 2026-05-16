"""Quick FR pipeline validation against the running TTS server.

Sends 3 phrases sequentially and prints latency + chunk metrics.
"""
import asyncio
import json
import time

import websockets

URI = "ws://localhost:8767"
PHRASES = [
    "Bonjour, ceci est un test de synthèse vocale en français.",
    "Je parle normalement, avec des liaisons et une prosodie naturelle.",
    "Les nombres 42, 2026 et 3,14 doivent être lus en français.",
]


async def synth_one(idx: int, text: str) -> dict:
    chunks = 0
    bytes_total = 0
    t_first = None
    t0 = time.monotonic()
    end_payload = None
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
            msg = await ws.recv()
            if isinstance(msg, (bytes, bytearray)):
                chunks += 1
                bytes_total += len(msg)
                if t_first is None:
                    t_first = time.monotonic() - t0
            else:
                data = json.loads(msg)
                if data.get("type") in ("end", "error"):
                    end_payload = data
                    break
    total = time.monotonic() - t0
    return {
        "idx": idx,
        "text": text,
        "chunks": chunks,
        "bytes": bytes_total,
        "first_chunk_ms": int((t_first or total) * 1000),
        "total_ms": int(total * 1000),
        "end": end_payload,
    }


async def main():
    results = []
    for i, ph in enumerate(PHRASES, 1):
        try:
            r = await synth_one(i, ph)
        except Exception as exc:
            r = {"idx": i, "text": ph, "error": str(exc)}
        results.append(r)
        print(json.dumps(r, ensure_ascii=False))
    print("---SUMMARY---")
    print(json.dumps(results, ensure_ascii=False, indent=2))


asyncio.run(main())
