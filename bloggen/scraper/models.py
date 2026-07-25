"""Structured scraper request, result, and failure models."""

from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScrapeRequest(BaseModel):
    """Validated page scraping input."""

    model_config = ConfigDict(extra="forbid")

    url: str
    use_cache: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        normalized = value.strip()
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Scrape URL must be an absolute HTTP(S) URL")
        return normalized


class ScrapedPage(BaseModel):
    """Clean article page returned by the scraper."""

    model_config = ConfigDict(extra="forbid")

    url: str
    final_url: str
    title: str = ""
    markdown: str = Field(min_length=1)
    word_count: int = Field(ge=1)
    content_hash: str
    status_code: int = Field(ge=100, le=599)
    extracted_at: datetime
    cached: bool = False


class ScrapeFailure(BaseModel):
    """Structured failure for one URL in a concurrent batch."""

    url: str
    error: str


class ScrapeBatch(BaseModel):
    """Ordered result of scraping multiple URLs."""

    pages: list[ScrapedPage]
    failures: list[ScrapeFailure]

    @property
    def total(self) -> int:
        """Return total URLs processed."""
        return len(self.pages) + len(self.failures)
