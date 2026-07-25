"""Structured validation result models."""

from pydantic import BaseModel, ConfigDict, Field


class Score(BaseModel):
    """Named score on a 0-100 scale."""

    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0, le=100)
    label: str
    rationale: str


class WeakSection(BaseModel):
    """Section-level quality issue."""

    heading: str
    issue: str
    words: int = Field(ge=0)


class ValidationResult(BaseModel):
    """Complete generated blog validation report."""

    model_config = ConfigDict(extra="forbid")

    seo: Score
    grammar: Score
    readability: Score
    confidence: Score
    duplicate_risk: Score
    weak_sections: list[WeakSection]
    suggestions: list[str]
    overall_rating: str
    overall_score: float = Field(ge=0, le=100)
    word_count: int = Field(ge=0)
