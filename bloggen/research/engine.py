"""Research search orchestration, deduplication, and caching."""

from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from loguru import logger

from bloggen.config.settings import ResearchSettings
from bloggen.core.logging import pipeline_step
from bloggen.research.cache import SearchCache
from bloggen.research.duckduckgo import DuckDuckGoSearchProvider
from bloggen.research.models import SearchRequest, SearchResponse, SearchResult


class SearchEngine:
    """Search facade consumed by future research workflows."""

    def __init__(self, settings: ResearchSettings) -> None:
        self.settings = settings
        self.provider = DuckDuckGoSearchProvider(settings)
        self.cache = SearchCache(settings.cache_directory, settings.cache_ttl_seconds)

    @pipeline_step("research.search")
    def search(self, request: SearchRequest) -> SearchResponse:
        """Return unique top-N results using configured search depth."""
        key = self.cache.key(request.query, request.depth, request.top_n, self.settings.backends)
        if request.use_cache:
            cached = self.cache.get(key)
            if cached is not None:
                logger.info("Search cache hit query={!r}", request.query)
                return cached

        fetch_limit = min(request.top_n * request.depth, 100)
        logger.info("Searching query={!r} top_n={} depth={}", request.query, request.top_n, request.depth)
        raw_results = self.provider.search(request.query, limit=fetch_limit)
        results = self._deduplicate(raw_results)[: request.top_n]
        response = SearchResponse(
            query=request.query,
            results=results,
            requested_top_n=request.top_n,
            depth=request.depth,
            backends=self.settings.backends,
            searched_at=datetime.now(timezone.utc),
        )
        if request.use_cache:
            self.cache.put(key, response)
        logger.info("Search completed query={!r} unique_results={}", request.query, len(results))
        return response

    @classmethod
    def _deduplicate(cls, results: list[SearchResult]) -> list[SearchResult]:
        """Deduplicate canonical URLs while preserving provider rank order."""
        unique: dict[str, SearchResult] = {}
        for result in results:
            canonical = cls._canonical_url(result.url)
            if canonical not in unique:
                unique[canonical] = result
        return [result.model_copy(update={"rank": rank}) for rank, result in enumerate(unique.values(), start=1)]

    @staticmethod
    def _canonical_url(url: str) -> str:
        """Normalize URLs and discard common tracking parameters."""
        parsed = urlsplit(url.strip())
        query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if not key.lower().startswith(("utm_", "fbclid", "gclid"))]
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower().rstrip("."), parsed.path.rstrip("/"), urlencode(query), "")).casefold()
