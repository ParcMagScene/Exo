"""Capture le PCM streaming d'Orpheus WS et l'écrit en WAV pour A/B avec batch."""
import asyncio
import json
import struct
import sys
import wave

import websockets

URI = "ws://127.0.0.1:8767"
TEXT = "Bonjour, je suis Orphee, votre assistant vocal francais."
OUT = "orpheus_stream_capture.wav"
SR = 24000


async def main():
    pcm = bytearray()
    chunks = 0
    async with websockets.connect(URI, max_size=None) as ws:
        # attendre ready
        msg = await ws.recv()
        print("server:", msg)
        await ws.send(json.dumps({
            "type": "synthesize",
            "text": TEXT,
            "voice": "pierre",
            "lang": "fr",
            "rate": 1.0,
            "pitch": 1.0,
        }))
        while True:
            r = await ws.recv()
            if isinstance(r, bytes):
                pcm.extend(r)
                chunks += 1
            else:
                data = json.loads(r)
                t = data.get("type")
                print("msg:", data)
                if t in ("end", "error", "done"):
                    break

    with wave.open(OUT, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(bytes(pcm))
    dur = len(pcm) / 2 / SR
    print(f"[ok] {OUT} chunks={chunks} bytes={len(pcm)} duration={dur:.2f}s")


asyncio.run(main())
