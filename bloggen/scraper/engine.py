"""Concurrent HTTP fetching and article scraping."""

import asyncio
import hashlib
from collections.abc import Iterable
from datetime import datetime, timezone

import httpx
from loguru import logger

from bloggen.config.settings import ScraperSettings
from bloggen.core.logging import pipeline_step
from bloggen.scraper.cache import PageCache
from bloggen.scraper.exceptions import FetchError
from bloggen.scraper.extractor import extract_article
from bloggen.scraper.models import ScrapeBatch, ScrapeFailure, ScrapeRequest, ScrapedPage


class WebScraper:
    """Async-first scraper with bounded concurrency and page caching."""

    def __init__(self, settings: ScraperSettings) -> None:
        self.settings = settings
        self.cache = PageCache(settings.cache_directory, settings.cache_ttl_seconds)

    @pipeline_step("scraper.scrape")
    async def scrape(self, request: ScrapeRequest, client: httpx.AsyncClient | None = None) -> ScrapedPage:
        """Fetch and extract one page."""
        if request.use_cache:
            cached = self.cache.get(request.url)
            if cached is not None:
                logger.info("Page cache hit url={}", request.url)
                return cached
        owns_client = client is None
        active_client = client or self._client()
        try:
            response = await self._fetch(active_client, request.url)
            title, markdown = extract_article(response.text, str(response.url))
            page = ScrapedPage(
                url=request.url,
                final_url=str(response.url),
                title=title,
                markdown=markdown,
                word_count=len(markdown.split()),
                content_hash=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
                status_code=response.status_code,
                extracted_at=datetime.now(timezone.utc),
            )
            if request.use_cache:
                self.cache.put(page)
            return page
        finally:
            if owns_client:
                await active_client.aclose()

    @pipeline_step("scraper.scrape_many")
    async def scrape_many(self, requests: Iterable[ScrapeRequest]) -> ScrapeBatch:
        """Scrape URLs concurrently while preserving input order within each outcome."""
        request_list = list(requests)
        semaphore = asyncio.Semaphore(self.settings.concurrency)
        async with self._client() as client:
            async def run(request: ScrapeRequest) -> ScrapedPage | ScrapeFailure:
                async with semaphore:
                    try:
                        return await self.scrape(request, client)
                    except Exception as exc:
                        logger.error("Scrape failed url={} error={}", request.url, exc)
                        return ScrapeFailure(url=request.url, error=str(exc))

            outcomes = await asyncio.gather(*(run(request) for request in request_list))
        return ScrapeBatch(
            pages=[outcome for outcome in outcomes if isinstance(outcome, ScrapedPage)],
            failures=[outcome for outcome in outcomes if isinstance(outcome, ScrapeFailure)],
        )

    def scrape_urls(self, urls: Iterable[str], *, use_cache: bool = True) -> ScrapeBatch:
        """Synchronous convenience wrapper for CLI and scripts."""
        requests = [ScrapeRequest(url=url, use_cache=use_cache) for url in urls]
        return asyncio.run(self.scrape_many(requests))

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.settings.timeout_seconds),
            follow_redirects=True,
            headers={"User-Agent": self.settings.user_agent, "Accept": "text/html,application/xhtml+xml"},
        )

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        """Fetch with bounded exponential retries for transient failures."""
        attempts = self.settings.max_retries + 1
        for attempt in range(attempts):
            try:
                response = await client.get(url)
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if content_type and "html" not in content_type and "xhtml" not in content_type:
                    raise FetchError(f"Unsupported content type: {content_type}")
                return response
            except FetchError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                retryable = isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)) or getattr(exc.response, "status_code", 0) in {429, 500, 502, 503, 504}
                if not retryable or attempt == attempts - 1:
                    logger.error("HTTP fetch failed url={} attempts={}", url, attempt + 1)
                    raise FetchError(f"Could not fetch URL after {attempt + 1} attempt(s): {url}") from exc
                delay = self.settings.retry_backoff_seconds * (2**attempt)
                logger.warning("HTTP fetch retry url={} delay={}s", url, delay)
                await asyncio.sleep(delay)
        raise FetchError(f"Could not fetch URL: {url}")
