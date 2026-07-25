"""Production pipeline orchestration over independent Bloggen modules."""

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from bloggen.config.settings import Settings
from bloggen.core.logging import pipeline_step
from bloggen.pipeline.exceptions import PipelineError
from bloggen.pipeline.models import PipelineResult, PipelineStage, PipelineStatus, StageReport
from bloggen.research.analyzer import ResearchAnalyzer
from bloggen.research.engine import SearchEngine
from bloggen.research.models import SearchRequest, SearchResponse
from bloggen.scraper.engine import WebScraper
from bloggen.scraper.models import ScrapeRequest, ScrapeBatch
from bloggen.seo.engine import SEOEngine
from bloggen.seo.models import SEOPlan
from bloggen.storage.project import ProjectStore
from bloggen.validation.engine import ValidationEngine
from bloggen.validation.models import ValidationResult
from bloggen.writer.engine import BlogWriter
from bloggen.writer.models import BlogPost


class ProductionPipeline:
    """Run Topic → Search → Scrape → Research → SEO → Writer → Validator → Output."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.search = SearchEngine(settings.research)
        self.scraper = WebScraper(settings.scraper)
        self.research = ResearchAnalyzer(settings)
        self.seo = SEOEngine(settings)
        self.writer = BlogWriter(settings)
        self.validator = ValidationEngine()

    @pipeline_step("pipeline.run")
    def run(self, topic: str, *, style: str | None = None, use_cache: bool = True) -> PipelineResult:
        """Run the pipeline and return a graceful result on the first failure."""
        normalized_topic = " ".join(topic.split())
        if not normalized_topic:
            raise PipelineError("Pipeline topic cannot be empty.")
        started = datetime.now(timezone.utc)
        project = ProjectStore.create(self.settings.storage.projects_directory, normalized_topic)
        reports = [StageReport(stage=stage) for stage in PipelineStage]
        state = _RunState(uuid.uuid4().hex, normalized_topic, started, project, reports)
        logger.info("pipeline.run.start run_id={} topic={!r} project={}", state.run_id, normalized_topic, project.path)

        search_result = self._stage(state, PipelineStage.SEARCH, lambda: self.search.search(SearchRequest(query=normalized_topic, top_n=self.settings.pipeline.top_n, depth=self.settings.pipeline.depth, use_cache=use_cache)))
        if search_result is None:
            return self._finish_failure(state)
        project.save_json("research", "search.json", search_result.model_dump(mode="json"))

        urls = [item.url for item in search_result.results[: self.settings.pipeline.max_articles]]
        scrape_result = self._stage(state, PipelineStage.SCRAPE, lambda: self.scraper.scrape_many([ScrapeRequest(url=url, use_cache=use_cache) for url in urls]))
        if scrape_result is None:
            return self._finish_failure(state)
        if not scrape_result.pages:
            self._mark_failure(state, PipelineStage.SCRAPE, "No articles could be scraped.")
            return self._finish_failure(state)
        for index, page in enumerate(scrape_result.pages, start=1):
            project.save_markdown(f"source-{index:03d}.md", page.markdown)
            project.save_html(f"source-{index:03d}.html", page.markdown, title=page.title or page.url)
        project.save_json("research", "scrape.json", scrape_result.model_dump(mode="json"))

        research_result = self._stage(state, PipelineStage.RESEARCH, lambda: self.research.analyze(scrape_result.pages, normalized_topic, use_cache=use_cache))
        if research_result is None:
            return self._finish_failure(state)
        project.save_json("research", "research.json", research_result.model_dump(mode="json"))

        seo_result = self._stage(state, PipelineStage.SEO, lambda: self.seo.generate(research_result, normalized_topic, use_cache=use_cache))
        if seo_result is None:
            return self._finish_failure(state)
        state.seo_score = None
        project.save_json("seo", "seo.json", seo_result.model_dump(mode="json"))

        post_result = self._stage(state, PipelineStage.WRITER, lambda: self.writer.write(research_result, seo_result, style=style, use_cache=use_cache))
        if post_result is None:
            return self._finish_failure(state)
        state.generated_title = post_result.title
        project.save_markdown("article.md", post_result.markdown)
        project.save_html("article.html", post_result.markdown, title=post_result.title)

        validation_result = self._stage(state, PipelineStage.VALIDATOR, lambda: self.validator.validate(post_result.markdown, seo=seo_result, research=research_result, source_urls=post_result.source_urls))
        if validation_result is None:
            return self._finish_failure(state)
        state.seo_score = validation_result.seo.score
        state.confidence_score = validation_result.confidence.score
        project.save_json("metadata", "validation.json", validation_result.model_dump(mode="json"))

        output_result = self._stage(state, PipelineStage.OUTPUT, lambda: self._save_output(state, research_result, seo_result, post_result, validation_result))
        if output_result is None:
            return self._finish_failure(state)
        state.status = PipelineStatus.SUCCEEDED
        return self._finish(state)

    def _stage(self, state: "_RunState", stage: PipelineStage, operation: Callable[[], Any]) -> Any | None:
        report = state.report(stage)
        report.status = PipelineStatus.RUNNING
        report.started_at = datetime.now(timezone.utc)
        logger.info("pipeline.stage.start run_id={} stage={}", state.run_id, stage.value)
        try:
            result = operation()
        except Exception as exc:
            self._mark_failure(state, stage, str(exc))
            logger.exception("pipeline.stage.error run_id={} stage={}", state.run_id, stage.value)
            return None
        report.status = PipelineStatus.SUCCEEDED
        report.completed_at = datetime.now(timezone.utc)
        report.detail = self._detail(result)
        logger.success("pipeline.stage.success run_id={} stage={}", state.run_id, stage.value)
        return result

    def _save_output(self, state: "_RunState", research: Any, seo: SEOPlan, post: BlogPost, validation: ValidationResult) -> str:
        state.project.save_log_snapshot(self.settings.logging.log_directory / "bloggen.log")
        return state.project.project_id

    def _finish_failure(self, state: "_RunState") -> PipelineResult:
        state.status = PipelineStatus.FAILED
        state.project.save_log_snapshot(self.settings.logging.log_directory / "bloggen.log")
        return self._finish(state)

    @staticmethod
    def _mark_failure(state: "_RunState", stage: PipelineStage, error: str) -> None:
        report = state.report(stage)
        report.status = PipelineStatus.FAILED
        report.completed_at = datetime.now(timezone.utc)
        report.error = error
        state.error = error
        seen = False
        for item in state.reports:
            if item.stage == stage:
                seen = True
            elif seen and item.status == PipelineStatus.PENDING:
                item.status = PipelineStatus.SKIPPED
                item.detail = "Stopped after upstream failure."

    @staticmethod
    def _detail(result: Any) -> str:
        if isinstance(result, SearchResponse):
            return f"{len(result.results)} search result(s)"
        if isinstance(result, ScrapeBatch):
            return f"{len(result.pages)} page(s), {len(result.failures)} failure(s)"
        if isinstance(result, BlogPost):
            return f"{result.word_count} words"
        if isinstance(result, ValidationResult):
            return f"{result.overall_rating} ({result.overall_score:.1f}/100)"
        return "completed"

    def _finish(self, state: "_RunState") -> PipelineResult:
        completed = datetime.now(timezone.utc)
        result = PipelineResult(
            run_id=state.run_id,
            topic=state.topic,
            status=state.status,
            started_at=state.started_at,
            completed_at=completed,
            stages=state.reports,
            output_directory=state.project.path or Path("."),
            error=state.error,
            execution_seconds=round((completed - state.started_at).total_seconds(), 3),
            generated_title=state.generated_title,
            seo_score=state.seo_score,
            confidence_score=state.confidence_score,
        )
        if state.status == PipelineStatus.FAILED:
            state.project.save_json("metadata", "pipeline.json", result.model_dump(mode="json"))
            state.project.finalize(kind="pipeline", status="failed", topic=state.topic, error=state.error)
        else:
            state.project.save_json("metadata", "pipeline.json", result.model_dump(mode="json"))
            state.project.finalize(kind="pipeline", status="succeeded", topic=state.topic)
        result.files = [path for path in state.project.path.rglob("*") if path.is_file()] if state.project.path else []
        return result


class _RunState:
    """Mutable internal state kept out of the public result contract."""

    def __init__(self, run_id: str, topic: str, started_at: datetime, project: ProjectStore, reports: list[StageReport]) -> None:
        self.run_id = run_id
        self.topic = topic
        self.started_at = started_at
        self.project = project
        self.reports = reports
        self.status = PipelineStatus.RUNNING
        self.error: str | None = None
        self.generated_title: str | None = None
        self.seo_score: float | None = None
        self.confidence_score: float | None = None

    def report(self, stage: PipelineStage) -> StageReport:
        return next(item for item in self.reports if item.stage == stage)
