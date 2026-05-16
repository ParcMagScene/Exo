#!/usr/bin/env python3
"""

# Patch global EXO : forcer le working directory à D:/EXO/ pour tous les services
import os
os.chdir("D:/EXO/")
EXO v5.2 — Knowledge Server (WebSocket)
Port 8775 — Accès encyclopédique via Wikipedia API (aucune clé API requise)

Protocol WebSocket :
  → JSON {"action":"get_summary","params":{"topic":"Intelligence artificielle"}}
  ← JSON {"ok":true,"data":{"title":"...","summary":"...","url":"...","categories":[]}}
"""

import asyncio
try:
    import ujson as json  # v6.0 perf : 3-5x plus rapide que stdlib (audit perf)
except ImportError:
    import json
import logging
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

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


# --- Logging EXO centralisé (identique C++) ---
import os
from pathlib import Path
def _get_exo_logfile():
    # Correction : tous les logs doivent aller dans D:/EXO/logs/
    log_dir = os.environ.get("EXO_LOGS_DIR", "D:/EXO/logs")
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    ts = os.environ.get("EXO_SESSION_TIMESTAMP")
    if not ts:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(log_dir, f"exo_{ts}.log")

logfile = _get_exo_logfile()

_file_handler = logging.FileHandler(logfile, encoding="utf-8", delay=False)
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [Knowledge] %(message)s"))
_file_handler.flush = _file_handler.stream.flush
log = logging.getLogger("knowledge_server")
log.addHandler(_file_handler)
log.propagate = True
log.info("=== EXO KNOWLEDGE_SERVER STARTUP ===")
_file_handler.flush()

PORT = 8775

WIKI_API = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
WIKI_SEARCH = "https://{lang}.wikipedia.org/w/api.php"

HEADERS = {
    "User-Agent": "EXO-Assistant/5.2 (https://github.com/AlexanderVDF/EXO; exo-assistant@users.noreply.github.com)",
    "Accept": "application/json",
}


async def wikipedia_search(
    session: aiohttp.ClientSession,
    query: str,
    lang: str = "fr",
) -> str | None:
    """Recherche Wikipedia pour trouver le titre exact d'un article."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": "1",
        "format": "json",
    }
    url = WIKI_SEARCH.format(lang=lang)
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            results = data.get("query", {}).get("search", [])
            if results:
                return results[0]["title"]
    except (asyncio.TimeoutError, aiohttp.ClientError, KeyError) as exc:
        log.warning("Wikipedia search error: %s", exc)
    return None


async def wikipedia_summary(
    session: aiohttp.ClientSession,
    title: str,
    lang: str = "fr",
) -> dict[str, Any] | None:
    """Récupère le résumé Wikipedia via l'API REST."""
    url = WIKI_API.format(lang=lang, title=quote(title.replace(" ", "_"), safe="()"))
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 404:
                return None
            if resp.status != 200:
                log.warning("Wikipedia API HTTP %d pour %s", resp.status, title)
                return None
            data = await resp.json()
    except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
        log.warning("Wikipedia API error: %s", exc)
        return None

    extract = data.get("extract", "")
    if not extract:
        return None

    return {
        "title": data.get("title", title),
        "summary": extract,
        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        "description": data.get("description", ""),
        "thumbnail": data.get("thumbnail", {}).get("source", ""),
    }


async def get_summary(topic: str, lang: str = "fr") -> dict[str, Any]:
    """Point d'entrée : recherche + résumé Wikipedia."""
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # D'abord essayer directement le titre
        result = await wikipedia_summary(session, topic, lang)
        if result:
            return result

        # Sinon, rechercher le bon titre
        title = await wikipedia_search(session, topic, lang)
        if title:
            result = await wikipedia_summary(session, title, lang)
            if result:
                return result

        # Fallback en anglais si le français ne donne rien
        if lang != "en":
            title = await wikipedia_search(session, topic, "en")
            if title:
                result = await wikipedia_summary(session, title, "en")
                if result:
                    result["note"] = "Résultat en anglais (article français non trouvé)"
                    return result

    return {"title": topic, "summary": f"Aucun article trouvé pour « {topic} ».", "url": ""}


# ─────────────────────────────────────────────────────
#  WebSocket handler
# ─────────────────────────────────────────────────────

async def handle_client(ws: Any) -> None:
    peer = ws.remote_address
    log.info("Client connecté: %s", peer)

    # ReadinessProtocol v5
    await ws.send(json.dumps({
        "type": "ready",
        "service": "knowledge",
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

        if action == "get_summary":
            topic = params.get("topic", "").strip()
            if not topic:
                await ws.send(json.dumps({"ok": False, "error": "topic manquant"}))
                continue

            lang = params.get("lang", "fr")
            log.info("Recherche encyclopédique: %r (lang=%s)", topic, lang)

            data = await get_summary(topic, lang)

            await ws.send(json.dumps({
                "ok": True,
                "data": data,
            }, ensure_ascii=False))
        else:
            await ws.send(json.dumps({"ok": False, "error": f"action inconnue: {action}"}))

    log.info("Client déconnecté: %s", peer)


async def main() -> None:
    global _v9
    ensure_single_instance(PORT, "knowledge_server")
    _v9 = init_v9("knowledge_server", PORT)
    log.info("Démarrage Knowledge Server sur le port %d", PORT)

    async with websockets.serve(handle_client, "localhost", PORT,
                                **_v9.ws_serve_kwargs()):
        log.info("Knowledge Server prêt — ws://localhost:%d", PORT)
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Arrêt Knowledge Server")
