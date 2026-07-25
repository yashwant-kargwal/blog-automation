"""Search-specific exception types."""


class SearchError(RuntimeError):
    """Base class for search failures."""


class SearchProviderError(SearchError):
    """Raised when DuckDuckGo Search cannot return results."""


class SearchCacheError(SearchError):
    """Raised when cache data cannot be read or written safely."""
