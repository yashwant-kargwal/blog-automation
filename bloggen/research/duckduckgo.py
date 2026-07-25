"""DuckDuckGo Search adapter backed by the maintained DDGS package."""

from typing import Any

from ddgs import DDGS
from loguru import logger

from bloggen.config.settings import ResearchSettings
from bloggen.research.exceptions import SearchProviderError
from bloggen.research.models import SearchResult


class DuckDuckGoSearchProvider:
    """Search DuckDuckGo and configured DDGS metasearch backends."""

    name = "duckduckgo"

    def __init__(self, settings: ResearchSettings) -> None:
        self.settings = settings

    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        """Fetch raw results from multiple configured search backends."""
        try:
            client = DDGS(timeout=self.settings.timeout_seconds)
            raw_results = client.text(
                query,
                region=self.settings.region,
                safesearch=self.settings.safe_search,
                max_results=limit,
                backend=",".join(self.settings.backends),
            )
        except Exception as exc:
            logger.exception("DuckDuckGo search failed for query={!r}", query)
            raise SearchProviderError("DuckDuckGo Search could not complete the query.") from exc

        results: list[SearchResult] = []
        for item in raw_results:
            normalized = self._normalize(item)
            if normalized is not None:
                results.append(normalized)
        return results

    @staticmethod
    def _normalize(item: dict[str, Any]) -> SearchResult | None:
        url = str(item.get("href", "")).strip()
        title = str(item.get("title", "")).strip()
        if not url or not title:
            return None
        try:
            from urllib.parse import urlparse

            return SearchResult(
                rank=1,
                title=title,
                url=url,
                snippet=str(item.get("body", "")).strip(),
                source=urlparse(url).netloc.lower(),
            )
        except ValueError:
            return None
