"""
Tests unitaires — News Server (RSS)
Teste le parsing RSS, le nettoyage HTML, le parsing de dates et la déduplication.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from news_server import _clean_html, _parse_rss_date, RSS_FEEDS


class TestCleanHTML:
    """Tests du nettoyage HTML dans les descriptions RSS."""

    def test_strip_tags(self):
        assert _clean_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_strip_img(self):
        result = _clean_html('<img src="photo.jpg"/>Some text')
        assert "img" not in result
        assert "Some text" in result

    def test_empty_string(self):
        assert _clean_html("") == ""

    def test_entities(self):
        result = _clean_html("&amp; &lt; &gt;")
        assert "&" in result

    def test_plain_text_passthrough(self):
        assert _clean_html("Just plain text") == "Just plain text"

    def test_nested_tags(self):
        result = _clean_html("<div><p><span>Deep</span> text</p></div>")
        assert "Deep" in result
        assert "text" in result


class TestRSSFeedsConfig:
    """Tests de la configuration des flux RSS."""

    def test_french_general_feeds_exist(self):
        assert "fr" in RSS_FEEDS
        assert "general" in RSS_FEEDS["fr"]
        assert len(RSS_FEEDS["fr"]["general"]) > 0

    def test_english_feeds_exist(self):
        assert "en" in RSS_FEEDS
        assert "general" in RSS_FEEDS["en"]

    def test_tech_category_exists(self):
        assert "tech" in RSS_FEEDS["fr"]
        assert len(RSS_FEEDS["fr"]["tech"]) > 0

    def test_science_category_exists(self):
        assert "science" in RSS_FEEDS["fr"]
        assert len(RSS_FEEDS["fr"]["science"]) > 0

    def test_all_feeds_are_urls(self):
        for region in RSS_FEEDS:
            for topic in RSS_FEEDS[region]:
                for url in RSS_FEEDS[region][topic]:
                    assert url.startswith("http"), f"Invalid feed URL: {url}"


class TestParseRSSDate:
    """Tests du parsing de dates RSS (RFC 2822 et ISO 8601)."""

    def test_rfc2822_with_tz_offset(self):
        dt = _parse_rss_date("Mon, 15 Jan 2024 14:30:00 +0100")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 14

    def test_rfc2822_with_gmt(self):
        dt = _parse_rss_date("Tue, 20 Feb 2024 08:00:00 GMT")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 2

    def test_iso8601_with_tz(self):
        dt = _parse_rss_date("2024-03-10T12:00:00+02:00")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 3

    def test_iso8601_utc_z(self):
        dt = _parse_rss_date("2024-06-01T09:30:00Z")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 6

    def test_invalid_date(self):
        assert _parse_rss_date("not a date") is None

    def test_empty_string(self):
        assert _parse_rss_date("") is None

    def test_whitespace_stripped(self):
        dt = _parse_rss_date("  2024-06-01T09:30:00Z  ")
        assert dt is not None


class TestDeduplication:
    """Tests de la déduplication par titre."""

    def test_duplicate_titles_removed(self):
        articles = [
            {"title": "Breaking News", "url": "https://a.com", "summary": "", "published": "", "source": "a.com"},
            {"title": "Breaking News", "url": "https://b.com", "summary": "", "published": "", "source": "b.com"},
            {"title": "Other News", "url": "https://c.com", "summary": "", "published": "", "source": "c.com"},
        ]
        seen: set[str] = set()
        unique = []
        for a in articles:
            key = a["title"].lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(a)
        assert len(unique) == 2
        assert unique[0]["url"] == "https://a.com"
        assert unique[1]["title"] == "Other News"

    def test_case_insensitive_dedup(self):
        articles = [
            {"title": "Test Title", "url": "1", "summary": "", "published": "", "source": ""},
            {"title": "test title", "url": "2", "summary": "", "published": "", "source": ""},
        ]
        seen: set[str] = set()
        unique = []
        for a in articles:
            key = a["title"].lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(a)
        assert len(unique) == 1


class TestTopicRegionDefaults:
    """Tests des valeurs par défaut topic/region."""

    def test_unknown_region_falls_back_to_fr(self):
        region = "de"
        resolved = region.lower() if region.lower() in RSS_FEEDS else "fr"
        assert resolved == "fr"

    def test_unknown_topic_falls_back_to_general(self):
        region = "fr"
        topic = "sports"
        resolved = topic.lower() if topic.lower() in RSS_FEEDS[region] else "general"
        assert resolved == "general"

    def test_valid_region_en(self):
        region = "en"
        resolved = region.lower() if region.lower() in RSS_FEEDS else "fr"
        assert resolved == "en"

    def test_valid_topic_tech(self):
        region = "fr"
        topic = "tech"
        resolved = topic.lower() if topic.lower() in RSS_FEEDS[region] else "general"
        assert resolved == "tech"
