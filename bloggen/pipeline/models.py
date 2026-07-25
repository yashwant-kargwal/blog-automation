"""Pipeline state and result models."""

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class PipelineStage(StrEnum):
    """Ordered pipeline stages."""

    SEARCH = "search"
    SCRAPE = "scrape"
    RESEARCH = "research"
    SEO = "seo"
    WRITER = "writer"
    VALIDATOR = "validator"
    OUTPUT = "output"


class PipelineStatus(StrEnum):
    """Stage and run status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageReport(BaseModel):
    """Timing and outcome for one stage."""

    model_config = ConfigDict(extra="forbid")

    stage: PipelineStage
    status: PipelineStatus = PipelineStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    detail: str = ""
    error: str | None = None


class PipelineResult(BaseModel):
    """Complete production pipeline run result."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    topic: str
    status: PipelineStatus
    started_at: datetime
    completed_at: datetime
    stages: list[StageReport] = Field(min_length=1)
    output_directory: Path
    error: str | None = None
    execution_seconds: float = Field(ge=0)
    generated_title: str | None = None
    seo_score: float | None = Field(default=None, ge=0, le=100)
    confidence_score: float | None = Field(default=None, ge=0, le=100)
    files: list[Path] = Field(default_factory=list)
