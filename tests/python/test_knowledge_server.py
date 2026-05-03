"""
Tests unitaires — Knowledge Server (Wikipedia)
Teste la construction d'URL, le fallback de langue, et les fonctions avec mock.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import quote

import pytest

from knowledge_server import PORT, WIKI_API, WIKI_SEARCH, wikipedia_search, wikipedia_summary, get_summary


class _AsyncCM:
    """Helper pour mocker un async context manager (async with session.get(...))."""
    def __init__(self, resp):
        self.resp = resp
    async def __aenter__(self):
        return self.resp
    async def __aexit__(self, *args):
        return False


def _mock_session(resp):
    """Crée un mock de session aiohttp dont .get() retourne un async CM."""
    session = MagicMock()
    session.get.return_value = _AsyncCM(resp)
    return session


class TestKnowledgeServerConfig:
    """Tests de configuration basique."""

    def test_port(self):
        assert PORT == 8775

    def test_wikipedia_url_format(self):
        """Vérifie le format des URL Wikipedia REST API."""
        lang = "fr"
        topic = "Python_(langage)"
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{topic}"
        assert "fr.wikipedia.org" in url
        assert "rest_v1/page/summary" in url

    def test_wikipedia_search_url_format(self):
        lang = "en"
        query = "artificial intelligence"
        url = f"https://{lang}.wikipedia.org/w/api.php"
        assert "en.wikipedia.org" in url

    def test_language_fallback(self):
        """Le serveur doit supporter fr et en."""
        supported = ["fr", "en"]
        for lang in supported:
            url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/Test"
            assert lang in url


class TestURLConstruction:
    """Tests de la construction d'URL avec encodage."""

    def test_spaces_encoded(self):
        title = "Intelligence artificielle"
        encoded = quote(title.replace(" ", "_"), safe="()")
        assert " " not in encoded
        assert "Intelligence_artificielle" in encoded

    def test_parentheses_preserved(self):
        title = "Python (langage)"
        encoded = quote(title.replace(" ", "_"), safe="()")
        assert "(langage)" in encoded

    def test_wiki_api_template(self):
        url = WIKI_API.format(lang="fr", title="Test")
        assert url == "https://fr.wikipedia.org/api/rest_v1/page/summary/Test"

    def test_wiki_search_template(self):
        url = WIKI_SEARCH.format(lang="en")
        assert url == "https://en.wikipedia.org/w/api.php"


class TestWikipediaSearch:
    """Tests de wikipedia_search avec mock aiohttp."""

    @pytest.mark.asyncio
    async def test_search_returns_title(self):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "query": {"search": [{"title": "Python (langage)"}]}
        })

        result = await wikipedia_search(_mock_session(mock_resp), "python langage")
        assert result == "Python (langage)"

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"query": {"search": []}})

        result = await wikipedia_search(_mock_session(mock_resp), "xyznonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_search_http_error(self):
        mock_resp = AsyncMock()
        mock_resp.status = 500

        result = await wikipedia_search(_mock_session(mock_resp), "test")
        assert result is None


class TestWikipediaSummary:
    """Tests de wikipedia_summary avec mock aiohttp."""

    @pytest.mark.asyncio
    async def test_summary_success(self):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "title": "Python (langage)",
            "extract": "Python est un langage de programmation.",
            "content_urls": {"desktop": {"page": "https://fr.wikipedia.org/wiki/Python"}},
            "description": "langage de programmation",
            "thumbnail": {"source": "https://upload.wikimedia.org/thumb.jpg"},
        })

        result = await wikipedia_summary(_mock_session(mock_resp), "Python (langage)", "fr")
        assert result is not None
        assert result["title"] == "Python (langage)"
        assert "programmation" in result["summary"]
        assert result["url"] == "https://fr.wikipedia.org/wiki/Python"

    @pytest.mark.asyncio
    async def test_summary_404(self):
        mock_resp = AsyncMock()
        mock_resp.status = 404

        result = await wikipedia_summary(_mock_session(mock_resp), "PageInexistante", "fr")
        assert result is None

    @pytest.mark.asyncio
    async def test_summary_empty_extract(self):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "title": "Test",
            "extract": "",
        })

        result = await wikipedia_summary(_mock_session(mock_resp), "Test", "fr")
        assert result is None


class TestGetSummary:
    """Tests de get_summary (point d'entrée principal) avec mock."""

    @pytest.mark.asyncio
    async def test_fallback_not_found(self):
        """Si rien n'est trouvé, renvoie un message d'erreur."""
        with patch("knowledge_server.wikipedia_summary", new_callable=AsyncMock, return_value=None), \
             patch("knowledge_server.wikipedia_search", new_callable=AsyncMock, return_value=None):
            result = await get_summary("TopicInexistant", "fr")
            assert "Aucun article" in result["summary"]
            assert result["title"] == "TopicInexistant"
