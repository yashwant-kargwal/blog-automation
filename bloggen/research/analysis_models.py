"""Grounded structured research models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class GroundedItem(BaseModel):
    """A claim with direct evidence and one or more source URLs."""

    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1)
    evidence: str = Field(min_length=1, description="Verbatim excerpt from a supplied article")
    citations: list[HttpUrl] = Field(min_length=1)


class Statistic(GroundedItem):
    """A source-backed statistic."""

    value: str = Field(min_length=1)


class ImportantConcept(GroundedItem):
    """A source-backed concept and explanation."""

    name: str = Field(min_length=1)


class FrequentlyAskedQuestion(GroundedItem):
    """A source-backed question and answer."""

    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)


class Quote(BaseModel):
    """A verbatim quote with attribution and citation."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    attribution: str = "Unknown"
    evidence: str = Field(min_length=1)
    citations: list[HttpUrl] = Field(min_length=1)


class ResearchSource(BaseModel):
    """Source metadata included in the JSON artifact."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    title: str = ""
    content_hash: str


class StructuredResearch(BaseModel):
    """Complete grounded research artifact."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    generated_at: datetime
    model: str
    sources: list[ResearchSource] = Field(min_length=1)
    facts: list[GroundedItem] = Field(default_factory=list)
    statistics: list[Statistic] = Field(default_factory=list)
    important_concepts: list[ImportantConcept] = Field(default_factory=list)
    frequently_asked_questions: list[FrequentlyAskedQuestion] = Field(default_factory=list)
    quotes: list[Quote] = Field(default_factory=list)
    key_takeaways: list[GroundedItem] = Field(default_factory=list)
    discarded_items: int = Field(default=0, ge=0)


class AnalysisEnvelope(BaseModel):
    """Strict model-only payload before source validation."""

    model_config = ConfigDict(extra="forbid")

    facts: list[GroundedItem] = Field(default_factory=list)
    statistics: list[Statistic] = Field(default_factory=list)
    important_concepts: list[ImportantConcept] = Field(default_factory=list)
    frequently_asked_questions: list[FrequentlyAskedQuestion] = Field(default_factory=list)
    quotes: list[Quote] = Field(default_factory=list)
    key_takeaways: list[GroundedItem] = Field(default_factory=list)
