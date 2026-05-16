#!/usr/bin/env python3
"""
EXO v5.2 — News Server (WebSocket)
Port 8774 — Actualités via RSS feeds publics (aucune clé API requise)

Protocol WebSocket :
  → JSON {"action":"get_news","params":{"topic":"tech","region":"fr","timeframe":"24h"}}
  ← JSON {"ok":true,"data":{"articles":[{"title":"...","source":"...","summary":"...","url":"...","published":"..."}]}}
"""

# Patch global EXO : forcer le working directory à D:/EXO/ pour tous les services
import os
os.chdir("D:/EXO/")

import asyncio
try:
    import ujson as json  # v6.0 perf : 3-5x plus rapide que stdlib (audit perf)
except ImportError:
    import json
import logging
import sys
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

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
_file_handler.setFormatter(logging.Formatter("%(asctime)s [News] %(message)s"))
_file_handler.flush = _file_handler.stream.flush
log = logging.getLogger("news_server")
log.addHandler(_file_handler)
log.propagate = True
log.info("=== EXO NEWS_SERVER STARTUP ===")
_file_handler.flush()

PORT = 8774

# Persistent aiohttp session (created in main())
_http_session: aiohttp.ClientSession | None = None

# ─────────────────────────────────────────────────────
#  RSS Feeds — sources publiques gratuites
# ─────────────────────────────────────────────────────

RSS_FEEDS: dict[str, dict[str, list[str]]] = {
    "fr": {
        "general": [
            "https://www.lemonde.fr/rss/une.xml",
            "https://www.france24.com/fr/rss",
        ],
        "tech": [
            "https://www.01net.com/feed/",
            "https://www.numerama.com/feed/",
        ],
        "science": [
            "https://www.futura-sciences.com/rss/actualites.xml",
        ],
        "world": [
            "https://www.france24.com/fr/rss",
        ],
    },
    "en": {
        "general": [
            "https://feeds.bbci.co.uk/news/rss.xml",
        ],
        "tech": [
            "https://feeds.arstechnica.com/arstechnica/index",
        ],
        "science": [
            "https://www.newscientist.com/section/news/feed/",
        ],
        "world": [
            "https://feeds.bbci.co.uk/news/world/rss.xml",
        ],
    },
}

HEADERS = {
    "User-Agent": "EXO-Assistant/5.2 (NewsReader)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}


def _clean_html(text: str) -> str:
    """Retire les balises HTML d'un texte."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_rss_date(date_str: str) -> datetime | None:
    """Parse les dates RSS (RFC 2822 et ISO 8601)."""
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


async def fetch_rss(session: aiohttp.ClientSession, url: str) -> list[dict[str, str]]:
    """Télécharge et parse un flux RSS."""
    articles: list[dict[str, str]] = []
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                log.warning("RSS %s → HTTP %d", url, resp.status)
                return articles
            content = await resp.text()
    except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
        log.warning("RSS %s → %s", url, exc)
        return articles

    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        log.warning("RSS %s → XML invalide", url)
        return articles

    # RSS 2.0 : channel/item
    items = root.findall(".//item")
    # Atom : entry
    if not items:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//atom:entry", ns)

    for item in items[:10]:  # Max 10 par feed
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description") or item.find("summary")
        date_el = item.find("pubDate") or item.find("published") or item.find("updated")

        title = _clean_html(title_el.text or "") if title_el is not None and title_el.text else ""
        link = ""
        if link_el is not None:
            link = link_el.text or link_el.get("href", "")
        summary = _clean_html(desc_el.text or "") if desc_el is not None and desc_el.text else ""
        published = date_el.text.strip() if date_el is not None and date_el.text else ""

        # Tronquer le résumé
        if len(summary) > 300:
            summary = summary[:297] + "..."

        if title:
            articles.append({
                "title": title,
                "url": link,
                "summary": summary,
                "published": published,
                "source": url.split("/")[2],  # domaine
            })

    return articles


async def get_news(
    topic: str = "general",
    region: str = "fr",
    timeframe: str = "24h",
    max_articles: int = 8,
) -> list[dict[str, str]]:
    """Récupère les actualités par thème et région."""
    region = region.lower() if region.lower() in RSS_FEEDS else "fr"
    topic = topic.lower() if topic.lower() in RSS_FEEDS[region] else "general"

    feeds = RSS_FEEDS[region][topic]

    # Charger tous les feeds en parallèle
    session = _http_session or aiohttp.ClientSession(headers=HEADERS)
    tasks = [fetch_rss(session, url) for url in feeds]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    articles: list[dict[str, str]] = []
    for result in all_results:
        if isinstance(result, list):
            articles.extend(result)

    # Filtrage par timeframe
    now = datetime.now(timezone.utc)
    if timeframe == "24h":
        cutoff = now - timedelta(hours=24)
    elif timeframe == "7d":
        cutoff = now - timedelta(days=7)
    else:
        cutoff = now - timedelta(hours=24)

    filtered: list[dict[str, str]] = []
    for article in articles:
        pub_date = _parse_rss_date(article.get("published", ""))
        if pub_date is None:
            filtered.append(article)  # Garder si date non parsable
        elif pub_date.replace(tzinfo=timezone.utc if pub_date.tzinfo is None else pub_date.tzinfo) >= cutoff:
            filtered.append(article)

    # Déduplications par titre
    seen_titles: set[str] = set()
    unique: list[dict[str, str]] = []
    for article in filtered:
        key = article["title"].lower().strip()
        if key not in seen_titles:
            seen_titles.add(key)
            unique.append(article)

    return unique[:max_articles]


# ─────────────────────────────────────────────────────
#  WebSocket handler
# ─────────────────────────────────────────────────────

async def handle_client(ws: Any) -> None:
    peer = ws.remote_address
    log.info("Client connecté: %s", peer)

    # ReadinessProtocol v5
    await ws.send(json.dumps({
        "type": "ready",
        "service": "news",
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

        if action == "get_news":
            topic = params.get("topic", "general")
            region = params.get("region", "fr")
            timeframe = params.get("timeframe", "24h")

            log.info("News: topic=%s region=%s timeframe=%s", topic, region, timeframe)

            articles = await get_news(topic, region, timeframe)

            await ws.send(json.dumps({
                "ok": True,
                "data": {
                    "topic": topic,
                    "region": region,
                    "timeframe": timeframe,
                    "articles": articles,
                    "count": len(articles),
                },
            }, ensure_ascii=False))
        else:
            await ws.send(json.dumps({"ok": False, "error": f"action inconnue: {action}"}))

    log.info("Client déconnecté: %s", peer)


async def main() -> None:
    global _http_session, _v9
    ensure_single_instance(PORT, "news_server")
    _v9 = init_v9("news_server", PORT)
    log.info("Démarrage News Server sur le port %d", PORT)

    _http_session = aiohttp.ClientSession(headers=HEADERS)
    try:
        async with websockets.serve(handle_client, "localhost", PORT,
                                    **_v9.ws_serve_kwargs()):
            log.info("News Server prêt — ws://localhost:%d", PORT)
            await asyncio.Future()
    finally:
        await _http_session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Arrêt News Server")
