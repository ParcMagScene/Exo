"""E2E test for the 4 new tool microservices."""
import asyncio
import json
import sys

import websockets


async def test_service(port, action, params, name):
    try:
        async with websockets.connect(f"ws://localhost:{port}", open_timeout=5) as ws:
            ready = await asyncio.wait_for(ws.recv(), timeout=5)
            ready_data = json.loads(ready)
            print(f"[{name}] Readiness: {ready_data.get('status', '?')}")

            msg = json.dumps({"action": action, "params": params})
            await ws.send(msg)
            resp = await asyncio.wait_for(ws.recv(), timeout=15)
            data = json.loads(resp)
            ok = data.get("ok", False)
            if ok:
                result = data.get("data", {})
                preview = str(result)[:150]
                print(f"[{name}] OK -> {preview}")
            else:
                print(f"[{name}] FAIL -> {data.get('error', 'unknown')}")
    except Exception as e:
        print(f"[{name}] ERROR: {type(e).__name__}: {e}")


async def main():
    print("=" * 60)
    print("E2E Test — 4 Tool Microservices")
    print("=" * 60)

    # Tools: calculate
    await test_service(8776, "calculate", {"expression": "2+2*3"}, "Tools/calc")

    # Tools: convert
    await test_service(8776, "convert", {"value": 100, "from_unit": "km", "to_unit": "miles"}, "Tools/conv")

    # Knowledge: Wikipedia summary
    await test_service(8775, "get_summary", {"topic": "Python (langage)", "lang": "fr"}, "Knowledge")

    # WebSearch: DuckDuckGo
    await test_service(8773, "search_web", {"query": "test websearch exo", "max_results": 3}, "WebSearch")

    # News: RSS
    await test_service(8774, "get_news", {"topic": "tech", "region": "fr", "max_results": 3}, "News")

    print("=" * 60)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
