"""Structured SEO plan models."""

import re
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SuggestedImage(BaseModel):
    """One editorial image recommendation."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1)
    alt_text: str = Field(min_length=1, max_length=160)
    placement: str = Field(min_length=1)
    image_type: str = Field(min_length=1)


class Heading(BaseModel):
    """One heading in the recommended article outline."""

    model_config = ConfigDict(extra="forbid")

    level: int = Field(ge=1, le=6)
    text: str = Field(min_length=1, max_length=120)
    purpose: str = Field(min_length=1)


class SEOFAQ(BaseModel):
    """FAQ entry for an article plan."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    answer_direction: str = Field(min_length=1)


class InternalLinkSuggestion(BaseModel):
    """A link opportunity that does not invent an unknown URL."""

    model_config = ConfigDict(extra="forbid")

    anchor_text: str = Field(min_length=1)
    target_topic: str = Field(min_length=1)
    placement: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    target_url: str | None = None

    @field_validator("target_url")
    @classmethod
    def validate_target_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("target_url must be an absolute HTTP(S) URL")
        return value


class SEOPlan(BaseModel):
    """Complete structured SEO plan."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    seo_title: str = Field(min_length=1, max_length=70)
    meta_description: str = Field(min_length=1, max_length=180)
    slug: str = Field(min_length=1, max_length=100)
    primary_keyword: str = Field(min_length=1)
    secondary_keywords: list[str] = Field(default_factory=list)
    lsi_keywords: list[str] = Field(default_factory=list)
    suggested_images: list[SuggestedImage] = Field(default_factory=list)
    target_word_count: int = Field(ge=300, le=100000)
    faq: list[SEOFAQ] = Field(default_factory=list)
    heading_structure: list[Heading] = Field(min_length=1)
    internal_linking_suggestions: list[InternalLinkSuggestion] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    generated_at: datetime
    model: str

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        normalized = value.strip().strip("/").lower()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
            raise ValueError("slug must contain lowercase words separated by hyphens")
        return normalized
