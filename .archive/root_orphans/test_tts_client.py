import asyncio
import websockets
import json

async def test_tts():
    uri = "ws://localhost:8767"
    chunks = 0
    try:
        async with websockets.connect(uri) as websocket:
            msg = {
                "type": "synthesize",
                "text": "Bonjour, je suis EXO.",
                "voice": "exo_default",
                "lang": "fr",
                "rate": 1.0,
                "pitch": 1.0
            }
            await websocket.send(json.dumps(msg))
            while True:
                response = await websocket.recv()
                if isinstance(response, bytes):
                    chunks += 1
                else:
                    data = json.loads(response)
                    if data.get("type") == "end":
                        break
        print(f"SUCCESS: Received {chunks} chunks")
    except Exception as e:
        print(f"ERROR: {e}")

asyncio.run(test_tts())
