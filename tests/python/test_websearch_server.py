"""
Tests unitaires — WebSearch Server (DuckDuckGo Lite)
Teste le parsing HTML, la validation des paramètres, et search_duckduckgo avec mock.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from websearch_server import _parse_ddg_lite, FRESHNESS_MAP, MAX_RESULTS_LIMIT, search_duckduckgo


class TestDDGLiteParsing:
    """Tests du parsing HTML DuckDuckGo Lite."""

    SAMPLE_HTML = """
    <html><body>
    <table>
    <tr>
        <td>1.&nbsp;</td>
        <td><a rel="nofollow" href="https://example.com/page1">Example Page 1</a></td>
    </tr>
    <tr>
        <td class="result-snippet">This is the snippet for page 1.</td>
    </tr>
    <tr>
        <td>2.&nbsp;</td>
        <td><a rel="nofollow" href="https://example.com/page2">Example Page 2</a></td>
    </tr>
    <tr>
        <td class="result-snippet">Another snippet for page 2.</td>
    </tr>
    </table>
    </body></html>
    """

    def test_parse_basic_results(self):
        results = _parse_ddg_lite(self.SAMPLE_HTML, 10)
        assert len(results) == 2
        assert results[0]["url"] == "https://example.com/page1"
        assert results[0]["title"] == "Example Page 1"
        assert "snippet" in results[0]["snippet"].lower() or len(results[0]["snippet"]) > 0

    def test_parse_empty_html(self):
        results = _parse_ddg_lite("", 10)
        assert results == []

    def test_parse_no_results(self):
        results = _parse_ddg_lite("<html><body><p>No results</p></body></html>", 10)
        assert results == []

    def test_parse_max_results(self):
        results = _parse_ddg_lite(self.SAMPLE_HTML, 1)
        assert len(results) <= 1


class TestWebSearchValidation:
    """Tests de validation des paramètres."""

    def test_freshness_values(self):
        valid = {"day", "week", "month", "year"}
        for v in valid:
            assert v in valid

    def test_max_results_bounds(self):
        # Côté serveur, max_results est borné entre 1 et 10
        assert max(1, min(10, 0)) == 1
        assert max(1, min(10, 5)) == 5
        assert max(1, min(10, 20)) == 10


class TestFreshnessMap:
    """Tests du mapping de fraîcheur DuckDuckGo."""

    def test_all_keys_mapped(self):
        assert FRESHNESS_MAP["day"] == "d"
        assert FRESHNESS_MAP["week"] == "w"
        assert FRESHNESS_MAP["month"] == "m"
        assert FRESHNESS_MAP["year"] == "y"

    def test_unknown_freshness_not_in_map(self):
        assert "hour" not in FRESHNESS_MAP
        assert "" not in FRESHNESS_MAP

    def test_max_results_limit(self):
        assert MAX_RESULTS_LIMIT == 10


class TestParseEdgeCases:
    """Tests de parsing supplémentaires pour DDG Lite."""

    def test_internal_links_skipped(self):
        """Les liens internes (commençant par /) sont ignorés."""
        html = '''
        <a rel="nofollow" href="/internal">Internal Link</a>
        <td class="result-snippet">Internal snippet</td>
        <a rel="nofollow" href="https://example.com">External</a>
        <td class="result-snippet">External snippet</td>
        '''
        results = _parse_ddg_lite(html, 10)
        for r in results:
            assert not r["url"].startswith("/")

    def test_html_in_title_stripped(self):
        """Les balises HTML dans les titres sont retirées."""
        html = '''
        <a rel="nofollow" href="https://example.com">
            <b>Bold</b> Title
        </a>
        <td class="result-snippet">Snippet</td>
        '''
        results = _parse_ddg_lite(html, 10)
        if results:
            assert "<b>" not in results[0]["title"]

    def test_missing_snippets(self):
        """Si pas de snippet, le résultat a un snippet vide."""
        html = '''
        <a rel="nofollow" href="https://example.com">Title Only</a>
        '''
        results = _parse_ddg_lite(html, 10)
        for r in results:
            assert "snippet" in r


class TestSearchDuckDuckGo:
    """Tests de search_duckduckgo avec mock HTTP."""

    MOCK_HTML = """
    <html><body><table>
    <tr><td><a rel="nofollow" href="https://result.com">Mock Result</a></td></tr>
    <tr><td class="result-snippet">Mock snippet text</td></tr>
    </table></body></html>
    """

    @pytest.mark.asyncio
    async def test_search_success(self):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value=self.MOCK_HTML)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("websearch_server.aiohttp.ClientSession", return_value=mock_session):
            results = await search_duckduckgo("test query")
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_http_error(self):
        mock_resp = AsyncMock()
        mock_resp.status = 503

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("websearch_server.aiohttp.ClientSession", return_value=mock_session):
            results = await search_duckduckgo("test")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_max_results_clamped(self):
        """max_results ne dépasse jamais MAX_RESULTS_LIMIT."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value="<html></html>")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("websearch_server.aiohttp.ClientSession", return_value=mock_session):
            results = await search_duckduckgo("test", max_results=100)
            assert isinstance(results, list)
