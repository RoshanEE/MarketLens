"""
Tests for the crawler service.

_extract_with_beautifulsoup is tested as a pure HTML-parsing function.
crawl_url is tested by patching _fetch_html to avoid real network calls.
"""

import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.crawler import (
    _extract_with_beautifulsoup,
    _extract_with_trafilatura,
    crawl_url,
)


# ---------------------------------------------------------------------------
# _extract_with_beautifulsoup
# ---------------------------------------------------------------------------

class TestExtractWithBeautifulSoup:
    def _html(self, body: str, title: str = "") -> str:
        title_tag = f"<title>{title}</title>" if title else ""
        return f"<html><head>{title_tag}</head><body>{body}</body></html>"

    def _long_p(self, text: str = "x", length: int = 60) -> str:
        return f"<p>{text * length}</p>"

    def test_extracts_title(self):
        html = self._html(self._long_p(), title="My Page")
        title, _ = _extract_with_beautifulsoup(html)
        assert title == "My Page"

    def test_no_title_returns_none(self):
        html = self._html(self._long_p())
        title, _ = _extract_with_beautifulsoup(html)
        assert title is None

    def test_extracts_paragraph_content(self):
        paragraph = "a" * 60
        html = self._html(f"<p>{paragraph}</p>")
        _, content = _extract_with_beautifulsoup(html)
        assert paragraph in content

    def test_joins_multiple_paragraphs(self):
        html = self._html(f"<p>{'a' * 60}</p><p>{'b' * 60}</p>")
        _, content = _extract_with_beautifulsoup(html)
        assert "a" * 60 in content
        assert "b" * 60 in content

    def test_filters_paragraphs_shorter_than_40_chars(self):
        html = self._html(f"<p>Short.</p>{self._long_p('y')}")
        _, content = _extract_with_beautifulsoup(html)
        assert "Short." not in content
        assert "y" * 60 in content

    def test_removes_script_tags(self):
        html = self._html(f"<script>evil()</script>{self._long_p()}")
        _, content = _extract_with_beautifulsoup(html)
        assert "evil()" not in content

    def test_removes_style_tags(self):
        html = self._html(f"<style>.x{{ color: red }}</style>{self._long_p()}")
        _, content = _extract_with_beautifulsoup(html)
        assert ".x{" not in content

    def test_removes_nav_footer_header_tags(self):
        main_p = "m" * 60
        html = self._html(
            f"<nav>Navigation</nav><header>Site Header</header>"
            f"<footer>Footer</footer><p>{main_p}</p>"
        )
        _, content = _extract_with_beautifulsoup(html)
        assert "Navigation" not in content
        assert "Site Header" not in content
        assert "Footer" not in content
        assert main_p in content

    def test_prefers_article_container_over_full_body(self):
        article_text = "a" * 60
        sidebar_text = "b" * 60
        html = self._html(
            f"<article><p>{article_text}</p></article>"
            f"<div><p>{sidebar_text}</p></div>"
        )
        _, content = _extract_with_beautifulsoup(html)
        assert article_text in content
        assert sidebar_text not in content

    def test_prefers_main_over_body_when_no_article(self):
        main_text = "m" * 60
        other_text = "o" * 60
        html = self._html(
            f"<main><p>{main_text}</p></main>"
            f"<div><p>{other_text}</p></div>"
        )
        _, content = _extract_with_beautifulsoup(html)
        assert main_text in content
        assert other_text not in content

    def test_no_qualifying_paragraphs_returns_none_content(self):
        html = self._html("<p>Too short.</p>")
        _, content = _extract_with_beautifulsoup(html)
        assert content is None


# ---------------------------------------------------------------------------
# crawl_url  (network calls replaced by patching _fetch_html)
# ---------------------------------------------------------------------------

def _make_html(body: str, title: str = "Test Page") -> str:
    return (
        f"<html><head><title>{title}</title></head>"
        f"<body>{body}</body></html>"
    )


@pytest.mark.asyncio
class TestCrawlUrl:
    async def test_successful_crawl_returns_success_status(self):
        html = _make_html("<p>" + "x" * 200 + "</p>")
        with patch("app.services.crawler._fetch_html", AsyncMock(return_value=html)):
            result = await crawl_url("https://example.com")

        assert result.status == "success"
        assert result.url == "https://example.com"
        assert result.content is not None
        assert result.crawled_at is not None

    async def test_content_hash_is_sha256_of_extracted_content(self):
        html = _make_html("<p>" + "a" * 300 + "</p>")
        with patch("app.services.crawler._fetch_html", AsyncMock(return_value=html)):
            result = await crawl_url("https://example.com")

        expected = hashlib.sha256(result.content.encode()).hexdigest()
        assert result.content_hash == expected

    async def test_fetch_error_returns_failed_status(self):
        with patch(
            "app.services.crawler._fetch_html",
            AsyncMock(side_effect=Exception("Connection refused")),
        ):
            result = await crawl_url("https://unreachable.example.com")

        assert result.status == "failed"
        assert result.content is None
        assert result.content_hash is None
        assert "Connection refused" in result.error

    async def test_no_extractable_content_returns_failed(self):
        html = _make_html("<div>No paragraphs here at all.</div>")
        with (
            patch("app.services.crawler._fetch_html", AsyncMock(return_value=html)),
            patch(
                "app.services.crawler._extract_with_trafilatura",
                return_value=(None, None),
            ),
        ):
            result = await crawl_url("https://example.com/empty")

        assert result.status == "failed"
        assert result.error is not None

    async def test_trafilatura_failure_falls_back_to_beautifulsoup(self):
        """When trafilatura returns no content, BS4 result is used."""
        bs4_content = "b" * 200
        html = _make_html(f"<article><p>{bs4_content}</p></article>")
        with (
            patch("app.services.crawler._fetch_html", AsyncMock(return_value=html)),
            patch(
                "app.services.crawler._extract_with_trafilatura",
                return_value=(None, None),
            ),
        ):
            result = await crawl_url("https://example.com")

        assert result.status == "success"
        assert bs4_content in result.content

    async def test_title_from_trafilatura_preserved(self):
        html = _make_html("<p>" + "x" * 200 + "</p>", title="Trafilatura Title")
        with (
            patch("app.services.crawler._fetch_html", AsyncMock(return_value=html)),
            patch(
                "app.services.crawler._extract_with_trafilatura",
                return_value=("Trafilatura Title", "x" * 200),
            ),
        ):
            result = await crawl_url("https://example.com")

        assert result.title == "Trafilatura Title"
