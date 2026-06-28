"""
Web crawler service.
Primary extractor: Trafilatura (article-quality content extraction).
Fallback extractor: BeautifulSoup (heuristic paragraph extraction).
"""

import hashlib
import asyncio
from datetime import datetime, timezone
from dataclasses import dataclass

import httpx
import trafilatura
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import get_settings
from app.models.enums import CrawlStatus

settings = get_settings()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; MarketLens/1.0; +https://github.com/marketlens)"
    )
}


@dataclass
class CrawlResult:
    url: str
    title: str | None
    content: str | None
    content_hash: str | None
    status: CrawlStatus
    error: str | None = None
    crawled_at: datetime | None = None


def _extract_with_trafilatura(html: str, url: str) -> tuple[str | None, str | None]:
    """Returns (title, content) using Trafilatura."""
    content = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
        favor_precision=True,
    )
    metadata = trafilatura.extract_metadata(html, default_url=url)
    title = metadata.title if metadata else None
    return title, content


def _extract_with_beautifulsoup(html: str) -> tuple[str | None, str | None]:
    """Fallback: extracts <title> and visible paragraph text via BeautifulSoup."""
    soup = BeautifulSoup(html, "lxml")

    # Remove noisy tags
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else None

    # Prefer <article> or <main>, otherwise fall back to all <p>
    container = soup.find("article") or soup.find("main") or soup
    paragraphs = container.find_all("p")
    content = "\n\n".join(p.get_text(separator=" ", strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40)
    return title, content or None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.TransportError),
    reraise=True,
)
async def _fetch_html(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url, headers=HEADERS, follow_redirects=True)
    response.raise_for_status()
    return response.text


async def crawl_url(url: str) -> CrawlResult:
    """Fetch and extract clean text content from a single URL."""
    async with httpx.AsyncClient(timeout=settings.crawler_timeout_seconds) as client:
        try:
            html = await _fetch_html(client, url)
        except Exception as exc:
            return CrawlResult(url=url, title=None, content=None, content_hash=None, status=CrawlStatus.FAILED, error=str(exc))

    # Try Trafilatura first
    title, content = _extract_with_trafilatura(html, url)

    # Fall back to BeautifulSoup if Trafilatura returns nothing
    if not content:
        title_bs, content_bs = _extract_with_beautifulsoup(html)
        title = title or title_bs
        content = content_bs

    if not content:
        return CrawlResult(
            url=url, title=title, content=None, content_hash=None,
            status=CrawlStatus.FAILED, error="No extractable content found."
        )

    content_hash = hashlib.sha256(content.encode()).hexdigest()
    return CrawlResult(
        url=url,
        title=title,
        content=content,
        content_hash=content_hash,
        status=CrawlStatus.SUCCESS,
        crawled_at=datetime.now(timezone.utc),
    )


async def crawl_urls(urls: list[str]) -> list[CrawlResult]:
    """Crawl multiple URLs concurrently."""
    return await asyncio.gather(*[crawl_url(url) for url in urls])
