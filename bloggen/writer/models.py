"""Structured blog writer models."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BlogPost(BaseModel):
    """A validated, publication-ready Markdown blog post."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    style: str = Field(min_length=1)
    markdown: str = Field(min_length=1)
    word_count: int = Field(ge=1)
    source_urls: list[str] = Field(min_length=1)
    generated_at: datetime
    model: str

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        normalized = value.strip().strip("/").lower()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
            raise ValueError("slug must contain lowercase words separated by hyphens")
        return normalized


class WriterInput(BaseModel):
    """Input bundle for a blog writing request."""

    model_config = ConfigDict(arbitrary_types_allowed=False, extra="forbid")

    research_json: str = Field(min_length=1)
    seo_json: str = Field(min_length=1)
    style: str = Field(min_length=1)
