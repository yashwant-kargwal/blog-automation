"""Structured search domain models."""

from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchRequest(BaseModel):
    """Validated search input."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    top_n: int = Field(default=10, ge=1, le=100)
    depth: int = Field(default=1, ge=1, le=5)
    use_cache: bool = True

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Search query cannot be empty")
        return normalized


class SearchResult(BaseModel):
    """One normalized web search result."""

    model_config = ConfigDict(extra="ignore")

    rank: int = Field(ge=1)
    title: str
    url: str
    snippet: str = ""
    source: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Search result URL must be an absolute HTTP(S) URL")
        return value


class SearchResponse(BaseModel):
    """Structured search response returned by the engine."""

    model_config = ConfigDict(extra="forbid")

    query: str
    results: list[SearchResult]
    requested_top_n: int
    depth: int
    backends: list[str]
    cached: bool = False
    searched_at: datetime

    @property
    def total(self) -> int:
        """Return the number of unique results."""
        return len(self.results)
