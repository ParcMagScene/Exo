#!/usr/bin/env python3
"""
EXO v5.2 — WebSearch Server (WebSocket)
Port 8773 — Recherche web via DuckDuckGo (aucune clé API requise)

Protocol WebSocket :
  → JSON {"action":"search_web","params":{"query":"...","freshness":"week","max_results":5}}
  ← JSON {"ok":true,"data":{"results":[{"title":"...","url":"...","snippet":"..."}],"query":"..."}}
"""

import asyncio
import json
import logging
import sys
import traceback
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")

try:
    import aiohttp
except ImportError:
    raise SystemExit("pip install aiohttp")

# Singleton guard
from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9

logging.basicConfig(level=logging.INFO, format="%(asctime)s [WebSearch] %(message)s")
log = logging.getLogger("websearch_server")

PORT = 8773
MAX_RESULTS_LIMIT = 10

# Persistent aiohttp session (created in main())
_http_session: aiohttp.ClientSession | None = None

# ─────────────────────────────────────────────────────
#  DuckDuckGo HTML search (no API key needed)
# ─────────────────────────────────────────────────────

FRESHNESS_MAP = {
    "day": "d",
    "week": "w",
    "month": "m",
    "year": "y",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
}


async def search_duckduckgo(
    query: str,
    freshness: str = "",
    max_results: int = 5,
) -> list[dict[str, str]]:
    """Recherche DuckDuckGo via l'API Lite HTML (pas de JS requis)."""
    max_results = min(max_results, MAX_RESULTS_LIMIT)
    params: dict[str, Any] = {"q": query, "kl": "fr-fr"}

    if freshness in FRESHNESS_MAP:
        params["df"] = FRESHNESS_MAP[freshness]

    url = "https://lite.duckduckgo.com/lite/"

    results: list[dict[str, str]] = []
    try:
        session = _http_session or aiohttp.ClientSession(headers=HEADERS)
        async with session.post(url, data=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                log.warning("DuckDuckGo HTTP %d", resp.status)
                return results
            html = await resp.text()

        # Parse simple du HTML lite de DuckDuckGo
        results = _parse_ddg_lite(html, max_results)
    except asyncio.TimeoutError:
        log.warning("DuckDuckGo timeout pour: %s", query)
    except Exception as exc:
        log.error("DuckDuckGo erreur: %s", exc)

    return results


def _parse_ddg_lite(html: str, max_results: int) -> list[dict[str, str]]:
    """Parse le HTML de DuckDuckGo Lite pour extraire les résultats."""
    import re

    results: list[dict[str, str]] = []

    # Pattern: liens de résultats dans les <a class="result-link">
    # DDG Lite utilise des tables avec des liens
    link_pattern = re.compile(
        r'<a[^>]+rel="nofollow"[^>]+href="([^"]+)"[^>]*>\s*(.*?)\s*</a>',
        re.DOTALL,
    )
    # Snippets dans les <td class="result-snippet">
    snippet_pattern = re.compile(
        r'<td\s+class="result-snippet"[^>]*>\s*(.*?)\s*</td>',
        re.DOTALL,
    )

    links = link_pattern.findall(html)
    snippets = snippet_pattern.findall(html)

    for i, (href, title) in enumerate(links):
        if i >= max_results:
            break
        # Nettoyer le HTML des titres et snippets
        clean_title = re.sub(r"<[^>]+>", "", title).strip()
        clean_snippet = ""
        if i < len(snippets):
            clean_snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()

        if href and clean_title and not href.startswith("/"):
            results.append({
                "title": clean_title,
                "url": href,
                "snippet": clean_snippet,
            })

    return results


# ─────────────────────────────────────────────────────
#  WebSocket handler
# ─────────────────────────────────────────────────────

async def handle_client(ws: Any) -> None:
    """Gère une connexion WebSocket cliente."""
    peer = ws.remote_address
    log.info("Client connecté: %s", peer)

    # ReadinessProtocol v5
    await ws.send(json.dumps({
        "type": "ready",
        "service": "websearch",
        "port": PORT,
    }))

    async for raw in ws:
        # v9 protocol: ping, health, metrics, traces, errors
        v9_resp = await _v9.handle_ws_message(ws, raw)
        if v9_resp is not None:
            await ws.send(v9_resp)
            continue

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await ws.send(json.dumps({"ok": False, "error": "JSON invalide"}))
            continue

        action = msg.get("action", "")
        params = msg.get("params", {})

        if action == "search_web":
            query = params.get("query", "").strip()
            if not query:
                await ws.send(json.dumps({"ok": False, "error": "query manquant"}))
                continue

            freshness = params.get("freshness", "")
            max_results = min(int(params.get("max_results", 5)), MAX_RESULTS_LIMIT)

            log.info("Recherche: %r (freshness=%s, max=%d)", query, freshness, max_results)

            results = await search_duckduckgo(query, freshness, max_results)

            await ws.send(json.dumps({
                "ok": True,
                "data": {
                    "query": query,
                    "results": results,
                    "count": len(results),
                },
            }, ensure_ascii=False))
        else:
            await ws.send(json.dumps({"ok": False, "error": f"action inconnue: {action}"}))

    log.info("Client déconnecté: %s", peer)


async def main() -> None:
    global _http_session, _v9
    ensure_single_instance(PORT, "websearch_server")
    _v9 = init_v9("websearch_server", PORT)
    log.info("Démarrage WebSearch Server sur le port %d", PORT)

    _http_session = aiohttp.ClientSession(headers=HEADERS)
    try:
        async with websockets.serve(handle_client, "localhost", PORT,
                                    **_v9.ws_serve_kwargs()):
            log.info("WebSearch Server prêt — ws://localhost:%d", PORT)
            await asyncio.Future()  # run forever
    finally:
        await _http_session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Arrêt WebSearch Server")
