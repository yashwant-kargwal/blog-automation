"""Scraper-specific exceptions."""


class ScraperError(RuntimeError):
    """Base class for scraping failures."""


class FetchError(ScraperError):
    """Raised when a page cannot be downloaded."""


class ExtractionError(ScraperError):
    """Raised when no useful article content can be extracted."""
